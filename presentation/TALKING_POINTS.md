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
| 3 · Imputation | 10 | 1:30 |
| 4 · Reduction + Louizos + method | 11–15 | 4:00 |
| **First half** | **1–15** | **~12:00** |
| 5 · Proof of concept (design + results) | 16–20 | 5:30 |
| 6 · Close | 21–23 | 2:00 |
| **Second half** | **16–23** | **~7:30** |

## Delivery notes (PolicyEngine voice)

- Use exact numbers; never "large" / "significant" / "dramatically".
- Describe what the method does, not whether it is good. Sign the gaps ("17 points
  lower", "the smaller in-to-out gap"), do not say "better".
- Lead with the median; the mean is tail-sensitive and is reported, not headlined.
- Treat effective sample size as a result, not a caveat.
- This is a proof of concept on national and state targets — say so plainly.

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
- **KEY MESSAGE:** Two pieces: Ledger, the source-data foundation, and Populace, the
  microdata engine.
- **SAY:** One sentence: "Ledger turns government publications into source-backed facts;
  Populace is the engine that builds survey microdata into a calibrated, deployable
  population."

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
  - (If asked, the mechanics: quantile regression forests — weighted bootstrap, regime
    gates, sequential chaining.)
- **TRANSITION:** "All this richness multiplies the record count — which is why we prune."

## Slide 11 · The reduction problem
- **KEY MESSAGE:** With the universe and targets fixed, reduction is a sampling problem
  with fitted weights.
- **SAY:** Walk input → constraint → goal → output. Emphasize the output is selected
  records *and* calibrated positive weights — selection and weighting are coupled.
- **TRANSITION:** "There are four ways to do this, and they differ in where selection
  enters."

## Slide 12 · Four methods
- **KEY MESSAGE:** Four samplers, one shared calibrator; the comparison isolates where selection enters.
- **SAY:**
  - Target-informed sparse selection: **informed L0** (hard-concrete gates select and
    weight jointly; the L0 penalty sets an exact retained count) and **L1** (penalizes the
    total magnitude of the weights; a fixed pull toward zero each step sends any weight the
    targets do not strongly need to exactly zero, dropping that record).
  - The two classical baselines differ in ordering: **random + reweight** draws a subset
    first, then fits weights on it; **survey-weight sampling** calibrates the full universe
    first, then draws records with probability proportional to the fitted weights.
  - Targets and universe stay fixed, so the comparison isolates *where selection enters*.
- **TRANSITION:** "The two sparse methods come from a deep-learning idea — here is L0."

## Slide 13 · Louizos foundation
- **KEY MESSAGE:** Louizos, Welling and Kingma (2018) made L0 trainable by gradient
  descent for neural-network sparsification; we reuse that machinery.
- **SAY:**
  - Their goal was to make a neural network smaller by automatically driving some of its
    weights to exactly zero.
  - Why pure L0 "norm" (the count of non-zero weights) cannot be trained directly: 
    a count is a step function. It stays flat as a weight changes, then jumps by 
    one the instant the weight crosses zero. So its gradient is zero almost everywhere 
    and undefined at the jumps — gradient descent gets no signal telling it which weight 
    to turn off and thus cannot learn from it.
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
    fitted to initial weight.
  - The L2 term penalizes the squared magnitude of each fitted weight
    (relative to its starting weight), which discourages loading the fit onto a few very
    large weights — that keeps population mass spread across records, so the effective
    sample size stays high and the dataset stays usable downstream. A hard per-record cap
    bounds the single largest weight as a backstop.
  - A a record only contributes to the training objective when its gate is open.
  - At publication, gates are evaluated deterministically: the output is an ordinary
    sparse dataset with calibrated positive weights.
  - The point: **selection is trained against the same target system the final weights must**
    **match, so records survive when keeping them helps reproduce a target.**
- **TRANSITION:** "So does informed selection actually beat the baselines? Here is the proof of concept."

---

# Second half — proof of concept (slides 16–23)

> Numbers and figures below reflect the final four-way sweep (L0 vs L1 vs random vs
> survey-weight), production loss cap c=1, run `4way-l1-cap1`.

## Slide 16 · Experiment design
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

## Slide 17 · Calibration objective
- **KEY MESSAGE:** One loss scores every method — capped weighted MAPE (Mean Abs % Error).
- **SAY:**
  - Relative error puts count and dollar targets on one scale; the cap c limits any single
    hard-to-fit target, so one bad row cannot dominate the gradient.
  - The reported runs use the production cap c=1, so targets more than 100% away do not contribute
    to the gradient. 
  - The per-target weights ω_j scale each target by the square root of its size, within two
    bases (count vs dollar) that are rescaled to contribute equally — so large aggregates
    count for more, and the many dollar cells do not swamp the count targets.
  - Same targets, same loss, same weight bounds — only the sampler changes.
- **TRANSITION:** "So where does informed selection actually win?"

## Slide 18 · Main frontier
- **KEY MESSAGE:** Graceful degradation under compression — informed selection leads at
  tight budgets, the baselines draw level as the budget grows.
- **SAY:**
  - Read the figure: out-of-sample error against retained records, median and mean panels,
    all four methods.
  - At 2,000 records, informed L0's median out-of-sample ARE (Abs Rel Error) is 47.3% vs random 
    50.1%, survey-weight 48.1%, and L1 at 100% (its weights collapse toward zero); on the 
    tail-sensitive mean the gap is far wider — 225% vs random's 1,798%.
  - As the budget grows the baselines draw level: on the median, random + reweight overtakes
    from ~5,000 records up, while informed L0 keeps the lower mean at every budget.
    At 10k, L0 median is 35.0%.
  - L1 is the convex point of comparison, and the weakest arm at every budget: one penalty
    cannot both select records and size their weights, so it collapses under forced sparsity
    and recovers toward L0 only at the largest budgets.
- **TRANSITION:** "Does the retained sample generalize to targets it never saw?"

## Slide 19 · Generalization
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

## Slide 20 · Operability
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

## Slide 21 · Future work
- **KEY MESSAGE:** The proof of concept points at two production extensions; classical
  calibrators are related work, not missing baselines.
- **SAY:**
  - Build really large, then prune: push from the compact file to a deliberately over-built
    pool, then prune back to a publishable artifact at far more aggressive compression.
  - Congressional-district production builds: score the method on the full subnational
    surface it is designed for, not just national and state.
  - Broader held-out targets: bring district age, SNAP, and SOI facts into the held-out
    design.
  - [If asked about GREG / IPF / raking / balanced sampling: they are reference methods for
    simpler margin surfaces, not full-surface baselines here — they apply only as robustness
    checks on the categorical-margin subsets where their assumptions hold (see the lit
    review). L1 is now in the sweep, not future work.]
- **TRANSITION:** "To wrap up."

## Slide 22 · Conclusion
- **KEY MESSAGE:** Target-informed pruning is both a calibration method and a sampling
  method, with record count and weight concentration as tunable, reportable outputs.
- **SAY:** It selects records because they help reproduce the target system, and keeps the
  retained count and weight concentration as explicit controls. This is a proof of concept
  on national and state targets. We will build on the observed operability and performance 
  at large compression regimes to score the subnational case.

## Slide 23 · Questions
- **KEY MESSAGE:** Open the floor.
- **SAY:** Thank the audience and invite questions. Likely areas: the median/mean split, the
  effective-sample-size cost, and why classical calibrators are not baselines.
