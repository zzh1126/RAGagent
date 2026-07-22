from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel

from src.llm.schemas import ChatMessage, LLMCallRecord


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
LLMEventSink = Callable[[LLMCallRecord], None]


class LLMClient(Protocol):
    provider: str
    model: str

    def generate_structured(
        self,
        *,
        messages: Sequence[ChatMessage | Mapping[str, str]],
        response_model: type[StructuredModel],
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        node: str = "llm_client",
    ) -> StructuredModel:
        ...
