"""End-to-end smoke of the experiment pipeline on the toy frame.

Guards the path the paper runs -- the four sampling arms, the long-format CSV, the
per-target store, the cap-parameterized crunch, and the figure renderers -- through
the shared ``l0 demo`` pipeline, so a refactor that breaks "run the experiment and
draw the figures" fails CI. Stays on the toy frame: no network, no PolicyEngine-US,
no restricted data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from l0_paper.cli.demo import run_demo
from l0_paper.experiments import aggregate, crunch

ARMS = {"informed_l0", "informed_l1", "dense_sample", "random_reweight"}


def test_demo_runs_all_arms_with_runtime_and_finite_objective(tmp_path):
    """All four arms run, each carries a runtime, and the objective is finite at any cap."""
    result = run_demo(tmp_path, budgets=(40, 80), seeds=(0,), epochs=50, with_figures=False)

    long_df = aggregate.load_long(result["long_csv"])
    assert set(long_df["method"]) == ARMS
    runtime = long_df[long_df["metric"] == "runtime_s"]
    assert set(runtime["method"]) == ARMS
    assert (runtime["value"] >= 0).all()

    diag = aggregate.load_target_diagnostics(result["diag_csv"])
    for cap in (1.0, 10.0, None):
        obj = crunch.summarize(diag, cap=cap)["objective_capped_weighted"].to_numpy(dtype=float)
        assert np.all(np.isfinite(obj)), f"objective must be finite at cap={cap}"
        assert np.all(obj >= 0.0)
    capped = crunch.summarize(diag, cap=1.0).set_index("method")["objective_capped_weighted"]
    uncapped = crunch.summarize(diag, cap=None).set_index("method")["objective_capped_weighted"]
    assert (capped <= uncapped + 1e-9).all()


def test_demo_renders_figures(tmp_path):
    """The figure renderers consume the run and emit the frontier set."""
    pytest.importorskip("matplotlib")
    result = run_demo(tmp_path, budgets=(40, 80), seeds=(0,), epochs=50, with_figures=True)
    names = {Path(p).name for p in result["figures"]}
    assert {"f1_frontier.png", "f3_generalization_gap.png"} <= names
