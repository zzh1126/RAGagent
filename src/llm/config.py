from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = Field(default="qwen3:4b", min_length=1)
    think: Literal[False] = False
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    keep_alive: str = Field(default="30m", min_length=1)
    num_predict: int = Field(default=768, ge=1, le=4096)
    seed: int = 42
    max_retries: int = Field(default=1, ge=0, le=1)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not contain credentials")
        return normalized

    @field_validator("model", "keep_alive")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class AgentLLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner_backend: Literal["rule"] = "rule"
    generator_backend: Literal["offline_rule", "llm"] = "offline_rule"
    planner_fallback: Literal["rule"] = "rule"
    generator_fallback: Literal["offline_rule"] = "offline_rule"
