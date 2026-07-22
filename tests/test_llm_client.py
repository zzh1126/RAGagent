from __future__ import annotations

import logging
from typing import Literal

import pytest
import requests
from pydantic import BaseModel, ConfigDict, ValidationError

from src.llm import (
    LLMEmptyResponseError,
    LLMSchemaError,
    LLMSettings,
    LLMTimeoutError,
    LLMUnavailableError,
    OllamaClient,
    create_llm_client,
)
from src.schemas import AnswerClaim, AnswerPayload


class StatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    evidence_ids: list[str]


class FakeResponse:
    def __init__(self, data=None, *, status_code: int = 200, json_error: Exception | None = None):
        self.data = data
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.data


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(content: str, **metadata) -> FakeResponse:
    return FakeResponse({"message": {"content": content}, **metadata})


def settings(**overrides) -> LLMSettings:
    return LLMSettings.model_validate(overrides)


def messages(secret: str = "synthetic question") -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Return schema-valid JSON."},
        {"role": "user", "content": secret},
    ]


def test_structured_success_uses_strict_ollama_contract_and_sanitized_log(caplog) -> None:
    session = FakeSession(
        response(
            '{"status":"ok","evidence_ids":["E1"]}',
            prompt_eval_count=12,
            eval_count=7,
            done_reason="stop",
        )
    )
    events = []
    client = OllamaClient(settings(), session=session, event_sink=events.append)

    with caplog.at_level(logging.INFO, logger="src.llm.ollama_client"):
        result = client.generate_structured(
            messages=messages("PRIVATE_PROMPT_MARKER"),
            response_model=StatusPayload,
            node="contract_test",
        )

    assert result == StatusPayload(status="ok", evidence_ids=["E1"])
    assert len(session.calls) == 1
    request = session.calls[0]
    assert request["url"] == "http://127.0.0.1:11434/api/chat"
    assert request["json"]["think"] is False
    assert request["json"]["stream"] is False
    assert request["json"]["format"] == StatusPayload.model_json_schema()
    assert request["json"]["options"]["temperature"] == 0.0
    assert request["timeout"] == 120.0
    assert len(events) == 1
    assert events[0].success is True
    assert events[0].schema_valid is True
    assert events[0].attempts == 1
    assert events[0].prompt_tokens == 12
    assert events[0].completion_tokens == 7
    assert "PRIVATE_PROMPT_MARKER" not in caplog.text
    assert "message.content" not in caplog.text


def test_empty_content_fails_without_reading_thinking_or_retrying() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "message": {
                    "content": "   ",
                    "thinking": '{"status":"ok","evidence_ids":["E1"]}',
                }
            }
        )
    )
    events = []
    client = OllamaClient(settings(), session=session, event_sink=events.append)

    with pytest.raises(LLMEmptyResponseError, match="message.content is empty"):
        client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert len(session.calls) == 1
    assert events[0].error_type == "LLMEmptyResponseError"
    assert "thinking" not in events[0].model_dump()


def test_schema_failure_gets_one_generic_repair_attempt() -> None:
    session = FakeSession(
        response('{"status":"wrong","evidence_ids":[]}'),
        response('{"status":"ok","evidence_ids":["E1"]}'),
    )
    client = OllamaClient(settings(), session=session)

    result = client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert result.status == "ok"
    assert len(session.calls) == 2
    repair_messages = session.calls[1]["json"]["messages"]
    assert repair_messages[-1]["role"] == "system"
    assert "required JSON Schema" in repair_messages[-1]["content"]
    assert "status:literal_error" in repair_messages[-1]["content"]
    assert '"status":"wrong"' not in repair_messages[-1]["content"]
    assert client.last_call is not None
    assert client.last_call.attempts == 2


def test_schema_failure_after_repair_raises_typed_error() -> None:
    session = FakeSession(response("not json"), response('{"status":"wrong"}'))
    client = OllamaClient(settings(), session=session)

    with pytest.raises(LLMSchemaError, match="StatusPayload"):
        client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert len(session.calls) == 2
    assert client.last_call is not None
    assert client.last_call.error_type == "LLMSchemaError"
    assert client.last_call.validation_issues


def test_timeout_retries_once_then_succeeds() -> None:
    session = FakeSession(
        requests.Timeout("first timeout"),
        response('{"status":"ok","evidence_ids":["E1"]}'),
    )
    client = OllamaClient(settings(), session=session)

    result = client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert result.status == "ok"
    assert len(session.calls) == 2
    assert client.last_call is not None
    assert client.last_call.attempts == 2


def test_repeated_timeout_raises_typed_error() -> None:
    session = FakeSession(requests.Timeout("first"), requests.Timeout("second"))
    client = OllamaClient(settings(), session=session)

    with pytest.raises(LLMTimeoutError, match="2 attempt"):
        client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert len(session.calls) == 2
    assert client.last_call is not None
    assert client.last_call.error_type == "LLMTimeoutError"


def test_unavailable_service_fails_immediately() -> None:
    session = FakeSession(requests.ConnectionError("connection refused"))
    client = OllamaClient(settings(), session=session)

    with pytest.raises(LLMUnavailableError, match="service is unavailable"):
        client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert len(session.calls) == 1


def test_http_failure_is_unavailable_and_not_retried() -> None:
    session = FakeSession(FakeResponse(status_code=404))
    client = OllamaClient(settings(), session=session)

    with pytest.raises(LLMUnavailableError, match="HTTP 404"):
        client.generate_structured(messages=messages(), response_model=StatusPayload)

    assert len(session.calls) == 1


def test_factory_validates_settings_and_applies_explicit_environment_overrides() -> None:
    client = create_llm_client(
        settings(),
        session=FakeSession(),
        environ={
            "OLLAMA_BASE_URL": "http://localhost:11500/",
            "OLLAMA_MODEL": "qwen3:4b-test",
        },
    )

    assert isinstance(client, OllamaClient)
    assert client.base_url == "http://localhost:11500"
    assert client.model == "qwen3:4b-test"

    with pytest.raises(ValidationError):
        LLMSettings.model_validate({"think": True})
    with pytest.raises(ValidationError):
        LLMSettings.model_validate({"max_retries": 2})
    with pytest.raises(ValidationError, match="must not contain credentials"):
        LLMSettings.model_validate({"base_url": "http://user:secret@localhost:11434"})


def test_invalid_node_fails_before_sending_request() -> None:
    session = FakeSession(response('{"status":"ok","evidence_ids":["E1"]}'))
    client = OllamaClient(settings(), session=session)

    with pytest.raises(ValueError, match="node must not be blank"):
        client.generate_structured(
            messages=messages(),
            response_model=StatusPayload,
            node="   ",
        )

    assert not session.calls


def test_answer_payload_uses_typed_claims_and_rejects_unknown_fields() -> None:
    payload = AnswerPayload(
        answer="结构化回答",
        claims=[
            {
                "claim": "随机森林属于集成学习。",
                "evidence_ids": ["E1"],
                "graph_path_ids": ["P1"],
            }
        ],
    )

    assert isinstance(payload.claims[0], AnswerClaim)
    assert payload.generator_backend == "offline_rule"
    assert payload.claims[0].graph_path_ids == ["P1"]

    with pytest.raises(ValidationError):
        AnswerPayload(
            answer="包含未知字段",
            claims=[{"claim": "事实", "evidence_ids": [], "invented_field": True}],
        )
