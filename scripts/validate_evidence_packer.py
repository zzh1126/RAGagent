from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.generators import EvidencePacker
from src.agent.workflow import build_default_workflow
from src.llm.config import AgentLLMSettings


VALIDATION_SPLITS = ("dev", "pilot")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def selection_signature(pack) -> dict:
    trace = pack.trace
    return {
        "context": pack.context,
        "selected_evidence_ids": trace.selected_evidence_ids,
        "selected_chunk_ids": trace.selected_chunk_ids,
        "selected_graph_path_ids": trace.selected_graph_path_ids,
        "reason_codes_by_evidence": trace.reason_codes_by_evidence,
        "entity_coverage": trace.entity_coverage,
        "coverage_gaps": trace.coverage_gaps,
        "truncated_evidence_ids": trace.truncated_evidence_ids,
        "dropped_evidence_ids": trace.dropped_evidence_ids,
        "selection_target": trace.selection_target,
    }


def validate_pack(question_id: str, retrieval, first, second) -> list[str]:
    errors: list[str] = []
    if selection_signature(first) != selection_signature(second):
        errors.append(f"{question_id}: repeated packing is not deterministic")
    if len(first.context) > first.trace.max_context_chars:
        errors.append(f"{question_id}: packed context exceeds its character budget")
    if first.trace.packed_character_count != len(first.context):
        errors.append(f"{question_id}: packed character trace is inaccurate")
    if len(first.text_evidence) > first.trace.max_text_evidence:
        errors.append(f"{question_id}: selected too many text evidence items")
    if len(first.text_evidence) > first.trace.selection_target:
        errors.append(f"{question_id}: selected evidence exceeds the intent target")
    if len(first.graph_paths) > first.trace.max_graph_paths:
        errors.append(f"{question_id}: selected too many graph paths")

    source_evidence_ids = {item.evidence_id for item in retrieval.text_evidence}
    source_chunk_ids = {item.chunk_id for item in retrieval.text_evidence}
    source_path_ids = {path.path_id for path in retrieval.graph_paths}
    selected_evidence_ids = first.trace.selected_evidence_ids
    selected_chunk_ids = first.trace.selected_chunk_ids
    selected_path_ids = first.trace.selected_graph_path_ids
    if not set(selected_evidence_ids).issubset(source_evidence_ids):
        errors.append(f"{question_id}: packer created an unknown evidence ID")
    if not set(selected_chunk_ids).issubset(source_chunk_ids):
        errors.append(f"{question_id}: packer created an unknown chunk ID")
    if not set(selected_path_ids).issubset(source_path_ids):
        errors.append(f"{question_id}: packer created an unknown graph path ID")
    if len(selected_chunk_ids) != len(set(selected_chunk_ids)):
        errors.append(f"{question_id}: selected chunks are not deduplicated")
    if set(first.trace.reason_codes_by_evidence) != set(selected_evidence_ids):
        errors.append(f"{question_id}: reason-code keys differ from selected evidence IDs")
    if [item.evidence_id for item in first.text_evidence] != selected_evidence_ids:
        errors.append(f"{question_id}: packed evidence order differs from its trace")
    if [path.path_id for path in first.graph_paths] != selected_path_ids:
        errors.append(f"{question_id}: packed path order differs from its trace")
    return errors


def main() -> None:
    settings = yaml.safe_load(
        (PROJECT_ROOT / "config/settings.yaml").read_text(encoding="utf-8")
    )
    agent = AgentLLMSettings.model_validate(settings.get("agent", {}))
    packer = EvidencePacker(
        max_text_evidence=agent.max_text_evidence,
        max_graph_paths=agent.max_graph_paths,
        max_chars_per_evidence=agent.max_chars_per_evidence,
        max_context_chars=agent.max_context_chars,
        comparison_evidence_per_entity=agent.comparison_evidence_per_entity,
    )
    workflow = build_default_workflow(PROJECT_ROOT, generator_backend="offline_rule")
    errors: list[str] = []
    question_count = 0
    selected_counts: list[int] = []
    context_lengths: list[int] = []
    gap_counts: Counter[str] = Counter()
    gap_examples: dict[str, list[str]] = {}

    for split in VALIDATION_SPLITS:
        questions = read_jsonl(
            PROJECT_ROOT / "data/evaluation" / f"{split}_questions.jsonl"
        )
        for item in questions:
            question_count += 1
            route = workflow.router.route(item["question"])
            retrieval = workflow.retriever.retrieve(
                item["question"],
                route.intent,
                route.mode,
                top_k=workflow.top_k,
            )
            before = retrieval.model_dump(mode="json")
            first = packer.pack(item["question"], retrieval)
            second = packer.pack(item["question"], retrieval)
            errors.extend(validate_pack(item["question_id"], retrieval, first, second))
            if retrieval.model_dump(mode="json") != before:
                errors.append(f"{item['question_id']}: packer mutated RetrievalResult")
            selected_counts.append(len(first.text_evidence))
            context_lengths.append(len(first.context))
            gap_counts.update(first.trace.coverage_gaps)
            for gap in first.trace.coverage_gaps:
                gap_examples.setdefault(gap, []).append(item["question_id"])

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    mean_selected = sum(selected_counts) / len(selected_counts) if selected_counts else 0.0
    print("OK: evidence packer is deterministic and contract-safe on dev/pilot")
    print(
        f"OK: questions={question_count} splits={','.join(VALIDATION_SPLITS)} "
        f"mean_selected={mean_selected:.2f} max_context_chars={max(context_lengths)}"
    )
    print(f"OK: coverage_gap_events={sum(gap_counts.values())}")
    for gap, count in sorted(gap_counts.items()):
        print(f"- {gap}: {count} examples={','.join(gap_examples[gap][:3])}")


if __name__ == "__main__":
    main()
