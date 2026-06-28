"""Split a target set into fit and out-of-sample (held-out) targets.

A sampler can match the targets it is fit to and generalize poorly, so the
experiment scores on targets that no method was fit to. Strategies, in order of
how defensible the out-of-sample claim is:

* :func:`split_targets` -- a deterministic random split of any ``TargetSet``.
  Targets within a source family are nested/correlated (a national total is the
  sum of its state cells), so a random split *leaks*: a held-out cell is nearly
  determined by its fit siblings. Fine for a quick toy check, not for the paper.
* :func:`split_registry_by_family` -- hold out whole families, so a family is
  entirely in-fit or entirely held out (no within-family leakage). One fixed
  split; the frontier sweep uses this.
* :func:`family_grouped_folds` -- rotated family-level holdout: deal whole
  families into ``n_folds`` balanced folds, so every family is held out exactly
  once across the rotation. Leak-free (like ``split_registry_by_family``) *and*
  immune to single-split luck / leaderboard overfitting. Used for the
  holdout-robustness panel at the anchor budget.

Validation-only families (Populace diagnostics, e.g. ``cbo``; see
:func:`validation_only_families`) are excluded from the fit by every strategy
that takes a registry.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace

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
    specs = registry.specs
    targets = _targets_with_registry_family(registry)
    available = {spec.family for spec in specs}
    unknown = sorted(families - available)
    if unknown:
        raise ValueError(
            "Unknown holdout family/families: "
            f"{unknown}. Available registry families: {sorted(available)}."
        )

    fit: list[Target] = []
    holdout: list[Target] = []
    for spec, target in zip(specs, targets, strict=True):
        (holdout if spec.family in families else fit).append(target)

    if extra_holdout_frac > 0.0 and fit:
        fit_set, extra = split_targets(fit, holdout_frac=extra_holdout_frac, seed=seed)
        fit = list(fit_set)
        holdout.extend(extra)
    return TargetSet(fit), TargetSet(holdout)


def deal_families_into_folds(
    family_of_target: Sequence[str],
    *,
    n_folds: int = 5,
    seed: int = 0,
    balance_by: str = "target_count",
) -> tuple[tuple[int, ...], ...]:
    """Deal whole families into ``n_folds`` folds; return per-fold target indices.

    ``family_of_target[i]`` is target ``i``'s family. Every family's targets land
    in exactly one fold, so a family is never split across folds -- this is what
    makes the holdout leak-free. The folds partition ``range(len(family_of_target))``.

    ``balance_by``:

    * ``"target_count"`` (default) -- greedy largest-family-first assignment to
      the least-full fold, so folds carry roughly equal *target* counts. With very
      unequal families (e.g. SOI has thousands of targets, Medicare one) this keeps
      each held-out fold a comparable fraction of the surface.
    * ``"family"`` -- round-robin over families, so folds carry roughly equal
      *family* counts (target counts may be very unequal).

    ``seed`` permutes the families first, so the rotation is reproducible but not
    tied to family name order; with ``balance_by="target_count"`` it only breaks
    ties between equal-sized families (the size ordering dominates).
    """
    indices_by_family: dict[str, list[int]] = {}
    for i, family in enumerate(family_of_target):
        indices_by_family.setdefault(family, []).append(i)
    families = list(indices_by_family)
    n_unique = len(families)
    if not (2 <= n_folds <= n_unique):
        raise ValueError(
            f"n_folds must be between 2 and the number of families={n_unique}, "
            f"got {n_folds!r}."
        )
    if balance_by not in ("target_count", "family"):
        raise ValueError(
            f"balance_by must be 'target_count' or 'family', got {balance_by!r}."
        )

    order = np.random.default_rng(seed).permutation(n_unique)
    families = [families[k] for k in order]

    fold_indices: list[list[int]] = [[] for _ in range(n_folds)]
    if balance_by == "family":
        for position, family in enumerate(families):
            fold_indices[position % n_folds].extend(indices_by_family[family])
    else:
        # Stable sort keeps the seeded order among equal-sized families.
        families.sort(key=lambda f: len(indices_by_family[f]), reverse=True)
        fold_load = [0] * n_folds
        for family in families:
            fold = min(range(n_folds), key=fold_load.__getitem__)
            fold_indices[fold].extend(indices_by_family[family])
            fold_load[fold] += len(indices_by_family[family])
    return tuple(tuple(sorted(idx)) for idx in fold_indices)


def family_grouped_folds(
    registry: TargetRegistry,
    *,
    n_folds: int = 5,
    seed: int = 0,
    balance_by: str = "target_count",
    exclude_validation_only: bool = True,
) -> list[tuple[TargetSet, TargetSet]]:
    """Rotated family-level holdout over a registry: ``(fit, holdout)`` per fold.

    Deals the registry's families into ``n_folds`` balanced folds with
    :func:`deal_families_into_folds`, then returns one ``(fit, holdout)`` pair per
    fold whose holdout is every target of the fold's families. Because whole
    families move together there is no within-family leakage, and across the
    ``n_folds`` pairs every (rotatable) family is held out exactly once.

    Validation-only families are added to *every* fold's holdout and never rotated
    into the fit (they are Populace diagnostics, not contemporaneous targets).
    """
    specs = registry.specs
    targets = _targets_with_registry_family(registry)
    families = [spec.family for spec in specs]

    validation_only = (
        validation_only_families(registry) if exclude_validation_only else set()
    )
    rotatable_positions = [i for i, fam in enumerate(families) if fam not in validation_only]
    validation_positions = {i for i, fam in enumerate(families) if fam in validation_only}

    folds = deal_families_into_folds(
        [families[i] for i in rotatable_positions],
        n_folds=n_folds,
        seed=seed,
        balance_by=balance_by,
    )

    result: list[tuple[TargetSet, TargetSet]] = []
    for fold in folds:
        holdout_positions = {rotatable_positions[j] for j in fold} | validation_positions
        fit = [t for i, t in enumerate(targets) if i not in holdout_positions]
        held = [targets[i] for i in sorted(holdout_positions)]
        result.append((TargetSet(fit), TargetSet(held)))
    return result


def _targets_with_registry_family(registry: TargetRegistry) -> list[Target]:
    """Return registry targets with their source family preserved in metadata."""
    return [
        _target_with_family_metadata(target, spec.family)
        for spec, target in zip(registry.specs, registry.to_target_set(), strict=True)
    ]


def _target_with_family_metadata(target: Target, family: str) -> Target:
    metadata = dict(target.metadata or {})
    metadata.setdefault("family", str(family))
    return replace(target, metadata=metadata)


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
    try:
        from populace.build.us.source_coverage import validation_only_family_ids
    except ModuleNotFoundError:
        from populace.build.us_runtime.source_coverage import validation_only_family_ids

    classified = set(validation_only_family_ids())
    families = {
        family
        for coverage_id, family in _VALIDATION_ONLY_COVERAGE_TO_FAMILY.items()
        if coverage_id in classified
    }
    if registry is not None:
        families &= {spec.family for spec in registry.specs}
    return families
