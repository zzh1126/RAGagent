from __future__ import annotations

import re

import pytest

from src.agent.answer_generator import GroundedAnswerGenerator
from src.agent.generators import (
    EvidenceContextSerializer,
    FallbackAnswerGenerator,
    LLMAnswerGenerator,
    create_answer_generator,
)
from src.agent.workflow import build_default_workflow
from src.llm import LLMUnavailableError
from src.llm.config import AgentLLMSettings
from src.llm.schemas import LLMCallRecord
from src.schemas import (
    GraphPath,
    GraphTriple,
    LinkedEntity,
    RetrievalResult,
    TextEvidence,
)
from src.verification.evidence_verifier import EvidenceVerifier


class StubGraphRepository:
    def validate_path(self, triples: list[dict]) -> bool:
        return bool(triples)

    def find_entity(self, entity_id: str) -> dict:
        return {
            "entity_id": entity_id,
            "description_zh": "随机森林是基于随机化决策树的集成方法",
        }


def sample_retrieval(*, duplicate: bool = False) -> RetrievalResult:
    evidence = [
        TextEvidence(
            evidence_id="E1",
            chunk_id="C1",
            source_id="S4",
            page_title="Ensemble methods",
            heading_path=["Random forests"],
            url="https://scikit-learn.org/stable/modules/ensemble.html",
            display_text=(
                "Random forests are ensemble methods based on randomized decision trees. "
                "Averaging reduces variance while retaining predictive strength."
            ),
            score=0.91,
        )
    ]
    paths = [
        GraphPath(
            path_id="P1",
            triples=[
                GraphTriple(
                    source_id="ALG_RF",
                    source_name="随机森林",
                    relation="BELONGS_TO",
                    target_id="FAM_ENSEMBLE",
                    target_name="集成学习",
                    relation_id="R1",
                    evidence_chunk_ids=["C1"],
                    review_status="approved",
                )
            ],
            evidence_chunk_ids=["C1"],
        )
    ]
    if duplicate:
        evidence.append(
            TextEvidence(
                evidence_id="E2",
                chunk_id="C2",
                source_id="S4",
                page_title="Very long evidence",
                heading_path=["Long"],
                url="https://scikit-learn.org/stable/modules/ensemble.html#long",
                display_text="token " * 500,
                score=0.5,
            )
        )
        paths.append(paths[0].model_copy(update={"path_id": "P2"}))
    return RetrievalResult(
        intent="relation",
        mode="hybrid",
        entities=[
            LinkedEntity(
                entity_id="ALG_RF",
                name_en="Random Forest",
                name_zh="随机森林",
                type="Algorithm",
                matched_text="随机森林",
            )
        ],
        graph_paths=paths,
        text_evidence=evidence,
    )


class StubLLMClient:
    provider = "ollama"
    model = "qwen3:4b-stub"

    def __init__(self, output: dict | None = None, error: Exception | None = None):
        self.output = output
        self.error = error
        self.calls: list[dict] = []
        self.last_call: LLMCallRecord | None = None

    def generate_structured(self, *, messages, response_model, node, **kwargs):
        self.calls.append(
            {"messages": messages, "response_model": response_model, "node": node, **kwargs}
        )
        if self.error is not None:
            self.last_call = call_record(success=False, error_type=type(self.error).__name__)
            raise self.error
        self.last_call = call_record(success=True)
        return response_model.model_validate(self.output)


class ContextAwareLLMClient(StubLLMClient):
    def __init__(self):
        super().__init__()

    def generate_structured(self, *, messages, response_model, node, **kwargs):
        context = messages[-1]["content"]
        evidence_match = re.search(r"AVAILABLE_TEXT_EVIDENCE_IDS: ([^\n]+)", context)
        path_match = re.search(r"AVAILABLE_GRAPH_PATH_IDS: ([^\n]+)", context)
        evidence_id = evidence_match.group(1).split(",")[0].strip()
        path_value = path_match.group(1).split(",")[0].strip() if path_match else "(none)"
        path_ids = [] if path_value == "(none)" else [path_value]
        self.output = {
            "answer": f"随机森林的结论由当前证据支持 [{evidence_id}]。",
            "claims": [
                {
                    "claim": "随机森林的结论由当前证据支持。",
                    "evidence_ids": [evidence_id],
                    "graph_path_ids": path_ids,
                    "supporting_quotes": [
                        {
                            "evidence_id": evidence_id,
                            "quote": self._extract_quote(context, evidence_id),
                        }
                    ],
                }
            ],
            "graph_paths": path_ids,
            "unsupported_claims": [],
            "confidence": 0.8,
        }
        return super().generate_structured(
            messages=messages,
            response_model=response_model,
            node=node,
            **kwargs,
        )

    @staticmethod
    def _extract_quote(context: str, evidence_id: str) -> str:
        match = re.search(
            rf"\[{re.escape(evidence_id)}\][\s\S]*?\ntext=([^\n]+)",
            context,
        )
        assert match is not None
        return match.group(1)[:80]


class UnexpectedFailureGenerator:
    def generate(self, query, retrieval):
        raise ValueError("programming error")

    @staticmethod
    def refusal_answer() -> str:
        return "refuse"


def call_record(*, success: bool, error_type: str | None = None) -> LLMCallRecord:
    return LLMCallRecord(
        request_id="stub-request",
        node="llm_generate_answer",
        provider="ollama",
        model="qwen3:4b-stub",
        response_schema="LLMAnswerDraft",
        success=success,
        schema_valid=success,
        attempts=1,
        latency_ms=12.5,
        error_type=error_type,
    )


def valid_output() -> dict:
    return {
        "answer": "随机森林属于集成学习 [E1][P1]。",
        "claims": [
            {
                "claim": "随机森林属于集成学习。",
                "evidence_ids": ["E1"],
                "graph_path_ids": ["P1"],
                "relation_id": "R1",
                "supporting_quotes": [
                    {
                        "evidence_id": "E1",
                        "quote": "Random forests are ensemble methods based on randomized decision trees.",
                    }
                ],
            }
        ],
        "graph_paths": ["P1"],
        "unsupported_claims": [],
        "confidence": 0.9,
    }


def test_context_serializer_limits_items_and_evidence_length() -> None:
    serializer = EvidenceContextSerializer(
        max_text_evidence=1,
        max_graph_paths=1,
        max_chars_per_evidence=220,
        max_context_chars=2500,
    )

    context = serializer.serialize("随机森林属于什么模型族？", sample_retrieval(duplicate=True))

    assert "AVAILABLE_TEXT_EVIDENCE_IDS: E1" in context
    assert "AVAILABLE_GRAPH_PATH_IDS: P1" in context
    assert "[E2]" not in context
    assert "[P2]" not in context
    assert len(context) <= 2500


def test_llm_generator_uses_wire_schema_and_sets_runtime_metadata() -> None:
    client = StubLLMClient(output=valid_output())
    generator = LLMAnswerGenerator(client)

    payload = generator.generate("随机森林属于什么模型族？", sample_retrieval())

    assert payload.generator_backend == "ollama"
    assert payload.fallback_used is False
    assert payload.generation_attempts == 1
    assert payload.generation_latency_ms == 12.5
    assert payload.evidence_packing is not None
    assert payload.evidence_packing.selected_evidence_ids == ["E1"]
    assert payload.claims[0].evidence_ids == ["E1"]
    assert client.calls[0]["node"] == "llm_generate_answer"
    wire_properties = client.calls[0]["response_model"].model_json_schema()["properties"]
    assert "generator_backend" not in wire_properties
    assert "fallback_reason" not in wire_properties
    assert "claims" in client.calls[0]["response_model"].model_json_schema()["required"]
    assert "AVAILABLE_TEXT_EVIDENCE_IDS: E1" in client.calls[0]["messages"][-1]["content"]


def test_llm_rejects_ids_present_in_retrieval_but_hidden_by_packer() -> None:
    output = valid_output()
    output["claims"][0].update(
        evidence_ids=["E2"],
        graph_path_ids=["P2"],
        supporting_quotes=[
            {
                "evidence_id": "E2",
                "quote": "token token token token",
            }
        ],
    )
    output["graph_paths"] = ["P2"]
    generator = LLMAnswerGenerator(
        StubLLMClient(output=output),
        context_serializer=EvidenceContextSerializer(
            max_text_evidence=1,
            max_graph_paths=1,
        ),
    )

    payload = generator.generate(
        "随机森林属于什么模型族？",
        sample_retrieval(duplicate=True),
    )

    assert payload.evidence_packing is not None
    assert payload.evidence_packing.selected_evidence_ids == ["E1"]
    assert payload.evidence_packing.selected_graph_path_ids == ["P1"]
    assert any("E2" in item for item in payload.unsupported_claims)
    assert any("P2" in item for item in payload.unsupported_claims)


def test_llm_generator_rebuilds_answer_from_structured_claims() -> None:
    output = valid_output()
    output["answer"] = "随机森林的模型族，而且它一定优于所有其他算法 [E1]。"
    generator = LLMAnswerGenerator(StubLLMClient(output=output))

    payload = generator.generate("随机森林属于什么模型族？", sample_retrieval())

    assert payload.answer.startswith("- 随机森林属于集成学习")
    assert "[E1][P1]" in payload.answer
    assert "优于所有其他算法" not in payload.answer


def test_llm_generator_rejects_case_changed_nonverbatim_quote() -> None:
    output = valid_output()
    output["claims"][0]["supporting_quotes"][0]["quote"] = (
        "random forests are ensemble methods based on randomized decision trees."
    )
    generator = LLMAnswerGenerator(StubLLMClient(output=output))

    payload = generator.generate("随机森林属于什么模型族？", sample_retrieval())

    assert any("supporting quote 不存在于 E1" in item for item in payload.unsupported_claims)


def test_llm_generator_removes_top_level_path_not_used_by_claims() -> None:
    output = valid_output()
    output["claims"][0]["graph_path_ids"] = []
    output["claims"][0]["relation_id"] = ""
    generator = LLMAnswerGenerator(StubLLMClient(output=output))

    payload = generator.generate("随机森林属于什么模型族？", sample_retrieval())

    assert payload.graph_paths == []
    assert "顶层 graph_paths 与 Claims 实际使用的路径不一致" in payload.unsupported_claims


def test_unknown_evidence_path_and_relation_ids_cannot_pass_verification() -> None:
    output = valid_output()
    output["claims"][0].update(
        evidence_ids=["E999"],
        graph_path_ids=["P999"],
        relation_id="R999",
        supporting_quotes=[{"evidence_id": "E999", "quote": "invented supporting quote"}],
    )
    output["graph_paths"] = ["P999"]
    generator = LLMAnswerGenerator(StubLLMClient(output=output))
    retrieval = sample_retrieval()

    payload = generator.generate("随机森林属于什么模型族？", retrieval)
    result = EvidenceVerifier(max_retries=0).verify(
        "随机森林属于什么模型族？",
        payload,
        retrieval,
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "refuse"
    assert any("E999" in item for item in result.unsupported_claims)
    assert any("P999" in item for item in result.unsupported_claims)
    assert any("R999" in item for item in result.unsupported_claims)


def test_model_declared_gap_produces_partial_pass() -> None:
    output = valid_output()
    output["unsupported_claims"] = ["证据没有给出具体超参数"]
    generator = LLMAnswerGenerator(StubLLMClient(output=output))
    retrieval = sample_retrieval()

    payload = generator.generate("随机森林属于什么模型族？", retrieval)
    result = EvidenceVerifier(max_retries=0).verify(
        "随机森林属于什么模型族？",
        payload,
        retrieval,
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "partial_pass"
    assert result.retained_claim_ids == ["C1"]
    assert "证据没有给出具体超参数" in result.unsupported_claims


def test_exact_but_semantically_misaligned_quote_is_rejected_by_term_coverage() -> None:
    output = valid_output()
    output["claims"][0] = {
        "claim": "AdaBoost 在每次迭代中提高错误样本权重，从而降低偏差。",
        "evidence_ids": ["E1"],
        "graph_path_ids": ["P1"],
        "relation_id": "R1",
        "supporting_quotes": [
            {
                "evidence_id": "E1",
                "quote": "Random forests are ensemble methods based on randomized decision trees.",
            }
        ],
    }
    generator = LLMAnswerGenerator(StubLLMClient(output=output))
    retrieval = sample_retrieval()

    payload = generator.generate("随机森林属于什么模型族？", retrieval)
    result = EvidenceVerifier(max_retries=0).verify(
        "随机森林属于什么模型族？",
        payload,
        retrieval,
        graph_repo=StubGraphRepository(),
    )

    assert result.decision == "refuse"
    assert any("权重" in item and "偏差" in item for item in result.unsupported_claims)


def test_expected_llm_failure_falls_back_to_offline_generator() -> None:
    client = StubLLMClient(error=LLMUnavailableError("offline"))
    settings = AgentLLMSettings(generator_backend="llm")
    generator = create_answer_generator(
        settings,
        graph_repo=StubGraphRepository(),
        llm_client=client,
    )

    payload = generator.generate("随机森林属于什么模型族？", sample_retrieval())

    assert payload.generator_backend == "offline_rule"
    assert payload.fallback_used is True
    assert payload.fallback_reason == "LLMUnavailableError"
    assert payload.generation_attempts == 1
    assert payload.evidence_packing is not None
    assert payload.evidence_packing.selected_evidence_ids == ["E1"]
    assert "随机森林" in payload.answer


def test_fallback_does_not_hide_unexpected_programming_errors() -> None:
    generator = FallbackAnswerGenerator(
        primary=UnexpectedFailureGenerator(),
        fallback=GroundedAnswerGenerator(StubGraphRepository()),
    )

    with pytest.raises(ValueError, match="programming error"):
        generator.generate("问题", sample_retrieval())


def test_factory_keeps_offline_mode_without_llm_client() -> None:
    generator = create_answer_generator(
        AgentLLMSettings(generator_backend="offline_rule"),
        graph_repo=StubGraphRepository(),
    )

    assert isinstance(generator, GroundedAnswerGenerator)


def test_default_workflow_can_run_injected_llm_generator_path() -> None:
    client = ContextAwareLLMClient()
    workflow = build_default_workflow(
        llm_client=client,
    )

    response = workflow.invoke("随机森林为什么更稳定")

    assert response.verification.decision == "pass"
    assert response.answer_payload.generator_backend == "ollama"
    assert response.answer_payload.fallback_used is False
    assert response.generation_trace[0].provider == "ollama"
    assert response.generation_trace[0].model == "qwen3:4b-stub"
    assert response.latency_trace.llm_generation_latency_ms == 12.5
    assert response.latency_trace.end_to_end_latency_ms >= 12.5
    assert workflow.prewarm().status == "unsupported"
    assert response.answer_payload is not None
    assert len(response.generation_trace) == 1
    assert len(response.evidence_packing_trace) == 1
    assert response.evidence_packing_trace[0].selected_evidence_ids
    assert response.generation_trace[0].structured_output_success is True
    assert client.calls


def test_workflow_preserves_one_packing_trace_per_retry_generation() -> None:
    client = StubLLMClient(output=valid_output())
    workflow = build_default_workflow(llm_client=client)

    response = workflow.invoke("随机森林的学习率是多少")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1
    assert len(response.generation_trace) == 2
    assert len(response.evidence_packing_trace) == 2
    assert len(client.calls) == 2
