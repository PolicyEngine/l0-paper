"use client";

import BulletList from "@/components/content/BulletList";
import ContentCard from "@/components/content/ContentCard";
import DonorFusion from "@/components/content/DonorFusion";
import EquationCard from "@/components/content/EquationCard";
import FactAnatomy from "@/components/content/FactAnatomy";
import Figure from "@/components/content/Figure";
import FrameAnatomy from "@/components/content/FrameAnatomy";
import HardConcreteGate from "@/components/content/HardConcreteGate";
import LossBars from "@/components/content/LossBars";
import PipelineDiagram from "@/components/content/PipelineDiagram";
import StatNumber from "@/components/content/StatNumber";
import TranslationTable from "@/components/content/TranslationTable";
import WeightFormats from "@/components/content/WeightFormats";
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
        <Figure
          src="/figures/snap_benefits_by_district.png"
          width={4788}
          height={3431}
          alt="Hexagonal cartogram of estimated SNAP benefits for every US congressional district"
        />
      </div>
    </Slide>
  );
}

export function WeightLayoutWideSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Weight layout">
          Two matrix representations of subnational weights
        </SlideTitle>
        <WeightFormats className="mt-12" showLong={false} />
      </div>
    </Slide>
  );
}

export function WeightLayoutBothSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Weight layout">
          Two matrix representations of subnational weights
        </SlideTitle>
        <WeightFormats className="mt-12" showLong />
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
              "The spine is three years of CPS ASEC pooled and aged to one period — more households and variability, while keeping the CPS survey design.",
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

// --- Main result: progressive loss-bar arc (one beat per slide; the deck has no
// in-slide reveal, so each beat is its own slide sharing the LossBars component). ---

export function ResultsArcBaselinesSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Main result · where we start">
            Two reference points before we prune cleverly
          </SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Keep every record and calibrate (dense no-L0) and you reach 5.07% on the full Populace
            surface. Naively prune to 57,240 at random and refit weights on that subset, and you get
            7.55%.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            Dense uses all 337,704 records, so it is a reference, not a deployable budget. The question
            is how close a 57,240-record file can get.
          </p>
        </div>
        <LossBars revealed={["dense_full", "random_reweight"]} />
      </div>
    </Slide>
  );
}

export function ResultsArcScaledSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Main result · skip the reweighting?">
            The reweighting was doing the work
          </SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Take the same random sample but keep the dense weights and just rescale them to the
            population total, with no refit. Loss jumps to 24.24%.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            So the gain from random + reweight came from re-fitting the weights on the retained subset,
            not from the sample itself.
          </p>
        </div>
        <LossBars revealed={["dense_full", "random_reweight", "dense_scaled"]} />
      </div>
    </Slide>
  );
}

export function ResultsArcL0Slide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Main result · the informed selector: L0">
            A target-informed selector &mdash; yet it underperforms
          </SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Informed L0 chooses the 57,240 records jointly with their gated weights. It should beat a
            blind random sample. But the raw gated weights score 9.86% &mdash; worse than random +
            reweight.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            The gates select the support well, but the gated weights they return are not publication
            weights.
          </p>
        </div>
        <LossBars revealed={["dense_full", "random_reweight", "dense_scaled", "l0_gated"]} />
      </div>
    </Slide>
  );
}

export function ResultsArcRefitSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.78fr_1.22fr] items-center gap-10">
        <div>
          <SlideTitle kicker="Main result · refit once more">
            Refit the selected records and L0 wins
          </SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Keep the records the gates chose, drop the gates, and refit ordinary calibration weights on
            that subset. Loss drops to 4.74% &mdash; below dense no-L0&rsquo;s 5.07%, and well below every
            sampling baseline.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            L0&rsquo;s value is <span className="font-bold text-pe-dark">support selection</span>,
            realized only after the post-selection refit.
          </p>
        </div>
        <LossBars revealed={["dense_full", "random_reweight", "dense_scaled", "l0_gated", "l0_refit"]} />
      </div>
    </Slide>
  );
}

export function GeographyAccuracySlide() {
  const rows = [
    { level: "National", targets: "478", median: "1.30", mean: "20.12", max: "557" },
    { level: "State", targets: "7,815", median: "0.31", mean: "86.36", max: "122,712" },
    { level: "Congressional district", targets: "24,340", median: "1.48", mean: "85.29", max: "162,496" },
  ];
  return (
    <Slide>
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Main result · by geography">
          The refit fit holds at every geographic level
        </SlideTitle>
        <p className="mt-6 max-w-5xl text-xl leading-snug text-slate-600">
        </p>
        <div className="mt-8 overflow-hidden rounded-lg border border-slate-200">
          <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] bg-slate-50 px-6 py-3 text-sm font-bold uppercase tracking-[0.12em] text-pe-dark">
            <div>Geographic level</div>
            <div className="text-right">Targets</div>
            <div className="text-right">Median ARE</div>
            <div className="text-right">Mean ARE</div>
            <div className="text-right">Max ARE</div>
          </div>
          {rows.map((r) => (
            <div
              key={r.level}
              className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] border-t border-slate-100 px-6 py-3 text-lg text-slate-700"
            >
              <div className="font-semibold text-pe-dark">{r.level}</div>
              <div className="text-right tabular-nums">{r.targets}</div>
              <div className="text-right font-bold tabular-nums text-pe-teal">{r.median}%</div>
              <div className="text-right tabular-nums text-slate-500">{r.mean}%</div>
              <div className="text-right tabular-nums text-slate-500">{r.max}%</div>
            </div>
          ))}
          <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] border-t-2 border-slate-200 bg-pe-light/40 px-6 py-3 text-lg font-bold text-pe-dark">
            <div>All scored targets</div>
            <div className="text-right tabular-nums">32,633</div>
            <div className="text-right tabular-nums text-pe-teal">0.89%</div>
            <div className="text-right tabular-nums">84.64%</div>
            <div className="text-right tabular-nums">162,496%</div>
          </div>
        </div>
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
          <BulletList
            className="mt-8"
            items={[
              "Effective sample size is a primary result, not a footnote.",
              "The raw L0-gated weights are the ones with highest ESS, lowest max weight, as the L0 selects the most informative records.",
              "The refit that restores accuracy gives some of that concentration back, but L0 + refit still beats the matched random support.",
            ]}
          />
        </div>
        <Figure
          src="/figures/f2_usability.png"
          width={2168}
          height={886}
          alt="Effective sample size and largest household weight across the five method arms"
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
      <div className="flex h-full flex-col justify-center">
        <SlideTitle kicker="Future work">From proof of concept to production-scale pruning</SlideTitle>
        <div className="mt-9 grid grid-cols-2 gap-5">
          <ContentCard title="Build really large, then prune" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              Sweep normalized L0 penalties on the three-year support and larger over-built pools, then
              prune back to a publishable artifact.
            </p>
          </ContentCard>
          <ContentCard title="Contrast penalty designs" accent="teal">
            <p className="text-lg leading-snug text-slate-600">
              Compare the L0 penalty against an{" "}
              <span className="font-bold text-pe-dark">L1 penalty</span> as an alternative
              sparsity-inducing selector, and sweep the{" "}
              <span className="font-bold text-pe-dark">
                &lambda;<sub>L2</sub> penalty and weight cap against &lambda;<sub>L0</sub>
              </span>{" "}
              to trace the accuracy&ndash;concentration trade-off.
            </p>
          </ContentCard>
          <ContentCard title="Complete the comparator set" accent="amber">
            <p className="text-lg leading-snug text-slate-600">
              Add PPS survey-weight sampling, categorical-margin raking panels, and longer dense
              convergence checks under the same Populace loss.
            </p>
          </ContentCard>
          <ContentCard title="Targeted robustness" accent="slate">
            <p className="text-lg leading-snug text-slate-600">
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
      subtitle="The full-surface probe says: choosing a sparse support with L0 and then refitting reaches lower completed-run loss than dense no-L0 and matched random baselines, at the production scale."
    />
  );
}

export function QuestionsSlide() {
  return <EndSlide />;
}
