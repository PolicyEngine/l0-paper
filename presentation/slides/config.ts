import { SlideshowConfig } from "@/lib/types";
import {
  ArchSlide,
  BaselinesSlide,
  BuildBigThenPruneSlide,
  CalibrationObjectiveSlide,
  DataEngineSectionSlide,
  ExperimentDesignSlide,
  FutureWorkSlide,
  GeneralizationSlide,
  L0MathSlide,
  LouizosFoundationSlide,
  MainFrontierSlide,
  NestedTargetsSlide,
  OperabilitySlide,
  PipelineSlide,
  PolicyGoalSlide,
  PopulaceValueSlide,
  ProductionTieSlide,
  ProofSectionSlide,
  QuestionsSlide,
  ReductionSectionSlide,
  RepresentativenessSlide,
  RoadmapSlide,
  SamplingQuestionSlide,
  ScaleSlide,
  TakeawaySlide,
  TitleSlide,
  TranslationSlide,
  VariabilitySlide,
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
    NestedTargetsSlide,
    BuildBigThenPruneSlide,
    // 2 · Data engine
    DataEngineSectionSlide,
    ArchSlide,
    PopulaceValueSlide,
    PipelineSlide,
    // 3 · Imputation mechanics
    RepresentativenessSlide,
    VariabilitySlide,
    ScaleSlide,
    // 4 · Reduction problem + Louizos + method
    ReductionSectionSlide,
    SamplingQuestionSlide,
    BaselinesSlide,
    LouizosFoundationSlide,
    TranslationSlide,
    L0MathSlide,
    ProductionTieSlide,
    // 5 · Proof of concept
    ProofSectionSlide,
    ExperimentDesignSlide,
    CalibrationObjectiveSlide,
    MainFrontierSlide,
    GeneralizationSlide,
    OperabilitySlide,
    // 6 · Close
    FutureWorkSlide,
    TakeawaySlide,
    QuestionsSlide,
  ],
};
