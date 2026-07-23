from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import (
    DATASET_PATH,
    EXECUTION_RECEIPT_PATH,
    EXECUTION_STATE_PATH,
    FINAL_OUTPUT_PATHS,
    METHOD_ORDER,
    load_release_artifacts,
    sha256_file,
    validate_execution_artifacts,
    validate_release_record,
    write_new_json,
)
from src.evaluation.extension_runner import (
    blind_review_rows,
    build_method_workflow,
    build_shadow_verifier,
    evaluate_extension_question,
    method_report,
    read_questions,
    unload_ollama_model,
    utc_now,
    write_blind_review,
    write_json_atomic,
)


def validate_preflight(*, require_unexecuted: bool) -> tuple[dict, dict, str]:
    try:
        implementation, release = load_release_artifacts(PROJECT_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    errors = validate_release_record(
        PROJECT_ROOT,
        release,
        implementation,
        check_runtime_model=True,
        require_unexecuted=require_unexecuted,
    )
    graph_override = os.environ.get("GRAPH_BACKEND", "networkx").lower()
    if graph_override != "networkx":
        errors.append("controlled extension execution requires GRAPH_BACKEND=networkx")
    model_override = os.environ.get("OLLAMA_MODEL")
    frozen_model = release["runtime_model"]["model"]
    if model_override and model_override != frozen_model:
        errors.append("OLLAMA_MODEL differs from the released model")
    execution_errors, execution_status = validate_execution_artifacts(
        PROJECT_ROOT,
        release,
    )
    errors.extend(execution_errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    return implementation, release, execution_status


def execute_once(release: dict) -> None:
    questions = read_questions(PROJECT_ROOT / DATASET_PATH)
    if len(questions) != 23:
        raise RuntimeError(f"released extension dataset must contain 23 questions, got {len(questions)}")

    started_at = utc_now()
    state = {
        "schema_version": "1.0",
        "artifact": "extension_execution_state",
        "release_id": release["release_id"],
        "status": "in_progress",
        "started_at": started_at,
        "current_item": None,
        "results": {method_id: [] for method_id in METHOD_ORDER},
    }
    write_new_json(PROJECT_ROOT / EXECUTION_STATE_PATH, state)
    reports: dict[str, dict] = {}
    shadow_verifier = build_shadow_verifier(PROJECT_ROOT)
    cold_start_pending = True
    try:
        for method_id in METHOD_ORDER:
            if method_id == "llm_generator" and cold_start_pending:
                unload_ollama_model(
                    release["runtime_model"]["base_url"],
                    release["runtime_model"]["model"],
                )
            workflow = build_method_workflow(PROJECT_ROOT, method_id)
            method_started_at = utc_now()
            for index, item in enumerate(questions, start=1):
                is_cold = method_id == "llm_generator" and cold_start_pending
                state["current_item"] = {
                    "method_id": method_id,
                    "question_id": item["question_id"],
                }
                write_json_atomic(PROJECT_ROOT / EXECUTION_STATE_PATH, state)
                result = evaluate_extension_question(
                    workflow,
                    shadow_verifier,
                    item,
                    cold_start=is_cold,
                )
                state["results"][method_id].append(result)
                state["current_item"] = None
                if is_cold:
                    cold_start_pending = False
                write_json_atomic(PROJECT_ROOT / EXECUTION_STATE_PATH, state)
                print(
                    f"[{method_id} {index:02d}/{len(questions):02d}] "
                    f"{item['question_id']} expected={result['expected_decision']} "
                    f"actual={result['actual_decision']}"
                )
            report = method_report(
                method_id,
                state["results"][method_id],
                release=release,
                started_at=method_started_at,
                completed_at=utc_now(),
            )
            write_new_json(PROJECT_ROOT / FINAL_OUTPUT_PATHS[method_id], report)
            reports[method_id] = report

        combined = {
            "schema_version": "1.0",
            "artifact": "extension_combined_metrics",
            "release_id": release["release_id"],
            "dataset_sha256": release["dataset_sha256"],
            "method_order": list(METHOD_ORDER),
            "metrics": {
                method_id: reports[method_id]["metrics"] for method_id in METHOD_ORDER
            },
            "human_metrics_status": "pending_user_confirmed_single_review",
            "claim_scope": "descriptive_only_due_to_small_sample",
        }
        write_new_json(PROJECT_ROOT / FINAL_OUTPUT_PATHS["combined_metrics"], combined)
        review_rows, method_key = blind_review_rows(
            reports,
            seed=release["randomization_seed"],
        )
        write_blind_review(PROJECT_ROOT / FINAL_OUTPUT_PATHS["blind_review"], review_rows)
        write_new_json(
            PROJECT_ROOT / FINAL_OUTPUT_PATHS["blind_method_key"],
            {
                "schema_version": "1.0",
                "artifact": "extension_blind_method_key",
                "release_id": release["release_id"],
                "rows": method_key,
            },
        )

        completed_at = utc_now()
        state.update(
            {
                "status": "completed",
                "completed_at": completed_at,
                "current_item": None,
            }
        )
        write_json_atomic(PROJECT_ROOT / EXECUTION_STATE_PATH, state)
        output_hashes = {
            key: {
                "path": path.as_posix(),
                "sha256": sha256_file(PROJECT_ROOT / path),
            }
            for key, path in FINAL_OUTPUT_PATHS.items()
        }
        receipt = {
            "schema_version": "1.0",
            "artifact": "extension_execution_receipt",
            "release_id": release["release_id"],
            "status": "completed_once",
            "started_at": started_at,
            "completed_at": completed_at,
            "method_order": list(METHOD_ORDER),
            "question_count_per_method": len(questions),
            "qa_invocation_count": len(questions) * len(METHOD_ORDER),
            "execution_state_sha256": sha256_file(PROJECT_ROOT / EXECUTION_STATE_PATH),
            "output_hashes": output_hashes,
            "final_result_policy": "v1.0_final_read_only_unchanged",
        }
        write_new_json(PROJECT_ROOT / EXECUTION_RECEIPT_PATH, receipt)
        print(f"OK: extension completed once release_id={release['release_id']}")
        print(f"OK: receipt={EXECUTION_RECEIPT_PATH.as_posix()}")
    except BaseException as exc:
        state.update(
            {
                "status": "failed_requires_manual_audit",
                "failed_at": utc_now(),
                "error_type": type(exc).__name__,
            }
        )
        write_json_atomic(PROJECT_ROOT / EXECUTION_STATE_PATH, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled one-time extension evaluation")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--release-id")
    parser.add_argument("--confirm-one-time-run", action="store_true")
    args = parser.parse_args()

    _, release, execution_status = validate_preflight(
        require_unexecuted=args.execute_once
    )
    if args.preflight:
        print(f"OK: release_id={release['release_id']}")
        print(f"OK: effective_execution_status={execution_status}")
        print("OK: preflight only; extension questions were not sent to the QA workflow")
        return
    if args.release_id != release["release_id"]:
        raise SystemExit("--release-id must exactly match the frozen release record.")
    if not args.confirm_one_time_run:
        raise SystemExit("Refusing extension execution without --confirm-one-time-run.")
    execute_once(release)


if __name__ == "__main__":
    main()
