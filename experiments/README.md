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
[`l0_paper.precalibration`](../src/l0_paper/precalibration.py) as a pickle +
`registry.json` + `precalibration_manifest.json`. Every experiment loads this one
frozen artifact.

## Calibration conditions (this issue)

[`l0_paper.experiments.conditions`](../src/l0_paper/experiments/conditions.py):

1. **Informed L0** (`run_l0`) — `calibrate(..., target_records=N)` jointly fits
   weights and Hard-Concrete gates to retain ~N records.
2. **Survey-weight sampling** (`run_dense_then_sample`) — calibrate-then-reduce:
   `calibrate(..., target_records=None, l0_lambda=0.0)` fits all weights, then
   draws a **probability-proportional (PPS) random** sample of `n = ` (the L0
   retained count), each record drawn with probability ∝ its fitted weight, and
   reweights it (integerisation). This is the paper's method 3 — it is *not*
   "keep the largest weights" (that would be deterministic top-weight selection).
3. **Random + reweight** (`run_random_then_reweight`) — reduce-first: draw a
   **uniform** (equal-probability) random subset of size `n`, weight it up to the
   population total, then reweight just that subset to the targets by gradient
   descent (gates off). The paper's method 2.

All three return a full-length weight vector (zero for unretained records), scored
in- and out-of-sample by [`metrics`](../src/l0_paper/experiments/metrics.py) with
targets held out via [`holdout`](../src/l0_paper/experiments/holdout.py). The
sampling-comparison table now fills three of its four method rows (combinatorial
optimisation remains `\tbc`).

## Getting the Ledger facts file

Target values come from a PolicyEngine Ledger `consumer_facts.jsonl`, produced by
**`PolicyEngine/arch-data`** (namespace `arch` / `policyengine_ledger`):

- A small stand-in may be available in an `arch-data` checkout as
  `arch/fixtures/consumer_facts.jsonl` (real schema, partial coverage — use with
  `--allow-partial-facts`). It is not committed in this repository.
- The full mixed-vintage file is emitted in one call from a clone of
  `PolicyEngine/arch-data`:

  ```bash
  uv run arch build-bundle --year 2023 --out /tmp/arch-us-2024 --replace
  # writes /tmp/arch-us-2024/consumer_facts.jsonl  (+ coverage.json, reports/)
  ```

  `build-bundle` merges all default source packages, each at its own vintage:
  year-pinned aliases (`jct-tax-expenditures-2024`, `census-pep-2024-*`,
  `ssa-…-2025`, `soi-*-2022`) carry their fixed period regardless of `--year`,
  while `--year` only sets the year-templated sources (the `soi-table-*`
  distribution tables, whose latest published tax year is **2023**). So
  `--year 2023` yields the complete set for a **2024 dataset**; arch-data
  resolves the mix, and Populace maps it onto its 2024 target period (run with
  `--period 2024`, the default). Check `coverage.json` / `reports/build_bundle.json`
  to confirm no families were skipped. Source bytes come from the private
  `arch-raw` R2 bucket (Wrangler auth) or, with `ARCH_SOURCE_ARTIFACT_FETCH=1`,
  are fetched from each source's public URL and SHA-256-verified.

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
uv run python experiments/build_targets.py --base /path/to/base/consumer_facts.jsonl
# From scratch (slow base build; needs arch-data source access / ARCH_SOURCE_ARTIFACT_FETCH=1):
uv run python experiments/build_targets.py --build-base --year 2023
```

It writes the full target set to `data/targets/consumer_facts.jsonl` plus a
`targets_manifest.json` provenance record. Every off-year artifact is local in
arch-data's `db/` package, so the merge needs no network or R2 auth.

A few granular IRS SOI targets (table 2.5 `qualifying_children`, table 4.3
`income_percentile_range`) carry filter dimensions the US fiscal materializer
cannot compute. They stay in the bundle file; `build_precalibration_dataset`
drops them **at materialization time** (recorded in the pre-calibration manifest
as `unsupported_filter_dropped`). Pass `--keep-unsupported-targets` to
`run_poc.py` to retain them and let materialization abort loudly instead.

## Running

```bash
# Full proof-of-concept (downloads the published base frame from HuggingFace,
# runs the PolicyEngine-US materialization, then all conditions). Uses the
# complete in-repo target set; no --allow-partial-facts needed:
uv run python experiments/run_poc.py \
    --ledger-facts data/targets/consumer_facts.jsonl \
    --period 2024 \
    --out experiments/runs/poc \
    --subsample 20000 --target-records 5000 --seed 0

# Reuse a frozen pre-calibration dataset (skips the heavy build):
uv run python experiments/run_poc.py \
    --reuse-precalibration experiments/runs/poc/precalibration \
    --out experiments/runs/poc2 --target-records 5000 --seed 0

# Smoke the whole real pipeline with the arch-data fixture (tiny):
uv run python experiments/run_poc.py \
    --ledger-facts /path/to/arch-data/arch/fixtures/consumer_facts.jsonl \
    --allow-partial-facts \
    --period 2023 --subsample 2000 --target-records 800 --epochs 60 \
    --mass free --holdout-frac 0.0 --out experiments/runs/smoke
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
`max_weight_ratio` are recorded too — note Populace bounds weight concentration
with the hard `max_weight_ratio` cap, not the paper's soft L2 penalty (the solver
has no L2 term), so `l2_lambda` is reported for parity but is not applied.

Holdout note: Populace itself uses **rotated k-fold** holdout
(`populace/build/holdout.py`, every target held out once) plus **family-level
`validation_only`** targets (excluded from the fit, scored separately) and
out-of-sample reform validation. The current `holdout.split_targets` is a single
fixed split; `split_registry_by_family` does family-level holdout. Aligning fully
with rotated k-fold is a planned follow-up.

**Validation-only families** (Populace's `source_coverage` marks e.g. `cbo`
income/revenue projections as diagnostics, not contemporaneous calibration
targets) are **excluded from every method's fit by default** and scored
out-of-sample only — `holdout.validation_only_families()` derives the set from
Populace's live classification (`validation_only_family_ids()`), so it tracks
Populace rather than a hardcoded list. Pass `--fit-validation-only` to include
them in the fit. The set is recorded per run in
`run_manifest.json` → `target_split.validation_only_families`.

## Full candidate universe (generate-big build)

[`build_full_candidate.py`](build_full_candidate.py) wires Populace's 15-stage
imputation (`populace.build.us.us_plan` → `StagePlan.run`) for the true pre-prune
candidate universe. It is **not run by default** (needs donor source data and
~48 GB RAM) and has one extension point — the per-stage implementations Populace
does not yet export publicly.

## Tests

`tests/test_experiments.py` exercises both conditions, scoring, holdout, artifact
summaries, and table rendering on the toy frame — offline, no PolicyEngine-US, no
network (`uv run pytest`).
