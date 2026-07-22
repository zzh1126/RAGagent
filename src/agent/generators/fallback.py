from __future__ import annotations

from src.agent.generators.base import AnswerGenerator
from src.llm.exceptions import (
    LLMEmptyResponseError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from src.schemas import AnswerPayload, RetrievalResult


EXPECTED_LLM_FAILURES = (
    LLMUnavailableError,
    LLMTimeoutError,
    LLMEmptyResponseError,
    LLMSchemaError,
)


class FallbackAnswerGenerator:
    def __init__(self, primary: AnswerGenerator, fallback: AnswerGenerator) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(self, query: str, retrieval: RetrievalResult) -> AnswerPayload:
        try:
            return self.primary.generate(query, retrieval)
        except EXPECTED_LLM_FAILURES as exc:
            failed_call = getattr(self.primary, "last_call", None)
            payload = self.fallback.generate(query, retrieval)
            return payload.model_copy(
                update={
                    "fallback_used": True,
                    "fallback_reason": type(exc).__name__,
                    "generation_attempts": failed_call.attempts if failed_call else 1,
                    "generation_latency_ms": failed_call.latency_ms if failed_call else 0.0,
                }
            )

    def refusal_answer(self) -> str:
        return self.fallback.refusal_answer()
