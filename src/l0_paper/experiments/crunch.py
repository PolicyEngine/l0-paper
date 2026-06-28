"""Crunch summary metrics from the per-target diagnostics store.

Every headline number derives from ``target_diagnostics_long.csv`` -- one row per
``(target x method x split x budget x seed)`` carrying the raw ``target_value`` and
``achieved_value`` (and, when available, the loss weight ``loss_weight`` and the
denominator ``scale``). Because the raw per-target values are stored, the cap, the
weighting, and the choice of mean vs. median are *reporting* decisions made here
rather than baked into a run.

In particular the calibration objective -- the capped, weighted MAPE of Equation 8
*less the penalties* -- can be evaluated out of sample at any cap without re-running
the experiment. Populace's US-fiscal production build caps at ``c = 1``
(``US_FISCAL_TARGET_LOSS_CAP``); the paper's runs optimised at ``c = 10``. The
*optimisation* cap shapes the fitted weights, so a production-faithful fit still needs
a rerun, but the *reported* objective can be crunched at either cap from one file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Default grouping for :func:`summarize` -- one summary row per method/split/budget
#: (and per L2 penalty, when the sweep varied it).
GROUP = ("method", "split", "l2_lambda", "budget_requested")


def _scale(target_value: np.ndarray, floor: float = 1.0) -> np.ndarray:
    """The objective's denominator ``s_j = max(|t_j|, floor)`` (Equation 8)."""
    return np.maximum(np.abs(np.asarray(target_value, dtype=float)), float(floor))


def capped_relative_error(
    df: pd.DataFrame, *, cap: float | None, scale_floor: float = 1.0
) -> np.ndarray:
    """Per-target capped relative error ``min(|a - t| / max(|t|, floor), cap)``.

    This is the per-target term of the calibration objective (Equation 8). The
    stored ``scale`` column is used when present; otherwise it is recomputed from
    ``target_value``. ``cap=None`` leaves the error uncapped.
    """
    t = df["target_value"].to_numpy(dtype=float)
    a = df["achieved_value"].to_numpy(dtype=float)
    s = df["scale"].to_numpy(dtype=float) if "scale" in df.columns else _scale(t, scale_floor)
    rel = np.abs(a - t) / s
    if cap is not None:
        rel = np.minimum(rel, float(cap))
    return rel


def raw_relative_error(df: pd.DataFrame) -> np.ndarray:
    """Per-target raw relative error ``|a - t| / |t|`` (NaN for zero-valued targets).

    The uncapped, unweighted, ``|t|``-denominator metric the paper currently leads
    with; near-zero denominators are exactly the targets that inflate its mean, which
    is why the objective uses a floored, capped denominator instead.
    """
    t = df["target_value"].to_numpy(dtype=float)
    a = df["achieved_value"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(a - t) / np.abs(t)
    rel[t == 0.0] = np.nan
    return rel


def _weighted_mean(values: np.ndarray, weights: np.ndarray | None) -> float:
    values = np.asarray(values, dtype=float)
    keep = ~np.isnan(values)
    values = values[keep]
    if values.size == 0:
        return float("nan")
    if weights is None:
        return float(values.mean())
    w = np.asarray(weights, dtype=float)[keep]
    total = w.sum()
    return float((values * w).sum() / total) if total > 0 else float("nan")


def objective(df: pd.DataFrame, *, cap: float = 1.0) -> float:
    """Capped weighted MAPE (Equation 8, penalty-free) over the rows in ``df``.

    Uses ``loss_weight`` (the per-target ``omega_j``) when the column is present,
    else falls back to an unweighted mean. Evaluate on the ``out_of_sample`` rows
    for the objective-consistent headline. ``cap`` defaults to the production cap
    (1.0); pass ``cap=10`` to match the paper's optimisation cap.
    """
    rel = capped_relative_error(df, cap=cap)
    weights = df["loss_weight"].to_numpy(dtype=float) if "loss_weight" in df.columns else None
    # Uniform-weighted runs store no omega (the column is all-NaN); fall back to an
    # unweighted mean rather than propagating NaN.
    if weights is not None and np.all(np.isnan(weights)):
        weights = None
    return _weighted_mean(rel, weights)


def fraction_within(df: pd.DataFrame, *, threshold: float) -> float:
    """Share of (non-zero) targets whose raw relative error is ``<= threshold``."""
    rel = raw_relative_error(df)
    rel = rel[~np.isnan(rel)]
    return float((rel <= threshold).mean()) if rel.size else float("nan")


def summarize(
    df: pd.DataFrame,
    *,
    cap: float = 1.0,
    group: tuple[str, ...] = GROUP,
    within: float = 0.10,
    drop_degenerate: bool = False,
) -> pd.DataFrame:
    """One row per group with the objective and its companion diagnostics.

    Columns: ``objective_capped_weighted`` (Equation 8 at ``cap``), ``median_are``
    and ``mean_are`` (raw ``|a-t|/|t|``, the paper's current metric), ``frac_within``
    (share within ``within``), and ``n``. Set ``drop_degenerate=True`` to exclude
    rows flagged ``is_degenerate`` (so the objective and the raw metrics can be read
    with and without the near-zero-denominator tail).
    """
    if drop_degenerate and "is_degenerate" in df.columns:
        df = df[~df["is_degenerate"].astype(bool)]
    keys = [g for g in group if g in df.columns]
    records: list[dict] = []
    for key, sub in df.groupby(keys, sort=True):
        raw = raw_relative_error(sub)
        raw = raw[~np.isnan(raw)]
        key_tuple = key if isinstance(key, tuple) else (key,)
        record = dict(zip(keys, key_tuple, strict=True))
        record.update(
            objective_capped_weighted=objective(sub, cap=cap),
            median_are=float(np.median(raw)) if raw.size else float("nan"),
            mean_are=float(np.mean(raw)) if raw.size else float("nan"),
            frac_within=fraction_within(sub, threshold=within),
            n=int(len(sub)),
        )
        records.append(record)
    return pd.DataFrame.from_records(records)
