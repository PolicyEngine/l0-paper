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
            "The institutional setting: PolicyEngine in the United States and United Kingdom.",
            "The modeling problem: local-area weights worked in the UK, but not as a direct US template.",
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
            PolicyEngine runs live tax-and-benefit simulations in the United States and the
            United Kingdom. Analysts ask the same reform question nationally, by state or region,
            and by local constituency.
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

export function LocalAreaModelingSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Why US pruning is different">
          The UK local-area approach did not transfer cleanly
        </SlideTitle>
        <div className="mt-9 grid grid-cols-3 gap-5">
          <ContentCard title="PolicyEngine scope" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              PolicyEngine maintains open-source microsimulation models for the US and UK, with
              applications that need national and local estimates from the same policy logic.
            </p>
          </ContentCard>
          <ContentCard title="UK first implementation" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Our first local-area system kept one national microdataset and built a matrix of
              weights by parliamentary constituency and local authority.
            </p>
          </ContentCard>
          <ContentCard title="The limitation" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Separate area-weight columns can disagree across overlapping geographies. The
              inconsistency gets worse as users ask for more geographic breakdowns.
            </p>
          </ContentCard>
        </div>
        <p className="mt-8 max-w-6xl text-2xl leading-snug text-slate-600">
          In the US, users need state, county, congressional-district, and state-legislative
          views. Policy also varies locally, mostly by state and sometimes by county, so local
          geography has to live on the records themselves.
        </p>
      </div>
    </Slide>
  );
}

export function LongwiseGeographySlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="US design choice">
          Go longwise: assign records to the finest geography
        </SlideTitle>
        <div className="mt-9 grid grid-cols-4 gap-4">
          <ContentCard title="1. Place households" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              Assign each household a Census block, the finest local identifier in the build.
            </p>
          </ContentCard>
          <ContentCard title="2. Derive geographies" accent="slate">
            <p className="text-lg leading-snug text-slate-600">
              Build state, county, congressional-district, and legislative-district views from the
              block assignment.
            </p>
          </ContentCard>
          <ContentCard title="3. Oversaturate support" accent="amber">
            <p className="text-lg leading-snug text-slate-600">
              Synthesize many candidate households because the source survey lacks true local
              identifiers.
            </p>
          </ContentCard>
          <ContentCard title="4. Calibrate and prune" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              Use targets to decide which synthetic placements survive in a deployable dataset.
            </p>
          </ContentCard>
        </div>
        <p className="mt-8 max-w-6xl text-2xl leading-snug text-slate-600">
          The block assignment makes every geography internally consistent, but it creates a large
          candidate universe with many plausible household-to-place assignments. L0 is a way to prune
          that universe using the same target loss that calibrates it.
        </p>
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
            Current run: 37,053 Ledger facts compile to 32,633 active targets, including 24,340
            congressional-district targets.
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
        <SlideTitle kicker="Five completed arms">Where does selection enter the workflow?</SlideTitle>

        <div className="mt-9 grid grid-cols-5 gap-4">
          <ContentCard title="Informed L0" accent="teal">
            <p className="text-base leading-snug text-slate-600">
              Hard-concrete gates select records and fit weights jointly.
            </p>
          </ContentCard>
          <ContentCard title="L0 + refit" accent="teal">
            <p className="text-base leading-snug text-slate-600">
              Keep selected records, remove gates, and refit ordinary calibration weights.
            </p>
          </ContentCard>
          <ContentCard title="Dense no-L0" accent="teal">
            <p className="text-base leading-snug text-slate-600">
              Fit ordinary calibration weights on the full candidate universe.
            </p>
          </ContentCard>
          <ContentCard title="Random + reweight" accent="slate">
            <p className="text-base leading-snug text-slate-600">
              Draw a random subset first, then fit weights on that fixed subset.
            </p>
          </ContentCard>
          <ContentCard title="Dense sample" accent="amber">
            <p className="text-base leading-snug text-slate-600">
              Randomly keep dense calibrated weights and scale them back to total mass.
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
          One frozen input, the full Populace target surface
        </SlideTitle>
        <div className="mt-9 grid grid-cols-4 gap-5">
          <StatNumber value="337,704" label="households" sublabel="three-year ASEC support" />
          <StatNumber value="5" label="method arms" sublabel="L0, dense, random baselines" />
          <StatNumber value="57,240" label="retained" sublabel="matched record count" />
          <StatNumber value="32,633" label="targets" sublabel="all fit and scored" />
        </div>
        <ContentCard className="mt-8" accent="teal">
          <p className="text-2xl leading-snug text-slate-700">
            All methods share the candidate frame, Populace production loss, target weights, and
            scoring path; only record selection differs. The headline experiment fits and scores the
            full materialized surface, including validation and district targets.
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
          All methods are scored by the same loss
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
              {["Informed L0", "L0 + refit", "Dense no-L0", "Random + reweight", "Dense sample, scaled"].map((m) => (
                <div
                  key={m}
                  className="rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-lg font-medium text-pe-dark"
                >
                  {m}
                </div>
              ))}
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
          <SlideTitle kicker="Main result">L0 selects a better support than random</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            On the current full Populace target surface, the raw gated L0 weights are not the publication
            weights. But the records selected by the gates become substantially more accurate after an
            ordinary calibration refit.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            At 57,240 records, L0 + refit reaches 4.74% Populace loss. Dense no-L0 with all records is
            5.07%, and random + reweight at the same count is 7.55%.
          </p>
        </div>
        <Figure
          src="/figures/f0_objective_frontier.png"
          width={2168}
          height={886}
          alt="Matched full-surface Populace objective loss for L0 gated weights, L0 refit, and random reweight"
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
          src="/figures/f1_frontier.png"
          width={2168}
          height={886}
          alt="Full-surface median and mean absolute relative error versus retained records for the four samplers"
        />
        <div>
          <SlideTitle kicker="Diagnostics">Median and mean tell different stories</SlideTitle>
          <BulletList
            className="mt-9"
            items={[
              "The Populace loss is the headline score; raw ARE is supplemental.",
              "Median ARE shows typical target fit across the full surface.",
              "Mean ARE remains tail-sensitive, so we report it as a diagnostic rather than the main score.",
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
          <SlideTitle kicker="Concentration">The selected subset is also better conditioned</SlideTitle>
          <p className="mt-7 text-xl leading-snug text-slate-600">
            Effective sample size is a primary result, not a footnote. In this matched probe, dense
            calibration has the highest sparse-fit ESS because it retains all records; among sparse
            supports, L0 + refit beats random + reweight on both target loss and concentration.
          </p>
          <div className="mt-6 space-y-2.5">
            <p className="border-l-[3px] border-pe-teal pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">L0 + refit:</span> ESS 4,726; max weight 913,836.
            </p>
            <p className="border-l-[3px] border-teal-700 pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">Dense no-L0:</span> ESS 5,970; max weight 579,298.
            </p>
            <p className="border-l-[3px] border-slate-400 pl-4 text-lg leading-snug text-slate-600">
              <span className="font-bold text-pe-dark">Random + reweight:</span> ESS 2,480; max weight
              1,163,939.
            </p>
          </div>
          <p className="mt-5 text-lg leading-snug text-slate-500">
            The next methodological work is a normalized-penalty sweep, with concentration controls added
            around this full-surface result.
          </p>
        </div>
        <Figure
          src="/figures/f2_usability.png"
          width={2168}
          height={886}
          alt="Effective sample size and largest fitted weight versus retained records for the four samplers"
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
              Sweep normalized L0 penalties on the three-year support and larger over-built pools, then
              prune back to a publishable artifact.
            </p>
          </ContentCard>
          <ContentCard title="Complete the comparator set" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Add PPS survey-weight sampling, categorical-margin raking panels, longer dense convergence
              checks, and concentration controls around the same Populace loss.
            </p>
          </ContentCard>
          <ContentCard title="Targeted robustness" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Keep family holdouts separate from the headline fit; use them to test robustness, not as the
              production objective.
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
      title="Target-informed pruning works as support selection"
      subtitle="The full-surface probe says: choosing a sparse support with L0 and then refitting reaches lower completed-run loss than dense no-L0 and matched random baselines."
    />
  );
}

export function QuestionsSlide() {
  return <EndSlide />;
}
