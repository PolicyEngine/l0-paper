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
            National surveys support national estimates. State, district, and local analysis need the
            same households to aggregate correctly across several geographic levels.
          </p>
        </div>
        <div className="space-y-5">
          <StatNumber value="many" label="target families" sublabel="tax, transfer, health, and income aggregates" />
          <StatNumber value="nested" label="geographies" sublabel="national, state, and future local targets" />
          <StatNumber value="fixed" label="record budget" sublabel="the final dataset still has to run quickly" />
        </div>
      </div>
    </Slide>
  );
}

export function CandidateUniverseSlide() {
  return (
    <SectionSlide
      section="The operational problem"
      title="Fidelity grows the candidate universe; deployment needs it smaller"
      subtitle="The pipeline can add information through imputation and geography, but the final file must still be cheap to store, calibrate, and simulate."
    />
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

export function SamplingQuestionSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.95fr_1.05fr] items-center gap-12">
        <div>
          <SlideTitle kicker="Paper question">Which records should survive?</SlideTitle>
          <p className="mt-8 text-2xl leading-snug text-slate-600">
            Given a candidate universe and a target system, the reduction problem becomes a sampling
            problem with fitted weights.
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
              <span className="font-bold text-pe-dark">Output:</span> selected records and calibrated positive weights
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
        <SlideTitle kicker="Objective">The loss separates fit, size, and concentration</SlideTitle>
        <div className="mt-9 grid grid-cols-2 gap-8">
          <EquationCard
            title="Shared calibration loss"
            equation="capped weighted MAPE(t_hat, t)"
            note="The cap keeps one hard-to-fit target from dominating the gradient; target weights are uniform in the current draft runs."
          />
          <EquationCard
            title="Informed selection loss"
            equation="calibration + lambda_L0 * open gates + lambda_L2 * weight ratio squared"
            note="lambda_L0 controls retained count. lambda_L2 and max_weight_ratio expose the weight-concentration tradeoff."
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
            targets out of every method's fit, then scores them only after calibration.
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

export function CaveatsSlide() {
  return (
    <Slide>
      <div className="grid h-full grid-cols-[0.9fr_1.1fr] items-center gap-12">
        <SlideTitle kicker="Caveats">The claims need to stay bounded by the current target surface</SlideTitle>
        <div className="space-y-5">
          <ContentCard title="Current geography" accent="slate">
            <p className="text-xl leading-snug text-slate-600">
              The paper motivates subnational production use, but the scored target surface is national
              and state in the current proof of concept.
            </p>
          </ContentCard>
          <ContentCard title="Metric tail" accent="amber">
            <p className="text-xl leading-snug text-slate-600">
              Near-zero-denominator targets can inflate mean relative error, so median error and named
              sensitivity checks matter.
            </p>
          </ContentCard>
          <ContentCard title="Weight concentration" accent="teal">
            <p className="text-xl leading-snug text-slate-600">
              High concentration may be acceptable for aggregate calibration but is still an operational
              cost to report.
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
