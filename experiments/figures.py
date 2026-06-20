#!/usr/bin/env python
"""Figures + reporting for the budget sweep (``metrics_long.csv``).

Reads the sweep's tidy long CSV, aggregates it with
:mod:`l0_paper.experiments.aggregate`, and emits:

* **LaTeX tables** (frontier, paired comparison, rotation) and a Markdown summary
  -- these need no plotting dependency.
* **matplotlib figures** (vector PDF + PNG, paper-ready) -- the frontier and its
  supporting cuts. matplotlib is imported lazily, so if the ``viz`` extra is not
  installed the tables/summary are still written and the figures are skipped with
  a note.

Figures
-------
* F1  frontier: out-of-sample mean & median ARE vs retained records (seed bands).
* F2  usability: effective sample size and max weight vs budget.
* F3  generalization gap: out-of-sample minus in-sample mean ARE vs budget.
* F4  by-family ARE at the anchor budget (rotation holdout when available).
* F5  cost-accuracy: runtime vs out-of-sample mean ARE.

Run
---
    uv run --extra viz python experiments/figures.py \
        --sweep experiments/runs/sweep-moderate \
        --paper-figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from l0_paper.experiments import aggregate, tables
from l0_paper.experiments.tables import SWEEP_METHOD_LABELS, SWEEP_METHOD_ORDER

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_FIGURES = REPO_ROOT / "paper" / "figures"

# Colour-blind-safe, stable per method across every figure.
METHOD_COLORS = {
    "informed_l0": "#1f77b4",
    "random_reweight": "#ff7f0e",
    "dense_sample": "#2ca02c",
}


# --- Tables + Markdown (no plotting dependency) ---------------------------------


def _fmt_pct(value: object) -> str:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    return "" if f != f else f"{f * 100:.2f}"


def _validation_only_families(long_csv: Path) -> tuple[str, ...]:
    """Read validation-only families from the sweep manifest when available."""
    manifest_path = long_csv.parent / "sweep_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        families = (
            manifest.get("frontier_split", {})
            .get("validation_only_families", [])
        )
        return tuple(str(f) for f in families)
    return ("cbo",)


def write_reports(long_csv: Path, out_dir: Path, *, anchor_budget: int | None) -> dict:
    """Aggregate the long CSV and write LaTeX tables + a Markdown summary."""
    df = aggregate.load_long(long_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    validation_only = _validation_only_families(long_csv)

    has_rotation = "rotation" in set(df["holdout_type"])
    # frontier_table returns both splits; render_frontier filters by split.
    frontier = aggregate.frontier_table(df, metric="mean_are")
    paired = aggregate.paired_method_diff(df)
    macro = aggregate.macro_average(df)
    rotation_front = (
        aggregate.rotation_frontier_table(
            df,
            metric="mean_are",
            validation_only_families=validation_only,
        )
        if has_rotation else None
    )

    table_paths = tables.write_sweep_tables(
        out_dir / "tables",
        frontier_oos=frontier,
        frontier_in=frontier,
        paired=paired,
        rotation_oos=rotation_front,
    )
    frontier_oos = frontier

    # Markdown summary.
    oos = frontier_oos[frontier_oos["split"] == "out_of_sample"]
    lines = [
        f"# Sweep summary: {long_csv.parent.name}",
        "",
        f"- Budgets: `{sorted(oos['budget_requested'].unique().tolist())}`",
        f"- Seeds per point: `{int(oos['n_seeds'].max()) if not oos.empty else 0}`",
        f"- Rotation panel: `{'yes' if has_rotation else 'no'}`",
        "",
        "## Out-of-sample mean ARE (%) by budget",
        "",
    ]
    methods = [m for m in SWEEP_METHOD_ORDER if m in set(oos["method"])]
    lines.append("| Retained | " + " | ".join(SWEEP_METHOD_LABELS[m].replace("$", "") for m in methods) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in methods) + " |")
    for budget in sorted(oos["budget_requested"].unique()):
        cells = []
        retained = oos[oos["budget_requested"] == budget]["budget_achieved"].mean()
        for method in methods:
            row = oos[(oos["method"] == method) & (oos["budget_requested"] == budget)]
            cells.append(_fmt_pct(row["mean_are_mean"].iloc[0]) if not row.empty else "")
        lines.append(f"| {retained:,.0f} | " + " | ".join(cells) + " |")

    lines += ["", "## Paired L0 vs random+reweight (out-of-sample)", ""]
    if not paired.empty:
        lines.append("| Budget | L0 | random | diff (pp) | p | significant |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for _, r in paired.iterrows():
            lines.append(
                f"| {r['budget_requested']:,.0f} | {_fmt_pct(r['informed_l0_mean'])} | "
                f"{_fmt_pct(r['random_reweight_mean'])} | {r['diff_mean'] * 100:+.2f} | "
                f"{r['p_value']:.3f} | {'yes' if r['significant'] else 'no'} |"
            )

    # Family macro-average (equal weight per family) de-biases the SOI-dominated
    # micro mean -- a secondary read on whether a method wins broadly or just on SOI.
    lines += ["", "## Out-of-sample family macro-average mean ARE (%)", ""]
    if not macro.empty:
        lines.append("| Budget | " + " | ".join(SWEEP_METHOD_LABELS[m].replace("$", "") for m in methods) + " |")
        lines.append("| --- | " + " | ".join("---" for _ in methods) + " |")
        for budget in sorted(macro["budget_requested"].unique()):
            cells = []
            for method in methods:
                row = macro[(macro["method"] == method) & (macro["budget_requested"] == budget)]
                cells.append(_fmt_pct(row["macro_mean_are_mean"].iloc[0]) if not row.empty else "")
            lines.append(f"| {budget:,.0f} | " + " | ".join(cells) + " |")

    lines += ["", "## Rotation robustness: target-weighted mean ARE (%)", ""]
    if rotation_front is not None and not rotation_front.empty:
        lines.append(
            "Each seed's rotation folds are aggregated first; validation-only "
            f"families excluded from this aggregate: `{list(validation_only)}`."
        )
        lines.append("")
        lines.append("| Retained | " + " | ".join(SWEEP_METHOD_LABELS[m].replace("$", "") for m in methods) + " |")
        lines.append("| --- | " + " | ".join("---" for _ in methods) + " |")
        rot_oos = rotation_front[rotation_front["split"] == "out_of_sample"]
        for budget in sorted(rot_oos["budget_requested"].unique()):
            cells = []
            retained = rot_oos[rot_oos["budget_requested"] == budget]["budget_achieved"].mean()
            for method in methods:
                row = rot_oos[
                    (rot_oos["method"] == method)
                    & (rot_oos["budget_requested"] == budget)
                ]
                cells.append(_fmt_pct(row["mean_are_mean"].iloc[0]) if not row.empty else "")
            lines.append(f"| {retained:,.0f} | " + " | ".join(cells) + " |")
    else:
        lines.append("No rotation panel found.")

    summary_path = out_dir / "sweep_summary.md"
    summary_path.write_text("\n".join(lines) + "\n")

    return {
        "df": df,
        "frontier": frontier_oos,
        "macro": macro,
        "paired": paired,
        "rotation": rotation_front,
        "has_rotation": has_rotation,
        "validation_only_families": validation_only,
        "table_paths": table_paths,
        "summary": summary_path,
        "anchor_budget": anchor_budget,
    }


# --- matplotlib figures (lazy import) ------------------------------------------


def _label(method: str) -> str:
    return SWEEP_METHOD_LABELS.get(method, method).replace("$", "")


def _plot_methods(ax, agg, *, x_col, mean_col, lo_col, hi_col, scale=1.0, log_x=True, log_y=False):
    """Plot one line (+ seed CI band) per method on ``ax`` from an aggregate frame."""
    import numpy as np

    for method in [m for m in SWEEP_METHOD_ORDER if m in set(agg["method"])]:
        d = agg[agg["method"] == method].sort_values(x_col)
        if d.empty:
            continue
        color = METHOD_COLORS.get(method, "#444")
        x = d[x_col].to_numpy(dtype=float)
        y = d[mean_col].to_numpy(dtype=float) * scale
        ax.plot(x, y, marker="o", color=color, label=_label(method), lw=2, ms=5)
        lo = d[lo_col].to_numpy(dtype=float) * scale
        hi = d[hi_col].to_numpy(dtype=float) * scale
        if np.isfinite(lo).all() and np.isfinite(hi).all() and np.any(hi > lo):
            ax.fill_between(x, lo, hi, color=color, alpha=0.15, linewidth=0)
    if log_x:
        ax.set_xscale("log")
    if log_y:
        ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.25)


def _save(fig, fig_dir: Path, name: str, fmts: tuple[str, ...]) -> list[Path]:
    written = []
    for fmt in fmts:
        path = fig_dir / f"{name}.{fmt}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        written.append(path)
    return written


def write_figures(report: dict, out_dir: Path, *, fmts: tuple[str, ...]) -> list[Path]:
    """Render the matplotlib figures; returns the files written.

    No-op (with a note) if matplotlib is missing -- tables/summary are still
    written by :func:`write_reports`.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed -- skipping figures (install the 'viz' extra). "
              "Tables and the Markdown summary were still written.")
        return []

    import numpy as np

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    df = report["df"]
    written: list[Path] = []

    # F1: frontier (OOS mean | median), retained records on a log x-axis.
    front_mean = aggregate.frontier_table(df, metric="mean_are")
    front_median = aggregate.frontier_table(df, metric="median_are")
    f1, (ax_mean, ax_med) = plt.subplots(1, 2, figsize=(11, 4.5))
    _plot_methods(ax_mean, front_mean[front_mean["split"] == "out_of_sample"],
                  x_col="budget_achieved", mean_col="mean_are_mean",
                  lo_col="mean_are_lo", hi_col="mean_are_hi", scale=100.0)
    _plot_methods(ax_med, front_median[front_median["split"] == "out_of_sample"],
                  x_col="budget_achieved", mean_col="median_are_mean",
                  lo_col="median_are_lo", hi_col="median_are_hi", scale=100.0)
    ax_mean.set(title="Mean ARE", xlabel="Retained records (log)", ylabel="Out-of-sample ARE (%)")
    ax_med.set(title="Median ARE", xlabel="Retained records (log)", ylabel="Out-of-sample ARE (%)")
    ax_mean.legend(title="Method", fontsize=9)
    f1.suptitle("F1 — Accuracy vs record budget (out-of-sample)")
    f1.tight_layout()
    written += _save(f1, fig_dir, "f1_frontier", fmts)
    plt.close(f1)

    # F2: usability — ESS and max weight vs budget.
    ess = aggregate.run_metric(df, metric="ess")
    maxw = aggregate.run_metric(df, metric="max_weight")
    f2, (ax_ess, ax_mw) = plt.subplots(1, 2, figsize=(11, 4.5))
    _plot_methods(ax_ess, ess, x_col="budget_requested", mean_col="ess_mean",
                  lo_col="ess_lo", hi_col="ess_hi")
    _plot_methods(ax_mw, maxw, x_col="budget_requested", mean_col="max_weight_mean",
                  lo_col="max_weight_lo", hi_col="max_weight_hi", log_y=True)
    ax_ess.set(title="Effective sample size", xlabel="Requested budget (log)", ylabel="ESS")
    ax_mw.set(title="Max weight", xlabel="Requested budget (log)", ylabel="Max weight (log)")
    ax_ess.legend(title="Method", fontsize=9)
    f2.suptitle("F2 — Usability: ESS and weight concentration")
    f2.tight_layout()
    written += _save(f2, fig_dir, "f2_usability", fmts)
    plt.close(f2)

    # F3: generalization gap (OOS - in-sample) mean ARE.
    gap_rows = []
    fm = front_mean
    for method in [m for m in SWEEP_METHOD_ORDER if m in set(fm["method"])]:
        for budget in sorted(fm["budget_requested"].unique()):
            o = fm[(fm["method"] == method) & (fm["budget_requested"] == budget)
                   & (fm["split"] == "out_of_sample")]
            i = fm[(fm["method"] == method) & (fm["budget_requested"] == budget)
                   & (fm["split"] == "in_sample")]
            if o.empty or i.empty:
                continue
            gap_rows.append({
                "method": method, "budget_achieved": float(o["budget_achieved"].iloc[0]),
                "gap_mean": float(o["mean_are_mean"].iloc[0]) - float(i["mean_are_mean"].iloc[0]),
                "gap_lo": float("nan"), "gap_hi": float("nan"),
            })
    f3, ax3 = plt.subplots(figsize=(7, 4.5))
    _plot_methods(ax3, pd.DataFrame(gap_rows), x_col="budget_achieved",
                  mean_col="gap_mean", lo_col="gap_lo", hi_col="gap_hi", scale=100.0)
    ax3.axhline(0.0, color="#888", lw=1, ls="--")
    ax3.set(title="F3 — Generalization gap (out-of-sample − in-sample mean ARE)",
            xlabel="Retained records (log)", ylabel="ARE gap (pp)")
    ax3.legend(title="Method", fontsize=9)
    f3.tight_layout()
    written += _save(f3, fig_dir, "f3_generalization_gap", fmts)
    plt.close(f3)

    # F4: by-family ARE at the anchor budget (rotation holdout when available).
    holdout_type = "rotation" if report["has_rotation"] else "fixed_family"
    anchor = report["anchor_budget"]
    if anchor is None:
        budgets = sorted(df[df["holdout_type"] == holdout_type]["budget_requested"].unique())
        anchor = budgets[len(budgets) // 2] if budgets else None
    if anchor is not None:
        fam = aggregate.by_family_at_budget(
            df, budget_requested=int(anchor), holdout_type=holdout_type
        )
        families = sorted(fam["family"].unique())
        methods = [m for m in SWEEP_METHOD_ORDER if m in set(fam["method"])]
        f4, ax4 = plt.subplots(figsize=(max(7, 0.7 * len(families) + 3), 4.5))
        x = np.arange(len(families))
        width = 0.8 / max(len(methods), 1)
        for k, method in enumerate(methods):
            d = fam[fam["method"] == method].set_index("family").reindex(families)
            ax4.bar(x + (k - (len(methods) - 1) / 2) * width, d["mean_are"].to_numpy(dtype=float) * 100,
                    width, label=_label(method), color=METHOD_COLORS.get(method, "#444"))
        ax4.set_xticks(x)
        ax4.set_xticklabels(families, rotation=45, ha="right", fontsize=8)
        ax4.set(title=f"F4 — Out-of-sample ARE by family at budget {int(anchor):,} ({holdout_type})",
                ylabel="Mean ARE (%)")
        ax4.legend(title="Method", fontsize=9)
        ax4.grid(True, axis="y", alpha=0.25)
        f4.tight_layout()
        written += _save(f4, fig_dir, "f4_by_family", fmts)
        plt.close(f4)

    # F5: cost-accuracy — runtime vs OOS mean ARE.
    runtime = aggregate.run_metric(df, metric="runtime_s")
    fm_oos = front_mean[front_mean["split"] == "out_of_sample"]
    f5, ax5 = plt.subplots(figsize=(7, 4.5))
    for method in [m for m in SWEEP_METHOD_ORDER if m in set(fm_oos["method"])]:
        rt = runtime[runtime["method"] == method].set_index("budget_requested")
        acc = fm_oos[fm_oos["method"] == method].set_index("budget_requested")
        budgets = sorted(set(rt.index) & set(acc.index))
        if not budgets:
            continue
        xs = [rt.loc[b, "runtime_s_mean"] for b in budgets]
        ys = [acc.loc[b, "mean_are_mean"] * 100 for b in budgets]
        ax5.scatter(xs, ys, s=60, color=METHOD_COLORS.get(method, "#444"), label=_label(method))
        for b, xv, yv in zip(budgets, xs, ys, strict=True):
            ax5.annotate(f"{b:,}", (xv, yv), textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax5.set_xscale("log")
    ax5.set(title="F5 — Cost vs accuracy", xlabel="Runtime (s, log)",
            ylabel="Out-of-sample mean ARE (%)")
    ax5.legend(title="Method", fontsize=9)
    ax5.grid(True, which="both", alpha=0.25)
    f5.tight_layout()
    written += _save(f5, fig_dir, "f5_cost_accuracy", fmts)
    plt.close(f5)

    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--sweep", type=Path, help="Sweep run dir (contains metrics_long.csv).")
    g.add_argument("--long", type=Path, help="Path to a metrics_long.csv directly.")
    parser.add_argument("--out", type=Path, default=None, help="Output dir (default: <sweep>/report).")
    parser.add_argument("--anchor-budget", type=int, default=None)
    parser.add_argument("--format", default="pdf,png", help="Output formats, comma-separated (pdf,png,svg).")
    parser.add_argument("--paper-figures", action="store_true", help="Copy figures into paper/figures.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    long_csv = (args.sweep / "metrics_long.csv") if args.sweep else args.long
    if not long_csv.is_file():
        raise FileNotFoundError(f"metrics_long.csv not found: {long_csv}")
    out_dir = args.out or (long_csv.parent / "report")
    fmts = tuple(f.strip() for f in args.format.split(",") if f.strip())

    report = write_reports(long_csv, out_dir, anchor_budget=args.anchor_budget)
    print(f"Wrote tables: {json.dumps({k: str(v) for k, v in report['table_paths'].items()}, indent=2)}")
    print(f"Wrote summary: {report['summary']}")

    written = write_figures(report, out_dir, fmts=fmts)
    for path in written:
        print(f"  figure: {path}")

    if args.paper_figures and written:
        PAPER_FIGURES.mkdir(parents=True, exist_ok=True)
        import shutil

        for path in written:
            if path.suffix in (".pdf", ".png", ".svg"):
                shutil.copy(path, PAPER_FIGURES / path.name)
        print(f"Copied static figures into {PAPER_FIGURES}")


if __name__ == "__main__":
    main()
