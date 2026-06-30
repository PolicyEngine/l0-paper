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
l0_lambda=0.0)`` fits all weights, then a probability-proportional-to-size sample
of ``n`` draws is taken from the calibrated weights. The sweep default is
sampling with replacement plus ``equal_mass`` reweighting: each draw receives
``sum(weights) / n``, so a record drawn ``k`` times carries ``k`` shares. This is
the Hansen-Hurwitz integerisation of the dense weights. With ``n`` set to
condition A's retained count, the two are compared at a matched record budget.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from populace.calibrate import calibrate
from populace.calibrate.target import TargetSet
from populace.frame import MassChange, WeightKind, Weights

# Default Hard-Concrete / optimizer hyperparameters (Appendix table in the paper).
DEFAULT_EPOCHS = 1000
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
    # Weight-concentration controls. ``max_weight_ratio`` is a hard per-record
    # cap; ``l2_lambda`` is Populace's soft concentration penalty and is only
    # applied for the L0/Hard-Concrete gated condition.
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
    target_records: int | None,
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
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> RunResult:
    """Condition A: informed L0 sampling with Hard-Concrete gates.

    When ``target_records`` is provided, Populace searches for an L0 penalty that
    reaches the requested retained-record count. When it is ``None``, the supplied
    ``l0_lambda`` is used directly as a fixed sparsity penalty.

    ``l2_lambda`` is passed through to Populace's soft concentration penalty.
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
        l2_lambda=l2_lambda,
        init_mean=init_mean,
        temperature=temperature,
        budget_iters=budget_iters,
        seed=seed,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
        progress_callback=progress_callback,
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


def run_l0_post_refit(
    frame,
    fit_targets: TargetSet,
    l0_selection: RunResult,
    *,
    weight_entity: str = "household",
    seed: int | None = None,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    mass: str = "conserve",
    max_weight_ratio: float | None = None,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> RunResult:
    """Post-selection refit for an informed-L0 subset.

    Hard-Concrete gates decide which records survive. This refits ordinary dense
    calibration weights on exactly those survivors, using the L0 weights as the
    starting vector, then maps the fitted subset back onto the full candidate
    universe. It is the post-L0 analogue of the random-then-reweight baseline.
    """
    start = time.perf_counter()
    if weight_entity != l0_selection.weight_entity:
        raise ValueError(
            "weight_entity must match l0_selection.weight_entity "
            f"({weight_entity!r} != {l0_selection.weight_entity!r})."
        )
    full_weights = np.asarray(l0_selection.weights, dtype=np.float64)
    ids = frame.table(weight_entity)[f"{weight_entity}_id"].to_numpy()
    if full_weights.shape != ids.shape:
        raise ValueError(
            "l0_selection weights must align with the candidate frame, got "
            f"{full_weights.shape} vs {ids.shape}."
        )
    prune_atol = 1e-6 * float(np.mean(np.asarray(l0_selection.initial_weights)))
    selected = full_weights > prune_atol
    if not selected.any():
        raise ValueError("Cannot post-refit L0 selection with no retained records.")

    chosen_ids = set(ids[selected].tolist())
    membership_column = f"person_{weight_entity}_id"
    person_mask = frame.table("person")[membership_column].isin(chosen_ids).to_numpy()
    subset = frame.select(person_mask)

    subset_ids = subset.table(weight_entity)[f"{weight_entity}_id"].to_numpy()
    selected_weights = (
        pd.Series(full_weights, index=ids)
        .reindex(subset_ids)
        .astype(np.float64)
        .to_numpy()
    )
    if not np.isfinite(selected_weights).all() or not (selected_weights > 0).any():
        raise ValueError("Selected L0 weights are not a positive finite vector.")

    subset_start = subset.weights_for(weight_entity)
    subset = subset.with_weights(
        weight_entity,
        Weights(values=selected_weights, kind=WeightKind.CALIBRATED),
        mass=MassChange(
            factor=float(selected_weights.sum() / subset_start.values.sum()),
            reason="initialize dense post-refit from informed L0 selected weights",
        ),
    )
    fit_seed = l0_selection.seed if seed is None else seed
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
        seed=fit_seed,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
        progress_callback=progress_callback,
    )

    def _to_full(values: np.ndarray) -> np.ndarray:
        return (
            pd.Series(np.asarray(values, dtype=np.float64), index=subset_ids)
            .reindex(ids)
            .fillna(0.0)
            .to_numpy()
        )

    weights = _to_full(result.weights)
    initial_weights = _to_full(result.initial_weights)
    runtime = l0_selection.runtime_s + (time.perf_counter() - start)
    options = dict(result.options)
    options.update(
        {
            "post_l0_refit": True,
            "selection_l0_lambda": l0_selection.l0_lambda,
            "selection_runtime_s": l0_selection.runtime_s,
            "selection_final_loss": l0_selection.final_loss,
            "selection_n_selected": l0_selection.n_selected,
            "target_loss_cap": target_loss_cap,
        }
    )
    return RunResult(
        method="informed_l0_refit",
        weight_entity=weight_entity,
        weights=weights,
        initial_weights=initial_weights,
        n_records=weights.size,
        n_selected=int(np.count_nonzero(weights)),
        l0_lambda=float(l0_selection.l0_lambda),
        l2_lambda=float(l0_selection.l2_lambda),
        max_weight_ratio=max_weight_ratio,
        loss_trajectory=np.asarray(result.loss_trajectory, dtype=np.float64),
        initial_loss=float(result.initial_loss),
        final_loss=float(result.final_loss),
        runtime_s=runtime,
        seed=fit_seed,
        options=options,
        calibration_result=result,
        sampling={
            "strategy": "post_l0_refit",
            "selection_method": l0_selection.method,
            "selection_n_selected": int(l0_selection.n_selected),
        },
    )


def run_l1(
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
    l1_lambda_bracket: tuple[float, float] = (1e-3, 1e2),
    budget_iters: int = 10,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
) -> RunResult:
    """Condition D: informed L1 sampling -- proximal (soft-threshold) selection.

    The convex-sparse analog of :func:`run_l0`: the *same* calibrator with
    ``method="prox"`` and an L1 penalty drives low-pull records to exact zero,
    jointly selecting and weighting a sparse subset. An outer bisection on
    ``log10(l1_lambda)`` hits the requested record count -- a larger ``l1_lambda``
    retains fewer records (monotone) -- mirroring the L0 budget search so the two
    sparse methods are compared at a matched budget.
    """
    start = time.perf_counter()

    def _fit(l1_lambda: float):
        try:
            return calibrate(
                frame,
                fit_targets,
                weight_entity=weight_entity,
                method="prox",
                epochs=epochs,
                learning_rate=learning_rate,
                mass=mass,
                max_weight_ratio=max_weight_ratio,
                l1_lambda=l1_lambda,
                seed=seed,
                target_loss_weights=target_loss_weights,
                target_loss_cap=target_loss_cap,
            )
        except ValueError as exc:
            # l1_lambda large enough to zero every weight: report as zero survivors
            # so the search backs the penalty off. Other ValueErrors are genuine
            # input/solver failures and should stop the sweep loudly.
            if "L1 penalty zeroed every weight" not in str(exc):
                raise
            return None

    if len(l1_lambda_bracket) != 2:
        raise ValueError("l1_lambda_bracket must contain exactly two positive bounds.")
    bracket = tuple(float(x) for x in l1_lambda_bracket)
    if bracket[0] <= 0 or bracket[1] <= 0:
        raise ValueError("l1_lambda_bracket bounds must be positive.")
    if bracket[0] > bracket[1]:
        raise ValueError("l1_lambda_bracket lower bound must be <= upper bound.")

    log_lo = float(np.log10(bracket[0]))
    log_hi = float(np.log10(bracket[1]))
    best = None
    best_gap = None
    chosen_l1 = bracket[0]
    for _ in range(budget_iters):
        mid = (log_lo + log_hi) / 2.0
        l1_lambda = float(10.0**mid)
        result = _fit(l1_lambda)
        n_selected = 0 if result is None else int(result.n_nonzero)
        if result is not None:
            gap = abs(n_selected - target_records)
            if best is None or gap < best_gap:
                best, best_gap, chosen_l1 = result, gap, l1_lambda
        if n_selected > target_records:
            log_lo = mid  # too many records retained -> raise the penalty
        else:
            log_hi = mid  # too few (or all zeroed) -> lower the penalty
    if best is None:
        # Nothing in the bracket fit without zeroing every weight; fall back to the
        # smallest penalty, which retains the most records.
        chosen_l1 = bracket[0]
        best = _fit(chosen_l1)
        if best is None:
            raise ValueError(
                "L1 lambda bracket zeroed every weight even at the lower bound "
                f"{chosen_l1:g}; widen the bracket downward or lower the learning rate."
            )
    runtime = time.perf_counter() - start

    weights = np.asarray(best.weights, dtype=np.float64)
    options = dict(best.options)
    options.update(
        {
            "l1_lambda": chosen_l1,
            "l1_lambda_bracket": list(bracket),
            "budget_iters": budget_iters,
            "target_loss_cap": target_loss_cap,
        }
    )
    return RunResult(
        method="informed_l1",
        weight_entity=weight_entity,
        weights=weights,
        initial_weights=np.asarray(best.initial_weights, dtype=np.float64),
        n_records=weights.size,
        n_selected=int(best.n_nonzero),
        l0_lambda=0.0,
        l2_lambda=0.0,
        max_weight_ratio=max_weight_ratio,
        loss_trajectory=np.asarray(best.loss_trajectory, dtype=np.float64),
        initial_loss=float(best.initial_loss),
        final_loss=float(best.final_loss),
        runtime_s=runtime,
        seed=seed,
        options=options,
        calibration_result=best,
        sampling=None,
    )


def weighted_sample(
    weights: np.ndarray,
    n_sample: int,
    *,
    seed: int = 0,
    replace: bool = True,
    reweight: str = "equal_mass",
) -> np.ndarray:
    """Draw records with probability proportional to ``weights``.

    Returns a full-length weight vector (zeros for unselected records). Under
    ``replace=True`` and ``reweight="equal_mass"``, this is the unbiased
    Hansen-Hurwitz integerisation of the dense weights: every draw receives
    ``sum(weights) / n_sample`` and repeated draws accumulate on the same record,
    so ``E[sampled_weight_i] == weights_i``.

    * ``"equal_mass"`` -- every draw gets ``sum(weights) / n_sample``.
      With replacement this is unbiased for the input weights. Without replacement
      it forces equal post-weights on distinct records and under-weights large
      probability records at large budgets.
    * ``"renorm_kept"`` -- selected records keep their fitted weight, then the
      vector is rescaled so its total equals ``sum(weights)``. This is a biased
      contrast for PPS draws because high-weight records are both more likely to
      be sampled and keep larger post-sample weights.
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
        raise ValueError(
            f"reweight must be 'equal_mass' or 'renorm_kept', got {reweight!r}."
        )
    return full


def calibrate_dense(
    frame,
    fit_targets: TargetSet,
    *,
    weight_entity: str = "household",
    seed: int = 0,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    mass: str = "conserve",
    max_weight_ratio: float | None = None,
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> tuple[Any, float]:
    """Dense calibration (gates off); returns ``(calibration_result, runtime_s)``.

    The dense fit does not depend on the sample size, so a budget sweep fits it
    **once per seed** and draws many matched-budget samples from it with
    :func:`sample_from_dense` -- far cheaper than re-fitting the full frame at
    every budget. :func:`run_dense_then_sample` composes the two for the
    single-run path.
    """
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
        progress_callback=progress_callback,
    )
    return dense, time.perf_counter() - start


def sample_from_dense(
    dense: Any,
    *,
    weight_entity: str = "household",
    n_sample: int,
    seed: int = 0,
    max_weight_ratio: float | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    sample_seed: int | None = None,
    replace: bool = True,
    reweight: str = "equal_mass",
    dense_runtime: float = 0.0,
) -> RunResult:
    """Build a ``dense_sample`` :class:`RunResult` from a cached dense fit.

    ``dense_runtime`` is folded into the reported ``runtime_s`` so the survey-weight
    sampling cost reflects the full fit-then-sample pipeline even when the dense
    fit is amortized across budgets. The default is ``replace=True`` with
    ``reweight="equal_mass"``, the unbiased PPS/Hansen-Hurwitz integerisation.
    """
    start = time.perf_counter()
    draw_seed = seed if sample_seed is None else sample_seed
    sampled = weighted_sample(
        dense.weights, n_sample, seed=draw_seed, replace=replace, reweight=reweight
    )
    runtime = dense_runtime + (time.perf_counter() - start)
    options = dict(dense.options)
    options.update(
        {
            "l2_lambda": 0.0,
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
        n_selected=int(n_sample),
        l0_lambda=0.0,
        l2_lambda=0.0,
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
            "n_unique_selected": int(np.count_nonzero(sampled)),
            "sample_seed": int(draw_seed),
            "replace": bool(replace),
            "reweight": reweight,
        },
    )


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
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    sample_seed: int | None = None,
    replace: bool = True,
    reweight: str = "equal_mass",
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> RunResult:
    """Condition B: dense calibration (gates off), then weighted random sampling."""
    dense, dense_runtime = calibrate_dense(
        frame,
        fit_targets,
        weight_entity=weight_entity,
        seed=seed,
        epochs=epochs,
        learning_rate=learning_rate,
        mass=mass,
        max_weight_ratio=max_weight_ratio,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
        progress_callback=progress_callback,
    )
    return sample_from_dense(
        dense,
        weight_entity=weight_entity,
        n_sample=n_sample,
        seed=seed,
        max_weight_ratio=max_weight_ratio,
        target_loss_cap=target_loss_cap,
        sample_seed=sample_seed,
        replace=replace,
        reweight=reweight,
        dense_runtime=dense_runtime,
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
    target_loss_weights: np.ndarray | None = None,
    target_loss_cap: float = DEFAULT_TARGET_LOSS_CAP,
    sample_seed: int | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
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
        progress_callback=progress_callback,
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
            "l2_lambda": 0.0,
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
        l2_lambda=0.0,
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
