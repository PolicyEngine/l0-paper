"""Scoring for a calibrated/sampled dataset against a target set.

Populace's exported ``score_targets`` helper evaluates a frozen weight vector
against any target set through the same constraint-matrix path used by
calibration. This module layers the paper-specific summaries on top: overall
ARE, by-family/geography cuts, denominator-degenerate labeling, and weight
diagnostics.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from populace.calibrate import default_target_loss_scales, score_targets
from populace.calibrate.target import Target, TargetSet

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
    achieved = float(
        target.achieved_value(frame, np.asarray(weights, dtype=np.float64))
    )
    return abs(achieved - value) / abs(value)


def target_diagnostics(
    frame,
    weights: np.ndarray,
    targets: Iterable[Target],
    *,
    loss_weights: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """Per-target achieved values and errors for ``weights``.

    Relative errors are undefined for zero-valued targets, so those rows carry
    ``None`` for relative fields and still report signed/absolute misses.

    When ``loss_weights`` (the per-target ``omega_j``, aligned to ``targets``) is
    given, each row carries it as ``loss_weight``. ``scale`` is emitted from
    Populace's canonical :func:`default_target_loss_scales` helper, so the stored
    diagnostics reproduce the production objective denominator. Storing the raw
    ``target_value``/``achieved_value`` together with ``scale`` and
    ``loss_weight`` lets the capped, weighted MAPE be recomputed downstream at
    any cap (see :mod:`l0_paper.experiments.crunch`).
    """
    targets = list(targets)
    if not targets:
        return []
    weights = np.asarray(weights, dtype=np.float64)
    scored = score_targets(frame, TargetSet(targets), weights=weights)
    scored_targets = list(scored.problem.targets)
    values = np.asarray(
        [float(diag.target) for diag in scored.diagnostics], dtype=np.float64
    )
    scales = default_target_loss_scales(values)
    omega_by_name: dict[str, float] = {}
    if loss_weights is not None:
        omega = np.asarray(loss_weights, dtype=np.float64)
        omega_by_name = {
            target.row_name: float(weight)
            for target, weight in zip(targets, omega, strict=True)
        }
    rows: list[dict[str, Any]] = []
    for index, (target, diag) in enumerate(
        zip(scored_targets, scored.diagnostics, strict=True)
    ):
        value = float(diag.target)
        achieved = float(diag.final_estimate)
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
                "scale": float(scales[index]),
                "loss_weight": omega_by_name.get(target.row_name),
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


def identifiability_floors(
    frame, targets: Iterable[Target], *, weight_entity: str = "household"
) -> dict[str, float]:
    """Per-target *identifiability floor*: the largest single-record contribution.

    A target's relative error is only meaningful when no single record can move it
    by O(1). The floor for target ``j`` is ``max_i |M_ji| w0_i`` -- the biggest
    contribution any one record makes at its *initial* weight, where ``M`` is the
    constraint matrix and ``w0`` the initial weights. A target whose ``|value|`` is
    below its floor is **denominator-degenerate**: one household's presence or
    absence swings its ARE past 100%, so the ARE reflects integer placement noise
    rather than calibration quality (see :func:`degenerate_target_names`). This is
    a structural property of the target surface, computed once, not a percentile
    or winsorization cutoff.

    Keyed by :pyattr:`Target.row_name` (matching :func:`target_diagnostics`).
    """
    from populace.calibrate.matrix import build_constraint_matrix
    from populace.calibrate.target import TargetSet

    targets = list(targets)
    if not targets:
        return {}
    problem = build_constraint_matrix(frame, TargetSet(targets), weight_entity)
    w0 = np.asarray(problem.initial_weights.values, dtype=np.float64)
    coo = problem.matrix.tocoo()
    contributions = np.abs(coo.data) * w0[coo.col]
    floors = np.zeros(problem.matrix.shape[0], dtype=np.float64)
    np.maximum.at(floors, coo.row, contributions)
    return {
        target.row_name: float(floors[i]) for i, target in enumerate(problem.targets)
    }


def degenerate_audit(
    frame, targets: Iterable[Target], *, weight_entity: str = "household"
) -> list[dict[str, Any]]:
    """One-time audit of the denominator-degenerate targets (named, with floors).

    Returns one row per degenerate target -- ``name``, ``family``,
    ``geography_level``, ``target_value``, ``identifiability_floor``, and the
    ``floor_ratio`` (floor / |value|, how many households-worth one record is) --
    so the report can *name* exactly what is dropped in the targeted-removal
    sensitivity, with no statistical cutoff.
    """
    targets = list(targets)
    floors = identifiability_floors(frame, targets, weight_entity=weight_entity)
    rows: list[dict[str, Any]] = []
    for target in targets:
        floor = floors.get(target.row_name)
        value = float(target.value)
        if floor is None or value == 0.0 or abs(value) >= floor:
            continue
        rows.append(
            {
                "name": target.row_name,
                "family": target_family(target),
                "geography_level": geography_level(target),
                "target_value": value,
                "identifiability_floor": floor,
                "floor_ratio": floor / abs(value),
            }
        )
    return sorted(rows, key=lambda r: r["floor_ratio"], reverse=True)


def degenerate_target_names(
    frame, targets: Iterable[Target], *, weight_entity: str = "household"
) -> set[str]:
    """Names of denominator-degenerate targets (``|value| <`` identifiability floor).

    See :func:`identifiability_floors`. These targets are *named and reported*, and
    a targeted-removal sensitivity is computed beside the full mean (rather than
    winsorizing the ARE distribution).
    """
    floors = identifiability_floors(frame, targets, weight_entity=weight_entity)
    degenerate: set[str] = set()
    for target in targets:
        floor = floors.get(target.row_name)
        if floor is not None and abs(float(target.value)) < floor:
            degenerate.add(target.row_name)
    return degenerate


def score(
    frame,
    weights: np.ndarray,
    targets: Iterable[Target],
    *,
    label: str = "",
    degenerate_names: set[str] | None = None,
) -> dict[str, Any]:
    """Score ``weights`` on ``frame`` against ``targets``.

    Returns overall ARE stats (mean/median/max), the weight distribution + ESS,
    and breakdowns ``by_family`` and ``by_geography``. When ``degenerate_names`` is
    given (see :func:`degenerate_target_names`), also reports
    ``mean_are_ex_degenerate`` -- the overall mean with exactly those named
    denominator-degenerate targets removed -- and ``n_degenerate``.
    """
    weights = np.asarray(weights, dtype=np.float64)
    targets = list(targets)
    degenerate_names = degenerate_names or set()

    diagnostics = target_diagnostics(frame, weights, targets)
    overall_errors: list[float] = []
    nondegenerate_errors: list[float] = []
    n_degenerate = 0
    zero_value_absolute_errors: list[float] = []
    by_geo: dict[str, list[float]] = {}
    by_family: dict[str, list[float]] = {}
    for row in diagnostics:
        are = row["absolute_relative_error"]
        if are is None:
            zero_value_absolute_errors.append(row["absolute_error"])
            continue
        overall_errors.append(are)
        if row["name"] in degenerate_names:
            n_degenerate += 1
        else:
            nondegenerate_errors.append(are)
        by_geo.setdefault(row["geography_level"], []).append(are)
        by_family.setdefault(row["family"], []).append(are)

    result: dict[str, Any] = {
        "label": label,
        "n_targets": len(targets),
        "n_zero_value_targets": len(zero_value_absolute_errors),
        **_are_stats(overall_errors),
        "by_family": {
            name: _are_stats(errors) for name, errors in sorted(by_family.items())
        },
        "by_geography": {
            level: _are_stats(errors) for level, errors in sorted(by_geo.items())
        },
        "zero_value_absolute_error": _absolute_error_stats(zero_value_absolute_errors),
    }
    if degenerate_names:
        result["n_degenerate"] = n_degenerate
        result["mean_are_ex_degenerate"] = (
            float(np.mean(nondegenerate_errors)) if nondegenerate_errors else None
        )
    result.update(weight_diagnostics(weights))
    return result
