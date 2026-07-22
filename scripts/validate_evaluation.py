from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FINAL_COUNTS = {
    "single_hop": 8,
    "multi_hop": 9,
    "definition": 7,
    "comparison": 5,
    "principle_pros_cons": 5,
    "metric_selection": 2,
    "no_answer": 4,
}
REQUIRED_FIELDS = {
    "question_id",
    "split",
    "category",
    "question",
    "expected_behavior",
    "gold_entities",
    "gold_relations",
    "expected_keywords",
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_ids(path: Path, field: str) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row[field] for row in csv.DictReader(handle)}


def validate_rows(rows: list[dict], split: str, entity_ids: set[str], relation_ids: set[str]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            errors.append(f"{split} line {index}: missing fields {sorted(missing)}")
            continue
        if row["split"] != split:
            errors.append(f"{row['question_id']}: split must be {split}")
        if row["question_id"] in seen_ids:
            errors.append(f"duplicate question_id: {row['question_id']}")
        if row["question"] in seen_questions:
            errors.append(f"duplicate question text in {split}: {row['question']}")
        if row["expected_behavior"] not in {"answer", "refuse"}:
            errors.append(f"{row['question_id']}: invalid expected_behavior")
        unknown_entities = set(row["gold_entities"]) - entity_ids
        unknown_relations = set(row["gold_relations"]) - relation_ids
        if unknown_entities:
            errors.append(f"{row['question_id']}: unknown entities {sorted(unknown_entities)}")
        if unknown_relations:
            errors.append(f"{row['question_id']}: unknown relations {sorted(unknown_relations)}")
        seen_ids.add(row["question_id"])
        seen_questions.add(row["question"])
    return errors


def main() -> None:
    evaluation_dir = PROJECT_ROOT / "data" / "evaluation"
    paths = {
        "dev": evaluation_dir / "dev_questions.jsonl",
        "demo": evaluation_dir / "demo_questions.jsonl",
        "pilot": evaluation_dir / "pilot_questions.jsonl",
        "final": evaluation_dir / "final_questions.jsonl",
    }
    entity_ids = read_ids(PROJECT_ROOT / "data" / "graph" / "entities.csv", "entity_id")
    relation_types = read_ids(PROJECT_ROOT / "data" / "graph" / "relations.csv", "relation")
    datasets = {split: read_jsonl(path) for split, path in paths.items()}

    errors: list[str] = []
    for split, rows in datasets.items():
        errors.extend(validate_rows(rows, split, entity_ids, relation_types))
    if len(datasets["dev"]) != 10:
        errors.append(f"dev set must contain 10 questions, got {len(datasets['dev'])}")
    if len(datasets["demo"]) != 8:
        errors.append(f"demo set must contain 8 questions, got {len(datasets['demo'])}")
    if len(datasets["pilot"]) != 40:
        errors.append(f"pilot set must contain 40 questions, got {len(datasets['pilot'])}")
    if len(datasets["final"]) != 40:
        errors.append(f"final set must contain 40 questions, got {len(datasets['final'])}")

    observed_counts = Counter(row["category"] for row in datasets["final"])
    if dict(observed_counts) != EXPECTED_FINAL_COUNTS:
        errors.append(f"final category counts mismatch: {dict(observed_counts)}")

    final_questions = {row["question"] for row in datasets["final"]}
    dev_overlap = final_questions & {row["question"] for row in datasets["dev"]}
    if dev_overlap:
        errors.append(f"dev/final leakage: {sorted(dev_overlap)}")
    pilot_overlap = final_questions & {row["question"] for row in datasets["pilot"]}
    if pilot_overlap:
        errors.append(f"pilot/final leakage: {sorted(pilot_overlap)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("OK: evaluation datasets are valid")
    print(
        f"OK: dev={len(datasets['dev'])} demo={len(datasets['demo'])} "
        f"pilot={len(datasets['pilot'])} final={len(datasets['final'])}"
    )
    print("OK: final distribution=" + ", ".join(f"{key}:{value}" for key, value in observed_counts.items()))


if __name__ == "__main__":
    sys.exit(main())
