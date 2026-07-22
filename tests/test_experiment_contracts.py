from pathlib import Path

import pytest
from pydantic import ValidationError

from src.evaluation.config import ExperimentSuite, load_experiment_suite
from src.evaluation.schemas import (
    ExperimentMetrics,
    ExperimentRunReport,
    LatencyBreakdown,
    MetricValue,
    QuestionRunResult,
)


ROOT = Path(__file__).resolve().parents[1]


def computed(value: float, denominator: float) -> MetricValue:
    return MetricValue(
        value=value,
        numerator=value * denominator,
        denominator=denominator,
        status="computed",
    )


def test_experiment_matrix_is_frozen_and_valid():
    suite = load_experiment_suite(ROOT / "config" / "experiments.yaml")

    assert suite.protocol.tuning_split == "dev"
    assert suite.protocol.experiment_split == "pilot"
    assert suite.protocol.retrieval_recall_k == 5
    assert suite.protocol.frozen_holdout.split == "final"
    assert suite.protocol.frozen_holdout.policy == "reuse_v1_result_only"
    assert suite.experiments["direct_llm"].enabled is False
    assert suite.experiments["no_router"].enabled is False
    assert {
        name for name, item in suite.experiments.items() if item.enabled
    } == {"vector_rag", "graph_only", "proposed", "no_verifier"}
    assert len(suite.fingerprint()) == 64


def test_experiment_matrix_rejects_final_as_experiment_split():
    raw = {
        "schema_version": "1.0",
        "protocol": {
            "tuning_split": "final",
            "experiment_split": "pilot",
            "frozen_holdout": {"split": "final", "policy": "reuse_v1_result_only"},
        },
        "experiments": {},
    }

    with pytest.raises(ValidationError):
        ExperimentSuite.model_validate(raw)


def test_experiment_run_report_keeps_automated_and_human_metrics_separate():
    metrics = ExperimentMetrics(
        decision_accuracy=computed(1.0, 1),
        answer_correctness=MetricValue(
            status="pending_human_review", note="manual review required"
        ),
        evidence_faithfulness=MetricValue(
            status="pending_human_review", note="manual review required"
        ),
        retrieval_recall_at_5=computed(0.5, 2),
        path_validity=computed(1.0, 1),
        refusal_accuracy=computed(1.0, 1),
        hallucination_rate=MetricValue(status="pending_human_review"),
        over_refusal_rate=MetricValue(status="pending_human_review"),
        citation_rate=computed(1.0, 1),
        latency_ms=computed(2.0, 1),
    )
    result = QuestionRunResult(
        question_id="Q-01",
        question="测试问题",
        category="definition",
        expected_decision="pass",
        actual_decision="pass",
        decision_correct=True,
        retrieval_mode="vector",
        latency=LatencyBreakdown(total_ms=2.0),
    )
    report = ExperimentRunReport(
        run_id="run-001",
        experiment_id="vector_rag",
        experiment_config=load_experiment_suite(
            ROOT / "config" / "experiments.yaml"
        ).experiments["vector_rag"],
        dataset_split="pilot",
        dataset_path="data/evaluation/pilot_questions.jsonl",
        dataset_sha256="a" * 64,
        config_fingerprint="b" * 64,
        engine="langgraph",
        started_at="2026-07-22T00:00:00+00:00",
        completed_at="2026-07-22T00:00:01+00:00",
        question_count=1,
        metrics=metrics,
        results=[result],
    )

    assert report.metrics.answer_correctness.status == "pending_human_review"
    assert report.results[0].decision_correct is True


def test_experiment_run_report_rejects_result_count_mismatch():
    with pytest.raises(ValidationError):
        ExperimentRunReport(
            run_id="run-001",
            experiment_id="proposed",
            experiment_config=load_experiment_suite(
                ROOT / "config" / "experiments.yaml"
            ).experiments["proposed"],
            dataset_split="pilot",
            dataset_path="data/evaluation/pilot_questions.jsonl",
            dataset_sha256="a" * 64,
            config_fingerprint="b" * 64,
            engine="langgraph",
            started_at="2026-07-22T00:00:00+00:00",
            completed_at="2026-07-22T00:00:01+00:00",
            question_count=1,
            metrics=ExperimentMetrics(
                decision_accuracy=computed(1.0, 1),
                answer_correctness=MetricValue(status="pending_human_review"),
                evidence_faithfulness=MetricValue(status="pending_human_review"),
                retrieval_recall_at_5=MetricValue(status="not_applicable"),
                path_validity=MetricValue(status="not_applicable"),
                refusal_accuracy=MetricValue(status="not_applicable"),
                hallucination_rate=MetricValue(status="pending_human_review"),
                over_refusal_rate=MetricValue(status="pending_human_review"),
                citation_rate=MetricValue(status="not_applicable"),
                latency_ms=MetricValue(status="not_applicable"),
            ),
            results=[],
        )
