"""Small Populace-backed calibration scenario used by repo tests.

This module intentionally exercises the active Populace API surface used by
the paper experiments: a :class:`populace.frame.Frame`, a declarative
``TargetSet``, and ``calibrate(..., target_records=...)`` for L0/Hard Concrete
budget control.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from populace.calibrate import Target, TargetSet, calibrate
from populace.frame import EntitySchema, Frame, WeightKind, Weights


@dataclass(frozen=True)
class SmokeCalibration:
    """Summary of a tiny L0 calibration run."""

    initial_loss: float
    final_loss: float
    n_records: int
    n_nonzero: int
    l0_lambda: float


def make_toy_frame(seed: int = 0, n: int = 120) -> tuple[Frame, dict[str, float]]:
    """Build a deterministic one-person-per-household Populace frame."""
    rng = np.random.default_rng(seed)
    income = rng.lognormal(10.4, 0.55, n)
    is_renter = (rng.random(n) < 0.35).astype(float)
    household_id = np.arange(n, dtype=np.int64)
    weights = np.full(n, 1_000.0)

    household = pd.DataFrame(
        {
            "household_id": household_id,
            "income": income,
            "is_renter": is_renter,
        }
    )
    person = pd.DataFrame(
        {
            "person_id": household_id,
            "person_household_id": household_id,
        }
    )
    frame = Frame(
        {"person": person, "household": household},
        EntitySchema(group_entities=("household",)),
        {"household": Weights(values=weights, kind=WeightKind.DESIGN)},
    )
    truths = {
        "households": float(weights.sum()),
        "income": float(np.dot(income, weights)),
        "renters": float(np.dot(is_renter, weights)),
    }
    return frame, truths


def make_toy_targets(truths: dict[str, float]) -> TargetSet:
    """Targets with a common scale shift so a calibration can improve all rows."""
    scale = 1.08
    return TargetSet(
        (
            Target(
                name="households",
                entity="household",
                aggregation="count",
                value=truths["households"] * scale,
            ),
            Target(
                name="income",
                entity="household",
                aggregation="sum",
                measure="income",
                value=truths["income"] * scale,
            ),
            Target(
                name="renters",
                entity="household",
                aggregation="sum",
                measure="is_renter",
                value=truths["renters"] * scale,
            ),
        )
    )


def run_l0_smoke(
    *,
    seed: int = 0,
    n: int = 120,
    target_records: int = 60,
    epochs: int = 120,
) -> SmokeCalibration:
    """Run a tiny Populace L0 calibration and return a stable summary."""
    frame, truths = make_toy_frame(seed=seed, n=n)
    result = calibrate(
        frame,
        make_toy_targets(truths),
        weight_entity="household",
        epochs=epochs,
        learning_rate=0.15,
        target_records=target_records,
        seed=seed,
    )
    return SmokeCalibration(
        initial_loss=result.initial_loss,
        final_loss=result.final_loss,
        n_records=n,
        n_nonzero=result.n_nonzero,
        l0_lambda=result.l0_lambda,
    )
