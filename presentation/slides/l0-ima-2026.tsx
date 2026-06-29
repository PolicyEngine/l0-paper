"use client";

import AutoFitMath from "@/components/content/AutoFitMath";
import BulletList from "@/components/content/BulletList";
import ContentCard from "@/components/content/ContentCard";
import DonorFusion from "@/components/content/DonorFusion";
import EquationCard from "@/components/content/EquationCard";
import FactAnatomy from "@/components/content/FactAnatomy";
import Figure from "@/components/content/Figure";
import FrameAnatomy from "@/components/content/FrameAnatomy";
import GeographyHierarchy from "@/components/content/GeographyHierarchy";
import HardConcreteGate from "@/components/content/HardConcreteGate";
import Math from "@/components/content/Math";
import PipelineDiagram from "@/components/content/PipelineDiagram";
import StatNumber from "@/components/content/StatNumber";
import TranslationTable from "@/components/content/TranslationTable";
import Slide from "@/components/core/Slide";
import CoverSlide from "@/components/layout/CoverSlide";
import EndSlide from "@/components/layout/EndSlide";
import SectionSlide from "@/components/layout/SectionSlide";
import SlideTitle from "@/components/layout/SlideTitle";

const speakers = [
  {
    name: "Maria Juaristi",
    title: "PolicyEngine",
    headshot: "/headshots/maria-juaristi.png",
  },
];

/* ------------------------------------------------------------------ */
/* 0 · Open                                                            */
/* ------------------------------------------------------------------ */

export function TitleSlide() {
  return (
    <CoverSlide
      title="L0 regularization for subnational microsimulation calibration"
      subtitle="Selecting which microdata records survive when a faithful candidate population has to become a deployable dataset."
      event="IMA 2026, Brussels"
      date="2026-07-01"
      speakers={speakers}
    />
  );
}

export function RoadmapSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Roadmap">What this talk covers</SlideTitle>
        <BulletList
          className="mt-10 max-w-5xl"
          items={[
            "The goal: granular, live policy analysis across geographies.",
            "The data engine: Ledger facts and the Populace sampling frame.",
            "Why a faithful candidate dataset grows too large to ship.",
            "L0 regularization, from Louizos et al. to record selection.",
            "A proof-of-concept comparison, and where it goes next.",
          ]}
        />
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 1 · Motivation                                                      */
/* ------------------------------------------------------------------ */

export function PolicyGoalSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1fr_1fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Motivation">
            Policy questions arrive at every level of geography
          </SlideTitle>
          <p className="mt-8 max-w-2xl text-2xl leading-snug text-slate-600">
            PolicyEngine runs live tax-and-benefit simulations. The same reform question is asked
            nationally, by state, and by congressional district.
          </p>
          <p className="mt-6 max-w-2xl text-xl leading-snug text-slate-500">
            Each answer needs microdata that represents that geography, not a national average
            stretched to fit.
          </p>
        </div>
        <GeographyHierarchy subnote="Levels shown are the United States; the same nesting applies to any country with its own subnational divisions." />
      </div>
    </Slide>
  );
}

export function NestedTargetsSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1fr_1fr] items-center gap-12">
        <div>
          <SlideTitle kicker="The requirement">
            One weighted dataset must reproduce nested administrative totals
          </SlideTitle>
          <p className="mt-8 max-w-2xl text-2xl leading-snug text-slate-600">
            Calibration finds weights so the weighted dataset reproduces published totals. Subnational
            work makes this hierarchical: districts sum to states, and states to the nation, in a single
            set of weights.
          </p>
          <div className="mt-8 rounded-md bg-slate-50 px-6 py-5">
            <AutoFitMath>
              <Math
                display
                tex="\sum_i w_i\, x_{ij} = T_j \quad \text{for every target } j,\ \text{at every level}"
                className="text-[1.3rem]"
              />
            </AutoFitMath>
          </div>
        </div>
        <GeographyHierarchy showSummation />
      </div>
    </Slide>
  );
}

export function BuildBigThenPruneSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="The tension">Build big, then prune</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            A pipeline built for fidelity combines many sources and adds record-level variation. That
            makes the candidate dataset rich enough to represent the targets, and also too large to
            store and simulate.
          </p>
        </div>
        <div className="space-y-5">
          <ContentCard title="Build big" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Pool survey records, attach imputations, add geography, and oversample rare support where
              the population needs detail.
            </p>
          </ContentCard>
          <ContentCard title="The pressure point" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Calibration memory scales with targets times records; the shipped file still has to be
              cheap to store, load, and simulate.
            </p>
          </ContentCard>
          <ContentCard title="Prune with evidence" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Keep records because they help reproduce source-backed targets, not because they won an
              arbitrary random draw.
            </p>
          </ContentCard>
        </div>
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 2 · The data engine: Ledger + Populace                                */
/* ------------------------------------------------------------------ */

export function DataEngineSectionSlide() {
  return (
    <SectionSlide
      section="The data engine"
      title="From government publications to a shipped dataset"
      subtitle="Ledger turns published values into source-backed facts; Populace carries a weighted sampling frame through imputation, geography, and calibration."
    />
  );
}

export function LedgerSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1fr_1fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Ledger">Source-backed facts, provenance intact</SlideTitle>
          <BulletList
            className="mt-8"
            items={[
              "A fact pins a value to its geography, entity, measure, aggregation, and source.",
              "Ledger re-expresses published values; it never reconciles, ages, or imputes.",
            ]}
          />
          <p className="mt-7 text-base text-slate-400">
            Roughly 22k candidate facts, with 9k at district level; this build calibrates to 4,393
            active US targets.
          </p>
        </div>
        <FactAnatomy />
      </div>
    </Slide>
  );
}

export function PopulaceValueSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Populace">A population is a weighted sampling frame</SlideTitle>
          <BulletList
            className="mt-10"
            items={[
              "Entity tables preserve household, person, tax-unit, and family structure.",
              "Generation sets which records exist; calibration sets how much each counts. Keeping the two separate is what lets us prune records safely.",
            ]}
          />
        </div>
        <FrameAnatomy />
      </div>
    </Slide>
  );
}

export function PipelineSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Data pipeline">Populace carries one frame through the build</SlideTitle>
        <div className="mt-8">
          <PipelineDiagram />
        </div>
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 3 · Imputation mechanics                                            */
/* ------------------------------------------------------------------ */

export function RepresentativenessSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Imputation">
            Borrow whole distributions from many surveys
          </SlideTitle>
          <BulletList
            className="mt-9"
            items={[
              "Fill each gap from whichever survey measures it best — many surveys can be donors.",
              "The fitting step learns a conditional distribution on the donor data, not a single prediction.",
              "Predicting the whole distribution and sampling a draw per record preserves real variability.",
            ]}
          />
        </div>
        <DonorFusion />
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 4 · Reduction problem + Louizos + our method                        */
/* ------------------------------------------------------------------ */

export function SamplingQuestionSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="The reduction problem">A sampling problem with fitted weights</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            With a candidate universe and a target system fixed, reducing the dataset becomes a sampling
            problem with fitted weights and geographic representativeness constraints.
          </p>
        </div>
        <ContentCard accent="teal">
          <div className="space-y-6 text-2xl leading-snug text-slate-700">
            <div>
              <span className="font-bold text-pe-dark">Input:</span> candidate records, uniform weights,
              calibration targets
            </div>
            <div>
              <span className="font-bold text-pe-dark">Constraint:</span> retain a deployable number of
              records
            </div>
            <div>
              <span className="font-bold text-pe-dark">Goal:</span> preserve target fit for each
              represented geography
            </div>
            <div>
              <span className="font-bold text-pe-dark">Output:</span> selected records and calibrated
              positive weights
            </div>
          </div>
        </ContentCard>
      </div>
    </Slide>
  );
}

export function BaselinesSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Four methods">Where does selection enter the workflow?</SlideTitle>

        <div className="mt-9 grid grid-cols-2 gap-5">
          <ContentCard title="Informed L0" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              Hard-concrete gates select records and fit weights jointly; the L0 penalty sets an exact
              retained count.
            </p>
          </ContentCard>
          <ContentCard title="L1 (convex sparse)" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              A convex L1 penalty on weight magnitude; soft-thresholding drives small weights to
              exact zeros.
            </p>
          </ContentCard>
          <ContentCard title="Random + reweight" accent="slate">
            <p className="text-lg leading-snug text-slate-600">
              Draw a random subset first, then fit weights on that fixed subset.
            </p>
          </ContentCard>
          <ContentCard title="Survey-weight sampling" accent="amber">
            <p className="text-lg leading-snug text-slate-600">
              Calibrate the full universe first, then draw records with probability proportional to fitted
              weights.
            </p>
          </ContentCard>
        </div>

        <p className="mt-7 max-w-5xl text-xl leading-snug text-slate-500">
          Targets and candidate universe stay fixed, so the comparison isolates where selection enters.
        </p>
      </div>
    </Slide>
  );
}

export function LouizosFoundationSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.9fr_1.1fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Foundation">Louizos, Welling and Kingma (2018)</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Their problem was network sparsification: automatically zeroing weights in a neural network.
            The L0 norm counts non-zeros, but it is non-differentiable and combinatorial.
          </p>
          <BulletList
            className="mt-7"
            items={[
              "A hard-concrete gate stretches a continuous value past [0,1], then clips it back.",
              "Clipping creates point masses at exactly 0 and exactly 1.",
              "The probability a gate is open is closed-form and differentiable.",
            ]}
          />
        </div>
        <HardConcreteGate />
      </div>
    </Slide>
  );
}

export function TranslationSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="From their setting to ours">
          Translating L0 from weights to records
        </SlideTitle>
        <div className="mt-9">
          <TranslationTable />
        </div>
        <p className="mt-7 max-w-5xl text-xl leading-snug text-slate-500">
          The same machinery that prunes a network prunes a microdataset: records replace weights, and
          the retained-record count replaces the count of active weights.
        </p>
      </div>
    </Slide>
  );
}

export function L0MathSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Our method · training objective">
          L0 adds two terms to the calibration loss
        </SlideTitle>
        <div className="mt-8 grid grid-cols-2 gap-8">
          <EquationCard
            title="What the optimizer minimizes"
            equation="\begin{aligned}\mathcal{L}(w,\alpha)=\;&\mathcal{L}_{\mathrm{cal}}(w\odot z)\\[2pt]&+\;\lambda_{L_0}\textstyle\sum_i \Pr(z_i\neq 0)\\[2pt]&+\;\lambda_{L_2}\,\tfrac{1}{n}\textstyle\sum_i\!\left(\tfrac{w_i}{w_{0,i}}\right)^{2}\end{aligned}"
            note="The first term is the shared calibration loss, on gated weights. The L0 term prices open gates (λ_L0 sets the retained count via an outer bisection); the L2 term, with a hard weight cap, controls concentration."
          />
          <EquationCard
            title="Estimate and publication"
            equation="\hat{t}_j=\sum_i M_{ji}\,w_i\,z_i"
            note="A record contributes only through its gate. At publication, gates are evaluated deterministically: the result is an ordinary sparse microdataset with calibrated positive weights."
          />
        </div>
        <p className="mt-7 max-w-6xl text-xl leading-snug text-slate-600">
          
        </p>
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 5 · Proof of concept: design + results                              */
/* ------------------------------------------------------------------ */

export function ExperimentDesignSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Experiment design">
          One frozen input, four samplers, held-out target families
        </SlideTitle>
        <div className="mt-9 grid grid-cols-4 gap-5">
          <StatNumber value="75,112" label="households" sublabel="Populace US 2024 candidate file" />
          <StatNumber value="4" label="samplers" sublabel="L0, L1, random, survey-weight" />
          <StatNumber value="2k–40k" label="budget sweep" sublabel="aggressive compression upward" />
          <StatNumber value="206" label="held out" sublabel="family-level out-of-sample targets" />
        </div>
        <ContentCard className="mt-8" accent="teal">
          <p className="text-2xl leading-snug text-slate-700">
            All four methods share the calibrator, loss, and weight bounds; only record selection
            differs. Medicaid, SNAP, state income tax, and validation-only CBO targets stay out of every
            fit and are scored after calibration.
          </p>
        </ContentCard>
        <p className="mt-4 text-base text-slate-400">
        </p>
      </div>
    </Slide>
  );
}

export function CalibrationObjectiveSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Experiment · shared objective">
          All four methods are scored by the same loss
        </SlideTitle>
        <div className="mt-9 grid grid-cols-[1.15fr_0.85fr] items-center gap-10">
          <EquationCard
            title="The calibration loss: capped weighted MAPE"
            equation="\mathcal{L}_{\mathrm{cal}}(w)=\frac{\sum_j \omega_j\,\min\!\left(\left|\frac{\hat{t}_j-t_j}{s_j}\right|,\,c\right)}{\sum_j \omega_j}"
            note="Relative error puts count and dollar targets on one scale; the cap c limits any single hard-to-fit target. The reported runs use the production value c = 1."
          />
          <div>
            <div className="mb-3 text-base font-bold uppercase tracking-[0.16em] text-pe-teal">
              Held fixed across every method
            </div>
            <div className="space-y-2.5">
              {["Informed L0", "L1 (convex sparse)", "Random + reweight", "Survey-weight sampling"].map(
                (m) => (
                  <div
                    key={m}
                    className="rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-lg font-medium text-pe-dark"
                  >
                    {m}
                  </div>
                ),
              )}
            </div>
            <p className="mt-5 text-lg leading-snug text-slate-500">
              Same targets, same loss, same weight bounds. Only the sampler changes, so the comparison
              isolates selection.
            </p>
          </div>
        </div>
      </div>
    </Slide>
  );
}

export function MainFrontierSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Main result">Graceful degradation under compression</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            At the smallest budgets, informed selection spends the budget on the records the targets
            need, and leads. As the budget grows the baselines catch up: on the median they draw level
            and overtake, while informed L0 keeps the lower mean throughout.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            The crossover region is itself the finding. L1 anchors the convex point of comparison.
          </p>
        </div>
        <Figure
          src="/figures/f1_frontier.png"
          width={2168}
          height={886}
          alt="Out-of-sample median and mean ARE versus retained records for the four samplers"
        />
      </div>
    </Slide>
  );
}

export function GeneralizationSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1.1fr_0.9fr] items-center gap-10">
        <Figure
          src="/figures/f3_generalization_gap.png"
          width={1367}
          height={868}
          alt="Out-of-sample minus in-sample error across the budget sweep for the four methods"
        />
        <div>
          <SlideTitle kicker="Generalization">Hold out whole families, not random cells</SlideTitle>
          <BulletList
            className="mt-9"
            items={[
              "Random target splits leak through nested totals.",
              "Whole-family holdout tests reproduction of unseen domains.",
              "Informed selection carries over with the smaller in-sample to out-of-sample gap.",
            ]}
          />
        </div>
      </div>
    </Slide>
  );
}

export function OperabilitySlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Operability">Trading accuracy for usable weights</SlideTitle>
          <p className="mt-7 text-xl leading-snug text-slate-600">
            We lead with the median, because a few near-zero-denominator targets inflate the mean. And we
            report effective sample size as a primary result: matching a demanding target system can
            concentrate weight on a few records.
          </p>
          <div className="mt-6 space-y-2.5">
            <p className="border-l-[3px] border-pe-teal pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">L0 penalty:</span> sets the retained-record budget
              by pricing open gates.
            </p>
            <p className="border-l-[3px] border-slate-400 pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">L2 penalty:</span> softly discourages high
              fitted-weight ratios across the retained records.
            </p>
            <p className="border-l-[3px] border-pe-amber pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">Max weight ratio:</span> hard cap on how much any
              one record can inflate relative to its starting weight.
            </p>
          </div>
          <p className="mt-5 text-lg leading-snug text-slate-500">
            Sweeping the L2 penalty traces an effective-sample-size against accuracy frontier: cheap to buy
            at large budgets, costly at tight ones. Value shifts from accuracy toward operability and
            robustness.
          </p>
        </div>
        <Figure
          src="/figures/f6_operability.png"
          width={2175}
          height={886}
          alt="Effective sample size bought against out-of-sample accuracy cost as the L2 penalty varies, across budgets"
        />
      </div>
    </Slide>
  );
}

/* ------------------------------------------------------------------ */
/* 6 · Close                                                           */
/* ------------------------------------------------------------------ */

export function FutureWorkSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.9fr_1.1fr] items-center gap-12">
        <SlideTitle kicker="Future work">From proof of concept to production-scale pruning</SlideTitle>
        <div className="space-y-5">
          <ContentCard title="Build really large, then prune" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Push from the compact file to a deliberately over-built pool, then prune back to a
              publishable artifact.
            </p>
          </ContentCard>
          <ContentCard title="Congressional-district production builds" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Score the method on the full subnational target surface it is designed for, not just
              national and state.
            </p>
          </ContentCard>
          <ContentCard title="Broader held-out targets" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Bring district age, SNAP, and SOI facts into the held-out design.
            </p>
          </ContentCard>
        </div>
      </div>
    </Slide>
  );
}

export function TakeawaySlide() {
  return (
    <SectionSlide
      section="In closing"
      title="Target-informed pruning is both a calibration method and a sampling method"
      subtitle="It keeps records that help reproduce the targets, and turns dataset size and weight concentration into tunable, reportable controls — a proof of concept on national and state targets, built for the subnational case."
    />
  );
}

export function QuestionsSlide() {
  return <EndSlide />;
}
