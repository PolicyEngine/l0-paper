"""End-to-end smoke of the experiment pipeline on the toy frame.

Guards the path the paper runs -- the four sampling arms, the long-format CSV, the
per-target store, the cap-parameterized crunch, and the figure renderers -- through
the shared ``l0 demo`` pipeline, so a refactor that breaks "run the experiment and
draw the figures" fails CI. Stays on the toy frame: no network, no PolicyEngine-US,
no real data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from l0_paper.cli import _COMMANDS, paper, sweep
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


def test_paper_command_is_registered_with_manuscript_defaults():
    args = paper._parse_args([])

    assert "paper" in _COMMANDS
    assert args.budgets == [2000, 5000, 10000, 20000, 40000]
    assert args.seeds == [0, 1, 2]
    assert args.target_loss_cap == 10.0
    assert args.methods == ["informed_l0", "random_reweight", "dense_sample"]
    assert args.l2_lambdas == [0.0, 1e-4]
    assert args.holdout_families == ["cms_medicaid", "usda_snap", "state_income_tax"]
    assert args.jobs == 1
    assert args.pdf_builder == "quarto"
    assert args.resume is True
    assert args.smoke is False


def test_paper_smoke_preset_is_small_and_resumable():
    args = paper._parse_args(["--smoke"])

    assert args.out == paper.SMOKE_OUT
    assert args.run_id == paper.SMOKE_RUN_ID
    assert args.budgets == [2000]
    assert args.seeds == [0]
    assert args.epochs == 50
    assert args.budget_iters == 1
    assert args.l2_lambdas == [0.0]
    assert args.rotation_folds == 1
    assert args.skip_figures is True
    assert args.resume is True


def test_paper_smoke_respects_explicit_out_and_run_id(tmp_path):
    out = tmp_path / "custom-smoke"
    args = paper._parse_args(
        ["--smoke", "--out", str(out), "--run-id", "custom-smoke"]
    )

    assert args.out == out
    assert args.run_id == "custom-smoke"


def test_paper_command_fails_early_when_artifacts_are_missing(tmp_path):
    missing = tmp_path / "missing.jsonl"
    out = tmp_path / "run"

    with pytest.raises(SystemExit) as exc:
        paper.main(["--out", str(out), "--consumer-facts", str(missing)])

    assert "consumer facts not found" in str(exc.value)
    assert "--reuse-precalibration" in str(exc.value)
    assert not out.exists()


def test_paper_sweep_args_forward_entity_and_manuscript_defaults(monkeypatch, tmp_path):
    captured: dict[str, list[str]] = {}

    def fake_call_cli(label, _main, args):
        captured[label] = [str(arg) for arg in args]

    monkeypatch.setattr(paper, "_call_cli", fake_call_cli)
    args = paper._parse_args(["--out", str(tmp_path / "run"), "--weight-entity", "tax_unit"])

    paper._run_sweep(args, tmp_path / "precalibration")
    sweep_args = captured["l0 sweep"]

    assert sweep_args[sweep_args.index("--weight-entity") + 1] == "tax_unit"
    assert sweep_args[sweep_args.index("--rotation-budget") + 1] == "10000"
    assert sweep_args[sweep_args.index("--target-loss-cap") + 1] == "10.0"
    assert sweep_args[sweep_args.index("--jobs") + 1] == "1"
    assert "--resume" in sweep_args
    assert sweep_args[sweep_args.index("--methods") + 1:] == [
        "informed_l0",
        "random_reweight",
        "dense_sample",
    ]


def test_paper_sweep_args_can_disable_resume(monkeypatch, tmp_path):
    captured: dict[str, list[str]] = {}

    def fake_call_cli(label, _main, args):
        captured[label] = [str(arg) for arg in args]

    monkeypatch.setattr(paper, "_call_cli", fake_call_cli)
    args = paper._parse_args(["--out", str(tmp_path / "run"), "--no-resume"])

    paper._run_sweep(args, tmp_path / "precalibration")

    assert "--no-resume" in captured["l0 sweep"]
    assert "--resume" not in captured["l0 sweep"]


def test_paper_sweep_args_forward_jobs(monkeypatch, tmp_path):
    captured: dict[str, list[str]] = {}

    def fake_call_cli(label, _main, args):
        captured[label] = [str(arg) for arg in args]

    monkeypatch.setattr(paper, "_call_cli", fake_call_cli)
    args = paper._parse_args(["--out", str(tmp_path / "run"), "--jobs", "4"])

    paper._run_sweep(args, tmp_path / "precalibration")

    sweep_args = captured["l0 sweep"]
    assert sweep_args[sweep_args.index("--jobs") + 1] == "4"


def test_sweep_completed_cell_keys_require_all_requested_methods():
    base = {
        "seed": "0",
        "budget_requested": "2000",
        "l2_lambda": "0.0",
        "holdout_type": "fixed_family",
        "fold": "-1",
        "split": "na",
        "scope": "run",
        "scope_value": "",
        "metric": "budget_achieved",
        "value": "1928.0",
    }
    rows = [
        {**base, "method": "informed_l0"},
        {**base, "method": "random_reweight"},
        {**base, "method": "dense_sample", "metric": "runtime_s"},
    ]
    key = sweep._cell_key(
        holdout_type="fixed_family",
        fold=-1,
        seed=0,
        budget=2000,
        l2_lambda=0.0,
    )

    assert key in sweep._completed_cell_keys(
        rows, ["informed_l0", "random_reweight"]
    )
    assert key not in sweep._completed_cell_keys(
        rows, ["informed_l0", "random_reweight", "dense_sample"]
    )


def test_sweep_resume_tracks_completed_methods_and_achieved_budget():
    row = {
        "method": "informed_l0",
        "seed": "0",
        "budget_requested": "2000",
        "budget_achieved": "1928",
        "l2_lambda": "0.0",
        "holdout_type": "fixed_family",
        "fold": "-1",
        "split": "na",
        "scope": "run",
        "scope_value": "",
        "metric": "budget_achieved",
        "value": "1928.0",
    }
    l0_key = sweep._method_key(
        holdout_type="fixed_family",
        fold=-1,
        seed=0,
        budget=2000,
        l2_lambda=0.0,
        method="informed_l0",
    )
    random_key = sweep._method_key(
        holdout_type="fixed_family",
        fold=-1,
        seed=0,
        budget=2000,
        l2_lambda=0.0,
        method="random_reweight",
    )

    completed = sweep._completed_method_keys([row])

    assert l0_key in completed
    assert random_key not in completed
    assert sweep._budget_achieved_by_method([row])[l0_key] == 1928
    assert not sweep._completed_cells_from_methods(
        completed, ["informed_l0", "random_reweight"]
    )


def test_sweep_resume_rejects_checkpoint_row_count_mismatch(tmp_path):
    metrics = tmp_path / "metrics_long.csv"
    diagnostics = tmp_path / "target_diagnostics_long.csv"
    manifest = tmp_path / "sweep_manifest.json"

    with pytest.raises(SystemExit, match="incomplete checkpoint"):
        sweep._validate_resume_checkpoint(
            manifest={"n_rows": 2, "n_target_diagnostic_rows": 0},
            rows=[{"method": "informed_l0"}],
            diag_rows=[],
            metrics_path=metrics,
            diagnostics_path=diagnostics,
            manifest_path=manifest,
        )


def test_sweep_resume_rejects_diagnostics_without_manifest(tmp_path):
    metrics = tmp_path / "metrics_long.csv"
    diagnostics = tmp_path / "target_diagnostics_long.csv"
    manifest = tmp_path / "sweep_manifest.json"

    with pytest.raises(SystemExit, match="manifest"):
        sweep._validate_resume_checkpoint(
            manifest={},
            rows=[],
            diag_rows=[{"method": "informed_l0"}],
            metrics_path=metrics,
            diagnostics_path=diagnostics,
            manifest_path=manifest,
        )


def test_sweep_method_expansion_reuses_existing_l0_budget(monkeypatch):
    rows = [
        {
            "method": "informed_l0",
            "seed": "0",
            "budget_requested": "2000",
            "budget_achieved": "1928",
            "l2_lambda": "0.0",
            "holdout_type": "fixed_family",
            "fold": "-1",
            "split": "na",
            "scope": "run",
            "scope_value": "",
            "metric": "budget_achieved",
            "value": "1928.0",
        }
    ]
    completed = sweep._completed_method_keys(rows)
    achieved = sweep._budget_achieved_by_method(rows)
    random_calls: list[int] = []

    monkeypatch.setattr(
        sweep.metrics,
        "degenerate_target_names",
        lambda *_args, **_kwargs: set(),
    )
    monkeypatch.setattr(
        sweep.target_loss,
        "target_loss_weights",
        lambda *_args, **_kwargs: np.asarray([1.0]),
    )
    monkeypatch.setattr(
        sweep,
        "run_l0",
        lambda *_args, **_kwargs: pytest.fail("completed L0 should not rerun"),
    )

    def fake_random(*_args, n_sample, seed, **_kwargs):
        random_calls.append(n_sample)
        return SimpleNamespace(
            method="random_reweight",
            n_selected=n_sample,
            weights=np.ones(2),
        )

    def fake_score_and_emit(rows, *, run, method, seed, budget_requested, **_kwargs):
        rows.append(
            {
                "method": method,
                "seed": seed,
                "budget_requested": budget_requested,
                "budget_achieved": run.n_selected,
                "l2_lambda": 0.0,
                "holdout_type": "fixed_family",
                "fold": -1,
                "split": "na",
                "scope": "run",
                "scope_value": "",
                "metric": "budget_achieved",
                "value": float(run.n_selected),
            }
        )

    monkeypatch.setattr(sweep, "run_random_then_reweight", fake_random)
    monkeypatch.setattr(sweep, "_score_and_emit", fake_score_and_emit)

    sweep._sweep_split(
        rows,
        frame=SimpleNamespace(),
        fit_targets=(),
        holdout_targets=(),
        budgets=[2000],
        seeds=[0],
        l0_optimizer={"weight_entity": "household"},
        baseline_optimizer={"weight_entity": "household"},
        sample_kwargs={},
        holdout_type="fixed_family",
        fold=-1,
        methods=["informed_l0", "random_reweight"],
        l2_lambda=0.0,
        target_loss_weighting="uniform",
        completed_methods=completed,
        budget_achieved_by_method=achieved,
    )

    assert random_calls == [1928]
    assert [row["method"] for row in rows].count("informed_l0") == 1
    assert any(row["method"] == "random_reweight" for row in rows)


def test_parallel_sweep_split_merges_worker_rows_in_parent(monkeypatch, tmp_path):
    def fake_sweep_split(rows, *, seeds, diag_rows, checkpoint, **_kwargs):
        assert len(seeds) == 1
        seed = seeds[0]
        rows.append(
            {
                "method": "informed_l0",
                "seed": seed,
                "budget_requested": 2000,
                "budget_achieved": 1900 + seed,
                "l2_lambda": 0.0,
                "holdout_type": "fixed_family",
                "fold": -1,
                "split": "na",
                "scope": "run",
                "scope_value": "",
                "metric": "budget_achieved",
                "value": float(1900 + seed),
            }
        )
        if diag_rows is not None:
            diag_rows.append(
                {
                    "method": "informed_l0",
                    "l2_lambda": 0.0,
                    "seed": seed,
                    "budget_requested": 2000,
                    "split": "out_of_sample",
                    "target_name": f"target-{seed}",
                    "family": "demo",
                    "geography_level": "national",
                    "target_value": 1.0,
                    "achieved_value": 1.0,
                    "scale": 1.0,
                    "loss_weight": 1.0,
                    "absolute_relative_error": 0.0,
                    "is_degenerate": False,
                }
            )
        if checkpoint is not None:
            checkpoint(f"seed {seed} budget 2000")
        return {str(seed): float(seed + 0.5)}

    monkeypatch.setattr(sweep, "_sweep_split", fake_sweep_split)
    rows: list[dict] = []
    diag_rows: list[dict] = []
    completed: set[sweep.MethodKey] = set()
    achieved: dict[sweep.MethodKey, int] = {}
    checkpoints: list[str] = []
    shard_root = tmp_path / "shards"

    dense = sweep._run_sweep_split(
        rows,
        frame=SimpleNamespace(),
        fit_targets=(),
        holdout_targets=(),
        budgets=[2000],
        seeds=[0, 1],
        l0_optimizer={},
        baseline_optimizer={},
        sample_kwargs={},
        holdout_type="fixed_family",
        fold=-1,
        methods=["informed_l0"],
        l2_lambda=0.0,
        target_loss_weighting="uniform",
        jobs=2,
        diag_rows=diag_rows,
        completed_methods=completed,
        budget_achieved_by_method=achieved,
        shard_checkpoint_root=shard_root,
        checkpoint=checkpoints.append,
    )

    assert sorted(row["seed"] for row in rows) == [0, 1]
    assert sorted(row["target_name"] for row in diag_rows) == [
        "target-0",
        "target-1",
    ]
    assert dense == {"0": 0.5, "1": 1.5}
    assert sorted(key[2] for key in completed) == [0, 1]
    assert sorted(achieved.values()) == [1900, 1901]
    assert len(checkpoints) == 2

    recovered_rows: list[dict] = []
    recovered_diag_rows: list[dict] = []
    shards, n_rows, n_diag_rows = sweep._merge_shard_checkpoints(
        recovered_rows, recovered_diag_rows, shard_root
    )

    assert shards == 2
    assert n_rows == 2
    assert n_diag_rows == 2
    assert sorted(int(row["seed"]) for row in recovered_rows) == [0, 1]
    assert sorted(row["target_name"] for row in recovered_diag_rows) == [
        "target-0",
        "target-1",
    ]


def test_sweep_l0_budget_progress_logger_reports_iteration_results(capsys):
    logger = sweep._l0_budget_progress_logger(
        holdout_type="fixed_family",
        fold=-1,
        seed=0,
        budget=2000,
        l2_lambda=0.0,
        started_at=0.0,
    )

    logger(
        {
            "budget_search": True,
            "budget_iteration": 1,
            "budget_iters": 8,
            "l0_lambda": 1e-3,
            "epoch": 1,
            "epochs": 2,
            "loss": 4.2,
        }
    )
    logger(
        {
            "budget_search": True,
            "budget_iteration": 1,
            "budget_iters": 8,
            "l0_lambda": 1e-3,
            "epoch": 2,
            "epochs": 2,
            "loss": 3.5,
        }
    )
    logger({"kind": "calibration_epoch", "epoch": 1, "epochs": 1, "loss": 99.0})

    out = capsys.readouterr().out
    assert "L0 budget iter 1/8" in out
    assert "lambda=1.000e-03 started" in out
    assert "loss=3.5" in out
    assert "99" not in out


def test_paper_implicit_precalibration_reuse_validates_manifest(tmp_path):
    facts = tmp_path / "consumer_facts.jsonl"
    facts.write_text('{"aggregate_fact_key": "x"}\n')
    out = tmp_path / "run"
    precalibration = out / "precalibration"
    precalibration.mkdir(parents=True)
    manifest = {
        "period": 2024,
        "weight_entity": "household",
        "reset_weights": "uniform",
        "subsample": None,
        "subsample_seed": None,
        "allow_partial_facts": False,
        "drop_unsupported_filters": True,
        "ledger_facts_sha256": paper._sha256(facts),
        "base_h5_sha256": paper.PAPER_BASE_H5_SHA256,
    }
    (precalibration / paper.MANIFEST_JSON).write_text(json.dumps(manifest))
    args = paper._parse_args(["--out", str(out), "--consumer-facts", str(facts)])

    assert paper._prepare_precalibration(args, facts) == precalibration

    manifest["base_h5_sha256"] = "0" * 64
    (precalibration / paper.MANIFEST_JSON).write_text(json.dumps(manifest))
    with pytest.raises(SystemExit) as exc:
        paper._prepare_precalibration(args, facts)

    assert "base_h5_sha256" in str(exc.value)

    manifest["base_h5_sha256"] = paper.PAPER_BASE_H5_SHA256
    (precalibration / paper.MANIFEST_JSON).write_text(json.dumps(manifest))
    args.weight_entity = "tax_unit"
    with pytest.raises(SystemExit) as exc:
        paper._prepare_precalibration(args, facts)

    assert "does not match this run" in str(exc.value)
    assert "weight_entity" in str(exc.value)


def test_paper_base_h5_uses_pinned_snapshot_and_validates_hash(monkeypatch, tmp_path):
    base_h5 = tmp_path / "populace_us_2024.h5"
    base_h5.write_text("base frame placeholder")
    calls = {}

    def fake_hf_hub_download(**kwargs):
        calls.update(kwargs)
        return str(base_h5)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=fake_hf_hub_download),
    )
    monkeypatch.setattr(paper, "PAPER_BASE_H5_SHA256", paper._sha256(base_h5))
    args = paper._parse_args([])

    assert paper._base_h5_for_build(args) == base_h5
    assert calls == {
        "repo_id": paper.PAPER_BASE_REPO_ID,
        "filename": paper.PAPER_BASE_FILENAME,
        "repo_type": "dataset",
        "revision": paper.PAPER_BASE_REVISION,
    }

    monkeypatch.setattr(paper, "PAPER_BASE_H5_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="base frame hash mismatch"):
        paper._base_h5_for_build(args)
