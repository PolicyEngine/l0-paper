"""Offline end-to-end tests for the experiment harness.

These exercise both calibration conditions, scoring, holdout splitting, artifact
summaries, and table rendering on the toy Populace frame -- no PolicyEngine-US and
no network, so CI stays fast and self-contained. The real-data path is driven by
``experiments/run_poc.py``.
"""

import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from l0_paper.experiments import (
    aggregate,
    artifacts,
    holdout,
    metrics,
    tables,
    target_loss,
)
from l0_paper.experiments.conditions import (
    calibrate_dense,
    run_dense_then_sample,
    run_l0,
    run_random_then_reweight,
    sample_from_dense,
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


def test_split_registry_by_family_rejects_unknown_family():
    import pytest

    _, targets = _toy()
    target_list = list(targets)
    registry = SimpleNamespace(
        specs=[SimpleNamespace(family="known") for _ in target_list],
        to_target_set=lambda: TargetSet(target_list),
    )

    with pytest.raises(ValueError, match="Unknown holdout family"):
        holdout.split_registry_by_family(
            registry, holdout_families=["known", "census_stc"]
        )


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
    # l2_lambda is zero unless the informed-L0/Hard-Concrete condition opts in.
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
    assert result.n_selected == 40  # with-replacement draw count
    assert result.sampling["n_sample"] == 40
    assert 0 < result.sampling["n_unique_selected"] <= 40
    assert result.sampling["replace"] is True


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
    assert 0 < np.count_nonzero(full) <= 3
    assert np.isclose(full.sum(), weights.sum())


def test_weighted_sample_can_draw_without_replacement():
    weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    full = weighted_sample(weights, 3, seed=0, replace=False)
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


def test_identifiability_floor_flags_degenerate_targets():
    """A target below a single household's contribution is denominator-degenerate."""
    frame, truths = make_toy_frame(seed=0, n=120)
    tiny = Target(name="tiny_income", entity="household",
                  measure="income", value=1.0)
    total = Target(name="total_income", entity="household",
                   measure="income", value=truths["income"])
    targets = TargetSet((tiny, total))

    floors = metrics.identifiability_floors(frame, targets)
    # One household contributes far more than the tiny target, but far less than the total.
    assert floors[tiny.row_name] > 1.0
    assert floors[total.row_name] < truths["income"]

    names = metrics.degenerate_target_names(frame, targets)
    assert tiny.row_name in names
    assert total.row_name not in names

    audit = metrics.degenerate_audit(frame, targets)
    assert [r["name"] for r in audit] == [tiny.row_name]
    assert audit[0]["floor_ratio"] > 1.0


def test_score_reports_degenerate_removal_sensitivity():
    """``score`` emits the targeted-removal mean alongside the tail-sensitive mean."""
    frame, truths = make_toy_frame(seed=0, n=120)
    weights = frame.weights_for("household").values
    tiny = Target(name="tiny_income", entity="household",
                  measure="income", value=1.0)
    total = Target(name="total_income", entity="household",
                   measure="income", value=truths["income"])
    targets = TargetSet((tiny, total))
    degenerate = metrics.degenerate_target_names(frame, targets)

    scored = metrics.score(frame, weights, targets, degenerate_names=degenerate)
    assert scored["n_degenerate"] == 1
    # At base weights the realistic total is hit exactly (ARE 0) while the tiny
    # target's ARE explodes; dropping the named degenerate target collapses the mean.
    assert scored["mean_are_ex_degenerate"] < scored["mean_are"]
    assert scored["mean_are_ex_degenerate"] < 0.01

    # Without degenerate_names the extra fields are absent (back-compatible).
    plain = metrics.score(frame, weights, targets)
    assert "mean_are_ex_degenerate" not in plain


def test_target_diagnostics_persistence_and_attribution(tmp_path):
    """Per-target rows round-trip and the attribution names the worst offender."""
    frame, truths = make_toy_frame(seed=0, n=120)
    weights = frame.weights_for("household").values
    tiny = Target(name="tiny_income", entity="household",
                  measure="income", value=1.0)
    total = Target(name="total_income", entity="household",
                   measure="income", value=truths["income"])
    targets = list(TargetSet((tiny, total)))
    degenerate = metrics.degenerate_target_names(frame, targets)

    diagnostics = metrics.target_diagnostics(frame, weights, targets)
    rows = aggregate.target_diagnostic_rows(
        method="informed_l0", seed=0, budget_requested=40, split="out_of_sample",
        diagnostics=diagnostics, degenerate_names=degenerate,
    )
    path = aggregate.write_target_diagnostics_csv(tmp_path / "diag.csv", rows)
    loaded = aggregate.load_target_diagnostics(path)
    assert set(loaded["target_name"]) == {tiny.row_name, total.row_name}

    top = aggregate.top_are_contributors(
        loaded, method="informed_l0", budget_requested=40, split="out_of_sample",
    )
    assert top.iloc[0]["target_name"] == tiny.row_name
    assert bool(top.iloc[0]["is_degenerate"])
    assert top.iloc[0]["share_of_mean"] > 0.99


def test_rows_from_run_emits_degenerate_metrics():
    rows = aggregate.rows_from_run(
        method="informed_l0", seed=0, budget_requested=1000, budget_achieved=995,
        holdout_type="fixed_family", fold=-1,
        in_sample={"mean_are": 0.5, "median_are": 0.1, "max_are": 9.0, "n": 10,
                   "mean_are_ex_degenerate": 0.08, "n_degenerate": 3,
                   "by_family": {}, "by_geography": {},
                   "ess": 50.0, "max_weight": 100.0, "n_selected": 995,
                   "sum_weight": 1.0, "mean_weight": 1.0, "p50_weight": 1.0,
                   "p90_weight": 1.0, "p99_weight": 1.0},
        out_of_sample={"mean_are": 0.2, "median_are": 0.1, "max_are": 0.4, "n": 5,
                       "by_family": {}, "by_geography": {}},
        run=SimpleNamespace(runtime_s=12.0, l0_lambda=1e-3, l2_lambda=1e-4, final_loss=0.4),
    )
    overall_in = {(r["metric"], r["value"]) for r in rows
                  if r["scope"] == "overall" and r["split"] == "in_sample"}
    assert ("mean_are_ex_degenerate", 0.08) in overall_in
    assert ("n_degenerate", 3.0) in overall_in


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
    try:
        from populace.build.us.source_coverage import validation_only_family_ids
    except ModuleNotFoundError:
        from populace.build.us_runtime.source_coverage import validation_only_family_ids

    classified = set(validation_only_family_ids())
    assert "cbo_income_revenue_projection" in classified


def test_production_us_fiscal_target_loss_imports_populace_helper():
    targets = TargetSet(
        (
            Target(
                name="amount_small",
                entity="household",
                measure="income",
                value=100.0,
                metadata={"source_measure_id": "payment_amount"},
            ),
            Target(
                name="amount_large",
                entity="household",
                measure="income",
                value=400.0,
                metadata={"source_measure_id": "payment_amount"},
            ),
            Target(
                name="count_row",
                entity="household",
                measure="household_count",
                value=25.0,
                metadata={
                    "source_measure_id": "return_count",
                    "measure_mode": "indicator_sum",
                },
            ),
        )
    )

    weights = target_loss.target_loss_weights(
        targets,
        weighting=target_loss.PRODUCTION_US_FISCAL,
    )

    assert weights is not None
    assert np.isclose(weights.mean(), 1.0)
    # Reuses Populace's production rule: sqrt(value) within the amount basis.
    assert np.isclose(weights[1] / weights[0], 2.0)
    assert target_loss.resolve_target_loss_cap(
        target_loss.PRODUCTION_US_FISCAL,
        None,
    ) == 10.0
    assert target_loss.resolve_target_loss_cap(target_loss.UNIFORM, None) == 10.0
    assert target_loss.target_loss_weight_summary(weights)["kind"] == "provided"


# --- Amplified sweep: family-grouped folds ------------------------------------


def test_deal_families_into_folds_is_leak_free_and_covers():
    # One dominant family plus several small ones (the real shape).
    families = ["soi"] * 10 + ["pep"] * 5 + ["snap"] * 3 + ["jct"] * 2 + ["cbo"] * 1
    folds = holdout.deal_families_into_folds(families, n_folds=3, seed=0)

    covered = sorted(i for fold in folds for i in fold)
    assert covered == list(range(len(families)))  # partition, no gaps/overlap

    # Every family's targets land in exactly one fold (no within-family leakage).
    fold_of = {i: fi for fi, fold in enumerate(folds) for i in fold}
    folds_per_family: dict[str, set[int]] = defaultdict(set)
    for i, family in enumerate(families):
        folds_per_family[family].add(fold_of[i])
    assert all(len(folds) == 1 for folds in folds_per_family.values())


def test_deal_families_into_folds_balances_and_is_deterministic():
    families = [f for fam in ("a", "b", "c", "d", "e", "f") for f in (fam, fam)]  # 6x2
    folds = holdout.deal_families_into_folds(families, n_folds=3, seed=0, balance_by="target_count")
    assert sorted(len(fold) for fold in folds) == [4, 4, 4]  # evenly balanced
    # Deterministic for a fixed seed.
    again = holdout.deal_families_into_folds(families, n_folds=3, seed=0, balance_by="target_count")
    assert folds == again


def test_deal_families_into_folds_rejects_too_many_folds():
    import pytest

    with pytest.raises(ValueError):
        holdout.deal_families_into_folds(["a", "a", "b"], n_folds=3)  # only 2 families


def test_family_grouped_folds_excludes_validation_only_and_rotates():
    families = ["soi", "soi", "soi", "pep", "pep", "jct", "jct", "cbo", "cbo", "snap"]
    targets = [
        Target(name=f"{fam}_{i}", entity="household",
                measure="is_renter", value=1.0)
        for i, fam in enumerate(families)
    ]
    registry = SimpleNamespace(
        specs=[SimpleNamespace(family=fam) for fam in families],
        to_target_set=lambda: TargetSet(targets),
    )
    name_family = {t.name: fam for t, fam in zip(targets, families, strict=True)}

    folds = holdout.family_grouped_folds(registry, n_folds=2, seed=0)
    assert len(folds) == 2

    held_in_fold: dict[str, set[int]] = defaultdict(set)
    for fi, (fit, held) in enumerate(folds):
        fit_families = [name_family[t.name] for t in fit]
        assert "cbo" not in fit_families  # validation-only never fit
        for t in held:
            held_in_fold[name_family[t.name]].add(fi)

    # cbo (validation-only) is held out of every fold; each rotatable family once.
    assert held_in_fold["cbo"] == {0, 1}
    for family in ("soi", "pep", "jct", "snap"):
        assert len(held_in_fold[family]) == 1


# --- Amplified sweep: dense-calibration caching --------------------------------


def test_calibrate_dense_then_sample_matches_run_dense_then_sample():
    """The cached dense fit + sample reproduces the single-shot path exactly."""
    frame, targets = _toy()
    direct = run_dense_then_sample(
        frame, targets, n_sample=40, seed=0, epochs=80, learning_rate=0.15, mass="free",
    )
    dense, _runtime = calibrate_dense(
        frame, targets, seed=0, epochs=80, learning_rate=0.15, mass="free",
    )
    cached = sample_from_dense(dense, n_sample=40, seed=0)

    assert np.allclose(direct.weights, cached.weights)
    assert direct.n_selected == cached.n_selected
    assert direct.method == cached.method == "dense_sample"


# --- Amplified sweep: aggregation + statistics ---------------------------------


def _synthetic_long_rows():
    rows: list[dict] = []
    # informed_l0 lower in/out error than random_reweight at both budgets.
    for method, base in (("informed_l0", 0.10), ("random_reweight", 0.12)):
        for budget in (1000, 2000):
            for seed in (0, 1, 2):
                in_stats = {
                    "mean_are": base, "median_are": base * 0.5, "max_are": base * 3, "n": 100,
                    "by_family": {"soi": {"mean_are": base, "median_are": base, "max_are": base, "n": 80},
                                  "snap": {"mean_are": base * 2, "median_are": base, "max_are": base * 4, "n": 20}},
                    "by_geography": {"national": {"mean_are": base, "median_are": base, "max_are": base, "n": 10}},
                    "ess": 500.0, "max_weight": 1000.0, "n_selected": budget,
                    "sum_weight": 1e6, "mean_weight": 2.0,
                    "p50_weight": 1.0, "p90_weight": 2.0, "p99_weight": 3.0,
                }
                # Small per-seed jitter keeps the L0-vs-random difference negative
                # with low (non-zero) variance, so across 3 seeds the paired CI
                # excludes zero and the t-test has something to chew on.
                bump = 0.0005 if method == "informed_l0" else 0.001
                out_stats = {**in_stats, "mean_are": base + 0.05 + bump * seed}
                run = SimpleNamespace(runtime_s=10.0 * (1 if method == "informed_l0" else 0.1),
                                      l0_lambda=1e-3, final_loss=0.5)
                rows.extend(aggregate.rows_from_run(
                    method=method, seed=seed, budget_requested=budget, budget_achieved=budget - 5,
                    holdout_type="fixed_family", fold=-1,
                    in_sample=in_stats, out_of_sample=out_stats, run=run,
                ))
    return rows


def _synthetic_rotation_rows():
    rows: list[dict] = []
    # Validation-only CBO appears in every fold and should be excluded from the
    # rotated-family aggregate; rot_a and rot_b should each count once per seed.
    for seed, offset in ((0, 0.0), (1, 0.10), (2, 0.20)):
        for fold, family, family_n, family_are in (
            (0, "rot_a", 10, 0.10 + offset),
            (1, "rot_b", 30, 0.30 + offset),
        ):
            out_stats = {
                "mean_are": 0.99,  # ignored by rotation_seed_scores
                "median_are": 0.99,
                "max_are": 0.99,
                "n": family_n + 5,
                "by_family": {
                    family: {
                        "mean_are": family_are,
                        "median_are": family_are,
                        "max_are": family_are,
                        "n": family_n,
                    },
                    "cbo": {
                        "mean_are": 0.90,
                        "median_are": 0.90,
                        "max_are": 0.90,
                        "n": 5,
                    },
                },
                "by_geography": {},
            }
            in_stats = {
                "mean_are": 0.05,
                "median_are": 0.05,
                "max_are": 0.05,
                "n": 10,
                "by_family": {},
                "by_geography": {},
                "ess": 100.0,
                "max_weight": 10.0,
                "n_selected": 1000,
                "sum_weight": 1.0,
                "mean_weight": 1.0,
                "p50_weight": 1.0,
                "p90_weight": 1.0,
                "p99_weight": 1.0,
            }
            rows.extend(aggregate.rows_from_run(
                method="informed_l0",
                seed=seed,
                budget_requested=1000,
                budget_achieved=995 + fold,
                holdout_type="rotation",
                fold=fold,
                in_sample=in_stats,
                out_of_sample=out_stats,
                run=SimpleNamespace(runtime_s=1.0, l0_lambda=1e-3, final_loss=0.1),
            ))
    return rows


def test_rows_from_run_emit_overall_family_geo_and_run_rows():
    rows = aggregate.rows_from_run(
        method="informed_l0", seed=0, budget_requested=1000, budget_achieved=995,
        holdout_type="fixed_family", fold=-1,
        in_sample={"mean_are": 0.1, "median_are": 0.05, "max_are": 0.3, "n": 10,
                   "by_family": {"soi": {"mean_are": 0.1, "median_are": 0.1, "max_are": 0.1, "n": 8}},
                   "by_geography": {"national": {"mean_are": 0.1, "median_are": 0.1, "max_are": 0.1, "n": 2}},
                   "ess": 50.0, "max_weight": 100.0, "n_selected": 995,
                   "sum_weight": 1.0, "mean_weight": 1.0, "p50_weight": 1.0, "p90_weight": 1.0, "p99_weight": 1.0},
        out_of_sample={"mean_are": 0.2, "median_are": 0.1, "max_are": 0.4, "n": 5,
                       "by_family": {}, "by_geography": {}},
        run=SimpleNamespace(runtime_s=12.0, l0_lambda=1e-3, final_loss=0.4),
    )
    scopes = {(r["scope"], r["split"], r["metric"]) for r in rows}
    assert ("overall", "out_of_sample", "mean_are") in scopes
    assert ("family", "in_sample", "mean_are") in scopes
    assert ("geography", "in_sample", "mean_are") in scopes
    assert ("run", "na", "ess") in scopes
    assert ("run", "na", "runtime_s") in scopes
    assert ("run", "na", "budget_achieved") in scopes


def test_frontier_and_paired_aggregation():
    df = pd.DataFrame(_synthetic_long_rows())

    frontier = aggregate.frontier_table(df, metric="mean_are")
    oos = frontier[frontier["split"] == "out_of_sample"]
    assert set(oos["method"]) == {"informed_l0", "random_reweight"}
    assert (oos["n_seeds"] == 3).all()
    # informed_l0 sits below random_reweight out-of-sample at every budget.
    for budget in (1000, 2000):
        l0 = oos[(oos["method"] == "informed_l0") & (oos["budget_requested"] == budget)]["mean_are_mean"].iloc[0]
        rw = oos[(oos["method"] == "random_reweight") & (oos["budget_requested"] == budget)]["mean_are_mean"].iloc[0]
        assert l0 < rw
        assert oos["budget_achieved"].notna().all()

    paired = aggregate.paired_method_diff(df)
    assert (paired["diff_mean"] < 0).all()  # challenger (L0) better
    assert paired["challenger_better"].all()
    assert paired["significant"].all()  # CI excludes zero
    assert paired["p_value"].notna().all()  # >=2 seeds with non-zero variance


def test_paired_significance_requires_three_seeds():
    df = pd.DataFrame(_synthetic_long_rows())
    single_seed = df[df["seed"] == 0]

    paired = aggregate.paired_method_diff(single_seed)

    assert not paired.empty
    assert not paired["significant"].any()
    assert paired["p_value"].isna().all()


def test_rotation_seed_scores_weight_folds_and_exclude_validation_only():
    df = pd.DataFrame(_synthetic_rotation_rows())

    seed_scores = aggregate.rotation_seed_scores(df)

    assert seed_scores["n_folds"].eq(2).all()
    assert seed_scores["n_targets"].eq(40).all()
    assert seed_scores["excluded_validation_only_targets"].eq(10).all()
    by_seed = seed_scores.set_index("seed")["mean_are"].to_dict()
    assert np.isclose(by_seed[0], (0.10 * 10 + 0.30 * 30) / 40)
    assert np.isclose(by_seed[1], (0.20 * 10 + 0.40 * 30) / 40)
    assert np.isclose(by_seed[2], (0.30 * 10 + 0.50 * 30) / 40)

    frontier = aggregate.rotation_frontier_table(df)
    row = frontier.iloc[0]
    assert row["n_seeds"] == 3
    assert np.isclose(row["mean_are_mean"], np.mean([0.25, 0.35, 0.45]))
    assert row["mean_are_lo"] < row["mean_are_mean"] < row["mean_are_hi"]


def test_macro_average_upweights_small_families():
    df = pd.DataFrame(_synthetic_long_rows())
    macro = aggregate.macro_average(df, split="in_sample")
    # informed_l0 in-sample: soi=base, snap=2*base -> macro = 1.5*base > micro mean (base).
    l0 = macro[macro["method"] == "informed_l0"]
    assert not l0.empty
    assert (l0["macro_mean_are_mean"] > 0.10).all()


def _l0_only_rows(l2_values):
    rows = []
    for l2, ess, oos in l2_values:
        in_stats = {"mean_are": 0.1, "median_are": 0.05, "max_are": 1.0, "n": 50,
                    "by_family": {}, "by_geography": {}, "ess": ess, "max_weight": 1e6 / (1 + l2 * 1e6),
                    "n_selected": 10000, "sum_weight": 1.0, "mean_weight": 1.0,
                    "p50_weight": 1.0, "p90_weight": 1.0, "p99_weight": 1.0}
        out_stats = {"mean_are": oos, "median_are": oos * 0.5, "max_are": oos * 2, "n": 30,
                     "by_family": {}, "by_geography": {}}
        rows += aggregate.rows_from_run(
            method="informed_l0", seed=0, budget_requested=10000, budget_achieved=9900,
            l2_lambda=l2, holdout_type="fixed_family", fold=-1,
            in_sample=in_stats, out_of_sample=out_stats,
            run=SimpleNamespace(runtime_s=1.0, l0_lambda=1e-3, l2_lambda=l2, final_loss=0.1),
        )
    return rows


def test_operability_table_traces_l2_frontier():
    df = pd.DataFrame(_l0_only_rows([(0.0, 1000.0, 0.2), (1e-3, 3000.0, 5.0)]))
    op = aggregate.operability_table(df, budget_requested=10000)
    assert list(op["l2_lambda"]) == [0.0, 1e-3]
    assert op.loc[op["l2_lambda"] == 0.0, "ess"].iloc[0] == 1000.0
    assert op.loc[op["l2_lambda"] == 1e-3, "ess"].iloc[0] == 3000.0
    # Accuracy degrades and max weight falls as l2 (and ESS) rise -- the trade-off.
    assert (op.loc[op["l2_lambda"] == 1e-3, "oos_mean_are"].iloc[0]
            > op.loc[op["l2_lambda"] == 0.0, "oos_mean_are"].iloc[0])
    assert (op.loc[op["l2_lambda"] == 1e-3, "max_weight"].iloc[0]
            < op.loc[op["l2_lambda"] == 0.0, "max_weight"].iloc[0])


def test_paired_method_diff_handles_l0_only_sweep():
    df = pd.DataFrame(_l0_only_rows([(0.0, 1000.0, 0.2)]))
    paired = aggregate.paired_method_diff(df)  # no random_reweight rows -> no pairs
    assert paired.empty  # returns cleanly rather than raising on the absent column


def test_mean_ci_and_extreme_counts():
    mean, lo, hi = aggregate.mean_ci([0.1, 0.2, 0.3])
    assert lo < mean < hi
    one = aggregate.mean_ci([0.5])
    assert one == (0.5, 0.5, 0.5)

    counts = aggregate.extreme_are_counts(
        [{"absolute_relative_error": 0.5}, {"absolute_relative_error": 2.0},
         {"absolute_relative_error": None}, {"absolute_relative_error": 10.0}]
    )
    assert counts["n_scored"] == 3.0
    assert counts["n_are_gt_1"] == 2.0
    assert counts["n_are_gt_5"] == 1.0


def test_render_frontier_and_paired_tables():
    df = pd.DataFrame(_synthetic_long_rows())
    frontier = aggregate.frontier_table(df, metric="mean_are")
    paired = aggregate.paired_method_diff(df)

    frontier_tex = tables.render_frontier(frontier, split="out_of_sample")
    assert "Informed $L_0$" in frontier_tex
    assert "Average retained records" in frontier_tex
    assert "\\label{tab:frontier_out_of_sample}" in frontier_tex

    paired_tex = tables.render_paired_comparison(paired)
    assert "Random + reweight" in paired_tex
    assert "$^\\star$" in paired_tex  # all synthetic budgets are significant
