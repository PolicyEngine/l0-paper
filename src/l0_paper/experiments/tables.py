"""Render paper-ready LaTeX tables from run summaries.

The generated tables drop into ``paper/tables/`` in place of the ``\\tbc``
placeholders. Only the rows this experiment produces are filled (informed L0 and
the dense + weighted-sampling baseline, which the paper labels "Survey-weight
sampling"); the other two paper-method rows stay ``\\tbc`` until implemented.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


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
            row("Random + reweight", None),
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
