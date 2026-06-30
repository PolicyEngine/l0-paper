#!/usr/bin/env python
"""Merge compatible sweep shard directories into one combined run directory.

This is for sweeps split across seeds or other embarrassingly parallel shards,
where each input has the same candidate universe, target surface, budgets,
optimizer settings, and scoring setup. It copies rows verbatim from each input
CSV, namespaces weight artifacts under the combined directory, and rebuilds the
manifest to describe the union.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l0_paper.experiments import aggregate
from l0_paper.experiments.artifacts import write_run_manifest

_EXPECTED_TO_DIFFER_TOP = (
    "run_id",
    "created_at",
    "updated_at",
    "long_csv",
    "target_diagnostics_csv",
    "weights_dir",
    "weights_manifest_csv",
    "n_rows",
    "n_target_diagnostic_rows",
    "n_weight_artifact_rows",
    "completed_cells",
    "shard_checkpoint_dir",
    "frontier_dense_runtimes_s",
    "merged_from",
)
_EXPECTED_TO_DIFFER_NESTED = {
    "command_args": ("out", "run_id", "seeds", "methods"),
    "grid": ("seeds",),
}


def _canonical_for_compare(manifest: dict[str, Any]) -> dict[str, Any]:
    m = copy.deepcopy(manifest)
    for key in _EXPECTED_TO_DIFFER_TOP:
        m.pop(key, None)
    for parent, children in _EXPECTED_TO_DIFFER_NESTED.items():
        if isinstance(m.get(parent), dict):
            for child in children:
                m[parent].pop(child, None)
    return m


def _first_difference(a: Any, b: Any, path: str = "") -> str | None:
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
        for index, (x, y) in enumerate(zip(a, b, strict=False)):
            diff = _first_difference(x, y, f"{path}[{index}]")
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


def _read_csv_lines(path: Path) -> tuple[str, list[str]]:
    lines = path.read_text().splitlines()
    if not lines:
        raise ValueError(f"Empty CSV: {path}")
    return lines[0], lines[1:]


def _merge_text_csv(inputs: Iterable[Path], out: Path) -> int:
    headers: list[str] = []
    blocks: list[list[str]] = []
    total = 0
    for path in inputs:
        header, data = _read_csv_lines(path)
        headers.append(header)
        blocks.append(data)
        total += len(data)
    if len(set(headers)) != 1:
        raise ValueError(f"CSV headers differ across inputs: {set(headers)}")
    out.write_text("\n".join([headers[0], *sum(blocks, [])]) + "\n")
    return total


def _csv_values(paths: Iterable[Path], column: str) -> list[str]:
    values: list[str] = []
    for path in paths:
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                value = row.get(column)
                if value is not None and value != "":
                    values.append(str(value))
    return values


def _copy_weight_artifacts(inputs: list[Path], out: Path) -> tuple[Path | None, int]:
    manifest_paths = [run_dir / "weights_manifest.csv" for run_dir in inputs]
    if not any(path.is_file() for path in manifest_paths):
        return None, 0
    if not all(path.is_file() for path in manifest_paths):
        raise FileNotFoundError(
            "Some inputs have weights_manifest.csv and others do not; refusing to merge."
        )

    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    weights_dir = out / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    for run_dir, manifest_path in zip(inputs, manifest_paths, strict=True):
        shard_name = run_dir.name
        with manifest_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if fieldnames is None:
                fieldnames = list(reader.fieldnames or [])
            elif fieldnames != list(reader.fieldnames or []):
                raise ValueError("weights_manifest.csv headers differ across inputs.")
            for row in reader:
                old_rel = Path(row["artifact_path"])
                src = run_dir / old_rel
                if not src.is_file():
                    raise FileNotFoundError(f"Missing weight artifact {src}")
                new_rel = Path("weights") / shard_name / old_rel.name
                dst = out / new_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                row = dict(row)
                row["artifact_path"] = str(new_rel)
                rows.append(row)

    out_manifest = out / "weights_manifest.csv"
    with out_manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_manifest, len(rows)


def merge_runs(
    inputs: list[Path], out: Path, run_id: str | None = None
) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("Need at least two input run directories to merge.")
    inputs = [path.resolve() for path in inputs]
    manifests = [_read_manifest(path) for path in inputs]

    base_cmp = _canonical_for_compare(manifests[0])
    for run_dir, manifest in zip(inputs[1:], manifests[1:], strict=True):
        diff = _first_difference(base_cmp, _canonical_for_compare(manifest))
        if diff is not None:
            raise ValueError(
                f"Refusing to merge: {inputs[0]} and {run_dir} differ outside "
                f"expected shard metadata at{diff}."
            )

    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    merged_metrics = out / "metrics_long.csv"
    n_rows = _merge_text_csv(
        [run_dir / "metrics_long.csv" for run_dir in inputs], merged_metrics
    )
    print(f"Wrote {n_rows:,} metric rows -> {merged_metrics}")

    diag_paths = [run_dir / "target_diagnostics_long.csv" for run_dir in inputs]
    diag_csv: Path | None = None
    n_diag_rows = 0
    if all(path.is_file() for path in diag_paths):
        diag_csv = out / "target_diagnostics_long.csv"
        n_diag_rows = _merge_text_csv(diag_paths, diag_csv)
        print(f"Wrote {n_diag_rows:,} per-target diagnostic rows -> {diag_csv}")
    elif any(path.is_file() for path in diag_paths):
        raise FileNotFoundError(
            "Some inputs have target_diagnostics_long.csv and others do not; refusing to merge."
        )

    deg_paths = [run_dir / "degenerate_targets.csv" for run_dir in inputs]
    if all(path.is_file() for path in deg_paths):
        contents = {path.read_text() for path in deg_paths}
        if len(contents) != 1:
            raise ValueError("degenerate_targets.csv differs across inputs.")
        shutil.copyfile(deg_paths[0], out / "degenerate_targets.csv")

    weights_manifest, n_weight_rows = _copy_weight_artifacts(inputs, out)
    if weights_manifest is not None:
        print(f"Wrote {n_weight_rows:,} weight artifact rows -> {weights_manifest}")

    df = aggregate.load_long(merged_metrics)
    manifest = copy.deepcopy(manifests[0])
    manifest["run_id"] = run_id or out.name
    now = datetime.now(UTC).isoformat()
    manifest["created_at"] = now
    manifest["updated_at"] = now
    manifest["long_csv"] = str(merged_metrics)
    manifest["target_diagnostics_csv"] = str(diag_csv) if diag_csv else None
    manifest["weights_dir"] = str(out / "weights") if weights_manifest else None
    manifest["weights_manifest_csv"] = (
        str(weights_manifest) if weights_manifest else None
    )
    manifest["n_rows"] = int(n_rows)
    manifest["n_target_diagnostic_rows"] = int(n_diag_rows)
    manifest["n_weight_artifact_rows"] = int(n_weight_rows)
    manifest["merged_from"] = [str(path) for path in inputs]
    completed_values = [m.get("completed_cells") for m in manifests]
    if all(isinstance(value, int) for value in completed_values):
        manifest["completed_cells"] = int(sum(completed_values))
    else:
        merged_cells: list[Any] = []
        for value in completed_values:
            if isinstance(value, list):
                merged_cells.extend(value)
        manifest["completed_cells"] = merged_cells
    runtimes: dict[str, Any] = {}
    for m in manifests:
        runtimes.update(m.get("frontier_dense_runtimes_s", {}) or {})
    manifest["frontier_dense_runtimes_s"] = runtimes

    seeds = sorted({int(v) for v in df["seed"].dropna().unique()})
    methods = sorted(str(v) for v in df["method"].dropna().unique())
    l2_lambdas = sorted(float(v) for v in df["l2_lambda"].dropna().unique())
    budgets = sorted(int(v) for v in df["budget_requested"].dropna().unique())
    manifest.setdefault("grid", {})["seeds"] = seeds
    manifest["grid"]["budgets"] = budgets
    manifest["grid"]["l2_lambdas"] = l2_lambdas
    if isinstance(manifest.get("command_args"), dict):
        manifest["command_args"]["out"] = str(out)
        manifest["command_args"]["run_id"] = run_id or out.name
        manifest["command_args"]["seeds"] = str(seeds)
        manifest["command_args"]["methods"] = str(methods)

    manifest_path = write_run_manifest(out / "sweep_manifest.json", manifest)
    print(f"Wrote combined manifest -> {manifest_path}")

    reloaded = aggregate.load_long(merged_metrics)
    if len(reloaded) != n_rows:
        raise AssertionError(f"Reloaded {len(reloaded):,} rows, expected {n_rows:,}.")
    print(
        f"Verified merged run: seeds={seeds}, methods={methods}, "
        f"budgets={budgets}, l2_lambdas={l2_lambdas}."
    )
    return {"metrics": merged_metrics, "manifest": manifest_path}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        required=True,
        help="Compatible sweep shard directories to merge.",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Combined output directory."
    )
    parser.add_argument(
        "--run-id", default=None, help="run_id for the merged manifest."
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    merge_runs(args.inputs, args.out, args.run_id)


if __name__ == "__main__":
    main()
