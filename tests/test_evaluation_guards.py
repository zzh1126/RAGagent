import pytest

from scripts.run_evaluation import ensure_split_runnable, evaluate_question
from src.schemas import (
    AnswerPayload,
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
