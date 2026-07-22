from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_chunks(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize_terms(text: str) -> list[str]:
    terms = [term.strip().lower() for term in re.split(r"[|/;,\s]+", text) if term.strip()]
    return [term for term in terms if len(term) > 1]


def score_chunk(chunk: dict, terms: list[str], relation: str) -> float:
    haystack = " ".join(
        [chunk["heading_path"][-1], chunk["page_title"], chunk["display_text"], chunk["embedding_text"]]
    ).lower()
    score = 0.0
    for term in terms:
        if term and term in haystack:
            score += 3.0 if term in chunk["heading_path"][-1].lower() else 1.0
    relation_bonus = {
        "BELONGS_TO": ["overview", "ensemble", "model", "method", "regression", "classification", "clustering"],
        "SOLVES": ["classification", "regression", "clustering"],
        "USES": ["regularization", "bootstrap", "kernel", "tree", "variance", "scaling"],
        "REQUIRES": ["scaling", "kernel", "regularization"],
        "EVALUATED_BY": ["metric", "score", "accuracy", "recall", "f1", "mse", "r2", "silhouette"],
        "HAS_ADVANTAGE": ["advantage", "robust", "stable", "variance", "interpretability"],
        "HAS_LIMITATION": ["limitation", "overfitting", "imbalance", "noise", "high-dimensional"],
        "MITIGATES": ["reduce", "mitigate", "regularization", "pruning", "bootstrap"],
        "DIFFERS_FROM": ["difference", "compare", "vs", "versus"],
    }.get(relation, [])
    for term in relation_bonus:
        if term in haystack:
            score += 0.5
    return score


def choose_evidence(chunk_index: dict[str, list[dict]], relation: dict, entities: dict[str, dict]) -> list[str]:
    source_id = relation["source_id"]
    target_id = relation["target_id"]
    source_entity = entities[source_id]
    target_entity = entities[target_id]
    terms = []
    for text in [
        source_entity["name_en"],
        source_entity["name_zh"],
        source_entity.get("aliases", ""),
        target_entity["name_en"],
        target_entity["name_zh"],
        target_entity.get("aliases", ""),
    ]:
        terms.extend(normalize_terms(text))
    terms = list(dict.fromkeys(terms))

    candidates = chunk_index.get(relation["evidence_source_id"], [])
    if not candidates:
        return []
    ranked = sorted(
        ((score_chunk(chunk, terms, relation["relation"]), chunk) for chunk in candidates),
        key=lambda item: (-item[0], item[1]["chunk_id"]),
    )
    selected = [chunk["chunk_id"] for score, chunk in ranked if score > 0][:2]
    if not selected:
        selected = [candidates[0]["chunk_id"]]
    return selected


def main() -> None:
    entities_path = PROJECT_ROOT / "data" / "graph" / "entities.csv"
    relations_path = PROJECT_ROOT / "data" / "graph" / "relations.csv"
    chunks_path = PROJECT_ROOT / "data" / "chroma" / "chunks_snapshot.jsonl"

    entities_rows = read_csv(entities_path)
    relations_rows = read_csv(relations_path)
    chunks = read_chunks(chunks_path)

    entities = {row["entity_id"]: row for row in entities_rows}
    chunk_index: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        chunk_index[chunk["source_id"]].append(chunk)

    updated = []
    for relation in relations_rows:
        evidence_chunk_ids = choose_evidence(chunk_index, relation, entities)
        relation["evidence_chunk_ids"] = "|".join(evidence_chunk_ids)
        relation["review_status"] = "approved"
        relation["notes"] = "evidence bound from source chunk selection"
        updated.append(relation)

    with relations_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=relations_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated)

    print(f"OK: approved {len(updated)} relations with bound chunk evidence")


if __name__ == "__main__":
    sys.exit(main())
