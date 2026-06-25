"""End-to-end smoke of the experiment pipeline on the toy frame.

Guards the path the paper runs -- the four sampling arms, the long-format CSV, the
per-target store, the cap-parameterized crunch, and the figure renderers -- through
the shared ``l0 demo`` pipeline, so a refactor that breaks "run the experiment and
draw the figures" fails CI. Stays on the toy frame: no network, no PolicyEngine-US,
no real data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from l0_paper.cli import _COMMANDS, paper
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
    assert args.pdf_builder == "quarto"


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
    assert sweep_args[sweep_args.index("--methods") + 1:] == [
        "informed_l0",
        "random_reweight",
        "dense_sample",
    ]


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
    }
    (precalibration / paper.MANIFEST_JSON).write_text(json.dumps(manifest))
    args = paper._parse_args(["--out", str(out), "--consumer-facts", str(facts)])

    assert paper._prepare_precalibration(args, facts) == precalibration

    args.weight_entity = "tax_unit"
    with pytest.raises(SystemExit) as exc:
        paper._prepare_precalibration(args, facts)

    assert "does not match this run" in str(exc.value)
    assert "weight_entity" in str(exc.value)
