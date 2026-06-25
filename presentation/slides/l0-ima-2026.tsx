"use client";

import BulletList from "@/components/content/BulletList";
import ContentCard from "@/components/content/ContentCard";
import EquationCard from "@/components/content/EquationCard";
import FigurePlaceholder from "@/components/content/FigurePlaceholder";
import PipelineDiagram from "@/components/content/PipelineDiagram";
import StatNumber from "@/components/content/StatNumber";
import Slide from "@/components/core/Slide";
import CoverSlide from "@/components/layout/CoverSlide";
import EndSlide from "@/components/layout/EndSlide";
import SectionSlide from "@/components/layout/SectionSlide";
import SlideTitle from "@/components/layout/SlideTitle";

const speakers = [
  {
    name: "Maria Juaristi",
    title: "PolicyEngine",
  },
];

export function TitleSlide() {
  return (
    <CoverSlide
      title="L0 regularization for subnational microsimulation calibration"
      subtitle="Selecting which microdata records survive when a rich candidate population has to become a deployable dataset."
      event="IMA 2026, Brussels"
      date="2026-07-01"
      speakers={speakers}
    />
  );
}

export function SubnationalProblemSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1.05fr_0.95fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Motivation">Subnational microsimulation raises the calibration burden</SlideTitle>
          <p className="mt-8 max-w-4xl text-2xl leading-snug text-slate-600">
            The data stack is moving from national-only calibration toward target systems that
            must hold together across national, state, and district-level geographies.
          </p>
          <p className="mt-6 max-w-4xl text-xl leading-snug text-slate-500">
            Arch can materialize thousands of source-backed aggregate facts. Populace then decides
            which facts are active for a build, which are validation-only, and which cannot yet be
            estimated by the current support universe.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <StatNumber compact value="22,456" label="candidate facts" sublabel="Arch source-package rows x measures" />
          <StatNumber compact value="9,177" label="district facts" sublabel="ACS S0101 and S2201 congressional district packages" />
          <StatNumber compact value="4,582" label="active US targets" sublabel="current Populace production release" />
          <StatNumber compact value="75,112" label="households" sublabel="US 2024 compact file used here" />
        </div>
      </div>
    </Slide>
  );
}

export function PopulaceValueSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Populace">A population is a weighted sampling frame, not a flat table</SlideTitle>
          <BulletList
            className="mt-10"
            items={[
              "Entity tables preserve household, person, tax-unit, and family structure.",
              "Typed weights make each stage explicit: design, importance, then calibrated.",
              "Strata carry provenance, so generation owns support while calibration owns representation.",
            ]}
          />
        </div>
        <FigurePlaceholder
          title="Populace visual placeholder"
          subtitle="Frame, typed weights, entity links, source strata"
        />
      </div>
    </Slide>
  );
}

export function PipelineSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="Data pipeline">Populace carries one weighted frame through the build</SlideTitle>
        <div className="mt-8">
          <PipelineDiagram />
        </div>
      </div>
    </Slide>
  );
}

export function BuildBigThenPruneSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Operational problem">Build big, then prune</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            The long-run Populace design is to generate a richer support pool first, then use
            calibration to decide which records are worth carrying into the published artifact.
          </p>
        </div>
        <div className="space-y-5">
          <ContentCard title="Build big" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Pool survey records, attach country-specific imputations, add geography, and
              oversample rare support where the population needs detail.
            </p>
          </ContentCard>
          <ContentCard title="The pressure point" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Calibration memory scales with targets times records; the production file still has
              to be cheap to store, load, and simulate.
            </p>
          </ContentCard>
          <ContentCard title="Prune with evidence" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Keep records because they help reproduce source-backed targets, not because they won
              an arbitrary random draw.
            </p>
          </ContentCard>
        </div>
      </div>
    </Slide>
  );
}

export function SamplingQuestionSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Paper question">Which records should survive?</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Given a candidate universe and a target system, the reduction problem becomes a sampling
            problem with fitted weights and geographic representativeness constraints.
          </p>
        </div>
        <ContentCard accent="teal">
          <div className="space-y-7 text-2xl leading-snug text-slate-700">
            <div>
              <span className="font-bold text-pe-dark">Input:</span> candidate records, initial weights, calibration targets
            </div>
            <div>
              <span className="font-bold text-pe-dark">Constraint:</span> retain a deployable number of records
            </div>
            <div>
              <span className="font-bold text-pe-dark">Goal:</span> preserve target fit for each represented geography
            </div>
            <div>
              <span className="font-bold text-pe-dark">Output:</span> selected records and calibrated positive weights
            </div>
          </div>
        </ContentCard>
      </div>
    </Slide>
  );
}

export function L0SolutionSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1fr_1fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Our approach">Add hard-concrete gates to a gradient calibrator</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            We adapt Louizos, Welling, and Kingma&apos;s L0 regularization idea:
            each record receives a stochastic gate whose expected open probability is penalized.
          </p>
          <p className="mt-6 text-xl leading-snug text-slate-500">
            During training the gate is differentiable, so Adam can optimize weights and selection
            together. At publication time, gates become a deterministic retained-record set.
          </p>
        </div>
        <FigurePlaceholder
          title="L0 approach visual placeholder"
          subtitle="Gates, weights, and retained records"
        />
      </div>
    </Slide>
  );
}

export function BaselinesSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="Comparison">Three ways to reduce the same candidate universe</SlideTitle>
        <div className="mt-10 grid grid-cols-3 gap-6">
          <ContentCard title="Informed L0" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Select records and fit weights jointly, with gates trained against the same target loss.
            </p>
          </ContentCard>
          <ContentCard title="Random then reweight" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Draw a random subset first, then fit weights on that fixed subset.
            </p>
          </ContentCard>
          <ContentCard title="Survey-weight sampling" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Calibrate the full universe, then draw records proportional to fitted survey weights.
            </p>
          </ContentCard>
        </div>
        <p className="mt-10 max-w-5xl text-2xl leading-snug text-slate-600">
          The comparison holds the targets and candidate universe fixed, so the difference is where
          selection enters the workflow.
        </p>
      </div>
    </Slide>
  );
}

export function L0MathSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="L0 objective">Target fit and record selection are optimized together</SlideTitle>
        <div className="mt-9 grid grid-cols-2 gap-8">
          <EquationCard
            title="Training objective"
            equation="L_target(z * w) + lambda_L0 * sum_i P(z_i > 0) + lambda_L2 * ||w / w0||^2"
            note="The hard-concrete relaxation makes the gate probability differentiable, following Louizos et al."
          />
          <EquationCard
            title="Published dataset"
            equation="keep record i when z_i is open; recalibrate positive weights on the retained support"
            note="The final artifact is an ordinary sparse microdataset with calibrated positive weights."
          />
        </div>
        <p className="mt-9 max-w-6xl text-2xl leading-snug text-slate-600">
          The technical claim is not that L0 changes the target definition. It changes the sampling
          decision: selection is trained against the same target system the final weights must match.
        </p>
      </div>
    </Slide>
  );
}

export function GateIntuitionSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Method intuition">A gate decides whether a record counts</SlideTitle>
          <BulletList
            className="mt-10"
            items={[
              "Each candidate record has a continuous gate during training.",
              "The L0 penalty prices open gates, so record count enters the objective.",
              "The final dataset evaluates gates deterministically and keeps the open records.",
            ]}
          />
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-9 shadow-sm">
          <div className="grid grid-cols-5 gap-4">
            {[1, 0, 1, 1, 0].map((open, index) => (
              <div key={`${open}-${index}`} className="text-center">
                <div
                  className={[
                    "mx-auto flex h-24 w-24 items-center justify-center rounded-full border-4 text-3xl font-extrabold",
                    open
                      ? "border-pe-teal bg-pe-light text-pe-dark"
                      : "border-slate-300 bg-slate-100 text-slate-400",
                  ].join(" ")}
                >
                  {open ? "1" : "0"}
                </div>
                <div className="mt-3 text-sm font-semibold text-slate-500">record {index + 1}</div>
              </div>
            ))}
          </div>
          <div className="mt-10 rounded-md bg-slate-50 p-5 text-center text-xl text-slate-600">
            Selection is target-informed because gates and weights optimize the same calibration loss.
          </div>
        </div>
      </div>
    </Slide>
  );
}

export function CalibrationObjectiveSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="Evaluation objective">Every comparison uses the same calibration loss</SlideTitle>
        <div className="mt-9 grid grid-cols-2 gap-8">
          <EquationCard
            title="Fit metric"
            equation="capped weighted MAPE(t_hat, t)"
            note="Relative error keeps heterogeneous count and amount targets on a common scale; the cap limits the influence of near-zero or hard-to-fit targets."
          />
          <EquationCard
            title="Comparison rule"
            equation="same targets + same loss + same weight bounds"
            note="The experiment tests sampling and selection. The calibration objective is held fixed across informed L0, random reweighting, and survey-weight sampling."
          />
        </div>
      </div>
    </Slide>
  );
}

export function ExperimentDesignSlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="Experiment design">One frozen input, three sampling methods, held-out target families</SlideTitle>
        <div className="mt-10 grid grid-cols-4 gap-5">
          <StatNumber value="75,112" label="households" sublabel="Populace US 2024 candidate file" />
          <StatNumber value="3" label="seeds" sublabel="expanded sweep design" />
          <StatNumber value="5" label="budgets" sublabel="from aggressive compression upward" />
          <StatNumber value="206" label="held out" sublabel="family-level out-of-sample targets" />
        </div>
        <ContentCard className="mt-8" accent="teal">
          <p className="text-2xl leading-snug text-slate-700">
            The fixed holdout keeps Medicaid, SNAP, state income tax, and validation-only CBO
            targets out of every method&apos;s fit, then scores them only after calibration.
          </p>
        </ContentCard>
      </div>
    </Slide>
  );
}

export function MainFrontierSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.9fr_1.1fr] gap-10">
        <div className="pt-6">
          <SlideTitle kicker="Main result">Frontier result will carry the central comparison</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            The final slide should explain where informed selection improves target fit under
            compression, where baselines catch up, and where the survey-weight baseline behaves
            differently.
          </p>
        </div>
        <FigurePlaceholder
          title="Out-of-sample error vs retained records"
          subtitle="Informed L0, random plus reweight, and survey-weight sampling"
        />
      </div>
    </Slide>
  );
}

export function GeneralizationSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[1.1fr_0.9fr] gap-10">
        <FigurePlaceholder
          kind="bars"
          title="Held-out-family generalization"
          subtitle="Gap between fit-target and held-out-target accuracy"
        />
        <div className="pt-6">
          <SlideTitle kicker="Generalization">The holdout is by family, not random target cells</SlideTitle>
          <BulletList
            className="mt-10"
            items={[
              "Random target splits leak through nested totals.",
              "Whole-family holdout tests whether selected records reproduce unseen domains.",
              "Rotation folds become robustness evidence rather than a single headline score.",
            ]}
          />
        </div>
      </div>
    </Slide>
  );
}

export function UsabilitySlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.92fr_1.08fr] gap-10">
        <div className="pt-6">
          <SlideTitle kicker="Usability">Accuracy is not enough if the weights concentrate</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            The talk should report effective sample size and largest fitted weight alongside error.
            This keeps the operational cost of calibration visible.
          </p>
        </div>
        <FigurePlaceholder
          kind="tradeoff"
          title="Effective sample size and max weight"
          subtitle="Representativeness diagnostics across methods and budgets"
        />
      </div>
    </Slide>
  );
}

export function OperabilitySlide() {
  return (
    <Slide>
      <div className="flex h-full flex-col">
        <SlideTitle kicker="Controls">The concentration controls turn a hidden cost into an explicit tradeoff</SlideTitle>
        <div className="mt-10 grid grid-cols-3 gap-6">
          <ContentCard title="lambda_L0" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Sets the retained-record budget by pricing open gates.
            </p>
          </ContentCard>
          <ContentCard title="lambda_L2" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              Softly discourages high fitted-weight ratios across the retained records.
            </p>
          </ContentCard>
          <ContentCard title="max_weight_ratio" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Hard cap on how much any one record can inflate relative to its starting weight.
            </p>
          </ContentCard>
        </div>
        <p className="mt-10 max-w-5xl text-2xl leading-snug text-slate-600">
          The final presentation should show what each control buys in effective sample size and what
          it costs in out-of-sample accuracy.
        </p>
      </div>
    </Slide>
  );
}

export function FutureWorkSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.9fr_1.1fr] items-center gap-12">
        <SlideTitle kicker="Future work">Move from proof of concept to production-scale pruning</SlideTitle>
        <div className="space-y-5">
          <ContentCard title="Congressional-district production builds" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              Populace production work already includes congressional-district calibrated datasets;
              the L0 evaluation should score that full geographic setting directly.
            </p>
          </ContentCard>
          <ContentCard title="Build really large, then prune" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              The current experiments use a compact candidate file. The next test is a deliberately
              over-built pool, then L0 pruning back to a publishable artifact.
            </p>
          </ContentCard>
          <ContentCard title="Broader target surfaces" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              District-level age, SNAP, and SOI facts should be part of the held-out target design,
              not just motivation for the method.
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
      section="Takeaway"
      title="Target-informed pruning is a calibration method and a sampling method"
      subtitle="The method selects records because they help reproduce the target system, while keeping record count and weight concentration as tunable, reportable outputs."
    />
  );
}

export function QuestionsSlide() {
  return <EndSlide />;
}
