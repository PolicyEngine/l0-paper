# Combinatorial optimization, random sampling, and weighted sampling for microdata reduction and small-area calibration: a focused review

*Prepared for the L0-regularized microsimulation calibration paper. These three methods are the ones with a genuine track record of reducing or constructing a microdata file by selecting records to match known totals, which is why they belong in the empirical comparison. Each section gives the formal definition and grounding work first, then traces how the method has been used for microdata calibration, dataset reduction, and small-area (local) subsampling. A note on scope: "applicable with prior domain use" is not the same as "the only mathematically valid options" — recombination, NNLS, and balanced sampling remain valid imports, and the L0 gates are one too, but none has been applied to microdata-file reduction before, so they sit better as contributions than as established baselines.*

---

## 1. Combinatorial optimization

### Formal definition

Combinatorial optimization (CO) treats record selection as a discrete optimization problem. Given a pool of candidate records (a survey microdata file or sample of anonymised records) and a set of benchmark constraint tables holding the known totals for an area, the task is to choose a combination of records — a subset, generally with integer multiplicities so that records can be cloned — that reproduces those totals as closely as possible. Fit is measured by an aggregate error statistic, classically the Total Absolute Error,

TAE = Σ over constraints j of | T̂ⱼ − Tⱼ |,

where Tⱼ is the benchmark total for cell j and T̂ⱼ is the corresponding total computed from the currently selected set, summed over all constraint tables and, in the spatial case, all areas. Because the search space is the combinatorial set of possible subsets, exhaustive evaluation is infeasible for any realistic size, so CO is solved with metaheuristics that explore the space intelligently. The standard ladder of search strategies, in increasing sophistication, is random swapping of one record at a time, hill-climbing (only accept swaps that lower TAE), simulated annealing (accept a worsening swap with probability exp(−ΔE/T), with the temperature T cooled over the run so the search can escape local minima early and settle late), and genetic algorithms (evolve a population of candidate selections through selection, crossover, and mutation). A lighter variant, quota sampling, draws records at random and admits a record only if it improves the fit, never replacing an admitted record, which makes it a one-pass sampling-without-replacement procedure.

### Grounding work

The method was introduced for population microdata by Williamson, Birkin and Rees (1998), who set out the TAE objective and compared random, hill-climbing, simulated-annealing, and genetic-algorithm searches, finding simulated annealing the most reliable. The simulated-annealing engine itself comes from Kirkpatrick, Gelatt and Vecchi (1983). Voas and Williamson (2000) gave the first systematic evaluation of the approach for synthetic microdata and, with their 2001 paper, developed the goodness-of-fit measures used to judge it. Huang and Williamson (2001) compared CO against synthetic reconstruction and found CO produced microdata fitting the constraint tables at least as well and with much lower run-to-run variability.

### Use in microdata calibration, reduction, and small-area work

CO is, in effect, calibration performed at the selection stage rather than the weighting stage: the selected set is chosen precisely so its aggregates match the benchmark totals. It has been the workhorse of a generation of small-area microsimulation models, including SimLeeds, Micro-MaPPAS, the static base-population step of SMILE for Ireland, MOSES, SimObesity, and SimAthens. The most useful methodological comparisons for your purposes are Harland, Heppenstall, Smith and Birkin (2012), which evaluated deterministic reweighting, conditional-probability (Monte Carlo IPF) reconstruction, and simulated annealing across several spatial scales using an absolute-error criterion, and Tanton, Williamson and Harding (2014), which compared CO directly against the generalised-regression reweighting used in the Australian SpatialMSM model and found CO slightly more accurate and able to return a solution for nearly every area where GREG sometimes failed to converge.

Two findings from this literature bear directly on your benchmark. First, the limitation Voas and Williamson identified: CO reproduces the variables it is constrained on well but reproduces cross-tabulations of non-constrained variables poorly, which is the concrete form of the "preserves the targeted totals, not necessarily the rest of the distribution" tension. Second, the cost: the search is computationally heavy, run-to-run stochastic, and several authors note it can become intractable for very large populations, which is exactly the operability axis on which a gradient method should have the advantage.

Recent work has pushed CO toward scale and hierarchy. A 2024 multi-objective combinatorial-optimization framework for large-scale hierarchical population synthesis (arXiv:2407.03180) handles nested individual-and-household structure and minimises contingency-table reconstruction error at large population sizes, which is the closest published setting to your nested-geography calibration. GREASYPOP-CO (2023) is a recent applied CO codebase for building geographically realistic synthetic populations. Implementations: the validated reference is R `simPop` (simulated-annealing calibration) and R `sms`; in Python the practical route is to define the TAE energy and a record-swap move on top of the `simanneal` package, since there is no turnkey Python equivalent.

---

## 2. Random sampling

### Formal definition

Simple random sampling without replacement gives every subset of size n from the N records an equal chance of selection, so each record has inclusion probability πᵢ = n/N and design weight dᵢ = 1/πᵢ = N/n. The Horvitz–Thompson estimator of a population total, Σ over the sample of yᵢ/πᵢ, then collapses to N·ȳ, the expanded sample mean, and is design-unbiased for the total with variance of order (1−f)S²/n, where f = n/N is the sampling fraction. Practical variants include Bernoulli and Poisson sampling, where each record is kept independently with a fixed probability (no replicate draws, no need to hold the whole file in memory), and reservoir sampling, which draws a fixed-size random sample in a single streaming pass.

### Grounding work

The design-based theory traces to Neyman (1934) and is consolidated in the standard texts: Cochran (1977), Kish (1965), and Särndal, Swensson and Wretman (1992). The unbiased estimation of totals from a sample rests on Horvitz and Thompson (1952).

### Use in microdata calibration, reduction, and small-area work

Random subsampling is the canonical reduction baseline against which every more elaborate method is measured. In the big-data subsampling literature it is the uniform reference that informativeness-based schemes try to beat, and the leveraging analysis of Ma, Mahoney and Yu (2015) is framed explicitly as uniform-versus-nonuniform random subsampling. Notably, the DeepCore benchmark (Guo et al., 2022) reports that random selection remains a strong baseline that many sophisticated pruning methods fail to beat at high reduction ratios — a useful point for your paper, since it means an "L0 versus random" comparison is the test the data-reduction field treats as real rather than a straw man.

Within microsimulation, random selection appears in three roles. It is the initialisation of combinatorial optimisation (Williamson, Birkin and Rees 1998 start from a random draw and improve it). It is used to run a model on a manageable subset of a full population to test scenarios cheaply, as in the SVERIGE dynamic model, where modules are run on either a random sample or the full Swedish population. And it appears inside iterative procedures such as the iterative proportional sampling used in MOSES (Birkin et al. 2006), which draws a random sample of anonymised records and then adjusts. On the calibration axis, the key property is the limitation: a random subsample preserves the distribution in expectation but does not reproduce the external administrative totals, so in your setting it is the "reduce first, calibrate after" baseline (random draw, then GREG or IPF to the targets). Implementation is a single NumPy call, or reservoir sampling for a one-pass draw over a large file.

---

## 3. Weighted sampling

### Formal definition

Weighted, or unequal-probability, sampling selects records with probabilities that depend on a size or weight variable. In probability-proportional-to-size (PPS) sampling the inclusion probability is set proportional to a known auxiliary, πᵢ ∝ xᵢ, and unbiased totals are recovered with the Horvitz–Thompson estimator (without replacement) or the Hansen–Hurwitz estimator (with replacement); the two coincide for without-replacement designs. Choosing πᵢ proportional to an x that is well correlated with the study variable reduces the variance of the estimated total, which is the entire rationale for the design, and PPS is essentially optimal for subset-sum estimation.

In the microsimulation context the dominant form of weighted sampling is **integerisation**: converting the fractional weights produced by a calibration step (IPF, GREG) into a whole number of cloned records by selecting records with probability proportional to their weight. This is the operation needed to turn a reweighted file into a finite, simulable population, and it is the natural "reduce right after calibration" route for your problem. The benchmark integerisation method, "truncate, replicate, sample" (TRS), has three steps: truncate each weight into an integer replication part and a fractional remainder; replicate each record by its integer part; then fill the remaining quota by weighted sampling without replacement on the fractional remainders. Because it samples the remainders rather than rounding them, it preserves the population size exactly and matches the aggregate constraints more tightly than rounding.

### Grounding work

PPS and unequal-probability estimation come from Hansen and Hurwitz (1943) and Horvitz and Thompson (1952), with the general design-based treatment in Särndal, Swensson and Wretman (1992). For integerisation specifically, Ballas et al. (2005) introduced the "threshold" and "counter-weight" top-up methods, Pritchard and Miller (2012) advanced the area, and Lovelace and Ballas (2013) catalogued the five methods — three deterministic (simple rounding, threshold, counter-weight) and two probabilistic (proportional probabilities, TRS) — and showed TRS to be the most accurate and fast. The foundational sample-based population-synthesis paper, Beckman, Baggerly and McKay (1996), is the ancestor of using a survey sample plus reweighting to build a population, as opposed to the sample-free synthesis of Barthelemy and Toint (2013).

### Use in microdata calibration, reduction, and small-area work

Weighted sampling is how spatial microsimulation routinely turns calibrated weights into a reduced, integer-weighted microdata file. TRS is used in SimAthens for small-area income and poverty estimation, in SimObesity, and across the models reviewed by Lovelace and Dumont (2016); it is described as "weighted sampling without replacement" and implemented in R via `wrswoR` and the original Lovelace–Ballas code. Because the selection probabilities are the calibration weights, the reduced file approximately preserves both the calibrated totals and the joint distribution, which is why it dominates simple random reduction in this literature, and TRS in particular guarantees the reduced population has exactly the target size.

On the calibration axis, the important structural point is that weighted sampling presupposes a calibration step: you first solve for weights that hit the external totals, then sample proportional to those weights. So in your framework it is the "calibrate, then reduce" baseline, complementary to CO's "reduce-as-calibration" and to random sampling's "reduce, then calibrate." In the broader subsampling literature, the principled versions of weighted sampling are leverage-score and OSMAC-type importance subsampling, where the weights are derived to minimise estimator variance rather than taken from a calibration; PPS being optimal for subset-sum is the abstract statement of why weighting by the right quantity beats uniform sampling. Implementation: NumPy weighted choice or R `wrswoR` for the sampling step; R `sampling` (`UPsystematic`, `UPpoisson`, `UPmultinomial`) for the classical PPS designs.

---

## Synthesis: how the three sit on your axes

All three reduce the file by selecting actual records, and they differ in where the calibration enters:

- **Combinatorial optimisation** targets the totals at the moment of selection — it is calibration-by-selection. It returns integer weights, is stochastic across runs, is the slowest of the three, and reproduces the constrained variables well but the unconstrained distribution less so. It is the discrete, gradient-free sibling of your L0 method, and the most informative non-trivial baseline.
- **Random sampling** preserves the conditional distribution in expectation but ignores the totals, which it can only recover through a post-hoc calibration. It is the fastest and the floor against which the others must justify themselves; the data-reduction field treats beating it as the genuine test.
- **Weighted sampling (integerisation)** bridges the two: by sampling proportional to calibration weights it approximately preserves both the calibrated totals and the distribution, and TRS fixes the size exactly. It assumes a prior calibration, so it is "calibrate, then reduce."

For your stated objective — reproduce the totals and, through them, preserve the conditional distribution — the three span the design space cleanly: CO pursues both at selection, weighted sampling pursues both conditional on a calibration step, and random sampling is the distribution-only floor. The experiment that discriminates among them, and that frames your contribution, is to sweep the retained size k and plot calibration error against a held-out distributional fidelity measure computed on cross-tabulations you deliberately did not calibrate to. That second axis is what separates "matched the totals" from "preserved the distribution," and it is the question your paper is really testing — with your L0 gates and CO as the methods that pursue both, and random and weighted sampling as the floor and the calibrate-then-reduce reference respectively.

---

## Bibliography

### Combinatorial optimisation
- Williamson, P., Birkin, M. & Rees, P. (1998). The estimation of population microdata by using data from small area statistics and samples of anonymised records. *Environment and Planning A* 30(5), 785–816.
- Kirkpatrick, S., Gelatt, C.D. & Vecchi, M.P. (1983). Optimization by simulated annealing. *Science* 220(4598), 671–680.
- Voas, D. & Williamson, P. (2000). An evaluation of the combinatorial optimisation approach to the creation of synthetic microdata. *Int. J. Population Geography* 6(5), 349–366.
- Voas, D. & Williamson, P. (2001). Evaluating goodness-of-fit measures for synthetic microdata. *Geographical and Environmental Modelling* 5(2), 177–200.
- Huang, Z. & Williamson, P. (2001). *A comparison of synthetic reconstruction and combinatorial optimisation approaches to the creation of small-area microdata.* Working Paper 2001/02, Dept. of Geography, University of Liverpool.
- Harland, K., Heppenstall, A., Smith, D. & Birkin, M. (2012). Creating realistic synthetic populations at varying spatial scales: a comparative critique of population synthesis techniques. *JASSS* 15(1), 1.
- Tanton, R., Williamson, P. & Harding, A. (2014). Comparing two methods of reweighting a survey file to small area data: generalised regression and combinatorial optimisation. *Int. J. Microsimulation* 7(1), 76–99.
- Farrell, N., Morrissey, K. & O'Donoghue, C. (2013). Creating a spatial microsimulation model of the Irish local economy (quota sampling). In Tanton & Edwards (eds.), *Spatial Microsimulation: A Reference Guide for Users*, Springer, 105–125.
- Multi-objective combinatorial optimisation framework for large-scale hierarchical population synthesis (2024). **[verified]** arXiv:2407.03180
- GREASYPOP-CO — geographically realistic synthetic population using combinatorial optimisation. **[verified]** https://github.com/CDDEP-DC/GREASYPOP-CO

### Random sampling
- Neyman, J. (1934). On the two different aspects of the representative method. *J. Royal Statistical Society* 97(4), 558–625.
- Horvitz, D.G. & Thompson, D.J. (1952). A generalization of sampling without replacement from a finite universe. *JASA* 47(260), 663–685.
- Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.
- Kish, L. (1965). *Survey Sampling*. Wiley.
- Särndal, C.-E., Swensson, B. & Wretman, J. (1992). *Model Assisted Survey Sampling*. Springer.
- Ma, P., Mahoney, M. & Yu, B. (2015). A statistical perspective on algorithmic leveraging. *JMLR* 16, 861–911.
- Guo, C. et al. (2022). DeepCore: a comprehensive library for coreset selection in deep learning. **[verified]** arXiv:2204.08499

### Weighted sampling and integerisation
- Hansen, M.H. & Hurwitz, W.N. (1943). On the theory of sampling from finite populations. *Annals of Mathematical Statistics* 14(4), 333–362.
- Beckman, R.J., Baggerly, K.A. & McKay, M.D. (1996). Creating synthetic baseline populations. *Transportation Research Part A* 30(6), 415–429.
- Ballas, D., Clarke, G., Dorling, D., Eyre, H., Thomas, B. & Rossiter, D. (2005). SimBritain: a spatial microsimulation approach to population dynamics (threshold and counter-weight integerisation). *Population, Space and Place* 11, 13–34.
- Pritchard, D.R. & Miller, E.J. (2012). Advances in population synthesis: fitting many attributes per agent and fitting to household and person margins simultaneously. *Transportation* 39(3), 685–704.
- Lovelace, R. & Ballas, D. (2013). 'Truncate, replicate, sample': a method for creating integer weights for spatial microsimulation. *Computers, Environment and Urban Systems* 41, 1–11. **[verified]** arXiv:1303.5228 ; code https://github.com/Robinlovelace/IPF-performance-testing
- Barthelemy, J. & Toint, P.L. (2013). Synthetic population generation without a sample. *Transportation Science* 47(2), 266–279.
- Lovelace, R. & Dumont, M. (2016). *Spatial Microsimulation with R*. CRC Press.

### Software
- R `simPop` — Templ, Meindl, Kowarik & Dupriez (2017), *J. Statistical Software* 79(10): synthetic populations via IPF, simulated annealing, and model-based methods.
- R `sms` — Kavroudakis (2015), *J. Statistical Software* 68(2): spatial microsimulation by combinatorial optimisation.
- R `wrswoR`, `sampling` (`UPsystematic`, `UPpoisson`, `UPmultinomial`): weighted/PPS sampling.
- Python `simanneal`: generic simulated annealing for a CO implementation; `numpy.random.choice` for random and weighted draws.

*Verification note: items marked **[verified]** were confirmed during this research. The survey-sampling texts and the older spatial-microsimulation references are standard citations given with enough detail to locate; confirm exact page ranges and the `simPop`/`sms` JSS issue numbers before final submission.*