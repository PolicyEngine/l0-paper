# L0 paper

Paper and experiment workspace for PolicyEngine's $L_0$ dataset-reduction work on
the Populace microsimulation data stack.

This repository contains the manuscript, figures, tables, and reproducibility
code for evaluating Hard Concrete / $L_0$ record selection as a way to compress a
large calibrated microsimulation candidate universe into a deployable dataset.
The current manuscript reports the comparison against random and survey-weight
baselines; the experiment package also includes a proximal $L_1$ arm for the
next real-data sweep. The paper is being prepared for IMA 2026 in Brussels:
<https://ima26.brussels/blog/presentation_maria_juaristi/>.

The implementation targets active `PolicyEngine/populace` APIs. Archived
`microplex` and `microplex-us` repositories are mentioned only as historical
migration context.

## Repository layout

```text
l0-paper/
├── src/l0_paper/
│   ├── cli/                 # the `l0` command line (drivers ship in the package)
│   │   ├── sweep.py         #   l0 sweep            multi-budget, multi-seed sweep
│   │   ├── poc.py           #   l0 poc              one-budget run; builds precalibration
│   │   ├── figures.py       #   l0 figures          figures + LaTeX tables from a sweep
│   │   ├── summarize.py     #   l0 summarize        readable summaries from a manifest
│   │   ├── merge_l2.py      #   l0 merge-l2         stitch single-l2 runs together
│   │   ├── build_candidate.py / build_targets.py   #   l0 build-candidate / build-targets
│   │   ├── demo.py          #   l0 demo             whole pipeline on the toy frame (no data)
│   │   └── assets/          #   vendored fonts for the figures
│   ├── experiments/         # library: conditions, metrics, holdout, crunch, aggregate, tables
│   ├── precalibration.py    # freeze Frame + TargetRegistry before calibration
│   ├── populace_smoke.py    # tiny toy Populace frame/targets (used by demo + tests)
│   └── _populace_driver.py  # Populace wiring helpers
├── paper/                   # main.tex, sections/, tables/, figures/, bibliography/
├── tests/                   # offline tests (toy frame); no network, no PolicyEngine-US
├── pyproject.toml           # package metadata, the `l0` entry point, extras, Populace paths
├── uv.lock                  # locked Python environment
└── .github/workflows/ci.yml # pytest + ruff against a pinned Populace commit
```

## The `l0` command line

The experiment drivers ship inside the package, so once the environment is set up
they run as `l0 <command>` (or `uv run l0 <command>`):

```text
l0 demo              run the whole pipeline end-to-end on the toy frame (no data)
l0 paper             current-paper reproduction workflow
l0 poc               single-budget run; builds/reuses the precalibration cache
l0 sweep             budget x seed sweep of the calibration conditions
l0 figures           render figures + LaTeX tables from a sweep's metrics_long.csv
l0 summarize         readable CSV/Markdown summaries from a run manifest
l0 build-candidate   build the candidate-universe precalibration frame
l0 build-targets     build the calibration target bundle from arch-data
l0 merge-l2          merge single-l2 sweep runs into one comparison directory
```

`l0 demo` needs nothing beyond the base install and is what CI runs to exercise
the experiment + figure path; the other commands need the `data`/`viz` extras
and, for the real run, the pinned Populace artifact below.

## Setup

This repository expects to be cloned next to `PolicyEngine/populace`, which
`pyproject.toml` references in editable mode:

```text
PolicyEngine/
  l0-paper/
  populace/
```

```bash
uv sync --all-extras
uv run l0 demo            # toy end-to-end sanity check
uv run pytest
uv run ruff check .
```

Extras: `--extra data` installs the heavy real-data path (`populace-data`,
`policyengine-us`, Hugging Face, H5 I/O); `--extra viz` installs the plotting
dependencies the figure renderers need.

CI checks out `l0-paper` and a pinned `PolicyEngine/populace` commit, then runs
`uv run --locked --extra viz pytest` and `uv run --locked ruff check .`.

## Experiment workflow

The design freezes the expensive pre-calibration input, then varies only the
calibration/sampling method.

```bash
# Full current-paper workflow: build/reuse precalibration, run the sweep, render figures.
uv run --extra data --extra viz l0 paper \
    --consumer-facts data/targets/consumer_facts.jsonl

# Fast real-data smoke: reuse/build the same precalibration, run one small cell.
uv run --extra data --extra viz l0 paper --smoke \
    --consumer-facts data/targets/consumer_facts.jsonl
```

`l0 paper` encodes the current manuscript defaults: budgets
2,000/5,000/10,000/20,000/40,000, seeds 0-2, the fixed held-out families
`cms_medicaid`, `usda_snap`, and `state_income_tax`, target-loss cap `c=10`,
the three reported methods, and the `lambda_L2 in {0, 1e-4}` operability
contrast. Pass `--reuse-precalibration <dir>` to skip the data build, or
`--build-targets --target-base <consumer_facts.jsonl>` to build
`data/targets/consumer_facts.jsonl` first. Lower-level commands (`l0 poc`,
`l0 sweep`, `l0 figures`) remain available for custom runs.

Sweeps checkpoint after every completed budget/seed/fold cell and resume by
default from `metrics_long.csv`; pass `--no-resume` to overwrite an output
directory. `l0 paper --smoke` uses `runs/real-smoke` by default, sets budget
2,000, seed 0, 50 epochs, one budget-bisection step, `lambda_L2=0`, disables
rotation, and skips figure rendering.

Use `--jobs N` to parallelize independent seed/fold/L2 shards. The parent process
still owns checkpoint writes; with `--jobs 1` checkpoints are written after each
budget cell, while parallel runs checkpoint as each shard returns. Keep
PyTorch/BLAS thread counts low to avoid CPU oversubscription, for example:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
uv run --extra data --extra viz l0 paper \
    --reuse-precalibration runs/full/precalibration \
    --out runs/35k-narrow \
    --budgets 2000 10000 40000 \
    --seeds 0 1 2 \
    --jobs 4 \
    --skip-figures
```

For exploratory runs, pass `--methods informed_l0 informed_l1 random_reweight
dense_sample` to include the proximal `informed_l1` baseline, and pass
`--target-loss-cap 1` to use the current production US-fiscal cap.

Methods available in the sweep:

- `informed_l0` — Populace calibration with Hard Concrete gates at a target budget.
- `informed_l1` — the convex-sparse analog: proximal ($L_1$ soft-threshold)
  selection at the matched budget (`method="prox"`, `l1_lambda`).
- `random_reweight` — uniform random subset, then gradient-descent reweighting.
- `dense_sample` — dense calibration, then survey-weight / PPS sampling.

The detailed protocol — metric definitions, holdout design, cap semantics, and
the output schema — is in [`src/l0_paper/cli/README.md`](src/l0_paper/cli/README.md).

## Data and provenance

The candidate universe is the Populace US 2024 household file on Hugging Face
(`policyengine/populace-us`), pinned to snapshot `be80a14f`, built from Populace
commit `6e1bcd0`, H5 SHA-256 beginning `f0af2519`. Target values come from
PolicyEngine Ledger / `arch-data` consumer facts.

The target bundle under `data/targets/` (`consumer_facts.jsonl`,
`base_consumer_facts.jsonl`, `targets_manifest.json`) is **generated, not checked
in** (it is git-ignored). Rebuild it with:

```bash
uv run --extra data l0 build-targets --base /path/to/base/consumer_facts.jsonl
```

## Rendering the paper

The manuscript PDF is Quarto-first:

```bash
quarto render paper/index.qmd
```

`l0 paper --rebuild-pdf` runs the same Quarto render after updating figures and
copies `_output/paper/index.pdf` to `paper/main.pdf`. Use
`--pdf-builder latexmk` only when you need the legacy direct-LaTeX route through
`paper/main.tex`.

The pipeline overview figure is generated separately:

```bash
uv run python paper/figures/populace_pipeline.py
```

## Tests

The suite runs offline on the toy frame (no network, no PolicyEngine-US), and
includes an end-to-end check that the four arms run, the objective crunches, the
figures render, and the `l0` CLI works:

```bash
uv run --extra viz pytest
```
