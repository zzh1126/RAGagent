from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ReviewStatus = Literal["pending", "approved", "rejected"]
RetrievalMode = Literal["vector", "graph", "hybrid"]
VerifyDecision = Literal["pass", "retry", "refuse"]


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


class AnswerPayload(BaseModel):
    answer: str
    claims: list[dict] = Field(default_factory=list)
    graph_paths: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    confidence: float = 0.0


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


class FinalResponse(BaseModel):
    query: str
    answer: str
    retrieval: RetrievalResult
    verification: VerifyResult
    latency_ms: int = 0
    retry_count: int = 0
