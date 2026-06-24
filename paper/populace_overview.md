# Populace and the calibration pipeline

Populace builds a synthetic population from survey microdata: it fills in what
the surveys miss, places records in geographies, and reweights the result to
reproduce official administrative totals at the national, state, and local level
at once. The L0 paper covers the calibration step.

Companion figure: `figures/populace_pipeline.png`.

## Architecture

One datatype, packages as operators. Every stage reads and writes the same
object — a `populace.frame.Frame` — and each package is one operation on it. The
imputation model or the calibration method can be swapped without rewriting the
pipeline.

| Package | Role |
|---|---|
| `populace-frame` | the kernel: the Frame datatype every stage flows through |
| `populace-data` | source loaders and the published population registry |
| `populace-fit` | imputation operator (fills missing variables) |
| `populace-calibrate` | representation operator: targets → weights (the L0 work) |
| `populace-build` | orchestrator: typed build stages, geography, release gates |

## The Frame

A `Frame` is a weighted sampling frame carried through the whole pipeline. It
holds:

- **Entity tables** (person, household, …) with explicit person↔group links,
  fixed once at assembly.
- **Typed weights** — `design → importance → calibrated`. Each stage declares
  which kind it produces; the kernel forbids silent zeroing, NaNs, and negatives.
- **Strata / provenance** — each record records its origin (`cps_passthrough`,
  `synthetic_conditional`, `tail_verbatim`, …), so scarce regions (e.g. the
  income tail) can be oversampled with honest mass.
- **Variable metadata and weighted accounting** — sums, means, quantiles, Gini
  as Frame methods (absorbs the old `microdf`).

Calibration changes the weights on the Frame; it never rebuilds it.

## Pipeline

The candidate universe grows through the middle stages (~300k → 3M → 30M
records) and is pruned back to a budget by calibration — the
generate-big-then-prune design.

1. **Sources** (`populace-data`) — load the source surveys. The US spine is the
   CPS ASEC: demographics, household structure, labour and transfer income,
   program participation. The CPS misses some tax variables, under-captures top
   incomes, and under-reports benefit receipt, so other sources load alongside
   it (IRS PUF, ACS, asset/wealth surveys).
2. **Combine** (`populace-frame`) — assemble the sources into one record
   universe: entity tables, typed weights, strata tagging each record's origin.
3. **Impute** (`populace-fit`) — fill the missing variables with weight-aware
   quantile regression forests, run in a chain so each imputed variable
   conditions on the previous ones. Tax variables come from the IRS PUF; rent,
   real-estate tax, and asset/net-worth components from other surveys.
   Imputation also adds household variants — the first source of growth.
4. **Geography** (`populace-build`) — assign records to geographies below the
   survey's level (state, district). One record can be placed in more than one
   area — the second source of growth, and what makes the model subnational.
5. **Build targets** (`populace-calibrate`) — compile the administrative totals
   into a sparse constraint matrix `M` (m targets × n records). `M[j,i]` is
   record `i`'s contribution to target `j`: an indicator/count for count
   targets, or a PolicyEngine-simulated value under the policy rules of the
   record's geography. Targets are totals with standard errors, drawn from
   several admin sources at national / state / district level.
6. **Calibrate** (`populace-calibrate`) — choose which records to keep and their
   weights so the kept set reproduces the targets. Output: retained records and
   calibrated weights, assembled into a PolicyEngine-ready dataset.

## Calibration (the L0 step)

Selection and weighting are one optimization. The optimizer minimizes:

```
L(w, α) = (1/m) Σ_j ((t̂_j − t_j) / |t_j|)²      relative calibration loss
        + λ_L0 Σ_i z̄_i                            number of records kept
        + λ_L2 ‖w‖²                                weight concentration
   where  t̂_j = Σ_i M[j,i] · w_i · z_i
```

- **Relative loss** weights a 1% miss equally on small and large targets.
- **`z_i`** is a Hard Concrete gate (Louizos et al. 2018), a differentiable
  on/off switch with expected activation `z̄_i`. `λ_L0` penalizes the expected
  number of open gates — the sample size — so it controls pruning.
- **`λ_L2`** bounds the mass any one kept record carries, since an L0 penalty
  alone can reach a sparse-but-unusable solution that piles weight on a few
  records.

Weights are fit in log space (kept positive); gates and weights are learned
together against the same loss, so a record survives only when keeping it helps
match a target. Instead of tuning `λ_L0` directly, `target_records = N` bisects
on `log(λ_L0)` until the non-zero count tracks the budget.

## Experiment

Holding the candidate universe and target set fixed, four methods reach the same
record budget, differing in where calibration enters the reduction:

1. **Informed L0** (Hard Concrete gates) — select and weight jointly.
2. **Random sample → reweight** — reduce first, calibrate after.
3. **Survey-weight sampling** — reweight the full universe, then sample
   proportional to weight down to budget.
4. **Combinatorial optimization** — simulated annealing selects records to
   minimize target error directly, no gradients.

Results are scored on held-out targets none of the methods were fit to, reported
by geographic level, with retained-record count, weight distribution, and
runtime.

## Statistics

The points the method has to defend.

- **L0 / Hard Concrete.** The true objective penalizes the *count* of kept
  records (an L0 norm), which is non-differentiable. The Hard Concrete gate
  (Louizos et al. 2018) is a continuous relaxation: a stretched-and-clamped
  Concrete variable whose expected activation `z̄_i` is differentiable, so the
  expected L0 penalty `λ_L0 Σ_i z̄_i` can be minimized by gradient descent. At
  the end the gates are evaluated deterministically to read off the kept set.
- **Samplers in survey-statistics terms.** The weights are typed `design →
  importance → calibrated`. The baselines map to standard tools: gradient-descent
  reweighting is generalized regression (GREG) estimation; survey-weight sampling
  reweights then *integerizes* (sampling proportional to weight); combinatorial
  optimization minimizes Total Absolute Error (TAE) by simulated annealing. L0 is
  the only one where the targets choose which records to keep.
- **Out-of-sample validity.** Generate-big-then-prune selects records *by* the
  calibration objective, so matching the fitted targets is not evidence of
  correctness. Scoring on held-out targets guards against this. Reusing one fixed
  holdout across many comparisons is leaderboard overfitting (the reusable-holdout
  problem), so fresh survey vintages rotate as the holdout.
- **Correlated evidence.** Target standard errors from one survey are
  design-correlated across its published cells. Treating them as diagonal
  overweights cell-rich surveys (the standard GREG caveat); evidence combination
  should account for within-source covariance.
- **Metrics.** Mean, median, and max absolute relative error across scored
  targets (in- and out-of-sample); retained-record count and effective sample
  size; the fitted-weight distribution including the largest weights; runtime.
  Errors are broken out by geographic level, since a sampler can match national
  totals while missing local ones.

## Notes

- The stack is **Populace**; the `data.tex` / `methodology.tex` drafts still say
  `\microplex`.
- Scale figures (~300k → 3M → 30M, 100k retained) are the design target, not
  measured results — pull exact counts from each run manifest.
- For a UK talk, swap the US sources (CPS, PUF) for UK equivalents (FRS spine).
- Generate-big-then-prune selects records by the calibration objective, so
  validity is scored on held-out targets and variables the objective never saw.
