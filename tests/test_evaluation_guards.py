import pytest

from scripts.run_evaluation import ensure_split_runnable, evaluate_question, summarize
from src.schemas import (
    AnswerClaim,
    AnswerPayload,
    ClaimResult,
    FinalResponse,
    GenerationCall,
    RetrievalResult,
    VerifyResult,
    WorkflowLatencyTrace,
)


def test_final_evaluation_is_not_runnable() -> None:
    with pytest.raises(SystemExit, match="frozen final"):
        ensure_split_runnable("final")


def test_extension_evaluation_is_locked() -> None:
    with pytest.raises(SystemExit, match="locked extension"):
        ensure_split_runnable("extension")


def test_development_split_remains_runnable() -> None:
    assert ensure_split_runnable("dev") is None


def test_evaluation_aggregates_all_generation_calls() -> None:
    response = FinalResponse(
        query="synthetic",
        answer="controlled refusal",
        answer_payload=AnswerPayload(
            answer="controlled refusal",
            generator_backend="offline_rule",
            fallback_used=True,
            fallback_reason="LLMUnavailableError",
        ),
        retrieval=RetrievalResult(intent="general", mode="vector"),
        verification=VerifyResult(decision="refuse", evidence_score=0.0),
        generation_trace=[
            GenerationCall(
                requested_backend="ollama",
                actual_backend="ollama",
                provider="ollama",
                model="qwen3:4b-test",
                attempts=2,
                latency_ms=20.0,
                structured_output_success=True,
            ),
            GenerationCall(
                requested_backend="ollama",
                actual_backend="offline_rule",
                provider="ollama",
                model="qwen3:4b-test",
                fallback_used=True,
                fallback_reason="LLMUnavailableError",
                attempts=1,
                latency_ms=10.0,
                structured_output_success=False,
            ),
        ],
        latency_trace=WorkflowLatencyTrace(
            llm_generation_latency_ms=30.0,
            retry_latency_ms=12.0,
            end_to_end_latency_ms=35.0,
        ),
        latency_ms=35,
        retry_count=1,
    )

    class StubWorkflow:
        def invoke(self, query: str) -> FinalResponse:
            return response

    result = evaluate_question(
        StubWorkflow(),
        {
            "question_id": "SYNTHETIC",
            "category": "no_answer",
            "question": "synthetic",
            "expected_behavior": "refuse",
            "expected_keywords": [],
            "gold_entities": [],
        },
    )

    assert result["generation_call_count"] == 2
    assert result["generation_attempts"] == 3
    assert result["generation_latency_ms"] == 30.0
    assert result["llm_generation_latency_ms"] == 30.0
    assert result["retry_latency_ms"] == 12.0
    assert result["end_to_end_latency_ms"] == 35.0
    assert result["generator_provider"] == "ollama"
    assert result["generator_model"] == "qwen3:4b-test"
    assert result["generator_requested_backend"] == "ollama"
    assert result["cache_status"] == "disabled"
    assert result["generator_fallback_used"] is True
    assert result["structured_output_success"] is False


def test_partial_pass_counts_as_success_for_answerable_development_question() -> None:
    response = FinalResponse(
        query="synthetic",
        answer="partial answer",
        answer_payload=AnswerPayload(answer="partial answer"),
        retrieval=RetrievalResult(intent="general", mode="vector"),
        verification=VerifyResult(
            decision="partial_pass",
            decision_policy="partial_pass",
            evidence_score=0.8,
        ),
    )

    class StubWorkflow:
        def invoke(self, query: str) -> FinalResponse:
            return response

    result = evaluate_question(
        StubWorkflow(),
        {
            "question_id": "SYNTHETIC-PARTIAL",
            "category": "definition",
            "question": "synthetic",
            "expected_behavior": "answer",
            "expected_keywords": [],
            "gold_entities": [],
        },
    )

    assert result["actual_decision"] == "partial_pass"
    assert result["decision_correct"] is True


def test_dev_summary_reports_over_refusal_claims_retries_and_audit_stages() -> None:
    partial_response = FinalResponse(
        query="partial",
        answer="supported",
        answer_payload=AnswerPayload(
            answer="supported",
            claims=[
                AnswerClaim(claim="supported"),
                AnswerClaim(claim="unsupported leaked"),
            ],
            generator_backend="ollama",
            generation_attempts=1,
        ),
        retrieval=RetrievalResult(intent="general", mode="vector"),
        verification=VerifyResult(
            decision="partial_pass",
            decision_policy="partial_pass",
            evidence_score=0.8,
            retrieval_sufficiency=1.0,
            reason_codes=["generator_reported_gap"],
            claim_results=[
                ClaimResult(
                    claim_id="C1",
                    claim_index=1,
                    claim="supported",
                    status="supported",
                    supported=True,
                    retained=True,
                ),
                ClaimResult(
                    claim_id="C2",
                    claim_index=2,
                    claim="unsupported leaked",
                    status="unsupported",
                    reason_codes=["quote_not_supported"],
                ),
            ],
            generated_claim_count=2,
            supported_claim_count=1,
            removed_claim_count=1,
            supported_claim_ids=["C1"],
            unsupported_claim_ids=["C2"],
            retained_claim_ids=["C1"],
            removed_claim_ids=["C2"],
            retained_claim_indexes=[1],
        ),
        generation_trace=[
            GenerationCall(
                requested_backend="ollama",
                actual_backend="ollama",
                provider="ollama",
                model="qwen3:4b-test",
                attempts=1,
                structured_output_success=True,
            )
        ],
    )
    refused_response = FinalResponse(
        query="answerable refused",
        answer="controlled refusal",
        answer_payload=AnswerPayload(
            answer="controlled refusal",
            generator_backend="ollama",
            generation_attempts=1,
        ),
        retrieval=RetrievalResult(intent="general", mode="vector"),
        verification=VerifyResult(
            decision="refuse",
            decision_policy="partial_pass",
            evidence_score=0.4,
            retrieval_sufficiency=1.0,
            claim_results=[
                ClaimResult(
                    claim_id="C1",
                    claim_index=1,
                    claim="unsupported",
                    status="unsupported",
                    reason_codes=["term_not_supported"],
                )
            ],
            generated_claim_count=1,
            removed_claim_count=1,
            unsupported_claim_ids=["C1"],
            removed_claim_ids=["C1"],
        ),
        generation_trace=[
            GenerationCall(
                requested_backend="ollama",
                actual_backend="ollama",
                provider="ollama",
                model="qwen3:4b-test",
                attempts=1,
                structured_output_success=True,
            )
        ],
        retry_count=1,
    )
    no_answer_response = FinalResponse(
        query="no answer",
        answer="controlled refusal",
        answer_payload=AnswerPayload(answer="controlled refusal"),
        retrieval=RetrievalResult(intent="general", mode="vector"),
        verification=VerifyResult(decision="refuse", evidence_score=0.0),
    )

    class StubWorkflow:
        def __init__(self, response: FinalResponse):
            self.response = response

        def invoke(self, query: str) -> FinalResponse:
            return self.response

    def run(response: FinalResponse, *, expected_behavior: str) -> dict:
        return evaluate_question(
            StubWorkflow(response),
            {
                "question_id": response.query,
                "category": "synthetic",
                "question": response.query,
                "expected_behavior": expected_behavior,
                "expected_keywords": [],
                "gold_entities": [],
            },
        )

    report = summarize(
        [
            run(partial_response, expected_behavior="answer"),
            run(refused_response, expected_behavior="answer"),
            run(no_answer_response, expected_behavior="refuse"),
        ],
        "synthetic",
    )

    assert report["answerable_count"] == 2
    assert report["over_refusal_count"] == 1
    assert report["over_refusal_rate"] == 0.5
    assert report["correct_refusal_count"] == 1
    assert report["refusal_accuracy"] == 1.0
    assert report["partial_pass_count"] == 1
    assert report["retry_question_count"] == 1
    assert report["retry_rate"] == 0.3333
    assert report["decision_distribution"] == {
        "partial_pass": 1,
        "refuse": 2,
    }
    assert report["structured_output_attempt_count"] == 2
    assert report["structured_output_not_called_count"] == 1
    assert report["structured_output_success_rate"] == 1.0
    assert report["generated_claim_count"] == 3
    assert report["supported_claim_count"] == 1
    assert report["retained_claim_count"] == 1
    assert report["removed_claim_count"] == 2
    assert report["unsupported_claim_leakage_count"] == 1
    assert report["verification_reason_code_counts"] == {
        "generator_reported_gap": 1
    }
    assert report["claim_reason_code_counts"] == {
        "quote_not_supported": 1,
        "term_not_supported": 1,
    }
    assert report["audit_stage_counts"] == {"verification": 2}
    assert report["outcome_error_counts"] == {"over_refusal": 1}
