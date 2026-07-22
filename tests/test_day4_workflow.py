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
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("随机森林为什么更稳定")

    assert response.retrieval.mode == "hybrid"
    assert response.verification.decision == "pass"
    assert "[E" in response.answer
    assert response.retrieval.graph_paths
    assert response.retrieval.text_evidence


def test_hybrid_workflow_uses_incoming_metric_relations():
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("类别不平衡时用什么指标")

    assert response.verification.decision == "pass"
    assert "平衡准确率" in response.answer
    assert "F1分数" in response.answer


def test_workflow_refuses_unknown_question():
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("如何烤蛋糕")

    assert response.verification.decision == "refuse"
    assert "证据不足" in response.answer


def test_workflow_refuses_entity_attribute_not_supported_by_sources():
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("随机森林的学习率是多少")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1


def test_workflow_refuses_external_algorithm_mentioned_only_as_reference():
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("XGBoost 如何处理缺失值")

    assert response.verification.decision == "refuse"


def test_workflow_refuses_false_graph_premise():
    workflow = build_default_workflow(ROOT)
    response = workflow.invoke("KMeans 是监督分类算法吗")

    assert response.verification.decision == "refuse"
    assert response.retry_count == 1


def test_workflow_accepts_true_graph_premise():
    workflow = build_default_workflow(ROOT)
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
