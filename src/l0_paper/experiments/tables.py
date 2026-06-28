"""Render paper-ready LaTeX tables from run summaries.

The generated tables drop into ``paper/tables/`` in place of the ``\\tbc``
placeholders. Rows for the methods this experiment produces are filled (informed
L0, informed L1, random + reweight, and the dense + weighted-sampling baseline,
which the paper labels "Survey-weight sampling"); any remaining paper-method rows
stay ``\\tbc`` until implemented.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

SWEEP_METHOD_LABELS = {
    "informed_l0": r"Informed $L_0$",
    "informed_l1": r"Informed $L_1$",
    "random_reweight": "Random + reweight",
    "dense_sample": "Survey-weight sampling",
}
SWEEP_METHOD_ORDER = ("informed_l0", "informed_l1", "random_reweight", "dense_sample")


def _pct(stats: dict[str, Any], key: str = "mean_are") -> str:
    value = stats.get(key)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    return f"{value * 100:.2f}"


def _int(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    return f"{value:,.0f}"


def _weight(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    return f"{value:,.1f}"


def _runtime(value: Any) -> str:
    if value is None:
        return "--"
    return f"{value:.1f}\\,s"


def render_sampling_comparison(summaries: dict[str, dict[str, Any]], budget: int) -> str:
    """Table 1: informed L0 vs baselines at a matched budget."""

    def row(label: str, key: str | None) -> str:
        if key is None or key not in summaries:
            return (
                f"{label} & \\tbc & \\tbc & \\tbc & \\tbc & \\tbc & \\tbc \\\\"
            )
        s = summaries[key]
        ins, oos = s["in_sample"], s["out_of_sample"]
        return (
            f"{label} & {_int(s['retained_records'])} & {_pct(ins)} & {_pct(oos)} & "
            f"{_int(ins.get('ess'))} & {_weight(ins.get('max_weight'))} & "
            f"{_runtime(s.get('runtime_s'))} \\\\"
        )

    rows = "\n".join(
        [
            row("Informed $L_0$", "informed_l0"),
            row("Informed $L_1$", "informed_l1"),
            row("Random + reweight", "random_reweight"),
            row("Survey-weight sampling", "dense_sample"),
            row("Combinatorial optim.", None),
        ]
    )
    return rf"""\begin{{table}}[ht]
\centering
{{\tablefont
\resizebox{{\textwidth}}{{!}}{{%
\begin{{tabular}}{{p{{0.2\textwidth}}rrrrrr}}
\toprule
Method & Budget & In-sample mean ARE (\%) & Out-of-sample mean ARE (\%) & ESS & Max weight & Runtime \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
}}
}}
\caption{{Informed $L_0$ sampling against random and stratified sampling at a matched record budget.
All methods share the candidate universe and the target set. ARE is absolute relative error across
the scored targets; ESS is the effective sample size.}}
\label{{tab:sampling_comparison}}
\tablenote{{The record budget and target counts are read from each run's manifest. Out-of-sample
columns score targets held out of every method's fit.}}
\end{{table}}
"""


def render_calibration_accuracy(geo_score: dict[str, Any]) -> str:
    """Table 2: informed-L0 accuracy by geographic level."""
    by_geo = geo_score.get("by_geography", {})
    level_rows = [
        ("National", "national"),
        ("State", "state"),
        ("Congressional district", "district"),
    ]

    def row(label: str, level: str) -> str:
        stats = by_geo.get(level)
        if not stats or stats.get("n", 0) == 0:
            return f"{label} & -- & -- & -- & -- \\\\"
        return (
            f"{label} & {_int(stats['n'])} & {_pct(stats, 'mean_are')} & "
            f"{_pct(stats, 'median_are')} & {_pct(stats, 'max_are')} \\\\"
        )

    rows = "\n".join(row(label, level) for label, level in level_rows)
    total = (
        f"\\textbf{{All scored targets}} & {_int(geo_score.get('n'))} & "
        f"{_pct(geo_score, 'mean_are')} & {_pct(geo_score, 'median_are')} & "
        f"{_pct(geo_score, 'max_are')} \\\\"
    )
    return rf"""\begin{{table}}[ht]
\centering
{{\tablefont
\begin{{tabular}}{{lrrrr}}
\toprule
Geographic level & Targets & Mean ARE (\%) & Median ARE (\%) & Max ARE (\%) \\
\midrule
{rows}
\midrule
{total}
\bottomrule
\end{{tabular}}
}}
\caption{{Calibration accuracy by geographic level for the informed $L_0$ run, measured as absolute
relative error (ARE) across the scored targets.}}
\label{{tab:calibration_accuracy}}
\tablenote{{Target counts are read from the run manifest.}}
\end{{table}}
"""


def render_calibration_accuracy_by_family(family_score: dict[str, Any]) -> str:
    """Informed-L0 accuracy by target family (the more informative cut while the
    target surface is national + state only)."""
    by_family = family_score.get("by_family", {})

    def row(name: str, stats: dict[str, Any]) -> str:
        label = name.replace("_", r"\_")
        return (
            f"{label} & {_int(stats.get('n'))} & {_pct(stats, 'mean_are')} & "
            f"{_pct(stats, 'median_are')} & {_pct(stats, 'max_are')} \\\\"
        )

    rows = "\n".join(row(name, by_family[name]) for name in sorted(by_family))
    total = (
        f"\\textbf{{All scored targets}} & {_int(family_score.get('n'))} & "
        f"{_pct(family_score, 'mean_are')} & {_pct(family_score, 'median_are')} & "
        f"{_pct(family_score, 'max_are')} \\\\"
    )
    return rf"""\begin{{table}}[ht]
\centering
{{\tablefont
\begin{{tabular}}{{lrrrr}}
\toprule
Target family & Targets & Mean ARE (\%) & Median ARE (\%) & Max ARE (\%) \\
\midrule
{rows}
\midrule
{total}
\bottomrule
\end{{tabular}}
}}
\caption{{Calibration accuracy by target family for the informed $L_0$ run, measured as absolute
relative error (ARE) across the scored targets.}}
\label{{tab:calibration_accuracy_by_family}}
\tablenote{{Target counts are read from the run manifest.}}
\end{{table}}
"""


def write_tables(
    out_dir: str | Path,
    *,
    summaries: dict[str, dict[str, Any]],
    l0_geo_score: dict[str, Any],
    budget: int,
) -> dict[str, Path]:
    """Write all tables into ``out_dir``; return their paths by table name."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "sampling_comparison": out_dir / "sampling_comparison.tex",
        "calibration_accuracy": out_dir / "calibration_accuracy.tex",
        "calibration_accuracy_by_family": out_dir / "calibration_accuracy_by_family.tex",
    }
    paths["sampling_comparison"].write_text(
        render_sampling_comparison(summaries, budget)
    )
    paths["calibration_accuracy"].write_text(
        render_calibration_accuracy(l0_geo_score)
    )
    paths["calibration_accuracy_by_family"].write_text(
        render_calibration_accuracy_by_family(l0_geo_score)
    )
    return paths


# --- Sweep tables (consume the aggregated DataFrames from aggregate.py) ---------


def _ci_cell(mean: Any, lo: Any, hi: Any, *, scale: float = 100.0, digits: int = 1) -> str:
    """Format ``mean [lo, hi]`` (scaled to %), or just the mean for a degenerate CI."""
    if mean is None or (isinstance(mean, float) and math.isnan(mean)):
        return "--"
    m = float(mean) * scale
    if (
        lo is None or hi is None
        or (isinstance(lo, float) and math.isnan(lo))
        or (isinstance(hi, float) and math.isnan(hi))
        or abs(float(hi) - float(lo)) < 1e-12
    ):
        return f"{m:.{digits}f}"
    return f"{m:.{digits}f} {{\\scriptsize[{float(lo) * scale:.{digits}f}, {float(hi) * scale:.{digits}f}]}}"


def render_frontier(
    frontier_df: pd.DataFrame,
    *,
    metric: str = "mean_are",
    split: str = "out_of_sample",
    caption: str | None = None,
    label: str | None = None,
    tablenote: str | None = None,
) -> str:
    """Table: per-budget ARE (with seed CI) for each method along the frontier.

    ``frontier_df`` is :func:`aggregate.frontier_table` output. One row per budget
    (labelled by mean retained records); one column per method.
    """
    df = frontier_df[frontier_df["split"] == split]
    multi_l2 = "l2_lambda" in df.columns and df["l2_lambda"].nunique() > 1
    methods = [m for m in SWEEP_METHOD_ORDER if m in set(df["method"])]
    columns = []
    for method in methods:
        l2_values = sorted(df[df["method"] == method]["l2_lambda"].unique()) if "l2_lambda" in df else [0.0]
        for l2 in l2_values:
            column_label = SWEEP_METHOD_LABELS[method]
            if multi_l2:
                column_label = f"{column_label} ($\\lambda_2={float(l2):g}$)"
            columns.append((method, float(l2), column_label))
    budgets = sorted(df["budget_requested"].unique())
    mean_col, lo_col, hi_col = f"{metric}_mean", f"{metric}_lo", f"{metric}_hi"
    lookup = {
        (row["method"], float(row.get("l2_lambda", 0.0)), int(row["budget_requested"])): row
        for _, row in df.iterrows()
    }
    achieved = df.groupby("budget_requested")["budget_achieved"].mean().to_dict()

    body_rows = []
    for budget in budgets:
        cells = []
        for method, l2, _label in columns:
            row = lookup.get((method, l2, budget))
            cells.append(
                "--" if row is None
                else _ci_cell(row[mean_col], row[lo_col], row[hi_col])
            )
        first = budget if multi_l2 else achieved.get(budget, float("nan"))
        body_rows.append(f"{first:,.0f} & " + " & ".join(cells) + r" \\")
    body = "\n".join(body_rows)
    first_header = "Requested budget" if multi_l2 else "Average retained records"
    header = first_header + " & " + " & ".join(label for _, _, label in columns) + r" \\"
    col_spec = "r" * (len(columns) + 1)
    split_label = "out-of-sample" if split == "out_of_sample" else "in-sample"
    caption = caption or (
        f"Mean absolute relative error ({split_label}) versus record budget, per "
        "selection method. Cells are the cross-seed mean with a 95\\% confidence "
        "interval in brackets. All methods share the candidate universe and the "
        "fixed family-level holdout."
    )
    label = label or f"tab:frontier_{split}"
    tablenote = tablenote or (
        "Average retained records is the cross-seed mean achieved budget; informed "
        "$L_0$ sets the budget at each grid point and the baselines match it."
        if not multi_l2 else
        "Rows are requested budgets; columns keep $\\lambda_2$ values separate "
        "to avoid averaging different concentration penalties."
    )
    note = f"\\tablenote{{{tablenote}}}" if tablenote else ""
    return rf"""\begin{{table}}[ht]
\centering
{{\tablefont
\resizebox{{\textwidth}}{{!}}{{%
\begin{{tabular}}{{{col_spec}}}
\toprule
{header}
\midrule
{body}
\bottomrule
\end{{tabular}}
}}
}}
\caption{{{caption}}}
\label{{{label}}}
{note}
\end{{table}}
"""


def render_paired_comparison(
    paired_df: pd.DataFrame,
    *,
    challenger: str = "informed_l0",
    baseline: str = "random_reweight",
) -> str:
    """Table: paired (same-seed) challenger-vs-baseline difference per budget.

    ``paired_df`` is :func:`aggregate.paired_method_diff` output. A negative
    difference means the challenger has lower error. The confidence intervals and
    p-values are descriptive diagnostics of the paired seed differences.
    """
    ch_label = SWEEP_METHOD_LABELS.get(challenger, challenger)
    bl_label = SWEEP_METHOD_LABELS.get(baseline, baseline)
    ch_mean_col, bl_mean_col = f"{challenger}_mean", f"{baseline}_mean"
    rows = []
    for _, row in paired_df.iterrows():
        diff = _ci_cell(row["diff_mean"], row["diff_lo"], row["diff_hi"])
        p = row.get("p_value")
        p_str = "--" if p is None or (isinstance(p, float) and math.isnan(p)) else f"{float(p):.3f}"
        budget = f"{row['budget_requested']:,.0f}"
        if "l2_lambda" in row.index:
            budget = f"{budget} ($\\lambda_2={float(row['l2_lambda']):g}$)"
        rows.append(
            f"{budget} & {_ci_cell(row[ch_mean_col], None, None)} & "
            f"{_ci_cell(row[bl_mean_col], None, None)} & {diff} & {p_str} \\\\"
        )
    body = "\n".join(rows)
    return rf"""\begin{{table}}[ht]
\centering
{{\tablefont
\begin{{tabular}}{{rrrrr}}
\toprule
Budget & {ch_label} (\%) & {bl_label} (\%) & $\Delta$ (pp) & $p$ \\
\midrule
{body}
\bottomrule
\end{{tabular}}
}}
\caption{{Paired out-of-sample comparison of {ch_label} against {bl_label} at each
budget. $\Delta$ is the cross-seed mean of the per-seed error difference (negative
favours {ch_label}) with a 95\% confidence interval. $p$ is a paired $t$-test and
should be read as descriptive rather than strong inferential evidence.}}
\label{{tab:paired_comparison}}
\end{{table}}
"""


def write_sweep_tables(
    out_dir: str | Path,
    *,
    frontier_oos: pd.DataFrame,
    frontier_in: pd.DataFrame,
    paired: pd.DataFrame,
    rotation_oos: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """Write the sweep LaTeX tables into ``out_dir``; return paths by name."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "frontier_out_of_sample": out_dir / "frontier_out_of_sample.tex",
        "frontier_in_sample": out_dir / "frontier_in_sample.tex",
        "paired_comparison": out_dir / "paired_comparison.tex",
    }
    paths["frontier_out_of_sample"].write_text(render_frontier(frontier_oos, split="out_of_sample"))
    paths["frontier_in_sample"].write_text(render_frontier(frontier_in, split="in_sample"))
    paths["paired_comparison"].write_text(render_paired_comparison(paired))
    if rotation_oos is not None and not rotation_oos.empty:
        path = out_dir / "frontier_rotation.tex"
        path.write_text(
            render_frontier(
                rotation_oos,
                split="out_of_sample",
                label="tab:frontier_rotation",
                caption=(
                    "Family-rotation robustness check at the anchor budget. Cells "
                    "are the cross-seed mean with a 95\\% confidence interval after "
                    "first aggregating each seed's fold scores into one "
                    "target-weighted rotated-family score."
                ),
                tablenote=(
                    "Rotation folds are not treated as independent replicates. "
                    "Validation-only families, such as CBO, are excluded from this "
                    "rotated-family aggregate because they appear in every fold."
                ),
            )
        )
        paths["frontier_rotation"] = path
    return paths
