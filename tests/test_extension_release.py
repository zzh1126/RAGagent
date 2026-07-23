from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.extension_release import (
    EXECUTION_RECEIPT_PATH,
    EXECUTION_STATE_PATH,
    FINAL_OUTPUT_PATHS,
    METHOD_ORDER,
    TRACE_CONTRACT_PATH,
    runtime_paths,
    sha256_file,
    validate_execution_artifacts,
    validate_static_contracts,
    write_new_json,
)
from src.evaluation.extension_runner import blind_review_rows, summarize_method


ROOT = Path(__file__).resolve().parents[1]


def synthetic_result(
    *,
    question_id: str,
    expected_behavior: str,
    actual_decision: str,
    citation_validity: float = 1.0,
    structured: bool = True,
    fallback: bool = False,
    cold: bool = False,
    latency_ms: int = 20,
) -> dict:
    expected_decision = "refuse" if expected_behavior == "refuse" else "pass"
    return {
        "question_id": question_id,
        "question": f"question {question_id}",
        "expected_behavior": expected_behavior,
        "expected_decision": expected_decision,
        "actual_decision": actual_decision,
        "decision_correct": actual_decision == expected_decision,
        "answer": "answer [E1]",
        "answer_payload": {"claims": [{"claim": "fact", "evidence_ids": ["E1"]}]},
        "retrieval": {
            "text_evidence": [
                {
                    "evidence_id": "E1",
                    "chunk_id": "C1",
                    "page_title": "Page",
                    "heading_path": ["Heading"],
                    "url": "https://example.test",
                    "display_text": "Evidence text",
                }
            ]
        },
        "shadow_verification": {"citation_validity": citation_validity},
        "structured_output_success": structured,
        "fallback_used": fallback,
        "cold_start": cold,
        "latency_ms": latency_ms,
        "generation_latency_ms": float(latency_ms - 1),
        "generation_attempts": 1,
    }


def test_static_trace_contract_is_frozen_and_matches_scoring_methods() -> None:
    assert validate_static_contracts(ROOT) == []
    paths = runtime_paths(ROOT)
    assert TRACE_CONTRACT_PATH in paths
    assert Path("scripts/run_extension_evaluation.py") in paths
    assert list(METHOD_ORDER) == [
        "rule_baseline",
        "llm_generator",
        "llm_generator_no_verifier",
    ]


def test_llm_trace_metrics_use_frozen_denominators() -> None:
    results = [
        synthetic_result(
            question_id="Q1",
            expected_behavior="answer",
            actual_decision="pass",
            cold=True,
            latency_ms=100,
        ),
        synthetic_result(
            question_id="Q2",
            expected_behavior="answer",
            actual_decision="refuse",
            structured=False,
            fallback=True,
            latency_ms=20,
        ),
        synthetic_result(
            question_id="Q3",
            expected_behavior="refuse",
            actual_decision="refuse",
            citation_validity=0.5,
            latency_ms=30,
        ),
    ]

    metrics = summarize_method("llm_generator", results)

    assert metrics["decision_accuracy"]["value"] == 0.6667
    assert metrics["refusal_accuracy"]["value"] == 1.0
    assert metrics["over_refusal_rate"]["value"] == 0.5
    assert metrics["citation_validity"]["value"] == 0.8333
    assert metrics["structured_output_success_rate"]["value"] == 0.6667
    assert metrics["fallback_rate"]["value"] == 0.3333
    assert metrics["cold_start_latency_ms"]["value"] == 100.0
    assert metrics["warm_end_to_end_latency_ms"]["value"] == 25.0


def test_rule_trace_metrics_mark_llm_only_metrics_not_applicable() -> None:
    metrics = summarize_method(
        "rule_baseline",
        [
            synthetic_result(
                question_id="Q1",
                expected_behavior="answer",
                actual_decision="pass",
            )
        ],
    )

    assert metrics["structured_output_success_rate"]["status"] == "not_applicable"
    assert metrics["fallback_rate"]["status"] == "not_applicable"
    assert metrics["cold_start_latency_ms"]["status"] == "not_applicable"


def test_blind_review_is_deterministic_and_keeps_method_key_separate() -> None:
    reports = {
        method_id: {
            "results": [
                synthetic_result(
                    question_id="Q1",
                    expected_behavior="answer",
                    actual_decision="pass",
                )
            ]
        }
        for method_id in METHOD_ORDER
    }

    rows, key = blind_review_rows(reports, seed=12345)
    repeated_rows, repeated_key = blind_review_rows(reports, seed=12345)

    assert rows == repeated_rows
    assert key == repeated_key
    assert len(rows) == 3
    assert {row["answer_label"] for row in rows} == {"A", "B", "C"}
    assert all("method_id" not in row for row in rows)
    assert {row["method_id"] for row in key} == set(METHOD_ORDER)


def test_execution_artifact_validator_rejects_output_without_state(tmp_path: Path) -> None:
    release = {"release_id": "release-test"}
    errors, status = validate_execution_artifacts(tmp_path, release)
    assert errors == []
    assert status == "authorized_not_executed"

    stray_path = tmp_path / next(iter(FINAL_OUTPUT_PATHS.values()))
    stray_path.parent.mkdir(parents=True)
    stray_path.write_text("{}", encoding="utf-8")

    errors, status = validate_execution_artifacts(tmp_path, release)
    assert status == "invalid"
    assert any("without an execution state" in error for error in errors)


def test_release_json_writer_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "release.json"
    write_new_json(path, {"release_id": "one"})

    with pytest.raises(FileExistsError):
        write_new_json(path, {"release_id": "two"})


def test_completed_execution_requires_matching_receipt_hashes(tmp_path: Path) -> None:
    release = {"release_id": "release-test"}
    state_path = tmp_path / EXECUTION_STATE_PATH
    write_new_json(
        state_path,
        {
            "artifact": "extension_execution_state",
            "release_id": "release-test",
            "status": "completed",
        },
    )
    output_hashes = {}
    for key, relative in FINAL_OUTPUT_PATHS.items():
        path = tmp_path / relative
        write_new_json(path, {"artifact": key})
        output_hashes[key] = {"path": relative.as_posix(), "sha256": sha256_file(path)}
    write_new_json(
        tmp_path / EXECUTION_RECEIPT_PATH,
        {
            "artifact": "extension_execution_receipt",
            "release_id": "release-test",
            "status": "completed_once",
            "qa_invocation_count": 69,
            "execution_state_sha256": sha256_file(state_path),
            "output_hashes": output_hashes,
        },
    )

    errors, status = validate_execution_artifacts(tmp_path, release)
    assert errors == []
    assert status == "completed_once"

    (tmp_path / FINAL_OUTPUT_PATHS["combined_metrics"]).write_text(
        '{"tampered": true}', encoding="utf-8"
    )
    errors, status = validate_execution_artifacts(tmp_path, release)
    assert status == "invalid"
    assert any("combined_metrics" in error for error in errors)


def test_text_release_hashes_are_stable_across_windows_line_endings(tmp_path: Path) -> None:
    lf_path = tmp_path / "lf.py"
    crlf_path = tmp_path / "crlf.py"
    lf_path.write_bytes(b"line one\nline two\n")
    crlf_path.write_bytes(b"line one\r\nline two\r\n")

    assert sha256_file(lf_path) == sha256_file(crlf_path)
