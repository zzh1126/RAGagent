from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.config import ExperimentDefinition, ExperimentSuite, load_experiment_suite
from src.evaluation.schemas import (
    ExperimentMetrics,
    ExperimentRunReport,
    LatencyBreakdown,
    MetricValue,
    QuestionRunResult,
)
from src.evaluation.workflow_factory import build_experiment_workflow


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_relations(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def derive_gold_chunk_ids(item: dict, relations: list[dict[str, str]]) -> list[str]:
    """Derive conservative gold chunks from approved graph relations when available."""

    gold_entities = set(item.get("gold_entities", []))
    gold_relations = set(item.get("gold_relations", []))
    if not gold_entities or not gold_relations:
        return []

    chunks: list[str] = []
    for relation in relations:
        if relation.get("review_status") != "approved":
            continue
        if relation.get("relation") not in gold_relations:
            continue
        endpoints = {relation.get("source_id", ""), relation.get("target_id", "")}
        if len(gold_entities) > 1:
            if not endpoints.issubset(gold_entities):
                continue
        elif not endpoints.intersection(gold_entities):
            continue
        chunks.extend(relation.get("evidence_chunk_ids", "").split("|"))
    return unique(chunks)


def independent_path_validity(response, graph_repo) -> float | None:
    paths = response.retrieval.graph_paths
    if not paths:
        return None
    valid = 0
    for path in paths:
        triples = [triple.model_dump() for triple in path.triples]
        if graph_repo.validate_path(triples):
            valid += 1
    return valid / len(paths)


def evaluate_question(workflow, item: dict, relations: list[dict[str, str]], recall_k: int) -> tuple[QuestionRunResult, bool | None]:
    response = workflow.invoke(item["question"])
    if response.verification.decision not in {"pass", "refuse"}:
        raise RuntimeError(
            f"workflow returned a non-final decision for {item['question_id']}: "
            f"{response.verification.decision}"
        )

    expected_decision = "refuse" if item["expected_behavior"] == "refuse" else "pass"
    retrieved_chunk_ids = unique([evidence.chunk_id for evidence in response.retrieval.text_evidence])
    gold_chunk_ids = derive_gold_chunk_ids(item, relations)
    recall_hit = (
        bool(set(retrieved_chunk_ids[:recall_k]) & set(gold_chunk_ids))
        if gold_chunk_ids
        else None
    )
    path_validity = independent_path_validity(response, workflow.graph_repo)
    result = QuestionRunResult(
        question_id=item["question_id"],
        question=item["question"],
        category=item["category"],
        expected_decision=expected_decision,
        actual_decision=response.verification.decision,
        decision_correct=response.verification.decision == expected_decision,
        answer=response.answer,
        intent=response.retrieval.intent,
        retrieval_mode=response.retrieval.mode,
        retry_count=response.retry_count,
        evidence_score=response.verification.evidence_score,
        claim_coverage=response.verification.claim_coverage,
        citation_validity=response.verification.citation_validity,
        path_validity=path_validity or 0.0,
        citation_present=bool(response.retrieval.text_evidence),
        retrieved_chunk_ids=retrieved_chunk_ids[:recall_k],
        gold_chunk_ids=gold_chunk_ids,
        graph_path_ids=[path.path_id for path in response.retrieval.graph_paths],
        unsupported_claims=response.verification.unsupported_claims,
        latency=LatencyBreakdown(total_ms=float(response.latency_ms)),
    )
    return result, recall_hit


def computed_metric(numerator: float, denominator: float, note: str = "") -> MetricValue:
    if denominator <= 0:
        return MetricValue(status="not_applicable", note=note or "no eligible questions")
    return MetricValue(
        value=round(numerator / denominator, 4),
        numerator=numerator,
        denominator=denominator,
        status="computed",
        note=note,
    )


def pending_metric(note: str) -> MetricValue:
    return MetricValue(status="pending_human_review", note=note)


def build_metrics(results: list[QuestionRunResult], recall_hits: list[bool]) -> ExperimentMetrics:
    answerable = [result for result in results if result.expected_decision == "pass"]
    no_answer = [result for result in results if result.expected_decision == "refuse"]
    path_results = [result for result in results if result.graph_path_ids]
    latencies = [result.latency.total_ms for result in results]
    return ExperimentMetrics(
        decision_accuracy=computed_metric(
            sum(result.decision_correct for result in results),
            len(results),
        ),
        answer_correctness=pending_metric(
            "requires manual 0/1/2 correctness scoring"
        ),
        evidence_faithfulness=pending_metric(
            "requires manual 0/1/2 faithfulness scoring"
        ),
        retrieval_recall_at_5=computed_metric(
            sum(recall_hits),
            len(recall_hits),
            note="computed only for questions with conservative graph-derived gold Chunk IDs",
        ),
        path_validity=computed_metric(
            sum(result.path_validity for result in path_results),
            len(path_results),
            note="computed independently of the Verifier setting",
        ),
        refusal_accuracy=computed_metric(
            sum(result.actual_decision == "refuse" for result in no_answer),
            len(no_answer),
        ),
        hallucination_rate=pending_metric(
            "requires manual review of unsupported professional claims"
        ),
        over_refusal_rate=computed_metric(
            sum(result.actual_decision == "refuse" for result in answerable),
            len(answerable),
        ),
        citation_rate=computed_metric(
            sum(result.citation_present for result in answerable),
            len(answerable),
            note="citation presence among answerable questions",
        ),
        latency_ms=computed_metric(
            sum(latencies),
            len(latencies),
            note="local workflow total latency; stage timers are not yet instrumented",
        ),
    )


def run_experiment(
    root: Path,
    suite: ExperimentSuite,
    experiment: ExperimentDefinition,
    split: str,
    output_path: Path,
) -> ExperimentRunReport:
    dataset_path = root / "data" / "evaluation" / f"{split}_questions.jsonl"
    relations_path = root / "data" / "graph" / "relations.csv"
    questions = read_jsonl(dataset_path)
    relations = read_relations(relations_path)
    workflow = build_experiment_workflow(root, experiment)
    started_at = datetime.now(timezone.utc)
    results: list[QuestionRunResult] = []
    recall_hits: list[bool] = []
    for index, item in enumerate(questions, start=1):
        result, recall_hit = evaluate_question(
            workflow,
            item,
            relations,
            suite.protocol.retrieval_recall_k,
        )
        results.append(result)
        if recall_hit is not None:
            recall_hits.append(recall_hit)
        print(
            f"[{experiment.id} {index:02d}/{len(questions):02d}] "
            f"{item['question_id']} expected={result.expected_decision} "
            f"actual={result.actual_decision}"
        )

    completed_at = datetime.now(timezone.utc)
    report = ExperimentRunReport(
        run_id=f"{experiment.id}-{split}-{completed_at.strftime('%Y%m%dT%H%M%SZ')}",
        experiment_id=experiment.id,
        experiment_config=experiment,
        dataset_split=split,
        dataset_path=str(dataset_path.relative_to(root)),
        dataset_sha256=sha256(dataset_path),
        config_fingerprint=suite.fingerprint(),
        engine=workflow.engine_name,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        question_count=len(results),
        metrics=build_metrics(results, recall_hits),
        results=results,
        notes=[
            "Generated by the configured offline experiment runner.",
            "Human correctness, faithfulness, and hallucination metrics remain pending manual review.",
            "The final holdout is read-only and is not executable by this command.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run configured main and ablation experiments")
    parser.add_argument("--split", choices=["dev", "pilot", "final"])
    parser.add_argument("--experiments", nargs="+", help="experiment IDs; defaults to all enabled methods")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the run plan only")
    args = parser.parse_args()

    root = PROJECT_ROOT
    suite = load_experiment_suite(root / "config" / "experiments.yaml")
    split = args.split or suite.protocol.experiment_split
    if split == suite.protocol.frozen_holdout.split:
        raise SystemExit(
            "Refusing to run the frozen final split. Reuse reports/evaluation_final.json instead."
        )

    selected_ids = args.experiments or [
        name for name, experiment in suite.experiments.items() if experiment.enabled
    ]
    unknown = [name for name in selected_ids if name not in suite.experiments]
    disabled = [name for name in selected_ids if not suite.experiments[name].enabled]
    if unknown:
        raise SystemExit(f"Unknown experiment IDs: {', '.join(unknown)}")
    if disabled:
        raise SystemExit(f"Requested experiments are disabled: {', '.join(disabled)}")

    output_dir = root / suite.protocol.output_dir
    output_paths = {name: output_dir / f"{name}_{split}.json" for name in selected_ids}
    existing = [str(path) for path in output_paths.values() if path.exists()]
    if existing:
        raise SystemExit("Refusing to overwrite existing experiment outputs: " + ", ".join(existing))

    print(f"Experiment split: {split}")
    print(f"Config fingerprint: {suite.fingerprint()}")
    print("Methods: " + ", ".join(selected_ids))
    if args.dry_run:
        for name, path in output_paths.items():
            print(f"DRY-RUN: {name} -> {path}")
        return

    for name in selected_ids:
        report = run_experiment(root, suite, suite.experiments[name], split, output_paths[name])
        print(
            f"OK: {name} decision_accuracy={report.metrics.decision_accuracy.value:.4f} "
            f"output={output_paths[name]}"
        )


if __name__ == "__main__":
    main()
