"""Split a target set into fit and out-of-sample (held-out) targets.

A sampler can match the targets it is fit to and generalize poorly, so the
experiment scores on targets that no method was fit to. Two split strategies:

* :func:`split_targets` -- a deterministic random split of any ``TargetSet``.
* :func:`split_registry_by_family` -- hold out whole target families (e.g. score
  on ``jct`` tax-expenditure targets that calibration never fit), which is the
  more defensible out-of-sample test for the paper.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from populace.calibrate import TargetRegistry
from populace.calibrate.target import Target, TargetSet


def split_targets(
    targets: Iterable[Target], *, holdout_frac: float = 0.2, seed: int = 0
) -> tuple[TargetSet, TargetSet]:
    """Randomly split ``targets`` into ``(fit, holdout)`` by fraction."""
    items = list(targets)
    if not 0.0 <= holdout_frac < 1.0:
        raise ValueError(f"holdout_frac must be in [0, 1), got {holdout_frac}.")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(items))
    n_holdout = int(round(len(items) * holdout_frac))
    holdout_idx = set(order[:n_holdout].tolist())
    fit = [t for i, t in enumerate(items) if i not in holdout_idx]
    holdout = [t for i, t in enumerate(items) if i in holdout_idx]
    return TargetSet(fit), TargetSet(holdout)


def split_registry_by_family(
    registry: TargetRegistry,
    *,
    holdout_families: Iterable[str],
    extra_holdout_frac: float = 0.0,
    seed: int = 0,
) -> tuple[TargetSet, TargetSet]:
    """Hold out whole families, optionally plus a random fraction of the rest."""
    families = set(holdout_families)
    targets = list(registry.to_target_set())
    specs = registry.specs

    fit: list[Target] = []
    holdout: list[Target] = []
    for spec, target in zip(specs, targets, strict=True):
        (holdout if spec.family in families else fit).append(target)

    if extra_holdout_frac > 0.0 and fit:
        fit_set, extra = split_targets(fit, holdout_frac=extra_holdout_frac, seed=seed)
        fit = list(fit_set)
        holdout.extend(extra)
    return TargetSet(fit), TargetSet(holdout)
