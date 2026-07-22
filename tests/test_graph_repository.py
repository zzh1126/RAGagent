from pathlib import Path

from src.graph.networkx_repository import NetworkXGraphRepository


ROOT = Path(__file__).resolve().parents[1]


def test_networkx_repository_finds_random_forest_pending_graph():
    repo = NetworkXGraphRepository(
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "graph" / "relations.csv",
        approved_only=False,
    )

    entity = repo.find_entity("随机森林")
    assert entity is not None
    assert entity["entity_id"] == "ALG_RF"

    triples = repo.get_neighbors("ALG_RF")
    observed = {(row["relation"], row["target_name"]) for row in triples}

    assert ("BELONGS_TO", "集成学习") in observed
    assert ("USES", "决策树") in observed
    assert ("HAS_ADVANTAGE", "方差") in observed


def test_runtime_repository_filters_pending_relations():
    repo = NetworkXGraphRepository(
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "graph" / "relations.csv",
        approved_only=True,
    )

    assert repo.find_entity("RandomForestClassifier")["entity_id"] == "ALG_RF"
    neighbors = repo.get_neighbors("ALG_RF")
    assert neighbors
    assert all(row["review_status"] == "approved" for row in neighbors)
