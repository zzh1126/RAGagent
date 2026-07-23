from __future__ import annotations

import csv
import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

from src.agent.workflow import build_default_workflow
from src.evaluation.extension_release import METHOD_ORDER
from src.evaluation.workflow_factory import NoVerifier
from src.verification.evidence_verifier import EvidenceVerifier


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_method_workflow(root: Path, method_id: str):
    if method_id not in METHOD_ORDER:
        raise ValueError(f"unknown extension method: {method_id}")
    if method_id == "rule_baseline":
        return build_default_workflow(root, generator_backend="offline_rule")
    verifier = NoVerifier() if method_id == "llm_generator_no_verifier" else None
    return build_default_workflow(
        root,
        verifier=verifier,
        generator_backend="llm",
    )


def build_shadow_verifier(root: Path) -> EvidenceVerifier:
    settings = yaml.safe_load((root / "config/settings.yaml").read_text(encoding="utf-8"))
    verification = settings.get("verification", {})
    return EvidenceVerifier(
        pass_threshold=float(verification.get("pass_threshold", 0.80)),
        retry_threshold=float(verification.get("retry_threshold", 0.55)),
        max_retries=0,
        min_vector_score=float(verification.get("min_vector_score", 0.08)),
    )


def evaluate_extension_question(
    workflow,
    shadow_verifier: EvidenceVerifier,
    item: dict,
    *,
    cold_start: bool = False,
) -> dict:
    response = workflow.invoke(item["question"])
    if response.verification.decision not in {"pass", "refuse"}:
        raise RuntimeError(
            f"non-final workflow decision for {item['question_id']}: "
            f"{response.verification.decision}"
        )
    shadow = shadow_verifier.verify(
        item["question"],
        response.answer_payload,
        response.retrieval,
        graph_repo=workflow.graph_repo,
        retry_count=shadow_verifier.max_retries,
    )
    trace = response.generation_trace
    packing_trace = response.evidence_packing_trace
    llm_calls = [call for call in trace if call.requested_backend == "ollama"]
    expected_decision = "refuse" if item["expected_behavior"] == "refuse" else "pass"
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "question": item["question"],
        "expected_behavior": item["expected_behavior"],
        "expected_decision": expected_decision,
        "actual_decision": response.verification.decision,
        "decision_correct": response.verification.decision == expected_decision,
        "required_aspects": item["required_aspects"],
        "forbidden_claims": item["forbidden_claims"],
        "answer": response.answer,
        "answer_payload": response.answer_payload.model_dump(mode="json"),
        "retrieval": response.retrieval.model_dump(mode="json"),
        "verification": response.verification.model_dump(mode="json"),
        "shadow_verification": shadow.model_dump(mode="json"),
        "generation_trace": [call.model_dump(mode="json") for call in trace],
        "evidence_packing_trace": [
            item.model_dump(mode="json") for item in packing_trace
        ],
        "route_trace": (
            response.route_trace.model_dump(mode="json")
            if response.route_trace is not None
            else None
        ),
        "retrieval_trace": [
            call.model_dump(mode="json") for call in response.retrieval_trace
        ],
        "verification_trace": [
            call.model_dump(mode="json") for call in response.verification_trace
        ],
        "latency_trace": response.latency_trace.model_dump(mode="json"),
        "generation_call_count": len(trace),
        "generation_attempts": sum(call.attempts for call in trace),
        "generation_latency_ms": round(sum(call.latency_ms for call in trace), 1),
        "evidence_packing_latency_ms": round(
            sum(item.evidence_packing_latency_ms for item in packing_trace),
            3,
        ),
        "structured_output_success": (
            bool(llm_calls) and all(call.structured_output_success for call in llm_calls)
        ),
        "fallback_used": any(call.fallback_used for call in trace),
        "fallback_reasons": list(
            dict.fromkeys(call.fallback_reason for call in trace if call.fallback_reason)
        ),
        "cold_start": cold_start,
        "latency_ms": response.latency_ms,
        "retrieval_latency_ms": response.latency_trace.retrieval_latency_ms,
        "verification_latency_ms": response.latency_trace.verification_latency_ms,
        "retry_latency_ms": response.latency_trace.retry_latency_ms,
        "end_to_end_latency_ms": (
            response.latency_trace.end_to_end_latency_ms
            or float(response.latency_ms)
        ),
        "cache_status": response.cache_status,
        "retry_count": response.retry_count,
    }


def computed_metric(numerator: float, denominator: int, *, note: str = "") -> dict:
    if denominator <= 0:
        return {"status": "not_applicable", "value": None, "note": note}
    return {
        "status": "computed",
        "value": round(numerator / denominator, 4),
        "numerator": numerator,
        "denominator": denominator,
        "note": note,
    }


def scalar_metric(value: float | None, *, note: str = "") -> dict:
    if value is None:
        return {"status": "not_applicable", "value": None, "note": note}
    return {"status": "computed", "value": round(value, 2), "note": note}


def summarize_method(method_id: str, results: list[dict]) -> dict:
    answerable = [row for row in results if row["expected_behavior"] == "answer"]
    refusals = [row for row in results if row["expected_behavior"] == "refuse"]
    citation_rows = [row for row in results if row["answer_payload"]["claims"]]
    is_llm = method_id != "rule_baseline"
    cold_rows = [row for row in results if row["cold_start"]]
    warm_rows = [row for row in results if is_llm and not row["cold_start"]]
    packing_rows = [row for row in results if "evidence_packing_latency_ms" in row]
    total_attempts = sum(row["generation_attempts"] for row in results)
    return {
        "decision_accuracy": computed_metric(
            sum(row["decision_correct"] for row in results), len(results)
        ),
        "refusal_accuracy": computed_metric(
            sum(row["actual_decision"] == "refuse" for row in refusals),
            len(refusals),
        ),
        "over_refusal_rate": computed_metric(
            sum(row["actual_decision"] == "refuse" for row in answerable),
            len(answerable),
        ),
        "citation_validity": computed_metric(
            sum(row["shadow_verification"]["citation_validity"] for row in citation_rows),
            len(citation_rows),
            note="standard verifier measured without changing the method decision",
        ),
        "structured_output_success_rate": (
            computed_metric(
                sum(row["structured_output_success"] for row in results), len(results)
            )
            if is_llm
            else computed_metric(0, 0, note="offline rule generator")
        ),
        "fallback_rate": (
            computed_metric(sum(row["fallback_used"] for row in results), len(results))
            if is_llm
            else computed_metric(0, 0, note="offline rule generator")
        ),
        "cold_start_latency_ms": scalar_metric(
            float(cold_rows[0]["latency_ms"]) if cold_rows else None,
            note="first LLM question after explicit model unload",
        ),
        "warm_end_to_end_latency_ms": scalar_metric(
            (
                sum(row["latency_ms"] for row in warm_rows) / len(warm_rows)
                if warm_rows
                else None
            ),
            note="mean question latency excluding the one cold-start question",
        ),
        "mean_end_to_end_latency_ms": scalar_metric(
            sum(row["latency_ms"] for row in results) / len(results) if results else None
        ),
        "mean_generation_latency_ms": scalar_metric(
            (
                sum(row["generation_latency_ms"] for row in results) / len(results)
                if results
                else None
            )
        ),
        "mean_evidence_packing_latency_ms": scalar_metric(
            (
                sum(row["evidence_packing_latency_ms"] for row in packing_rows)
                / len(packing_rows)
                if is_llm and packing_rows
                else None
            ),
            note="LLM evidence packing only",
        ),
        "generation_attempts_total": total_attempts,
        "question_count": len(results),
    }


def method_report(
    method_id: str,
    results: list[dict],
    *,
    release: dict,
    started_at: str,
    completed_at: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "artifact": "extension_method_report",
        "release_id": release["release_id"],
        "method_id": method_id,
        "dataset_sha256": release["dataset_sha256"],
        "runtime_bundle_sha256": release["runtime_bundle_sha256"],
        "prompt_contract": release["prompt_contract"],
        "runtime_model": release["runtime_model"] if method_id != "rule_baseline" else None,
        "started_at": started_at,
        "completed_at": completed_at,
        "metrics": summarize_method(method_id, results),
        "results": results,
    }


def blind_review_rows(
    reports: dict[str, dict],
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_method = {method_id: report["results"] for method_id, report in reports.items()}
    question_count = len(next(iter(by_method.values())))
    review_rows: list[dict[str, Any]] = []
    method_key: list[dict[str, str]] = []
    for index in range(question_count):
        question_id = by_method[METHOD_ORDER[0]][index]["question_id"]
        question_seed = int.from_bytes(
            hashlib.sha256(f"{seed}:{question_id}".encode("utf-8")).digest()[:8],
            "big",
        )
        shuffled_methods = list(METHOD_ORDER)
        random.Random(question_seed).shuffle(shuffled_methods)
        for label, method_id in zip(("A", "B", "C"), shuffled_methods, strict=True):
            result = by_method[method_id][index]
            if result["question_id"] != question_id:
                raise ValueError("method reports do not use identical question order")
            review_item_id = f"{question_id}-{label}"
            evidence = [
                {
                    "evidence_id": item["evidence_id"],
                    "chunk_id": item["chunk_id"],
                    "page_title": item["page_title"],
                    "heading_path": item["heading_path"],
                    "url": item["url"],
                    "display_text": item["display_text"],
                }
                for item in result["retrieval"]["text_evidence"]
            ]
            review_rows.append(
                {
                    "review_item_id": review_item_id,
                    "question_id": question_id,
                    "answer_label": label,
                    "question": result["question"],
                    "answer": result["answer"],
                    "retrieved_evidence_json": json.dumps(evidence, ensure_ascii=False),
                    "answer_correctness": "",
                    "evidence_faithfulness": "",
                    "hallucination": "",
                    "over_refusal": "",
                    "readability": "",
                    "review_notes": "",
                }
            )
            method_key.append(
                {
                    "review_item_id": review_item_id,
                    "question_id": question_id,
                    "answer_label": label,
                    "method_id": method_id,
                }
            )
    return review_rows, method_key


def write_blind_review(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("blind review output cannot be empty")
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def unload_ollama_model(base_url: str, model: str, timeout_seconds: float = 30.0) -> None:
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("failed to unload the Ollama model before the cold run") from exc
