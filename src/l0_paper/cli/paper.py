#!/usr/bin/env python
"""Run the current-paper real-data reproduction workflow.

This is the one-command wrapper around the paper pipeline:

1. optionally build ``data/targets/consumer_facts.jsonl`` with ``l0 build-targets``;
2. build or reuse a frozen pre-calibration artifact;
3. run the current manuscript's sweep defaults; and
4. render the report tables and figures.

The defaults encode the manuscript run: budgets 2k/5k/10k/20k/40k, seeds 0--2,
fixed holdout families ``cms_medicaid``, ``usda_snap``, and
``state_income_tax``, validation-only families held out, target-loss cap
``c=10``, the three reported methods, and the L2 operability contrast
``lambda_L2 in {0, 1e-4}``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from l0_paper.experiments import target_loss
from l0_paper.precalibration import MANIFEST_JSON, _sha256

PAPER_BUDGETS = (2_000, 5_000, 10_000, 20_000, 40_000)
PAPER_SEEDS = (0, 1, 2)
PAPER_HOLDOUT_FAMILIES = ("cms_medicaid", "usda_snap", "state_income_tax")
PAPER_METHODS = ("informed_l0", "random_reweight", "dense_sample")
PAPER_L2_LAMBDAS = (0.0, 1e-4)
DEFAULT_OUT = Path("runs/weighted-loss-3seed")
DEFAULT_RUN_ID = "weighted-loss-3seed"
SMOKE_OUT = Path("runs/real-smoke")
SMOKE_RUN_ID = "real-smoke"
DEFAULT_CONSUMER_FACTS = Path("data/targets/consumer_facts.jsonl")
DEFAULT_QUARTO_PDF = Path("_output/paper/index.pdf")
DEFAULT_PAPER_PDF = Path("paper/main.pdf")
PAPER_BASE_REPO_ID = "policyengine/populace-us"
PAPER_BASE_FILENAME = "populace_us_2024.h5"
PAPER_BASE_REVISION = "be80a14f5ac24d726d2dddb7da78c55570515aa3"
PAPER_BASE_H5_SHA256 = (
    "f0af25192d6c8a7efc2638da2bd8ec4278b066a1092cc89ef2275811efaff11d"
)


def _call_cli(label: str, main: Callable[[], object], args: Sequence[object]) -> None:
    """Call another argparse-backed CLI module without spawning a new Python."""
    saved = sys.argv
    sys.argv = [label, *(str(arg) for arg in args)]
    try:
        main()
    finally:
        sys.argv = saved


def _extend_option(argv: list[str], name: str, values: Sequence[object]) -> None:
    argv.append(name)
    argv.extend(str(value) for value in values)


def _arg_was_provided(argv: Sequence[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in argv)


def _apply_smoke_defaults(
    args: argparse.Namespace,
    *,
    out_was_provided: bool,
    run_id_was_provided: bool,
) -> None:
    """Mutate parsed args into the small real-data smoke preset."""
    if not out_was_provided:
        args.out = SMOKE_OUT
    if not run_id_was_provided:
        args.run_id = SMOKE_RUN_ID
    args.budgets = [2_000]
    args.seeds = [0]
    args.epochs = 50
    args.budget_iters = 1
    args.l2_lambdas = [0.0]
    args.rotation_folds = 1
    args.skip_figures = True


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    out_was_provided = _arg_was_provided(raw_argv, "--out")
    run_id_was_provided = _arg_was_provided(raw_argv, "--run-id")
    parser = argparse.ArgumentParser(
        prog="l0 paper",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"Workflow output directory (default: {DEFAULT_OUT}).")
    parser.add_argument("--consumer-facts", type=Path, default=DEFAULT_CONSUMER_FACTS,
                        help=f"consumer_facts.jsonl path (default: {DEFAULT_CONSUMER_FACTS}).")
    parser.add_argument("--reuse-precalibration", type=Path, default=None,
                        help="Existing frozen precalibration directory. Skips facts/base-frame build.")
    parser.add_argument("--base-h5", type=Path, default=None,
                        help="Candidate frame for precalibration (default: Populace HF frame).")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use a one-cell real-data smoke preset: budget 2k, seed 0, "
        "50 epochs, one budget iteration, no rotation, and no figure render.",
    )

    # Optional target bundle build.
    parser.add_argument("--build-targets", action="store_true",
                        help="Build --consumer-facts first by running l0 build-targets.")
    target_src = parser.add_mutually_exclusive_group()
    target_src.add_argument("--target-base", type=Path,
                            help="Existing default-source consumer_facts.jsonl for l0 build-targets --base.")
    target_src.add_argument("--build-target-base", action="store_true",
                            help="Let l0 build-targets build the default-source base bundle.")
    parser.add_argument("--arch-repo", type=Path, default=None,
                        help="arch-data checkout for --build-targets (default: sibling ../arch-data).")
    parser.add_argument("--target-year", type=int, default=2023,
                        help="Base source year for l0 build-targets (default: 2023).")
    parser.add_argument("--target-workdir", type=Path, default=None,
                        help="Scratch directory for l0 build-targets.")

    # Precalibration build settings.
    parser.add_argument("--period", type=int, default=2024)
    parser.add_argument("--reset-weights", choices=("uniform", "keep"), default="uniform")
    parser.add_argument("--weight-entity", default="household")
    parser.add_argument("--subsample", type=int, default=None,
                        help="Optional household subsample for smoke runs. Omit for paper reproduction.")
    parser.add_argument("--allow-partial-facts", action="store_true",
                        help="Tolerate partial facts; for smoke runs, not paper reproduction.")
    parser.add_argument("--keep-unsupported-targets", action="store_true",
                        help="Keep unsupported ledger-filter targets and fail if materialization cannot handle them.")

    # Sweep defaults.
    parser.add_argument("--budgets", type=int, nargs="+", default=list(PAPER_BUDGETS))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(PAPER_SEEDS))
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--mass", choices=("conserve", "free"), default="conserve")
    parser.add_argument("--budget-iters", type=int, default=8)
    parser.add_argument("--target-loss-weighting",
                        choices=target_loss.TARGET_LOSS_WEIGHTINGS,
                        default=target_loss.PRODUCTION_US_FISCAL)
    parser.add_argument("--target-loss-cap", type=float, default=10.0)
    parser.add_argument("--l2-lambdas", type=float, nargs="+", default=list(PAPER_L2_LAMBDAS))
    parser.add_argument("--max-weight-ratio", type=float, default=None)
    parser.add_argument("--holdout-families", nargs="*", default=list(PAPER_HOLDOUT_FAMILIES))
    parser.add_argument("--holdout-frac", type=float, default=0.0)
    parser.add_argument("--fit-validation-only", action="store_true")
    parser.add_argument("--rotation-folds", type=int, default=5)
    parser.add_argument("--rotation-budget", type=int, default=10_000)
    parser.add_argument("--rotation-balance", choices=("target_count", "family"),
                        default="target_count")
    parser.add_argument("--rotation-seed", type=int, default=0)
    parser.add_argument("--methods", nargs="+",
                        choices=["informed_l0", "informed_l1", "random_reweight", "dense_sample"],
                        default=list(PAPER_METHODS))
    parser.add_argument("--sample-reweight", choices=("equal_mass", "renorm_kept"),
                        default="equal_mass")
    parser.add_argument("--sample-replace", action=argparse.BooleanOptionalAction,
                        default=True)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Resume an interrupted sweep in --out (default: yes).")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)

    # Outputs.
    parser.add_argument("--skip-sweep", action="store_true",
                        help="Only prepare/reuse the precalibration artifact.")
    parser.add_argument("--skip-figures", action="store_true",
                        help="Run the sweep but do not render report figures/tables.")
    parser.add_argument("--paper-figures", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Copy rendered PNG figures into paper/figures (default: yes).")
    parser.add_argument("--rebuild-pdf", action="store_true",
                        help="Render the paper PDF after rendering figures.")
    parser.add_argument("--pdf-builder", choices=("quarto", "latexmk"), default="quarto",
                        help="PDF builder for --rebuild-pdf (default: quarto).")
    parser.add_argument("--pdf-output", type=Path, default=DEFAULT_PAPER_PDF,
                        help=f"Path to copy the rendered PDF to (default: {DEFAULT_PAPER_PDF}).")
    args = parser.parse_args(argv)
    if args.smoke:
        _apply_smoke_defaults(
            args,
            out_was_provided=out_was_provided,
            run_id_was_provided=run_id_was_provided,
        )
    return args


def _maybe_build_targets(args: argparse.Namespace) -> Path:
    facts = args.consumer_facts.expanduser()
    if args.reuse_precalibration is not None:
        return facts
    if args.build_targets:
        if args.target_base is None and not args.build_target_base:
            raise SystemExit(
                "l0 paper: --build-targets requires either --target-base or "
                "--build-target-base."
            )
        from l0_paper.cli import build_targets

        build_args: list[object] = ["--out", facts]
        if args.arch_repo is not None:
            build_args.extend(["--arch-repo", args.arch_repo])
        if args.target_base is not None:
            build_args.extend(["--base", args.target_base])
        else:
            build_args.append("--build-base")
        build_args.extend(["--year", args.target_year])
        if args.target_workdir is not None:
            build_args.extend(["--workdir", args.target_workdir])
        _call_cli("l0 build-targets", build_targets.main, build_args)
    elif not facts.is_file():
        raise SystemExit(
            f"l0 paper: consumer facts not found: {facts}. Provide --consumer-facts, pass "
            "--reuse-precalibration, or add --build-targets with --target-base "
            "or --build-target-base."
        )
    return facts


def _prepare_precalibration(args: argparse.Namespace, facts: Path) -> Path:
    if args.reuse_precalibration is not None:
        precal_dir = args.reuse_precalibration.expanduser()
        manifest = precal_dir / MANIFEST_JSON
        if not manifest.is_file():
            raise FileNotFoundError(f"precalibration manifest not found: {manifest}")
        print(f"Reusing precalibration: {precal_dir}")
        return precal_dir

    from l0_paper.precalibration import build_precalibration_dataset

    precal_dir = args.out / "precalibration"
    manifest = precal_dir / MANIFEST_JSON
    if manifest.is_file():
        _validate_implicit_precalibration_reuse(args, facts, manifest)
        print(f"Reusing existing precalibration: {precal_dir}")
        return precal_dir

    print(f"Building precalibration -> {precal_dir}")
    base_h5 = _base_h5_for_build(args)
    artifact = build_precalibration_dataset(
        ledger_facts=facts,
        out_dir=precal_dir,
        base_h5=base_h5,
        period=args.period,
        reset_weights=args.reset_weights,
        weight_entity=args.weight_entity,
        subsample=args.subsample,
        subsample_seed=args.seeds[0],
        allow_partial_facts=args.allow_partial_facts,
        drop_unsupported_filters=not args.keep_unsupported_targets,
    )
    return artifact.directory


def _base_h5_for_build(args: argparse.Namespace) -> Path:
    if args.base_h5 is not None:
        return args.base_h5.expanduser()
    from huggingface_hub import hf_hub_download

    path = Path(
        hf_hub_download(
            repo_id=PAPER_BASE_REPO_ID,
            filename=PAPER_BASE_FILENAME,
            repo_type="dataset",
            revision=PAPER_BASE_REVISION,
        )
    )
    actual = _sha256(path)
    if actual != PAPER_BASE_H5_SHA256:
        raise SystemExit(
            "l0 paper: downloaded paper base frame hash mismatch "
            f"(expected {PAPER_BASE_H5_SHA256}, got {actual})."
        )
    return path


def _validate_implicit_precalibration_reuse(
    args: argparse.Namespace, facts: Path, manifest_path: Path
) -> None:
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "period": args.period,
        "weight_entity": args.weight_entity,
        "reset_weights": args.reset_weights,
        "subsample": args.subsample,
        "subsample_seed": args.seeds[0] if args.subsample is not None else None,
        "allow_partial_facts": args.allow_partial_facts,
        "drop_unsupported_filters": not args.keep_unsupported_targets,
        "ledger_facts_sha256": _sha256(facts.expanduser().resolve()),
    }
    expected["base_h5_sha256"] = (
        _sha256(args.base_h5.expanduser().resolve())
        if args.base_h5 is not None
        else PAPER_BASE_H5_SHA256
    )

    mismatches = [
        f"{key}: manifest={manifest.get(key)!r}, requested={value!r}"
        for key, value in expected.items()
        if manifest.get(key) != value
    ]
    if mismatches:
        details = "; ".join(mismatches[:4])
        if len(mismatches) > 4:
            details += f"; and {len(mismatches) - 4} more"
        raise SystemExit(
            f"l0 paper: existing precalibration at {manifest_path.parent} does not "
            f"match this run ({details}). Delete that directory, choose a new --out, "
            "or pass --reuse-precalibration explicitly if this mismatch is intended."
        )


def _run_sweep(args: argparse.Namespace, precal_dir: Path) -> None:
    from l0_paper.cli import sweep

    sweep_args: list[object] = [
        "--reuse-precalibration", precal_dir,
        "--out", args.out,
        "--weight-entity", args.weight_entity,
        "--epochs", args.epochs,
        "--learning-rate", args.learning_rate,
        "--mass", args.mass,
        "--budget-iters", args.budget_iters,
        "--target-loss-weighting", args.target_loss_weighting,
        "--target-loss-cap", args.target_loss_cap,
        "--holdout-frac", args.holdout_frac,
        "--rotation-folds", args.rotation_folds,
        "--rotation-budget", args.rotation_budget,
        "--rotation-balance", args.rotation_balance,
        "--rotation-seed", args.rotation_seed,
        "--sample-reweight", args.sample_reweight,
        "--run-id", args.run_id,
    ]
    _extend_option(sweep_args, "--budgets", args.budgets)
    _extend_option(sweep_args, "--seeds", args.seeds)
    _extend_option(sweep_args, "--l2-lambdas", args.l2_lambdas)
    _extend_option(sweep_args, "--holdout-families", args.holdout_families)
    if args.max_weight_ratio is not None:
        sweep_args.extend(["--max-weight-ratio", args.max_weight_ratio])
    if args.fit_validation_only:
        sweep_args.append("--fit-validation-only")
    if not args.sample_replace:
        sweep_args.append("--no-sample-replace")
    sweep_args.append("--resume" if args.resume else "--no-resume")
    _extend_option(sweep_args, "--methods", args.methods)

    _call_cli("l0 sweep", sweep.main, sweep_args)


def _render_figures(args: argparse.Namespace) -> None:
    from l0_paper.cli import figures

    figure_args: list[object] = [
        "--sweep", args.out,
        "--anchor-budget", args.rotation_budget,
    ]
    if args.paper_figures:
        figure_args.append("--paper-figures")
    _call_cli("l0 figures", figures.main, figure_args)


def _copy_pdf(rendered: Path, output: Path) -> None:
    if not rendered.is_file():
        raise FileNotFoundError(f"rendered PDF not found: {rendered}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if rendered.resolve(strict=False) == output.resolve(strict=False):
        return
    shutil.copy2(rendered, output)
    print(f"Copied PDF -> {output}")


def _rebuild_pdf(args: argparse.Namespace) -> None:
    if args.pdf_builder == "quarto":
        subprocess.run(["quarto", "render", "paper/index.qmd"], check=True)
        _copy_pdf(DEFAULT_QUARTO_PDF, args.pdf_output.expanduser())
        return

    subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
        cwd=Path("paper"),
        check=True,
    )
    _copy_pdf(Path("paper/main.pdf"), args.pdf_output.expanduser())


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    args.out = args.out.expanduser()

    facts = _maybe_build_targets(args)
    args.out.mkdir(parents=True, exist_ok=True)
    precal_dir = _prepare_precalibration(args, facts)
    if args.skip_sweep:
        print(f"Prepared precalibration: {precal_dir}")
        return 0

    _run_sweep(args, precal_dir)
    if not args.skip_figures:
        _render_figures(args)
    if args.rebuild_pdf:
        _rebuild_pdf(args)
    print(f"Paper reproduction workflow complete: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
