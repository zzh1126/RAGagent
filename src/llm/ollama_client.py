from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Mapping, Sequence

import requests
from pydantic import BaseModel, ValidationError

from src.llm.base import LLMEventSink, StructuredModel
from src.llm.config import LLMSettings
from src.llm.exceptions import (
    LLMEmptyResponseError,
    LLMError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from src.llm.schemas import ChatMessage, LLMCallRecord


LOGGER = logging.getLogger(__name__)
REPAIR_MESSAGE = (
    "The previous response did not match the required JSON Schema. "
    "Return only one corrected JSON object that follows the supplied schema."
)


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        settings: LLMSettings,
        *,
        session: requests.Session | None = None,
        event_sink: LLMEventSink | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self.model = settings.model
        self.session = session or requests.Session()
        self.event_sink = event_sink
        self.last_call: LLMCallRecord | None = None

    def generate_structured(
        self,
        *,
        messages: Sequence[ChatMessage | Mapping[str, str]],
        response_model: type[StructuredModel],
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        node: str = "llm_client",
    ) -> StructuredModel:
        normalized_messages = self._normalize_messages(messages)
        if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
            raise TypeError("response_model must be a Pydantic BaseModel type")
        node = node.strip()
        if not node:
            raise ValueError("node must not be blank")

        effective_temperature = self.settings.temperature if temperature is None else temperature
        effective_timeout = self.settings.timeout_seconds if timeout_seconds is None else timeout_seconds
        if not 0.0 <= effective_temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if effective_timeout <= 0:
            raise ValueError("timeout_seconds must be positive")

        request_id = uuid.uuid4().hex
        started_at = time.perf_counter()
        attempts = 0
        response_data: dict = {}
        schema_valid = False
        validation_issues: list[str] = []
        request_messages = normalized_messages

        try:
            while attempts <= self.settings.max_retries:
                attempts += 1
                payload = self._request_payload(
                    request_messages,
                    response_model,
                    temperature=effective_temperature,
                )
                try:
                    response = self.session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=effective_timeout,
                    )
                except requests.Timeout as exc:
                    if attempts <= self.settings.max_retries:
                        continue
                    raise LLMTimeoutError(
                        f"Ollama timed out after {attempts} attempt(s)"
                    ) from exc
                except requests.ConnectionError as exc:
                    raise LLMUnavailableError("Ollama service is unavailable") from exc
                except requests.RequestException as exc:
                    raise LLMUnavailableError("Ollama request failed") from exc

                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    status_code = getattr(response, "status_code", "unknown")
                    raise LLMUnavailableError(
                        f"Ollama returned HTTP {status_code}"
                    ) from exc

                try:
                    candidate = response.json()
                except (TypeError, ValueError) as exc:
                    if attempts <= self.settings.max_retries:
                        request_messages = self._with_repair_message(normalized_messages)
                        continue
                    raise LLMSchemaError("Ollama returned an invalid response envelope") from exc
                if not isinstance(candidate, dict):
                    if attempts <= self.settings.max_retries:
                        request_messages = self._with_repair_message(normalized_messages)
                        continue
                    raise LLMSchemaError("Ollama returned an invalid response envelope")
                response_data = candidate
                message = response_data.get("message")
                if not isinstance(message, dict):
                    if attempts <= self.settings.max_retries:
                        request_messages = self._with_repair_message(normalized_messages)
                        continue
                    raise LLMSchemaError("Ollama response is missing message metadata")

                content = message.get("content")
                if not isinstance(content, str):
                    if attempts <= self.settings.max_retries:
                        request_messages = self._with_repair_message(normalized_messages)
                        continue
                    raise LLMSchemaError("Ollama message.content must be a string")
                content = content.strip()
                if not content:
                    raise LLMEmptyResponseError("Ollama message.content is empty")

                try:
                    parsed = response_model.model_validate_json(content)
                except ValidationError as exc:
                    validation_issues = self._validation_issues(exc)
                    if attempts <= self.settings.max_retries:
                        request_messages = self._with_repair_message(
                            normalized_messages,
                            validation_error=exc,
                        )
                        continue
                    raise LLMSchemaError(
                        f"Ollama content does not match {response_model.__name__}"
                    ) from exc

                schema_valid = True
                self._emit_record(
                    request_id=request_id,
                    node=node,
                    response_model=response_model,
                    success=True,
                    schema_valid=True,
                    attempts=attempts,
                    started_at=started_at,
                    response_data=response_data,
                    error_type=None,
                    validation_issues=[],
                )
                return parsed
        except LLMError as exc:
            self._emit_record(
                request_id=request_id,
                node=node,
                response_model=response_model,
                success=False,
                schema_valid=schema_valid,
                attempts=max(attempts, 1),
                started_at=started_at,
                response_data=response_data,
                error_type=type(exc).__name__,
                validation_issues=validation_issues,
            )
            raise

        raise AssertionError("Ollama retry loop exited without a result")

    def _request_payload(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        *,
        temperature: float,
    ) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "think": False,
            "stream": False,
            "format": response_model.model_json_schema(),
            "keep_alive": self.settings.keep_alive,
            "options": {
                "temperature": temperature,
                "seed": self.settings.seed,
                "num_predict": self.settings.num_predict,
            },
        }

    @staticmethod
    def _normalize_messages(
        messages: Sequence[ChatMessage | Mapping[str, str]],
    ) -> list[dict[str, str]]:
        if not messages:
            raise ValueError("messages must not be empty")
        return [
            ChatMessage.model_validate(message).model_dump(mode="json")
            for message in messages
        ]

    @staticmethod
    def _with_repair_message(
        messages: list[dict[str, str]],
        *,
        validation_error: ValidationError | None = None,
    ) -> list[dict[str, str]]:
        message = REPAIR_MESSAGE
        if validation_error is not None:
            issues = OllamaClient._validation_issues(validation_error)
            if issues:
                message += " Validation issues: " + ", ".join(issues) + "."
        return [*messages, {"role": "system", "content": message}]

    def _emit_record(
        self,
        *,
        request_id: str,
        node: str,
        response_model: type[BaseModel],
        success: bool,
        schema_valid: bool,
        attempts: int,
        started_at: float,
        response_data: dict,
        error_type: str | None,
        validation_issues: list[str],
    ) -> None:
        record = LLMCallRecord(
            request_id=request_id,
            node=node,
            provider=self.provider,
            model=self.model,
            response_schema=response_model.__name__,
            success=success,
            schema_valid=schema_valid,
            attempts=attempts,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 1),
            prompt_tokens=self._optional_nonnegative_int(response_data.get("prompt_eval_count")),
            completion_tokens=self._optional_nonnegative_int(response_data.get("eval_count")),
            done_reason=self._optional_string(response_data.get("done_reason")),
            error_type=error_type,
            validation_issues=validation_issues,
        )
        self.last_call = record
        LOGGER.info("llm_call %s", record.model_dump_json())
        if self.event_sink is not None:
            try:
                self.event_sink(record)
            except Exception as exc:
                LOGGER.warning("LLM event sink failed error_type=%s", type(exc).__name__)

    @staticmethod
    def _optional_nonnegative_int(value) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    @staticmethod
    def _optional_string(value) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _validation_issues(error: ValidationError) -> list[str]:
        issues = []
        for item in error.errors(include_url=False, include_input=False)[:5]:
            location = ".".join(str(part) for part in item.get("loc", ())) or "root"
            issues.append(f"{location}:{item.get('type', 'validation_error')}")
        return issues
