from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictLLMModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessage(StrictLLMModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LLMCallRecord(StrictLLMModel):
    request_id: str = Field(min_length=1)
    node: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    response_schema: str = Field(min_length=1)
    success: bool
    schema_valid: bool
    fallback_used: bool = False
    attempts: int = Field(ge=1)
    latency_ms: float = Field(ge=0.0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    done_reason: str | None = None
    error_type: str | None = None
    validation_issues: list[str] = Field(default_factory=list)
