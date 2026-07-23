from __future__ import annotations

from collections import Counter
from typing import Any

from src.agent.workflow import build_default_workflow
from src.evaluation.extension_release import V2_METHOD_ORDER
from src.evaluation.extension_runner import build_shadow_verifier
from src.evaluation.workflow_factory import NoVerifier
from src.verification.evidence_verifier import EvidenceVerifier


def build_v2_method_workflow(root, method_id: str):
    if method_id not in V2_METHOD_ORDER:
        raise ValueError(f"unknown v2 extension method: {method_id}")
    if method_id == "rule_baseline":
        return build_default_workflow(root, generator_backend="offline_rule")
    if method_id == "llm_strict_v2":
        return build_default_workflow(
            root,
            generator_backend="llm",
            verifier_policy="strict",
        )
    if method_id == "llm_no_verifier_v2":
        return build_default_workflow(
            root,
            generator_backend="llm",
            verifier=NoVerifier(),
        )
    return build_default_workflow(
        root,
        generator_backend="llm",
        verifier_policy="partial_pass",
    )


def build_v2_shadow_verifier(root) -> EvidenceVerifier:
    verifier = build_shadow_verifier(root)
    verifier.decision_policy = "partial_pass"
    return verifier


def _visible_claim_flags(claim_results, visible_claims) -> list[bool]:
    visible = Counter(claim.claim.strip() for claim in visible_claims)
    flags: list[bool] = []
    for result in claim_results:
        key = result.claim.strip()
        is_visible = visible[key] > 0
        flags.append(is_visible)
        if is_visible:
            visible[key] -= 1
    return flags


def evaluate_v2_extension_question(
    workflow,
    shadow_verifier: EvidenceVerifier,
    item: dict,
    *,
    method_id: str,
    cold_start: bool = False,
) -> dict[str, Any]:
    response = workflow.invoke(item["question"])
    if response.verification.decision not in {"pass", "partial_pass", "refuse"}:
        raise RuntimeError(
            f"non-final v2 workflow decision for {item['question_id']}: "
            f"{response.verification.decision}"
        )
    shadow = shadow_verifier.verify(
        item["question"],
        response.answer_payload,
        response.retrieval,
        graph_repo=workflow.graph_repo,
        retry_count=shadow_verifier.max_retries,
    )
    claim_verification = (
        shadow if method_id == "llm_no_verifier_v2" else response.verification
    )
    visible_flags = _visible_claim_flags(
        claim_verification.claim_results,
        response.answer_payload.claims,
    )
    supported_retained_count = sum(
        result.supported and visible
        for result, visible in zip(
            claim_verification.claim_results,
            visible_flags,
            strict=True,
        )
    )
    unsupported_leakage_count = sum(
        not result.supported and visible
        for result, visible in zip(
            claim_verification.claim_results,
            visible_flags,
            strict=True,
        )
    )
    cited_claim_count = 0
    citation_valid_claim_count = 0
    claim_trace: list[dict[str, Any]] = []
    for result, visible in zip(
        claim_verification.claim_results,
        visible_flags,
        strict=True,
    ):
        references = [*result.evidence_ids, *result.graph_path_ids]
        valid_references = [
            *result.valid_evidence_ids,
            *result.valid_graph_path_ids,
        ]
        if references:
            cited_claim_count += 1
            if len(valid_references) == len(references):
                citation_valid_claim_count += 1
        claim_trace.append(
            {
                "claim_id": result.claim_id,
                "supported": result.supported,
                "visible_in_final_answer": visible,
                "evidence_ids": list(result.evidence_ids),
                "valid_evidence_ids": list(result.valid_evidence_ids),
                "graph_path_ids": list(result.graph_path_ids),
                "valid_graph_path_ids": list(result.valid_graph_path_ids),
                "reason_codes": list(result.reason_codes),
            }
        )

    trace = response.generation_trace
    packing_trace = response.evidence_packing_trace
    llm_calls = [call for call in trace if call.requested_backend == "ollama"]
    expected_decision = "refuse" if item["expected_behavior"] == "refuse" else "pass"
    actual_decision = response.verification.decision
    decision_correct = (
        actual_decision == "refuse"
        if expected_decision == "refuse"
        else actual_decision in {"pass", "partial_pass"}
    )
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "question": item["question"],
        "expected_behavior": item["expected_behavior"],
        "expected_decision": expected_decision,
        "actual_decision": actual_decision,
        "decision_correct": decision_correct,
        "required_aspects": item["required_aspects"],
        "forbidden_claims": item["forbidden_claims"],
        "answer": response.answer,
        "answer_payload": response.answer_payload.model_dump(mode="json"),
        "retrieval": response.retrieval.model_dump(mode="json"),
        "verification": response.verification.model_dump(mode="json"),
        "shadow_verification": shadow.model_dump(mode="json"),
        "claim_verification_source": (
            "shadow_verifier"
            if method_id == "llm_no_verifier_v2"
            else "method_verifier"
        ),
        "claim_verification_trace": claim_trace,
        "generated_claim_count": len(claim_verification.claim_results),
        "supported_claim_count": sum(
            result.supported for result in claim_verification.claim_results
        ),
        "unsupported_claim_count": sum(
            not result.supported for result in claim_verification.claim_results
        ),
        "visible_claim_count": len(response.answer_payload.claims),
        "supported_claim_retained_count": supported_retained_count,
        "unsupported_claim_leakage_count": unsupported_leakage_count,
        "cited_claim_count": cited_claim_count,
        "citation_valid_claim_count": citation_valid_claim_count,
        "generation_trace": [call.model_dump(mode="json") for call in trace],
        "evidence_packing_trace": [
            packing.model_dump(mode="json") for packing in packing_trace
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
            sum(packing.evidence_packing_latency_ms for packing in packing_trace),
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


def summarize_v2_method(method_id: str, results: list[dict]) -> dict[str, Any]:
    answerable = [row for row in results if row["expected_behavior"] == "answer"]
    refusals = [row for row in results if row["expected_behavior"] == "refuse"]
    is_llm = method_id != "rule_baseline"
    cold_rows = [row for row in results if row["cold_start"]]
    warm_rows = [row for row in results if is_llm and not row["cold_start"]]
    generated_claim_count = sum(row["generated_claim_count"] for row in results)
    supported_claim_count = sum(row["supported_claim_count"] for row in results)
    unsupported_claim_count = sum(row["unsupported_claim_count"] for row in results)
    cited_claim_count = sum(row["cited_claim_count"] for row in results)
    return {
        "decision_accuracy": computed_metric(
            sum(row["decision_correct"] for row in results),
            len(results),
        ),
        "refusal_accuracy": computed_metric(
            sum(row["actual_decision"] == "refuse" for row in refusals),
            len(refusals),
        ),
        "over_refusal_rate": computed_metric(
            sum(row["actual_decision"] == "refuse" for row in answerable),
            len(answerable),
        ),
        "partial_pass_rate": computed_metric(
            sum(row["actual_decision"] == "partial_pass" for row in answerable),
            len(answerable),
        ),
        "citation_validity": computed_metric(
            sum(row["citation_valid_claim_count"] for row in results),
            cited_claim_count,
            note="claim-level validity over generated claims with citations",
        ),
        "supported_claim_retention_rate": computed_metric(
            sum(row["supported_claim_retained_count"] for row in results),
            supported_claim_count,
        ),
        "unsupported_claim_leakage_rate": computed_metric(
            sum(row["unsupported_claim_leakage_count"] for row in results),
            unsupported_claim_count,
        ),
        "structured_output_success_rate": (
            computed_metric(
                sum(row["structured_output_success"] for row in results),
                len(results),
            )
            if is_llm
            else computed_metric(0, 0, note="offline rule generator")
        ),
        "fallback_rate": (
            computed_metric(
                sum(row["fallback_used"] for row in results),
                len(results),
            )
            if is_llm
            else computed_metric(0, 0, note="offline rule generator")
        ),
        "cold_start_latency_ms": scalar_metric(
            float(cold_rows[0]["end_to_end_latency_ms"]) if cold_rows else None,
            note="first v2 LLM question after explicit model unload",
        ),
        "warm_end_to_end_latency_ms": scalar_metric(
            (
                sum(row["end_to_end_latency_ms"] for row in warm_rows) / len(warm_rows)
                if warm_rows
                else None
            ),
            note="mean question latency excluding the one cold-start question",
        ),
        "mean_end_to_end_latency_ms": scalar_metric(
            (
                sum(row["end_to_end_latency_ms"] for row in results) / len(results)
                if results
                else None
            )
        ),
        "mean_retrieval_latency_ms": scalar_metric(
            (
                sum(row["retrieval_latency_ms"] for row in results) / len(results)
                if results
                else None
            )
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
                sum(row["evidence_packing_latency_ms"] for row in results) / len(results)
                if is_llm and results
                else None
            ),
            note="LLM evidence packing only",
        ),
        "mean_verification_latency_ms": scalar_metric(
            (
                sum(row["verification_latency_ms"] for row in results) / len(results)
                if results
                else None
            )
        ),
        "mean_retry_latency_ms": scalar_metric(
            (
                sum(row["retry_latency_ms"] for row in results) / len(results)
                if results
                else None
            )
        ),
        "generation_attempts_total": sum(
            row["generation_attempts"] for row in results
        ),
        "generated_claim_count": generated_claim_count,
        "supported_claim_count": supported_claim_count,
        "unsupported_claim_count": unsupported_claim_count,
        "supported_claim_retained_count": sum(
            row["supported_claim_retained_count"] for row in results
        ),
        "unsupported_claim_leakage_count": sum(
            row["unsupported_claim_leakage_count"] for row in results
        ),
        "decision_distribution": dict(
            sorted(Counter(row["actual_decision"] for row in results).items())
        ),
        "question_count": len(results),
    }


def v2_method_report(
    method_id: str,
    results: list[dict],
    *,
    release: dict,
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "artifact": "extension_method_report",
        "protocol_version": "v2",
        "release_id": release["release_id"],
        "method_id": method_id,
        "dataset_sha256": release["dataset_sha256"],
        "runtime_bundle_sha256": release["runtime_bundle_sha256"],
        "prompt_contract": (
            release["prompt_contract"] if method_id != "rule_baseline" else None
        ),
        "runtime_model": (
            release["runtime_model"] if method_id != "rule_baseline" else None
        ),
        "started_at": started_at,
        "completed_at": completed_at,
        "metrics": summarize_v2_method(method_id, results),
        "results": results,
    }
