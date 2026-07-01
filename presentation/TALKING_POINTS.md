# IMA 2026 — talking points

L0 regularization for subnational microsimulation calibration · ~24 minutes.

The deck is deliberately front-loaded on context: the paper results are a proof of
concept, so most of the value is in the production goal, the data engine (Ledger +
Populace), the imputation mechanics, and the L0 foundation and our translation.

## Timing budget

| Section | Slides | Target |
|---|---|---|
| 0 · Open | 1–2 | 1:00 |
| 1 · Motivation | 3–6 | 2:30 |
| 2 · Data engine (Ledger + Populace) | 7–9 | 2:30 |
| 3 · Imputation | 10 | 1:30 |
| 4 · Reduction + Louizos + method | 11–15 | 4:00 |
| **First half** | **1–15** | **~11:30** |
| 5 · Proof of concept (design + results) | 16–24 | 6:30 |
| 6 · Close | 25–27 | 2:00 |
| **Second half** | **16–27** | **~8:30** |

## Delivery notes (PolicyEngine voice)

- Use exact numbers; never "large" / "significant" / "dramatically".
- Describe what the method does, not whether it is good. Sign the gaps ("4.74%
  loss versus dense 5.07% and random + reweight 7.55%", "ESS 4,726 versus
  random + reweight 2,480"), do not overstate one probe as a full frontier.
- Lead with the median; the mean is tail-sensitive and is reported, not headlined.
- Treat effective sample size as a result, not a caveat.
- This version leads with the full Populace target surface — do not describe the
  holdout run as the main result.

---

# First half — detailed talking points (slides 1–15)

## Slide 1 · Title
- **KEY MESSAGE:** This is about *which records survive* when a faithful candidate
  population has to become a deployable dataset.
- **SAY:**
  - One line on who you are and that this is joint PolicyEngine work.
  - "The question we address is: when a rich candidate dataset is too big
    to ship, which records do we keep, and at what weight?"
- **TRANSITION:** "Let me start with why we have a rich-but-too-big dataset at all."

## Slide 2 · Roadmap
- **KEY MESSAGE:** Six beats.
- **SAY:** Walk the five bullets in one breath each.
- **TRANSITION:** "It starts from what we are trying to produce."

## Slide 3 · Policy goal
- **KEY MESSAGE:** Reform questions can be asked at the national or subnational
  levels (such as states and congressional districts); each needs data that
  represents that geography.
- **SAY:**
  - PolicyEngine is a free, open-source platform that computes how tax and benefit 
    policy affects households and government budgets, for the US and UK. Anyone can 
    model a reform and see its distributional and fiscal impact. Policy questions can 
    be asked at different geographic questions.
  - A national average stretched to a district is not a district estimate.
  - So the data problem is subnational from the start.
  - (Visual) The map is estimated SNAP benefits for every congressional district (435
    plus DC), produced from one calibrated dataset — exactly the kind of subnational
    estimate this work enables.
- **TRANSITION:** "Representing all those levels at once is first a question of how the
  weights are laid out on the records."

## Slide 4 · Weight layout — wide (the UK layout)
- **KEY MESSAGE:** One layout is *wide* — a record carries one weight per subnational
  area. That is how our first (UK) local-area system worked.
- **SAY:**
  - Keep one national microdataset and build a matrix of weights by area: each record
    gets a weight in every area column.
  - The limitation: weight columns for overlapping geographies can disagree, and the
    inconsistency grows as users ask for more breakdowns.
- **TRANSITION:** "The US case has many overlapping views and local policy, which forced
  a different layout."

## Slide 5 · Weight layout — long (the US layout)
- **KEY MESSAGE:** The other layout is *long* — each record carries a single weight with
  its geography on the record, and that one weight set must reproduce nested totals.
- **SAY:**
  - The US needs state, county, congressional-district, and legislative views at once,
    and policy varies locally — so geography moves onto the records, one weight each.
  - This is the requirement that makes the long layout necessary: calibration finds
    weights so the weighted dataset reproduces published totals (the weighted sum of a
    variable equals the target T), and subnational work makes it *hierarchical* — district
    totals sum to state totals, state to national, in a *single* weight vector, not three
    independent fits.
  - The long layout keeps every geography internally consistent, but it inflates the
    candidate universe.
  - Classical calibration (Deville–Särndal, GREG, IPF) answers this for a fixed set of
    records; the open question is which records to fit on.
- **TRANSITION:** "Let me explain why the candidate set of records that has to satisfy all 
  those nested totals is large, on purpose."

## Slide 6 · Build big, then prune
- **KEY MESSAGE:** Fidelity makes the candidate dataset rich enough to represent the
  targets, and too large to simulate.
- **SAY:**
  - Build big: pool surveys, attach imputations, add geography, oversample rare support.
  - The pressure point: calibration memory scales with targets times records, and the
    shipped file still has to be cheap to load and simulate.
  - So we prune with evidence — keep records because they help reproduce a source-backed
    target, not because they won a random draw.
- **TRANSITION:** "To make that concrete, here is the engine that builds and prunes — two
  pieces: Ledger turns government publications into source-backed facts, and Populace builds
  survey microdata into a calibrated, deployable population."

## Slide 7 · Ledger
- **KEY MESSAGE:** Ledger is PolicyEngine's *source-data foundation* for social simulation:
  it captures source publications, preserves provenance, and represents published values
  as structured, queryable facts.
- **SAY:**
  - "Ledger captures source publications, preserves provenance, and represents published
    values as structured, queryable facts."
  - A fact = geography × entity × measure × aggregation × source provenance. Example:
    California, tax unit, adjusted gross income, sum, IRS SOI.
  - Ledger may re-express a published value, but never reconciles, ages, or imputes
    — that keeps the fact layer auditable.
- **TRANSITION:** "Populace is what consumes those facts."

## Slide 8 · Populace — the frame
- **KEY MESSAGE:** Populace is PolicyEngine's *microdata engine*, the micro stack: weighted
  entity bundles, synthesis, calibration, and rules-engine adapters for survey microdata.
- **SAY:**
  - "Populace is our microdata engine — weighted entity bundles, synthesis, calibration,
    and rules-engine adapters for survey microdata."
  - A population is a *weighted sampling frame*, not a flat table: entity tables keep the
    structure (person, household, tax unit, family).
  - Two jobs stay separate: generation decides *which records exist*, calibration decides
    *how much each one counts*. That separation is what lets us drop records safely when we
    prune later.
  - (The frame diagram also shows the three weight types — survey design → pool assembly →
    calibrated; mention only if time.)
- **TRANSITION:** "Those pieces flow through a fixed pipeline."

## Slide 9 · Pipeline
- **KEY MESSAGE:** One frame is carried through every stage; the stages are
  interchangeable components.
- **SAY:**
  - Load sources → combine → impute → geography → compose targets → calibrate and prune.
  - The imputation model and the calibration method are swappable; the L0 method later
    is one calibration option this pipeline supports.
- **TRANSITION:** "The stage that does the heavy lifting for representativeness is
  imputation."

## Slide 10 · Imputation
- **KEY MESSAGE:** No single survey measures everything, so we borrow from many different
  surveys — learning whole conditional distributions, which is what keeps the data faithful.
- **SAY:**
  - The CPS is strong on demographics and program receipt, thin on wealth, tax detail,
    wages, and housing.
  - Fill each gap from whichever survey measures it best — many surveys can be donors.
  - The fitting step learns a *conditional distribution* on the donor data —
    P(variable | demographics, income) — not a single point prediction.
  - We use Quantile Regression Forests to predict the whole distribution and sample a
    draw per record, preserving the variability (similar people get a realistic spread),
    not collapsed to a mean.
- **TRANSITION:** "Now that we know why this richness is important but costly, lets look at pruning."

## Slide 11 · The reduction problem
- **KEY MESSAGE:** With the universe and targets fixed, reduction is a sampling problem
  with fitted weights.
- **SAY:** Walk input → constraint → goal → output. Emphasize the output is selected
  records *and* calibrated positive weights — selection and weighting are coupled.
- **TRANSITION:** "There are four ways to do this, and they differ in where selection
  enters."

## Slide 12 · Five completed arms
- **KEY MESSAGE:** Five completed arms, one shared calibrator; the comparison isolates where selection enters.
- **SAY:**
  - Target-informed sparse selection: **informed L0** (hard-concrete gates select and
    weight jointly; the L0 penalty sets an exact retained count) and **L0 + refit**
    (keep the L0-selected records, remove the gates, and refit ordinary calibration
    weights on that subset).
  - The completed baselines differ in ordering: **dense no-L0** fits all records;
    **random + reweight** draws a subset first, then fits weights on it; **dense sample,
    scaled** calibrates the full universe first, then randomly keeps dense weights and scales
    them back to total mass without refitting.
  - Targets and universe stay fixed, so the comparison isolates *where selection enters*.
- **TRANSITION:** "Before we move to the results, let me explain the intution behind our developed method."

## Slide 13 · Louizos foundation
- **KEY MESSAGE:** Louizos, Welling and Kingma (2018) made L0 trainable by gradient
  descent for neural-network sparsification; we reuse that machinery.
- **SAY:**
  - Their goal: shrink a network by driving some weights to exactly zero.
  - The catch: the L0 "norm" (count of non-zeros) is a step function — flat, then a unit
    jump as a weight crosses zero — so its gradient is zero almost everywhere or undefined at
    jumps and gives gradient descent no signal about which weight to turn off.
  - The fix: replace each hard on/off with a *stochastic gate* and learn its probability of
    being open. The hard-concrete gate (point to the diagram) draws a smooth value in
    [0,1], stretches it past both ends, and clips — piling probability mass *exactly* at 0
    (off, weight dropped) and *exactly* at 1 (on, weight kept) while the middle stays
    smooth.
  - This makes the open probability is closed-form, so the *expected number of open gates*
    is differentiable — that is what we penalize, pushing toward fewer open gates.
- **TRANSITION:** "Now translate this from network weights to microdata records."

## Slide 14 · Translation
- **KEY MESSAGE:** The mapping is one-to-one: weights become records.
- **SAY:** Read the table left to right. A network weight becomes a candidate record;
  zeroing a weight becomes dropping a record; the expected count of open gates becomes
  the expected retained-record count; a sparser network becomes a dataset pruned to a
  budget.
- **TRANSITION:** "With that mapping, our objective is one loss over selection and
  weights."

## Slide 15 · Our objective
- **KEY MESSAGE:** Selection and weighting are optimized together against the same loss.
- **SAY:**
  - The training objective has three terms: the calibration loss on *gated* weights,
    an L0 penalty equal to the expected retained count, and an L2 penalty on the ratio of
    fitted to initial weight (to control how the population mass spreads across records).
  - For our experiments, however, we set L2 to 0 to isolate L0.
  - A record only contributes to the training objective when its gate is open.
  - At publication, gates are evaluated deterministically: the output is an ordinary
    sparse dataset with calibrated positive weights.
  - The point: **selection is trained against the same target system the final weights must**
    **match, so records survive when keeping them helps reproduce a target.**
- **TRANSITION:** "So does informed selection actually beat the baselines? Here is the proof of concept."

---

# Second half — proof of concept (slides 16–27)

> Numbers and figures below are from the full-surface matched probe:
> 37,053 Ledger facts compile to 32,633 materialized targets on 337,704 candidate
> households.

## Slide 16 · Experiment design
- **KEY MESSAGE:** Hold the input, the full target surface, and the budget fixed; vary only
  the method arm.
- **SAY:**
  - 337,704-household three-year ASEC support file; 32,633 materialized targets from
    37,053 Ledger facts; 24,340 targets are congressional-district targets.
  - The normalized L0 penalty share is 0.8, which retained 57,240 records.
  - The five arms in this probe are informed L0, informed L0 plus an ordinary
    post-selection refit, dense no-L0, random plus reweighting, and dense sample scaled.
  - All methods share the Populace production loss, target weights, candidate frame, and
    scoring path — the comparison varies selection and, for the refit arm, whether the
    selected records are reweighted after gates are removed.
  - Holdouts are separate diagnostics; the headline score fits and scores the full target
    surface.
- **TRANSITION:** "All of these are scored by the same loss."

## Slide 17 · Calibration objective
- **KEY MESSAGE:** One loss scores every method — capped weighted MAPE (Mean Abs % Error).
- **SAY:**
  - Relative error puts count and dollar targets on one scale; the cap c limits any single
    hard-to-fit target, so one bad row cannot dominate the gradient.
  - The reported runs use the production cap c=1, so targets more than 100% away do not contribute
    to the gradient.
  - The per-target weights ω_j scale each target by the square root of its size, within two
    bases (count vs dollar) that are rescaled to contribute equally — so dollar cells do not 
    swamp the count targets.
- **TRANSITION:** "So where does informed selection actually win? Build it up one arm at a time."

## Slide 18 · Main result · where we start
- **KEY MESSAGE:** Two reference points before the clever pruning — keep everything, or prune at random.
- **SAY:**
  - Dense no-L0 calibrates all 337,704 records and reaches 5.07% on the full Populace
    surface. It is a reference, not a deployable budget.
  - Naively prune to exactly 57,240 records at random and refit weights on that subset:
    7.55%.
  - The question for the rest of the arc: how close can a 57,240-record file get to dense?
- **TRANSITION:** "First, confirm that the reweighting — not the sample — is what helped."

## Slide 19 · Main result · skip the reweighting?
- **KEY MESSAGE:** The reweighting was doing the work, not the random sample.
- **SAY:**
  - Take the same random sample, keep the dense weights, and just rescale them to the
    population total with no refit: loss jumps to 24.24%.
  - So the gain from random + reweight came from re-fitting the weights on the retained
    subset, not from the sample itself.
- **TRANSITION:** "Now bring in the target-informed selector."

## Slide 20 · Main result · the informed selector: L0
- **KEY MESSAGE:** Informed L0 selects the support well, but its raw gated weights are not the publication weights.
- **SAY:**
  - Informed L0 chooses the 57,240 records jointly with their gated weights; it should beat
    a blind random sample.
  - But the raw gated weights score 9.86% — worse than random + reweight's 7.55%.
  - The gates select the support well; but the gated weights they return do not seem publication
    ready.
- **TRANSITION:** "So keep the records the gates chose, drop the gates, and refit."

## Slide 21 · Main result · refit once more
- **KEY MESSAGE:** L0's value is support selection, realized only after a post-selection refit.
- **SAY:**
  - Keep the 57,240 L0-selected records, remove the gates, and refit ordinary calibration
    weights on that subset: the loss falls to 4.74%.
  - That is below dense no-L0's 5.07% and well below every sampling baseline
    (random + reweight 7.55%, dense sample scaled 24.24%).
  - So the result is support selection, not direct publication of the gated weights.
- **TRANSITION:** "Does that fit hold across geography levels?"

## Slide 22 · Main result · by geography
- **KEY MESSAGE:** The L0 + refit fit holds at every geographic level.
- **SAY:**
  - Absolute relative error for the L0 + refit run at 57,240 records, by level: National
    median 1.30%, State 0.31%, Congressional district 1.48% — including the 24,340
    congressional-district targets.
  - Overall median ARE is 0.89% across 32,633 targets; the mean (84.64%) and max
    (162,496%) are tail-sensitive diagnostics, dominated by a few near-zero-denominator
    targets.
- **TRANSITION:** "Median and mean tell different stories — here is why we lead with the median."

## Slide 23 · Median and mean tell different stories
- **KEY MESSAGE:** Populace loss is the headline; raw median and mean ARE explain what is
  underneath it.
- **SAY:**
  - Median ARE shows typical target fit; mean ARE shows the tail.
  - Across methods: dense no-L0 has 0.56% median ARE; L0 + refit has 0.89%; random +
    reweight has 6.70%; raw gated L0 has 11.66%; dense sample scaled has 55.24%.
  - The raw mean remains tail-sensitive, so use it as a diagnostic, not the main score.
- **TRANSITION:** "Accuracy is not the whole story — what does it cost?"

## Slide 24 · Concentration
- **KEY MESSAGE:** Effective sample size is a primary result. The L0 gates already produce the
  best-conditioned weights; the accuracy refit trades some of that back, but L0 + refit still
  beats the matched random support.
- **SAY:**
  - Read ESS as a primary result — how much independent information the weighted file carries.
  - Raw L0-gated weights are the most spread-out of any arm — the *highest*, above dense full, 
    also with the lowest max weight.
  - The refit that restores accuracy gives back some concentration, though it still performs better
    than random samples. Dense full is the all-records reference at 5,970 / 579k.
  - So the deployable point is not just lower loss — among sparse supports it is the best trade
    of accuracy against concentration.
- **TRANSITION:** "Where does this go next?"

## Slide 25 · Future work
- **KEY MESSAGE:** The proof of concept points at two production extensions; classical
  calibrators are related work, not missing baselines.
- **SAY:**
  - Build really large, then prune: sweep normalized L0 penalties on the three-year support
    and larger over-built pools, then prune back to a publishable artifact.
  - Complete the comparator set: PPS survey-weight sampling, raking-compatible categorical
    margins, longer dense convergence checks, and concentration-penalty sweeps around the
    same Populace loss.
  - Targeted robustness: family holdouts are diagnostics around the production target
    surface, not replacements for the full-surface fit.
  - [If asked about GREG / IPF / raking / balanced sampling: they are reference methods for
    simpler margin surfaces, not full-surface baselines here — they apply only as robustness
    checks on the categorical-margin subsets where their assumptions hold (see the lit
    review). Convex sparse calibration is also a natural ablation, but it is not in this
    completed full-surface run.]
- **TRANSITION:** "To wrap up."

## Slide 26 · Conclusion
- **KEY MESSAGE:** Target-informed pruning works as support selection.
- **SAY:** The full-surface probe says: choose a sparse support with L0, then refit ordinary
  calibration weights on the retained support. This is not the final frontier; the next
  step is a normalized-penalty sweep with longer dense convergence checks, missing comparators,
  and concentration controls.

## Slide 27 · Questions
- **KEY MESSAGE:** Open the floor.
- **SAY:** Thank the audience and invite questions. Likely areas: the median/mean split, the
  effective-sample-size cost, and why classical calibrators are not baselines.
