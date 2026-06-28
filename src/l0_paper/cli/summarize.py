#!/usr/bin/env python
"""Write readable summaries from an experiment ``run_manifest.json``.

The experiment harness already writes strict JSON and paper-ready LaTeX. This
script adds analyst-friendly artifacts next to them:

* ``summary.md`` -- a compact Markdown report for quick reading.
* ``tables/method_summary.csv`` -- one row per method.
* ``tables/family_summary.csv`` -- family-level in/out-of-sample errors.

Example
-------
    uv run l0 summarize runs/full-20k-cbo-state-tax-holdout
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

METHOD_LABELS = {
    "informed_l0": "Informed L0",
    "random_reweight": "Random + reweight",
    "dense_sample": "Survey-weight sampling",
}
METHOD_ORDER = ("informed_l0", "random_reweight", "dense_sample")


def _manifest_path(path: Path) -> Path:
    if path.is_dir():
        path = path / "run_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Run manifest not found: {path}")
    return path


def _pct(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value) * 100:.2f}"


def _num(value: Any, digits: int = 2) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def _int(value: Any) -> str:
    if value is None:
        return ""
    return str(int(round(float(value))))


def _seconds(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.1f}"


def _method_keys(methods: dict[str, Any]) -> list[str]:
    known = [key for key in METHOD_ORDER if key in methods]
    extra = sorted(key for key in methods if key not in METHOD_ORDER)
    return [*known, *extra]


def method_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Return compact per-method rows for CSV/Markdown rendering."""
    rows: list[dict[str, str]] = []
    for key in _method_keys(manifest.get("methods", {})):
        summary = manifest["methods"][key]
        in_sample = summary["in_sample"]
        out = summary["out_of_sample"]
        rows.append(
            {
                "method": METHOD_LABELS.get(key, key),
                "retained_records": _int(summary.get("retained_records")),
                "epochs": _int(summary.get("epochs")),
                "in_sample_mean_are_pct": _pct(in_sample.get("mean_are")),
                "in_sample_median_are_pct": _pct(in_sample.get("median_are")),
                "out_of_sample_mean_are_pct": _pct(out.get("mean_are")),
                "out_of_sample_median_are_pct": _pct(out.get("median_are")),
                "ess": _int(in_sample.get("ess")),
                "max_weight": _num(in_sample.get("max_weight"), digits=1),
                "runtime_s": _seconds(summary.get("runtime_s")),
                "l0_lambda": _num(summary.get("l0_lambda"), digits=8),
            }
        )
    return rows


def family_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Return per-method, per-family rows for in- and out-of-sample splits."""
    rows: list[dict[str, str]] = []
    for key in _method_keys(manifest.get("methods", {})):
        summary = manifest["methods"][key]
        for split_name, split in (
            ("in_sample", summary["in_sample"]),
            ("out_of_sample", summary["out_of_sample"]),
        ):
            for family, stats in sorted(split.get("by_family", {}).items()):
                rows.append(
                    {
                        "method": METHOD_LABELS.get(key, key),
                        "split": split_name,
                        "family": family,
                        "n_targets": _int(stats.get("n")),
                        "mean_are_pct": _pct(stats.get("mean_are")),
                        "median_are_pct": _pct(stats.get("median_are")),
                        "max_are_pct": _pct(stats.get("max_are")),
                    }
                )
    return rows


def _markdown_table(rows: list[dict[str, str]], columns: Iterable[str]) -> str:
    columns = list(columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def render_markdown(manifest: dict[str, Any]) -> str:
    split = manifest.get("target_split", {})
    precal = manifest.get("precalibration", {})
    method_columns = [
        "method",
        "retained_records",
        "epochs",
        "in_sample_mean_are_pct",
        "out_of_sample_mean_are_pct",
        "out_of_sample_median_are_pct",
        "ess",
        "max_weight",
        "runtime_s",
    ]
    holdout_families = split.get("holdout_families") or []
    validation_only = split.get("validation_only_families") or []
    lines = [
        f"# Run Summary: {manifest.get('run_id', '')}",
        "",
        f"- Created at: `{manifest.get('created_at', '')}`",
        f"- Candidate records: `{precal.get('n_records', '')}`",
        f"- Targets: `{split.get('total', '')}` total, `{split.get('fit', '')}` fit, `{split.get('holdout', '')}` held out",
        f"- Holdout families: `{', '.join(holdout_families) or 'none'}`",
        f"- Validation-only families: `{', '.join(validation_only) or 'none'}`",
        f"- Requested/achieved budget: `{manifest.get('budget', '')}` retained records",
        "",
        "## Method Summary",
        "",
        _markdown_table(method_rows(manifest), method_columns),
        "",
        "## Out-Of-Sample Family Summary",
        "",
        _markdown_table(
            [row for row in family_rows(manifest) if row["split"] == "out_of_sample"],
            ["method", "family", "n_targets", "mean_are_pct", "median_are_pct", "max_are_pct"],
        ),
        "",
    ]
    return "\n".join(lines)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(manifest_path: Path) -> dict[str, Path]:
    manifest = json.loads(manifest_path.read_text())
    run_dir = manifest_path.parent
    paths = {
        "markdown": run_dir / "summary.md",
        "method_csv": run_dir / "tables" / "method_summary.csv",
        "family_csv": run_dir / "tables" / "family_summary.csv",
    }
    paths["markdown"].write_text(render_markdown(manifest))
    _write_csv(paths["method_csv"], method_rows(manifest))
    _write_csv(paths["family_csv"], family_rows(manifest))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Run directory or run_manifest.json path.")
    args = parser.parse_args()

    paths = write_summary(_manifest_path(args.run))
    for label, path in paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
