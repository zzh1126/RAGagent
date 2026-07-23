from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow
from src.agent.generators.llm_generator import ANSWER_PROMPT_VERSION
from src.schemas import FinalResponse


RUNNABLE_SPLITS = ("dev", "demo", "pilot")
FROZEN_SPLITS = ("final", "extension")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def visible_claim_leakage_count(response: FinalResponse) -> int:
    allowed_claims = Counter(
        result.claim.strip()
        for result in response.verification.claim_results
        if result.retained
    )
    leakage_count = 0
    for claim in response.answer_payload.claims:
        normalized = claim.claim.strip()
        if allowed_claims[normalized] > 0:
            allowed_claims[normalized] -= 1
        else:
            leakage_count += 1
    return leakage_count


def audit_stage_flags(
    *,
    expected_decision: str,
    actual_decision: str,
    structured_output_status: str,
    fallback_used: bool,
    entity_coverage: float,
    retrieval_sufficiency: float,
    packing_coverage_gaps: list[str],
    removed_claim_count: int,
) -> list[str]:
    flags: list[str] = []
    if fallback_used or structured_output_status == "failed":
        flags.append("generation")
    if expected_decision == "pass" and (
        entity_coverage < 1.0 or retrieval_sufficiency < 1.0
    ):
        flags.append("retrieval")
    if packing_coverage_gaps:
        flags.append("packing")
    if removed_claim_count or (
        expected_decision == "pass" and actual_decision == "refuse"
    ):
        flags.append("verification")
    return flags


def evaluate_question(workflow, item: dict) -> dict:
    response = workflow.invoke(item["question"])
    generation = response.answer_payload
    generation_trace = response.generation_trace
    packing_trace = response.evidence_packing_trace
    latency_trace = response.latency_trace
    llm_calls = [
        call for call in generation_trace if call.requested_backend == "ollama"
    ]
    runtime_call = (
        llm_calls[0]
        if llm_calls
        else generation_trace[0]
        if generation_trace
        else None
    )
    structured_output_status = (
        "not_called"
        if not llm_calls
        else "success"
        if all(call.structured_output_success for call in llm_calls)
        else "failed"
    )
    generation_latency_ms = round(sum(call.latency_ms for call in generation_trace), 1)
    packing_latency_ms = round(
        sum(trace.evidence_packing_latency_ms for trace in packing_trace),
        3,
    )
    verification_latency_ms = round(
        sum(call.latency_ms for call in response.verification_trace),
        3,
    )
    if not response.verification_trace:
        verification_latency_ms = response.verification.verification_latency_ms
    expected_decision = (
        "refuse" if item["expected_behavior"] == "refuse" else "pass"
    )
    actual_decision = response.verification.decision
    decision_correct = (
        actual_decision == "refuse"
        if expected_decision == "refuse"
        else actual_decision in {"pass", "partial_pass"}
    )
    retrieved_entities = {entity.entity_id for entity in response.retrieval.entities}
    for path in response.retrieval.graph_paths:
        for triple in path.triples:
            retrieved_entities.update([triple.source_id, triple.target_id])
    answer_text = response.answer.lower()
    keywords = item["expected_keywords"]
    keyword_hits = sum(1 for keyword in keywords if keyword.lower() in answer_text)
    keyword_coverage = keyword_hits / len(keywords) if keywords else 1.0
    gold_entities = set(item["gold_entities"])
    entity_coverage = (
        len(gold_entities & retrieved_entities) / len(gold_entities)
        if gold_entities
        else 1.0
    )
    fallback_used = any(call.fallback_used for call in generation_trace)
    packing_coverage_gaps = list(
        dict.fromkeys(
            gap
            for trace in packing_trace
            for gap in trace.coverage_gaps
        )
    )
    over_refusal = expected_decision == "pass" and actual_decision == "refuse"
    false_accept = expected_decision == "refuse" and actual_decision != "refuse"
    outcome_error_type = (
        "over_refusal" if over_refusal else "false_accept" if false_accept else None
    )
    unsupported_claim_leakage_count = visible_claim_leakage_count(response)
    stage_flags = audit_stage_flags(
        expected_decision=expected_decision,
        actual_decision=actual_decision,
        structured_output_status=structured_output_status,
        fallback_used=fallback_used,
        entity_coverage=entity_coverage,
        retrieval_sufficiency=response.verification.retrieval_sufficiency,
        packing_coverage_gaps=packing_coverage_gaps,
        removed_claim_count=response.verification.removed_claim_count,
    )
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "question": item["question"],
        "expected_decision": expected_decision,
        "actual_decision": actual_decision,
        "decision_correct": decision_correct,
        "answerable": expected_decision == "pass",
        "over_refusal": over_refusal,
        "correct_refusal": (
            expected_decision == "refuse" and actual_decision == "refuse"
        ),
        "false_accept": false_accept,
        "outcome_error_type": outcome_error_type,
        "partial_pass": actual_decision == "partial_pass",
        "keyword_coverage": round(keyword_coverage, 4),
        "entity_coverage": round(entity_coverage, 4),
        "citation_present": bool(response.retrieval.text_evidence) if expected_decision == "pass" else True,
        "evidence_score": response.verification.evidence_score,
        "claim_coverage": response.verification.claim_coverage,
        "citation_validity": response.verification.citation_validity,
        "path_validity": response.verification.path_validity,
        "retrieval_sufficiency": response.verification.retrieval_sufficiency,
        "latency_ms": response.latency_ms,
        "retry_count": response.retry_count,
        "retry_used": response.retry_count > 0,
        "mode": response.retrieval.mode,
        "route_trace": response.route_trace.model_dump(mode="json") if response.route_trace else None,
        "retrieval_trace": [
            call.model_dump(mode="json") for call in response.retrieval_trace
        ],
        "verification_trace": [
            call.model_dump(mode="json") for call in response.verification_trace
        ],
        "latency_trace": latency_trace.model_dump(mode="json"),
        "routing_latency_ms": latency_trace.routing_latency_ms,
        "retrieval_latency_ms": latency_trace.retrieval_latency_ms,
        "evidence_packing_latency_ms": packing_latency_ms,
        "llm_generation_latency_ms": generation_latency_ms,
        "verification_latency_ms": verification_latency_ms,
        "retry_latency_ms": latency_trace.retry_latency_ms,
        "end_to_end_latency_ms": (
            latency_trace.end_to_end_latency_ms or float(response.latency_ms)
        ),
        "cache_status": response.cache_status,
        "generator_provider": runtime_call.provider if runtime_call else None,
        "generator_model": runtime_call.model if runtime_call else None,
        "generator_requested_backend": (
            runtime_call.requested_backend if runtime_call else None
        ),
        "generator_backend": generation.generator_backend,
        "generator_fallback_used": fallback_used,
        "generator_fallback_reason": next(
            (call.fallback_reason for call in generation_trace if call.fallback_reason),
            None,
        ),
        "generation_call_count": len(generation_trace),
        "generation_attempts": sum(call.attempts for call in generation_trace),
        "generation_latency_ms": generation_latency_ms,
        "evidence_packing_trace": [
            trace.model_dump(mode="json") for trace in packing_trace
        ],
        "structured_output_attempted": bool(llm_calls),
        "structured_output_status": structured_output_status,
        "structured_output_success": structured_output_status == "success",
        "generated_claim_count": response.verification.generated_claim_count,
        "supported_claim_count": response.verification.supported_claim_count,
        "retained_claim_count": len(response.verification.retained_claim_ids),
        "removed_claim_count": response.verification.removed_claim_count,
        "visible_claim_count": len(generation.claims),
        "claim_support_rate": ratio(
            response.verification.supported_claim_count,
            response.verification.generated_claim_count,
        ),
        "claim_retention_rate": ratio(
            len(response.verification.retained_claim_ids),
            response.verification.generated_claim_count,
        ),
        "unsupported_claim_leakage_count": unsupported_claim_leakage_count,
        "verification_reason_codes": list(response.verification.reason_codes),
        "claim_diagnostics": [
            {
                "claim_id": result.claim_id,
                "status": result.status,
                "retained": result.retained,
                "reason_codes": list(result.reason_codes),
            }
            for result in response.verification.claim_results
        ],
        "packing_coverage_gaps": packing_coverage_gaps,
        "audit_stage_flags": stage_flags,
        "generator_unsupported_claims": list(generation.unsupported_claims),
        "verifier_unsupported_claims": list(response.verification.unsupported_claims),
    }


def summarize(results: list[dict], engine: str) -> dict:
    total = len(results)
    if not total:
        raise ValueError("Cannot summarize an empty evaluation result set")
    category_rows: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        category_rows[row["category"]].append(row)
    category_metrics = {
        category: {
            "count": len(rows),
            "decision_accuracy": round(sum(row["decision_correct"] for row in rows) / len(rows), 4),
            "mean_keyword_coverage": round(sum(row["keyword_coverage"] for row in rows) / len(rows), 4),
        }
        for category, rows in category_rows.items()
    }
    answerable_rows = [row for row in results if row["expected_decision"] == "pass"]
    no_answer_rows = [row for row in results if row["expected_decision"] == "refuse"]
    structured_attempts = [row for row in results if row["structured_output_attempted"]]
    generated_claim_count = sum(row["generated_claim_count"] for row in results)
    supported_claim_count = sum(row["supported_claim_count"] for row in results)
    retained_claim_count = sum(row["retained_claim_count"] for row in results)
    removed_claim_count = sum(row["removed_claim_count"] for row in results)
    decision_distribution = Counter(row["actual_decision"] for row in results)
    structured_status_distribution = Counter(
        row["structured_output_status"] for row in results
    )
    verification_reason_code_counts = Counter(
        code
        for row in results
        for code in row["verification_reason_codes"]
    )
    claim_reason_code_counts = Counter(
        code
        for row in results
        for claim in row["claim_diagnostics"]
        for code in claim["reason_codes"]
    )
    audit_stage_counts = Counter(
        stage
        for row in results
        for stage in row["audit_stage_flags"]
    )
    packing_coverage_gap_counts = Counter(
        gap
        for row in results
        for gap in row["packing_coverage_gaps"]
    )
    fallback_reason_counts = Counter(
        row["generator_fallback_reason"] or "unspecified"
        for row in results
        if row["generator_fallback_used"]
    )
    outcome_error_counts = Counter(
        row["outcome_error_type"]
        for row in results
        if row["outcome_error_type"]
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": engine,
        "question_count": total,
        "decision_accuracy": round(
            sum(row["decision_correct"] for row in results) / total,
            4,
        ),
        "answerable_count": len(answerable_rows),
        "no_answer_count": len(no_answer_rows),
        "answerable_answered_count": sum(
            row["actual_decision"] in {"pass", "partial_pass"}
            for row in answerable_rows
        ),
        "over_refusal_count": sum(row["over_refusal"] for row in answerable_rows),
        "over_refusal_rate": ratio(
            sum(row["over_refusal"] for row in answerable_rows),
            len(answerable_rows),
        ),
        "correct_refusal_count": sum(
            row["correct_refusal"] for row in no_answer_rows
        ),
        "refusal_accuracy": ratio(
            sum(row["correct_refusal"] for row in no_answer_rows),
            len(no_answer_rows),
        ),
        "false_accept_count": sum(row["false_accept"] for row in no_answer_rows),
        "decision_distribution": dict(sorted(decision_distribution.items())),
        "partial_pass_count": decision_distribution["partial_pass"],
        "partial_pass_rate": ratio(decision_distribution["partial_pass"], total),
        "retry_question_count": sum(row["retry_used"] for row in results),
        "retry_rate": ratio(sum(row["retry_used"] for row in results), total),
        "total_retry_count": sum(row["retry_count"] for row in results),
        "citation_rate": round(sum(row["citation_present"] for row in results) / total, 4),
        "mean_keyword_coverage": round(sum(row["keyword_coverage"] for row in results) / total, 4),
        "mean_entity_coverage": round(sum(row["entity_coverage"] for row in results) / total, 4),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in results) / total, 2),
        "mean_routing_latency_ms": round(
            sum(row["routing_latency_ms"] for row in results) / total,
            3,
        ),
        "mean_retrieval_latency_ms": round(
            sum(row["retrieval_latency_ms"] for row in results) / total,
            3,
        ),
        "mean_generation_latency_ms": round(
            sum(row["generation_latency_ms"] for row in results) / total,
            2,
        ),
        "mean_evidence_packing_latency_ms": round(
            sum(row["evidence_packing_latency_ms"] for row in results) / total,
            3,
        ),
        "mean_verification_latency_ms": round(
            sum(row["verification_latency_ms"] for row in results) / total,
            3,
        ),
        "mean_retry_latency_ms": round(
            sum(row["retry_latency_ms"] for row in results) / total,
            3,
        ),
        "mean_end_to_end_latency_ms": round(
            sum(row["end_to_end_latency_ms"] for row in results) / total,
            2,
        ),
        "structured_output_attempt_count": len(structured_attempts),
        "structured_output_success_count": sum(
            row["structured_output_success"] for row in structured_attempts
        ),
        "structured_output_failed_count": structured_status_distribution["failed"],
        "structured_output_not_called_count": structured_status_distribution[
            "not_called"
        ],
        "structured_output_coverage_rate": ratio(len(structured_attempts), total),
        "structured_output_success_rate": ratio(
            sum(row["structured_output_success"] for row in structured_attempts),
            len(structured_attempts),
        ),
        "structured_output_status_distribution": dict(
            sorted(structured_status_distribution.items())
        ),
        "generated_claim_count": generated_claim_count,
        "supported_claim_count": supported_claim_count,
        "retained_claim_count": retained_claim_count,
        "removed_claim_count": removed_claim_count,
        "claim_support_rate": ratio(supported_claim_count, generated_claim_count),
        "claim_retention_rate": ratio(retained_claim_count, generated_claim_count),
        "claim_removal_rate": ratio(removed_claim_count, generated_claim_count),
        "unsupported_claim_leakage_count": sum(
            row["unsupported_claim_leakage_count"] for row in results
        ),
        "unsupported_claim_leakage_question_count": sum(
            row["unsupported_claim_leakage_count"] > 0 for row in results
        ),
        "verification_reason_code_counts": dict(
            sorted(verification_reason_code_counts.items())
        ),
        "claim_reason_code_counts": dict(sorted(claim_reason_code_counts.items())),
        "audit_stage_counts": dict(sorted(audit_stage_counts.items())),
        "packing_coverage_gap_counts": dict(
            sorted(packing_coverage_gap_counts.items())
        ),
        "fallback_reason_counts": dict(sorted(fallback_reason_counts.items())),
        "outcome_error_counts": dict(sorted(outcome_error_counts.items())),
        "fallback_rate": round(
            sum(row["generator_fallback_used"] for row in results) / total,
            4,
        ),
        "category_metrics": category_metrics,
        "results": results,
    }


def generator_metadata(workflow) -> dict:
    generator = workflow.answer_generator
    primary = getattr(generator, "primary", generator)
    client = getattr(primary, "client", None)
    serializer = getattr(primary, "context_serializer", None)
    packer = getattr(serializer, "packer", None)
    return {
        "requested_backend": "llm" if client is not None else "offline_rule",
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
        "prompt_version": ANSWER_PROMPT_VERSION if client is not None else None,
        "evidence_packer_version": getattr(packer, "VERSION", None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the frozen scikit-learn QA workflow")
    parser.add_argument("--split", choices=[*RUNNABLE_SPLITS, *FROZEN_SPLITS], default="dev")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    ensure_split_runnable(args.split)

    input_path = PROJECT_ROOT / "data" / "evaluation" / f"{args.split}_questions.jsonl"
    output_path = args.output or PROJECT_ROOT / "reports" / f"evaluation_{args.split}.json"
    workflow = build_default_workflow(PROJECT_ROOT)
    questions = read_jsonl(input_path)
    results = []
    for index, item in enumerate(questions, start=1):
        result = evaluate_question(workflow, item)
        results.append(result)
        print(
            f"[{index:02d}/{len(questions):02d}] {item['question_id']} "
            f"expected={result['expected_decision']} actual={result['actual_decision']}"
        )

    report = summarize(results, workflow.engine_name)
    report["dataset_sha256"] = sha256(input_path)
    report["settings_sha256"] = sha256(PROJECT_ROOT / "config" / "settings.yaml")
    report["generator"] = generator_metadata(workflow)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: report={output_path}")
    print(f"OK: decision_accuracy={report['decision_accuracy']:.4f}")
    print(f"OK: mean_keyword_coverage={report['mean_keyword_coverage']:.4f}")
    print(f"OK: structured_output_success_rate={report['structured_output_success_rate']:.4f}")
    print(f"OK: fallback_rate={report['fallback_rate']:.4f}")
    print(
        "OK: over_refusal="
        f"{report['over_refusal_count']}/{report['answerable_count']} "
        f"({report['over_refusal_rate']:.4f})"
    )
    print(
        "OK: refusal_accuracy="
        f"{report['correct_refusal_count']}/{report['no_answer_count']} "
        f"({report['refusal_accuracy']:.4f})"
    )
    print(
        "OK: retry_rate="
        f"{report['retry_question_count']}/{report['question_count']} "
        f"({report['retry_rate']:.4f})"
    )
    print(
        "OK: claims="
        f"generated={report['generated_claim_count']} "
        f"supported={report['supported_claim_count']} "
        f"retained={report['retained_claim_count']} "
        f"removed={report['removed_claim_count']}"
    )


def ensure_split_runnable(split: str) -> None:
    if split == "final":
        raise SystemExit(
            "Refusing to run the frozen final split. Reuse reports/evaluation_final.json instead."
        )
    if split == "extension":
        raise SystemExit(
            "Refusing to run the locked extension through the generic runner. "
            "Use scripts/run_extension_evaluation.py only with a valid release record."
        )


if __name__ == "__main__":
    sys.exit(main())
