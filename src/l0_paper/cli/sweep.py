#!/usr/bin/env python
"""Amplified budget sweep: calibration conditions across N and seeds.

Where ``l0 poc`` runs one budget at one seed, this sweeps a grid of record
budgets x seeds on a *frozen* pre-calibration dataset and writes one tidy
long-format CSV (``metrics_long.csv``) that every figure and table consumes.

Design choices that keep it honest and affordable:

* **Frozen input.** Always reuses a pre-built ``(Frame, TargetRegistry)`` via
  ``--reuse-precalibration`` -- the calibration method is the only thing that
  varies. Build the artifact once with ``l0 poc``.
* **Leak-free holdout.** The frontier uses one fixed *family-level* split
  (whole families held out, so nested cells never leak across the split). An
  optional rotation panel (``--rotation-folds``) re-runs at one anchor budget with
  family-grouped k-fold so every family is held out once -- a robustness check on
  the chosen split, not a per-point cost on the whole sweep.
* **Dense reuse.** The dense fit for survey-weight sampling does not depend on the
  budget, so it is computed once per seed and resampled at every budget.
* **Matched budget.** Informed L0 sets the budget at each (seed, budget) point;
  the other methods match its retained count.

Example
-------
    uv run --extra data l0 sweep \
        --reuse-precalibration runs/poc/precalibration \
        --out runs/sweep-moderate \
        --budgets 2000 5000 10000 20000 40000 \
        --seeds 0 1 2 \
        --epochs 1000 \
        --holdout-families cms_medicaid usda_snap state_income_tax \
        --rotation-folds 5 --rotation-budget 10000 \
        --target-loss-cap 10 \
        --methods informed_l0 random_reweight dense_sample

That command reproduces the current paper frontier. Omit ``--methods`` to include
the proximal L1 arm, and omit ``--target-loss-cap 10`` to use the current
production US-fiscal cap.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from l0_paper.experiments import aggregate, holdout, metrics, target_loss
from l0_paper.experiments.artifacts import _jsonable, write_run_manifest
from l0_paper.experiments.conditions import (
    DEFAULT_EPOCHS,
    calibrate_dense,
    run_l0,
    run_l1,
    run_random_then_reweight,
    sample_from_dense,
)
from l0_paper.precalibration import MANIFEST_JSON, load_precalibration_dataset

METRICS_CSV = "metrics_long.csv"
TARGET_DIAGNOSTICS_CSV = "target_diagnostics_long.csv"
SWEEP_MANIFEST_JSON = "sweep_manifest.json"
SHARD_CHECKPOINT_DIR = "shard_checkpoints"
SHARD_MANIFEST_JSON = "shard_manifest.json"

CellKey = tuple[str, int, int, int, float]
MethodKey = tuple[str, int, int, int, float, str]


@dataclass(frozen=True)
class SplitShardResult:
    """Rows emitted by one parallel seed/fold/L2 shard."""

    label: str
    rows: list[dict]
    diag_rows: list[dict]
    dense_runtimes: dict[str, float]

_RESUME_COMPAT_ARG_KEYS = (
    "weight_entity",
    "epochs",
    "learning_rate",
    "mass",
    "max_weight_ratio",
    "budget_iters",
    "target_loss_weighting",
    "target_loss_cap",
    "holdout_families",
    "holdout_frac",
    "fit_validation_only",
    "rotation_folds",
    "rotation_budget",
    "rotation_balance",
    "rotation_seed",
    "sample_reweight",
    "sample_replace",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-precalibration", type=Path, required=True,
                        help="Frozen pre-calibration artifact directory (built by l0 poc).")
    parser.add_argument("--out", type=Path, required=True, help="Sweep output directory.")
    parser.add_argument("--budgets", type=int, nargs="+", required=True,
                        help="Record budgets (target_records) to sweep.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--weight-entity", default="household")

    # Optimizer.
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--mass", choices=("conserve", "free"), default="conserve")
    parser.add_argument("--max-weight-ratio", type=float, default=None,
                        help="Informed-L0 per-record hard cap: no calibrated weight may "
                             "exceed max_weight_ratio * its INITIAL weight (clamped each "
                             "step). Default None (uncapped). NB: with uniform-reset "
                             "weights a small cap (e.g. 5) forbids the ~100x concentration "
                             "the fiscal targets need and breaks L0 -- treat the cap as a "
                             "swept axis, not a fixed default.")
    parser.add_argument("--l2-lambdas", type=float, nargs="+", default=[0.0],
                        help="Soft weight-concentration penalties to sweep for the "
                             "informed-L0/Hard-Concrete condition only. Dense and "
                             "random-reweight baselines remain unpenalized.")
    parser.add_argument("--budget-iters", type=int, default=10,
                        help="L0 budget-bisection iterations. Each is a FULL optimization "
                             "re-run to hit target_records, so this is the dominant L0 "
                             "cost multiplier. Lower (e.g. 4-5) is ~2x faster with looser "
                             "budget matching -- fine since the frontier plots vs achieved "
                             "budget.")
    parser.add_argument("--target-loss-weighting",
                        choices=target_loss.TARGET_LOSS_WEIGHTINGS,
                        default=target_loss.PRODUCTION_US_FISCAL,
                        help="Target-row weights used inside Populace's calibration "
                             "loss. Default 'production_us_fiscal' imports Populace's "
                             "production _fiscal_target_loss_weights helper; 'uniform' "
                             "preserves the historical unweighted experiment loss.")
    parser.add_argument("--target-loss-cap", type=float, default=None,
                        help="Per-target cap in the calibration loss. Defaults by "
                             "weighting: production_us_fiscal -> 1.0, uniform -> "
                             "10.0. Pass 10.0 to reproduce the current paper runs.")

    # Fixed frontier holdout (family-level, leak-free).
    parser.add_argument("--holdout-families", nargs="*",
                        default=["cms_medicaid", "usda_snap", "state_income_tax"],
                        help="Families held out of every method's fit for the frontier. "
                             "Default is a representative leak-free basket spanning three "
                             "domains (healthcare / transfer / state-tax), each with a "
                             "sibling family kept in the fit (cms_aca+cms_medicare; snap's "
                             "sibling tanf; federal irs_soi), so generalisation is tested "
                             "without orphaning a domain. cbo (validation-only) is always "
                             "added unless --fit-validation-only is set.")
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

    # Sampling. The survey-weight baseline is PPS (draw probability proportional to
    # the dense weight) with ``equal_mass`` reweighting under sampling **with
    # replacement** -- the Hansen-Hurwitz integerisation of the dense weights,
    # unbiased at every budget (E[assigned weight_i] = w_i). A record drawn k times
    # accumulates k*(W/n), so duplicates collapse into one record carrying ~w_i.
    # ``renorm_kept`` (keep w_i, then rescale) is a DIFFERENT, biased object: it
    # re-weights sub-aggregates by w^2, over-favouring high-weight records, so it is
    # not survey-weight sampling and is kept only for contrast. Without replacement,
    # equal_mass under-weights high-w records at large n (the sample drifts toward
    # uniform), which is why replacement is the default.
    parser.add_argument("--sample-reweight", choices=("equal_mass", "renorm_kept"),
                        default="equal_mass")
    parser.add_argument("--sample-replace", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="PPS sampling with replacement (default; the unbiased "
                             "Hansen-Hurwitz integerisation with equal_mass). Pass "
                             "--no-sample-replace for distinct-record draws (biased low "
                             "on high-weight records at large budgets).")

    parser.add_argument(
        "--methods", nargs="+",
        choices=["informed_l0", "informed_l1", "random_reweight", "dense_sample"],
        default=["informed_l0", "informed_l1", "random_reweight", "dense_sample"],
        help="Which calibration conditions to run. Default all four. Use e.g. "
             "--methods informed_l0 to run L0 only (the expensive condition); the "
             "cheap baselines can be added in a later run at matched budgets.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel seed/fold/L2 shards to run. The parent process "
             "owns checkpoint writes. Keep BLAS/PyTorch thread env vars low "
             "(for example OMP_NUM_THREADS=1) when using jobs > 1.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume from existing metrics_long.csv in --out by skipping completed "
        "budget/seed/fold cells (default: yes). Pass --no-resume to overwrite.",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be >= 1")
    return args


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _load_existing_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _atomic_write_long_csv(path: Path, rows: list[dict]) -> Path:
    tmp = path.with_name(f".{path.name}.tmp")
    aggregate.write_long_csv(tmp, rows)
    tmp.replace(path)
    return path


def _atomic_write_target_diagnostics_csv(path: Path, rows: list[dict]) -> Path:
    tmp = path.with_name(f".{path.name}.tmp")
    aggregate.write_target_diagnostics_csv(tmp, rows)
    tmp.replace(path)
    return path


def _atomic_write_manifest(path: Path, manifest: dict) -> Path:
    tmp = path.with_name(f".{path.name}.tmp")
    write_run_manifest(tmp, manifest)
    tmp.replace(path)
    return path


def _row_signature(row: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in row.items()))


def _merge_unique_rows(target: list[dict], incoming: list[dict]) -> int:
    existing = {_row_signature(row) for row in target}
    added = 0
    for row in incoming:
        signature = _row_signature(row)
        if signature in existing:
            continue
        target.append(row)
        existing.add(signature)
        added += 1
    return added


def _safe_shard_name(label: str) -> str:
    return "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in label
    )


def _write_shard_checkpoint(
    shard_dir: Path,
    *,
    label: str,
    rows: list[dict],
    diag_rows: list[dict],
) -> None:
    """Persist one worker's local rows after a completed budget cell."""
    shard_dir.mkdir(parents=True, exist_ok=True)
    if rows:
        _atomic_write_long_csv(shard_dir / METRICS_CSV, rows)
    if diag_rows:
        _atomic_write_target_diagnostics_csv(
            shard_dir / TARGET_DIAGNOSTICS_CSV, diag_rows
        )
    manifest = {
        "schema_version": 1,
        "label": label,
        "updated_at": datetime.now(UTC).isoformat(),
        "metrics_csv": str(shard_dir / METRICS_CSV),
        "target_diagnostics_csv": (
            str(shard_dir / TARGET_DIAGNOSTICS_CSV) if diag_rows else None
        ),
        "n_rows": len(rows),
        "n_target_diagnostic_rows": len(diag_rows),
    }
    _atomic_write_manifest(shard_dir / SHARD_MANIFEST_JSON, manifest)


def _merge_shard_checkpoints(
    rows: list[dict],
    diag_rows: list[dict],
    shard_root: Path,
) -> tuple[int, int, int]:
    """Merge completed worker-local checkpoints into the in-memory run state."""
    if not shard_root.is_dir():
        return (0, 0, 0)

    shards = 0
    added_rows = 0
    added_diag_rows = 0
    for manifest_path in sorted(shard_root.glob(f"*/{SHARD_MANIFEST_JSON}")):
        manifest = _load_existing_manifest(manifest_path)
        metrics_rows = _read_csv_rows(manifest_path.parent / METRICS_CSV)
        diagnostic_rows = _read_csv_rows(
            manifest_path.parent / TARGET_DIAGNOSTICS_CSV
        )
        if manifest.get("n_rows") != len(metrics_rows):
            raise SystemExit(
                "l0 sweep: shard checkpoint row-count mismatch in "
                f"{manifest_path.parent} (manifest={manifest.get('n_rows')!r}, "
                f"loaded={len(metrics_rows)})."
            )
        if manifest.get("n_target_diagnostic_rows") != len(diagnostic_rows):
            raise SystemExit(
                "l0 sweep: shard diagnostic row-count mismatch in "
                f"{manifest_path.parent} "
                f"(manifest={manifest.get('n_target_diagnostic_rows')!r}, "
                f"loaded={len(diagnostic_rows)})."
            )
        shards += 1
        added_rows += _merge_unique_rows(rows, metrics_rows)
        added_diag_rows += _merge_unique_rows(diag_rows, diagnostic_rows)
    return (shards, added_rows, added_diag_rows)


def _validate_resume_checkpoint(
    *,
    manifest: dict,
    rows: list[dict],
    diag_rows: list[dict],
    metrics_path: Path,
    diagnostics_path: Path,
    manifest_path: Path,
) -> None:
    """Reject resume state whose manifest does not certify the loaded CSVs."""
    if not rows and not diag_rows:
        return
    if not manifest:
        raise SystemExit(
            f"l0 sweep: refusing to resume from {metrics_path} / "
            f"{diagnostics_path} because "
            f"{manifest_path} is missing. Pass --no-resume to overwrite."
        )
    expected_rows = manifest.get("n_rows")
    expected_diag_rows = manifest.get("n_target_diagnostic_rows")
    if expected_rows != len(rows) or expected_diag_rows != len(diag_rows):
        raise SystemExit(
            "l0 sweep: refusing to resume from an incomplete checkpoint "
            f"(manifest n_rows={expected_rows!r}, loaded metrics={len(rows)}; "
            f"manifest n_target_diagnostic_rows={expected_diag_rows!r}, "
            f"loaded diagnostics={len(diag_rows)} from {diagnostics_path}). "
            "Pass --no-resume to overwrite or repair the output directory."
        )


def _cell_key(
    *,
    holdout_type: str,
    fold: int,
    seed: int,
    budget: int,
    l2_lambda: float,
) -> CellKey:
    return (holdout_type, int(fold), int(seed), int(budget), float(l2_lambda))


def _cell_key_from_row(row: dict) -> CellKey:
    return _cell_key(
        holdout_type=str(row["holdout_type"]),
        fold=int(float(row["fold"])),
        seed=int(float(row["seed"])),
        budget=int(float(row["budget_requested"])),
        l2_lambda=float(row.get("l2_lambda") or 0.0),
    )


def _method_key(
    *,
    holdout_type: str,
    fold: int,
    seed: int,
    budget: int,
    l2_lambda: float,
    method: str,
) -> MethodKey:
    return (
        holdout_type,
        int(fold),
        int(seed),
        int(budget),
        float(l2_lambda),
        method,
    )


def _method_key_from_row(row: dict) -> MethodKey:
    return _method_key(
        holdout_type=str(row["holdout_type"]),
        fold=int(float(row["fold"])),
        seed=int(float(row["seed"])),
        budget=int(float(row["budget_requested"])),
        l2_lambda=float(row.get("l2_lambda") or 0.0),
        method=str(row["method"]),
    )


def _completed_method_keys(
    rows: list[dict],
    methods: list[str] | None = None,
) -> set[MethodKey]:
    """Return method-level cells with a completed run-level budget marker."""
    requested_methods = set(methods) if methods is not None else None
    completed: set[MethodKey] = set()
    for row in rows:
        if row.get("scope") != "run" or row.get("metric") != "budget_achieved":
            continue
        method = str(row.get("method", ""))
        if requested_methods is not None and method not in requested_methods:
            continue
        try:
            key = _method_key_from_row(row)
        except (KeyError, TypeError, ValueError):
            continue
        completed.add(key)
    return completed


def _budget_achieved_by_method(rows: list[dict]) -> dict[MethodKey, int]:
    """Map completed method-level cells to their achieved record budget."""
    achieved: dict[MethodKey, int] = {}
    for row in rows:
        if row.get("scope") != "run" or row.get("metric") != "budget_achieved":
            continue
        try:
            key = _method_key_from_row(row)
            achieved[key] = int(float(row["value"]))
        except (KeyError, TypeError, ValueError):
            continue
    return achieved


def _completed_cell_keys(rows: list[dict], methods: list[str]) -> set[CellKey]:
    """Return cells that have a completed run metric for every requested method."""
    return _completed_cells_from_methods(_completed_method_keys(rows, methods), methods)


def _completed_cells_from_methods(
    completed_methods: set[MethodKey],
    methods: list[str],
) -> set[CellKey]:
    requested_methods = set(methods)
    methods_by_cell: dict[CellKey, set[str]] = {}
    for holdout_type, fold, seed, budget, l2_lambda, method in completed_methods:
        if method not in requested_methods:
            continue
        key = (holdout_type, fold, seed, budget, l2_lambda)
        methods_by_cell.setdefault(key, set()).add(method)
    return {
        key
        for key, completed_methods in methods_by_cell.items()
        if requested_methods <= completed_methods
    }


def _progress_prefix(
    *,
    holdout_type: str,
    fold: int,
    seed: int,
    budget: int,
    l2_lambda: float,
) -> str:
    return (
        f"[{holdout_type} fold={fold} seed={seed} budget={budget} "
        f"l2={l2_lambda:g}]"
    )


def _l0_budget_progress_logger(
    *,
    holdout_type: str,
    fold: int,
    seed: int,
    budget: int,
    l2_lambda: float,
    started_at: float,
) -> Callable[[dict[str, object]], None]:
    """Print one start/result pair for each Populace L0 budget-search iteration."""
    prefix = _progress_prefix(
        holdout_type=holdout_type,
        fold=fold,
        seed=seed,
        budget=budget,
        l2_lambda=l2_lambda,
    )
    started_iterations: set[int] = set()
    completed_iterations: set[int] = set()

    def log(event: dict[str, object]) -> None:
        if not event.get("budget_search"):
            return
        iteration = int(event.get("budget_iteration") or 0)
        total = int(event.get("budget_iters") or 0)
        epoch = int(event.get("epoch") or 0)
        epochs = int(event.get("epochs") or 0)
        l0_lambda = float(event.get("l0_lambda") or 0.0)
        if iteration <= 0 or epochs <= 0:
            return

        if epoch == 1 and iteration not in started_iterations:
            started_iterations.add(iteration)
            print(
                f"    {prefix} L0 budget iter {iteration}/{total}: "
                f"lambda={l0_lambda:.3e} started.",
                flush=True,
            )
        if epoch == epochs and iteration not in completed_iterations:
            completed_iterations.add(iteration)
            loss = float(event["loss"])
            elapsed = perf_counter() - started_at
            print(
                f"    {prefix} L0 budget iter {iteration}/{total}: "
                f"lambda={l0_lambda:.3e}, loss={loss:.6g}, "
                f"elapsed={elapsed:.1f}s.",
                flush=True,
            )

    return log


def _resume_manifest_mismatches(
    args: argparse.Namespace,
    manifest: dict,
    *,
    precal_dir: Path,
) -> list[str]:
    previous_args = manifest.get("command_args")
    if not isinstance(previous_args, dict):
        return []

    mismatches: list[str] = []
    previous_precal = manifest.get("precalibration_dir")
    if previous_precal is not None:
        previous_precal_path = Path(str(previous_precal)).expanduser().resolve()
        if previous_precal_path != precal_dir:
            mismatches.append(
                f"precalibration_dir: previous={previous_precal_path}, "
                f"current={precal_dir}"
            )

    for key in _RESUME_COMPAT_ARG_KEYS:
        if key not in previous_args:
            continue
        previous = previous_args[key]
        current = str(getattr(args, key))
        if previous != current:
            mismatches.append(f"{key}: previous={previous!r}, current={current!r}")
    return mismatches


def _build_manifest(
    *,
    args: argparse.Namespace,
    status: str,
    run_id: str,
    created_at: str,
    precal_dir: Path,
    precal_manifest: dict,
    target_loss_cap: float,
    frontier_target_loss_weights: np.ndarray,
    baseline_optimizer: dict,
    fit_targets,
    holdout_targets,
    holdout_families: list[str],
    validation_only: set[str],
    frontier_dense_runtimes: dict[str, dict[str, float]],
    rotation_meta: dict,
    rows: list[dict],
    diag_rows: list[dict],
    completed_cells: set[CellKey],
    out: Path,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "created_at": created_at,
        "updated_at": datetime.now(UTC).isoformat(),
        "command_args": {k: str(v) for k, v in vars(args).items()},
        "precalibration_dir": str(precal_dir),
        "precalibration": precal_manifest,
        "grid": {
            "budgets": args.budgets,
            "seeds": args.seeds,
            "epochs": args.epochs,
            "l2_lambdas": args.l2_lambdas,
        },
        "target_loss": {
            "weighting": args.target_loss_weighting,
            "cap": target_loss_cap,
            "frontier_fit_weight_summary": target_loss.target_loss_weight_summary(
                frontier_target_loss_weights
            ),
            "production_source_path": (
                target_loss.production_source_path()
                if args.target_loss_weighting == target_loss.PRODUCTION_US_FISCAL
                else None
            ),
        },
        "l0_optimizer": _jsonable(
            {
                **baseline_optimizer,
                "max_weight_ratio": args.max_weight_ratio,
                "budget_iters": args.budget_iters,
                "l2_lambdas": args.l2_lambdas,
                "l2_applies_to": "informed_l0_only",
            }
        ),
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
        "long_csv": str(out / METRICS_CSV),
        "target_diagnostics_csv": (
            str(out / TARGET_DIAGNOSTICS_CSV) if diag_rows else None
        ),
        "shard_checkpoint_dir": str(out / SHARD_CHECKPOINT_DIR),
        "n_rows": len(rows),
        "n_target_diagnostic_rows": len(diag_rows),
        "completed_cells": len(completed_cells),
    }


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
    l2_lambda: float,
    holdout_type: str,
    fold: int,
    degenerate_fit: set[str] | None = None,
    degenerate_holdout: set[str] | None = None,
    fit_loss_weights: np.ndarray | None = None,
    holdout_loss_weights: np.ndarray | None = None,
    diag_rows: list[dict] | None = None,
) -> None:
    """Score one run in/out-of-sample and append its long-format rows.

    ``degenerate_fit`` / ``degenerate_holdout`` are the denominator-degenerate
    target names (:func:`metrics.degenerate_target_names`) for each split, used to
    emit the targeted-removal sensitivity. When ``diag_rows`` is given, per-target
    diagnostics for the headline (``fixed_family``) split are appended for both
    splits, carrying the raw values plus the production loss weight
    (``fit_loss_weights`` / ``holdout_loss_weights``) so the capped, weighted
    objective can be recomputed downstream (:mod:`l0_paper.experiments.crunch`).
    """
    in_sample = metrics.score(
        frame, run.weights, fit_targets, label="in_sample",
        degenerate_names=degenerate_fit,
    )
    out_of_sample = metrics.score(
        frame, run.weights, holdout_targets, label="out_of_sample",
        degenerate_names=degenerate_holdout,
    )
    holdout_diag = metrics.target_diagnostics(
        frame, run.weights, holdout_targets, loss_weights=holdout_loss_weights
    )
    extreme = aggregate.extreme_are_counts(holdout_diag)
    rows.extend(
        aggregate.rows_from_run(
            method=method,
            seed=seed,
            budget_requested=budget_requested,
            budget_achieved=run.n_selected,
            l2_lambda=l2_lambda,
            holdout_type=holdout_type,
            fold=fold,
            in_sample=in_sample,
            out_of_sample=out_of_sample,
            run=run,
            extra_run_metrics={f"holdout_{k}": v for k, v in extreme.items()},
        )
    )
    if diag_rows is not None and holdout_type == "fixed_family":
        fit_diag = metrics.target_diagnostics(
            frame, run.weights, fit_targets, loss_weights=fit_loss_weights
        )
        diag_rows.extend(
            aggregate.target_diagnostic_rows(
                method=method, l2_lambda=l2_lambda, seed=seed,
                budget_requested=budget_requested,
                split="in_sample", diagnostics=fit_diag,
                degenerate_names=degenerate_fit,
            )
        )
        diag_rows.extend(
            aggregate.target_diagnostic_rows(
                method=method, l2_lambda=l2_lambda, seed=seed,
                budget_requested=budget_requested,
                split="out_of_sample", diagnostics=holdout_diag,
                degenerate_names=degenerate_holdout,
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
    methods: list[str],
    l2_lambda: float,
    target_loss_weighting: str,
    diag_rows: list[dict] | None = None,
    completed_methods: set[MethodKey] | None = None,
    budget_achieved_by_method: dict[MethodKey, int] | None = None,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, float]:
    """Run the selected conditions across budgets x seeds for one (fit, holdout) split.

    Informed L0 (when selected) sets the matched record budget; otherwise the
    requested budget is used directly. Dense calibration is computed once per seed
    and only when ``dense_sample`` is requested. Returns per-seed dense runtimes.
    """
    want_survey = "dense_sample" in methods
    completed_methods = completed_methods if completed_methods is not None else set()
    if budget_achieved_by_method is None:
        budget_achieved_by_method = {}

    # Denominator-degenerate targets are a property of the split (not the run), so
    # compute them once here and reuse across budgets/seeds/methods.
    weight_entity = baseline_optimizer["weight_entity"]
    degenerate_fit = metrics.degenerate_target_names(
        frame, fit_targets, weight_entity=weight_entity
    )
    degenerate_holdout = metrics.degenerate_target_names(
        frame, holdout_targets, weight_entity=weight_entity
    )
    target_loss_weights = target_loss.target_loss_weights(
        fit_targets,
        weighting=target_loss_weighting,
    )
    # Per-target omega for the held-out targets too, so the stored diagnostics carry
    # the production weight on both splits and the weighted objective can be crunched
    # out-of-sample (the optimizer never weighted the holdout; this applies the same
    # production scheme to it for reporting).
    holdout_loss_weights = target_loss.target_loss_weights(
        holdout_targets,
        weighting=target_loss_weighting,
    )
    split_baseline_optimizer = {
        **baseline_optimizer,
        "target_loss_weights": target_loss_weights,
    }
    split_l0_optimizer = {
        **l0_optimizer,
        "target_loss_weights": target_loss_weights,
    }

    dense_runtimes: dict[str, float] = {}
    for seed in seeds:
        pending_methods_by_budget = {
            budget: [
                method
                for method in methods
                if _method_key(
                    holdout_type=holdout_type,
                    fold=fold,
                    seed=seed,
                    budget=budget,
                    l2_lambda=l2_lambda,
                    method=method,
                )
                not in completed_methods
            ]
            for budget in budgets
        }
        pending_budgets = [
            budget for budget, pending in pending_methods_by_budget.items() if pending
        ]
        if not pending_budgets:
            print(
                f"  [{holdout_type} fold={fold} seed={seed} l2={l2_lambda:g}] "
                f"skipping {len(budgets)} completed budget cell(s).",
                flush=True,
            )
            continue

        dense = None
        dense_runtime = 0.0
        needs_dense = want_survey and any(
            "dense_sample" in pending
            for pending in pending_methods_by_budget.values()
        )
        if needs_dense:
            print(
                f"  [{holdout_type} fold={fold} seed={seed} l2={l2_lambda:g}] "
                "calibrating dense baseline once for pending budgets...",
                flush=True,
            )
            dense_start = perf_counter()
            dense, dense_runtime = calibrate_dense(
                frame, fit_targets, seed=seed, **split_baseline_optimizer
            )
            dense_runtimes[str(seed)] = dense_runtime
            print(
                f"  [{holdout_type} fold={fold} seed={seed} l2={l2_lambda:g}] "
                f"dense baseline ready in {perf_counter() - dense_start:.1f}s.",
                flush=True,
            )
        for budget in budgets:
            pending_methods = pending_methods_by_budget[budget]
            if not pending_methods:
                print(
                    f"  [{holdout_type} fold={fold} seed={seed} budget={budget} "
                    f"l2={l2_lambda:g}] skipping completed cell.",
                    flush=True,
                )
                continue

            cell_start = perf_counter()
            cell_label = (
                f"{holdout_type} fold={fold} seed={seed} budget={budget} "
                f"l2={l2_lambda:g}"
            )
            print(
                f"  [{cell_label}] starting {', '.join(pending_methods)}.",
                flush=True,
            )
            runs = []
            l0_key = _method_key(
                holdout_type=holdout_type,
                fold=fold,
                seed=seed,
                budget=budget,
                l2_lambda=l2_lambda,
                method="informed_l0",
            )
            matched = budget_achieved_by_method.get(l0_key, budget)
            if "informed_l0" in pending_methods:
                budget_search_start = perf_counter()
                progress_prefix = _progress_prefix(
                    holdout_type=holdout_type,
                    fold=fold,
                    seed=seed,
                    budget=budget,
                    l2_lambda=l2_lambda,
                )
                print(
                    f"  {progress_prefix} L0 budget search: target={budget:,}, "
                    f"iters={split_l0_optimizer['budget_iters']}, "
                    f"epochs={split_l0_optimizer['epochs']}.",
                    flush=True,
                )
                l0 = run_l0(
                    frame, fit_targets, target_records=budget, seed=seed,
                    progress_callback=_l0_budget_progress_logger(
                        holdout_type=holdout_type,
                        fold=fold,
                        seed=seed,
                        budget=budget,
                        l2_lambda=l2_lambda,
                        started_at=budget_search_start,
                    ),
                    **split_l0_optimizer,
                )
                matched = l0.n_selected
                runs.append(l0)
                print(
                    f"  [{cell_label}] L0 retained {matched:,} "
                    f"(l0_lambda={l0.l0_lambda:.3e})",
                    flush=True,
                )
            elif l0_key in budget_achieved_by_method:
                print(
                    f"  [{cell_label}] reusing completed L0 matched budget {matched:,}.",
                    flush=True,
                )
            else:
                # No L0 to set the budget; match the requested budget directly.
                print(
                    f"  [{cell_label}] baselines at requested budget {matched:,} "
                    "(no L0).",
                    flush=True,
                )
            if "dense_sample" in pending_methods:
                step_start = perf_counter()
                print(
                    f"  [{cell_label}] running dense_sample baseline at matched "
                    f"budget {matched:,}...",
                    flush=True,
                )
                runs.append(sample_from_dense(
                    dense, n_sample=matched, seed=seed, dense_runtime=dense_runtime,
                    max_weight_ratio=split_baseline_optimizer.get("max_weight_ratio"),
                    target_loss_cap=split_baseline_optimizer["target_loss_cap"],
                    **sample_kwargs,
                ))
                print(
                    f"  [{cell_label}] dense_sample baseline finished in "
                    f"{perf_counter() - step_start:.1f}s.",
                    flush=True,
                )
            if "informed_l1" in pending_methods:
                # Convex-sparse selector: proximal L1 at the matched budget, its own
                # bisection on l1_lambda hitting the same retained count as L0.
                step_start = perf_counter()
                print(
                    f"  [{cell_label}] running informed_l1 baseline at matched "
                    f"budget {matched:,}...",
                    flush=True,
                )
                runs.append(run_l1(
                    frame, fit_targets, target_records=matched, seed=seed,
                    **split_baseline_optimizer,
                ))
                print(
                    f"  [{cell_label}] informed_l1 baseline finished in "
                    f"{perf_counter() - step_start:.1f}s.",
                    flush=True,
                )
            if "random_reweight" in pending_methods:
                step_start = perf_counter()
                print(
                    f"  [{cell_label}] running random_reweight baseline at matched "
                    f"budget {matched:,}...",
                    flush=True,
                )
                runs.append(run_random_then_reweight(
                    frame, fit_targets, n_sample=matched, seed=seed,
                    **split_baseline_optimizer,
                ))
                print(
                    f"  [{cell_label}] random_reweight baseline finished in "
                    f"{perf_counter() - step_start:.1f}s.",
                    flush=True,
                )
            for run in runs:
                step_start = perf_counter()
                print(
                    f"  [{cell_label}] scoring {run.method}...",
                    flush=True,
                )
                _score_and_emit(
                    rows, run=run, frame=frame, fit_targets=fit_targets,
                    holdout_targets=holdout_targets, method=run.method, seed=seed,
                    budget_requested=budget, l2_lambda=l2_lambda,
                    holdout_type=holdout_type, fold=fold,
                    degenerate_fit=degenerate_fit, degenerate_holdout=degenerate_holdout,
                    fit_loss_weights=target_loss_weights,
                    holdout_loss_weights=holdout_loss_weights,
                    diag_rows=diag_rows,
                )
                run_key = _method_key(
                    holdout_type=holdout_type,
                    fold=fold,
                    seed=seed,
                    budget=budget,
                    l2_lambda=l2_lambda,
                    method=run.method,
                )
                completed_methods.add(run_key)
                budget_achieved_by_method[run_key] = int(run.n_selected)
                print(
                    f"  [{cell_label}] scored {run.method} in "
                    f"{perf_counter() - step_start:.1f}s.",
                    flush=True,
                )
            if checkpoint is not None:
                step_start = perf_counter()
                print(f"  [{cell_label}] writing checkpoint...", flush=True)
                checkpoint(cell_label)
                print(
                    f"  [{cell_label}] checkpoint written in "
                    f"{perf_counter() - step_start:.1f}s.",
                    flush=True,
                )
            print(
                f"  [{cell_label}] completed in {perf_counter() - cell_start:.1f}s.",
                flush=True,
            )
    return dense_runtimes


def _sweep_split_shard(
    *,
    label: str,
    frame,
    fit_targets,
    holdout_targets,
    budgets: list[int],
    seed: int,
    l0_optimizer: dict,
    baseline_optimizer: dict,
    sample_kwargs: dict,
    holdout_type: str,
    fold: int,
    methods: list[str],
    l2_lambda: float,
    target_loss_weighting: str,
    collect_diagnostics: bool,
    completed_methods: set[MethodKey],
    budget_achieved_by_method: dict[MethodKey, int],
    checkpoint_dir: Path | None = None,
) -> SplitShardResult:
    """Run one independent seed/fold/L2 shard with local row buffers."""
    shard_rows: list[dict] = []
    shard_diag_rows: list[dict] | None = [] if collect_diagnostics else None
    checkpoint_callback = None
    if checkpoint_dir is not None:
        shard_dir = checkpoint_dir / _safe_shard_name(label)

        def checkpoint_callback(_cell_label: str) -> None:
            _write_shard_checkpoint(
                shard_dir,
                label=label,
                rows=shard_rows,
                diag_rows=shard_diag_rows or [],
            )

    dense_runtimes = _sweep_split(
        shard_rows,
        frame=frame,
        fit_targets=fit_targets,
        holdout_targets=holdout_targets,
        budgets=budgets,
        seeds=[seed],
        l0_optimizer=l0_optimizer,
        baseline_optimizer=baseline_optimizer,
        sample_kwargs=sample_kwargs,
        holdout_type=holdout_type,
        fold=fold,
        methods=methods,
        l2_lambda=l2_lambda,
        target_loss_weighting=target_loss_weighting,
        diag_rows=shard_diag_rows,
        completed_methods=set(completed_methods),
        budget_achieved_by_method=dict(budget_achieved_by_method),
        checkpoint=checkpoint_callback,
    )
    if checkpoint_dir is not None and (shard_rows or shard_diag_rows):
        _write_shard_checkpoint(
            checkpoint_dir / _safe_shard_name(label),
            label=label,
            rows=shard_rows,
            diag_rows=shard_diag_rows or [],
        )
    return SplitShardResult(
        label=label,
        rows=shard_rows,
        diag_rows=shard_diag_rows or [],
        dense_runtimes=dense_runtimes,
    )


def _run_sweep_split(
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
    methods: list[str],
    l2_lambda: float,
    target_loss_weighting: str,
    jobs: int,
    diag_rows: list[dict] | None = None,
    completed_methods: set[MethodKey] | None = None,
    budget_achieved_by_method: dict[MethodKey, int] | None = None,
    checkpoint: Callable[[str], None] | None = None,
    shard_checkpoint_root: Path | None = None,
) -> dict[str, float]:
    """Run a split sequentially or as parallel seed/fold/L2 shards.

    ``_sweep_split`` owns the calibration logic. This wrapper only controls
    concurrency and keeps all checkpoint writes in the caller thread.
    """
    completed_methods = completed_methods if completed_methods is not None else set()
    if budget_achieved_by_method is None:
        budget_achieved_by_method = {}
    if jobs <= 1 or len(seeds) <= 1:
        return _sweep_split(
            rows,
            frame=frame,
            fit_targets=fit_targets,
            holdout_targets=holdout_targets,
            budgets=budgets,
            seeds=seeds,
            l0_optimizer=l0_optimizer,
            baseline_optimizer=baseline_optimizer,
            sample_kwargs=sample_kwargs,
            holdout_type=holdout_type,
            fold=fold,
            methods=methods,
            l2_lambda=l2_lambda,
            target_loss_weighting=target_loss_weighting,
            diag_rows=diag_rows,
            completed_methods=completed_methods,
            budget_achieved_by_method=budget_achieved_by_method,
            checkpoint=checkpoint,
        )

    workers = min(jobs, len(seeds))
    print(
        f"Parallel sweep: {holdout_type} fold={fold} l2={l2_lambda:g} "
        f"using {workers} worker(s) across {len(seeds)} seed shard(s).",
        flush=True,
    )
    dense_runtimes: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for seed in seeds:
            label = f"{holdout_type} fold={fold} seed={seed} l2={l2_lambda:g}"
            future = executor.submit(
                _sweep_split_shard,
                label=label,
                frame=frame,
                fit_targets=fit_targets,
                holdout_targets=holdout_targets,
                budgets=budgets,
                seed=seed,
                l0_optimizer=l0_optimizer,
                baseline_optimizer=baseline_optimizer,
                sample_kwargs=sample_kwargs,
                holdout_type=holdout_type,
                fold=fold,
                methods=methods,
                l2_lambda=l2_lambda,
                target_loss_weighting=target_loss_weighting,
                collect_diagnostics=diag_rows is not None,
                completed_methods=completed_methods,
                budget_achieved_by_method=budget_achieved_by_method,
                checkpoint_dir=shard_checkpoint_root,
            )
            futures[future] = label

        for future in as_completed(futures):
            result = future.result()
            rows.extend(result.rows)
            if diag_rows is not None:
                diag_rows.extend(result.diag_rows)
            completed_methods.update(_completed_method_keys(result.rows, methods))
            budget_achieved_by_method.update(_budget_achieved_by_method(result.rows))
            dense_runtimes.update(result.dense_runtimes)
            print(
                f"  [{result.label}] shard merged: {len(result.rows):,} "
                f"metric rows, {len(result.diag_rows):,} diagnostic rows.",
                flush=True,
            )
            if checkpoint is not None and (result.rows or result.diag_rows):
                checkpoint(f"{result.label} shard")
    return dense_runtimes


def main() -> None:
    args = _parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    precal_dir = args.reuse_precalibration.resolve()
    frame, registry = load_precalibration_dataset(precal_dir)
    precal_manifest = json.loads((precal_dir / MANIFEST_JSON).read_text())
    target_loss_cap = target_loss.resolve_target_loss_cap(
        args.target_loss_weighting,
        args.target_loss_cap,
    )

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
        target_loss_cap=target_loss_cap,
    )
    sample_kwargs = dict(
        weight_entity=args.weight_entity,
        reweight=args.sample_reweight,
        replace=args.sample_replace,
    )

    metrics_path = out / METRICS_CSV
    diagnostics_path = out / TARGET_DIAGNOSTICS_CSV
    manifest_path = out / SWEEP_MANIFEST_JSON
    shard_checkpoint_root = out / SHARD_CHECKPOINT_DIR
    existing_manifest = _load_existing_manifest(manifest_path) if args.resume else {}
    rows: list[dict] = _read_csv_rows(metrics_path) if args.resume else []
    # Per-target OOS diagnostics for the headline split.
    diag_rows: list[dict] = _read_csv_rows(diagnostics_path) if args.resume else []
    _validate_resume_checkpoint(
        manifest=existing_manifest,
        rows=rows,
        diag_rows=diag_rows,
        metrics_path=metrics_path,
        diagnostics_path=diagnostics_path,
        manifest_path=manifest_path,
    )
    if args.resume:
        shards, shard_rows, shard_diag_rows = _merge_shard_checkpoints(
            rows, diag_rows, shard_checkpoint_root
        )
        if shards:
            print(
                f"Recovered {shard_rows:,} metric rows and "
                f"{shard_diag_rows:,} diagnostic rows from {shards} "
                f"parallel shard checkpoint(s) in {shard_checkpoint_root}.",
                flush=True,
            )

    if rows and existing_manifest:
        mismatches = _resume_manifest_mismatches(
            args,
            existing_manifest,
            precal_dir=precal_dir,
        )
        if mismatches:
            details = "; ".join(mismatches[:5])
            if len(mismatches) > 5:
                details += f"; and {len(mismatches) - 5} more"
            raise SystemExit(
                "l0 sweep: existing run output is not compatible with this "
                f"resume ({details}). Use a new --out or pass --no-resume to "
                "overwrite the metrics."
            )

    completed_methods = _completed_method_keys(rows)
    budget_achieved = _budget_achieved_by_method(rows)
    completed_cells = _completed_cells_from_methods(completed_methods, args.methods)
    if rows:
        print(
            f"Resuming from {metrics_path}: {len(rows):,} metric rows, "
            f"{len(diag_rows):,} diagnostic rows, "
            f"{len(completed_methods):,} completed method(s), "
            f"{len(completed_cells):,} completed cell(s).",
            flush=True,
        )
    elif not args.resume and metrics_path.exists():
        print(f"Starting fresh and overwriting existing output in {out}.", flush=True)

    run_id = (
        args.run_id
        or existing_manifest.get("run_id")
        or f"sweep-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    )
    created_at = (
        existing_manifest.get("created_at")
        if existing_manifest.get("created_at")
        else datetime.now(UTC).isoformat()
    )

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
    print(f"Methods: {args.methods}")
    print(f"Jobs: {args.jobs}")
    frontier_target_loss_weights = target_loss.target_loss_weights(
        fit_targets,
        weighting=args.target_loss_weighting,
    )
    print(
        "Target loss: "
        f"weighting={args.target_loss_weighting}, cap={target_loss_cap:g}, "
        f"weights={target_loss.target_loss_weight_summary(frontier_target_loss_weights)}"
    )

    frontier_dense_runtimes: dict[str, dict[str, float]] = existing_manifest.get(
        "frontier_dense_runtimes_s",
        {},
    )
    if not isinstance(frontier_dense_runtimes, dict):
        frontier_dense_runtimes = {}
    rotation_meta: dict = {}

    def write_checkpoint(status: str, label: str) -> None:
        completed_cells = _completed_cells_from_methods(completed_methods, args.methods)
        if diag_rows:
            _atomic_write_target_diagnostics_csv(diagnostics_path, diag_rows)
        elif diagnostics_path.exists():
            diagnostics_path.unlink()
        long_csv = _atomic_write_long_csv(metrics_path, rows)
        manifest = _build_manifest(
            args=args,
            status=status,
            run_id=run_id,
            created_at=created_at,
            precal_dir=precal_dir,
            precal_manifest=precal_manifest,
            target_loss_cap=target_loss_cap,
            frontier_target_loss_weights=frontier_target_loss_weights,
            baseline_optimizer=baseline_optimizer,
            fit_targets=fit_targets,
            holdout_targets=holdout_targets,
            holdout_families=holdout_families,
            validation_only=validation_only,
            frontier_dense_runtimes=frontier_dense_runtimes,
            rotation_meta=rotation_meta,
            rows=rows,
            diag_rows=diag_rows,
            completed_cells=completed_cells,
            out=out,
        )
        written_manifest = _atomic_write_manifest(manifest_path, manifest)
        print(
            f"Checkpoint {label}: {len(rows):,} metric rows, "
            f"{len(diag_rows):,} diagnostic rows -> {long_csv}; "
            f"manifest -> {written_manifest}",
            flush=True,
        )

    # One-time audit naming the denominator-degenerate targets (identifiability
    # floor), so the targeted-removal sensitivity is transparent, not a cutoff.
    audit_rows = [
        {"split": split_name, **row}
        for split_name, tset in (("fit", fit_targets), ("holdout", holdout_targets))
        for row in metrics.degenerate_audit(frame, tset, weight_entity=args.weight_entity)
    ]
    if audit_rows:
        audit_path = out / "degenerate_targets.csv"
        with audit_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0].keys()))
            writer.writeheader()
            writer.writerows(audit_rows)
        print(f"Degenerate-target audit: {len(audit_rows)} targets -> {audit_path}")

    for l2_lambda in args.l2_lambdas:
        l0_optimizer = {
            **baseline_optimizer,
            "max_weight_ratio": args.max_weight_ratio,
            "budget_iters": args.budget_iters,
            "l2_lambda": l2_lambda,
        }
        dense_runtimes = _run_sweep_split(
            rows, frame=frame, fit_targets=fit_targets, holdout_targets=holdout_targets,
            budgets=args.budgets, seeds=args.seeds, l0_optimizer=l0_optimizer,
            baseline_optimizer=baseline_optimizer,
            sample_kwargs=sample_kwargs, holdout_type="fixed_family", fold=-1,
            methods=args.methods, l2_lambda=l2_lambda,
            target_loss_weighting=args.target_loss_weighting, jobs=args.jobs,
            diag_rows=diag_rows,
            completed_methods=completed_methods,
            budget_achieved_by_method=budget_achieved,
            shard_checkpoint_root=shard_checkpoint_root,
            checkpoint=lambda label: write_checkpoint("running", label),
        )
        frontier_dense_runtimes.setdefault(str(l2_lambda), {}).update(dense_runtimes)

    # --- Rotation robustness panel: family-grouped k-fold at one anchor budget. ---
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
            "fit_target_loss_weight_summaries": [
                target_loss.target_loss_weight_summary(
                    target_loss.target_loss_weights(
                        fold_fit,
                        weighting=args.target_loss_weighting,
                    )
                )
                for fold_fit, _fold_holdout in folds
            ],
        }
        for fold_idx, (fold_fit, fold_holdout) in enumerate(folds):
            for l2_lambda in args.l2_lambdas:
                l0_optimizer = {
                    **baseline_optimizer,
                    "max_weight_ratio": args.max_weight_ratio,
                    "budget_iters": args.budget_iters,
                    "l2_lambda": l2_lambda,
                }
                _run_sweep_split(
                    rows, frame=frame, fit_targets=fold_fit, holdout_targets=fold_holdout,
                    budgets=[anchor], seeds=args.seeds, l0_optimizer=l0_optimizer,
                    baseline_optimizer=baseline_optimizer,
                    sample_kwargs=sample_kwargs, holdout_type="rotation", fold=fold_idx,
                    methods=args.methods, l2_lambda=l2_lambda,
                    target_loss_weighting=args.target_loss_weighting, jobs=args.jobs,
                    completed_methods=completed_methods,
                    budget_achieved_by_method=budget_achieved,
                    shard_checkpoint_root=shard_checkpoint_root,
                    checkpoint=lambda label: write_checkpoint("running", label),
                )

    # --- Persist: long CSV (source of truth) + reproducibility manifest. ---
    write_checkpoint("complete", "complete")


if __name__ == "__main__":
    main()
