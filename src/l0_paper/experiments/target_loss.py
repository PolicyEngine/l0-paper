"""Target-loss weighting options for the experiment harness.

The paper experiments default to Populace's current US fiscal production
weighting, while retaining the historical uniform target-row loss as an explicit
contrast. Until Populace
exposes that helper from a public package module, this file imports the private
release-builder implementation so the experiment uses the same code path as
production rather than a local reimplementation.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from l0_paper._populace_driver import _DRIVER_RELPATH, _populace_repo_root
from populace.calibrate.target import TargetSet

UNIFORM = "uniform"
PRODUCTION_US_FISCAL = "production_us_fiscal"
TARGET_LOSS_WEIGHTINGS = (UNIFORM, PRODUCTION_US_FISCAL)

#: Generic solver fallback cap (Populace's ``_DEFAULT_TARGET_LOSS_CAP``); the cap
#: for the uniform-weighting baseline.
DEFAULT_TARGET_LOSS_CAP = 10.0
#: Production US-fiscal cap, mirroring ``US_FISCAL_TARGET_LOSS_CAP`` in Populace's
#: ``tools/build_us_fiscal_refresh_release.py`` so the production weighting inherits
#: the production cap rather than the generic 10.0.
PRODUCTION_US_FISCAL_TARGET_LOSS_CAP = 1.0

#: Default target-loss cap per weighting when none is passed explicitly.
_DEFAULT_TARGET_LOSS_CAP_BY_WEIGHTING = {
    UNIFORM: DEFAULT_TARGET_LOSS_CAP,
    PRODUCTION_US_FISCAL: PRODUCTION_US_FISCAL_TARGET_LOSS_CAP,
}


def resolve_target_loss_cap(weighting: str, cap: float | None) -> float:
    """Return the effective cap for a target-loss weighting scheme.

    An explicit ``cap`` always wins. Otherwise the default is per weighting:
    ``production_us_fiscal`` inherits the production cap (1.0); ``uniform`` keeps the
    generic solver default (10.0).
    """
    if cap is not None:
        resolved = float(cap)
    elif weighting in _DEFAULT_TARGET_LOSS_CAP_BY_WEIGHTING:
        resolved = _DEFAULT_TARGET_LOSS_CAP_BY_WEIGHTING[weighting]
    else:
        raise ValueError(f"Unknown target-loss weighting {weighting!r}.")
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"target_loss_cap must be positive and finite, got {cap!r}.")
    return resolved


def _spec_family(target: Any) -> str:
    """Family of a target, matching Populace's registry derivation.

    Populace's ``TargetRegistry`` derives a spec's ``family`` from the
    ``"<family>/..."`` name prefix (``calibrate/registry.py``); mirror that so the
    production loss-weighting helper, which keys per-concept budgets on
    ``spec.family``, sees the same value. Fall back to the full name when a target
    carries no prefix: the registry surface always prefixes, and bare-name targets
    appear only in tests, where each name is unique so the concept grouping is a
    no-op.
    """
    name = str(target.name)
    return name.split("/", 1)[0] if "/" in name else name


class _SpecView:
    """Read-only view of a :class:`Target` that also exposes ``family``.

    Populace's production weighting reads each spec's ``value``, ``metadata``,
    ``entity``, ``period``, ``filter``, ``name`` and ``family``. A ``TargetSet``
    yields ``Target``s, which carry every field but ``family`` (a registry-level
    attribute). This view delegates every attribute to the wrapped target and
    supplies ``family``, so it stays correct if the helper later reads another
    existing target field.
    """

    __slots__ = ("_target", "family")

    def __init__(self, target: Any) -> None:
        self._target = target
        self.family = _spec_family(target)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._target, attr)


def target_loss_weights(targets: TargetSet, *, weighting: str) -> np.ndarray | None:
    """Return target-row loss weights aligned to ``targets`` or ``None``."""
    if weighting == UNIFORM:
        return None
    if weighting != PRODUCTION_US_FISCAL:
        raise ValueError(f"Unknown target-loss weighting {weighting!r}.")

    # Populace's private helper reads ``registry.specs`` and a small spec-like
    # surface for each row. A TargetSet carries those fields in the same order
    # passed to calibrate; this shim preserves row alignment while avoiding a
    # lossy TargetSet -> TargetRegistry reconstruction.
    registry_like = SimpleNamespace(specs=tuple(_spec_like_targets(targets)))
    return np.asarray(
        _production_module()._fiscal_target_loss_weights(registry_like),
        dtype=np.float64,
    )


def target_loss_weight_summary(weights: np.ndarray | None) -> dict[str, Any]:
    """Small JSON-safe summary proving whether row weights were active."""
    if weights is None:
        return {"kind": "uniform"}
    arr = np.asarray(weights, dtype=np.float64)
    return {
        "kind": "provided",
        "n": int(arr.size),
        "sum": float(arr.sum()),
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def production_source_path() -> str:
    """Path of the private Populace module used for production weighting."""
    return str(_production_module_path())


@lru_cache(maxsize=1)
def _production_module():
    path = _production_module_path()
    spec = importlib.util.spec_from_file_location(
        "_populace_us_fiscal_refresh_private", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Populace production target-loss helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _production_module_path() -> Path:
    path = _populace_repo_root() / _DRIVER_RELPATH
    if not path.is_file():
        raise FileNotFoundError(
            "Populace production target-loss helper not found at "
            f"{path}. Set L0_PAPER_POPULACE_REPO or expose the helper from "
            f"Populace before using {PRODUCTION_US_FISCAL!r}."
        )
    return path


def _spec_like_targets(targets: TargetSet) -> tuple[SimpleNamespace, ...]:
    return tuple(_spec_like_target(target) for target in targets)


def _spec_like_target(target) -> SimpleNamespace:
    metadata = dict(target.metadata or {})
    return SimpleNamespace(
        name=target.name,
        entity=target.entity,
        measure=target.measure,
        value=target.value,
        period=target.period,
        tolerance=target.tolerance,
        filter=target.filter,
        source=target.source,
        metadata=metadata,
        family=_target_family(target, metadata),
    )


def _target_family(target, metadata: dict[str, str]) -> str:
    explicit = getattr(target, "family", None) or metadata.get("family")
    if explicit:
        return str(explicit)
    source_record_id = metadata.get("ledger_source_record_id")
    if source_record_id:
        source_record_id = str(source_record_id)
        for separator in (".", "/"):
            if separator in source_record_id:
                return source_record_id.split(separator, 1)[0]
        return source_record_id
    name = str(target.name)
    for separator in ("/", "."):
        if separator in name:
            return name.split(separator, 1)[0]
    return "unspecified"
