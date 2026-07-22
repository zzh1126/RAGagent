from __future__ import annotations

from src.retrieval.graph_retriever import GraphRetriever
from src.retrieval.vector_retriever import TfidfVectorRetriever
from src.schemas import LinkedEntity, RetrievalMode, RetrievalResult, TextEvidence


class HybridRetriever:
    def __init__(
        self,
        vector_retriever: TfidfVectorRetriever,
        graph_retriever: GraphRetriever,
        default_top_k: int = 8,
    ):
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
        self.default_top_k = default_top_k

    def retrieve(
        self,
        query: str,
        intent: str,
        mode: RetrievalMode,
        top_k: int | None = None,
    ) -> RetrievalResult:
        limit = top_k or self.default_top_k
        entities: list[LinkedEntity] = []
        graph_paths = []
        graph_evidence: list[TextEvidence] = []
        vector_evidence: list[TextEvidence] = []

        if mode in {"graph", "hybrid"}:
            graph_result = self.graph_retriever.retrieve(query, intent=intent)
            entities = graph_result.entities
            graph_paths = graph_result.graph_paths
            graph_evidence = graph_result.text_evidence
        else:
            entities = self.graph_retriever.link_entities(query)

        if mode in {"vector", "hybrid"}:
            vector_evidence = self.vector_retriever.query(query, top_k=limit)

        evidence = self._merge_evidence(graph_evidence, vector_evidence, limit)
        return RetrievalResult(
            intent=intent,
            mode=mode,
            entities=entities,
            graph_paths=graph_paths,
            text_evidence=evidence,
        )

    @staticmethod
    def _merge_evidence(
        graph_evidence: list[TextEvidence],
        vector_evidence: list[TextEvidence],
        top_k: int,
    ) -> list[TextEvidence]:
        by_chunk: dict[str, TextEvidence] = {}
        order: list[str] = []
        for item in [*graph_evidence, *vector_evidence]:
            current = by_chunk.get(item.chunk_id)
            if current is None:
                by_chunk[item.chunk_id] = item.model_copy(deep=True)
                order.append(item.chunk_id)
            elif item.score > current.score:
                by_chunk[item.chunk_id] = item.model_copy(deep=True)

        merged: list[TextEvidence] = []
        for index, chunk_id in enumerate(order[:top_k], start=1):
            item = by_chunk[chunk_id]
            item.evidence_id = f"E{index}"
            merged.append(item)
        return merged
