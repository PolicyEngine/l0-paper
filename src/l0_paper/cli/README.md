# Experiments

Populace-backed calibration experiments for the L0 paper.

The design separates **building the dataset** (everything PolicyEngine's Populace
pipeline does *except* calibration) from **running calibration routines** on it,
so the calibration method is the only thing that varies between conditions.

## The pre-calibration boundary

`populace/tools/build_us_fiscal_refresh_release.py` builds the production dataset
as: resolve Ledger facts into a target registry → load the base frame →
materialize the target measures → **calibrate**. We freeze the dataset at the step
*before* `calibrate`: the materialized `(Frame, TargetRegistry)` pair, written by
[`l0_paper.precalibration`](../precalibration.py) as a pickle +
`registry.json` + `precalibration_manifest.json`. Every experiment loads this one
frozen artifact.

## Calibration conditions

[`l0_paper.experiments.conditions`](../experiments/conditions.py):

1. **Informed L0** (`run_l0`) — `calibrate(..., target_records=N)` jointly fits
   weights and Hard-Concrete gates to retain ~N records.
2. **Informed L1** (`run_l1`) — proximal L1 soft-thresholding
   (`method="prox"`, `l1_lambda`) selects an exact-zero sparse subset at the
   matched budget. The code path is wired for the next real-data sweep; the
   current manuscript's committed figures and tables predate those results.
3. **Survey-weight sampling** (`run_dense_then_sample`) — calibrate-then-reduce:
   `calibrate(..., target_records=None, l0_lambda=0.0)` fits all weights, then
   draws a **probability-proportional (PPS) random** sample of `n` (the L0
   retained count), each record drawn with probability ∝ its fitted weight, and
   reweights it (integerisation). This is the paper's method 3 — it is *not*
   "keep the largest weights" (that would be deterministic top-weight selection).
4. **Random + reweight** (`run_random_then_reweight`) — reduce-first: draw a
   **uniform** (equal-probability) random subset of size `n`, weight it up to the
   population total, then reweight just that subset to the targets by gradient
   descent (gates off). The paper's method 2.

All four return a full-length weight vector (zero for unretained records), scored
in- and out-of-sample by [`metrics`](../experiments/metrics.py) with
targets held out via [`holdout`](../experiments/holdout.py). The current paper
tables report the three real-data arms that have been run: informed L0,
random + reweight, and survey-weight sampling.

## Getting the Ledger facts file

Target values come from a PolicyEngine Ledger `consumer_facts.jsonl`, produced by
**`PolicyEngine/arch-data`** (namespace `arch` / `policyengine_ledger`):

- A small stand-in may be available in an `arch-data` checkout as
  `arch/fixtures/consumer_facts.jsonl` (real schema, partial coverage — use with
  `--allow-partial-facts`). It is not committed in this repository.
- A default-source base bundle is emitted in one call from a clone of
  `PolicyEngine/arch-data`:

  ```bash
  uv run arch build-bundle --year 2023 --out /tmp/arch-us-2024 --replace
  # writes /tmp/arch-us-2024/consumer_facts.jsonl  (+ coverage.json, reports/)
  ```

  `build-bundle` uses the requested literal `--year` when it looks up source
  artifacts. That makes it a useful default-source base bundle, but not the
  complete paper feed: sources whose artifacts are pinned to another year are
  skipped here and added by `l0 build-targets` in the next section. For example,
  `--year 2023` captures the latest SOI distribution tables, while the paper
  feed separately adds 2024 JCT, ACS, and SNAP-by-district sources plus CMS ACA
  sources at their pinned years. Source bytes come from the private `arch-raw`
  R2 bucket (Wrangler auth) or, with `ARCH_SOURCE_ARTIFACT_FETCH=1`, are fetched
  from each source's public URL and SHA-256-verified.

> The production registry compile requires a fact for **every** declared
> reference (including the JCT tax-expenditure rows), so a partial file needs
> `--allow-partial-facts` (dynamic references only; for wiring/smoke, not paper
> numbers).

### Complete target set — off-year sources (`build_targets.py`)

`arch build-bundle --year 2023` looks up each source's artifact at the literal
`--year`, so it **silently skips** sources pinned to another year — including
`jct-tax-expenditures-2024` (required by the production registry compile), the
census ACS age (`s0101`) / SNAP-by-district (`s2201`) sources, and the CMS ACA
enrollment sources. The complete target set is reproduced by
[`build_targets.py`](build_targets.py), which builds those off-year sources at
their pinned years (`build-suite`) and merges them into the base bundle:

```bash
# Cheap: reuse a default-source bundle (the output of `arch build-bundle --year 2023`):
uv run --extra data l0 build-targets --base /path/to/base/consumer_facts.jsonl
# From scratch (slow base build; needs arch-data source access / ARCH_SOURCE_ARTIFACT_FETCH=1):
uv run --extra data l0 build-targets --build-base --year 2023
```

It writes the full target set to `data/targets/consumer_facts.jsonl` plus a
`targets_manifest.json` provenance record. Every off-year artifact is local in
arch-data's `db/` package, so the merge needs no network or R2 auth.

A few granular IRS SOI targets (table 2.5 `qualifying_children`, table 4.3
`income_percentile_range`) carry filter dimensions the US fiscal materializer
cannot compute. They stay in the bundle file; `build_precalibration_dataset`
drops them **at materialization time** (recorded in the pre-calibration manifest
as `unsupported_filter_dropped`). Pass `--keep-unsupported-targets` to
`l0 poc` to retain them and let materialization abort loudly instead.

## Running

For the current manuscript reproduction, prefer the wrapper:

```bash
uv run --extra data --extra viz l0 paper \
    --consumer-facts data/targets/consumer_facts.jsonl
```

It builds or reuses `runs/weighted-loss-3seed/precalibration`, runs the paper
budget x seed sweep, renders report tables/figures, and copies PNG figures into
`paper/figures`. Add `--rebuild-pdf` to render `paper/index.qmd` with Quarto
and copy the result to `paper/main.pdf`; `--pdf-builder latexmk` keeps the
legacy direct-LaTeX path through `paper/main.tex`. Add
`--build-targets --target-base <consumer_facts.jsonl>` to first construct
`data/targets/consumer_facts.jsonl`, or pass `--reuse-precalibration <dir>`
when the frozen artifact already exists.

The lower-level commands below are useful for custom smoke runs and individual
steps.

```bash
# Full proof-of-concept (downloads the published base frame from HuggingFace,
# runs the PolicyEngine-US materialization, then all conditions). Uses the
# complete in-repo target set; no --allow-partial-facts needed:
uv run --extra data l0 poc \
    --ledger-facts data/targets/consumer_facts.jsonl \
    --period 2024 \
    --out runs/poc \
    --subsample 20000 --target-records 5000 --seed 0

# Reuse a frozen pre-calibration dataset (skips the heavy build):
uv run --extra data l0 poc \
    --reuse-precalibration runs/poc/precalibration \
    --out runs/poc2 --target-records 5000 --seed 0

# Smoke the whole real pipeline with the arch-data fixture (tiny):
uv run --extra data l0 poc \
    --ledger-facts /path/to/arch-data/arch/fixtures/consumer_facts.jsonl \
    --allow-partial-facts \
    --period 2023 --subsample 2000 --target-records 800 --epochs 60 \
    --mass free --holdout-frac 0.0 --out runs/smoke
```

Outputs per run: `run_manifest.json` (Populace commit, registry version, base-H5
and facts SHA-256, solver options, seeds, retained count, in/out-of-sample fit
metrics, runtime, output paths), `<method>.npz` (weights + loss trajectory +
diagnostics), and `tables/` (paper-ready LaTeX). Pass `--write-paper-tables` to
also overwrite `paper/tables/`.

Metrics (aligned with PR #5's stats list): mean/median/max absolute relative
error in- and out-of-sample, ESS, retained count, weight distribution incl. the
largest weight, runtime, broken out **by target family and by geographic level**.
Because the US target surface is national + state only, the by-family table is
usually the more informative cut. `l0_lambda` is recorded per run; `l2_lambda` and
`max_weight_ratio` are recorded too. `max_weight_ratio` is an informed-L0
**per-record** hard cap (no calibrated weight may exceed `max_weight_ratio *` its
*initial* weight, clamped each step), default **None (uncapped)**; the baselines
are left uncapped and their weight concentration is reported directly. Because the
cap is relative to each record's initial weight and the experiment resets weights
to uniform, a small cap (e.g. 5) gives every record the same low ceiling and
forbids the ~100x concentration the fiscal targets require -- so it must be treated
as a swept axis, not a fixed default (see issue #4). `l2_lambda` applies to the
informed-L0 path only.

Holdout note: Populace itself uses **rotated k-fold** holdout
(`populace/build/holdout.py`, every target held out once) plus **family-level
`validation_only`** targets (excluded from the fit, scored separately) and
out-of-sample reform validation. The quick POC can still use a single fixed split;
the amplified sweep adds a family-grouped rotation panel for the robustness check.

**Validation-only families** (Populace's `source_coverage` marks e.g. `cbo`
income/revenue projections as diagnostics, not contemporaneous calibration
targets) are **excluded from every method's fit by default** and scored
out-of-sample only — `holdout.validation_only_families()` derives the set from
Populace's live classification (`validation_only_family_ids()`), so it tracks
Populace rather than a hardcoded list. Pass `--fit-validation-only` to include
them in the fit. The set is recorded per run in
`run_manifest.json` → `target_split.validation_only_families`.

## Amplified budget sweep

`l0 poc` runs one budget at one seed. The paper needs the **frontier**: how
each method's accuracy moves as the record budget shrinks, with error bars and a
leak-free out-of-sample test. [`sweep.py`](sweep.py) provides that.

```bash
uv run --extra data l0 sweep \
    --reuse-precalibration runs/full-20k-cbo-state-tax-holdout/precalibration \
    --out runs/sweep-moderate \
    --budgets 2000 5000 10000 20000 40000 \
    --seeds 0 1 2 \
    --epochs 1000 \
    --holdout-families cms_medicaid usda_snap state_income_tax \
    --rotation-folds 5 --rotation-budget 10000 \
    --target-loss-cap 10 \
    --methods informed_l0 random_reweight dense_sample
```

Add `--jobs N` to run independent seed/fold/L2 shards in parallel. The parent
process owns checkpoint writes, so parallel workers never write the shared CSV or
manifest directly. Set PyTorch/BLAS thread env vars low when using multiple jobs:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
uv run --extra data l0 sweep \
    --reuse-precalibration runs/full-35k/precalibration \
    --out runs/35k-narrow \
    --budgets 2000 10000 40000 \
    --seeds 0 1 2 \
    --jobs 4 \
    --methods informed_l0 informed_l1 random_reweight dense_sample
```

Production US-fiscal weighting defaults to the production target-loss cap
(`c=1`). The current manuscript's committed real-data runs used the generic
solver cap (`c=10`), so pass `--target-loss-cap 10` when reproducing those
figures and tables.

Design points:

- **Frozen input only** (`--reuse-precalibration`): the calibration method is the
  only thing that varies. Build the artifact once with `l0 poc`.
- **Matched budget**: informed L0 sets the budget at each `(seed, budget)` point;
  `informed_l1`, `random_reweight`, and `dense_sample` (survey-weight sampling)
  match its retained count.
- **Weight concentration**: `--max-weight-ratio` is an informed-L0 **per-record**
  cap (weight <= ratio x *initial* weight), default **None (uncapped)**. Since the
  experiment resets weights to uniform, the cap is relative to a flat initial
  weight, so a small value (5) forbids the ~100x concentration fiscal targets need
  and collapses L0 to a near-uniform, non-fitting solution -- treat the cap as a
  swept axis (issue #4), not a fixed default. The baselines are left unconstrained;
  their ESS and max weight are reported so concentration is visible. Use
  `--methods informed_l0` to run only the (expensive) L0 condition.
- **Dense reuse**: the dense fit for survey-weight sampling does not depend on the
  budget, so [`conditions.calibrate_dense`](../experiments/conditions.py)
  computes it once per seed and [`conditions.sample_from_dense`](../experiments/conditions.py)
  resamples it at every budget.
- **Parallel shards**: `--jobs` parallelizes across seed/fold/L2 shards, keeping
  budgets sequential inside each shard so dense calibration is still reused. With
  `--jobs 1`, checkpoints are written after every budget cell; with `--jobs >1`,
  checkpoints are written as each shard finishes.
- **Leak-free holdout**: the frontier uses one fixed *family-level* split
  (`split_registry_by_family`) so nested cells (a national total and its state
  parts) never straddle the fit/holdout boundary. `--rotation-folds k` adds a
  robustness panel at `--rotation-budget`: [`holdout.family_grouped_folds`](../experiments/holdout.py)
  deals **whole families** into `k` balanced folds so every family is held out
  exactly once, with no within-family leakage. Validation-only families (`cbo`)
  are excluded from every fit and scored out-of-sample only.
- **Fail-fast families**: `--holdout-families` must use Populace registry family
  names (`spec.family`, e.g. `state_income_tax`, `census_population`, `ssa`). An
  unknown name stops the run instead of silently leaving those targets in-sample.

Output: one tidy **long CSV** (`metrics_long.csv`) — one row per
`(method, seed, budget, holdout_type, fold, split, scope, metric)` — plus a
`sweep_manifest.json`. The long table is the single source of truth.

> Family naming: the holdout split keys on Populace's `spec.family`
> (`state_income_tax`, `census_population`, `ssa`), while the per-family scoring
> breakdown labels families by Ledger metadata (`census_stc`, `census_pep`,
> `ssa_supplement`). Same targets, two naming layers.

### Aggregation, figures, and tables

[`aggregate.py`](../experiments/aggregate.py) (pure
numpy/pandas/scipy) turns the long CSV into cross-seed statistics:
mean ± t confidence interval (`frontier_table`), the paired same-seed
`informed_l0` - `random_reweight` difference with paired descriptive diagnostics
(`paired_method_diff`), the
family macro-average that de-biases the SOI-dominated micro mean (`macro_average`),
and per-budget run diagnostics (`run_metric`, e.g. ESS / max weight).

[`figures.py`](figures.py) consumes the long CSV and writes the LaTeX tables
(`frontier`, `paired_comparison`, rotation) and a Markdown summary — no plotting
dependency needed — plus matplotlib figures (static PDF/PNG/SVG):

```bash
uv run --extra viz l0 figures \
    --sweep runs/sweep-moderate --paper-figures
```

- **F1** frontier — out-of-sample mean & median ARE vs retained records (seed bands).
- **F2** usability — effective sample size and max weight vs budget.
- **F3** generalization gap — out-of-sample minus in-sample mean ARE.
- **F4** by-family ARE at the anchor budget (rotation holdout when present).
- **F5** cost–accuracy — runtime vs out-of-sample mean ARE.
- **F6** operability — L2 concentration penalty versus fit.

Matplotlib is imported lazily, so without the `viz` extra the tables and summary
are still written and the figures are skipped with a note.

Rotation-panel uncertainty is summarized conservatively. The reporting script
first collapses every seed's folds into one target-weighted rotated-family score,
then computes the interval across seeds. Validation-only families such as `cbo`
are excluded from that rotated-family aggregate because they appear in every fold;
they remain available in the by-family diagnostics.

## Full candidate universe (generate-big build)

[`build_candidate.py`](build_candidate.py) wires Populace's 15-stage
imputation (`populace.build.us_runtime.us_plan` -> `StagePlan.run`) for the true pre-prune
candidate universe. It is **not run by default** (needs donor source data and
~48 GB RAM) and has one extension point — the per-stage implementations Populace
does not yet export publicly.

## Tests

`tests/test_experiments.py` and `tests/test_end_to_end.py` exercise the sampling
conditions, scoring, holdout, artifact summaries, table rendering, and toy
four-arm demo — offline, no PolicyEngine-US, no network (`uv run pytest`).
