"""Run artifacts: per-method ``.npz`` payloads and the reproducibility manifest.

Issue #4 requires each run to record enough to reproduce the comparison: the
Populace commit, target/build identity, solver options, seeds, retained count,
fit metrics, runtime, and output paths. :func:`method_summary` assembles the
per-method record and :func:`write_run_manifest` writes the combined manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .conditions import RunResult
from .metrics import target_diagnostics


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _jsonable(obj: Any) -> Any:
    """Coerce an arbitrary object graph into JSON-serializable form."""
    return json.loads(json.dumps(obj, default=_json_default, allow_nan=False))


def method_summary(
    run: RunResult,
    in_sample: dict[str, Any],
    out_of_sample: dict[str, Any],
    *,
    artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    """Per-method record with metadata + in/out-of-sample fit metrics."""
    summary = {
        "method": run.method,
        "weight_entity": run.weight_entity,
        "seed": run.seed,
        "candidate_records": run.n_records,
        "retained_records": run.n_selected,
        "l0_lambda": run.l0_lambda,
        # ``max_weight_ratio`` is the hard cap; ``l2_lambda`` is the soft
        # concentration penalty used only by the informed-L0/Hard-Concrete path.
        "l2_lambda": run.l2_lambda,
        "max_weight_ratio": run.max_weight_ratio,
        "epochs": int(run.loss_trajectory.size),
        "solver_initial_loss": run.initial_loss,
        "solver_final_loss": run.final_loss,
        "runtime_s": run.runtime_s,
        "solver_options": _jsonable(run.options),
        "sampling": run.sampling,
        "in_sample": _jsonable(in_sample),
        "out_of_sample": _jsonable(out_of_sample),
    }
    if artifact_path is not None:
        summary["artifact_path"] = str(artifact_path)
    return summary


def _float_array(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray(
        [np.nan if row[key] is None else row[key] for row in rows],
        dtype=np.float64,
    )


def _object_array(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([row[key] for row in rows], dtype=object)


def save_method_npz(
    path: str | Path,
    run: RunResult,
    *,
    frame,
    fit_targets,
    holdout_targets=(),
) -> Path:
    """Persist weights, loss trajectory, and fit diagnostics for one method."""
    path = Path(path)
    fit_rows = target_diagnostics(frame, run.weights, fit_targets)
    holdout_rows = target_diagnostics(frame, run.weights, holdout_targets)
    fit_names = _object_array(fit_rows, "name")
    fit_values = _float_array(fit_rows, "target_value")
    fit_achieved = _float_array(fit_rows, "achieved_value")
    fit_relative = _float_array(fit_rows, "relative_error")
    fit_absolute_relative = _float_array(fit_rows, "absolute_relative_error")
    np.savez_compressed(
        path,
        weights=run.weights,
        initial_weights=run.initial_weights,
        solver_loss_trajectory=run.loss_trajectory,
        loss_trajectory=run.loss_trajectory,
        fit_target_names=fit_names,
        fit_target_values=fit_values,
        fit_achieved_values=fit_achieved,
        fit_errors=_float_array(fit_rows, "error"),
        fit_absolute_errors=_float_array(fit_rows, "absolute_error"),
        fit_relative_errors=fit_relative,
        fit_absolute_relative_errors=fit_absolute_relative,
        fit_families=_object_array(fit_rows, "family"),
        fit_geography_levels=_object_array(fit_rows, "geography_level"),
        fit_is_zero_value_target=np.asarray(
            [row["is_zero_value_target"] for row in fit_rows], dtype=bool
        ),
        holdout_target_names=_object_array(holdout_rows, "name"),
        holdout_target_values=_float_array(holdout_rows, "target_value"),
        holdout_achieved_values=_float_array(holdout_rows, "achieved_value"),
        holdout_errors=_float_array(holdout_rows, "error"),
        holdout_absolute_errors=_float_array(holdout_rows, "absolute_error"),
        holdout_relative_errors=_float_array(holdout_rows, "relative_error"),
        holdout_absolute_relative_errors=_float_array(
            holdout_rows, "absolute_relative_error"
        ),
        holdout_families=_object_array(holdout_rows, "family"),
        holdout_geography_levels=_object_array(holdout_rows, "geography_level"),
        holdout_is_zero_value_target=np.asarray(
            [row["is_zero_value_target"] for row in holdout_rows], dtype=bool
        ),
        # Backward-compatible aliases for the fit diagnostics.
        target_names=fit_names,
        target_values=fit_values,
        final_estimates=fit_achieved,
        relative_errors=fit_relative,
        absolute_relative_errors=fit_absolute_relative,
    )
    return path


def save_weight_npz(
    path: str | Path,
    run: RunResult,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Persist the full candidate-aligned weights needed to rescore a run.

    This intentionally stays lighter than :func:`save_method_npz`: per-target
    diagnostics already live in ``target_diagnostics_long.csv``. The weight vector,
    initial weights, loss trajectory, and JSON metadata are enough to reconstruct
    any later Populace score against the frozen precalibration artifact.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    payload = _jsonable(metadata or {})
    with tmp.open("wb") as handle:
        np.savez_compressed(
            handle,
            weights=np.asarray(run.weights, dtype=np.float64),
            initial_weights=np.asarray(run.initial_weights, dtype=np.float64),
            solver_loss_trajectory=np.asarray(run.loss_trajectory, dtype=np.float64),
            loss_trajectory=np.asarray(run.loss_trajectory, dtype=np.float64),
            metadata_json=np.asarray(json.dumps(payload, default=_json_default)),
        )
    tmp.replace(path)
    return path


def write_run_manifest(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write the run manifest JSON."""
    path = Path(path)
    path.write_text(
        json.dumps(payload, indent=2, default=_json_default, allow_nan=False)
    )
    return path
