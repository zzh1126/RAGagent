from __future__ import annotations

from pathlib import Path

from src.evaluation import extension_runner_v2
from src.evaluation.extension_release import (
    IMPLEMENTATION_MANIFEST_PATH,
    RELEASE_RECORD_PATH,
    V2_METHOD_ORDER,
    sha256_file,
)
from src.evaluation.extension_release_v2 import (
    V2_EXECUTION_RECEIPT_PATH,
    V2_EXECUTION_STATE_PATH,
    V2_FINAL_OUTPUT_PATHS,
    V2_IMPLEMENTATION_MANIFEST_PATH,
    V2_STATIC_RUNTIME_PATHS,
    validate_v2_execution_artifacts,
)
from src.evaluation.extension_runner import blind_review_rows_for_methods
from src.evaluation.extension_runner_v2 import summarize_v2_method


ROOT = Path(__file__).resolve().parents[1]


def synthetic_v2_result(
    *,
    expected_behavior: str = "answer",
    actual_decision: str = "pass",
    supported: int = 2,
    unsupported: int = 1,
    retained: int = 2,
    leaked: int = 0,
    cold_start: bool = False,
) -> dict:
    return {
        "question_id": "Q1",
        "expected_behavior": expected_behavior,
        "actual_decision": actual_decision,
        "decision_correct": (
            actual_decision == "refuse"
            if expected_behavior == "refuse"
            else actual_decision in {"pass", "partial_pass"}
        ),
        "generated_claim_count": supported + unsupported,
        "supported_claim_count": supported,
        "unsupported_claim_count": unsupported,
        "supported_claim_retained_count": retained,
        "unsupported_claim_leakage_count": leaked,
        "cited_claim_count": supported + unsupported,
        "citation_valid_claim_count": supported + unsupported,
        "structured_output_success": True,
        "fallback_used": False,
        "cold_start": cold_start,
        "end_to_end_latency_ms": 100.0,
        "retrieval_latency_ms": 2.0,
        "generation_latency_ms": 90.0,
        "evidence_packing_latency_ms": 3.0,
        "verification_latency_ms": 1.0,
        "retry_latency_ms": 0.0,
        "generation_attempts": 1,
    }


def test_v1_release_artifacts_remain_byte_stable() -> None:
    assert sha256_file(ROOT / RELEASE_RECORD_PATH) == (
        "af4f8ac10c247483af20e93f5fdde5220b608fb8c9dfb8c031d777d8b1932d0c"
    )
    assert sha256_file(ROOT / IMPLEMENTATION_MANIFEST_PATH) == (
        "2f6e0b06c66d66d6efcc020d8ea7b291ba4ec92e6a1e4b9c575d06f3b2676382"
    )


def test_v2_paths_are_versioned_and_do_not_overlap_v1() -> None:
    assert V2_IMPLEMENTATION_MANIFEST_PATH != IMPLEMENTATION_MANIFEST_PATH
    assert V2_EXECUTION_STATE_PATH.as_posix().startswith("reports/extension_v2/")
    assert V2_EXECUTION_RECEIPT_PATH.as_posix().startswith("reports/extension_v2/")
    assert all(
        path.as_posix().startswith("reports/extension_v2/")
        for path in V2_FINAL_OUTPUT_PATHS.values()
    )
    assert Path("scripts/run_extension_evaluation_v2.py") in V2_STATIC_RUNTIME_PATHS
    assert Path("config/extension_evaluation_v2.yaml") in V2_STATIC_RUNTIME_PATHS


def test_v2_method_matrix_maps_to_expected_workflow_policies(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_build(root, **kwargs):
        calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(extension_runner_v2, "build_default_workflow", fake_build)
    workflows = {
        method_id: extension_runner_v2.build_v2_method_workflow(ROOT, method_id)
        for method_id in V2_METHOD_ORDER
    }

    assert workflows["rule_baseline"]["generator_backend"] == "offline_rule"
    assert workflows["llm_strict_v2"]["verifier_policy"] == "strict"
    assert workflows["llm_no_verifier_v2"]["generator_backend"] == "llm"
    assert workflows["llm_no_verifier_v2"]["verifier"].max_retries == 0
    assert workflows["llm_partial_pass_v2"]["verifier_policy"] == "partial_pass"
    assert len(calls) == 4


def test_v2_metrics_preserve_claim_numerators_and_denominators() -> None:
    metrics = summarize_v2_method(
        "llm_partial_pass_v2",
        [
            synthetic_v2_result(actual_decision="partial_pass"),
            synthetic_v2_result(
                expected_behavior="refuse",
                actual_decision="refuse",
                supported=0,
                unsupported=1,
                retained=0,
            ),
        ],
    )

    assert metrics["decision_accuracy"]["value"] == 1.0
    assert metrics["refusal_accuracy"]["value"] == 1.0
    assert metrics["partial_pass_rate"]["value"] == 1.0
    assert metrics["supported_claim_retention_rate"] == {
        "status": "computed",
        "value": 1.0,
        "numerator": 2,
        "denominator": 2,
        "note": "",
    }
    assert metrics["unsupported_claim_leakage_rate"]["value"] == 0.0


def test_v2_blind_review_uses_four_labels_without_method_identity() -> None:
    reports = {
        method_id: {
            "results": [
                {
                    "question_id": "Q1",
                    "question": "question",
                    "answer": "answer",
                    "retrieval": {"text_evidence": []},
                }
            ]
        }
        for method_id in V2_METHOD_ORDER
    }

    rows, key = blind_review_rows_for_methods(
        reports,
        method_order=V2_METHOD_ORDER,
        answer_labels=("A", "B", "C", "D"),
        seed=42,
    )

    assert len(rows) == 4
    assert {row["answer_label"] for row in rows} == {"A", "B", "C", "D"}
    assert all("method_id" not in row for row in rows)
    assert {row["method_id"] for row in key} == set(V2_METHOD_ORDER)


def test_v2_execution_validator_rejects_outputs_without_state(tmp_path: Path) -> None:
    release = {"release_id": "extension-test-v2", "status": "authorized_not_executed"}
    errors, status = validate_v2_execution_artifacts(tmp_path, release)
    assert errors == []
    assert status == "authorized_not_executed"

    stray = tmp_path / next(iter(V2_FINAL_OUTPUT_PATHS.values()))
    stray.parent.mkdir(parents=True)
    stray.write_text("{}", encoding="utf-8")
    errors, status = validate_v2_execution_artifacts(tmp_path, release)
    assert status == "invalid"
    assert any("without an execution state" in error for error in errors)
