from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    sources = yaml.safe_load((PROJECT_ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    ontology = yaml.safe_load((PROJECT_ROOT / "config" / "ontology.yaml").read_text(encoding="utf-8"))
    entities = read_csv(PROJECT_ROOT / "data" / "graph" / "entities.csv")
    relations = read_csv(PROJECT_ROOT / "data" / "graph" / "relations.csv")

    source_ids = {row["id"] for row in sources["sources"]}
    entity_by_id = {row["entity_id"]: row for row in entities}
    if len(entity_by_id) != len(entities):
        fail("entity_id values must be unique")

    if not 40 <= len(entities) <= 50:
        fail(f"expected 40-50 entities, found {len(entities)}")

    if not 100 <= len(relations) <= 120:
        fail(f"expected 100-120 relations, found {len(relations)}")

    allowed_types = set(ontology["node_types"])
    for entity in entities:
        if entity["type"] not in allowed_types:
            fail(f"unknown entity type: {entity}")
        if entity["review_status"] not in {"pending", "approved", "rejected"}:
            fail(f"invalid entity review_status: {entity}")

    relation_rules = ontology["relations"]
    relation_ids = set()
    approved = 0
    pending = 0
    relation_counter: Counter[str] = Counter()
    for relation in relations:
        relation_id = relation["relation_id"]
        if relation_id in relation_ids:
            fail(f"duplicate relation_id: {relation_id}")
        relation_ids.add(relation_id)

        source_id = relation["source_id"]
        target_id = relation["target_id"]
        if source_id not in entity_by_id:
            fail(f"relation source does not exist: {relation}")
        if target_id not in entity_by_id:
            fail(f"relation target does not exist: {relation}")
        if relation["evidence_source_id"] not in source_ids:
            fail(f"relation evidence_source_id is not in sources.yaml: {relation}")
        if relation["review_status"] not in {"pending", "approved", "rejected"}:
            fail(f"invalid relation review_status: {relation}")

        rule = relation_rules.get(relation["relation"])
        if not rule:
            fail(f"unknown relation type: {relation}")
        source_type = entity_by_id[source_id]["type"]
        target_type = entity_by_id[target_id]["type"]
        if source_type not in rule["source_types"]:
            fail(f"invalid source type for relation: {relation_id} {source_type}->{relation['relation']}")
        if target_type not in rule["target_types"]:
            fail(f"invalid target type for relation: {relation_id} {relation['relation']}->{target_type}")

        if relation["review_status"] == "approved":
            approved += 1
            if not relation["evidence_chunk_ids"]:
                fail(f"approved relation must have evidence_chunk_ids: {relation_id}")
        if relation["review_status"] == "pending":
            pending += 1
        relation_counter[relation["relation"]] += 1

    print("OK: graph data is valid")
    print(f"OK: entities={len(entities)} relations={len(relations)} pending={pending} approved={approved}")
    print("OK: relation distribution=" + ", ".join(f"{k}:{v}" for k, v in sorted(relation_counter.items())))


if __name__ == "__main__":
    sys.exit(main())
