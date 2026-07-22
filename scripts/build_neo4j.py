from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.networkx_repository import NetworkXGraphRepository


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def print_random_forest_smoke(repo) -> None:
    entity = repo.find_entity("随机森林")
    if not entity:
        raise SystemExit("ERROR: cannot find entity 随机森林")
    neighbors = repo.get_neighbors(
        entity["entity_id"],
        relation_types=["BELONGS_TO", "USES", "HAS_ADVANTAGE"],
    )
    required = {
        ("随机森林", "BELONGS_TO", "集成学习"),
        ("随机森林", "USES", "决策树"),
        ("随机森林", "HAS_ADVANTAGE", "方差"),
    }
    observed = {(row["source_name"], row["relation"], row["target_name"]) for row in neighbors}
    missing = required - observed
    if missing:
        raise SystemExit(f"ERROR: random forest smoke query missing triples: {sorted(missing)}")
    print("OK: random forest smoke query")
    for row in neighbors:
        print(f"{row['source_name']} -{row['relation']}-> {row['target_name']} [{row['review_status']}]")


def build_networkx() -> None:
    repo = NetworkXGraphRepository(
        PROJECT_ROOT / "data" / "graph" / "entities.csv",
        PROJECT_ROOT / "data" / "graph" / "relations.csv",
        approved_only=False,
    )
    print(f"OK: loaded NetworkX graph nodes={repo.graph.number_of_nodes()} edges={repo.graph.number_of_edges()}")
    print_random_forest_smoke(repo)


def build_neo4j() -> None:
    from neo4j import GraphDatabase

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    entities = read_csv(PROJECT_ROOT / "data" / "graph" / "entities.csv")
    relations = read_csv(PROJECT_ROOT / "data" / "graph" / "relations.csv")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE")
        for row in entities:
            aliases = [x for x in row.get("aliases", "").split("|") if x]
            session.run(
                """
                MERGE (e:Entity {entity_id: $entity_id})
                SET e.type = $type,
                    e.name_en = $name_en,
                    e.name_zh = $name_zh,
                    e.aliases = $aliases,
                    e.description_zh = $description_zh,
                    e.review_status = $review_status
                """,
                aliases=aliases,
                **row,
            )
        for row in relations:
            if row["review_status"] != "approved":
                continue
            rel_type = row["relation"]
            chunk_ids = [x for x in row.get("evidence_chunk_ids", "").split("|") if x]
            session.run(
                f"""
                MATCH (a:Entity {{entity_id: $source_id}})
                MATCH (b:Entity {{entity_id: $target_id}})
                MERGE (a)-[r:{rel_type} {{relation_id: $relation_id}}]->(b)
                SET r.evidence_source_id = $evidence_source_id,
                    r.evidence_chunk_ids = $evidence_chunk_ids,
                    r.confidence = toFloat($confidence),
                    r.review_status = $review_status,
                    r.notes = $notes
                """,
                evidence_chunk_ids=chunk_ids,
                **row,
            )
    driver.close()
    print(f"OK: imported Neo4j entities={len(entities)} approved_relations={sum(r['review_status'] == 'approved' for r in relations)}")


def main() -> None:
    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")
    backend = os.environ.get("GRAPH_BACKEND", "networkx").lower()
    if backend == "neo4j":
        build_neo4j()
    else:
        build_networkx()


if __name__ == "__main__":
    main()
