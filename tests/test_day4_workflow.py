from pathlib import Path

from src.agent.workflow import QAWorkflow, build_default_workflow
from src.retrieval.intent_router import IntentRouter
from src.schemas import RetrievalResult, TextEvidence
from src.verification.evidence_verifier import EvidenceVerifier


ROOT = Path(__file__).resolve().parents[1]


def test_intent_router_selects_three_modes():
    router = IntentRouter()
    assert router.route("随机森林属于什么模型族").mode == "graph"
    assert router.route("Bagging 和 AdaBoost 有什么区别").mode == "hybrid"
    assert router.route("什么是逻辑回归").mode == "vector"


def test_hybrid_workflow_answers_with_verified_evidence():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("随机森林为什么更稳定")

    assert workflow.verifier.decision_policy == "strict"
    assert response.retrieval.mode == "hybrid"
    assert response.verification.decision == "pass"
    assert "[E" in response.answer
    assert response.retrieval.graph_paths
    assert response.retrieval.text_evidence
    assert response.route_trace is not None
    assert response.route_trace.mode == "hybrid"
    assert len(response.retrieval_trace) == 1
    assert len(response.verification_trace) == 1
    assert response.retrieval_trace[0].is_retry is False
    assert response.verification_trace[0].decision == "pass"
    assert response.latency_trace.retrieval_latency_ms >= 0.0
    assert response.latency_trace.verification_latency_ms >= 0.0
    assert response.latency_trace.retry_latency_ms == 0.0
    assert response.latency_trace.end_to_end_latency_ms >= max(
        response.latency_trace.routing_latency_ms,
        response.latency_trace.retrieval_latency_ms,
        response.latency_trace.verification_latency_ms,
    )
    assert response.cache_status == "disabled"


def test_hybrid_workflow_uses_incoming_metric_relations():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("类别不平衡时用什么指标")

    assert response.verification.decision == "pass"
    assert "平衡准确率" in response.answer
    assert "F1分数" in response.answer


def test_workflow_refuses_unknown_question():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("如何烤蛋糕")

    assert response.verification.decision == "refuse"
    assert "证据不足" in response.answer


def test_workflow_refuses_entity_attribute_not_supported_by_sources():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("随机森林的学习率是多少")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1
    assert len(response.generation_trace) == 2
    assert len(response.retrieval_trace) == 2
    assert len(response.verification_trace) == 2
    assert response.retrieval_trace[1].is_retry is True
    assert response.retrieval_trace[1].top_k == response.retrieval_trace[0].top_k * 2
    assert response.verification_trace[0].decision == "retry"
    assert response.verification_trace[1].decision == "refuse"
    assert response.latency_trace.retry_latency_ms >= 0.0
    assert response.latency_trace.llm_generation_latency_ms == 0.0


def test_workflow_refuses_external_algorithm_mentioned_only_as_reference():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("XGBoost 如何处理缺失值")

    assert response.verification.decision == "refuse"


def test_workflow_refuses_false_graph_premise():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("KMeans 是监督分类算法吗")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 0
    assert "premise_not_supported" in response.verification.reason_codes


def test_workflow_accepts_true_graph_premise():
    workflow = build_default_workflow(ROOT, generator_backend="offline_rule")
    response = workflow.invoke("随机森林是否使用 Bootstrap 抽样？")

    assert response.verification.decision == "pass"


class WeakRetriever:
    def retrieve(self, query, intent, mode, top_k=None):
        return RetrievalResult(
            intent=intent,
            mode=mode,
            text_evidence=[
                TextEvidence(
                    evidence_id="E1",
                    chunk_id="weak",
                    source_id="S1",
                    page_title="unrelated",
                    url="https://scikit-learn.org/",
                    display_text="unrelated",
                    score=0.01,
                )
            ],
        )


def test_weak_evidence_retries_once_then_refuses():
    workflow = QAWorkflow(
        retriever=WeakRetriever(),
        graph_repo=None,
        verifier=EvidenceVerifier(max_retries=1, min_vector_score=0.08),
    )
    response = workflow.invoke("一个无法由当前证据支持的问题")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1


def test_llm_workflow_defaults_to_partial_pass_and_supports_strict_override():
    partial_workflow = build_default_workflow(ROOT)
    strict_workflow = build_default_workflow(ROOT, verifier_policy="strict")

    assert partial_workflow.verifier.decision_policy == "partial_pass"
    assert strict_workflow.verifier.decision_policy == "strict"
