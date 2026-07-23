from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import (
    DATASET_PATH,
    V2_METHOD_ORDER,
    sha256_file,
    write_new_json,
)
from src.evaluation.extension_release_v2 import (
    V2_EXECUTION_RECEIPT_PATH,
    V2_EXECUTION_STATE_PATH,
    V2_FINAL_OUTPUT_PATHS,
    load_v2_release_artifacts,
    validate_v2_effective_release_status,
    validate_v2_release_record,
)
from src.evaluation.extension_runner import (
    blind_review_rows_for_methods,
    read_questions,
    unload_ollama_model,
    utc_now,
    write_blind_review,
    write_json_atomic,
)
from src.evaluation.extension_runner_v2 import (
    build_v2_method_workflow,
    build_v2_shadow_verifier,
    evaluate_v2_extension_question,
    v2_method_report,
)


def validate_preflight(
    *,
    require_unexecuted: bool,
    requested_release_id: str | None = None,
) -> tuple[dict, dict, str]:
    try:
        implementation, release = load_v2_release_artifacts(PROJECT_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if requested_release_id and requested_release_id != release.get("release_id"):
        raise SystemExit("--release-id must exactly match the authorized v2 release record.")

    status_errors, execution_status = validate_v2_effective_release_status(
        PROJECT_ROOT,
        release,
    )
    errors = validate_v2_release_record(
        PROJECT_ROOT,
        release,
        implementation,
        check_runtime_model=True,
        require_unexecuted=require_unexecuted,
    )
    graph_override = os.environ.get("GRAPH_BACKEND", "networkx").lower()
    if graph_override != "networkx":
        errors.append("controlled v2 extension execution requires GRAPH_BACKEND=networkx")
    model_override = os.environ.get("OLLAMA_MODEL")
    frozen_model = release["runtime_model"]["model"]
    if model_override and model_override != frozen_model:
        errors.append("OLLAMA_MODEL differs from the v2 released model")
    errors.extend(status_errors)
    if execution_status != "authorized_not_executed":
        errors.append(
            "v2 extension execution is not available from status: "
            f"{execution_status}"
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    return implementation, release, execution_status


def execute_once(release: dict) -> None:
    questions = read_questions(PROJECT_ROOT / DATASET_PATH)
    if len(questions) != 23:
        raise RuntimeError(
            f"released v2 extension dataset must contain 23 questions, got {len(questions)}"
        )

    started_at = utc_now()
    state = {
        "schema_version": "2.0",
        "artifact": "extension_execution_state",
        "protocol_version": "v2",
        "release_id": release["release_id"],
        "status": "in_progress",
        "started_at": started_at,
        "current_item": None,
        "results": {method_id: [] for method_id in V2_METHOD_ORDER},
    }
    write_new_json(PROJECT_ROOT / V2_EXECUTION_STATE_PATH, state)
    reports: dict[str, dict] = {}
    shadow_verifier = build_v2_shadow_verifier(PROJECT_ROOT)
    cold_start_pending = True
    try:
        for method_id in V2_METHOD_ORDER:
            if method_id == "llm_strict_v2" and cold_start_pending:
                unload_ollama_model(
                    release["runtime_model"]["base_url"],
                    release["runtime_model"]["model"],
                )
            workflow = build_v2_method_workflow(PROJECT_ROOT, method_id)
            method_started_at = utc_now()
            for index, item in enumerate(questions, start=1):
                is_cold = method_id == "llm_strict_v2" and cold_start_pending
                state["current_item"] = {
                    "method_id": method_id,
                    "question_id": item["question_id"],
                }
                write_json_atomic(PROJECT_ROOT / V2_EXECUTION_STATE_PATH, state)
                result = evaluate_v2_extension_question(
                    workflow,
                    shadow_verifier,
                    item,
                    method_id=method_id,
                    cold_start=is_cold,
                )
                state["results"][method_id].append(result)
                state["current_item"] = None
                if is_cold:
                    cold_start_pending = False
                write_json_atomic(PROJECT_ROOT / V2_EXECUTION_STATE_PATH, state)
                print(
                    f"[{method_id} {index:02d}/{len(questions):02d}] "
                    f"{item['question_id']} expected={result['expected_decision']} "
                    f"actual={result['actual_decision']}"
                )
            report = v2_method_report(
                method_id,
                state["results"][method_id],
                release=release,
                started_at=method_started_at,
                completed_at=utc_now(),
            )
            write_new_json(PROJECT_ROOT / V2_FINAL_OUTPUT_PATHS[method_id], report)
            reports[method_id] = report

        combined = {
            "schema_version": "2.0",
            "artifact": "extension_combined_metrics",
            "protocol_version": "v2",
            "release_id": release["release_id"],
            "dataset_sha256": release["dataset_sha256"],
            "method_order": list(V2_METHOD_ORDER),
            "metrics": {
                method_id: reports[method_id]["metrics"]
                for method_id in V2_METHOD_ORDER
            },
            "human_metrics_status": "pending_user_confirmed_single_review",
            "claim_scope": "descriptive_only_due_to_small_sample",
        }
        write_new_json(
            PROJECT_ROOT / V2_FINAL_OUTPUT_PATHS["combined_metrics"],
            combined,
        )
        review_rows, method_key = blind_review_rows_for_methods(
            reports,
            method_order=V2_METHOD_ORDER,
            answer_labels=("A", "B", "C", "D"),
            seed=release["randomization_seed"],
        )
        write_blind_review(
            PROJECT_ROOT / V2_FINAL_OUTPUT_PATHS["blind_review"],
            review_rows,
        )
        write_new_json(
            PROJECT_ROOT / V2_FINAL_OUTPUT_PATHS["blind_method_key"],
            {
                "schema_version": "2.0",
                "artifact": "extension_blind_method_key",
                "protocol_version": "v2",
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
        write_json_atomic(PROJECT_ROOT / V2_EXECUTION_STATE_PATH, state)
        output_hashes = {
            key: {
                "path": path.as_posix(),
                "sha256": sha256_file(PROJECT_ROOT / path),
            }
            for key, path in V2_FINAL_OUTPUT_PATHS.items()
        }
        receipt = {
            "schema_version": "2.0",
            "artifact": "extension_execution_receipt",
            "protocol_version": "v2",
            "release_id": release["release_id"],
            "status": "completed_once",
            "started_at": started_at,
            "completed_at": completed_at,
            "method_order": list(V2_METHOD_ORDER),
            "question_count_per_method": len(questions),
            "qa_invocation_count": len(questions) * len(V2_METHOD_ORDER),
            "execution_state_sha256": sha256_file(
                PROJECT_ROOT / V2_EXECUTION_STATE_PATH
            ),
            "output_hashes": output_hashes,
            "final_result_policy": "v2_final_read_only_after_execution",
        }
        write_new_json(PROJECT_ROOT / V2_EXECUTION_RECEIPT_PATH, receipt)
        print(f"OK: v2 extension completed once release_id={release['release_id']}")
        print(f"OK: receipt={V2_EXECUTION_RECEIPT_PATH.as_posix()}")
    except BaseException as exc:
        state.update(
            {
                "status": "failed_requires_manual_audit",
                "failed_at": utc_now(),
                "error_type": type(exc).__name__,
            }
        )
        write_json_atomic(PROJECT_ROOT / V2_EXECUTION_STATE_PATH, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Controlled one-time v2 extension evaluation"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--release-id")
    parser.add_argument("--confirm-one-time-run", action="store_true")
    args = parser.parse_args()

    _, release, execution_status = validate_preflight(
        require_unexecuted=args.execute_once,
        requested_release_id=args.release_id if args.execute_once else None,
    )
    if args.preflight:
        print(f"OK: release_id={release['release_id']}")
        print(f"OK: effective_execution_status={execution_status}")
        print("OK: preflight only; v2 extension questions were not sent to QA")
        return
    if args.release_id != release["release_id"]:
        raise SystemExit("--release-id must exactly match the frozen v2 release record.")
    if not args.confirm_one_time_run:
        raise SystemExit("Refusing v2 execution without --confirm-one-time-run.")
    execute_once(release)


if __name__ == "__main__":
    main()
