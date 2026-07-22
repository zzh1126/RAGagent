from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow
from src.agent.generators.llm_generator import ANSWER_PROMPT_VERSION


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


def evaluate_question(workflow, item: dict) -> dict:
    response = workflow.invoke(item["question"])
    generation = response.answer_payload
    generation_trace = response.generation_trace
    llm_calls = [call for call in generation_trace if call.requested_backend == "ollama"]
    expected_decision = "refuse" if item["expected_behavior"] == "refuse" else "pass"
    retrieved_entities = {entity.entity_id for entity in response.retrieval.entities}
    for path in response.retrieval.graph_paths:
        for triple in path.triples:
            retrieved_entities.update([triple.source_id, triple.target_id])
    answer_text = response.answer.lower()
    keywords = item["expected_keywords"]
    keyword_hits = sum(1 for keyword in keywords if keyword.lower() in answer_text)
    keyword_coverage = keyword_hits / len(keywords) if keywords else 1.0
    gold_entities = set(item["gold_entities"])
    entity_coverage = len(gold_entities & retrieved_entities) / len(gold_entities) if gold_entities else 1.0
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "question": item["question"],
        "expected_decision": expected_decision,
        "actual_decision": response.verification.decision,
        "decision_correct": response.verification.decision == expected_decision,
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
        "mode": response.retrieval.mode,
        "generator_backend": generation.generator_backend,
        "generator_fallback_used": any(call.fallback_used for call in generation_trace),
        "generator_fallback_reason": next(
            (call.fallback_reason for call in generation_trace if call.fallback_reason),
            None,
        ),
        "generation_call_count": len(generation_trace),
        "generation_attempts": sum(call.attempts for call in generation_trace),
        "generation_latency_ms": round(sum(call.latency_ms for call in generation_trace), 1),
        "structured_output_success": bool(
            llm_calls and all(call.structured_output_success for call in llm_calls)
        ),
        "generator_unsupported_claims": list(generation.unsupported_claims),
        "verifier_unsupported_claims": list(response.verification.unsupported_claims),
    }


def summarize(results: list[dict], engine: str) -> dict:
    total = len(results)
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
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": engine,
        "question_count": total,
        "decision_accuracy": round(sum(row["decision_correct"] for row in results) / total, 4),
        "citation_rate": round(sum(row["citation_present"] for row in results) / total, 4),
        "mean_keyword_coverage": round(sum(row["keyword_coverage"] for row in results) / total, 4),
        "mean_entity_coverage": round(sum(row["entity_coverage"] for row in results) / total, 4),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in results) / total, 2),
        "mean_generation_latency_ms": round(
            sum(row["generation_latency_ms"] for row in results) / total,
            2,
        ),
        "structured_output_success_rate": round(
            sum(row["structured_output_success"] for row in results) / total,
            4,
        ),
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
    return {
        "requested_backend": "llm" if client is not None else "offline_rule",
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
        "prompt_version": ANSWER_PROMPT_VERSION if client is not None else None,
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


def ensure_split_runnable(split: str) -> None:
    if split == "final":
        raise SystemExit(
            "Refusing to run the frozen final split. Reuse reports/evaluation_final.json instead."
        )
    if split == "extension":
        raise SystemExit(
            "Refusing to run the locked extension holdout before an explicit release record exists."
        )


if __name__ == "__main__":
    sys.exit(main())
