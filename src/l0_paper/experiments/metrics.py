"""Scoring for a calibrated/sampled dataset against a target set.

The Populace ``CalibrationResult`` only carries diagnostics for the targets it was
*fit* to, so out-of-sample scoring is done here: each target's achieved aggregate
is computed exactly with :meth:`populace.calibrate.target.Target.achieved_value`
under the method's weight vector and compared to the target value. Aggregates are
reported overall and broken out two ways -- by target family and by geographic
level -- because a sampler can match national totals or one source while missing
others. The current US target surface is national + state only, so the by-family
breakdown is usually the more informative cut.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from populace.calibrate.target import Target

_NATIONAL_LEVELS = {"country", "nation", "national", "us", "0100000us"}
_DISTRICT_LEVELS = {"congressional_district", "district", "cd"}


def geography_level(target: Target) -> str:
    """Classify a target as ``national``, ``state``, or ``district``.

    Reads Populace's ``ledger_geography_level`` metadata (values like ``country``
    / ``state``), with fallbacks for custom/toy targets.
    """
    metadata = target.metadata or {}
    raw = (
        metadata.get("ledger_geography_level")
        or metadata.get("geography_level")
        or metadata.get("geo_level")
    )
    if raw:
        key = str(raw).strip().lower()
        if key in _NATIONAL_LEVELS:
            return "national"
        if key in _DISTRICT_LEVELS:
            return "district"
        return key  # e.g. "state"
    if metadata.get("state_fips"):
        return "state"
    return "national"


def target_family(target: Target) -> str:
    """Group a target by source family (e.g. ``irs_soi``, ``jct``, ``cms_aca``).

    Uses the Ledger ``source_record_id`` prefix, which matches Populace's
    ``TargetSpec.family``; falls back to ``target_role`` then ``"unknown"``.
    """
    metadata = target.metadata or {}
    explicit_family = metadata.get("target_family") or metadata.get("family")
    if explicit_family:
        return str(explicit_family)
    source_record_id = metadata.get("ledger_source_record_id") or target.name
    if source_record_id and "." in str(source_record_id):
        return str(source_record_id).split(".", 1)[0]
    return str(metadata.get("target_role") or source_record_id or "unknown")


def absolute_relative_error(target: Target, frame, weights: np.ndarray) -> float | None:
    """Absolute relative error for one target, or ``None`` if its value is zero."""
    value = float(target.value)
    if value == 0.0:
        return None
    achieved = float(target.achieved_value(frame, np.asarray(weights, dtype=np.float64)))
    return abs(achieved - value) / abs(value)


def target_diagnostics(
    frame, weights: np.ndarray, targets: Iterable[Target]
) -> list[dict[str, Any]]:
    """Per-target achieved values and errors for ``weights``.

    Relative errors are undefined for zero-valued targets, so those rows carry
    ``None`` for relative fields and still report signed/absolute misses.
    """
    weights = np.asarray(weights, dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for target in targets:
        value = float(target.value)
        achieved = float(target.achieved_value(frame, weights))
        error = achieved - value
        if value == 0.0:
            relative_error = None
            absolute_relative_error_value = None
        else:
            relative_error = error / value
            absolute_relative_error_value = abs(error) / abs(value)
        rows.append(
            {
                "name": target.row_name,
                "target_value": value,
                "achieved_value": achieved,
                "error": error,
                "absolute_error": abs(error),
                "relative_error": relative_error,
                "absolute_relative_error": absolute_relative_error_value,
                "family": target_family(target),
                "geography_level": geography_level(target),
                "is_zero_value_target": value == 0.0,
            }
        )
    return rows


def _are_stats(errors: list[float]) -> dict[str, float | int | None]:
    if not errors:
        return {"n": 0, "mean_are": None, "median_are": None, "max_are": None}
    arr = np.asarray(errors, dtype=np.float64)
    return {
        "n": int(arr.size),
        "mean_are": float(arr.mean()),
        "median_are": float(np.median(arr)),
        "max_are": float(arr.max()),
    }


def _absolute_error_stats(errors: list[float]) -> dict[str, float | int | None]:
    if not errors:
        return {"n": 0, "mean_absolute_error": None, "max_absolute_error": None}
    arr = np.asarray(errors, dtype=np.float64)
    return {
        "n": int(arr.size),
        "mean_absolute_error": float(arr.mean()),
        "max_absolute_error": float(arr.max()),
    }


def weight_diagnostics(weights: np.ndarray) -> dict[str, float | int]:
    """Effective sample size, max weight, and the retained-weight distribution."""
    weights = np.asarray(weights, dtype=np.float64)
    retained = weights[weights > 0]
    if retained.size == 0:
        return {
            "n_selected": 0,
            "sum_weight": 0.0,
            "ess": 0.0,
            "min_weight": 0.0,
            "mean_weight": 0.0,
            "max_weight": 0.0,
            "p50_weight": 0.0,
            "p90_weight": 0.0,
            "p99_weight": 0.0,
        }
    total = float(retained.sum())
    ess = total**2 / float((retained**2).sum())
    return {
        "n_selected": int(retained.size),
        "sum_weight": total,
        "ess": ess,
        "min_weight": float(retained.min()),
        "mean_weight": float(retained.mean()),
        "max_weight": float(retained.max()),
        "p50_weight": float(np.percentile(retained, 50)),
        "p90_weight": float(np.percentile(retained, 90)),
        "p99_weight": float(np.percentile(retained, 99)),
    }


def score(frame, weights: np.ndarray, targets: Iterable[Target], *, label: str = "") -> dict[str, Any]:
    """Score ``weights`` on ``frame`` against ``targets``.

    Returns overall ARE stats (mean/median/max), the weight distribution + ESS,
    and breakdowns ``by_family`` and ``by_geography``.
    """
    weights = np.asarray(weights, dtype=np.float64)
    targets = list(targets)

    diagnostics = target_diagnostics(frame, weights, targets)
    overall_errors: list[float] = []
    zero_value_absolute_errors: list[float] = []
    by_geo: dict[str, list[float]] = {}
    by_family: dict[str, list[float]] = {}
    for row in diagnostics:
        are = row["absolute_relative_error"]
        if are is None:
            zero_value_absolute_errors.append(row["absolute_error"])
            continue
        overall_errors.append(are)
        by_geo.setdefault(row["geography_level"], []).append(are)
        by_family.setdefault(row["family"], []).append(are)

    result: dict[str, Any] = {
        "label": label,
        "n_targets": len(targets),
        "n_zero_value_targets": len(zero_value_absolute_errors),
        **_are_stats(overall_errors),
        "by_family": {name: _are_stats(errors) for name, errors in sorted(by_family.items())},
        "by_geography": {level: _are_stats(errors) for level, errors in sorted(by_geo.items())},
        "zero_value_absolute_error": _absolute_error_stats(zero_value_absolute_errors),
    }
    result.update(weight_diagnostics(weights))
    return result
