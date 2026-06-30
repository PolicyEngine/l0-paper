#!/usr/bin/env python
"""Figures + reporting for the budget sweep (``metrics_long.csv``).

Reads the sweep's tidy long CSV, aggregates it with
:mod:`l0_paper.experiments.aggregate`, and emits:

* **LaTeX tables** (frontier, paired comparison, rotation) and a Markdown summary
  -- these need no plotting dependency.
* **matplotlib figures** (PNG, paper-ready) -- the frontier and its
  supporting cuts. matplotlib is imported lazily, so if the ``viz`` extra is not
  installed the tables/summary are still written and the figures are skipped with
  a note.

Figures
-------
* F0  objective frontier: Populace capped weighted loss vs retained records.
* F1  raw-error frontier: mean & median ARE vs average retained records.
* F2  usability: effective sample size and max weight vs budget.
* F3  generalization gap: out-of-sample minus in-sample mean ARE when a holdout exists.
* F4  by-family ARE at the anchor budget when a holdout exists.
* F5  cost-accuracy: runtime vs the headline split's median ARE.

Run
---
    uv run --extra viz l0 figures \
        --sweep runs/sweep-moderate \
        --paper-figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from l0_paper.experiments import aggregate, crunch, tables
from l0_paper.experiments.tables import SWEEP_METHOD_LABELS, SWEEP_METHOD_ORDER

# Fonts are vendored with the package (found via __file__, so they ship in the
# wheel). The paper's figure directory is resolved from the working directory --
# these commands run from the repo checkout.
FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts" / "Inter"
PAPER_FIGURES = Path.cwd() / "paper" / "figures"
PAPER_TABLES = Path.cwd() / "paper" / "tables"

# PolicyEngine palette (theme.css --chart-1/2/5), stable per method across every
# figure. Each method also gets a distinct marker so the series stay legible in
# grayscale -- the design system asks for charts that don't rely on colour alone.
METHOD_COLORS = {
    "informed_l0_refit": "#0F766E",  # darker teal for post-selection refit
    "informed_l0": "#319795",  # --chart-1 teal (the informed method)
    "informed_l1": "#026AA2",  # --chart-4 dark blue (convex-sparse L1 analog)
    "random_reweight": "#0EA5E9",  # --chart-2 blue
    "dense_sample": "#6B7280",  # --chart-5 gray (naive survey-weight baseline)
}
METHOD_MARKERS = {
    "informed_l0_refit": "o",
    "informed_l0": "o",
    "informed_l1": "D",
    "random_reweight": "s",
    "dense_sample": "^",
}
# The method-comparison figures (F1-F5) fix lambda_L2 at this value; the
# accuracy <-> ESS trade-off as lambda_L2 varies gets its own figure (F6).
COMPARISON_L2 = 0.0


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
        families = manifest.get("frontier_split", {}).get(
            "validation_only_families", []
        )
        return tuple(str(f) for f in families)
    return ("cbo",)


def _sweep_manifest(long_csv: Path) -> dict:
    manifest_path = long_csv.parent / "sweep_manifest.json"
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text())
    return {}


def _default_anchor_budget(df: pd.DataFrame, requested: int | None) -> int | None:
    """Choose a fixed-family L2 anchor budget for operability plots.

    Prefer an explicit anchor when it exists in the fixed-family frontier. When
    none is supplied, use the median requested budget among budgets with the
    richest L2 grid; this avoids accidentally picking the smallest budget merely
    because it appears first in a groupby result.
    """
    l0_runs = df[
        (df["holdout_type"] == "fixed_family")
        & (df["method"] == "informed_l0")
        & (df["scope"] == "run")
        & (df["metric"] == "ess")
    ]
    if l0_runs.empty:
        return requested

    available = sorted(int(b) for b in l0_runs["budget_requested"].unique())
    if requested is not None and int(requested) in available:
        return int(requested)

    l2_counts = l0_runs.groupby("budget_requested")["l2_lambda"].nunique()
    if l2_counts.empty:
        return requested
    max_l2 = int(l2_counts.max())
    candidates = sorted(int(b) for b, n in l2_counts.items() if int(n) == max_l2)
    if not candidates:
        return requested
    return candidates[len(candidates) // 2]


def _headline_label(split: str) -> str:
    return "Out-of-sample" if split == "out_of_sample" else "Full-surface in-sample"


def _headline_l0_method(df: pd.DataFrame) -> str:
    methods = set(df["method"]) if "method" in df.columns else set()
    return "informed_l0_refit" if "informed_l0_refit" in methods else "informed_l0"


def _objective_across_seeds(seed_summary: pd.DataFrame) -> pd.DataFrame:
    """Collapse seed-level objective summaries to cross-seed means and CIs."""
    if seed_summary.empty:
        return seed_summary
    group_cols = [
        c
        for c in ("method", "split", "l2_lambda", "budget_requested")
        if c in seed_summary.columns
    ]
    metrics = ("objective_capped_weighted", "median_are", "mean_are", "frac_within")
    records: list[dict] = []
    for key, sub in seed_summary.groupby(group_cols, sort=True):
        key_tuple = key if isinstance(key, tuple) else (key,)
        record = dict(zip(group_cols, key_tuple, strict=True))
        record["n_seeds"] = (
            int(sub["seed"].nunique()) if "seed" in sub else int(len(sub))
        )
        if "n" in sub:
            record["n"] = int(round(float(sub["n"].mean())))
        for metric in metrics:
            if metric not in sub:
                continue
            mean, lo, hi = aggregate.mean_ci(sub[metric])
            record[f"{metric}_mean"] = mean
            record[f"{metric}_lo"] = lo
            record[f"{metric}_hi"] = hi
        records.append(record)
    return pd.DataFrame.from_records(records)


def write_reports(long_csv: Path, out_dir: Path, *, anchor_budget: int | None) -> dict:
    """Aggregate the long CSV and write LaTeX tables + a Markdown summary."""
    df = aggregate.load_long(long_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    anchor_budget = _default_anchor_budget(df, anchor_budget)
    manifest = _sweep_manifest(long_csv)
    target_loss_cap = float(manifest.get("target_loss", {}).get("cap", 1.0))
    validation_only = _validation_only_families(long_csv)
    l2_values = sorted(df["l2_lambda"].dropna().unique().tolist())
    multi_l2 = len(l2_values) > 1

    has_rotation = "rotation" in set(df["holdout_type"])
    # frontier_table returns both splits; render_frontier filters by split.
    frontier = aggregate.frontier_table(df, metric="mean_are")
    frontier_median = aggregate.frontier_table(df, metric="median_are")
    # Targeted-removal sensitivity: mean with the named denominator-degenerate
    # targets dropped (emitted only where such targets exist -- chiefly in-sample).
    has_exdeg = (df["metric"] == "mean_are_ex_degenerate").any()
    frontier_exdeg = (
        aggregate.frontier_table(df, metric="mean_are_ex_degenerate")
        if has_exdeg
        else None
    )
    paired = pd.DataFrame()
    macro = pd.DataFrame()
    rotation_front = (
        aggregate.rotation_frontier_table(
            df,
            metric="mean_are",
            validation_only_families=validation_only,
        )
        if has_rotation
        else None
    )

    frontier_oos = frontier
    headline_split = "out_of_sample"
    if frontier_oos[
        (frontier_oos["split"] == "out_of_sample")
        & frontier_oos["mean_are_mean"].notna()
    ].empty:
        headline_split = "in_sample"
    headline_label = _headline_label(headline_split)
    headline_l0 = _headline_l0_method(df)
    headline_l0_label = SWEEP_METHOD_LABELS.get(headline_l0, headline_l0).replace(
        "$", ""
    )
    paired = aggregate.paired_method_diff(
        df, challenger=headline_l0, split=headline_split
    )
    macro = aggregate.macro_average(df, split=headline_split)

    table_paths = tables.write_sweep_tables(
        out_dir / "tables",
        frontier_oos=frontier,
        frontier_in=frontier,
        paired=paired,
        rotation_oos=rotation_front,
        paired_challenger=headline_l0,
        paired_split=headline_split,
    )
    # Curated paper result tables (median-led, all methods, l2=0), regenerated from
    # the same sweep so paper/tables/ stays in sync. Kept in a separate directory so
    # they do not clobber the report's frontier-style tables above.
    paper_table_paths = tables.write_paper_tables(
        out_dir / "paper_tables", df, budget=anchor_budget
    )

    # Markdown summary. Lead with the Populace objective loss (capped, weighted,
    # penalty-free), with ARE tables as companion diagnostics.
    oos = frontier_oos[frontier_oos["split"] == headline_split]
    methods = [m for m in SWEEP_METHOD_ORDER if m in set(oos["method"])]

    def _display_groups(front, *, split: str = "out_of_sample"):
        sub = front[front["split"] == split]
        groups = []
        for method in methods:
            for l2 in sorted(sub[sub["method"] == method]["l2_lambda"].unique()):
                label = SWEEP_METHOD_LABELS[method].replace("$", "")
                if multi_l2:
                    label = f"{label} (l2={float(l2):g})"
                groups.append((method, float(l2), label))
        return groups

    def _budget_table(
        front, value_col: str, *, split: str = "out_of_sample"
    ) -> list[str]:
        sub = front[front["split"] == split]
        groups = _display_groups(front, split=split)
        first_col = "Requested budget" if multi_l2 else "Average retained records"
        out_lines = [
            f"| {first_col} | " + " | ".join(label for _, _, label in groups) + " |",
            "| --- | " + " | ".join("---" for _ in groups) + " |",
        ]
        for budget in sorted(sub["budget_requested"].unique()):
            retained = sub[sub["budget_requested"] == budget]["budget_achieved"].mean()
            cells = []
            for method, l2, _label in groups:
                row = sub[
                    (sub["method"] == method)
                    & (sub["l2_lambda"] == l2)
                    & (sub["budget_requested"] == budget)
                ]
                cells.append(_fmt_pct(row[value_col].iloc[0]) if not row.empty else "")
            first = f"{budget:,.0f}" if multi_l2 else f"{retained:,.0f}"
            out_lines.append(f"| {first} | " + " | ".join(cells) + " |")
        return out_lines

    def _objective_budget_table(summary: pd.DataFrame) -> list[str]:
        if summary.empty:
            return ["No per-target diagnostics available for objective scoring."]
        value_col = (
            "objective_capped_weighted_mean"
            if "objective_capped_weighted_mean" in summary.columns
            else "objective_capped_weighted"
        )
        groups = []
        for method in methods:
            for l2 in sorted(
                summary[summary["method"] == method]["l2_lambda"].unique()
            ):
                label = SWEEP_METHOD_LABELS[method].replace("$", "")
                if multi_l2:
                    label = f"{label} (l2={float(l2):g})"
                groups.append((method, float(l2), label))
        first_col = "Requested budget" if multi_l2 else "Budget"
        out_lines = [
            f"| {first_col} | " + " | ".join(label for _, _, label in groups) + " |",
            "| --- | " + " | ".join("---" for _ in groups) + " |",
        ]
        for budget in sorted(summary["budget_requested"].unique()):
            cells = []
            for method, l2, _label in groups:
                row = summary[
                    (summary["method"] == method)
                    & (summary["l2_lambda"] == l2)
                    & (summary["budget_requested"] == budget)
                ]
                cells.append(_fmt_pct(row[value_col].iloc[0]) if not row.empty else "")
            out_lines.append(f"| {int(budget):,.0f} | " + " | ".join(cells) + " |")
        return out_lines

    diag_path = long_csv.parent / "target_diagnostics_long.csv"
    objective_summary = pd.DataFrame()
    if diag_path.exists():
        diag = aggregate.load_target_diagnostics(diag_path)
        objective_seed_summary = crunch.summarize(
            diag[diag["split"] == headline_split],
            cap=target_loss_cap,
            group=("method", "split", "l2_lambda", "budget_requested", "seed"),
        )
        objective_summary = _objective_across_seeds(objective_seed_summary)
        if not objective_summary.empty:
            objective_summary.to_csv(out_dir / "objective_summary.csv", index=False)

    lines = [
        f"# Sweep summary: {long_csv.parent.name}",
        "",
        f"- Budgets: `{sorted(oos['budget_requested'].unique().tolist())}`",
        f"- Seeds per point: `{int(oos['n_seeds'].max()) if not oos.empty else 0}`",
        f"- Headline split: `{headline_split}`",
        f"- Populace loss cap: `{target_loss_cap:g}`",
        f"- Rotation panel: `{'yes' if has_rotation else 'no'}`",
        "",
        f"## {headline_label} Populace objective loss (%) by budget (headline; capped weighted MAPE, penalty-free)",
        "",
        *_objective_budget_table(objective_summary),
        "",
        f"## {headline_label} median ARE (%) by budget (supplement; robust to the near-zero tail)",
        "",
        *_budget_table(frontier_median, "median_are_mean", split=headline_split),
        "",
        f"## {headline_label} mean ARE (%) by budget (supplement; tail-sensitive; see degenerate audit)",
        "",
        *_budget_table(frontier_oos, "mean_are_mean", split=headline_split),
    ]

    lines += [
        "",
        f"## Paired {headline_l0_label} vs random+reweight ({headline_label.lower()})",
        "",
    ]
    if not paired.empty:
        lines.append("| Budget | L0 arm | random | diff (pp) | p | CI excludes 0 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for _, r in paired.iterrows():
            budget_label = f"{r['budget_requested']:,.0f}"
            if multi_l2:
                budget_label = f"{budget_label} (l2={r['l2_lambda']:g})"
            lines.append(
                f"| {budget_label} | {_fmt_pct(r[f'{headline_l0}_mean'])} | "
                f"{_fmt_pct(r['random_reweight_mean'])} | {r['diff_mean'] * 100:+.2f} | "
                f"{r['p_value']:.3f} | {'yes' if r['ci_excludes_zero'] else 'no'} |"
            )

    # Family macro-average (equal weight per family) de-biases the SOI-dominated
    # micro mean -- a secondary read on whether a method wins broadly or just on SOI.
    lines += ["", f"## {headline_label} family macro-average mean ARE (%)", ""]
    if not macro.empty:
        groups = _display_groups(frontier_oos, split=headline_split)
        lines.append("| Budget | " + " | ".join(label for _, _, label in groups) + " |")
        lines.append("| --- | " + " | ".join("---" for _ in groups) + " |")
        for budget in sorted(macro["budget_requested"].unique()):
            cells = []
            for method, l2, _label in groups:
                row = macro[
                    (macro["method"] == method)
                    & (macro["l2_lambda"] == l2)
                    & (macro["budget_requested"] == budget)
                ]
                cells.append(
                    _fmt_pct(row["macro_mean_are_mean"].iloc[0])
                    if not row.empty
                    else ""
                )
            lines.append(f"| {budget:,.0f} | " + " | ".join(cells) + " |")

    def _raw_metric_budget_table(
        *,
        title: str,
        note: str,
        split: str,
        scope: str,
        metric: str,
        formatter,
    ) -> None:
        sub = df[
            (df["holdout_type"] == "fixed_family")
            & (df["split"] == split)
            & (df["scope"] == scope)
            & (df["metric"] == metric)
        ]
        if sub.empty:
            return
        metric_methods = [m for m in SWEEP_METHOD_ORDER if m in set(sub["method"])]
        lines.extend(["", title, "", note, ""])
        lines.append(
            "| Budget / l2 | "
            + " | ".join(
                SWEEP_METHOD_LABELS[m].replace("$", "") for m in metric_methods
            )
            + " |"
        )
        lines.append("| --- | " + " | ".join("---" for _ in metric_methods) + " |")
        for budget in sorted(frontier_oos["budget_requested"].unique()):
            for l2 in sorted(
                frontier_oos[frontier_oos["budget_requested"] == budget][
                    "l2_lambda"
                ].unique()
            ):
                cells = []
                for method in metric_methods:
                    row = sub[
                        (sub["method"] == method)
                        & (sub["l2_lambda"] == l2)
                        & (sub["budget_requested"] == budget)
                    ]
                    cells.append(
                        formatter(row["value"].mean()) if not row.empty else ""
                    )
                lines.append(
                    f"| {budget:,.0f} / {float(l2):g} | " + " | ".join(cells) + " |"
                )

    _raw_metric_budget_table(
        title="## In-sample mean ARE (%) on final retained records",
        note=(
            "Actual fit-target error after each method's final retained/sampled "
            "weight vector is scored. This replaces solver `final_loss` for the "
            "sampling methods: for `dense_sample`, the stored `final_loss` is "
            "the dense pre-sampling calibration loss, not the post-sampling "
            "vector's error."
        ),
        split="in_sample",
        scope="overall",
        metric="mean_are",
        formatter=_fmt_pct,
    )
    _raw_metric_budget_table(
        title="## Effective sample size by budget",
        note=(
            "ESS is computed on each method's final full weight vector, then "
            "averaged over seeds. For nonzero `l2`, only `Informed L_0` uses "
            "the L2 penalty; the other methods are rerun at the matched "
            "achieved budget for that L0 configuration."
        ),
        split="na",
        scope="run",
        metric="ess",
        formatter=lambda value: f"{float(value):,.0f}",
    )

    # In-sample targeted-removal sensitivity: the mean before/after dropping the
    # *named* denominator-degenerate targets (no winsorization), led by the median.
    lines += [
        "",
        f"## In-sample degenerate-target sensitivity ({headline_l0_label})",
        "",
    ]
    if frontier_exdeg is not None:
        in_mean = frontier_oos[frontier_oos["split"] == "in_sample"]
        in_med = frontier_median[frontier_median["split"] == "in_sample"]
        in_exd = frontier_exdeg[frontier_exdeg["split"] == "in_sample"]
        ndeg = df[
            (df["holdout_type"] == "fixed_family")
            & (df["split"] == "in_sample")
            & (df["scope"] == "overall")
            & (df["metric"] == "n_degenerate")
        ]
        first_col = "Budget / l2" if multi_l2 else "Budget"
        lines += [
            "Mean ARE before/after dropping the *named* denominator-degenerate "
            "targets (identifiability floor, `degenerate_targets.csv`); median leads.",
            "",
            f"| {first_col} | mean | mean (ex-degenerate) | median | n_degenerate |",
            "| --- | --- | --- | --- | --- |",
        ]

        def _pick(front, col, budget, l2):
            r = front[
                (front["method"] == headline_l0)
                & (front["l2_lambda"] == l2)
                & (front["budget_requested"] == budget)
            ]
            return _fmt_pct(r[col].iloc[0]) if not r.empty else ""

        for budget in sorted(in_mean["budget_requested"].unique()):
            for l2 in sorted(
                in_mean[in_mean["budget_requested"] == budget]["l2_lambda"].unique()
            ):
                nd = ndeg[
                    (ndeg["method"] == headline_l0)
                    & (ndeg["l2_lambda"] == l2)
                    & (ndeg["budget_requested"] == budget)
                ]["value"]
                nd_val = f"{nd.mean():.0f}" if not nd.empty else ""
                budget_label = f"{budget:,.0f}"
                if multi_l2:
                    budget_label = f"{budget_label} / {float(l2):g}"
                lines.append(
                    f"| {budget_label} | {_pick(in_mean, 'mean_are_mean', budget, l2)} | "
                    f"{_pick(in_exd, 'mean_are_ex_degenerate_mean', budget, l2)} | "
                    f"{_pick(in_med, 'median_are_mean', budget, l2)} | {nd_val} |"
                )
    else:
        lines.append("No denominator-degenerate targets in the fit split.")

    # Attribution: which named targets drive the out-of-sample mean (no trimming).
    lines += [
        "",
        f"## {headline_label} ARE attribution: top targets driving the mean ({headline_l0_label})",
        "",
    ]
    if diag_path.exists() and not oos.empty:
        diag = aggregate.load_target_diagnostics(diag_path)
        max_budget = int(sorted(oos["budget_requested"].unique())[-1])
        skipped_attribution = False
        if multi_l2:
            lines.append(
                "Skipped in the combined multi-l2 report to avoid mixing penalty "
                "values; call `aggregate.top_are_contributors(..., l2_lambda=...)` "
                "for a specific penalty."
            )
            skipped_attribution = True
            top = None
        else:
            top = aggregate.top_are_contributors(
                diag,
                method=headline_l0,
                budget_requested=max_budget,
                l2_lambda=l2_values[0] if l2_values else 0.0,
                split=headline_split,
                top_k=12,
            )
        if top is not None and not top.empty:
            lines += [
                f"`{headline_l0}` at budget {max_budget:,}, mean over seeds. "
                "`deg` flags denominator-degenerate targets.",
                "",
                "| Target | Family | ARE (%) | Share of mean | deg |",
                "| --- | --- | --- | --- | --- |",
            ]
            for _, r in top.iterrows():
                name = str(r["target_name"])
                short = name if len(name) <= 60 else name[:57] + "..."
                lines.append(
                    f"| {short} | {r['family']} | {_fmt_pct(r['mean_are'])} | "
                    f"{r['share_of_mean'] * 100:.1f}% | {'yes' if r['is_degenerate'] else ''} |"
                )
        elif not skipped_attribution:
            lines.append("No per-target diagnostics for this config.")
    else:
        lines.append(
            "No per-target diagnostics CSV found (run the sweep to generate it)."
        )

    lines += ["", "## Rotation robustness: target-weighted mean ARE (%)", ""]
    if rotation_front is not None and not rotation_front.empty:
        lines.append(
            "Each seed's rotation folds are aggregated first; validation-only "
            f"families excluded from this aggregate: `{list(validation_only)}`."
        )
        lines.append("")
        rot_oos = rotation_front[rotation_front["split"] == "out_of_sample"]
        rot_groups = _display_groups(rotation_front)
        first_col = "Requested budget" if multi_l2 else "Average retained records"
        lines.append(
            "| "
            + first_col
            + " | "
            + " | ".join(label for _, _, label in rot_groups)
            + " |"
        )
        lines.append("| --- | " + " | ".join("---" for _ in rot_groups) + " |")
        for budget in sorted(rot_oos["budget_requested"].unique()):
            cells = []
            retained = rot_oos[rot_oos["budget_requested"] == budget][
                "budget_achieved"
            ].mean()
            for method, l2, _label in rot_groups:
                row = rot_oos[
                    (rot_oos["method"] == method)
                    & (rot_oos["budget_requested"] == budget)
                    & (rot_oos["l2_lambda"] == l2)
                ]
                cells.append(
                    _fmt_pct(row["mean_are_mean"].iloc[0]) if not row.empty else ""
                )
            first = f"{budget:,.0f}" if multi_l2 else f"{retained:,.0f}"
            lines.append(f"| {first} | " + " | ".join(cells) + " |")
    else:
        lines.append("No rotation panel found.")

    # Per-fold rotation (descriptive): each fold holds out *different* families, so
    # these are NOT iid replicates. Shown to surface folds where a method
    # generalises poorly -- notably the fold holding out the dominant irs_soi family.
    if has_rotation:
        rot = df[(df["holdout_type"] == "rotation") & (df["split"] == "out_of_sample")]
        fams = rot[(rot["scope"] == "family") & (rot["metric"] == "mean_are")]
        lines += [
            "",
            "## Rotation per-fold (descriptive; folds are different held-out families, not replicates)",
            "",
            "Each cell is mean / median OOS ARE (%) over seeds.",
            "",
            "| Fold | Held-out families | "
            + " | ".join(label for _, _, label in _display_groups(frontier_oos))
            + " |",
            "| --- | --- | "
            + " | ".join("---" for _ in _display_groups(frontier_oos))
            + " |",
        ]
        for fold in sorted(rot["fold"].unique()):
            held = ", ".join(sorted(fams[fams["fold"] == fold]["scope_value"].unique()))
            cells = []
            for m, l2, _label in _display_groups(frontier_oos):
                ov = rot[
                    (rot["fold"] == fold)
                    & (rot["method"] == m)
                    & (rot["l2_lambda"] == l2)
                    & (rot["scope"] == "overall")
                ]
                mean_v = ov[ov["metric"] == "mean_are"]["value"].mean()
                med_v = ov[ov["metric"] == "median_are"]["value"].mean()
                cells.append(f"{_fmt_pct(mean_v)} / {_fmt_pct(med_v)}")
            lines.append(f"| {int(fold)} | {held} | " + " | ".join(cells) + " |")

    summary_path = out_dir / "sweep_summary.md"
    summary_path.write_text("\n".join(lines) + "\n")

    return {
        "df": df,
        "frontier": frontier_oos,
        "macro": macro,
        "paired": paired,
        "rotation": rotation_front,
        "objective_summary": objective_summary,
        "headline_split": headline_split,
        "headline_label": headline_label,
        "target_loss_cap": target_loss_cap,
        "has_rotation": has_rotation,
        "validation_only_families": validation_only,
        "table_paths": table_paths,
        "paper_table_paths": paper_table_paths,
        "summary": summary_path,
        "anchor_budget": anchor_budget,
    }


# --- matplotlib figures (lazy import) ------------------------------------------


def _label(method: str, *, comparison_l2: bool = False) -> str:
    label = SWEEP_METHOD_LABELS.get(method, method)
    if comparison_l2 and method == "informed_l0":
        label = rf"{label} ($\lambda_{{L_2}}=0$)"
    return label


def _setup_style() -> None:
    """Register the vendored Inter font and set PolicyEngine paper-figure rcParams.

    Falls back to a system sans stack (with a one-line install hint) when the
    vendored TTFs are absent, so figure generation never hard-fails on the font.
    """
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    ttfs = sorted(FONTS_DIR.glob("*.ttf")) if FONTS_DIR.is_dir() else []
    for ttf in ttfs:
        fm.fontManager.addfont(str(ttf))
    if not ttfs:
        print(
            "Inter not vendored under l0_paper/cli/assets/fonts/Inter -- falling "
            "back to a system sans. For brand fidelity: brew install --cask font-inter"
        )

    plt.rcParams.update(
        {
            "font.family": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": 12,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "legend.title_fontsize": 10,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "figure.titlesize": 14,
            "axes.edgecolor": "#475569",  # gray-600
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlecolor": "#101828",  # gray-900
            "axes.labelcolor": "#101828",
            "text.color": "#101828",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "grid.color": "#E2E8F0",  # --border / gray-200
            "grid.linewidth": 0.7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _budget_label(budget: int) -> str:
    b = int(budget)
    return f"{b // 1000}k" if b >= 1000 and b % 1000 == 0 else f"{b:,}"


def _budget_axis(ax, budgets) -> None:
    """Log x-axis with fixed ticks at the real budgets, no overlapping minor labels."""
    from matplotlib.ticker import FixedFormatter, FixedLocator, NullFormatter

    budgets = sorted(int(b) for b in budgets)
    if not budgets:
        return
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(budgets))
    ax.xaxis.set_major_formatter(FixedFormatter([_budget_label(b) for b in budgets]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", which="minor", length=0)


def _plot_methods(
    ax,
    agg,
    *,
    x_col,
    mean_col,
    lo_col,
    hi_col,
    scale=1.0,
    log_y=False,
    comparison_l2_label: bool = False,
):
    """One line (+ seed CI band) per method from an aggregate frame.

    Callers pass the ``COMPARISON_L2`` slice, so there is a single line per method;
    the x-axis is set separately by the caller (usually :func:`_budget_axis`).
    """
    import numpy as np

    required = {x_col, mean_col, lo_col, hi_col, "method"}
    if agg.empty or not required.issubset(agg.columns):
        return False

    plotted = False
    for method in [m for m in SWEEP_METHOD_ORDER if m in set(agg["method"])]:
        d = agg[agg["method"] == method].sort_values(x_col)
        if d.empty:
            continue
        color = METHOD_COLORS.get(method, "#444")
        marker = METHOD_MARKERS.get(method, "o")
        x = d[x_col].to_numpy(dtype=float)
        y = d[mean_col].to_numpy(dtype=float) * scale
        ax.plot(
            x,
            y,
            marker=marker,
            color=color,
            label=_label(method, comparison_l2=comparison_l2_label),
            lw=2,
            ms=6,
        )
        plotted = True
        lo = d[lo_col].to_numpy(dtype=float) * scale
        hi = d[hi_col].to_numpy(dtype=float) * scale
        if np.isfinite(lo).all() and np.isfinite(hi).all() and np.any(hi > lo):
            ax.fill_between(x, lo, hi, color=color, alpha=0.15, linewidth=0)
    if log_y:
        ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.4)
    return plotted


def _save(fig, fig_dir: Path, name: str) -> list[Path]:
    path = fig_dir / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    return [path]


def write_figures(report: dict, out_dir: Path) -> list[Path]:
    """Render the matplotlib figures; returns the files written.

    No-op (with a note) if matplotlib is missing -- tables/summary are still
    written by :func:`write_reports`.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "matplotlib not installed -- skipping figures (install the 'viz' extra). "
            "Tables and the Markdown summary were still written."
        )
        return []

    import numpy as np

    _setup_style()

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    df = report["df"]
    written: list[Path] = []
    headline_split = str(report.get("headline_split", "out_of_sample"))
    headline_label = str(report.get("headline_label", _headline_label(headline_split)))

    l2_values = sorted(float(v) for v in df["l2_lambda"].dropna().unique())

    def at_cmp_l2(frame: pd.DataFrame) -> pd.DataFrame:
        """Slice to the comparison lambda_L2 (F1-F5 hold the penalty fixed)."""
        if frame.empty or "l2_lambda" not in frame.columns:
            return frame
        return frame[frame["l2_lambda"] == COMPARISON_L2]

    def add_legend(ax, *, title: str = "Method") -> None:
        handles, _labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(title=title)

    objective_summary = at_cmp_l2(report.get("objective_summary", pd.DataFrame()))
    if not objective_summary.empty:
        value_col = (
            "objective_capped_weighted_mean"
            if "objective_capped_weighted_mean" in objective_summary.columns
            else "objective_capped_weighted"
        )
        lo_col = (
            "objective_capped_weighted_lo"
            if "objective_capped_weighted_lo" in objective_summary.columns
            else None
        )
        hi_col = (
            "objective_capped_weighted_hi"
            if "objective_capped_weighted_hi" in objective_summary.columns
            else None
        )
        required = {"method", "budget_requested", value_col}
        if required.issubset(objective_summary.columns):
            f0, ax0 = plt.subplots(figsize=(7, 4.5))
            for method in [
                m for m in SWEEP_METHOD_ORDER if m in set(objective_summary["method"])
            ]:
                d = objective_summary[
                    objective_summary["method"] == method
                ].sort_values("budget_requested")
                if d.empty:
                    continue
                color = METHOD_COLORS.get(method, "#444")
                x = d["budget_requested"].to_numpy(dtype=float)
                y = d[value_col].to_numpy(dtype=float) * 100.0
                ax0.plot(
                    x,
                    y,
                    marker=METHOD_MARKERS.get(method, "o"),
                    color=color,
                    label=_label(method),
                    lw=2,
                    ms=6,
                )
                if lo_col and hi_col:
                    lo = d[lo_col].to_numpy(dtype=float) * 100.0
                    hi = d[hi_col].to_numpy(dtype=float) * 100.0
                    if (
                        np.isfinite(lo).all()
                        and np.isfinite(hi).all()
                        and np.any(hi > lo)
                    ):
                        ax0.fill_between(
                            x, lo, hi, color=color, alpha=0.15, linewidth=0
                        )
            _budget_axis(ax0, objective_summary["budget_requested"].unique())
            ax0.set(
                title=f"{headline_label} Populace objective loss",
                xlabel="Requested budget",
                ylabel="Capped weighted MAPE (%, lower is better)",
            )
            ax0.grid(True, which="both", alpha=0.4)
            add_legend(ax0)
            f0.tight_layout()
            written += _save(f0, fig_dir, "f0_objective_frontier")
            plt.close(f0)

    # F1: frontier (headline-split median | mean) at the comparison lambda_L2, requested
    # record budget on a log x-axis. Plotting against the *requested* budget keeps
    # every method aligned at the same x ticks, so the curves stay vertically
    # comparable even though each method's achieved count differs slightly --
    # notably L1, which prunes to its own budget rather than matching L0 exactly.
    front_mean = aggregate.frontier_table(df, metric="mean_are")
    front_median = aggregate.frontier_table(df, metric="median_are")
    fm_head = at_cmp_l2(front_mean[front_mean["split"] == headline_split])
    fmed_head = at_cmp_l2(front_median[front_median["split"] == headline_split])
    requested_budgets = sorted(
        int(b) for b in set(fm_head["budget_requested"].dropna().unique())
    )

    if requested_budgets:
        f1, (ax_med, ax_mean) = plt.subplots(1, 2, figsize=(11, 4.5))
        # Log y: ARE spans several orders of magnitude on the full target surface,
        # so a linear axis is dominated by the worst point and flattens every other curve.
        plotted_med = _plot_methods(
            ax_med,
            fmed_head,
            x_col="budget_requested",
            mean_col="median_are_mean",
            lo_col="median_are_lo",
            hi_col="median_are_hi",
            scale=100.0,
            log_y=True,
        )
        plotted_mean = _plot_methods(
            ax_mean,
            fm_head,
            x_col="budget_requested",
            mean_col="mean_are_mean",
            lo_col="mean_are_lo",
            hi_col="mean_are_hi",
            scale=100.0,
            log_y=True,
        )
        if plotted_med or plotted_mean:
            for ax in (ax_mean, ax_med):
                _budget_axis(ax, requested_budgets)
                ax.set_xlabel("Requested budget")
            ax_mean.set(title="Mean ARE", ylabel=f"{headline_label} ARE (%, log)")
            ax_med.set(title="Median ARE", ylabel=f"{headline_label} ARE (%, log)")
            add_legend(ax_med)
            f1.suptitle(f"Accuracy versus requested budget ({headline_label.lower()})")
            f1.tight_layout(rect=(0, 0, 1, 0.96))
            written += _save(f1, fig_dir, "f1_frontier")
        plt.close(f1)

    # F2: usability — effective sample size and max weight vs budget.
    ess = at_cmp_l2(aggregate.run_metric(df, metric="ess"))
    maxw = at_cmp_l2(aggregate.run_metric(df, metric="max_weight"))
    usability_budgets = requested_budgets or sorted(
        int(b)
        for b in set(
            ess.get("budget_requested", pd.Series(dtype=float)).dropna().unique()
        )
    )
    f2, (ax_ess, ax_mw) = plt.subplots(1, 2, figsize=(11, 4.5))
    plotted_ess = _plot_methods(
        ax_ess,
        ess,
        x_col="budget_requested",
        mean_col="ess_mean",
        lo_col="ess_lo",
        hi_col="ess_hi",
        comparison_l2_label=True,
    )
    plotted_mw = _plot_methods(
        ax_mw,
        maxw,
        x_col="budget_requested",
        mean_col="max_weight_mean",
        lo_col="max_weight_lo",
        hi_col="max_weight_hi",
        log_y=True,
        comparison_l2_label=True,
    )
    if plotted_ess or plotted_mw:
        for ax in (ax_ess, ax_mw):
            _budget_axis(ax, usability_budgets)
            ax.set_xlabel("Requested budget")
        ax_ess.set(title="Effective sample size", ylabel="ESS")
        ax_mw.set(title="Max weight", ylabel="Max weight (log)")
        add_legend(ax_ess)
        f2.suptitle("Usability: effective sample size and weight concentration")
        f2.tight_layout(rect=(0, 0, 1, 0.96))
        written += _save(f2, fig_dir, "f2_usability")
    plt.close(f2)

    # F3: generalization gap (OOS − in-sample) mean ARE at the comparison lambda_L2.
    gap_rows = []
    fm_cmp = at_cmp_l2(front_mean)
    if "out_of_sample" in set(fm_cmp.get("split", pd.Series(dtype=str))):
        for method in [m for m in SWEEP_METHOD_ORDER if m in set(fm_cmp["method"])]:
            for budget in requested_budgets:
                o = fm_cmp[
                    (fm_cmp["method"] == method)
                    & (fm_cmp["budget_requested"] == budget)
                    & (fm_cmp["split"] == "out_of_sample")
                ]
                i = fm_cmp[
                    (fm_cmp["method"] == method)
                    & (fm_cmp["budget_requested"] == budget)
                    & (fm_cmp["split"] == "in_sample")
                ]
                if o.empty or i.empty:
                    continue
                gap_rows.append(
                    {
                        "method": method,
                        "budget_requested": int(budget),
                        "gap_mean": float(o["mean_are_mean"].iloc[0])
                        - float(i["mean_are_mean"].iloc[0]),
                        "gap_lo": float("nan"),
                        "gap_hi": float("nan"),
                    }
                )
    gap_df = pd.DataFrame(gap_rows)
    if not gap_df.empty:
        f3, ax3 = plt.subplots(figsize=(7, 4.5))
        _plot_methods(
            ax3,
            gap_df,
            x_col="budget_requested",
            mean_col="gap_mean",
            lo_col="gap_lo",
            hi_col="gap_hi",
            scale=100.0,
        )
        _budget_axis(ax3, requested_budgets)
        # Symlog y: the gap is signed (a plain log can't be used), and L1's coupled
        # prune+shrink blows its gap out by ~3 orders of magnitude over the others.
        # A symmetric-log axis keeps the inter-method structure readable near zero
        # while still showing L1's excursion; linthresh = the largest non-L1 gap, so
        # the other three sit in the linear (fully resolved) band.
        nonl1 = gap_df[gap_df["method"] != "informed_l1"]["gap_mean"].abs() * 100.0
        linthresh = float(nonl1.max()) if len(nonl1) and nonl1.max() > 0 else 1.0
        ax3.set_yscale("symlog", linthresh=linthresh)
        ax3.axhline(0.0, color="#94A3B8", lw=1, ls="--")
        ax3.set(
            title="Generalization gap (out-of-sample − in-sample mean ARE)",
            xlabel="Requested budget",
            ylabel="ARE gap (pp, symlog)",
        )
        add_legend(ax3)
        f3.tight_layout()
        written += _save(f3, fig_dir, "f3_generalization_gap")
        plt.close(f3)

    # F4: out-of-sample ARE by held-out family at an anchor budget. Uses the
    # fixed-family holdout + out-of-sample split (consistent with F1) at the
    # comparison lambda_L2. The rotation holdout's family scope only exists at the
    # single rotation budget, so it cannot share the frontier anchor.
    anchor = report["anchor_budget"]
    if anchor is None and requested_budgets:
        anchor = requested_budgets[len(requested_budgets) // 2]
    if anchor is not None:
        fam = aggregate.by_family_at_budget(
            df,
            budget_requested=int(anchor),
            holdout_type="fixed_family",
            split="out_of_sample",
            metric="mean_are",
        )
        fam = fam[fam["l2_lambda"] == COMPARISON_L2]
        families = sorted(fam["family"].unique())
        methods = [m for m in SWEEP_METHOD_ORDER if m in set(fam["method"])]
        if families and methods:
            f4, ax4 = plt.subplots(figsize=(max(7, 1.1 * len(families) + 2), 4.5))
            x = np.arange(len(families))
            width = 0.8 / max(len(methods), 1)
            for k, method in enumerate(methods):
                d = fam[fam["method"] == method].set_index("family").reindex(families)
                ax4.bar(
                    x + (k - (len(methods) - 1) / 2) * width,
                    d["mean_are"].to_numpy(dtype=float) * 100,
                    width,
                    label=_label(method),
                    color=METHOD_COLORS.get(method, "#444"),
                )
            # Log y only when the held-out families span more than ~1.5 decades,
            # so a single hard family doesn't flatten the rest.
            vals = fam["mean_are"].to_numpy(dtype=float) * 100
            vals = vals[np.isfinite(vals) & (vals > 0)]
            use_log = bool(vals.size) and (vals.max() / vals.min() > 30)
            if use_log:
                ax4.set_yscale("log")
            ax4.set_xticks(x)
            ax4.set_xticklabels(families, rotation=45, ha="right")
            ax4.set(
                title=f"Out-of-sample ARE by held-out family (budget {int(anchor):,})",
                ylabel="Mean ARE (%, log)" if use_log else "Mean ARE (%)",
            )
            ax4.legend(title="Method")
            ax4.grid(True, axis="y", which="both", alpha=0.4)
            f4.tight_layout()
            written += _save(f4, fig_dir, "f4_by_family")
            plt.close(f4)

    # F5: cost-accuracy — runtime vs headline-split median ARE at the comparison lambda_L2.
    # Median (not mean) on y because the raw ARE mean is dominated by near-zero targets.
    runtime = at_cmp_l2(aggregate.run_metric(df, metric="runtime_s"))
    if not runtime.empty and not fmed_head.empty:
        f5, ax5 = plt.subplots(figsize=(7, 4.5))
        for method in [m for m in SWEEP_METHOD_ORDER if m in set(fmed_head["method"])]:
            rt = runtime[runtime["method"] == method].set_index("budget_requested")
            acc = fmed_head[fmed_head["method"] == method].set_index("budget_requested")
            bs = sorted(set(rt.index) & set(acc.index))
            if not bs:
                continue
            xs = [rt.loc[b, "runtime_s_mean"] for b in bs]
            ys = [acc.loc[b, "median_are_mean"] * 100 for b in bs]
            ax5.plot(
                xs,
                ys,
                marker=METHOD_MARKERS.get(method, "o"),
                ms=8,
                lw=1.2,
                color=METHOD_COLORS.get(method, "#444"),
                label=_label(method),
            )
            # Label only the budget endpoints per method: survey-weight runtime is
            # ~constant (dense calibration dominates), so all-point labels collide.
            ends = {0: (4, 6), len(bs) - 1: (4, -10)}
            for idx, (b, xv, yv) in enumerate(zip(bs, xs, ys, strict=True)):
                if idx in ends:
                    ax5.annotate(
                        _budget_label(b),
                        (xv, yv),
                        textcoords="offset points",
                        xytext=ends[idx],
                        fontsize=8,
                        color=METHOD_COLORS.get(method, "#444"),
                    )
        ax5.set_xscale("log")
        ax5.set_yscale("log")
        ax5.set(
            title="Cost versus accuracy",
            xlabel="Runtime (s, log)",
            ylabel=f"{headline_label} median ARE (%, log)",
        )
        add_legend(ax5)
        ax5.grid(True, which="both", alpha=0.4)
        f5.tight_layout()
        written += _save(f5, fig_dir, "f5_cost_accuracy")
        plt.close(f5)

    # F6: operability — the lambda_L2 penalty lifts effective sample size (spreads
    # the weights) at an accuracy cost, traced across the budget axis for the
    # informed L0 method. Drawn only when the sweep varied lambda_L2 (>= 2 values).
    if len(l2_values) >= 2:
        lo_l2, hi_l2 = float(l2_values[0]), float(l2_values[-1])
        ess_l0 = aggregate.run_metric(df, metric="ess")
        ess_l0 = ess_l0[ess_l0["method"] == "informed_l0"]
        are_l0 = front_mean[
            (front_mean["method"] == "informed_l0")
            & (front_mean["split"] == headline_split)
        ]
        op_tick_budgets = sorted(int(b) for b in ess_l0["budget_requested"].unique())
        teal = METHOD_COLORS["informed_l0"]
        # Same hue (it is one method); solid+filled for the smaller penalty,
        # dashed+open for the larger, so the pair reads in grayscale too.
        styles = {
            lo_l2: dict(
                ls="-", marker="o", mfc=teal, label=rf"$\lambda_{{L_2}}$ = {lo_l2:g}"
            ),
            hi_l2: dict(
                ls="--",
                marker="s",
                mfc="white",
                label=rf"$\lambda_{{L_2}}$ = {hi_l2:g}",
            ),
        }

        def _op_line(ax, frame, ycol, scale=1.0):
            for l2 in (lo_l2, hi_l2):
                st = styles[l2]
                d = frame[frame["l2_lambda"] == l2].sort_values("budget_requested")
                if d.empty:
                    continue
                xv = d["budget_requested"].to_numpy(dtype=float)
                ax.plot(
                    xv,
                    d[f"{ycol}_mean"].to_numpy(dtype=float) * scale,
                    color=teal,
                    lw=2,
                    ms=7,
                    ls=st["ls"],
                    marker=st["marker"],
                    mfc=st["mfc"],
                    mec=teal,
                    label=st["label"],
                )
                lo = d[f"{ycol}_lo"].to_numpy(dtype=float) * scale
                hi = d[f"{ycol}_hi"].to_numpy(dtype=float) * scale
                if np.isfinite(lo).all() and np.isfinite(hi).all() and np.any(hi > lo):
                    ax.fill_between(xv, lo, hi, color=teal, alpha=0.12, linewidth=0)

        f6, (ax_ess, ax_are) = plt.subplots(1, 2, figsize=(11, 4.5))
        _op_line(ax_ess, ess_l0, "ess")
        # are_l0 carries mean_are_{mean,lo,hi}; reuse the same helper.
        _op_line(
            ax_are,
            are_l0.rename(
                columns={
                    "mean_are_mean": "are_mean",
                    "mean_are_lo": "are_lo",
                    "mean_are_hi": "are_hi",
                }
            ),
            "are",
            scale=100.0,
        )
        for ax in (ax_ess, ax_are):
            _budget_axis(ax, op_tick_budgets)
            ax.set_xlabel("Requested budget")
            ax.grid(True, which="both", alpha=0.4)
        ax_ess.set(title="Effective sample size", ylabel="ESS")
        ax_are.set(
            title=f"{headline_label} mean ARE", ylabel=f"{headline_label} ARE (%, log)"
        )
        ax_are.set_yscale("log")
        add_legend(ax_ess, title=r"$\lambda_{L_2}$")
        f6.suptitle(
            r"Operability: the $\lambda_{L_2}$ penalty trades weight concentration for accuracy"
        )
        f6.tight_layout(rect=(0, 0, 1, 0.96))
        written += _save(f6, fig_dir, "f6_operability")
        plt.close(f6)

    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--sweep", type=Path, help="Sweep run dir (contains metrics_long.csv)."
    )
    g.add_argument("--long", type=Path, help="Path to a metrics_long.csv directly.")
    parser.add_argument(
        "--out", type=Path, default=None, help="Output dir (default: <sweep>/report)."
    )
    parser.add_argument("--anchor-budget", type=int, default=None)
    parser.add_argument(
        "--paper-figures", action="store_true", help="Copy figures into paper/figures."
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    long_csv = (args.sweep / "metrics_long.csv") if args.sweep else args.long
    if not long_csv.is_file():
        raise FileNotFoundError(f"metrics_long.csv not found: {long_csv}")
    out_dir = args.out or (long_csv.parent / "report")

    report = write_reports(long_csv, out_dir, anchor_budget=args.anchor_budget)
    print(
        f"Wrote tables: {json.dumps({k: str(v) for k, v in report['table_paths'].items()}, indent=2)}"
    )
    print(f"Wrote summary: {report['summary']}")

    written = write_figures(report, out_dir)
    for path in written:
        print(f"  figure: {path}")

    if args.paper_figures:
        import shutil

        if written:
            PAPER_FIGURES.mkdir(parents=True, exist_ok=True)
            for path in written:
                if path.suffix == ".png":
                    shutil.copy(path, PAPER_FIGURES / path.name)
            print(f"Copied static figures into {PAPER_FIGURES}")

        PAPER_TABLES.mkdir(parents=True, exist_ok=True)
        for path in report["paper_table_paths"].values():
            shutil.copy(path, PAPER_TABLES / path.name)
        print(f"Copied paper result tables into {PAPER_TABLES}")


if __name__ == "__main__":
    main()
