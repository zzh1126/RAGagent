from __future__ import annotations

import os
from collections.abc import Mapping

import requests

from src.llm.base import LLMClient, LLMEventSink
from src.llm.config import LLMSettings
from src.llm.ollama_client import OllamaClient


def create_llm_client(
    settings: LLMSettings | Mapping,
    *,
    session: requests.Session | None = None,
    event_sink: LLMEventSink | None = None,
    environ: Mapping[str, str] | None = None,
) -> LLMClient:
    config = settings if isinstance(settings, LLMSettings) else LLMSettings.model_validate(settings)
    environment = os.environ if environ is None else environ
    overrides = {}
    if environment.get("OLLAMA_BASE_URL"):
        overrides["base_url"] = environment["OLLAMA_BASE_URL"]
    if environment.get("OLLAMA_MODEL"):
        overrides["model"] = environment["OLLAMA_MODEL"]
    if overrides:
        config = config.model_copy(update=overrides)
        config = LLMSettings.model_validate(config.model_dump())

    if config.provider == "ollama":
        return OllamaClient(config, session=session, event_sink=event_sink)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
