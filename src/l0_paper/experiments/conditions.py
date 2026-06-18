"""All calibration conditions, run on a shared pre-calibration frame.

Conditions consume a Populace :class:`~populace.frame.Frame` and a
:class:`~populace.calibrate.target.TargetSet` (the *fit* targets) and return a
:class:`RunResult` whose ``weights`` is a full-length vector over the candidate
universe -- zero for records the method did not retain. Representing the reduced
dataset as a sparse full-length vector lets every method be scored identically
against the same targets (zeros contribute nothing to an aggregate).

Condition A -- informed L0 / Hard-Concrete: ``calibrate(..., target_records=N)``
jointly fits log-weights and gates to retain ~N records.

Condition B -- dense then sample: ``calibrate(..., target_records=None,
l0_lambda=0.0)`` fits all weights, then a weighted random sample of ``n`` records
(probability proportional to the calibrated weight) is drawn and reweighted to a
deployable dataset. With ``n`` set to condition A's retained count, the two are
compared at a matched record budget.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from populace.calibrate import calibrate
from populace.calibrate.target import TargetSet
from populace.frame import MassChange, Weights

# Default Hard-Concrete / optimizer hyperparameters (Appendix table in the paper).
DEFAULT_EPOCHS = 256
DEFAULT_LEARNING_RATE = 0.02
DEFAULT_INIT_MEAN = 0.999
DEFAULT_TEMPERATURE = 0.25
DEFAULT_TARGET_LOSS_CAP = 10.0


@dataclass(frozen=True)
class RunResult:
    """Outcome of one calibration condition, with paper-ready diagnostics."""

    method: str
    weight_entity: str
    weights: np.ndarray
    initial_weights: np.ndarray
    n_records: int
    n_selected: int
    l0_lambda: float
    # Weight-concentration controls. Populace bounds per-record weight magnitude
    # with a HARD cap (``max_weight_ratio``), not the paper's soft L2 penalty, so
    # ``calibrate`` has no L2 term. ``l2_lambda`` is recorded for reporting parity
    # with the paper's loss (Eq. 1) but is not currently applied by the solver.
    l2_lambda: float
    max_weight_ratio: float | None
    loss_trajectory: np.ndarray
    initial_loss: float
    final_loss: float
    runtime_s: float
    seed: int
    options: dict[str, Any]
    calibration_result: Any = field(repr=False, default=None)
    sampling: dict[str, Any] | None = None


def run_l0(
    frame,
    fit_targets: TargetSet,
    *,
    weight_entity: str = "household",
    target_records: int,
    seed: int = 0,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    mass: str = "conserve",
    max_weight_ratio: float | None = None,
    l0_lambda: float = 1e-3,
    l2_lambda: float = 0.0,
    init_mean: float = DEFAULT_INIT_MEAN,
    temperature: float = DEFAULT_TEMPERATURE,
    budget_iters: int = 10,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
) -> RunResult:
    """Condition A: informed L0 sampling with Hard-Concrete gates at a budget.

    ``l2_lambda`` is recorded only; Populace controls weight concentration via the
    hard ``max_weight_ratio`` cap, so it is not passed to ``calibrate``.
    """
    start = time.perf_counter()
    result = calibrate(
        frame,
        fit_targets,
        weight_entity=weight_entity,
        epochs=epochs,
        learning_rate=learning_rate,
        mass=mass,
        max_weight_ratio=max_weight_ratio,
        target_records=target_records,
        l0_lambda=l0_lambda,
        init_mean=init_mean,
        temperature=temperature,
        budget_iters=budget_iters,
        seed=seed,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
    )
    runtime = time.perf_counter() - start
    weights = np.asarray(result.weights, dtype=np.float64)
    options = dict(result.options)
    options.update(
        {
            "l0_lambda_warm_start": l0_lambda,
            "l2_lambda": l2_lambda,
            "init_mean": init_mean,
            "temperature": temperature,
            "budget_iters": budget_iters,
            "target_loss_cap": target_loss_cap,
        }
    )
    return RunResult(
        method="informed_l0",
        weight_entity=weight_entity,
        weights=weights,
        initial_weights=np.asarray(result.initial_weights, dtype=np.float64),
        n_records=weights.size,
        n_selected=int(result.n_nonzero),
        l0_lambda=float(result.l0_lambda),
        l2_lambda=float(l2_lambda),
        max_weight_ratio=max_weight_ratio,
        loss_trajectory=np.asarray(result.loss_trajectory, dtype=np.float64),
        initial_loss=float(result.initial_loss),
        final_loss=float(result.final_loss),
        runtime_s=runtime,
        seed=seed,
        options=options,
        calibration_result=result,
        sampling=None,
    )


def weighted_sample(
    weights: np.ndarray,
    n_sample: int,
    *,
    seed: int = 0,
    replace: bool = False,
    reweight: str = "equal_mass",
) -> np.ndarray:
    """Draw ``n_sample`` records with probability proportional to ``weights``.

    Returns a full-length weight vector (zeros for unselected records). The
    selected records are reweighted so the sample carries the same total
    population mass as the input weights:

    * ``"equal_mass"`` -- every selected record gets ``sum(weights) / n_sample``
      (integerisation: probability-proportional-to-size with equal post-weights).
    * ``"renorm_kept"`` -- selected records keep their fitted weight, then the
      vector is rescaled so its total equals ``sum(weights)``.
    """
    weights = np.asarray(weights, dtype=np.float64)
    n = weights.size
    total = float(weights.sum())
    if total <= 0:
        raise ValueError("weighted_sample requires positive total weight.")
    if not replace:
        n_sample = min(n_sample, n)
    probabilities = weights / total
    rng = np.random.default_rng(seed)
    indices = rng.choice(n, size=n_sample, replace=replace, p=probabilities)

    full = np.zeros(n, dtype=np.float64)
    if reweight == "equal_mass":
        np.add.at(full, indices, total / n_sample)
    elif reweight == "renorm_kept":
        np.add.at(full, indices, weights[indices])
        achieved = full.sum()
        if achieved > 0:
            full *= total / achieved
    else:
        raise ValueError(f"reweight must be 'equal_mass' or 'renorm_kept', got {reweight!r}.")
    return full


def run_dense_then_sample(
    frame,
    fit_targets: TargetSet,
    *,
    weight_entity: str = "household",
    n_sample: int,
    seed: int = 0,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    mass: str = "conserve",
    max_weight_ratio: float | None = None,
    l2_lambda: float = 0.0,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    sample_seed: int | None = None,
    replace: bool = False,
    reweight: str = "equal_mass",
) -> RunResult:
    """Condition B: dense calibration (gates off), then weighted random sampling."""
    start = time.perf_counter()
    dense = calibrate(
        frame,
        fit_targets,
        weight_entity=weight_entity,
        epochs=epochs,
        learning_rate=learning_rate,
        mass=mass,
        max_weight_ratio=max_weight_ratio,
        target_records=None,
        l0_lambda=0.0,
        seed=seed,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
    )
    draw_seed = seed if sample_seed is None else sample_seed
    sampled = weighted_sample(
        dense.weights, n_sample, seed=draw_seed, replace=replace, reweight=reweight
    )
    runtime = time.perf_counter() - start
    options = dict(dense.options)
    options.update(
        {
            "l2_lambda": l2_lambda,
            "target_loss_cap": target_loss_cap,
            "gates": "off",
        }
    )

    return RunResult(
        method="dense_sample",
        weight_entity=weight_entity,
        weights=sampled,
        initial_weights=np.asarray(dense.initial_weights, dtype=np.float64),
        n_records=sampled.size,
        n_selected=int(np.count_nonzero(sampled)),
        l0_lambda=0.0,
        l2_lambda=float(l2_lambda),
        max_weight_ratio=max_weight_ratio,
        loss_trajectory=np.asarray(dense.loss_trajectory, dtype=np.float64),
        initial_loss=float(dense.initial_loss),
        final_loss=float(dense.final_loss),
        runtime_s=runtime,
        seed=seed,
        options=options,
        calibration_result=dense,
        sampling={
            "n_sample": int(n_sample),
            "sample_seed": int(draw_seed),
            "replace": bool(replace),
            "reweight": reweight,
        },
    )


def run_random_then_reweight(
    frame,
    fit_targets: TargetSet,
    *,
    weight_entity: str = "household",
    n_sample: int,
    seed: int = 0,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    mass: str = "free",
    max_weight_ratio: float | None = None,
    l2_lambda: float = 0.0,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    sample_seed: int | None = None,
) -> RunResult:
    """Condition C: uniform random subset, then gradient-descent reweight.

    The paper's reduce-first "Random + reweight" baseline. Selection is *not*
    informed by the targets: an equal-probability random subset of ``n_sample``
    records is drawn first, and only that subset is reweighted to the targets by a
    dense calibration (gates off). The subset is first weighted up to the full
    population total, so the reweighting targets the same population as the
    full-frame conditions A and B.
    """
    start = time.perf_counter()
    id_column = f"{weight_entity}_id"
    membership_column = f"person_{weight_entity}_id"
    ids = frame.table(weight_entity)[id_column].to_numpy()
    n_full = ids.size
    n_sample = min(n_sample, n_full)
    draw_seed = seed if sample_seed is None else sample_seed
    rng = np.random.default_rng(draw_seed)
    chosen = rng.choice(ids, size=n_sample, replace=False)

    person_mask = (
        frame.table("person")[membership_column].isin(set(chosen.tolist())).to_numpy()
    )
    subset = frame.select(person_mask)

    # Weight the random subset up to the full population total before reweighting,
    # so it represents the same population as the full-frame conditions.
    full_total = float(frame.weights_for(weight_entity).values.sum())
    subset_weights = subset.weights_for(weight_entity)
    subset_total = float(subset_weights.values.sum())
    n_subset = len(subset_weights.values)
    uniform = np.full(n_subset, full_total / n_subset, dtype=np.float64)
    subset = subset.with_weights(
        weight_entity,
        Weights(values=uniform, kind=subset_weights.kind),
        mass=MassChange(
            factor=full_total / subset_total,
            reason="weight uniform random subset up to population total",
        ),
    )

    result = calibrate(
        subset,
        fit_targets,
        weight_entity=weight_entity,
        epochs=epochs,
        learning_rate=learning_rate,
        mass=mass,
        max_weight_ratio=max_weight_ratio,
        target_records=None,
        l0_lambda=0.0,
        seed=seed,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
    )

    # Map the subset's fitted weights back onto the full candidate universe
    # (zeros for unselected records), keyed by id so Frame.select reordering is safe.
    subset_ids = subset.table(weight_entity)[id_column].to_numpy()

    def _to_full(values: np.ndarray) -> np.ndarray:
        return (
            pd.Series(np.asarray(values, dtype=np.float64), index=subset_ids)
            .reindex(ids)
            .fillna(0.0)
            .to_numpy()
        )

    weights = _to_full(result.weights)
    runtime = time.perf_counter() - start
    options = dict(result.options)
    options.update(
        {
            "l2_lambda": l2_lambda,
            "target_loss_cap": target_loss_cap,
            "gates": "off",
            "selection": "uniform_random",
        }
    )

    return RunResult(
        method="random_reweight",
        weight_entity=weight_entity,
        weights=weights,
        initial_weights=_to_full(result.initial_weights),
        n_records=n_full,
        n_selected=int(np.count_nonzero(weights)),
        l0_lambda=0.0,
        l2_lambda=float(l2_lambda),
        max_weight_ratio=max_weight_ratio,
        loss_trajectory=np.asarray(result.loss_trajectory, dtype=np.float64),
        initial_loss=float(result.initial_loss),
        final_loss=float(result.final_loss),
        runtime_s=runtime,
        seed=seed,
        options=options,
        calibration_result=result,
        sampling={
            "strategy": "uniform_random",
            "n_sample": int(n_sample),
            "sample_seed": int(draw_seed),
        },
    )
