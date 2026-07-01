import { SlideshowConfig } from "@/lib/types";
import {
  BaselinesSlide,
  BuildBigThenPruneSlide,
  CalibrationObjectiveSlide,
  ExperimentDesignSlide,
  FutureWorkSlide,
  GeneralizationSlide,
  GeographyAccuracySlide,
  L0MathSlide,
  LedgerSlide,
  LouizosFoundationSlide,
  OperabilitySlide,
  PipelineSlide,
  PolicyGoalSlide,
  PopulaceValueSlide,
  QuestionsSlide,
  RepresentativenessSlide,
  ResultsArcBaselinesSlide,
  ResultsArcL0Slide,
  ResultsArcRefitSlide,
  ResultsArcScaledSlide,
  RoadmapSlide,
  SamplingQuestionSlide,
  TakeawaySlide,
  TitleSlide,
  TranslationSlide,
  WeightLayoutBothSlide,
  WeightLayoutWideSlide,
} from "@/slides/l0-ima-2026";

export const l0Ima2026Config: SlideshowConfig = {
  id: "l0-ima-2026",
  title: "L0 regularization for subnational microsimulation calibration",
  description: "Draft PolicyEngine presentation for IMA 2026.",
  date: "2026-07-01",
  location: "IMA 2026, Brussels",
  footerText: "PolicyEngine - IMA 2026 - L0 calibration",
  speakers: [
    {
      name: "Maria Juaristi",
      title: "PolicyEngine",
    },
  ],
  slides: [
    // 0 · Open
    TitleSlide,
    RoadmapSlide,
    // 1 · Motivation
    PolicyGoalSlide,
    WeightLayoutWideSlide,
    WeightLayoutBothSlide,
    BuildBigThenPruneSlide,
    // 2 · Data engine
    LedgerSlide,
    PopulaceValueSlide,
    PipelineSlide,
    // 3 · Imputation
    RepresentativenessSlide,
    // 4 · Reduction problem + Louizos + method
    SamplingQuestionSlide,
    BaselinesSlide,
    LouizosFoundationSlide,
    TranslationSlide,
    L0MathSlide,
    // 5 · Proof of concept
    ExperimentDesignSlide,
    CalibrationObjectiveSlide,
    // Main result: progressive loss-bar arc (one beat per slide)
    ResultsArcBaselinesSlide,
    ResultsArcScaledSlide,
    ResultsArcL0Slide,
    ResultsArcRefitSlide,
    GeographyAccuracySlide,
    GeneralizationSlide,
    OperabilitySlide,
    // 6 · Close
    FutureWorkSlide,
    TakeawaySlide,
    QuestionsSlide,
  ],
};
