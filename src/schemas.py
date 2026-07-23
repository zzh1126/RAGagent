from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ReviewStatus = Literal["pending", "approved", "rejected"]
RetrievalMode = Literal["vector", "graph", "hybrid"]
VerifyDecision = Literal["pass", "partial_pass", "retry", "refuse"]
VerifierDecisionPolicy = Literal["strict", "partial_pass"]
VerifierPolicy = Literal["strict", "partial_pass", "disabled"]
ClaimStatus = Literal["supported", "unsupported"]
GeneratorBackend = Literal["offline_rule", "ollama"]
CacheStatus = Literal["disabled", "hit", "miss"]


class TextEvidence(BaseModel):
    evidence_id: str
    chunk_id: str
    source_id: str
    page_title: str
    heading_path: list[str] = Field(default_factory=list)
    url: str
    display_text: str = ""
    score: float = 0.0


class GraphTriple(BaseModel):
    source_id: str
    source_name: str
    relation: str
    target_id: str
    target_name: str
    relation_id: str = ""
    evidence_source_id: str | None = None
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    review_status: str = ""


class GraphPath(BaseModel):
    path_id: str
    triples: list[GraphTriple]
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class LinkedEntity(BaseModel):
    entity_id: str
    name_en: str
    name_zh: str
    type: str
    matched_text: str
    score: float = 1.0


class RetrievalResult(BaseModel):
    intent: str
    mode: RetrievalMode
    entities: list[LinkedEntity] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    text_evidence: list[TextEvidence] = Field(default_factory=list)


class EvidencePackingTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packer_version: Literal["intent_aware_v2"] = "intent_aware_v2"
    intent: str
    selected_evidence_ids: list[str] = Field(default_factory=list)
    selected_chunk_ids: list[str] = Field(default_factory=list)
    selected_graph_path_ids: list[str] = Field(default_factory=list)
    reason_codes_by_evidence: dict[str, list[str]] = Field(default_factory=dict)
    entity_coverage: dict[str, int] = Field(default_factory=dict)
    coverage_gaps: list[str] = Field(default_factory=list)
    truncated_evidence_ids: list[str] = Field(default_factory=list)
    dropped_evidence_ids: list[str] = Field(default_factory=list)
    input_evidence_count: int = Field(default=0, ge=0)
    deduplicated_evidence_count: int = Field(default=0, ge=0)
    input_character_count: int = Field(default=0, ge=0)
    packed_character_count: int = Field(default=0, ge=0)
    selection_target: int = Field(default=1, ge=1)
    max_text_evidence: int = Field(ge=1)
    max_graph_paths: int = Field(ge=0)
    max_context_chars: int = Field(ge=1)
    evidence_packing_latency_ms: float = Field(default=0.0, ge=0.0)


class EvidencePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: str
    graph_paths: list[GraphPath] = Field(default_factory=list)
    text_evidence: list[TextEvidence] = Field(default_factory=list)
    trace: EvidencePackingTrace


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=12, max_length=500)


class AnswerClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    graph_path_ids: list[str] = Field(default_factory=list)
    relation_id: str = ""
    supporting_quotes: list[EvidenceQuote] = Field(default_factory=list)


class AnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    claims: list[AnswerClaim] = Field(default_factory=list)
    graph_paths: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generator_backend: GeneratorBackend = "offline_rule"
    fallback_used: bool = False
    fallback_reason: str | None = None
    generation_attempts: int = Field(default=0, ge=0)
    generation_latency_ms: float = Field(default=0.0, ge=0.0)
    evidence_packing: EvidencePackingTrace | None = None


class ClaimResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    claim_index: int = Field(ge=1)
    claim: str = Field(min_length=1)
    status: ClaimStatus
    supported: bool = False
    retained: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    valid_evidence_ids: list[str] = Field(default_factory=list)
    graph_path_ids: list[str] = Field(default_factory=list)
    valid_graph_path_ids: list[str] = Field(default_factory=list)
    relation_id: str = ""
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "ClaimResult":
        if self.supported != (self.status == "supported"):
            raise ValueError("ClaimResult supported must match status")
        if self.retained and not self.supported:
            raise ValueError("unsupported Claim cannot be retained")
        return self


class VerifyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: VerifyDecision
    decision_policy: VerifierPolicy = "strict"
    evidence_score: float
    claim_coverage: float = 0.0
    citation_validity: float = 0.0
    path_validity: float = 0.0
    retrieval_sufficiency: float = 0.0
    unsupported_claims: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    claim_results: list[ClaimResult] = Field(default_factory=list)
    generated_claim_count: int = Field(default=0, ge=0)
    supported_claim_count: int = Field(default=0, ge=0)
    removed_claim_count: int = Field(default=0, ge=0)
    supported_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    retained_claim_ids: list[str] = Field(default_factory=list)
    removed_claim_ids: list[str] = Field(default_factory=list)
    retained_claim_indexes: list[int] = Field(default_factory=list)
    partial_pass_reason: str | None = None
    verification_latency_ms: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_claim_summary(self) -> "VerifyResult":
        if not self.claim_results:
            return self
        if len(self.claim_results) != self.generated_claim_count:
            raise ValueError("generated_claim_count must match claim_results")
        supported_ids = [
            result.claim_id for result in self.claim_results if result.supported
        ]
        unsupported_ids = [
            result.claim_id for result in self.claim_results if not result.supported
        ]
        retained_ids = [
            result.claim_id for result in self.claim_results if result.retained
        ]
        removed_ids = [
            result.claim_id for result in self.claim_results if not result.retained
        ]
        if self.supported_claim_count != len(supported_ids):
            raise ValueError("supported_claim_count does not match claim_results")
        if self.supported_claim_ids != supported_ids:
            raise ValueError("supported_claim_ids does not match claim_results")
        if self.unsupported_claim_ids != unsupported_ids:
            raise ValueError("unsupported_claim_ids does not match claim_results")
        if self.retained_claim_ids != retained_ids:
            raise ValueError("retained_claim_ids does not match claim_results")
        if self.removed_claim_ids != removed_ids:
            raise ValueError("removed_claim_ids does not match claim_results")
        if self.removed_claim_count != len(removed_ids):
            raise ValueError("removed_claim_count does not match claim_results")
        expected_indexes = [
            result.claim_index for result in self.claim_results if result.retained
        ]
        if self.retained_claim_indexes != expected_indexes:
            raise ValueError("retained_claim_indexes does not match claim_results")
        return self


class GenerationCall(BaseModel):
    requested_backend: GeneratorBackend
    actual_backend: GeneratorBackend
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    attempts: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    structured_output_success: bool = False


class RouteTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    mode: RetrievalMode
    reason: str
    latency_ms: float = Field(default=0.0, ge=0.0)


class RetrievalCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    is_retry: bool = False
    intent: str
    mode: RetrievalMode
    top_k: int = Field(ge=1)
    entity_count: int = Field(default=0, ge=0)
    graph_path_count: int = Field(default=0, ge=0)
    text_evidence_count: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)


class VerificationCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    is_retry: bool = False
    decision: VerifyDecision
    decision_policy: VerifierPolicy
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_claim_count: int = Field(default=0, ge=0)
    supported_claim_count: int = Field(default=0, ge=0)
    removed_claim_count: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)


class WorkflowLatencyTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing_latency_ms: float = Field(default=0.0, ge=0.0)
    retrieval_latency_ms: float = Field(default=0.0, ge=0.0)
    evidence_packing_latency_ms: float = Field(default=0.0, ge=0.0)
    llm_generation_latency_ms: float = Field(default=0.0, ge=0.0)
    verification_latency_ms: float = Field(default=0.0, ge=0.0)
    retry_latency_ms: float = Field(default=0.0, ge=0.0)
    end_to_end_latency_ms: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_end_to_end_latency(self) -> "WorkflowLatencyTrace":
        component_values = (
            self.routing_latency_ms,
            self.retrieval_latency_ms,
            self.evidence_packing_latency_ms,
            self.llm_generation_latency_ms,
            self.verification_latency_ms,
            self.retry_latency_ms,
        )
        if component_values and max(component_values) > self.end_to_end_latency_ms + 0.001:
            raise ValueError("end_to_end_latency_ms must cover every individual stage")
        return self


class FinalResponse(BaseModel):
    query: str
    answer: str
    answer_payload: AnswerPayload
    retrieval: RetrievalResult
    verification: VerifyResult
    route_trace: RouteTrace | None = None
    retrieval_trace: list[RetrievalCall] = Field(default_factory=list)
    generation_trace: list[GenerationCall] = Field(default_factory=list)
    evidence_packing_trace: list[EvidencePackingTrace] = Field(default_factory=list)
    verification_trace: list[VerificationCall] = Field(default_factory=list)
    latency_trace: WorkflowLatencyTrace = Field(default_factory=WorkflowLatencyTrace)
    cache_status: CacheStatus = "disabled"
    latency_ms: int = 0
    retry_count: int = 0
