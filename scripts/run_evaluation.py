from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evaluate_question(workflow, item: dict) -> dict:
    response = workflow.invoke(item["question"])
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
        "latency_ms": response.latency_ms,
        "retry_count": response.retry_count,
        "mode": response.retrieval.mode,
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
        "category_metrics": category_metrics,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the frozen scikit-learn QA workflow")
    parser.add_argument("--split", choices=["dev", "demo", "pilot", "final"], default="dev")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: report={output_path}")
    print(f"OK: decision_accuracy={report['decision_accuracy']:.4f}")
    print(f"OK: mean_keyword_coverage={report['mean_keyword_coverage']:.4f}")


if __name__ == "__main__":
    sys.exit(main())
