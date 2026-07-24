from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import DATASET_PATH, V2_METHOD_ORDER, read_json
from src.evaluation.extension_release_v2 import (
    V2_EXECUTION_RECEIPT_PATH,
    V2_EXECUTION_STATE_PATH,
    V2_FINAL_OUTPUT_PATHS,
    load_v2_release_artifacts,
    validate_v2_execution_artifacts,
    validate_v2_release_record,
)
from src.evaluation.extension_runner_v2 import summarize_v2_method


BLIND_COLUMNS = {
    "review_item_id",
    "question_id",
    "answer_label",
    "question",
    "answer",
    "retrieved_evidence_json",
    "answer_correctness",
    "evidence_faithfulness",
    "hallucination",
    "over_refusal",
    "readability",
    "review_notes",
}
FORBIDDEN_PERSISTED_KEYS = {
    "raw_prompt",
    "raw_prompt_content",
    "raw_model_thinking",
    "thinking",
    "system_prompt",
}


def read_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def find_forbidden_keys(value: Any, *, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        errors: list[str] = []
        for key, nested in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_PERSISTED_KEYS:
                errors.append(child_path)
            errors.extend(find_forbidden_keys(nested, path=child_path))
        return errors
    if isinstance(value, list):
        return [
            item_error
            for index, item in enumerate(value)
            for item_error in find_forbidden_keys(item, path=f"{path}[{index}]")
        ]
    return []


def validate_blind_review(
    root: Path,
    *,
    release: dict[str, Any],
    question_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    review_path = root / V2_FINAL_OUTPUT_PATHS["blind_review"]
    key_path = root / V2_FINAL_OUTPUT_PATHS["blind_method_key"]
    try:
        with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        key_payload = read_json(key_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"unable to read v2 blind-review artifacts: {exc}"]

    if not rows:
        errors.append("v2 blind review is empty")
        return errors
    if set(rows[0]) != BLIND_COLUMNS:
        errors.append("v2 blind review column set mismatch")
    if any("method_id" in row for row in rows):
        errors.append("v2 blind review exposes method identity")
    if any(any(field.startswith("expected") for field in row) for row in rows):
        errors.append("v2 blind review exposes expected-answer fields")
    expected_row_count = len(question_ids) * len(V2_METHOD_ORDER)
    if len(rows) != expected_row_count:
        errors.append("v2 blind review row count mismatch")

    labels = {"A", "B", "C", "D"}
    if {row["answer_label"] for row in rows} != labels:
        errors.append("v2 blind review labels must be A/B/C/D")
    by_question: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_question.setdefault(row["question_id"], []).append(row)
    if list(by_question) != question_ids:
        errors.append("v2 blind review question order differs from the frozen dataset")
    for question_id in question_ids:
        question_rows = by_question.get(question_id, [])
        if len(question_rows) != len(V2_METHOD_ORDER):
            errors.append(f"v2 blind review count mismatch for {question_id}")
            continue
        if {row["answer_label"] for row in question_rows} != labels:
            errors.append(f"v2 blind review labels mismatch for {question_id}")

    if key_payload.get("artifact") != "extension_blind_method_key":
        errors.append("v2 blind method key artifact mismatch")
    if key_payload.get("protocol_version") != "v2":
        errors.append("v2 blind method key protocol mismatch")
    if key_payload.get("release_id") != release.get("release_id"):
        errors.append("v2 blind method key release ID mismatch")
    key_rows = key_payload.get("rows")
    if not isinstance(key_rows, list) or len(key_rows) != len(rows):
        errors.append("v2 blind method key row count mismatch")
        return errors
    visible_ids = {row["review_item_id"] for row in rows}
    key_ids = {row.get("review_item_id") for row in key_rows if isinstance(row, dict)}
    if key_ids != visible_ids:
        errors.append("v2 blind method key IDs do not match visible review rows")
    if {
        row.get("method_id") for row in key_rows if isinstance(row, dict)
    } != set(V2_METHOD_ORDER):
        errors.append("v2 blind method key method set mismatch")
    return errors


def validate_results(root: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        implementation, release = load_v2_release_artifacts(root)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return [f"unable to load v2 release artifacts: {exc}"], {}

    errors.extend(
        validate_v2_release_record(
            root,
            release,
            implementation,
            check_runtime_model=False,
            require_unexecuted=False,
        )
    )
    execution_errors, execution_status = validate_v2_execution_artifacts(root, release)
    errors.extend(execution_errors)
    if execution_status != "completed_once":
        errors.append(
            f"v2 extension must be completed_once for result audit, got {execution_status}"
        )

    questions = read_questions(root / DATASET_PATH)
    question_ids = [item["question_id"] for item in questions]
    reports: dict[str, dict[str, Any]] = {}
    for method_id in V2_METHOD_ORDER:
        path = root / V2_FINAL_OUTPUT_PATHS[method_id]
        try:
            report = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid v2 method report {method_id}: {exc}")
            continue
        reports[method_id] = report
        if report.get("artifact") != "extension_method_report":
            errors.append(f"v2 method report artifact mismatch: {method_id}")
        if report.get("protocol_version") != "v2":
            errors.append(f"v2 method report protocol mismatch: {method_id}")
        if report.get("release_id") != release.get("release_id"):
            errors.append(f"v2 method report release ID mismatch: {method_id}")
        if report.get("method_id") != method_id:
            errors.append(f"v2 method report method ID mismatch: {method_id}")
        results = report.get("results")
        if not isinstance(results, list) or len(results) != len(question_ids):
            errors.append(f"v2 method result count mismatch: {method_id}")
            continue
        if [row.get("question_id") for row in results] != question_ids:
            errors.append(f"v2 method question order mismatch: {method_id}")
        if report.get("metrics") != summarize_v2_method(method_id, results):
            errors.append(f"v2 method metrics do not recompute: {method_id}")
        forbidden = find_forbidden_keys(report)
        if forbidden:
            errors.append(
                f"v2 method report persists forbidden model fields: {method_id}: "
                + ", ".join(forbidden[:3])
            )

    combined_path = root / V2_FINAL_OUTPUT_PATHS["combined_metrics"]
    try:
        combined = read_json(combined_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid v2 combined metrics: {exc}")
        combined = {}
    else:
        if combined.get("artifact") != "extension_combined_metrics":
            errors.append("v2 combined metrics artifact mismatch")
        if combined.get("protocol_version") != "v2":
            errors.append("v2 combined metrics protocol mismatch")
        if combined.get("release_id") != release.get("release_id"):
            errors.append("v2 combined metrics release ID mismatch")
        if combined.get("method_order") != list(V2_METHOD_ORDER):
            errors.append("v2 combined metrics method order mismatch")
        expected_metrics = {
            method_id: reports[method_id].get("metrics")
            for method_id in V2_METHOD_ORDER
            if method_id in reports
        }
        if combined.get("metrics") != expected_metrics:
            errors.append("v2 combined metrics do not match method reports")

    errors.extend(
        validate_blind_review(root, release=release, question_ids=question_ids)
    )
    try:
        state = read_json(root / V2_EXECUTION_STATE_PATH)
        receipt = read_json(root / V2_EXECUTION_RECEIPT_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"unable to read v2 state or receipt: {exc}")
        state = {}
        receipt = {}
    if state.get("status") != "completed":
        errors.append("v2 execution state is not completed")
    if state.get("release_id") != release.get("release_id"):
        errors.append("v2 execution state release ID mismatch")
    state_results = state.get("results", {})
    if not isinstance(state_results, dict) or {
        key: len(value) if isinstance(value, list) else None
        for key, value in state_results.items()
    } != {method_id: len(question_ids) for method_id in V2_METHOD_ORDER}:
        errors.append("v2 execution state result counts mismatch")
    if receipt.get("qa_invocation_count") != len(question_ids) * len(V2_METHOD_ORDER):
        errors.append("v2 receipt QA invocation count mismatch")

    summary = {
        "release_id": release.get("release_id"),
        "execution_status": execution_status,
        "question_count_per_method": len(question_ids),
        "qa_invocation_count": receipt.get("qa_invocation_count"),
        "method_metrics": {
            method_id: reports[method_id]["metrics"] for method_id in V2_METHOD_ORDER
            if method_id in reports
        },
    }
    return errors, summary


def main() -> int:
    errors, summary = validate_results(PROJECT_ROOT)
    if errors:
        print("ERROR: v2 extension result validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: v2 extension results are internally consistent")
    print(f"OK: release_id={summary['release_id']}")
    print(f"OK: execution_status={summary['execution_status']}")
    print(f"OK: question_count_per_method={summary['question_count_per_method']}")
    print(f"OK: qa_invocation_count={summary['qa_invocation_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
