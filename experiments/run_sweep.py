#!/usr/bin/env python
"""Amplified budget sweep: the three calibration conditions across N and seeds.

Where ``run_poc.py`` runs one budget at one seed, this sweeps a grid of record
budgets x seeds on a *frozen* pre-calibration dataset and writes one tidy
long-format CSV (``metrics_long.csv``) that every figure and table consumes.

Design choices that keep it honest and affordable:

* **Frozen input.** Always reuses a pre-built ``(Frame, TargetRegistry)`` via
  ``--reuse-precalibration`` -- the calibration method is the only thing that
  varies. Build the artifact once with ``run_poc.py``.
* **Leak-free holdout.** The frontier uses one fixed *family-level* split
  (whole families held out, so nested cells never leak across the split). An
  optional rotation panel (``--rotation-folds``) re-runs at one anchor budget with
  family-grouped k-fold so every family is held out once -- a robustness check on
  the chosen split, not a per-point cost on the whole sweep.
* **Dense reuse.** The dense fit for survey-weight sampling does not depend on the
  budget, so it is computed once per seed and resampled at every budget.
* **Matched budget.** Informed L0 sets the budget at each (seed, budget) point;
  the two baselines match its retained count.

Example
-------
    uv run python experiments/run_sweep.py \
        --reuse-precalibration experiments/runs/full-20k-cbo-state-tax-holdout/precalibration \
        --out experiments/runs/sweep-moderate \
        --budgets 1000 2000 5000 10000 20000 \
        --seeds 0 1 2 \
        --epochs 1000 \
        --holdout-families census_population state_income_tax \
        --max-weight-ratio 5 \
        --rotation-folds 5 --rotation-budget 5000
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from l0_paper.experiments import aggregate, holdout, metrics
from l0_paper.experiments.artifacts import _jsonable, write_run_manifest
from l0_paper.experiments.conditions import (
    DEFAULT_EPOCHS,
    calibrate_dense,
    run_l0,
    run_random_then_reweight,
    sample_from_dense,
)
from l0_paper.precalibration import MANIFEST_JSON, load_precalibration_dataset


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-precalibration", type=Path, required=True,
                        help="Frozen pre-calibration artifact directory (built by run_poc.py).")
    parser.add_argument("--out", type=Path, required=True, help="Sweep output directory.")
    parser.add_argument("--budgets", type=int, nargs="+", required=True,
                        help="Record budgets (target_records) to sweep.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--weight-entity", default="household")

    # Optimizer.
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--mass", choices=("conserve", "free"), default="conserve")
    parser.add_argument("--max-weight-ratio", type=float, default=5.0,
                        help="Informed-L0 hard weight-concentration cap (max weight / "
                             "mean weight). Default 5.0 matches the production release "
                             "build. Pass a large value (e.g. 1e9) to run L0 effectively "
                             "uncapped.")

    # Fixed frontier holdout (family-level, leak-free).
    parser.add_argument("--holdout-families", nargs="*", default=None,
                        help="Families held out of every method's fit for the frontier.")
    parser.add_argument("--holdout-frac", type=float, default=0.0,
                        help="Extra random holdout fraction on top of the family split.")
    parser.add_argument("--fit-validation-only", action="store_true",
                        help="Include Populace validation-only families (e.g. cbo) in the fit.")

    # Rotation robustness panel (family-grouped k-fold at one anchor budget).
    parser.add_argument("--rotation-folds", type=int, default=0,
                        help="If >1, run a family-grouped k-fold rotation at --rotation-budget.")
    parser.add_argument("--rotation-budget", type=int, default=None,
                        help="Anchor budget for the rotation panel (default: median of --budgets).")
    parser.add_argument("--rotation-balance", choices=("target_count", "family"),
                        default="target_count")
    parser.add_argument("--rotation-seed", type=int, default=0,
                        help="Seed for the family->fold partition (fixed across calibration seeds).")

    # Sampling.
    parser.add_argument("--sample-reweight", choices=("equal_mass", "renorm_kept"),
                        default="equal_mass")
    parser.add_argument("--sample-replace", action="store_true")

    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def _score_and_emit(
    rows: list[dict],
    *,
    run,
    frame,
    fit_targets,
    holdout_targets,
    method: str,
    seed: int,
    budget_requested: int,
    holdout_type: str,
    fold: int,
) -> None:
    """Score one run in/out-of-sample and append its long-format rows."""
    in_sample = metrics.score(frame, run.weights, fit_targets, label="in_sample")
    out_of_sample = metrics.score(frame, run.weights, holdout_targets, label="out_of_sample")
    extreme = aggregate.extreme_are_counts(
        metrics.target_diagnostics(frame, run.weights, holdout_targets)
    )
    rows.extend(
        aggregate.rows_from_run(
            method=method,
            seed=seed,
            budget_requested=budget_requested,
            budget_achieved=run.n_selected,
            holdout_type=holdout_type,
            fold=fold,
            in_sample=in_sample,
            out_of_sample=out_of_sample,
            run=run,
            extra_run_metrics={f"holdout_{k}": v for k, v in extreme.items()},
        )
    )


def _sweep_split(
    rows: list[dict],
    *,
    frame,
    fit_targets,
    holdout_targets,
    budgets: list[int],
    seeds: list[int],
    l0_optimizer: dict,
    baseline_optimizer: dict,
    sample_kwargs: dict,
    holdout_type: str,
    fold: int,
) -> dict[str, float]:
    """Run all three conditions across budgets x seeds for one (fit, holdout) split.

    Dense calibration is computed once per seed and resampled at every budget.
    Returns per-seed dense runtimes for the manifest.
    """
    dense_runtimes: dict[str, float] = {}
    for seed in seeds:
        dense, dense_runtime = calibrate_dense(
            frame, fit_targets, seed=seed, **baseline_optimizer
        )
        dense_runtimes[str(seed)] = dense_runtime
        for budget in budgets:
            l0 = run_l0(
                frame, fit_targets, target_records=budget, seed=seed, **l0_optimizer
            )
            matched = l0.n_selected
            print(f"  [{holdout_type} fold={fold} seed={seed} budget={budget}] "
                  f"L0 retained {matched:,} (l0_lambda={l0.l0_lambda:.3e})")
            survey = sample_from_dense(
                dense, n_sample=matched, seed=seed, dense_runtime=dense_runtime,
                max_weight_ratio=baseline_optimizer.get("max_weight_ratio"),
                **sample_kwargs,
            )
            random_rw = run_random_then_reweight(
                frame, fit_targets, n_sample=matched, seed=seed, **baseline_optimizer
            )
            for run in (l0, survey, random_rw):
                _score_and_emit(
                    rows, run=run, frame=frame, fit_targets=fit_targets,
                    holdout_targets=holdout_targets, method=run.method, seed=seed,
                    budget_requested=budget, holdout_type=holdout_type, fold=fold,
                )
    return dense_runtimes


def main() -> None:
    args = _parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    precal_dir = args.reuse_precalibration.resolve()
    frame, registry = load_precalibration_dataset(precal_dir)
    precal_manifest = json.loads((precal_dir / MANIFEST_JSON).read_text())

    validation_only = (
        set() if args.fit_validation_only else holdout.validation_only_families(registry)
    )
    holdout_families = sorted(set(args.holdout_families or ()) | validation_only)

    baseline_optimizer = dict(
        weight_entity=args.weight_entity,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        max_weight_ratio=None,
        mass=args.mass,
    )
    l0_optimizer = {**baseline_optimizer, "max_weight_ratio": args.max_weight_ratio}
    sample_kwargs = dict(
        weight_entity=args.weight_entity,
        reweight=args.sample_reweight,
        replace=args.sample_replace,
    )

    rows: list[dict] = []

    # --- Frontier: one fixed leak-free family split, swept over budgets x seeds. ---
    if holdout_families:
        fit_targets, holdout_targets = holdout.split_registry_by_family(
            registry, holdout_families=holdout_families,
            extra_holdout_frac=args.holdout_frac, seed=args.rotation_seed,
        )
    else:
        fit_targets, holdout_targets = holdout.split_targets(
            registry.to_target_set(), holdout_frac=args.holdout_frac or 0.2, seed=args.rotation_seed,
        )
    print(f"Frontier split: {len(fit_targets)} fit, {len(holdout_targets)} held out "
          f"(families: {holdout_families or 'random'}). "
          f"Candidate records: {frame.n(args.weight_entity):,}.")
    frontier_dense_runtimes = _sweep_split(
        rows, frame=frame, fit_targets=fit_targets, holdout_targets=holdout_targets,
        budgets=args.budgets, seeds=args.seeds, l0_optimizer=l0_optimizer,
        baseline_optimizer=baseline_optimizer,
        sample_kwargs=sample_kwargs, holdout_type="fixed_family", fold=-1,
    )

    # --- Rotation robustness panel: family-grouped k-fold at one anchor budget. ---
    rotation_meta: dict = {}
    if args.rotation_folds and args.rotation_folds > 1:
        anchor = args.rotation_budget or sorted(args.budgets)[len(args.budgets) // 2]
        folds = holdout.family_grouped_folds(
            registry, n_folds=args.rotation_folds, seed=args.rotation_seed,
            balance_by=args.rotation_balance,
            exclude_validation_only=not args.fit_validation_only,
        )
        print(f"Rotation panel: {len(folds)}-fold family-grouped holdout at budget {anchor}.")
        rotation_meta = {
            "n_folds": len(folds),
            "anchor_budget": anchor,
            "balance_by": args.rotation_balance,
            "fold_holdout_sizes": [len(held) for _, held in folds],
        }
        for fold_idx, (fold_fit, fold_holdout) in enumerate(folds):
            _sweep_split(
                rows, frame=frame, fit_targets=fold_fit, holdout_targets=fold_holdout,
                budgets=[anchor], seeds=args.seeds, l0_optimizer=l0_optimizer,
                baseline_optimizer=baseline_optimizer,
                sample_kwargs=sample_kwargs, holdout_type="rotation", fold=fold_idx,
            )

    # --- Persist: long CSV (source of truth) + reproducibility manifest. ---
    long_csv = aggregate.write_long_csv(out / "metrics_long.csv", rows)
    print(f"Wrote {len(rows):,} rows -> {long_csv}")

    run_id = args.run_id or f"sweep-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "command_args": {k: str(v) for k, v in vars(args).items()},
        "precalibration_dir": str(precal_dir),
        "precalibration": precal_manifest,
        "grid": {"budgets": args.budgets, "seeds": args.seeds, "epochs": args.epochs},
        "l0_optimizer": _jsonable(l0_optimizer),
        "baseline_optimizer": _jsonable(baseline_optimizer),
        "frontier_split": {
            "fit": len(fit_targets),
            "holdout": len(holdout_targets),
            "holdout_families": holdout_families,
            "validation_only_families": sorted(validation_only),
            "holdout_frac": args.holdout_frac,
        },
        "frontier_dense_runtimes_s": frontier_dense_runtimes,
        "rotation": rotation_meta,
        "long_csv": str(long_csv),
        "n_rows": len(rows),
    }
    manifest_path = write_run_manifest(out / "sweep_manifest.json", manifest)
    print(f"Wrote sweep manifest: {manifest_path}")


if __name__ == "__main__":
    main()
