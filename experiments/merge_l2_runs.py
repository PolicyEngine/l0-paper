#!/usr/bin/env python
"""Merge single-``l2_lambda`` sweep runs into one combined run directory.

When the L2 penalties are swept in *separate* invocations of ``run_sweep.py``
(one run per ``l2_lambda``), each run directory holds only one penalty value, so
the figures that contrast penalties -- F6 operability (ESS / accuracy vs
``lambda_L2``) and the multi-``l2`` table columns -- cannot be drawn from any one
directory. This tool stitches those runs back into the single combined layout
``run_sweep.py`` would have produced had ``--l2-lambdas`` listed every penalty at
once (the ``expanded-3seed`` layout), so ``figures.py`` can render the L2
comparison.

It invents no numbers. Every metric row is copied verbatim (raw CSV text, no
float reparsing) from the source runs; only the manifest is rebuilt to describe
the union. Before merging it *refuses* unless the inputs are identical in every
respect except their ``l2_lambda`` -- same precalibration frame, budgets, seeds,
holdout split, target weighting, rotation config, optimizer settings. That guard
is what makes the resulting comparison honest: a difference in any other
dimension would silently confound the penalty effect, so the merge aborts
instead.

Example
-------
    uv run python experiments/merge_l2_runs.py \
        --inputs experiments/runs/weighted-loss-3seed/0l2 \
                 experiments/runs/weighted-loss-3seed/1l2 \
        --out experiments/runs/weighted-loss-3seed \
        --run-id weighted-loss-3seed

Then regenerate the report (note ``--sweep`` reads the merged metrics_long.csv):

    uv run --extra viz python experiments/figures.py \
        --sweep experiments/runs/weighted-loss-3seed
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l0_paper.experiments import aggregate
from l0_paper.experiments.artifacts import write_run_manifest

# Manifest fields that are *expected* to differ between per-penalty runs and so
# are excluded from the "identical except l2" comparability check below. Every
# other field must match exactly or the merge aborts.
_EXPECTED_TO_DIFFER_TOP = (
    "run_id",
    "created_at",
    "long_csv",
    "target_diagnostics_csv",
    "merged_from",
    "frontier_dense_runtimes_s",  # keyed by l2; unioned, not compared
    "n_rows",
)
_EXPECTED_TO_DIFFER_NESTED = {
    "command_args": ("run_id", "out", "l2_lambdas"),
    "grid": ("l2_lambdas",),
    "l0_optimizer": ("l2_lambdas",),
}


def _canonical_for_compare(manifest: dict[str, Any]) -> dict[str, Any]:
    """Strip the l2-related / path / timestamp fields so the rest can be compared."""
    m = copy.deepcopy(manifest)
    for key in _EXPECTED_TO_DIFFER_TOP:
        m.pop(key, None)
    for parent, children in _EXPECTED_TO_DIFFER_NESTED.items():
        if isinstance(m.get(parent), dict):
            for child in children:
                m[parent].pop(child, None)
    return m


def _first_difference(a: Any, b: Any, path: str = "") -> str | None:
    """Return a human-readable path to the first structural difference, or None."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return f"{path}.{key} (missing in first run)"
            if key not in b:
                return f"{path}.{key} (missing in other run)"
            diff = _first_difference(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path} (length {len(a)} vs {len(b)})"
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            diff = _first_difference(x, y, f"{path}[{i}]")
            if diff:
                return diff
        return None
    if a != b:
        return f"{path} ({a!r} vs {b!r})"
    return None


def _read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "sweep_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"No sweep_manifest.json in {run_dir}")
    return json.loads(path.read_text())


def _l2_of(manifest: dict[str, Any], run_dir: Path) -> float:
    """The single l2_lambda this run swept, taken from grid.l2_lambdas."""
    l2s = manifest.get("grid", {}).get("l2_lambdas")
    if not isinstance(l2s, list) or len(l2s) != 1:
        raise ValueError(
            f"{run_dir}: expected exactly one l2_lambda in grid.l2_lambdas, "
            f"got {l2s!r}. This tool merges single-penalty runs only."
        )
    return float(l2s[0])


def _read_csv_lines(path: Path) -> tuple[str, list[str]]:
    """Return (header_line, data_lines) preserving exact bytes (no float reparse)."""
    lines = path.read_text().splitlines()
    if not lines:
        raise ValueError(f"Empty CSV: {path}")
    return lines[0], lines[1:]


def _distinct_l2_in_csv(data_lines: list[str], header: str) -> set[str]:
    idx = header.split(",").index("l2_lambda")
    return {line.split(",")[idx] for line in data_lines if line}


def merge_runs(inputs: list[Path], out: Path, run_id: str | None) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("Need at least two input run directories to merge.")

    manifests = [_read_manifest(d) for d in inputs]

    # --- Guard 1: identical except l2. Refuse to fabricate a confounded compare.
    base_cmp = _canonical_for_compare(manifests[0])
    for run_dir, manifest in zip(inputs[1:], manifests[1:], strict=False):
        diff = _first_difference(base_cmp, _canonical_for_compare(manifest))
        if diff is not None:
            raise ValueError(
                f"Refusing to merge: {inputs[0]} and {run_dir} differ outside the "
                f"l2 penalty at{diff}. The runs must be identical except for "
                f"l2_lambda for the comparison to be valid."
            )

    # --- Guard 2: each run is a single, distinct penalty.
    l2_by_run = [_l2_of(m, d) for m, d in zip(manifests, inputs, strict=False)]
    if len(set(l2_by_run)) != len(l2_by_run):
        raise ValueError(f"Inputs do not have distinct l2_lambdas: {l2_by_run}")
    l2_union = sorted(set(l2_by_run))

    out.mkdir(parents=True, exist_ok=True)

    # --- Merge metrics_long.csv (header from first, data verbatim from all). -----
    headers, data_blocks, total_rows = [], [], 0
    for run_dir, declared_l2 in zip(inputs, l2_by_run, strict=False):
        header, data = _read_csv_lines(run_dir / "metrics_long.csv")
        headers.append(header)
        found = {float(v) for v in _distinct_l2_in_csv(data, header)}
        if found != {declared_l2}:
            raise ValueError(
                f"{run_dir}/metrics_long.csv carries l2 values {found}, expected the "
                f"single declared {{{declared_l2}}}."
            )
        data_blocks.append(data)
        total_rows += len(data)
    if len(set(headers)) != 1:
        raise ValueError(f"metrics_long.csv headers differ across inputs: {set(headers)}")
    merged_metrics = out / "metrics_long.csv"
    merged_metrics.write_text("\n".join([headers[0], *sum(data_blocks, [])]) + "\n")
    print(f"Wrote {total_rows:,} metric rows -> {merged_metrics}")

    # --- Merge target_diagnostics_long.csv if every input has one. ---------------
    diag_paths = [d / "target_diagnostics_long.csv" for d in inputs]
    diag_csv: Path | None = None
    if all(p.is_file() for p in diag_paths):
        d_headers, d_blocks, d_total = [], [], 0
        for p in diag_paths:
            h, data = _read_csv_lines(p)
            d_headers.append(h)
            d_blocks.append(data)
            d_total += len(data)
        if len(set(d_headers)) != 1:
            raise ValueError("target_diagnostics_long.csv headers differ across inputs.")
        diag_csv = out / "target_diagnostics_long.csv"
        diag_csv.write_text("\n".join([d_headers[0], *sum(d_blocks, [])]) + "\n")
        print(f"Wrote {d_total:,} per-target diagnostic rows -> {diag_csv}")
    elif any(p.is_file() for p in diag_paths):
        print("WARNING: some inputs lack target_diagnostics_long.csv; skipping merge.")

    # --- degenerate_targets.csv is l2-independent: require identical, copy one. ---
    # Compare by content (newline-normalized) but copy the first input's raw bytes
    # so the output is byte-faithful to the source rather than reserialized.
    deg_paths = [d / "degenerate_targets.csv" for d in inputs]
    if all(p.is_file() for p in deg_paths):
        contents = {p.read_text() for p in deg_paths}
        if len(contents) != 1:
            raise ValueError(
                "degenerate_targets.csv differs across inputs, but target degeneracy "
                "is l2-independent. The inputs are not the same target set."
            )
        shutil.copyfile(deg_paths[0], out / "degenerate_targets.csv")
        print(f"Copied degenerate_targets.csv (identical across inputs) -> {out}")

    # --- Rebuild the manifest to describe the union. -----------------------------
    manifest = copy.deepcopy(manifests[0])
    manifest["run_id"] = run_id or out.name
    manifest["created_at"] = datetime.now(UTC).isoformat()
    manifest["command_args"]["l2_lambdas"] = str(l2_union)
    manifest["command_args"]["out"] = str(out)
    manifest["command_args"]["run_id"] = run_id or out.name
    manifest["grid"]["l2_lambdas"] = l2_union
    if isinstance(manifest.get("l0_optimizer"), dict):
        manifest["l0_optimizer"]["l2_lambdas"] = l2_union
    runtimes: dict[str, Any] = {}
    for m in manifests:
        runtimes.update(m.get("frontier_dense_runtimes_s", {}) or {})
    manifest["frontier_dense_runtimes_s"] = runtimes
    manifest["long_csv"] = str(merged_metrics)
    manifest["target_diagnostics_csv"] = str(diag_csv) if diag_csv else None
    manifest["n_rows"] = total_rows
    manifest["merged_from"] = [str(d) for d in inputs]
    manifest_path = write_run_manifest(out / "sweep_manifest.json", manifest)
    print(f"Wrote combined manifest (l2_lambdas={l2_union}) -> {manifest_path}")

    # --- Self-check: reload and confirm the union is what we claimed. ------------
    df = aggregate.load_long(merged_metrics)
    got = sorted(float(v) for v in df["l2_lambda"].dropna().unique())
    if got != l2_union:
        raise AssertionError(f"Post-merge l2 set {got} != expected {l2_union}")
    print(f"Verified merged metrics_long.csv carries l2_lambdas={got} ({len(df):,} rows).")

    return {"metrics": merged_metrics, "manifest": manifest_path, "l2_lambdas": l2_union}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs", type=Path, nargs="+", required=True,
        help="Single-l2 sweep run directories to merge (>=2).",
    )
    parser.add_argument("--out", type=Path, required=True, help="Combined output directory.")
    parser.add_argument("--run-id", default=None, help="run_id for the merged manifest (default: out dir name).")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    merge_runs(args.inputs, args.out, args.run_id)


if __name__ == "__main__":
    main()
