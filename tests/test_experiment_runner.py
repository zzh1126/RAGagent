from pathlib import Path

import pytest

from src.evaluation.config import load_experiment_suite
from src.evaluation.workflow_factory import ConfiguredRouter, NoVerifier, build_experiment_workflow
from src.schemas import AnswerPayload, RetrievalResult


ROOT = Path(__file__).resolve().parents[1]


class StubRouter:
    def route(self, query: str):
        from src.retrieval.intent_router import RouteDecision

        return RouteDecision("definition", "vector", "stub")


def test_fixed_router_overrides_only_retrieval_mode():
    router = ConfiguredRouter("fixed_graph", base_router=StubRouter())
    decision = router.route("任意问题")

    assert decision.intent == "definition"
    assert decision.mode == "graph"
    assert "fixed route" in decision.reason


def test_no_verifier_accepts_without_retry_and_keeps_unsupported_claims():
    answer = AnswerPayload(
        answer="一个未验证的回答",
        claims=[{"claim": "未支持事实"}],
    )
    retrieval = RetrievalResult(intent="general", mode="vector")
    result = NoVerifier().verify("问题", answer, retrieval, retry_count=0)

    assert result.decision == "pass"
    assert result.unsupported_claims == ["未支持事实"]
    assert NoVerifier.max_retries == 0


def test_factory_applies_vector_graph_and_no_verifier_modes():
    suite = load_experiment_suite(ROOT / "config" / "experiments.yaml")

    vector_workflow = build_experiment_workflow(ROOT, suite.experiments["vector_rag"])
    graph_workflow = build_experiment_workflow(ROOT, suite.experiments["graph_only"])
    no_verifier_workflow = build_experiment_workflow(ROOT, suite.experiments["no_verifier"])

    assert vector_workflow.router.route("随机森林为什么更稳定").mode == "vector"
    assert graph_workflow.router.route("什么是随机森林").mode == "graph"

    response = no_verifier_workflow.invoke("如何烤蛋糕")
    assert response.verification.decision == "pass"
    assert response.retry_count == 0


def test_factory_rejects_disabled_direct_llm():
    suite = load_experiment_suite(ROOT / "config" / "experiments.yaml")

    with pytest.raises(ValueError, match="disabled"):
        build_experiment_workflow(ROOT, suite.experiments["direct_llm"])
