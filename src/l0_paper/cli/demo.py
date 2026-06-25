"""``l0 demo`` -- run the whole pipeline end-to-end on the toy frame.

No network, no PolicyEngine-US, no restricted data: it builds the in-package toy
frame, runs all four sampling arms across a small budget x seed grid, writes the
long-format and per-target CSVs, crunches the calibration objective, and (unless
``--no-figures``) renders the figure set. This is the smallest faithful exercise
of the experiment + figure path, and what CI runs to prove the CLI works.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from l0_paper.experiments import aggregate, crunch, holdout, metrics, target_loss
from l0_paper.experiments.conditions import (
    run_dense_then_sample,
    run_l0,
    run_l1,
    run_random_then_reweight,
)
from l0_paper.populace_smoke import make_toy_frame, make_toy_targets
from populace.calibrate import Target, TargetSet


def _toy_targets(truths: dict[str, float]) -> TargetSet:
    """Enrich the 3 toy measures into 12 consistent (same-valued) targets."""
    base = list(make_toy_targets(truths))
    return TargetSet(
        tuple(
            Target(name=f"{t.row_name}_{k}", entity=t.entity, measure=t.measure, value=t.value)
            for t in base
            for k in range(4)
        )
    )


def run_demo(
    out_dir: str | Path,
    *,
    budgets: tuple[int, ...] = (40, 80),
    seeds: tuple[int, ...] = (0, 1),
    epochs: int = 60,
    learning_rate: float = 0.15,
    with_figures: bool = True,
) -> dict:
    """Run the four arms on the toy frame and write the run artifacts to ``out_dir``.

    Returns the written paths plus the crunched objective summary, so tests and the
    CLI share one implementation of the toy pipeline.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame, truths = make_toy_frame(seed=0, n=300)
    fit, held = holdout.split_targets(_toy_targets(truths), holdout_frac=0.34, seed=1)
    fit, held = TargetSet(tuple(fit)), TargetSet(tuple(held))
    held_omega = target_loss.target_loss_weights(held, weighting=target_loss.UNIFORM)

    rows: list[dict] = []
    diag_rows: list[dict] = []
    for budget in budgets:
        for seed in seeds:
            l0 = run_l0(frame, fit, target_records=budget, seed=seed, epochs=epochs, learning_rate=learning_rate)
            l1 = run_l1(
                frame, fit, target_records=l0.n_selected, seed=seed,
                epochs=epochs, learning_rate=learning_rate, budget_iters=5,
            )
            dense = run_dense_then_sample(
                frame, fit, n_sample=l0.n_selected, seed=seed, epochs=epochs, learning_rate=learning_rate
            )
            rnd = run_random_then_reweight(
                frame, fit, n_sample=l0.n_selected, seed=seed, epochs=epochs, learning_rate=learning_rate
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
                diag_rows.extend(
                    aggregate.target_diagnostic_rows(
                        method=run.method, seed=seed, budget_requested=budget,
                        split="out_of_sample",
                        diagnostics=metrics.target_diagnostics(
                            frame, run.weights, held, loss_weights=held_omega
                        ),
                    )
                )

    long_csv = aggregate.write_long_csv(out_dir / "metrics_long.csv", rows)
    diag_csv = aggregate.write_target_diagnostics_csv(out_dir / "target_diagnostics_long.csv", diag_rows)
    summary = crunch.summarize(aggregate.load_target_diagnostics(diag_csv), cap=1.0)
    summary.to_csv(out_dir / "objective_summary.csv", index=False)

    figures: list = []
    if with_figures:
        from l0_paper.cli import figures as figures_mod

        report = figures_mod.write_reports(long_csv, out_dir / "report", anchor_budget=max(budgets))
        figures = figures_mod.write_figures(report, out_dir / "report")

    return {"long_csv": long_csv, "diag_csv": diag_csv, "summary": summary, "figures": figures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l0 demo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", type=Path, default=Path("demo-run"), help="Output directory.")
    parser.add_argument("--epochs", type=int, default=60, help="Optimizer epochs per arm.")
    parser.add_argument("--no-figures", action="store_true", help="Skip the figure renderers.")
    args = parser.parse_args(argv)

    result = run_demo(args.out, epochs=args.epochs, with_figures=not args.no_figures)
    cols = ["method", "budget_requested", "objective_capped_weighted", "median_are", "n"]
    print(f"demo run written to {args.out}/")
    print(result["summary"][cols].to_string(index=False))
    if result["figures"]:
        print("figures:", [Path(p).name for p in result["figures"]])
    return 0
