# IMA 2026 — talking points

L0 regularization for subnational microsimulation calibration · ~23 minutes.

The deck is deliberately front-loaded on context: the paper results are a proof of
concept, so most of the value is in the production goal, the data engine (Ledger +
Populace), the imputation mechanics, and the L0 foundation and our translation.

## Timing budget

| Section | Slides | Target |
|---|---|---|
| 0 · Open | 1–2 | 1:00 |
| 1 · Motivation | 3–5 | 2:30 |
| 2 · Data engine (Ledger + Populace) | 6–9 | 3:00 |
| 3 · Imputation mechanics | 10–12 | 3:30 |
| 4 · Reduction + Louizos + our method | 13–19 | 5:00 |
| **First half** | **1–19** | **~15:00** |
| 5 · Proof of concept (design + results) | 20–25 | 6:00 |
| 6 · Close | 26–28 | 2:00 |
| **Second half** | **20–28** | **~8:00** |

## Delivery notes (PolicyEngine voice)

- Use exact numbers; never "large" / "significant" / "dramatically".
- Describe what the method does, not whether it is good. Sign the gaps ("17 points
  lower", "the smaller in-to-out gap"), do not say "better".
- Lead with the median; the mean is tail-sensitive and is reported, not headlined.
- Treat effective sample size as a result, not a caveat.
- This is a proof of concept on national and state targets — say so plainly.

---

# First half — detailed talking points (slides 1–19)

## Slide 1 · Title
- **KEY MESSAGE:** This is about *which records survive* when a faithful candidate
  population has to become a deployable dataset.
- **SAY:**
  - One line on who you are and that this is joint PolicyEngine work.
  - "The question is narrow and practical: when a rich candidate dataset is too big
    to ship, which records do we keep, and at what weight?"
- **TRANSITION:** "Let me start with why we have a rich-but-too-big dataset at all."

## Slide 2 · Roadmap
- **KEY MESSAGE:** Five beats; the first four are context, the last is the experiment.
- **SAY:** Walk the five bullets in one breath each. Flag explicitly that you will
  spend most of the time on the data engine and the method, because the results are a
  proof of concept.
- **TRANSITION:** "It starts from what we are trying to produce."

## Slide 3 · Policy goal
- **KEY MESSAGE:** Reform questions can be asked at the national or subnationa 
  levels, (such as states, and congressional districts); each needs data that 
  represents that geography.
- **SAY:**
  - PolicyEngine runs live tax-and-benefit microsimulation for the US and UK.
  - A national average stretched to a district is not a district estimate.
  - So the data problem is subnational from the start, in the US: 1 nation, 
    51 state-level units, 435 congressional districts.
- **TRANSITION:** "Representing those levels means reproducing administrative totals at
  all of them at once."

## Slide 4 · Nested targets
- **KEY MESSAGE:** One set of weights must reproduce published totals across nested
  geographies — hierarchical calibration.
- **SAY:**
  - Calibration finds weights so the weighted dataset reproduces published totals:
    the weighted sum of a variable equals the target T.
  - Subnational makes it hierarchical: district totals sum to state totals, state to
    national — in a *single* weight vector, not three independent fits.
  - Classical calibration (Deville–Särndal, GREG, IPF) answers this for a fixed set of
    records; the open question is which records to fit on.
- **TRANSITION:** "And the candidate set of records is large, on purpose."

## Slide 5 · Build big, then prune
- **KEY MESSAGE:** Fidelity makes the candidate dataset rich enough to represent the
  targets, and too large to simulate.
- **SAY:**
  - Build big: pool surveys, attach imputations, add geography, oversample rare support.
  - The pressure point: calibration memory scales with targets times records, and the
    shipped file still has to be cheap to load and simulate.
  - So we prune with evidence — keep records because they help reproduce a source-backed
    target, not because they won a random draw.
- **TRANSITION:** "To make that concrete, here is the engine that builds and prunes."

## Slide 6 · Section — the data engine
- **KEY MESSAGE:** Two pieces: Ledger (facts) and Populace (the frame).
- **SAY:** One sentence: "Ledger turns government publications into facts; Populace
  carries one weighted sampling frame through imputation, geography, and calibration."

## Slide 7 · Ledger
- **KEY MESSAGE:** Ledger is a source-backed fact store; a fact pins a value to its full
  context and keeps its provenance.
- **SAY:**
  - A fact = geography × entity × measure × aggregation × source provenance. Example:
    California, tax unit, adjusted gross income, sum, IRS SOI.
  - Targets are classified: hard (we fit to it), validation-only (scored but never fit
    — e.g. SPM poverty, the thing we are trying to diagnose), and not-yet-estimable.
  - The boundary rule: Ledger may re-express a published value, but never reconciles,
    ages, or imputes — that keeps the fact layer auditable.
  - Scale is roughly tens of thousands of candidate facts; treat the exact counts as
    draft until confirmed.
- **TRANSITION:** "Populace is what consumes those facts."

## Slide 8 · Populace — the frame
- **KEY MESSAGE:** A population is a *weighted sampling frame*, not a flat table.
- **SAY:**
  - Entity tables preserve structure: person, household, tax unit, family.
  - Weights are *typed* and move one way: design (from the survey) → importance (from
    pool assembly) → calibrated (terminal — once calibrated, never reverts).
  - Strata record per-record provenance, so generation owns support and calibration
    owns representation. That separation is what lets us prune safely later.
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

## Slide 10 · Imputation — representativeness
- **KEY MESSAGE:** No single survey measures everything, so we combine surveys by
  imputation. Let us look at the US.
- **SAY:**
  - The CPS is strong on demographics and program receipt, weak on wealth, tax detail,
    wages, and housing.
  - For each gap, fit a model on the survey that measures it best, then predict onto the
    CPS: SCF for wealth, the IRS PUF for tax detail, SIPP for tips, CPS-ORG for wages,
    MEPS-IC for premiums, ACS for rent.
  - The key idea: we borrow a *conditional distribution* — P(wealth | demographics,
    income) — from people who were actually asked, not a single predicted number.
- **TRANSITION:** "Borrowing a distribution, not a mean, is the part that matters."

## Slide 11 · Imputation — variability
- **KEY MESSAGE:** We sample the weighted conditional distribution; we do not predict
  the mean.
- **SAY:**
  - Method is quantile regression forests with three properties.
  - Weighted bootstrap: training rows are resampled by survey weight before each forest
    is grown, so the draws follow the *weighted* population — the weights are in the
    data, not ignored.
  - Regime gates: split a variable by sign support (negative / zero / positive) first,
    then model the magnitude — so capital gains do not get interpolated across zero.
  - Chaining: each variable is drawn conditional on the ones already drawn, so the joint
    structure across variables survives.
  - The payoff: a uniform draw q in (0,1) per record reproduces the full conditional
    distribution, preserving heterogeneity instead of collapsing it to a point.
- **TRANSITION:** "Doing this across many sources is exactly what blows up the size."

## Slide 12 · Imputation — scale
- **KEY MESSAGE:** A faithful candidate population outgrows what production can carry —
  which is the reason pruning exists.
- **SAY:**
  - Combining sources, oversampling rare support, and cloning records for fine
    geographies all multiply the record count.
  - The design target runs from the survey spine (the initial frame) toward one
    statistically-faithful record per person — far more than a model can ship.
  - And calibration memory scales with targets times records, so the bigger we build the
    more pruning has to do.
- **TRANSITION:** "So: we have built big. Now, which records survive?"

## Slide 13 · Section — the pruning problem
- **KEY MESSAGE:** State the reduction problem cleanly.
- **SAY:** "Given a large candidate universe, a record budget, and a target system,
  which records does the shipped dataset keep, and at what weight?"

## Slide 14 · The reduction problem
- **KEY MESSAGE:** With the universe and targets fixed, reduction is a sampling problem
  with fitted weights.
- **SAY:** Walk input → constraint → goal → output. Emphasize the output is selected
  records *and* calibrated positive weights — selection and weighting are coupled.
- **TRANSITION:** "There are four ways to do this, and they differ in where selection
  enters."

## Slide 15 · Four methods
- **KEY MESSAGE:** Four samplers, one shared calibrator; the comparison isolates where selection enters.
- **SAY:**
  - Target-informed sparse selection: **informed L0** (hard-concrete gates select and
    weight jointly; the L0 penalty sets an exact retained count) and **L1** (a convex
    sparse penalty; a proximal solver soft-thresholds weights to exact zeros).
  - The two classical baselines differ in ordering: **random + reweight** draws a subset
    first, then fits weights on it; **survey-weight sampling** calibrates the full universe
    first, then draws records with probability proportional to the fitted weights.
  - One framing to land: survey-weight sampling *is* informed, but by how much population
    a record carries, not by how well it reproduces the targets — informed toward a
    different objective.
  - Targets and universe stay fixed, so the comparison isolates *where selection enters*.
- **TRANSITION:** "The two sparse methods come from a deep-learning idea — here is L0."

## Slide 16 · Louizos foundation
- **KEY MESSAGE:** Louizos, Welling and Kingma (2018) made L0 trainable by gradient
  descent for neural-network sparsification; we reuse that machinery.
- **SAY:**
  - Their problem: automatically zero weights in a neural network. The L0 "norm" simply
    counts how many weights are non-zero.
  - Why pure L0 cannot be trained directly: a count is a step function. It stays flat as
    a weight changes, then jumps by one the instant the weight crosses zero. So its
    gradient is zero almost everywhere and undefined at the jumps — gradient descent gets
    no signal telling it which weight to turn off, and choosing the subset to zero by hand
    is combinatorial.
  - The fix is to make the on/off decision *soft and learnable*: put a stochastic gate on
    each weight and learn the probability that the gate is open.
  - The stretch-and-clip intuition (point to the diagram): draw a smooth random number
    that normally lives between 0 and 1, deliberately stretch its range so it can spill
    slightly below 0 and above 1, then clip — anything below 0 becomes exactly 0, anything
    above 1 becomes exactly 1. The clipping piles up probability mass *exactly* at 0
    (fully off, weight dropped) and *exactly* at 1 (fully on, weight kept), while values in
    between stay smooth. So a gate can be genuinely off or on, yet the knob that controls
    it moves continuously.
  - Crucially, the probability a gate is open is closed-form (point to the formula), so
    the *expected number of open gates* is differentiable — that is what we penalize, and
    gradient descent can now push toward fewer open gates.
- **TRANSITION:** "Now translate this from network weights to microdata records."

## Slide 17 · Translation
- **KEY MESSAGE:** The mapping is one-to-one: weights become records.
- **SAY:** Read the table left to right. A network weight becomes a candidate record;
  zeroing a weight becomes dropping a record; the expected count of open gates becomes
  the expected retained-record count; a sparser network becomes a dataset pruned to a
  budget.
- **TRANSITION:** "With that mapping, our objective is one loss over selection and
  weights."

## Slide 18 · Our objective
- **KEY MESSAGE:** Selection and weighting are optimized together against the same loss.
- **SAY:**
  - The training objective has three terms: the calibration loss on *gated* weights,
    an L0 penalty equal to the expected retained count, and an L2 penalty on the ratio of
    fitted to initial weight.
  - The gated estimate of a target is the matrix-weight product with the gate folded in,
    so a record only contributes when its gate is open.
  - λ_L0 sets the retained count — tuned by an outer bisection to a requested budget,
    not by hand. The L2 term penalizes the squared magnitude of each fitted weight
    (relative to its starting weight), which discourages loading the fit onto a few very
    large weights — that keeps population mass spread across records, so the effective
    sample size stays high and the dataset stays usable downstream. A hard per-record cap
    bounds the single largest weight as a backstop.
  - At publication, gates are evaluated deterministically: the output is an ordinary
    sparse dataset with calibrated positive weights.
  - The point: selection is trained against the same target system the final weights must
    match, so records survive when keeping them helps reproduce a target.
- **TRANSITION:** "And this is not a one-off prototype."

## Slide 19 · Production tie
- **KEY MESSAGE:** Both sparse methods ship inside Populace's calibration step.
- **SAY:** Setting a record budget activates the hard-concrete L0 gates inside the same
  step that fits production weights; the convex L1 solver lives in the same place. So the
  paper method is a first-class build option, which is why getting it right matters.
- **TRANSITION:** "So does informed selection actually beat the baselines? Here is the
  proof of concept." (Hand into the second half.)

---

# Second half — proof of concept (slides 20–28)

> Numbers and figures below reflect the final four-way sweep (L0 vs L1 vs random vs
> survey-weight), production loss cap c=1, run `4way-l1-cap1`.

## Slide 20 · Section — proof of concept
- **KEY MESSAGE:** One frozen candidate universe, one target system, four samplers, a range
  of budgets — the experiment isolates how records are chosen.
- **SAY:** One sentence: "Everything upstream is held fixed; the only thing that varies is
  the sampler, so any difference is the selection rule, not the data."

## Slide 21 · Experiment design
- **KEY MESSAGE:** Hold the input, the targets, and the budget fixed; vary only the sampler,
  and score on families held out of every fit.
- **SAY:**
  - 75,112-household Populace US 2024 candidate file; one target set of ~4,393 targets, IRS
    SOI ~71% of them; budget sweep 2k–40k records, from aggressive compression upward.
  - All four methods share the calibrator, the loss, and the weight bounds — only record
    selection differs.
  - Generalization is tested on whole held-out families — Medicaid, SNAP, state income tax,
    plus validation-only CBO (206 targets held out) — scored after calibration.
- **TRANSITION:** "All four are scored by the same loss."

## Slide 22 · Calibration objective
- **KEY MESSAGE:** One loss scores every method — capped weighted MAPE — so the comparison
  is apples to apples.
- **SAY:**
  - Relative error puts count and dollar targets on one scale; the cap c limits any single
    hard-to-fit target, so one bad row cannot dominate the gradient.
  - The reported runs use the production cap c=1.
  - Same targets, same loss, same weight bounds — only the sampler changes.
- **TRANSITION:** "So where does informed selection actually win?"

## Slide 23 · Main frontier
- **KEY MESSAGE:** Graceful degradation under compression — informed selection leads at
  tight budgets, the baselines draw level as the budget grows.
- **SAY:**
  - Read the figure: out-of-sample error against retained records, median and mean panels,
    all four methods.
  - At 2,000 records, informed L0's median out-of-sample ARE (Abs Rel Error) is 47.3% vs random 
    50.1%, survey-weight 48.1%, and L1 pinned at 100%; on the tail-sensitive mean the gap is far
    wider — 225% vs random's 1,798%.
  - As the budget grows the baselines draw level: on the median, random + reweight overtakes
    from ~5,000 records up, while informed L0 keeps the lower mean at every budget — the
    small-budget story is as much about variance as accuracy. At 10k, L0 median is 35.0%.
  - L1 is the convex point of comparison: one penalty cannot both select records and keep
    their weights, so it collapses under forced sparsity and recovers toward L0 only at
    large budgets.
- **TRANSITION:** "Does the retained sample generalize to targets it never saw?"

## Slide 24 · Generalization
- **KEY MESSAGE:** Hold out whole families, not random cells, and informed selection carries
  over with the smaller in-sample-to-out-of-sample gap.
- **SAY:**
  - Why whole families: random target splits leak through nested totals (a held-out cell is
    nearly determined by its retained siblings), so they overstate generalization.
  - Read the figure: the gap between out-of-sample and in-sample error across the sweep.
    Informed L0's gap stays near zero; random + reweight fits the in-sample targets far more
    tightly but pays a large gap on families it never saw.
  - The reading: informed selection spends the budget on records that carry across families,
    rather than on driving the in-sample fit down.
- **TRANSITION:** "Accuracy is not the whole story — what does it cost?"

## Slide 25 · Reading the results honestly
- **KEY MESSAGE:** Lead with the median, and report effective sample size as a primary
  result — a good fit can still concentrate weight on a few records.
- **SAY:**
  - We lead with the median because a few near-zero-denominator targets inflate the mean; we
    name those targets in a one-time audit rather than winsorize.
  - Effective sample size is a result: matching a demanding target system can load population 
    mass onto a few records.
  - Read the figure: sweeping λ_L2 traces an effective-sample-size-against-accuracy frontier
    — cheap to buy at large budgets, costly at tight ones. Value shifts from accuracy toward
    operability and robustness.
- **TRANSITION:** "Where does this go next?"

## Slide 26 · Future work
- **KEY MESSAGE:** The proof of concept points at two production extensions; classical
  calibrators are related work, not missing baselines.
- **SAY:**
  - Build really large, then prune: push from the compact file to a deliberately over-built
    pool, then prune back to a publishable artifact at far more aggressive compression.
  - Congressional-district production builds: score the method on the full subnational
    surface it is designed for, not just national and state.
  - Broader held-out targets: bring district age, SNAP, and SOI facts into the held-out
    design.
  - If asked about GREG / IPF / raking / balanced sampling: they are reference methods for
    simpler margin surfaces, not full-surface baselines here — they apply only as robustness
    checks on the categorical-margin subsets where their assumptions hold (see the lit
    review). L1 is now in the sweep, not future work.
- **TRANSITION:** "To wrap up."

## Slide 27 · Takeaway
- **KEY MESSAGE:** Target-informed pruning is both a calibration method and a sampling
  method, with record count and weight concentration as tunable, reportable outputs.
- **SAY:** It selects records because they help reproduce the target system, and keeps the
  retained count and weight concentration as explicit controls. This is a proof of concept
  on national and state targets, built for the subnational case.

## Slide 28 · Questions
- **KEY MESSAGE:** Open the floor.
- **SAY:** Thank the audience and invite questions. Likely areas: the median/mean split, the
  effective-sample-size cost, and why classical calibrators are not baselines.
