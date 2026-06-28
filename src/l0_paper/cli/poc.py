#!/usr/bin/env python
"""Run the Issue #4 proof-of-concept: informed L0 vs dense + weighted sampling.

Builds (or reuses) the frozen pre-calibration dataset, runs both calibration
conditions at a matched record budget, scores them in- and out-of-sample, and
writes run artifacts and draft tables into the run directory. The manuscript's
result tables come from the multi-seed sweep instead (``l0 figures --sweep <run>
--paper-figures``), so this single-budget driver no longer writes ``paper/tables``.

Example
-------
    uv run --extra data l0 poc \
        --ledger-facts /path/to/consumer_facts.jsonl \
        --out runs/poc \
        --subsample 20000 --target-records 5000 --seed 0

Reuse a previously frozen pre-calibration dataset (skips the heavy build):

    uv run --extra data l0 poc \
        --reuse-precalibration runs/poc/precalibration \
        --out runs/poc2 --target-records 5000 --seed 0
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from l0_paper.experiments import artifacts, holdout, metrics, tables, target_loss
from l0_paper.experiments.conditions import (
    DEFAULT_EPOCHS,
    run_dense_then_sample,
    run_l0,
    run_random_then_reweight,
)
from l0_paper.precalibration import (
    MANIFEST_JSON,
    build_precalibration_dataset,
    load_precalibration_dataset,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Run output directory.")
    parser.add_argument("--target-records", type=int, required=True, help="L0 record budget.")
    parser.add_argument("--seed", type=int, default=0)

    # Pre-calibration dataset: build new, or reuse a frozen one.
    parser.add_argument("--ledger-facts", type=Path, help="consumer_facts.jsonl path.")
    parser.add_argument("--base-h5", type=Path, help="Candidate frame (defaults to HF).")
    parser.add_argument("--reuse-precalibration", type=Path, help="Frozen artifact dir.")
    parser.add_argument("--period", type=int, default=None)
    parser.add_argument("--reset-weights", choices=("uniform", "keep"), default="uniform")
    parser.add_argument("--subsample", type=int, default=None, help="Subsample N households.")
    parser.add_argument("--weight-entity", default="household")
    parser.add_argument(
        "--allow-partial-facts",
        action="store_true",
        help="Tolerate a facts file that doesn't cover every reference (smoke only).",
    )
    parser.add_argument(
        "--keep-unsupported-targets",
        action="store_true",
        help=(
            "Keep targets whose ledger_filter metadata the US materializer cannot "
            "compute (e.g. SOI income-percentile / qualifying-children slices). "
            "Default drops them before materialization and records them in the "
            "pre-calibration manifest."
        ),
    )

    # Optimizer.
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument(
        "--max-weight-ratio",
        type=float,
        default=None,
        help=(
            "Informed-L0 per-record hard cap: no calibrated weight may exceed "
            "max_weight_ratio * its INITIAL weight (clamped each step). Default "
            "None (uncapped). With uniform-reset weights a small cap (e.g. 5) "
            "forbids the ~100x concentration the fiscal targets need and breaks L0."
        ),
    )
    parser.add_argument("--mass", choices=("conserve", "free"), default="conserve")
    parser.add_argument("--l2-lambda", type=float, default=0.0,
                        help="Soft weight-concentration penalty for informed L0.")
    parser.add_argument("--target-loss-weighting",
                        choices=target_loss.TARGET_LOSS_WEIGHTINGS,
                        default=target_loss.PRODUCTION_US_FISCAL,
                        help="Target-row weights used inside Populace's calibration "
                             "loss. Default matches the production US fiscal weighting.")
    parser.add_argument("--target-loss-cap", type=float, default=None,
                        help="Per-target cap in the calibration loss. Defaults by "
                             "weighting: production_us_fiscal -> 1.0, uniform -> "
                             "10.0. Pass 10.0 to reproduce the current paper runs.")

    # Out-of-sample split.
    parser.add_argument("--holdout-frac", type=float, default=0.2)
    parser.add_argument("--holdout-families", nargs="*", default=None)
    parser.add_argument(
        "--fit-validation-only",
        action="store_true",
        help=(
            "Include Populace's validation-only families (e.g. cbo income/revenue "
            "projections) in the calibration fit. Default excludes them from the "
            "fit and scores them out-of-sample only."
        ),
    )

    # Sampling.
    parser.add_argument("--sample-reweight", choices=("equal_mass", "renorm_kept"), default="equal_mass")
    parser.add_argument("--sample-replace", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="PPS sampling with replacement (default). Pass "
                             "--no-sample-replace for distinct-record draws.")

    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if args.reuse_precalibration is None and args.ledger_facts is None:
        parser.error("one of --ledger-facts or --reuse-precalibration is required.")
    return args


def main() -> None:
    args = _parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    target_loss_cap = target_loss.resolve_target_loss_cap(
        args.target_loss_weighting,
        args.target_loss_cap,
    )

    # 1. Pre-calibration dataset (the shared experiment input).
    if args.reuse_precalibration is not None:
        precal_dir = args.reuse_precalibration.resolve()
        frame, registry = load_precalibration_dataset(precal_dir)
        precal_manifest = json.loads((precal_dir / MANIFEST_JSON).read_text())
    else:
        artifact = build_precalibration_dataset(
            ledger_facts=args.ledger_facts,
            out_dir=out / "precalibration",
            base_h5=args.base_h5,
            period=args.period,
            reset_weights=args.reset_weights,
            weight_entity=args.weight_entity,
            subsample=args.subsample,
            subsample_seed=args.seed,
            allow_partial_facts=args.allow_partial_facts,
            drop_unsupported_filters=not args.keep_unsupported_targets,
        )
        precal_dir = artifact.directory
        frame, registry = artifact.frame, artifact.registry
        precal_manifest = artifact.manifest

    # 2. Hold targets out of every method's fit. Populace's validation-only families
    #    (e.g. cbo) are diagnostics, not fit targets, so they are always excluded from
    #    the fit (scored out-of-sample only) unless --fit-validation-only is set.
    all_targets = registry.to_target_set()
    validation_only = (
        set() if args.fit_validation_only else holdout.validation_only_families(registry)
    )
    holdout_families = sorted(set(args.holdout_families or ()) | validation_only)
    if holdout_families:
        fit_targets, holdout_targets = holdout.split_registry_by_family(
            registry,
            holdout_families=holdout_families,
            extra_holdout_frac=args.holdout_frac,
            seed=args.seed,
        )
    else:
        fit_targets, holdout_targets = holdout.split_targets(
            all_targets, holdout_frac=args.holdout_frac, seed=args.seed
        )
    if validation_only:
        print(
            "Validation-only families excluded from the fit (scored out-of-sample "
            f"only): {sorted(validation_only)}"
        )
    print(
        f"Targets: {len(all_targets)} total -> {len(fit_targets)} fit, "
        f"{len(holdout_targets)} held out. Candidate records: {frame.n(args.weight_entity):,}."
    )
    target_loss_weights = target_loss.target_loss_weights(
        fit_targets,
        weighting=args.target_loss_weighting,
    )
    print(
        "Target loss: "
        f"weighting={args.target_loss_weighting}, cap={target_loss_cap:g}, "
        f"weights={target_loss.target_loss_weight_summary(target_loss_weights)}"
    )

    baseline_optimizer = dict(
        weight_entity=args.weight_entity,
        seed=args.seed,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        max_weight_ratio=None,
        mass=args.mass,
        target_loss_weights=target_loss_weights,
        target_loss_cap=target_loss_cap,
    )
    l0_optimizer = {
        **baseline_optimizer,
        "max_weight_ratio": args.max_weight_ratio,
        "l2_lambda": args.l2_lambda,
    }

    # 3. Condition A: informed L0. Its retained count sets the matched budget.
    l0 = run_l0(frame, fit_targets, target_records=args.target_records, **l0_optimizer)
    budget = l0.n_selected
    print(f"Informed L0 retained {budget:,} records (l0_lambda={l0.l0_lambda:.3e}).")

    # 4. Condition B: dense calibration + weighted sampling at the matched budget.
    dense = run_dense_then_sample(
        frame,
        fit_targets,
        n_sample=budget,
        reweight=args.sample_reweight,
        replace=args.sample_replace,
        **baseline_optimizer,
    )
    print(f"Dense + sampling retained {dense.n_selected:,} records.")

    # 4c. Condition C: uniform random subset + gradient-descent reweight (matched budget).
    random_rw = run_random_then_reweight(
        frame, fit_targets, n_sample=budget, **baseline_optimizer
    )
    print(f"Random + reweight retained {random_rw.n_selected:,} records.")

    # 5. Score each, in- and out-of-sample.
    summaries: dict[str, dict] = {}
    for run in (l0, dense, random_rw):
        in_sample = metrics.score(frame, run.weights, fit_targets, label="in_sample")
        out_of_sample = metrics.score(frame, run.weights, holdout_targets, label="out_of_sample")
        artifact_path = artifacts.save_method_npz(
            out / f"{run.method}.npz",
            run,
            frame=frame,
            fit_targets=fit_targets,
            holdout_targets=holdout_targets,
        )
        summaries[run.method] = artifacts.method_summary(
            run,
            in_sample,
            out_of_sample,
            artifact_path=artifact_path,
        )

    # 6. L0 accuracy by geography, scored across all targets (Table 2).
    l0_geo = metrics.score(frame, l0.weights, all_targets, label="all")

    # 7. Draft tables into the run directory (inspection only; the manuscript's
    #    result tables are regenerated from the multi-seed sweep by ``l0 figures``).
    table_paths = tables.write_tables(
        out / "tables", summaries=summaries, l0_geo_score=l0_geo, budget=budget
    )

    # 8. Reproducibility manifest.
    run_id = args.run_id or f"poc-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "command_args": {k: str(v) for k, v in vars(args).items()},
        "precalibration_dir": str(precal_dir),
        "precalibration": precal_manifest,
        "target_split": {
            "total": len(all_targets),
            "fit": len(fit_targets),
            "holdout": len(holdout_targets),
            "holdout_families": args.holdout_families,
            "validation_only_families": sorted(validation_only),
            "holdout_frac": args.holdout_frac,
        },
        "target_loss": {
            "weighting": args.target_loss_weighting,
            "cap": target_loss_cap,
            "fit_weight_summary": target_loss.target_loss_weight_summary(
                target_loss_weights
            ),
            "production_source_path": (
                target_loss.production_source_path()
                if args.target_loss_weighting == target_loss.PRODUCTION_US_FISCAL
                else None
            ),
        },
        "budget": budget,
        "methods": summaries,
        "l0_geography": l0_geo,
        "tables": {name: str(path) for name, path in table_paths.items()},
    }
    manifest_path = artifacts.write_run_manifest(out / "run_manifest.json", manifest)
    print(f"Wrote run manifest: {manifest_path}")


if __name__ == "__main__":
    main()
