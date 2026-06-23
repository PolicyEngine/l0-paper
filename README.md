# L0 paper

Paper and experiment workspace for PolicyEngine's $L_0$ dataset-reduction work
on the Populace microsimulation data stack.

This repository contains the manuscript, figures, tables, and reproducibility
code for evaluating Hard Concrete / $L_0$ record selection as a way to compress a
large calibrated microsimulation candidate universe into a deployable dataset.
The paper is being prepared for IMA 2026 in Brussels:
<https://ima26.brussels/blog/presentation_maria_juaristi/>.

The implementation targets active `PolicyEngine/populace` APIs. Archived
`microplex` and `microplex-us` repositories are mentioned only as historical
migration context.

## Repository Layout

```text
l0-paper/
├── data/
│   └── targets/              # generated Ledger fact bundles and target manifest
├── experiments/
│   ├── build_targets.py      # assemble the target fact bundle used by the paper
│   ├── run_poc.py            # one-budget proof-of-concept run
│   ├── run_sweep.py          # multi-budget, multi-seed sweep
│   ├── figures.py            # aggregate sweep outputs into figures/tables
│   ├── summarize_run.py      # inspect individual run manifests
│   ├── runs/                 # generated experiment outputs
│   └── README.md             # detailed experiment protocol
├── paper/
│   ├── main.tex              # LaTeX root used for the current manuscript
│   ├── main.pdf              # compiled manuscript artifact
│   ├── sections/             # manuscript sections
│   ├── tables/               # paper-ready LaTeX tables
│   ├── figures/              # paper figures and selected figure generators
│   ├── bibliography/         # BibTeX references
│   └── index.qmd             # Quarto entry point retained for incremental migration
├── src/l0_paper/
│   ├── precalibration.py     # freeze Frame + TargetRegistry before calibration
│   ├── _populace_driver.py   # small Populace wiring helpers
│   ├── populace_smoke.py     # tiny Populace smoke-calibration path
│   └── experiments/          # calibration conditions, metrics, holdout, tables
├── tests/                    # offline tests for experiment logic and smoke path
├── pyproject.toml            # package metadata, extras, and local Populace paths
├── uv.lock                   # locked Python environment
└── .github/workflows/ci.yml  # pytest + ruff against sibling Populace checkout
```

## Current Artifacts

The current paper figures live in `paper/figures/`:

| Figure | File(s) | Source |
| --- | --- | --- |
| Pipeline overview | `populace_pipeline.png`, `populace_pipeline.py` | Local figure script |
| Frontier | `f1_frontier.pdf/png` | `experiments/figures.py` from sweep outputs |
| Usability | `f2_usability.pdf/png` | `experiments/figures.py` |
| Generalization gap | `f3_generalization_gap.pdf/png` | `experiments/figures.py` |
| Family breakdown | `f4_by_family.pdf/png` | `experiments/figures.py` |
| Cost accuracy | `f5_cost_accuracy.pdf/png` | `experiments/figures.py` |
| Operability | `f6_operability.pdf/png` | `experiments/figures.py` |

`paper/tables/` contains the LaTeX tables currently included by the manuscript.
The expanded three-seed sweep outputs are under `experiments/runs/`; the long
CSV files and sweep manifests are the source of truth for derived figures and
tables.

## Data And Provenance

The calibration candidate universe used in the current manuscript is the
Populace US 2024 household file distributed on Hugging Face as
`policyengine/populace-us`. The paper pins the artifact used in these experiments
to snapshot `be80a14f`, built from Populace commit `6e1bcd0`, with the H5
SHA-256 beginning `f0af2519`.

Target values come from PolicyEngine Ledger / `arch-data` consumer facts. The
checked-in target bundle is under `data/targets/`:

- `consumer_facts.jsonl` - target fact bundle used by the experiments.
- `base_consumer_facts.jsonl` - base bundle before off-year source merge.
- `targets_manifest.json` - provenance for the generated target bundle.

Rebuild the target bundle with:

```bash
uv run python experiments/build_targets.py --base /path/to/base/consumer_facts.jsonl
```

See `experiments/README.md` for the full `arch-data` workflow, off-year target
sources, unsupported target filters, and the distinction between fit targets and
validation-only families.

## Setup

This repository expects to be cloned next to `PolicyEngine/populace`:

```text
PolicyEngine/
  l0-paper/
  populace/
```

`pyproject.toml` points `uv` at the sibling Populace packages in editable mode,
so local tests and experiments use the active Populace checkout.

```bash
uv sync --all-extras --dev
uv run pytest
uv run ruff check .
```

Useful extras:

- `--extra data` installs the heavier real-data path: `populace-data`,
  `policyengine-us`, Hugging Face support, and H5 I/O.
- `--extra viz` installs plotting dependencies for `experiments/figures.py`.

CI checks out both `l0-paper` and `PolicyEngine/populace`, then runs:

```bash
uv run --locked pytest
uv run --locked ruff check .
```

## Experiment Workflow

The experiment design freezes the expensive pre-calibration input, then varies
only the calibration/sampling method.

1. Build or reuse a frozen pre-calibration artifact:

   ```bash
   uv run --extra data python experiments/run_poc.py \
       --ledger-facts data/targets/consumer_facts.jsonl \
       --period 2024 \
       --out experiments/runs/poc \
       --subsample 20000 \
       --target-records 5000 \
       --seed 0
   ```

2. Run the budget sweep from that frozen artifact:

   ```bash
   uv run --extra data python experiments/run_sweep.py \
       --reuse-precalibration experiments/runs/poc/precalibration \
       --out experiments/runs/sweep-moderate \
       --budgets 1000 2000 5000 10000 20000 \
       --seeds 0 1 2 \
       --epochs 1000 \
       --holdout-families state_income_tax \
       --rotation-folds 5 \
       --rotation-budget 5000
   ```

3. Regenerate sweep-derived paper figures and tables:

   ```bash
   uv run --extra viz python experiments/figures.py \
       --sweep experiments/runs/sweep-moderate \
       --paper-figures
   ```

Methods compared by the current sweep:

- `informed_l0`: Populace calibration with Hard Concrete gates and a target
  record budget.
- `random_reweight`: uniform random subset followed by gradient-descent
  reweighting.
- `dense_sample`: dense calibration followed by survey-weight / PPS sampling at
  the matched retained count.

The detailed experiment protocol, metric definitions, holdout design, cap
semantics, and generated output schema are documented in `experiments/README.md`.

## Rendering The Paper

The current manuscript is LaTeX-first:

```bash
cd paper
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

If `latexmk` is available, this is equivalent:

```bash
cd paper
latexmk -pdf main.tex
```

The Quarto entry point is retained at `paper/index.qmd`, but the active compiled
artifact is `paper/main.pdf`.

The pipeline overview figure is generated separately:

```bash
uv run --locked python paper/figures/populace_pipeline.py
```

## Tests

The test suite is designed to run offline. It covers the toy calibration
conditions, metrics, holdout logic, artifact summaries, table rendering, and a
small Populace smoke path.

```bash
uv run --locked pytest
```

Use the real-data commands only when the heavier data dependencies and external
source artifacts are available.
