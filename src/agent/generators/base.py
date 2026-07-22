from __future__ import annotations

from typing import Protocol

from src.schemas import AnswerPayload, RetrievalResult


class AnswerGenerator(Protocol):
    def generate(self, query: str, retrieval: RetrievalResult) -> AnswerPayload:
        ...

    def refusal_answer(self) -> str:
        ...
