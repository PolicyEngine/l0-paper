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


# Populace marks sources "validation-only" in ``source_coverage.US_SOURCE_COVERAGE``
# (scored as diagnostics, not fit), but it keys that classification by *arch package
# alias* (e.g. ``cbo-revenue-projections-income-by-source-2026-02``) while the
# compiled registry labels targets by ``spec.family`` (a source domain, e.g.
# ``cbo``). Populace exposes no programmatic bridge between those two name spaces,
# so we translate here -- but only for coverage families that actually compile into
# registry targets, and the *authority* for what is validation-only stays in
# Populace (we gate on ``validation_only_family_ids()`` below).
#
# Map ONLY families that are entirely validation-only. The other validation-only
# coverage entries are deliberately omitted because they produce no registry
# targets and mapping them would be unsafe: ``snap_local_proxy`` (census ACS
# SNAP-by-district) shares the census-ACS source domain with the *hard-target* age
# distributions (registry family ``census_population``), so keying it by family
# could drop hard targets; ``wealth_balance_sheet`` (federal_reserve) and the
# package-less ``census_cps_spm`` / ``dina_distributional_accounts`` /
# ``acs_income_distribution`` simply never become targets.
_VALIDATION_ONLY_COVERAGE_TO_FAMILY: dict[str, str] = {
    "cbo_income_revenue_projection": "cbo",
}


def validation_only_families(registry: TargetRegistry | None = None) -> set[str]:
    """Return the registry families Populace classifies as validation-only.

    These should be **scored out-of-sample but never fit** (forecast/aging or
    survey-based diagnostics, not contemporaneous calibration targets). The set is
    gated by Populace's live ``validation_only_family_ids()`` -- this never returns
    a family Populace does not currently mark validation-only -- and, when
    ``registry`` is given, is intersected with the families actually present so
    phantom families are not passed downstream.
    """
    from populace.build.us.source_coverage import validation_only_family_ids

    classified = set(validation_only_family_ids())
    families = {
        family
        for coverage_id, family in _VALIDATION_ONLY_COVERAGE_TO_FAMILY.items()
        if coverage_id in classified
    }
    if registry is not None:
        families &= {spec.family for spec in registry.specs}
    return families
