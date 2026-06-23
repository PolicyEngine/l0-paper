"""Target-loss weighting options for the experiment harness.

The paper experiments default to the historical uniform target-row loss, but can
opt into Populace's current US fiscal production weighting. Until Populace
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

from populace.calibrate.target import TargetSet

UNIFORM = "uniform"
PRODUCTION_US_FISCAL = "production_us_fiscal"
TARGET_LOSS_WEIGHTINGS = (UNIFORM, PRODUCTION_US_FISCAL)

DEFAULT_TARGET_LOSS_CAP = 10.0


def resolve_target_loss_cap(weighting: str, cap: float | None) -> float:
    """Return the effective cap for a target-loss weighting scheme."""
    if cap is not None:
        resolved = float(cap)
    elif weighting in TARGET_LOSS_WEIGHTINGS:
        resolved = DEFAULT_TARGET_LOSS_CAP
    else:
        raise ValueError(f"Unknown target-loss weighting {weighting!r}.")
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"target_loss_cap must be positive and finite, got {cap!r}.")
    return resolved


def target_loss_weights(targets: TargetSet, *, weighting: str) -> np.ndarray | None:
    """Return target-row loss weights aligned to ``targets`` or ``None``."""
    if weighting == UNIFORM:
        return None
    if weighting != PRODUCTION_US_FISCAL:
        raise ValueError(f"Unknown target-loss weighting {weighting!r}.")

    # Populace's private helper only reads ``registry.specs`` and, for each spec,
    # ``value`` and ``metadata``. A TargetSet carries those fields in the same
    # order passed to calibrate, so this shim preserves exact row alignment while
    # avoiding a lossy TargetSet -> TargetRegistry reconstruction.
    registry_like = SimpleNamespace(specs=tuple(targets))
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
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root.parent / "populace" / "tools" / "build_us_fiscal_refresh_release.py"
    if not path.is_file():
        raise FileNotFoundError(
            "Populace production target-loss helper not found at "
            f"{path}. Run from the sibling l0-paper-expanded/populace checkout "
            "layout or expose the helper from Populace before using "
            f"{PRODUCTION_US_FISCAL!r}."
        )
    return path
