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

from l0_paper.experiments import aggregate

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


# --- Paper result tables (regenerated from a sweep's metrics_long.csv) -----------
#
# These reproduce the curated ``paper/tables/*.tex`` directly from a sweep run, so
# the manuscript's result tables stay in lockstep with the data: rerun
# ``l0 figures --sweep <run> --paper-figures`` and they regenerate. They read the
# un-penalised (``l2_lambda == 0``) reported frontier and the cross-seed means from
# :mod:`aggregate`. The dict-based ``render_*`` above stay as single-run poc drafts.


def _grp(s: str) -> str:
    """LaTeX thousands grouping: ``1,234`` -> ``1{,}234``."""
    return s.replace(",", "{,}")


def _pct1(v: Any) -> str:
    """A fraction (e.g. 0.236) as a percentage with one decimal: ``23.6``."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    return _grp(f"{float(v) * 100:,.1f}")


def _count(v: Any) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    return _grp(f"{float(v):,.0f}")


def _sci(v: Any) -> str:
    """Scientific notation as ``$m.m\\times10^{e}$`` (for the tiny L0 penalties)."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or float(v) == 0.0:
        return "--"
    exp = math.floor(math.log10(abs(float(v))))
    mant = float(v) / (10**exp)
    return rf"${mant:.1f}\times10^{{{exp}}}$"


def _at(
    frame: pd.DataFrame,
    *,
    method: str,
    budget: int,
    col: str,
    split: str | None = None,
    l2: float = 0.0,
) -> float | None:
    """Single cross-seed cell from an aggregate frame, or None if absent."""
    sub = frame[
        (frame["method"] == method)
        & (frame["l2_lambda"] == l2)
        & (frame["budget_requested"] == budget)
    ]
    if split is not None and "split" in frame.columns:
        sub = sub[sub["split"] == split]
    if sub.empty:
        return None
    return float(sub[col].iloc[0])


def render_paper_anchor_comparison(
    df: pd.DataFrame, *, budget: int, holdout_type: str = "fixed_family"
) -> str:
    """``tab:sampling_comparison``: all methods at the anchor budget, l2=0.

    Median-led (in-sample + out-of-sample) with the tail-sensitive out-of-sample
    mean alongside, plus the ESS and largest weight the accuracy is bought at.
    """
    fmed = aggregate.frontier_table(df, metric="median_are", holdout_type=holdout_type)
    fmean = aggregate.frontier_table(df, metric="mean_are", holdout_type=holdout_type)
    ess = aggregate.run_metric(df, metric="ess", holdout_type=holdout_type)
    maxw = aggregate.run_metric(df, metric="max_weight", holdout_type=holdout_type)
    methods = [m for m in SWEEP_METHOD_ORDER if m in set(fmed["method"])]
    n_seeds = int(fmed["n_seeds"].max()) if "n_seeds" in fmed else 0
    rows = []
    for m in methods:
        rows.append(
            f"{SWEEP_METHOD_LABELS[m]} & {_count(budget)} & "
            f"{_pct1(_at(fmed, method=m, budget=budget, col='median_are_mean', split='in_sample'))} & "
            f"{_pct1(_at(fmed, method=m, budget=budget, col='median_are_mean', split='out_of_sample'))} & "
            f"{_pct1(_at(fmean, method=m, budget=budget, col='mean_are_mean', split='out_of_sample'))} & "
            f"{_count(_at(ess, method=m, budget=budget, col='ess_mean'))} & "
            f"{_count(_at(maxw, method=m, budget=budget, col='max_weight_mean'))} \\\\"
        )
    body = "\n".join(rows)
    return rf"""\begin{{table}}[H]
\centering
{{\tablefont
\resizebox{{\textwidth}}{{!}}{{%
\begin{{tabular}}{{p{{0.20\textwidth}}rrrrrr}}
\toprule
Method & Budget & In-sample median ARE (\%) & Out-of-sample median ARE (\%) & Out-of-sample mean ARE (\%) & ESS & Max weight \\
\midrule
{body}
\bottomrule
\end{{tabular}}
}}
}}
\caption{{Informed $L_0$ sampling against the matched-budget baselines at a representative budget (the
$\sim$10{{,}}000-record anchor of Figure~\ref{{fig:budget_frontier}}), at $\lambda_{{L_2}}=0$. All methods
share the candidate universe, the target set, and the fixed family-level holdout, and differ only in how
records are selected. ARE is absolute relative error across the scored targets; the median is the headline
read and the mean is reported alongside as tail-sensitive. ESS is the Kish effective sample size, reported
as an output diagnostic because a sampler can fit the targets while concentrating population mass on a few
records. Cells are the cross-seed summary over {n_seeds} seeds.}}
\label{{tab:sampling_comparison}}
\tablenote{{The matched record budget and target counts are read from each run's manifest; the
out-of-sample columns score the held-out families. The survey-weight baseline is the unbiased
Hansen--Hurwitz integerisation (probability-proportional-to-size with replacement). Informed $L_0$ and
informed $L_1$ runtimes include the outer budget bisection that sets their penalty; the matched baselines
run once at the budget. Runtime and the family macro-average are reported in the run summary.}}
\end{{table}}
"""


def render_paper_geography_accuracy(
    df: pd.DataFrame,
    *,
    budget: int,
    method: str = "informed_l0",
    holdout_type: str = "fixed_family",
) -> str:
    """``tab:calibration_accuracy``: informed-L0 in-sample ARE by geography, l2=0."""
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["method"] == method)
        & (df["l2_lambda"] == 0.0)
        & (df["budget_requested"] == budget)
        & (df["split"] == "in_sample")
    ]

    def geo(level: str, metric: str) -> float | None:
        s = sub[(sub["scope"] == "geography") & (sub["scope_value"] == level) & (sub["metric"] == metric)]
        return float(s["value"].mean()) if not s.empty else None

    def over(metric: str) -> float | None:
        s = sub[(sub["scope"] == "overall") & (sub["metric"] == metric)]
        return float(s["value"].mean()) if not s.empty else None

    def grow(label: str, level: str, *, bold: bool = False) -> str:
        get = over if level == "overall" else (lambda metric: geo(level, metric))
        lab = rf"\textbf{{{label}}}" if bold else label
        return (
            f"{lab} & {_count(get('n'))} & {_pct1(get('median_are'))} & "
            f"{_pct1(get('mean_are'))} & {_pct1(get('max_are'))} \\\\"
        )

    body = "\n".join([grow("National", "national"), grow("State", "state")])
    total = grow("All scored targets", "overall", bold=True)
    return rf"""\begin{{table}}[H]
\centering
{{\tablefont
\begin{{tabular}}{{lrrrr}}
\toprule
Geographic level & Targets & Median ARE (\%) & Mean ARE (\%) & Max ARE (\%) \\
\midrule
{body}
\midrule
{total}
\bottomrule
\end{{tabular}}
}}
\caption{{Calibration accuracy by geographic level for the informed $L_0$ run at the representative
$\sim$10{{,}}000-record budget, measured as absolute relative error (ARE) across the in-sample targets.
The median reports the typical target's error; the mean and maximum are inflated by a handful of
near-zero-denominator targets whose relative error is large despite small absolute misses
(Section~\ref{{sec:results-degenerate}}).}}
\label{{tab:calibration_accuracy}}
\tablenote{{Target counts are read from the run manifest. No congressional-district targets are in the
prioritized subset, so that level is not scored. Out-of-sample geographic accuracy is not broken out
here; the aggregate held-out error appears in Table~\ref{{tab:sampling_comparison}} and
Figure~\ref{{fig:budget_frontier}}.}}
\end{{table}}
"""


def render_paper_presets(
    df: pd.DataFrame, *, method: str = "informed_l0", holdout_type: str = "fixed_family"
) -> str:
    """``tab:presets``: the converged L0 penalty and achieved count per budget, l2=0."""
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["method"] == method)
        & (df["l2_lambda"] == 0.0)
        & (df["scope"] == "run")
    ]
    budgets = sorted(int(b) for b in sub["budget_requested"].unique())

    def metric_at(budget: int, metric: str) -> float | None:
        s = sub[(sub["budget_requested"] == budget) & (sub["metric"] == metric)]
        return float(s["value"].mean()) if not s.empty else None

    n_seeds = int(sub.groupby("budget_requested")["seed"].nunique().max()) if not sub.empty else 0
    rows = []
    for b in budgets:
        rows.append(
            f"{_count(b)} & {_sci(metric_at(b, 'l0_lambda'))} & "
            f"{_count(metric_at(b, 'n_selected'))} \\\\"
        )
    body = "\n".join(rows)
    return rf"""\begin{{table}}[H]
\centering
{{\tablefont
\begin{{tabular}}{{rrr}}
\toprule
Requested records & $\lambda_{{L_0}}$ (converged) & Achieved records \\
\midrule
{body}
\bottomrule
\end{{tabular}}
}}
\caption{{The sparsity penalty $\lambda_{{L_0}}$ that each requested record count converged to under the
eight-step budget bisection (informed $L_0$, $\lambda_{{L_2}}=0$), with the achieved retained-record
count. Values are means over {n_seeds} seeds. A larger $\lambda_{{L_0}}$ prunes more records; the
bisection sets it per build rather than by hand.}}
\label{{tab:presets}}
\tablenote{{$\lambda_{{L_0}}$ and the achieved count are read from each run's metrics; the achieved count
is within three per cent of the requested count at every budget.}}
\end{{table}}
"""


def render_paper_paired_comparison(
    df: pd.DataFrame,
    *,
    challenger: str = "informed_l0",
    baseline: str = "random_reweight",
    holdout_type: str = "fixed_family",
) -> str:
    """``tab:paired_comparison``: same-seed L0-vs-baseline ARE diff per budget, l2=0.

    Median-led to match the paper's headline metric, with the tail-sensitive mean
    reported alongside. Both columns are paired (same-seed) differences: a negative
    delta favours the challenger.
    """

    def paired(metric: str) -> pd.DataFrame:
        p = aggregate.paired_method_diff(
            df, challenger=challenger, baseline=baseline, holdout_type=holdout_type, metric=metric
        )
        return p[p["l2_lambda"] == 0.0] if not p.empty else p

    med, mean = paired("median_are"), paired("mean_are")
    ch_label = SWEEP_METHOD_LABELS.get(challenger, challenger)
    bl_label = SWEEP_METHOD_LABELS.get(baseline, baseline)
    n_seeds = int(med["n_seeds"].max()) if not med.empty else 0
    med_by_b = {int(r["budget_requested"]): r for _, r in med.iterrows()}
    mean_by_b = {int(r["budget_requested"]): r for _, r in mean.iterrows()}

    def block(r: Any) -> list[str]:
        if r is None:
            return ["--", "--", "--"]
        delta = (
            f"{_pct1(r['diff_mean'])} "
            rf"{{\scriptsize[{_pct1(r['diff_lo'])}, {_pct1(r['diff_hi'])}]}}"
        )
        return [_pct1(r[f"{challenger}_mean"]), _pct1(r[f"{baseline}_mean"]), delta]

    rows = []
    for b in sorted(med_by_b):
        cells = [_count(b), *block(med_by_b.get(b)), *block(mean_by_b.get(b))]
        rows.append(" & ".join(cells) + r" \\")
    body = "\n".join(rows)
    return rf"""\begin{{table}}[H]
\centering
{{\tablefont
\resizebox{{\textwidth}}{{!}}{{%
\begin{{tabular}}{{rrrrrrr}}
\toprule
 & \multicolumn{{3}}{{c}}{{Median ARE (\%)}} & \multicolumn{{3}}{{c}}{{Mean ARE (\%)}} \\
\cmidrule(lr){{2-4}}\cmidrule(lr){{5-7}}
Budget & {ch_label} & {bl_label} & $\Delta$ (pp) & {ch_label} & {bl_label} & $\Delta$ (pp) \\
\midrule
{body}
\bottomrule
\end{{tabular}}
}}
}}
\caption{{Paired out-of-sample comparison of {ch_label} against {bl_label} at each budget, on the
headline median and the tail-sensitive mean. Each $\Delta$ is the cross-seed mean of the per-seed
difference between the methods (negative favours {ch_label}) with a 95\% confidence interval over the
{n_seeds} paired seeds; a paired $t$-test on these differences is reported in the text as a descriptive
diagnostic. On the median {ch_label} leads only under aggressive compression, where a small random draw
cannot span the targets; on the mean it leads at every budget, because the mean tracks the seed-to-seed
tail that {bl_label} cannot control. Numbers are the un-penalised ($\lambda_{{L_2}}=0$) rows.}}
\label{{tab:paired_comparison}}
\end{{table}}
"""


# Result tables copied into ``paper/tables/`` by ``l0 figures --paper-figures``.
PAPER_TABLE_NAMES = ("sampling_comparison", "calibration_accuracy", "presets", "paired_comparison")


def write_paper_tables(out_dir: str | Path, df: pd.DataFrame, *, budget: int) -> dict[str, Path]:
    """Write the curated paper result tables into ``out_dir``; return paths by name."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: out_dir / f"{name}.tex" for name in PAPER_TABLE_NAMES}
    paths["sampling_comparison"].write_text(render_paper_anchor_comparison(df, budget=budget))
    paths["calibration_accuracy"].write_text(render_paper_geography_accuracy(df, budget=budget))
    paths["presets"].write_text(render_paper_presets(df))
    paths["paired_comparison"].write_text(render_paper_paired_comparison(df))
    return paths
