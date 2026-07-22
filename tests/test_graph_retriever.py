from pathlib import Path

from src.graph.networkx_repository import NetworkXGraphRepository
from src.retrieval.graph_retriever import GraphRetriever


ROOT = Path(__file__).resolve().parents[1]


def test_graph_retriever_links_random_forest():
    repo = NetworkXGraphRepository(
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "graph" / "relations.csv",
        approved_only=True,
    )
    retriever = GraphRetriever(
        repo,
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "chroma" / "chunks_snapshot.jsonl",
    )

    result = retriever.retrieve("随机森林属于什么模型族", intent="relation")

    assert result.entities
    assert any(entity.entity_id == "ALG_RF" for entity in result.entities)
    assert result.graph_paths
    assert any(path.evidence_chunk_ids for path in result.graph_paths)


def test_graph_retriever_supports_compare_style_query():
    repo = NetworkXGraphRepository(
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "graph" / "relations.csv",
        approved_only=True,
    )
    retriever = GraphRetriever(
        repo,
        ROOT / "data" / "graph" / "entities.csv",
        ROOT / "data" / "chroma" / "chunks_snapshot.jsonl",
    )

    result = retriever.retrieve("Bagging 和 Boosting 有什么区别", intent="comparison")

    assert result.entities
    assert result.graph_paths
