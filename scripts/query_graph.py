from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.networkx_repository import NetworkXGraphRepository
from src.retrieval.graph_retriever import GraphRetriever


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "随机森林属于什么模型族"
    repo = NetworkXGraphRepository(
        PROJECT_ROOT / "data" / "graph" / "entities.csv",
        PROJECT_ROOT / "data" / "graph" / "relations.csv",
        approved_only=True,
    )
    retriever = GraphRetriever(
        repo,
        PROJECT_ROOT / "data" / "graph" / "entities.csv",
        PROJECT_ROOT / "data" / "chroma" / "chunks_snapshot.jsonl",
    )
    result = retriever.retrieve(query, intent="relation")
    print(f"QUERY: {query}")
    for entity in result.entities:
        print(f"ENTITY {entity.entity_id} {entity.name_zh} score={entity.score:.2f} match={entity.matched_text}")
    for path in result.graph_paths:
        print(f"PATH {path.path_id} evidence={path.evidence_chunk_ids}")
        for triple in path.triples:
            print(f"  {triple.source_name} -{triple.relation}-> {triple.target_name} [{triple.review_status}]")
    for evidence in result.text_evidence:
        print(f"EVIDENCE {evidence.evidence_id} {evidence.chunk_id} {evidence.url}")


if __name__ == "__main__":
    main()
