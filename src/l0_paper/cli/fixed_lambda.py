#!/usr/bin/env python
"""Run a fixed-penalty L0 pilot on a frozen Populace precalibration artifact.

This is the quick research loop for the full target-surface question: choose one
``lambda_L0``, let Populace's hard-concrete calibrator decide the retained record
count, then compare post-L0 refit and sample-first reweighting at that achieved
count. Prefer ``--l0-lambda-share`` for the full target surface: it sets the
sparsity penalty as a share of the candidate pool, then converts to Populace's
raw per-record ``l0_lambda``. The command deliberately skips the outer budget
bisection used by ``l0 sweep``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from l0_paper.experiments import aggregate, metrics, target_loss
from l0_paper.experiments.artifacts import (
    _jsonable,
    save_weight_npz,
    write_run_manifest,
)
from l0_paper.experiments.conditions import (
    DEFAULT_EPOCHS,
    DEFAULT_INIT_MEAN,
    DEFAULT_LEARNING_RATE,
    DEFAULT_TEMPERATURE,
    RunResult,
    run_dense_then_sample,
    run_l0,
    run_l0_post_refit,
    run_random_then_reweight,
)
from l0_paper.precalibration import (
    MANIFEST_JSON as PRECALIBRATION_MANIFEST_JSON,
)
from l0_paper.precalibration import (
    load_precalibration_dataset,
)

METRICS_CSV = "metrics_long.csv"
TARGET_DIAGNOSTICS_CSV = "target_diagnostics_long.csv"
MANIFEST_JSON = "fixed_lambda_manifest.json"
WEIGHTS_DIR = "weights"
WEIGHTS_MANIFEST_CSV = "weights_manifest.csv"
WEIGHTS_MANIFEST_COLUMNS = (
    "method",
    "seed",
    "budget_requested",
    "budget_achieved",
    "l2_lambda",
    "holdout_type",
    "fold",
    "artifact_path",
    "weight_entity",
    "candidate_records",
    "n_selected",
    "runtime_s",
    "l0_lambda",
    "final_loss",
    "target_loss_cap",
)

DEFAULT_METHODS = ("informed_l0", "informed_l0_refit", "random_reweight")
HOLDOUT_TYPE = "full_target_surface"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="l0 fixed-lambda",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--reuse-precalibration",
        type=Path,
        required=True,
        help="Frozen precalibration directory built by `l0 paper --skip-sweep`.",
    )
    parser.add_argument("--out", type=Path, required=True)
    l0_group = parser.add_mutually_exclusive_group(required=True)
    l0_group.add_argument(
        "--l0-lambda",
        type=float,
        help="Raw Populace per-record L0 penalty.",
    )
    l0_group.add_argument(
        "--l0-lambda-share",
        type=float,
        help=(
            "Candidate-pool-normalized L0 penalty. The objective is "
            "target_loss + share * expected_open_records / candidate_records, "
            "so the raw Populace l0_lambda is share / candidate_records."
        ),
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--mass", choices=("conserve", "free"), default="conserve")
    parser.add_argument("--weight-entity", default="household")
    parser.add_argument("--init-mean", type=float, default=DEFAULT_INIT_MEAN)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--l2-lambda", type=float, default=0.0)
    parser.add_argument("--max-weight-ratio", type=float, default=None)
    parser.add_argument(
        "--target-loss-weighting",
        choices=target_loss.TARGET_LOSS_WEIGHTINGS,
        default=target_loss.PRODUCTION_US_FISCAL,
    )
    parser.add_argument("--target-loss-cap", type=float, default=None)
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=[
            "informed_l0",
            "informed_l0_refit",
            "random_reweight",
            "dense_sample",
        ],
        default=list(DEFAULT_METHODS),
    )
    parser.add_argument(
        "--sample-reweight", choices=("equal_mass", "renorm_kept"), default="equal_mass"
    )
    parser.add_argument(
        "--sample-replace", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--compute-degenerate",
        action="store_true",
        help="Compute denominator-degenerate target names. This builds another "
        "large constraint matrix, so the pilot leaves it off by default.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Print optimizer progress every N epochs (default: 50).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier recorded in the manifest.",
    )
    args = parser.parse_args(argv)
    if args.l0_lambda is not None and (
        args.l0_lambda <= 0.0 or not np.isfinite(args.l0_lambda)
    ):
        parser.error("--l0-lambda must be positive and finite")
    if args.l0_lambda_share is not None and (
        args.l0_lambda_share <= 0.0 or not np.isfinite(args.l0_lambda_share)
    ):
        parser.error("--l0-lambda-share must be positive and finite")
    if args.epochs < 1:
        parser.error("--epochs must be >= 1")
    if args.progress_every < 1:
        parser.error("--progress-every must be >= 1")
    if "informed_l0_refit" in args.methods and "informed_l0" not in args.methods:
        parser.error("--methods informed_l0_refit requires informed_l0")
    return args


def _resolve_l0_lambda(
    *,
    raw_l0_lambda: float | None,
    l0_lambda_share: float | None,
    candidate_records: int,
) -> tuple[float, float]:
    """Return raw Populace lambda and candidate-pool-normalized share."""
    if candidate_records < 1:
        raise ValueError("candidate_records must be positive")
    if raw_l0_lambda is not None:
        raw = float(raw_l0_lambda)
        if raw <= 0.0 or not np.isfinite(raw):
            raise ValueError("raw_l0_lambda must be positive and finite")
        return raw, raw * candidate_records
    if l0_lambda_share is not None:
        share = float(l0_lambda_share)
        if share <= 0.0 or not np.isfinite(share):
            raise ValueError("l0_lambda_share must be positive and finite")
        return share / candidate_records, share
    raise ValueError("one of raw_l0_lambda or l0_lambda_share is required")


def _progress_logger(label: str, *, every: int):
    started_at = perf_counter()

    def callback(event: dict[str, object]) -> None:
        if event.get("kind") != "calibration_epoch":
            return
        epoch = int(event["epoch"])
        epochs = int(event["epochs"])
        if epoch != 1 and epoch != epochs and epoch % every != 0:
            return
        elapsed = perf_counter() - started_at
        print(
            f"[{label}] epoch {epoch:,}/{epochs:,}: "
            f"loss={float(event['loss']):.8g}, elapsed={elapsed:.1f}s",
            flush=True,
        )

    return callback


def _loss_summary(run: RunResult) -> dict[str, Any]:
    loss = np.asarray(run.loss_trajectory, dtype=np.float64)
    if loss.size == 0:
        return {}
    summary: dict[str, Any] = {
        "epochs": int(loss.size),
        "initial_loss": float(run.initial_loss),
        "final_loss": float(run.final_loss),
        "trajectory_first_loss": float(loss[0]),
        "trajectory_last_loss": float(loss[-1]),
        "trajectory_best_loss": float(np.min(loss)),
        "trajectory_best_epoch": int(np.argmin(loss) + 1),
    }
    for window in (50, 100, 250):
        if loss.size > window:
            previous = float(loss[-window - 1])
            current = float(loss[-1])
            denom = max(abs(previous), 1e-12)
            summary[f"last_{window}_relative_improvement"] = (
                previous - current
            ) / denom
    return summary


def _write_weights_manifest(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(WEIGHTS_MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _weight_artifact_name(method: str, *, seed: int, budget: int, l0_lambda: float) -> str:
    penalty = f"{l0_lambda:.3e}".replace("+", "").replace(".", "p")
    return f"{method}_seed{seed}_budget{budget}_l0{penalty}.npz"


def _score_and_record(
    *,
    run: RunResult,
    method: str,
    frame,
    targets,
    loss_weights: np.ndarray | None,
    degenerate_names: set[str],
    budget_requested: int,
    target_loss_cap: float,
    out: Path,
    rows: list[dict[str, Any]],
    diag_rows: list[dict[str, Any]],
    weight_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    print(
        f"[{method}] scoring {run.n_selected:,} selected record(s); "
        f"final_loss={run.final_loss:.8g}",
        flush=True,
    )
    in_sample = metrics.score(
        frame,
        run.weights,
        targets,
        label="in_sample",
        degenerate_names=degenerate_names,
    )
    fit_diag = metrics.target_diagnostics(
        frame, run.weights, targets, loss_weights=loss_weights
    )
    extreme = aggregate.extreme_are_counts(fit_diag)
    empty_out = metrics.score(frame, run.weights, (), label="out_of_sample")
    rows.extend(
        aggregate.rows_from_run(
            method=method,
            seed=run.seed,
            budget_requested=budget_requested,
            budget_achieved=run.n_selected,
            l2_lambda=run.l2_lambda,
            holdout_type=HOLDOUT_TYPE,
            fold=0,
            in_sample=in_sample,
            out_of_sample=empty_out,
            run=run,
            extra_run_metrics={f"fit_{key}": value for key, value in extreme.items()},
        )
    )
    diag_rows.extend(
        aggregate.target_diagnostic_rows(
            method=method,
            l2_lambda=run.l2_lambda,
            seed=run.seed,
            budget_requested=budget_requested,
            split="in_sample",
            diagnostics=fit_diag,
            degenerate_names=degenerate_names,
        )
    )
    artifact_path = out / WEIGHTS_DIR / _weight_artifact_name(
        method, seed=run.seed, budget=budget_requested, l0_lambda=run.l0_lambda
    )
    save_weight_npz(
        artifact_path,
        run,
        metadata={
            "method": method,
            "seed": run.seed,
            "budget_requested": budget_requested,
            "budget_achieved": run.n_selected,
            "holdout_type": HOLDOUT_TYPE,
            "fold": 0,
            "weight_entity": run.weight_entity,
            "candidate_records": run.n_records,
            "n_selected": run.n_selected,
            "l0_lambda": run.l0_lambda,
            "l2_lambda": run.l2_lambda,
            "runtime_s": run.runtime_s,
            "final_loss": run.final_loss,
            "target_loss_cap": target_loss_cap,
            "solver_options": run.options,
            "sampling": run.sampling,
            "fit_target_count": len(targets),
        },
    )
    weight_rows.append(
        {
            "method": method,
            "seed": int(run.seed),
            "budget_requested": int(budget_requested),
            "budget_achieved": int(run.n_selected),
            "l2_lambda": float(run.l2_lambda),
            "holdout_type": HOLDOUT_TYPE,
            "fold": 0,
            "artifact_path": str(artifact_path.relative_to(out)),
            "weight_entity": run.weight_entity,
            "candidate_records": int(run.n_records),
            "n_selected": int(run.n_selected),
            "runtime_s": float(run.runtime_s),
            "l0_lambda": float(run.l0_lambda),
            "final_loss": float(run.final_loss),
            "target_loss_cap": float(target_loss_cap),
        }
    )
    return {
        "method": method,
        "n_selected": int(run.n_selected),
        "runtime_s": float(run.runtime_s),
        "final_loss": float(run.final_loss),
        "mean_are": in_sample.get("mean_are"),
        "median_are": in_sample.get("median_are"),
        "ess": in_sample.get("ess"),
        "loss_summary": _loss_summary(run),
        "sampling": _jsonable(run.sampling),
        "artifact_path": str(artifact_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    precal_dir = args.reuse_precalibration.expanduser().resolve()
    frame, registry = load_precalibration_dataset(precal_dir)
    candidate_records = int(frame.n(args.weight_entity))
    l0_lambda_raw, l0_lambda_share = _resolve_l0_lambda(
        raw_l0_lambda=args.l0_lambda,
        l0_lambda_share=args.l0_lambda_share,
        candidate_records=candidate_records,
    )
    precal_manifest = json.loads(
        (precal_dir / PRECALIBRATION_MANIFEST_JSON).read_text()
    )
    targets = registry.to_target_set()
    target_loss_cap = target_loss.resolve_target_loss_cap(
        args.target_loss_weighting, args.target_loss_cap
    )
    loss_weights = target_loss.target_loss_weights(
        targets, weighting=args.target_loss_weighting
    )
    run_id = args.run_id or f"fixed-lambda-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"

    print(
        f"Fixed-lambda pilot: {candidate_records:,} "
        f"{args.weight_entity} records, {len(targets):,} target(s), "
        f"lambda_L0_raw={l0_lambda_raw:g}, "
        f"lambda_L0_share={l0_lambda_share:g}, epochs={args.epochs:,}, "
        f"methods={args.methods}.",
        flush=True,
    )
    print(
        f"Target loss: weighting={args.target_loss_weighting}, "
        f"cap={target_loss_cap:g}.",
        flush=True,
    )

    degenerate_names: set[str] = set()
    if args.compute_degenerate:
        print("Computing denominator-degenerate target names...", flush=True)
        degenerate_names = metrics.degenerate_target_names(
            frame, targets, weight_entity=args.weight_entity
        )
        print(f"Degenerate targets: {len(degenerate_names):,}.", flush=True)

    rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    print("[informed_l0] starting fixed-penalty calibration...", flush=True)
    l0 = run_l0(
        frame,
        targets,
        weight_entity=args.weight_entity,
        target_records=None,
        seed=args.seed,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        mass=args.mass,
        max_weight_ratio=args.max_weight_ratio,
        l0_lambda=l0_lambda_raw,
        l2_lambda=args.l2_lambda,
        init_mean=args.init_mean,
        temperature=args.temperature,
        target_loss_weights=loss_weights,
        target_loss_cap=target_loss_cap,
        progress_callback=_progress_logger(
            "informed_l0", every=args.progress_every
        ),
    )
    matched_budget = int(l0.n_selected)
    summaries.append(
        _score_and_record(
            run=l0,
            method="informed_l0",
            frame=frame,
            targets=targets,
            loss_weights=loss_weights,
            degenerate_names=degenerate_names,
            budget_requested=matched_budget,
            target_loss_cap=target_loss_cap,
            out=out,
            rows=rows,
            diag_rows=diag_rows,
            weight_rows=weight_rows,
        )
    )

    if "informed_l0_refit" in args.methods:
        print(
            f"[informed_l0_refit] refitting {matched_budget:,} L0-selected "
            "record(s)...",
            flush=True,
        )
        refit = run_l0_post_refit(
            frame,
            targets,
            l0,
            weight_entity=args.weight_entity,
            seed=args.seed,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            mass=args.mass,
            max_weight_ratio=args.max_weight_ratio,
            target_loss_weights=loss_weights,
            target_loss_cap=target_loss_cap,
            progress_callback=_progress_logger(
                "informed_l0_refit", every=args.progress_every
            ),
        )
        summaries.append(
            _score_and_record(
                run=refit,
                method="informed_l0_refit",
                frame=frame,
                targets=targets,
                loss_weights=loss_weights,
                degenerate_names=degenerate_names,
                budget_requested=matched_budget,
                target_loss_cap=target_loss_cap,
                out=out,
                rows=rows,
                diag_rows=diag_rows,
                weight_rows=weight_rows,
            )
        )

    if "random_reweight" in args.methods:
        print(
            f"[random_reweight] sampling {matched_budget:,} record(s), then "
            "dense-reweighting the subset...",
            flush=True,
        )
        random_reweight = run_random_then_reweight(
            frame,
            targets,
            weight_entity=args.weight_entity,
            n_sample=matched_budget,
            seed=args.seed,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            mass="free",
            max_weight_ratio=args.max_weight_ratio,
            target_loss_weights=loss_weights,
            target_loss_cap=target_loss_cap,
            progress_callback=_progress_logger(
                "random_reweight", every=args.progress_every
            ),
        )
        summaries.append(
            _score_and_record(
                run=random_reweight,
                method="random_reweight",
                frame=frame,
                targets=targets,
                loss_weights=loss_weights,
                degenerate_names=degenerate_names,
                budget_requested=matched_budget,
                target_loss_cap=target_loss_cap,
                out=out,
                rows=rows,
                diag_rows=diag_rows,
                weight_rows=weight_rows,
            )
        )

    if "dense_sample" in args.methods:
        print(
            f"[dense_sample] dense-calibrating full frame, then drawing "
            f"{matched_budget:,} PPS sample(s)...",
            flush=True,
        )
        dense_sample = run_dense_then_sample(
            frame,
            targets,
            weight_entity=args.weight_entity,
            n_sample=matched_budget,
            seed=args.seed,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            mass=args.mass,
            max_weight_ratio=args.max_weight_ratio,
            target_loss_weights=loss_weights,
            target_loss_cap=target_loss_cap,
            replace=args.sample_replace,
            reweight=args.sample_reweight,
            progress_callback=_progress_logger("dense_sample", every=args.progress_every),
        )
        summaries.append(
            _score_and_record(
                run=dense_sample,
                method="dense_sample",
                frame=frame,
                targets=targets,
                loss_weights=loss_weights,
                degenerate_names=degenerate_names,
                budget_requested=matched_budget,
                target_loss_cap=target_loss_cap,
                out=out,
                rows=rows,
                diag_rows=diag_rows,
                weight_rows=weight_rows,
            )
        )

    metrics_path = aggregate.write_long_csv(out / METRICS_CSV, rows)
    diagnostics_path = aggregate.write_target_diagnostics_csv(
        out / TARGET_DIAGNOSTICS_CSV, diag_rows
    )
    weights_manifest_path = _write_weights_manifest(
        out / WEIGHTS_MANIFEST_CSV, weight_rows
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "precalibration": {
            "directory": str(precal_dir),
            "manifest": precal_manifest,
        },
        "args": _jsonable(vars(args)),
        "l0_penalty": {
            "raw_l0_lambda": float(l0_lambda_raw),
            "l0_lambda_share": float(l0_lambda_share),
            "scale": (
                "target_loss + l0_lambda_share * "
                "expected_open_records / candidate_records"
            ),
            "candidate_records": int(candidate_records),
        },
        "frontier_split": {
            "full_target_surface": True,
            "fit": len(targets),
            "holdout": 0,
        },
        "target_loss": {
            "weighting": args.target_loss_weighting,
            "cap": target_loss_cap,
            "weights": target_loss.target_loss_weight_summary(loss_weights),
            "production_source_path": (
                target_loss.production_source_path()
                if args.target_loss_weighting == target_loss.PRODUCTION_US_FISCAL
                else None
            ),
        },
        "matched_budget": matched_budget,
        "summaries": summaries,
        "long_csv": str(metrics_path),
        "target_diagnostics_csv": str(diagnostics_path),
        "weights_dir": str(out / WEIGHTS_DIR),
        "weights_manifest_csv": str(weights_manifest_path),
        "n_rows": len(rows),
        "n_target_diagnostic_rows": len(diag_rows),
        "n_weight_artifact_rows": len(weight_rows),
    }
    write_run_manifest(out / MANIFEST_JSON, manifest)

    print("Fixed-lambda pilot complete.", flush=True)
    for summary in summaries:
        print(
            f"  {summary['method']}: final_loss={summary['final_loss']:.8g}, "
            f"selected={summary['n_selected']:,}, "
            f"mean_are={summary['mean_are']}, median_are={summary['median_are']}, "
            f"ess={summary['ess']}, runtime_s={summary['runtime_s']:.1f}",
            flush=True,
        )
    print(f"Manifest: {out / MANIFEST_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
