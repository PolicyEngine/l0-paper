"""Offline end-to-end tests for the experiment harness.

These exercise both calibration conditions, scoring, holdout splitting, artifact
summaries, and table rendering on the toy Populace frame -- no PolicyEngine-US and
no network, so CI stays fast and self-contained. The real-data path is driven by
``experiments/run_poc.py``.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np

from l0_paper.experiments import artifacts, holdout, metrics, tables
from l0_paper.experiments.conditions import (
    run_dense_then_sample,
    run_l0,
    run_random_then_reweight,
    weighted_sample,
)
from l0_paper.populace_smoke import make_toy_frame, make_toy_targets
from populace.calibrate import Target, TargetSet


def _toy():
    frame, truths = make_toy_frame(seed=0, n=120)
    return frame, make_toy_targets(truths)


def test_split_targets_partitions():
    _, targets = _toy()
    fit, held = holdout.split_targets(targets, holdout_frac=0.34, seed=0)
    assert len(fit) + len(held) == len(targets)
    assert len(held) >= 1
    # Deterministic for a fixed seed.
    _, held2 = holdout.split_targets(targets, holdout_frac=0.34, seed=0)
    assert [t.name for t in held] == [t.name for t in held2]


def test_run_l0_prunes_at_budget():
    frame, targets = _toy()
    result = run_l0(
        frame, targets, target_records=60, seed=0, epochs=120,
        learning_rate=0.15, mass="free",
    )
    assert result.method == "informed_l0"
    assert result.n_selected < result.n_records
    assert result.l0_lambda > 0
    assert result.final_loss < result.initial_loss
    # l2_lambda is recorded for reporting even though Populace applies no L2 term.
    assert result.l2_lambda == 0.0
    assert hasattr(result, "max_weight_ratio")


def test_dense_then_sample_matched_budget():
    frame, targets = _toy()
    result = run_dense_then_sample(
        frame, targets, n_sample=40, seed=0, epochs=120,
        learning_rate=0.15, mass="free",
    )
    assert result.method == "dense_sample"
    assert result.l0_lambda == 0.0
    assert result.n_selected == 40  # distinct draws without replacement
    assert result.sampling["n_sample"] == 40


def test_run_random_then_reweight_matched_budget():
    frame, targets = _toy()
    result = run_random_then_reweight(
        frame, targets, n_sample=40, seed=0, epochs=120,
        learning_rate=0.15, mass="free",
    )
    assert result.method == "random_reweight"
    assert result.l0_lambda == 0.0
    assert result.n_records == 120
    assert result.weights.size == 120
    assert result.n_selected == 40  # uniform subset of distinct households
    assert result.sampling["strategy"] == "uniform_random"
    assert result.sampling["n_sample"] == 40


def test_random_reweight_fills_table_row():
    frame, targets = _toy()
    fit, held = holdout.split_targets(targets, holdout_frac=0.34, seed=1)
    run = run_random_then_reweight(
        frame, fit, n_sample=40, seed=0, epochs=80, learning_rate=0.15, mass="free",
    )
    summary = artifacts.method_summary(
        run,
        metrics.score(frame, run.weights, fit),
        metrics.score(frame, run.weights, held),
    )
    tex = tables.render_sampling_comparison({"random_reweight": summary}, budget=40)
    random_row = next(line for line in tex.splitlines() if line.startswith("Random + reweight"))
    assert "\\tbc" not in random_row


def test_weighted_sample_conserves_mass():
    weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    full = weighted_sample(weights, 3, seed=0)
    assert np.count_nonzero(full) == 3
    assert np.isclose(full.sum(), weights.sum())


def test_metrics_score_reports_are_and_weights():
    frame, targets = _toy()
    result = run_l0(
        frame, targets, target_records=60, seed=0, epochs=120,
        learning_rate=0.15, mass="free",
    )
    scored = metrics.score(frame, result.weights, targets, label="in_sample")
    assert scored["n_targets"] == len(targets)
    assert scored["ess"] > 0
    assert scored["max_weight"] > 0
    assert "national" in scored["by_geography"]
    assert scored["by_family"]  # toy targets group into at least one family
    assert scored["mean_are"] is not None


def test_zero_value_targets_report_absolute_error_not_are():
    frame, _targets = _toy()
    weights = frame.weights_for("household").values
    zero_target = Target(
        name="zero_renters",
        entity="household",
        aggregation="sum",
        measure="is_renter",
        value=0.0,
    )
    zero_targets = TargetSet((zero_target,))

    scored = metrics.score(frame, weights, zero_targets)
    rows = metrics.target_diagnostics(frame, weights, zero_targets)

    assert scored["n_zero_value_targets"] == 1
    assert scored["mean_are"] is None
    assert scored["zero_value_absolute_error"]["n"] == 1
    assert scored["zero_value_absolute_error"]["max_absolute_error"] > 0
    assert rows[0]["relative_error"] is None
    assert rows[0]["absolute_relative_error"] is None


def test_dense_sample_npz_uses_sampled_weight_diagnostics(tmp_path):
    frame, targets = _toy()
    fit, held = holdout.split_targets(targets, holdout_frac=0.34, seed=1)
    result = run_dense_then_sample(
        frame,
        fit,
        n_sample=20,
        seed=0,
        epochs=60,
        learning_rate=0.15,
        mass="free",
    )

    path = artifacts.save_method_npz(
        tmp_path / "dense_sample.npz",
        result,
        frame=frame,
        fit_targets=fit,
        holdout_targets=held,
    )

    expected_sampled = np.asarray(
        [target.achieved_value(frame, result.weights) for target in fit],
        dtype=np.float64,
    )
    dense_pre_sample = np.asarray(
        [
            target.achieved_value(frame, result.calibration_result.weights)
            for target in fit
        ],
        dtype=np.float64,
    )
    with np.load(path, allow_pickle=True) as payload:
        assert np.allclose(payload["fit_achieved_values"], expected_sampled)
        assert np.allclose(payload["final_estimates"], expected_sampled)
        assert not np.allclose(payload["fit_achieved_values"], dense_pre_sample)
        assert len(payload["holdout_target_names"]) == len(held)


def test_manifest_is_strict_json_with_empty_holdout(tmp_path):
    frame, targets = _toy()
    result = run_l0(
        frame,
        targets,
        target_records=60,
        seed=0,
        epochs=60,
        learning_rate=0.15,
        mass="free",
    )
    in_sample = metrics.score(frame, result.weights, targets)
    out_of_sample = metrics.score(frame, result.weights, [], label="out_of_sample")
    summary = artifacts.method_summary(
        result,
        in_sample,
        out_of_sample,
        artifact_path=tmp_path / "informed_l0.npz",
    )
    path = artifacts.write_run_manifest(
        tmp_path / "run_manifest.json",
        {"methods": {"informed_l0": summary}},
    )
    text = path.read_text()

    def fail_constant(value):
        raise AssertionError(f"non-standard JSON constant emitted: {value}")

    loaded = json.loads(text, parse_constant=fail_constant)
    assert "NaN" not in text
    assert loaded["methods"]["informed_l0"]["out_of_sample"]["mean_are"] is None


def test_summarize_run_writes_readable_tables(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "summarize_run",
        Path(__file__).resolve().parents[1] / "experiments" / "summarize_run.py",
    )
    assert spec is not None
    assert spec.loader is not None
    summarize_run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summarize_run)

    manifest = {
        "run_id": "toy-run",
        "created_at": "2026-06-20T00:00:00+00:00",
        "budget": 40,
        "target_split": {
            "total": 3,
            "fit": 2,
            "holdout": 1,
            "holdout_families": ["cbo"],
            "validation_only_families": ["cbo"],
        },
        "precalibration": {"n_records": 120},
        "methods": {
            "informed_l0": {
                "retained_records": 39,
                "epochs": 1000,
                "l0_lambda": 0.001,
                "runtime_s": 12.3,
                "in_sample": {
                    "mean_are": 0.1,
                    "median_are": 0.05,
                    "ess": 25,
                    "max_weight": 1000,
                    "by_family": {
                        "irs_soi": {"n": 2, "mean_are": 0.1, "median_are": 0.05, "max_are": 0.2}
                    },
                },
                "out_of_sample": {
                    "mean_are": 0.2,
                    "median_are": 0.15,
                    "by_family": {
                        "cbo": {"n": 1, "mean_are": 0.2, "median_are": 0.15, "max_are": 0.2}
                    },
                },
            }
        },
    }
    path = tmp_path / "run_manifest.json"
    path.write_text(json.dumps(manifest))

    outputs = summarize_run.write_summary(path)

    text = outputs["markdown"].read_text()
    assert "Run Summary: toy-run" in text
    assert "Informed L0" in text
    assert outputs["method_csv"].read_text().startswith("method,retained_records")
    assert "cbo" in outputs["family_csv"].read_text()


def test_method_summary_and_table_rendering():
    frame, targets = _toy()
    fit, held = holdout.split_targets(targets, holdout_frac=0.34, seed=1)

    l0 = run_l0(frame, fit, target_records=60, seed=0, epochs=120, learning_rate=0.15, mass="free")
    dense = run_dense_then_sample(
        frame, fit, n_sample=l0.n_selected, seed=0, epochs=120, learning_rate=0.15, mass="free",
    )

    summaries = {}
    for run in (l0, dense):
        in_sample = metrics.score(frame, run.weights, fit)
        out_of_sample = metrics.score(frame, run.weights, held)
        summary = artifacts.method_summary(
            run,
            in_sample,
            out_of_sample,
            artifact_path=f"/tmp/{run.method}.npz",
        )
        assert summary["retained_records"] == run.n_selected
        assert summary["artifact_path"] == f"/tmp/{run.method}.npz"
        assert "solver_initial_loss" in summary
        assert "solver_final_loss" in summary
        assert "initial_loss" not in summary
        assert "final_loss" not in summary
        summaries[run.method] = summary

    # method_summary records the weight-concentration controls.
    assert "l2_lambda" in summaries["informed_l0"]
    assert "max_weight_ratio" in summaries["informed_l0"]
    assert summaries["informed_l0"]["solver_options"]["budget_iters"] == 10
    assert summaries["informed_l0"]["solver_options"]["target_loss_cap"] == 10.0

    geo = metrics.score(frame, l0.weights, targets)
    sampling_tex = tables.render_sampling_comparison(summaries, budget=l0.n_selected)
    accuracy_tex = tables.render_calibration_accuracy(geo)
    family_tex = tables.render_calibration_accuracy_by_family(geo)

    assert "Informed $L_0$" in sampling_tex
    assert "Survey-weight sampling" in sampling_tex
    assert "Combinatorial optim. &" in sampling_tex
    assert "Combinatorial optim.\\ &" not in sampling_tex
    assert "\\tbc" in sampling_tex  # the two unimplemented methods stay placeholders
    assert "Target family" in family_tex
    assert "Geographic level" in accuracy_tex
    assert "All scored targets" in accuracy_tex


def test_drop_unsupported_filter_targets():
    """The harness drops only targets the materializer flags, keeps the rest."""
    from l0_paper.precalibration import _drop_unsupported_filter_targets

    class _Spec:
        def __init__(self, name):
            self.name = name

    class _StubDriver:
        # Stands in for the Populace driver's classifier (the supported-key check
        # itself lives in populace and is exercised there); here we only verify the
        # harness drops exactly the flagged targets and reports them.
        @staticmethod
        def _unsupported_ledger_filter_metadata(specs):
            return {"soi/4_3/agi": ["ledger_filter_income_percentile_range"]}

    specs = (_Spec("soi/1_1/total"), _Spec("soi/4_3/agi"), _Spec("jct/salt"))
    kept, dropped = _drop_unsupported_filter_targets(_StubDriver, specs)
    assert [s.name for s in kept] == ["soi/1_1/total", "jct/salt"]
    assert dropped == {"soi/4_3/agi": ["ledger_filter_income_percentile_range"]}

    class _CleanDriver:
        @staticmethod
        def _unsupported_ledger_filter_metadata(specs):
            return {}

    kept2, dropped2 = _drop_unsupported_filter_targets(_CleanDriver, specs)
    assert kept2 == specs
    assert dropped2 == {}


def test_absolute_path_preserves_h5_symlink_suffix(tmp_path):
    """PolicyEngine requires the visible H5 path suffix, not the resolved blob."""
    from l0_paper.precalibration import _absolute_path

    blob = tmp_path / "f0af25192d6c8a7efc2638da2bd8ec4278b066a"
    blob.write_text("placeholder")
    link = tmp_path / "populace_us_2024.h5"
    link.symlink_to(blob)

    assert _absolute_path(link) == link
    assert _absolute_path(link).suffix == ".h5"
    assert _absolute_path(link).resolve().suffix == ""


def test_validation_only_families_tracks_populace():
    """Returns Populace-classified validation-only families (cbo), never hard ones."""
    fams = holdout.validation_only_families()
    # cbo income/revenue projections are validation-only per Populace's source coverage.
    assert "cbo" in fams
    # Hard-target families must never be excluded from the fit.
    assert fams.isdisjoint({"irs_soi", "census_population", "jct", "cms_aca", "ssa"})
    # The set is gated by Populace: every returned family is currently classified
    # validation-only there (translated from the coverage family ids).
    from populace.build.us.source_coverage import validation_only_family_ids

    classified = set(validation_only_family_ids())
    assert "cbo_income_revenue_projection" in classified
