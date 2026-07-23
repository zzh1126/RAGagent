from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewStatus = Literal["pending", "approved", "rejected"]
RetrievalMode = Literal["vector", "graph", "hybrid"]
VerifyDecision = Literal["pass", "retry", "refuse"]
GeneratorBackend = Literal["offline_rule", "ollama"]


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
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    supported: bool = False


class VerifyResult(BaseModel):
    decision: VerifyDecision
    evidence_score: float
    claim_coverage: float = 0.0
    citation_validity: float = 0.0
    path_validity: float = 0.0
    retrieval_sufficiency: float = 0.0
    unsupported_claims: list[str] = Field(default_factory=list)


class GenerationCall(BaseModel):
    requested_backend: GeneratorBackend
    actual_backend: GeneratorBackend
    fallback_used: bool = False
    fallback_reason: str | None = None
    attempts: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    structured_output_success: bool = False


class FinalResponse(BaseModel):
    query: str
    answer: str
    answer_payload: AnswerPayload
    retrieval: RetrievalResult
    verification: VerifyResult
    generation_trace: list[GenerationCall] = Field(default_factory=list)
    evidence_packing_trace: list[EvidencePackingTrace] = Field(default_factory=list)
    latency_ms: int = 0
    retry_count: int = 0
