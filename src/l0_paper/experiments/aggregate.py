#!/usr/bin/env python
"""Tidy long-format results schema + cross-seed aggregation for the budget sweep.

The sweep (``experiments/run_sweep.py``) writes one **long** CSV -- the single
source of truth -- with one row per atomic measurement:

    method, seed, budget_requested, budget_achieved, l2_lambda, holdout_type,
    fold, split, scope, scope_value, metric, value

* ``scope == "overall"`` -- a scored-target aggregate (``mean_are`` /
  ``median_are`` / ``max_are`` / ``n``) over the whole split.
* ``scope == "family"`` / ``"geography"`` -- the same aggregate restricted to one
  family or geographic level (``scope_value``).
* ``scope == "run"`` -- a weight/run diagnostic that depends only on the weight
  vector, not the target split (``ess``, ``max_weight``, ``p99_weight``,
  ``n_selected``, ``runtime_s``, ``l0_lambda``, ...); emitted once with
  ``split == "na"``.

Keeping everything in one tidy frame means every figure and table is a
``filter -> pivot -> aggregate`` away, and the cross-seed statistics
(confidence intervals, paired tests) live here rather than in plotting code.

This module is pure ``numpy`` / ``pandas`` / ``scipy`` -- no plotting deps -- so
it is import-safe for tests and the sweep.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LONG_COLUMNS = (
    "method",
    "seed",
    "budget_requested",
    "budget_achieved",
    "l2_lambda",
    "holdout_type",
    "fold",
    "split",
    "scope",
    "scope_value",
    "metric",
    "value",
)

# Scored-target aggregates carried for overall + per-family + per-geography scopes.
_ARE_METRICS = ("mean_are", "median_are", "max_are", "n")
# Overall-only extras: the targeted-removal sensitivity (mean with the named
# denominator-degenerate targets dropped) and how many were dropped.
_OVERALL_EXTRA_METRICS = ("mean_are_ex_degenerate", "n_degenerate")
# Weight/run diagnostics that depend only on the weight vector (one per run).
_RUN_METRICS = (
    "n_selected",
    "n_unique_selected",
    "ess",
    "sum_weight",
    "mean_weight",
    "max_weight",
    "p50_weight",
    "p90_weight",
    "p99_weight",
    "runtime_s",
    "l0_lambda",
    "l2_lambda",
    "final_loss",
    "budget_achieved",
)


def _scored_rows(
    base: dict[str, Any], split: str, scored: dict[str, Any]
) -> list[dict[str, Any]]:
    """Emit overall + by-family + by-geography ARE rows from a ``metrics.score`` dict."""
    rows: list[dict[str, Any]] = []

    def emit(scope: str, scope_value: str, stats: dict[str, Any]) -> None:
        for metric in _ARE_METRICS:
            value = stats.get(metric)
            if value is None:
                continue
            rows.append(
                {**base, "split": split, "scope": scope, "scope_value": scope_value,
                 "metric": metric, "value": float(value)}
            )

    emit("overall", "", scored)
    for metric in _OVERALL_EXTRA_METRICS:
        value = scored.get(metric)
        if value is not None:
            rows.append(
                {**base, "split": split, "scope": "overall", "scope_value": "",
                 "metric": metric, "value": float(value)}
            )
    for family, stats in scored.get("by_family", {}).items():
        emit("family", family, stats)
    for level, stats in scored.get("by_geography", {}).items():
        emit("geography", level, stats)
    return rows


def rows_from_run(
    *,
    method: str,
    seed: int,
    budget_requested: int,
    budget_achieved: int,
    l2_lambda: float = 0.0,
    holdout_type: str,
    fold: int,
    in_sample: dict[str, Any],
    out_of_sample: dict[str, Any],
    run: Any | None = None,
    extra_run_metrics: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Build all long-format rows for one calibrated method at one grid point.

    ``in_sample`` / ``out_of_sample`` are :func:`l0_paper.experiments.metrics.score`
    dicts. ``run`` is the :class:`~l0_paper.experiments.conditions.RunResult`
    (used for ``runtime_s`` / ``l0_lambda`` / ``final_loss``); the weight
    diagnostics (ESS, max weight, ...) are read from ``in_sample`` since they
    depend only on the weight vector. ``extra_run_metrics`` adds bespoke run-level
    rows (e.g. the extreme-ARE diagnostic).
    """
    base = {
        "method": method,
        "seed": int(seed),
        "budget_requested": int(budget_requested),
        "budget_achieved": int(budget_achieved),
        "l2_lambda": float(l2_lambda),
        "holdout_type": holdout_type,
        "fold": int(fold),
    }
    rows = _scored_rows(base, "in_sample", in_sample)
    rows += _scored_rows(base, "out_of_sample", out_of_sample)

    run_metrics: dict[str, float] = {"budget_achieved": float(budget_achieved)}
    if "n_selected" in in_sample and in_sample["n_selected"] is not None:
        run_metrics["n_unique_selected"] = float(in_sample["n_selected"])
    for key in ("ess", "sum_weight", "mean_weight", "max_weight",
                "p50_weight", "p90_weight", "p99_weight"):
        if key in in_sample and in_sample[key] is not None:
            run_metrics[key] = float(in_sample[key])
    if run is not None:
        run_metrics["n_selected"] = float(
            getattr(run, "n_selected", in_sample.get("n_selected", budget_achieved))
        )
        run_metrics["runtime_s"] = float(run.runtime_s)
        run_metrics["l0_lambda"] = float(run.l0_lambda)
        run_metrics["l2_lambda"] = float(getattr(run, "l2_lambda", l2_lambda))
        run_metrics["final_loss"] = float(run.final_loss)
    elif "n_selected" in in_sample and in_sample["n_selected"] is not None:
        run_metrics["n_selected"] = float(in_sample["n_selected"])
    if extra_run_metrics:
        run_metrics.update({k: float(v) for k, v in extra_run_metrics.items()})

    for metric, value in run_metrics.items():
        rows.append(
            {**base, "split": "na", "scope": "run", "scope_value": "",
             "metric": metric, "value": float(value)}
        )
    return rows


def extreme_are_counts(
    diagnostic_rows: Iterable[dict[str, Any]], *, thresholds: tuple[float, ...] = (1.0, 5.0)
) -> dict[str, float]:
    """Count scored targets whose absolute relative error exceeds each threshold.

    A handful of near-zero-denominator targets can dominate a mean ARE, so the
    sweep records how many targets sit in the tail rather than letting them hide
    inside the headline. ``ledger_filter``-free toy targets with a zero value are
    skipped (their ARE is undefined).
    """
    ares = [
        row["absolute_relative_error"]
        for row in diagnostic_rows
        if row.get("absolute_relative_error") is not None
    ]
    arr = np.asarray(ares, dtype=np.float64)
    out = {"n_scored": float(arr.size)}
    for threshold in thresholds:
        key = f"n_are_gt_{threshold:g}"
        out[key] = float(int((arr > threshold).sum()))
    return out


def write_long_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    """Write long-format rows to CSV with the canonical column order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LONG_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_long(path: str | Path) -> pd.DataFrame:
    """Load a long-format results CSV with sensible dtypes."""
    df = pd.read_csv(path)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "l2_lambda" not in df.columns:
        df["l2_lambda"] = 0.0
    df["l2_lambda"] = pd.to_numeric(df["l2_lambda"], errors="coerce").fillna(0.0)
    df["scope_value"] = df["scope_value"].fillna("")
    return df


# Per-target diagnostics: one row per (run config, scored target). Persisted for
# the headline (fixed-family) split only, so the near-zero-denominator drivers can
# be *named* (which targets inflate the mean) rather than trimmed away.
TARGET_DIAG_COLUMNS = (
    "method",
    "l2_lambda",
    "seed",
    "budget_requested",
    "split",
    "target_name",
    "family",
    "geography_level",
    "target_value",
    "achieved_value",
    "scale",
    "loss_weight",
    "absolute_relative_error",
    "is_degenerate",
)


def target_diagnostic_rows(
    *,
    method: str,
    l2_lambda: float = 0.0,
    seed: int,
    budget_requested: int,
    split: str,
    diagnostics: Iterable[dict[str, Any]],
    degenerate_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Flatten :func:`metrics.target_diagnostics` rows into persistable per-target rows."""
    degenerate = degenerate_names or set()
    return [
        {
            "method": method,
            "l2_lambda": float(l2_lambda),
            "seed": int(seed),
            "budget_requested": int(budget_requested),
            "split": split,
            "target_name": row["name"],
            "family": row["family"],
            "geography_level": row["geography_level"],
            "target_value": row["target_value"],
            "achieved_value": row["achieved_value"],
            "scale": row.get("scale"),
            "loss_weight": row.get("loss_weight"),
            "absolute_relative_error": row["absolute_relative_error"],
            "is_degenerate": bool(row["name"] in degenerate),
        }
        for row in diagnostics
    ]


def write_target_diagnostics_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    """Write per-target diagnostic rows to CSV with the canonical column order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TARGET_DIAG_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_target_diagnostics(path: str | Path) -> pd.DataFrame:
    """Load a per-target diagnostics CSV with sensible dtypes."""
    df = pd.read_csv(path)
    if "l2_lambda" not in df.columns:
        df["l2_lambda"] = 0.0
    df["l2_lambda"] = pd.to_numeric(df["l2_lambda"], errors="coerce").fillna(0.0)
    for col in ("target_value", "achieved_value", "scale", "loss_weight", "absolute_relative_error"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["is_degenerate"] = df["is_degenerate"].astype(bool)
    return df


def top_are_contributors(
    diag: pd.DataFrame,
    *,
    method: str,
    budget_requested: int,
    l2_lambda: float | None = None,
    split: str = "out_of_sample",
    top_k: int = 15,
) -> pd.DataFrame:
    """The targets that drive a run's mean ARE, averaged across seeds, with shares.

    Answers "*which named targets* push the mean up" -- the attribution that
    replaces winsorization. ``share_of_mean`` is a target's mean ARE as a fraction
    of the summed ARE (its contribution to the micro-average), and
    ``is_degenerate`` flags the denominator-degenerate ones
    (:func:`metrics.degenerate_target_names`).
    """
    sub = diag[
        (diag["method"] == method)
        & (diag["budget_requested"] == budget_requested)
        & (diag["split"] == split)
    ]
    if "l2_lambda" in sub.columns:
        values = sorted(pd.to_numeric(sub["l2_lambda"], errors="coerce").fillna(0.0).unique())
        if l2_lambda is None and len(values) > 1:
            raise ValueError(
                "top_are_contributors requires l2_lambda when diagnostics contain "
                f"multiple penalty values: {values}."
            )
        if l2_lambda is not None:
            sub = sub[pd.to_numeric(sub["l2_lambda"], errors="coerce").fillna(0.0) == float(l2_lambda)]
    sub = sub.dropna(subset=["absolute_relative_error"])
    if sub.empty:
        return pd.DataFrame(
            columns=["target_name", "family", "is_degenerate", "mean_are", "share_of_mean"]
        )
    per_target = (
        sub.groupby(["target_name", "family", "is_degenerate"], as_index=False)[
            "absolute_relative_error"
        ]
        .mean()
        .rename(columns={"absolute_relative_error": "mean_are"})
    )
    total = float(per_target["mean_are"].sum())
    per_target["share_of_mean"] = per_target["mean_are"] / total if total > 0 else 0.0
    return (
        per_target.sort_values("mean_are", ascending=False)
        .head(top_k)
        .reset_index(drop=True)
    )


def mean_ci(values: Iterable[float], *, confidence: float = 0.95) -> tuple[float, float, float]:
    """Sample mean and a two-sided t confidence interval ``(mean, lo, hi)``.

    Falls back to a degenerate (mean, mean, mean) interval when fewer than two
    finite values are present -- a single seed has no spread to report.
    """
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=np.float64)
    if arr.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    mean = float(arr.mean())
    if arr.size == 1:
        return (mean, mean, mean)
    from scipy.stats import t

    sem = float(arr.std(ddof=1) / np.sqrt(arr.size))
    half = sem * float(t.ppf((1.0 + confidence) / 2.0, arr.size - 1))
    return (mean, mean - half, mean + half)


def _overall(df: pd.DataFrame, *, holdout_type: str, split: str, metric: str) -> pd.DataFrame:
    return df[
        (df["holdout_type"] == holdout_type)
        & (df["split"] == split)
        & (df["scope"] == "overall")
        & (df["metric"] == metric)
    ]


def _budget_achieved_by_method(df: pd.DataFrame, *, holdout_type: str) -> pd.Series:
    """Mean retained-draw budget by method/l2/requested budget.

    Older sweep CSVs recorded ``dense_sample``'s ``budget_achieved`` as the
    number of unique nonzero records after with-replacement duplicate draws were
    collapsed. The experiment budget, however, is the number of PPS draws matched
    to informed L0. Recover that draw-count budget for reporting while leaving
    the unique count available as ``n_unique_selected`` in newly generated rows.
    """
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["scope"] == "run")
        & (df["metric"] == "budget_achieved")
    ]
    achieved = sub.groupby(["method", "l2_lambda", "budget_requested"])["value"].mean()
    if achieved.empty:
        return achieved

    fixed = achieved.to_dict()
    keys = {(float(l2), int(budget)) for _method, l2, budget in achieved.index}
    for l2_lambda, budget in keys:
        dense_key = ("dense_sample", l2_lambda, budget)
        if dense_key not in fixed:
            continue
        reference = fixed.get(("informed_l0", l2_lambda, budget))
        if reference is None:
            reference = fixed.get(("random_reweight", l2_lambda, budget))
        if reference is None:
            reference = float(budget)
        fixed[dense_key] = float(reference)
    return pd.Series(fixed)


def frontier_table(
    df: pd.DataFrame,
    *,
    holdout_type: str = "fixed_family",
    metric: str = "mean_are",
    confidence: float = 0.95,
) -> pd.DataFrame:
    """Per (method, budget): cross-seed mean ARE (+CI) in- and out-of-sample.

    The backbone of the frontier figure and table. ``budget`` is the requested
    grid budget; ``budget_achieved`` is the cross-seed mean retained count.
    """
    records: list[dict[str, Any]] = []
    achieved = _budget_achieved_by_method(df, holdout_type=holdout_type)
    for split in ("in_sample", "out_of_sample"):
        sub = _overall(df, holdout_type=holdout_type, split=split, metric=metric)
        for (method, l2_lambda, budget), group in sub.groupby(
            ["method", "l2_lambda", "budget_requested"]
        ):
            mean, lo, hi = mean_ci(group["value"], confidence=confidence)
            records.append(
                {
                    "method": method,
                    "l2_lambda": float(l2_lambda),
                    "budget_requested": int(budget),
                    "budget_achieved": float(
                        achieved.get((method, l2_lambda, budget), float("nan"))
                    ),
                    "split": split,
                    "n_seeds": int(group["seed"].nunique()),
                    f"{metric}_mean": mean,
                    f"{metric}_lo": lo,
                    f"{metric}_hi": hi,
                }
            )
    return pd.DataFrame(records).sort_values(
        ["split", "method", "l2_lambda", "budget_requested"]
    ).reset_index(drop=True)


def rotation_seed_scores(
    df: pd.DataFrame,
    *,
    metric: str = "mean_are",
    validation_only_families: Iterable[str] = ("cbo",),
    holdout_type: str = "rotation",
    split: str = "out_of_sample",
) -> pd.DataFrame:
    """Collapse rotation folds to one target-weighted score per seed.

    Rotation folds are different held-out target families, not iid repetitions. For
    inference, first aggregate every fold in a seed into one score, then summarize
    those seed-level scores. Validation-only families are excluded from this
    rotated-family aggregate because they are held out in every fold and would
    otherwise be counted once per fold.

    Currently this is defined for ``mean_are`` because the target-weighted average
    of family means recovers the all-target mean over the rotated families. The
    same is not true for medians or maxima.
    """
    if metric != "mean_are":
        raise ValueError("rotation_seed_scores currently supports metric='mean_are' only.")

    validation_only = {str(f) for f in validation_only_families}
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["split"] == split)
        & (df["scope"] == "family")
        & (df["metric"].isin((metric, "n")))
    ]
    if sub.empty:
        return pd.DataFrame(
            columns=[
                "method",
                "seed",
                "budget_requested",
                "budget_achieved",
                "split",
                metric,
                "n_targets",
                "n_folds",
                "excluded_validation_only_targets",
            ]
        )

    family = (
        sub.pivot_table(
            index=["method", "l2_lambda", "seed", "budget_requested", "fold", "scope_value"],
            columns="metric",
            values="value",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    required = family.dropna(subset=[metric, "n"])
    included = required[
        (~required["scope_value"].isin(validation_only)) & (required["n"] > 0)
    ]
    excluded = required[required["scope_value"].isin(validation_only)]
    achieved = (
        df[
            (df["holdout_type"] == holdout_type)
            & (df["scope"] == "run")
            & (df["metric"] == "budget_achieved")
        ]
        .groupby(["method", "l2_lambda", "seed", "budget_requested"])["value"]
        .mean()
    )
    excluded_targets = (
        excluded.groupby(["method", "l2_lambda", "seed", "budget_requested"])["n"].sum()
        if not excluded.empty else {}
    )

    records: list[dict[str, Any]] = []
    for (method, l2_lambda, seed, budget), group in included.groupby(
        ["method", "l2_lambda", "seed", "budget_requested"]
    ):
        n_targets = float(group["n"].sum())
        if n_targets <= 0:
            continue
        value = float((group[metric] * group["n"]).sum() / n_targets)
        key = (method, l2_lambda, seed, budget)
        records.append(
            {
                "method": method,
                "l2_lambda": float(l2_lambda),
                "seed": int(seed),
                "budget_requested": int(budget),
                "budget_achieved": float(achieved.get(key, float("nan"))),
                "split": split,
                metric: value,
                "n_targets": n_targets,
                "n_folds": int(group["fold"].nunique()),
                "excluded_validation_only_targets": float(
                    excluded_targets.get(key, 0.0)
                    if hasattr(excluded_targets, "get") else 0.0
                ),
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "method",
                "seed",
                "budget_requested",
                "budget_achieved",
                "split",
                metric,
                "n_targets",
                "n_folds",
                "excluded_validation_only_targets",
            ]
        )
    return (
        pd.DataFrame(records)
        .sort_values(["method", "l2_lambda", "budget_requested", "seed"])
        .reset_index(drop=True)
    )


def rotation_frontier_table(
    df: pd.DataFrame,
    *,
    metric: str = "mean_are",
    validation_only_families: Iterable[str] = ("cbo",),
    confidence: float = 0.95,
) -> pd.DataFrame:
    """Rotation robustness table using one target-weighted score per seed."""
    seed_scores = rotation_seed_scores(
        df,
        metric=metric,
        validation_only_families=validation_only_families,
    )
    mean_col = metric
    records: list[dict[str, Any]] = []
    for (method, l2_lambda, budget), group in seed_scores.groupby(
        ["method", "l2_lambda", "budget_requested"]
    ):
        mean, lo, hi = mean_ci(group[mean_col], confidence=confidence)
        records.append(
            {
                "method": method,
                "l2_lambda": float(l2_lambda),
                "budget_requested": int(budget),
                "budget_achieved": float(group["budget_achieved"].mean()),
                "split": "out_of_sample",
                "n_seeds": int(group["seed"].nunique()),
                "n_targets": float(group["n_targets"].mean()),
                f"{metric}_mean": mean,
                f"{metric}_lo": lo,
                f"{metric}_hi": hi,
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "method",
                "budget_requested",
                "budget_achieved",
                "split",
                "n_seeds",
                "n_targets",
                f"{metric}_mean",
                f"{metric}_lo",
                f"{metric}_hi",
            ]
        )
    return (
        pd.DataFrame(records)
        .sort_values(["split", "method", "l2_lambda", "budget_requested"])
        .reset_index(drop=True)
    )


def paired_method_diff(
    df: pd.DataFrame,
    *,
    challenger: str = "informed_l0",
    baseline: str = "random_reweight",
    split: str = "out_of_sample",
    metric: str = "mean_are",
    holdout_type: str = "fixed_family",
    confidence: float = 0.95,
    min_significance_seeds: int = 3,
) -> pd.DataFrame:
    """Per budget: paired (same-seed) ``challenger - baseline`` difference + test.

    Both methods see the *same* held-out targets at the same seed, so the
    comparison is paired: we difference within seed, then summarise across seeds.
    ``significant`` is whether the CI of the mean difference excludes zero (and,
    at least ``min_significance_seeds`` paired seeds are present). A negative
    ``diff_mean`` means the challenger has the lower error (better).
    """
    sub = _overall(df, holdout_type=holdout_type, split=split, metric=metric)
    records: list[dict[str, Any]] = []
    for (l2_lambda, budget), group in sub.groupby(["l2_lambda", "budget_requested"]):
        wide = group.pivot_table(index="seed", columns="method", values="value")
        if challenger not in wide.columns or baseline not in wide.columns:
            continue
        paired = wide[[challenger, baseline]].dropna()
        if paired.empty:
            continue
        diff = (paired[challenger] - paired[baseline]).to_numpy()
        mean, lo, hi = mean_ci(diff, confidence=confidence)
        p_value = float("nan")
        if diff.size >= 2 and np.ptp(diff) > 0:
            from scipy.stats import ttest_rel

            p_value = float(ttest_rel(paired[challenger], paired[baseline]).pvalue)
        ci_excludes_zero = bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))
        enough_seeds = paired.shape[0] >= min_significance_seeds
        records.append(
            {
                "budget_requested": int(budget),
                "l2_lambda": float(l2_lambda),
                "n_seeds": int(paired.shape[0]),
                f"{challenger}_mean": float(paired[challenger].mean()),
                f"{baseline}_mean": float(paired[baseline].mean()),
                "diff_mean": mean,
                "diff_lo": lo,
                "diff_hi": hi,
                "p_value": p_value,
                "challenger_better": bool(mean < 0),
                "significant": bool(enough_seeds and ci_excludes_zero),
            }
        )
    out = pd.DataFrame(records)
    if out.empty:
        # No paired (challenger, baseline) seeds -- e.g. an L0-only sweep. Callers
        # guard on ``.empty``; return it without sorting on an absent column.
        return out
    return out.sort_values(["l2_lambda", "budget_requested"]).reset_index(drop=True)


def macro_average(
    df: pd.DataFrame,
    *,
    holdout_type: str = "fixed_family",
    split: str = "out_of_sample",
    metric: str = "mean_are",
    confidence: float = 0.95,
) -> pd.DataFrame:
    """Family macro-average (+CI) per (method, budget).

    The micro-average over targets is dominated by the largest family (IRS SOI is
    ~72% of the surface), so a method that nails SOI looks good even if it misses
    every other source. The macro-average gives each family equal weight: average
    the per-family ARE within a seed, then summarise across seeds.
    """
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["split"] == split)
        & (df["scope"] == "family")
        & (df["metric"] == metric)
    ]
    per_seed = (
        sub.groupby(["method", "l2_lambda", "budget_requested", "seed"])["value"].mean().reset_index()
    )
    records: list[dict[str, Any]] = []
    for (method, l2_lambda, budget), group in per_seed.groupby(
        ["method", "l2_lambda", "budget_requested"]
    ):
        mean, lo, hi = mean_ci(group["value"], confidence=confidence)
        records.append(
            {
                "method": method,
                "l2_lambda": float(l2_lambda),
                "budget_requested": int(budget),
                "n_seeds": int(group["seed"].nunique()),
                f"macro_{metric}_mean": mean,
                f"macro_{metric}_lo": lo,
                f"macro_{metric}_hi": hi,
            }
        )
    return pd.DataFrame(records).sort_values(
        ["method", "l2_lambda", "budget_requested"]
    ).reset_index(drop=True)


def by_family_at_budget(
    df: pd.DataFrame,
    *,
    budget_requested: int,
    holdout_type: str = "rotation",
    split: str = "out_of_sample",
    metric: str = "mean_are",
) -> pd.DataFrame:
    """Per (method, family) ARE at one budget, averaged across seeds/folds.

    Feeds the by-family figure. Defaults to the rotation holdout so every family
    is a genuine out-of-sample fold.
    """
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["split"] == split)
        & (df["scope"] == "family")
        & (df["metric"] == metric)
        & (df["budget_requested"] == budget_requested)
    ]
    return (
        sub.groupby(["method", "l2_lambda", "scope_value"])["value"].mean().reset_index()
        .rename(columns={"scope_value": "family", "value": metric})
        .sort_values(["family", "method", "l2_lambda"]).reset_index(drop=True)
    )


def run_metric(
    df: pd.DataFrame, *, metric: str, holdout_type: str = "fixed_family", confidence: float = 0.95
) -> pd.DataFrame:
    """Per (method, budget): cross-seed mean (+CI) of a run-level metric (ESS, etc.)."""
    sub = df[
        (df["holdout_type"] == holdout_type)
        & (df["scope"] == "run")
        & (df["metric"] == metric)
    ]
    achieved = _budget_achieved_by_method(df, holdout_type=holdout_type)
    records: list[dict[str, Any]] = []
    for (method, l2_lambda, budget), group in sub.groupby(
        ["method", "l2_lambda", "budget_requested"]
    ):
        mean, lo, hi = mean_ci(group["value"], confidence=confidence)
        records.append(
            {
                "method": method,
                "l2_lambda": float(l2_lambda),
                "budget_requested": int(budget),
                "budget_achieved": float(
                    achieved.get((method, l2_lambda, budget), group["budget_achieved"].mean())
                ),
                f"{metric}_mean": mean,
                f"{metric}_lo": lo,
                f"{metric}_hi": hi,
            }
        )
    return pd.DataFrame(records).sort_values(
        ["method", "l2_lambda", "budget_requested"]
    ).reset_index(drop=True)


def operability_table(
    df: pd.DataFrame,
    *,
    method: str = "informed_l0",
    budget_requested: int | None = None,
    holdout_type: str = "fixed_family",
) -> pd.DataFrame:
    """The accuracy <-> ESS/concentration frontier as ``l2_lambda`` sweeps.

    For one method at a fixed budget, returns one row per ``l2_lambda`` with the
    cross-seed mean ESS, max weight, in-sample mean ARE, and out-of-sample mean and
    median ARE. Raising ``l2_lambda`` spreads the weights (ESS up, max weight down)
    but the concentration-hungry fiscal targets degrade -- this traces that
    trade-off, filling the operability figure. Feeds ``fig:operability``.
    """
    sub = df[(df["holdout_type"] == holdout_type) & (df["method"] == method)]
    if budget_requested is not None:
        sub = sub[sub["budget_requested"] == budget_requested]

    def by_l2(scope: str, split: str, metric: str) -> pd.Series:
        s = sub[(sub["scope"] == scope) & (sub["split"] == split) & (sub["metric"] == metric)]
        return s.groupby("l2_lambda")["value"].mean()

    table = pd.DataFrame(
        {
            "ess": by_l2("run", "na", "ess"),
            "max_weight": by_l2("run", "na", "max_weight"),
            "in_mean_are": by_l2("overall", "in_sample", "mean_are"),
            "oos_mean_are": by_l2("overall", "out_of_sample", "mean_are"),
            "oos_median_are": by_l2("overall", "out_of_sample", "median_are"),
        }
    )
    return table.reset_index().sort_values("l2_lambda").reset_index(drop=True)
