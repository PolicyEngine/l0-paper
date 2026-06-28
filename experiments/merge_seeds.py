#!/usr/bin/env python
"""Stitch per-seed ``l0 sweep`` runs into one combined run directory.

When the calibration seeds are run in *separate* invocations of ``l0 sweep``
(one process per seed, for 3-way parallelism), each run directory holds only one
seed's rows. The frontier figures/tables average across seeds, so they need the
union. This concatenates the per-seed ``metrics_long.csv`` and
``target_diagnostics_long.csv`` verbatim (raw CSV rows, no float reparsing) into
the combined layout ``l0 sweep`` would have produced had ``--seeds 0 1 2`` run in
one process, so ``l0 figures --sweep <out>`` can render the multi-seed report.

It invents no numbers. Rows are copied as-is; only the manifest is rebuilt to
describe the union. It refuses unless the inputs are identical in every respect
except their ``seed`` set -- same precalibration frame, budgets, holdout split,
target weighting/cap, rotation config, optimizer settings, l2 lambdas -- so a
stray config difference cannot silently confound the seed average.

Example
-------
    uv run python experiments/merge_seeds.py \
        --inputs runs/4way-l1-cap1/seed0 \
                 runs/4way-l1-cap1/seed1 \
                 runs/4way-l1-cap1/seed2 \
        --out runs/4way-l1-cap1 \
        --run-id 4way-l1-cap1

Then:
    uv run --extra viz python -m l0_paper.cli figures \
        --sweep runs/4way-l1-cap1 --anchor-budget 10000 --paper-figures
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

METRICS_CSV = "metrics_long.csv"
TARGET_DIAGNOSTICS_CSV = "target_diagnostics_long.csv"
MANIFEST_JSON = "sweep_manifest.json"
DEGENERATE_CSV = "degenerate_targets.csv"

# Manifest keys that must match across inputs (everything that defines the
# experiment except the seed grid). A mismatch here would confound the average.
_MUST_MATCH = (
    "precalibration_dir",
    "target_loss",
    "frontier_split",
    "rotation",
    "l0_optimizer",
    "baseline_optimizer",
)
_MUST_MATCH_GRID = ("budgets", "epochs", "l2_lambdas")


def _read_lines(path: Path) -> tuple[str, list[str]]:
    """Return (header_line, data_lines) for a CSV; ('', []) if absent."""
    if not path.is_file():
        return "", []
    lines = path.read_text().splitlines(keepends=True)
    if not lines:
        return "", []
    return lines[0], lines[1:]


def _concat_csv(inputs: list[Path], name: str, out: Path) -> int:
    headers = set()
    header = ""
    data: list[str] = []
    for d in inputs:
        h, rows = _read_lines(d / name)
        if not h:
            continue
        headers.add(h)
        header = h
        data.extend(rows)
    if not header:
        return 0
    if len(headers) > 1:
        raise SystemExit(
            f"merge_seeds: {name} headers differ across inputs; refusing to merge."
        )
    text = header + ("" if header.endswith("\n") else "\n") + "".join(data)
    (out / name).write_text(text)
    return len(data)


def _check_compatible(manifests: list[dict]) -> None:
    ref = manifests[0]
    for m in manifests[1:]:
        for key in _MUST_MATCH:
            if m.get(key) != ref.get(key):
                raise SystemExit(
                    f"merge_seeds: input manifests differ on {key!r}; refusing to "
                    "merge (would confound the seed average). Re-run the seeds with "
                    "identical config."
                )
        for key in _MUST_MATCH_GRID:
            if m.get("grid", {}).get(key) != ref.get("grid", {}).get(key):
                raise SystemExit(
                    f"merge_seeds: input manifests differ on grid.{key!r}; refusing."
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        required=True,
        help="Per-seed sweep run directories to combine.",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Combined output directory."
    )
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    inputs = [d.resolve() for d in args.inputs]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    manifests = []
    for d in inputs:
        mpath = d / MANIFEST_JSON
        if not mpath.is_file():
            raise SystemExit(f"merge_seeds: missing manifest: {mpath}")
        manifests.append(json.loads(mpath.read_text()))
    _check_compatible(manifests)

    n_metrics = _concat_csv(inputs, METRICS_CSV, out)
    n_diag = _concat_csv(inputs, TARGET_DIAGNOSTICS_CSV, out)

    # Degenerate-target audit is a property of the split, identical across seeds.
    for d in inputs:
        src = d / DEGENERATE_CSV
        if src.is_file():
            shutil.copy2(src, out / DEGENERATE_CSV)
            break

    seeds = sorted({s for m in manifests for s in m.get("grid", {}).get("seeds", [])})
    combined = dict(manifests[0])
    combined["run_id"] = args.run_id or combined.get("run_id")
    combined["status"] = "merged_seeds"
    combined["updated_at"] = datetime.now(UTC).isoformat()
    combined.setdefault("grid", {})["seeds"] = seeds
    combined["n_rows"] = n_metrics
    combined["n_target_diagnostic_rows"] = n_diag
    combined["merged_from"] = [str(d) for d in inputs]
    combined["long_csv"] = str(out / METRICS_CSV)
    combined["target_diagnostics_csv"] = (
        str(out / TARGET_DIAGNOSTICS_CSV) if n_diag else None
    )
    (out / MANIFEST_JSON).write_text(json.dumps(combined, indent=2))

    print(
        f"Merged {len(inputs)} seed runs (seeds={seeds}): "
        f"{n_metrics:,} metric rows, {n_diag:,} diagnostic rows -> {out}"
    )


if __name__ == "__main__":
    main()
