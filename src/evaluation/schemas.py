from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.evaluation.config import ExperimentDefinition


MetricStatus = Literal["computed", "user_confirmed", "pending_human_review", "not_applicable"]
Decision = Literal["pass", "refuse"]
ErrorStage = Literal[
    "entity_linking",
    "routing",
    "graph_retrieval",
    "text_retrieval",
    "fusion",
    "generation",
    "verification",
    "other",
]


class MetricValue(BaseModel):
    value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    status: MetricStatus
    note: str = ""

    @model_validator(mode="after")
    def validate_value_status(self) -> "MetricValue":
        if self.status in {"computed", "user_confirmed"} and self.value is None:
            raise ValueError("computed or user-confirmed metrics must include value")
        if self.status in {"pending_human_review", "not_applicable"} and self.value is not None:
            raise ValueError("pending or not-applicable metrics cannot include value")
        if self.denominator is not None and self.denominator <= 0:
            raise ValueError("metric denominator must be positive")
        return self


class LatencyBreakdown(BaseModel):
    route_ms: float = Field(default=0.0, ge=0.0)
    retrieval_ms: float = Field(default=0.0, ge=0.0)
    generation_ms: float = Field(default=0.0, ge=0.0)
    verification_ms: float = Field(default=0.0, ge=0.0)
    total_ms: float = Field(default=0.0, ge=0.0)


class HumanAssessment(BaseModel):
    correctness_score: int | None = Field(default=None, ge=0, le=2)
    faithfulness_score: int | None = Field(default=None, ge=0, le=2)
    hallucination: bool | None = None
    over_refusal: bool | None = None
    reviewer: str | None = None
    notes: str = ""


class QuestionRunResult(BaseModel):
    question_id: str
    question: str
    category: str
    expected_decision: Decision
    actual_decision: Decision
    decision_correct: bool
    answer: str = ""
    intent: str = ""
    retrieval_mode: Literal["none", "vector", "graph", "hybrid"]
    retry_count: int = Field(default=0, ge=0)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_validity: float = Field(default=0.0, ge=0.0, le=1.0)
    path_validity: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_present: bool = False
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    gold_chunk_ids: list[str] = Field(default_factory=list)
    graph_path_ids: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    latency: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    human_assessment: HumanAssessment | None = None
    error_stage: ErrorStage | None = None


class ExperimentMetrics(BaseModel):
    decision_accuracy: MetricValue
    answer_correctness: MetricValue
    evidence_faithfulness: MetricValue
    retrieval_recall_at_5: MetricValue
    path_validity: MetricValue
    refusal_accuracy: MetricValue
    hallucination_rate: MetricValue
    over_refusal_rate: MetricValue
    citation_rate: MetricValue
    latency_ms: MetricValue


class ExperimentRunReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    experiment_id: str
    experiment_config: ExperimentDefinition
    dataset_split: Literal["dev", "pilot", "final", "extension"]
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine: str
    started_at: str
    completed_at: str
    question_count: int = Field(ge=0)
    metrics: ExperimentMetrics
    results: list[QuestionRunResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_count(self) -> "ExperimentRunReport":
        if len(self.results) != self.question_count:
            raise ValueError(
                f"question_count ({self.question_count}) must match results ({len(self.results)})"
            )
        return self
