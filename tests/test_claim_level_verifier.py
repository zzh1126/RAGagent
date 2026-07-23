from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agent.workflow import QAWorkflow
from src.schemas import (
    AnswerClaim,
    AnswerPayload,
    ClaimResult,
    EvidenceQuote,
    GraphPath,
    GraphTriple,
    LinkedEntity,
    RetrievalResult,
    TextEvidence,
    VerifyResult,
)
from src.verification.evidence_verifier import EvidenceVerifier


class StubGraphRepository:
    def validate_path(self, triples: list[dict]) -> bool:
        return bool(triples)

    def get_neighbors(self, entity_id: str) -> list[dict]:
        return []


class StaticRetriever:
    def __init__(self, retrieval: RetrievalResult):
        self.retrieval = retrieval
        self.calls = 0

    def retrieve(self, query, intent, mode, top_k=None):
        self.calls += 1
        return self.retrieval.model_copy(deep=True)


class StaticGenerator:
    def __init__(self, payload: AnswerPayload):
        self.payload = payload
        self.calls = 0

    def generate(self, query: str, retrieval: RetrievalResult) -> AnswerPayload:
        self.calls += 1
        return self.payload.model_copy(deep=True)

    @staticmethod
    def refusal_answer() -> str:
        return "受控拒答"


def random_forest_retrieval() -> RetrievalResult:
    return RetrievalResult(
        intent="explanation",
        mode="hybrid",
        entities=[
            LinkedEntity(
                entity_id="ALG_RF",
                name_en="Random Forest",
                name_zh="随机森林",
                type="Algorithm",
                matched_text="随机森林",
            )
        ],
        graph_paths=[
            GraphPath(
                path_id="P1",
                triples=[
                    GraphTriple(
                        source_id="ALG_RF",
                        source_name="随机森林",
                        relation="BELONGS_TO",
                        target_id="FAM_ENSEMBLE",
                        target_name="集成学习",
                        relation_id="R1",
                        review_status="approved",
                    )
                ],
            )
        ],
        text_evidence=[
            TextEvidence(
                evidence_id="E1",
                chunk_id="C1",
                source_id="S4",
                page_title="Ensemble methods",
                heading_path=["Random forests"],
                url="https://scikit-learn.org/stable/modules/ensemble.html",
                display_text=(
                    "Random forests are ensemble methods based on randomized decision "
                    "trees. Averaging reduces variance."
                ),
                score=0.91,
            )
        ],
    )


def supported_claim() -> AnswerClaim:
    return AnswerClaim(
        claim="随机森林属于集成学习。",
        evidence_ids=["E1"],
        graph_path_ids=["P1"],
        relation_id="R1",
        supporting_quotes=[
            EvidenceQuote(
                evidence_id="E1",
                quote=(
                    "Random forests are ensemble methods based on randomized decision "
                    "trees."
                ),
            )
        ],
    )


def unsupported_claim() -> AnswerClaim:
    return AnswerClaim(
        claim="随机森林可以直接处理缺失值。",
        evidence_ids=["E999"],
        supporting_quotes=[
            EvidenceQuote(
                evidence_id="E999",
                quote="Invented evidence for a missing-value claim.",
            )
        ],
    )


def payload(*claims: AnswerClaim, unsupported: list[str] | None = None) -> AnswerPayload:
    return AnswerPayload(
        answer="原始模型答案",
        claims=list(claims),
        graph_paths=list(
            dict.fromkeys(
                path_id for claim in claims for path_id in claim.graph_path_ids
            )
        ),
        unsupported_claims=unsupported or [],
        confidence=0.9,
        generator_backend="ollama",
        generation_attempts=1,
    )


def test_all_supported_claims_pass_and_are_retained() -> None:
    result = EvidenceVerifier(max_retries=1).verify(
        "随机森林为什么更稳定",
        payload(supported_claim()),
        random_forest_retrieval(),
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "pass"
    assert result.generated_claim_count == 1
    assert result.supported_claim_count == 1
    assert result.retained_claim_ids == ["C1"]
    assert result.removed_claim_ids == []
    assert result.claim_results[0].status == "supported"
    assert result.claim_results[0].retained is True
    assert result.verification_latency_ms >= 0.0


def test_mixed_claims_partial_pass_retains_only_supported_claims() -> None:
    result = EvidenceVerifier(max_retries=1).verify(
        "随机森林为什么更稳定",
        payload(supported_claim(), unsupported_claim()),
        random_forest_retrieval(),
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "partial_pass"
    assert result.supported_claim_count == 1
    assert result.retained_claim_ids == ["C1"]
    assert result.removed_claim_ids == ["C2"]
    assert result.partial_pass_reason
    assert "unknown_evidence_id" in result.claim_results[1].reason_codes


def test_generator_gap_with_supported_claim_is_partial_pass() -> None:
    result = EvidenceVerifier(max_retries=1).verify(
        "随机森林为什么更稳定",
        payload(
            supported_claim(),
            unsupported=["当前证据没有覆盖问题中的另一个方面"],
        ),
        random_forest_retrieval(),
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "partial_pass"
    assert result.retained_claim_ids == ["C1"]
    assert "generator_reported_gap" in result.reason_codes


def test_zero_supported_claims_retry_once_then_refuse() -> None:
    verifier = EvidenceVerifier(max_retries=1)
    answer = payload(unsupported_claim())
    retrieval = random_forest_retrieval()

    first = verifier.verify(
        "随机森林为什么更稳定",
        answer,
        retrieval,
        graph_repo=StubGraphRepository(),
        retry_count=0,
    )
    second = verifier.verify(
        "随机森林为什么更稳定",
        answer,
        retrieval,
        graph_repo=StubGraphRepository(),
        retry_count=1,
    )

    assert first.decision == "retry"
    assert first.retained_claim_ids == []
    assert second.decision == "refuse"
    assert second.removed_claim_ids == ["C1"]


def test_strict_policy_never_partially_retains_mixed_claims() -> None:
    verifier = EvidenceVerifier(max_retries=1, decision_policy="strict")
    answer = payload(supported_claim(), unsupported_claim())
    retrieval = random_forest_retrieval()

    first = verifier.verify(
        "随机森林为什么更稳定",
        answer,
        retrieval,
        graph_repo=StubGraphRepository(),
        retry_count=0,
    )
    second = verifier.verify(
        "随机森林为什么更稳定",
        answer,
        retrieval,
        graph_repo=StubGraphRepository(),
        retry_count=1,
    )

    assert first.decision == "retry"
    assert first.retained_claim_ids == []
    assert second.decision == "refuse"
    assert second.supported_claim_ids == ["C1"]
    assert second.retained_claim_ids == []


def test_false_premise_invalidates_otherwise_supported_claim_without_retry() -> None:
    retrieval = RetrievalResult(
        intent="relation",
        mode="hybrid",
        entities=[
            LinkedEntity(
                entity_id="ALG_KMEANS",
                name_en="KMeans",
                name_zh="KMeans",
                type="Algorithm",
                matched_text="KMeans",
            )
        ],
        text_evidence=[
            TextEvidence(
                evidence_id="E1",
                chunk_id="C1",
                source_id="S6",
                page_title="Clustering",
                heading_path=["KMeans"],
                url="https://scikit-learn.org/stable/modules/clustering.html",
                display_text="KMeans is a clustering algorithm.",
                score=0.9,
            )
        ],
    )
    answer = payload(
        AnswerClaim(
            claim="KMeans 是一种聚类算法。",
            evidence_ids=["E1"],
            supporting_quotes=[
                EvidenceQuote(
                    evidence_id="E1",
                    quote="KMeans is a clustering algorithm.",
                )
            ],
        )
    )

    result = EvidenceVerifier(max_retries=1).verify(
        "KMeans 是监督分类算法吗",
        answer,
        retrieval,
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "refuse"
    assert "premise_not_supported" in result.reason_codes
    assert result.claim_results[0].supported is False
    assert "premise_not_supported" in result.claim_results[0].reason_codes


def test_partial_workflow_filters_removed_claim_from_answer_and_payload() -> None:
    retrieval = random_forest_retrieval()
    generator = StaticGenerator(payload(supported_claim(), unsupported_claim()))
    retriever = StaticRetriever(retrieval)
    workflow = QAWorkflow(
        retriever=retriever,
        graph_repo=StubGraphRepository(),
        answer_generator=generator,
        verifier=EvidenceVerifier(max_retries=1, decision_policy="partial_pass"),
    )

    response = workflow.invoke("随机森林为什么更稳定")

    assert response.verification.decision == "partial_pass"
    assert response.retry_count == 0
    assert retriever.calls == 1
    assert generator.calls == 1
    assert len(response.answer_payload.claims) == 1
    assert response.answer_payload.claims[0].claim == supported_claim().claim
    assert unsupported_claim().claim not in response.answer
    assert "其余方面缺少足够证据" in response.answer


def test_strict_workflow_retries_mixed_claims_then_refuses() -> None:
    retrieval = random_forest_retrieval()
    generator = StaticGenerator(payload(supported_claim(), unsupported_claim()))
    retriever = StaticRetriever(retrieval)
    workflow = QAWorkflow(
        retriever=retriever,
        graph_repo=StubGraphRepository(),
        answer_generator=generator,
        verifier=EvidenceVerifier(max_retries=1, decision_policy="strict"),
    )

    response = workflow.invoke("随机森林为什么更稳定")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1
    assert retriever.calls == 2
    assert generator.calls == 2
    assert response.answer == "受控拒答"
    assert response.answer_payload.claims == []


def test_claim_result_rejects_inconsistent_status_and_retention() -> None:
    with pytest.raises(ValidationError, match="supported must match status"):
        ClaimResult(
            claim_id="C1",
            claim_index=1,
            claim="事实",
            status="supported",
            supported=False,
        )
    with pytest.raises(ValidationError, match="unsupported Claim cannot be retained"):
        ClaimResult(
            claim_id="C1",
            claim_index=1,
            claim="事实",
            status="unsupported",
            supported=False,
            retained=True,
        )


def test_verify_result_rejects_inconsistent_claim_summary() -> None:
    result = ClaimResult(
        claim_id="C1",
        claim_index=1,
        claim="事实",
        status="supported",
        supported=True,
        retained=True,
    )

    with pytest.raises(ValidationError, match="generated_claim_count"):
        VerifyResult(
            decision="pass",
            decision_policy="partial_pass",
            evidence_score=1.0,
            claim_results=[result],
            generated_claim_count=0,
            supported_claim_count=1,
            supported_claim_ids=["C1"],
            retained_claim_ids=["C1"],
            retained_claim_indexes=[1],
        )
