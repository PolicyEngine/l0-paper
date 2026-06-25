"""End-to-end smoke of the experiment pipeline on the toy frame.

Guards the path the paper actually runs -- the three sampling arms, the
long-format CSV, the per-target diagnostics store, the cap-parameterized crunch,
and the figure/table renderers -- so a refactor that breaks "run the experiment
and draw the figures" fails CI rather than silently rotting. It composes the same
package functions ``run_sweep.py`` drives (the CLI itself needs a real
pre-calibration artifact), and stays on the toy frame so it needs no network,
no PolicyEngine-US, and no restricted data.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from l0_paper.experiments import aggregate, crunch, holdout, metrics, target_loss
from l0_paper.experiments.conditions import (
    run_dense_then_sample,
    run_l0,
    run_l1,
    run_random_then_reweight,
)
from l0_paper.populace_smoke import make_toy_frame, make_toy_targets
from populace.calibrate import Target, TargetSet

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _toy_targets(truths: dict[str, float]) -> TargetSet:
    """Enrich the 3 toy measures into 12 consistent (same-valued) targets."""
    base = list(make_toy_targets(truths))
    many = [
        Target(name=f"{t.row_name}_{k}", entity=t.entity, measure=t.measure, value=t.value)
        for t in base
        for k in range(4)
    ]
    return TargetSet(tuple(many))


def _run_sweep(out_dir: Path) -> tuple[Path, Path]:
    """Run the three arms over a tiny budget x seed grid; write the two CSVs."""
    frame, truths = make_toy_frame(seed=0, n=300)
    fit, held = holdout.split_targets(_toy_targets(truths), holdout_frac=0.34, seed=1)
    fit, held = TargetSet(tuple(fit)), TargetSet(tuple(held))
    held_omega = target_loss.target_loss_weights(held, weighting=target_loss.UNIFORM)

    rows: list[dict] = []
    diag_rows: list[dict] = []
    for budget in (40, 80):
        for seed in (0, 1):
            l0 = run_l0(frame, fit, target_records=budget, seed=seed, epochs=60, learning_rate=0.15)
            l1 = run_l1(
                frame, fit, target_records=l0.n_selected, seed=seed,
                epochs=60, learning_rate=0.15, budget_iters=5,
            )
            dense = run_dense_then_sample(
                frame, fit, n_sample=l0.n_selected, seed=seed, epochs=60, learning_rate=0.15
            )
            rnd = run_random_then_reweight(
                frame, fit, n_sample=l0.n_selected, seed=seed, epochs=60, learning_rate=0.15
            )
            for run in (l0, l1, dense, rnd):
                in_sample = metrics.score(frame, run.weights, fit, label="in_sample")
                out_of_sample = metrics.score(frame, run.weights, held, label="out_of_sample")
                rows.extend(
                    aggregate.rows_from_run(
                        method=run.method, seed=seed, budget_requested=budget,
                        budget_achieved=run.n_selected, l2_lambda=0.0,
                        holdout_type="fixed_family", fold=0,
                        in_sample=in_sample, out_of_sample=out_of_sample, run=run,
                    )
                )
                diag = metrics.target_diagnostics(
                    frame, run.weights, held, loss_weights=held_omega
                )
                diag_rows.extend(
                    aggregate.target_diagnostic_rows(
                        method=run.method, seed=seed, budget_requested=budget,
                        split="out_of_sample", diagnostics=diag,
                    )
                )
    long_csv = aggregate.write_long_csv(out_dir / "metrics_long.csv", rows)
    diag_csv = aggregate.write_target_diagnostics_csv(
        out_dir / "target_diagnostics_long.csv", diag_rows
    )
    return long_csv, diag_csv


def test_sweep_arms_and_crunch_end_to_end(tmp_path):
    """The three arms run, the long CSV carries runtime per arm, and the objective
    crunches to a finite value at any cap from the per-target store."""
    long_csv, diag_csv = _run_sweep(tmp_path)

    long_df = aggregate.load_long(long_csv)
    assert set(long_df["method"]) == {"informed_l0", "informed_l1", "dense_sample", "random_reweight"}
    # runtime is tracked per arm (the cost-vs-accuracy axis), one tidy row per run.
    runtime = long_df[long_df["metric"] == "runtime_s"]
    assert set(runtime["method"]) == {"informed_l0", "informed_l1", "dense_sample", "random_reweight"}
    assert (runtime["value"] >= 0).all()

    diag = aggregate.load_target_diagnostics(diag_csv)
    for cap in (1.0, 10.0, None):
        summary = crunch.summarize(diag, cap=cap)
        assert len(summary) > 0
        obj = summary["objective_capped_weighted"].to_numpy(dtype=float)
        assert np.all(np.isfinite(obj)), f"objective must be finite at cap={cap}"
        assert np.all(obj >= 0.0)
    # capping can only lower (or hold) the objective relative to uncapped.
    capped = crunch.summarize(diag, cap=1.0).set_index("method")["objective_capped_weighted"]
    uncapped = crunch.summarize(diag, cap=None).set_index("method")["objective_capped_weighted"]
    assert (capped <= uncapped + 1e-9).all()


def test_figures_render_end_to_end(tmp_path):
    """The figure/table renderers consume the long CSV and emit the frontier set."""
    pytest.importorskip("matplotlib")
    long_csv, _ = _run_sweep(tmp_path)

    spec = importlib.util.spec_from_file_location(
        "_figures_e2e", _REPO_ROOT / "experiments" / "figures.py"
    )
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)

    report = figures.write_reports(long_csv, tmp_path / "report", anchor_budget=80)
    figure_paths = figures.write_figures(report, tmp_path / "report")
    names = {Path(p).name for p in figure_paths}
    assert {"f1_frontier.png", "f3_generalization_gap.png"} <= names
