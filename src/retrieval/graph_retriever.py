from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.retrieval.entity_linker import EntityLinker
from src.schemas import GraphPath, GraphTriple, LinkedEntity, TextEvidence


@dataclass
class GraphRetrievalResult:
    entities: list[LinkedEntity]
    graph_paths: list[GraphPath]
    text_evidence: list[TextEvidence]


class GraphRetriever:
    def __init__(self, graph_repo, entities_path: Path, chunks_path: Path):
        self.graph_repo = graph_repo
        self.entity_linker = EntityLinker(entities_path)
        self.chunks_by_id = self._load_chunks(chunks_path)

    def retrieve(self, query: str, intent: str = "relation") -> GraphRetrievalResult:
        linked = self.entity_linker.link(query, top_k=3)
        entities = self._to_linked_entities(linked)
        graph_paths = self._route(query, intent, linked)
        text_evidence = self._paths_to_text_evidence(graph_paths)
        return GraphRetrievalResult(entities=entities, graph_paths=graph_paths, text_evidence=text_evidence)

    def link_entities(self, query: str, top_k: int = 3) -> list[LinkedEntity]:
        return self._to_linked_entities(self.entity_linker.link(query, top_k=top_k))

    def _route(self, query: str, intent: str, linked) -> list[GraphPath]:
        if not linked:
            return []
        relation_types = self._relation_types_for_query(query, intent)
        if intent == "comparison" and len(linked) >= 2:
            paths = self.graph_repo.find_paths(linked[0].entity_id, linked[1].entity_id, max_hops=2)
            if not paths:
                paths = self.graph_repo.find_paths(linked[1].entity_id, linked[0].entity_id, max_hops=2)
            if paths:
                difference_paths = [
                    row for row in paths if any(triple["relation"] == "DIFFERS_FROM" for triple in row["triples"])
                ]
                if difference_paths:
                    return [
                        self._to_graph_path(f"P{i+1}", row["triples"])
                        for i, row in enumerate(difference_paths[:3])
                    ]
            comparison_paths: list[GraphPath] = []
            seen_relations: set[str] = set()
            for entity in linked[:2]:
                neighbors = self.graph_repo.get_neighbors(
                    entity.entity_id,
                    relation_types=["DIFFERS_FROM", "HAS_ADVANTAGE", "HAS_LIMITATION"],
                )
                for path in self._neighbors_to_paths(entity.entity_id, neighbors, limit=3):
                    relation_id = path.triples[0].relation_id
                    if relation_id not in seen_relations:
                        comparison_paths.append(path)
                        seen_relations.add(relation_id)
            if comparison_paths:
                return comparison_paths[:6]
        if intent == "multi_hop":
            source_id = linked[0].entity_id
            multi_paths: list[dict] = []
            targets = linked[1:] if len(linked) >= 2 else [None]
            for target in targets:
                target_id = target.entity_id if target is not None else None
                paths = self.graph_repo.find_paths(source_id, target_id, max_hops=2)
                if not paths and target_id is not None:
                    paths = self.graph_repo.find_paths(target_id, source_id, max_hops=2)
                if paths:
                    shortest_hops = min(len(row["triples"]) for row in paths)
                    paths = [row for row in paths if len(row["triples"]) == shortest_hops]
                multi_paths.extend(paths[:3])
            if multi_paths:
                return [
                    self._to_graph_path(f"P{i+1}", row["triples"])
                    for i, row in enumerate(multi_paths[:6])
                ]

        if intent == "recommendation":
            recommendation_paths: list[GraphPath] = []
            seen_relations: set[str] = set()
            for entity in linked:
                neighbors = self.graph_repo.get_neighbors(entity.entity_id, relation_types=relation_types)
                if not neighbors and relation_types:
                    neighbors = self.graph_repo.get_neighbors(entity.entity_id)
                for path in self._neighbors_to_paths(entity.entity_id, neighbors, limit=3):
                    relation_id = path.triples[0].relation_id
                    if relation_id not in seen_relations:
                        recommendation_paths.append(path)
                        seen_relations.add(relation_id)
            if recommendation_paths:
                return recommendation_paths[:6]

        ordered_entities = sorted(linked, key=lambda item: item.type != "Algorithm")
        for entity in ordered_entities:
            neighbors = self.graph_repo.get_neighbors(entity.entity_id, relation_types=relation_types)
            if not neighbors and relation_types:
                neighbors = self.graph_repo.get_neighbors(entity.entity_id)
            if neighbors:
                return self._neighbors_to_paths(entity.entity_id, neighbors, limit=6)
        return []

    def _neighbors_to_paths(self, entity_id: str, neighbors: list[dict], limit: int = 4) -> list[GraphPath]:
        paths: list[GraphPath] = []
        for idx, row in enumerate(neighbors[:limit], start=1):
            triple = GraphTriple(**row)
            paths.append(GraphPath(path_id=f"P{idx}", triples=[triple], evidence_chunk_ids=triple.evidence_chunk_ids))
        return paths

    def _to_graph_path(self, path_id: str, triples: list[dict]) -> GraphPath:
        graph_triples = [GraphTriple(**triple) for triple in triples]
        evidence_chunk_ids = []
        for triple in graph_triples:
            evidence_chunk_ids.extend(triple.evidence_chunk_ids)
        return GraphPath(path_id=path_id, triples=graph_triples, evidence_chunk_ids=list(dict.fromkeys(evidence_chunk_ids)))

    def _paths_to_text_evidence(self, paths: list[GraphPath]) -> list[TextEvidence]:
        seen: set[str] = set()
        evidence: list[TextEvidence] = []
        idx = 1
        for path in paths:
            for chunk_id in path.evidence_chunk_ids:
                if chunk_id in seen:
                    continue
                chunk = self.chunks_by_id.get(chunk_id)
                if not chunk:
                    continue
                seen.add(chunk_id)
                evidence.append(
                    TextEvidence(
                        evidence_id=f"E{idx}",
                        chunk_id=chunk["chunk_id"],
                        source_id=chunk["source_id"],
                        page_title=chunk["page_title"],
                        heading_path=chunk["heading_path"],
                        url=chunk["url"],
                        display_text=chunk["display_text"],
                        score=1.0,
                    )
                )
                idx += 1
        return evidence

    @staticmethod
    def _to_linked_entities(linked) -> list[LinkedEntity]:
        return [
            LinkedEntity(
                entity_id=item.entity_id,
                name_en=item.name_en,
                name_zh=item.name_zh,
                type=item.type,
                matched_text=item.matched_text,
                score=item.score,
            )
            for item in linked
        ]

    @staticmethod
    def _relation_types_for_query(query: str, intent: str) -> list[str] | None:
        lowered = query.lower()
        mappings = [
            (("属于", "模型族", "belongs"), ["BELONGS_TO"]),
            (("使用", "基于", "uses"), ["USES", "REQUIRES"]),
            (("需要", "要求", "requires"), ["REQUIRES"]),
            (("解决", "用于", "任务", "solve"), ["SOLVES"]),
            (("不平衡", "imbalanc"), ["HAS_ADVANTAGE", "HAS_LIMITATION", "EVALUATED_BY"]),
            (("评估", "指标", "metric", "score"), ["EVALUATED_BY", "HAS_ADVANTAGE", "HAS_LIMITATION"]),
            (("优点", "优势", "稳定", "advantage"), ["HAS_ADVANTAGE", "MITIGATES"]),
            (("缺点", "局限", "限制", "limitation"), ["HAS_LIMITATION"]),
            (("方差", "variance"), ["HAS_ADVANTAGE"]),
            (("过拟合", "overfit"), ["HAS_LIMITATION", "MITIGATES"]),
            (("缓解", "mitigate"), ["MITIGATES"]),
            (("区别", "不同", "比较", "difference"), ["DIFFERS_FROM"]),
        ]
        for markers, relation_types in mappings:
            if any(marker in lowered for marker in markers):
                return relation_types
        if intent == "comparison":
            return ["DIFFERS_FROM"]
        return None

    @staticmethod
    def _load_chunks(path: Path) -> dict[str, dict]:
        with path.open("r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        return {row["chunk_id"]: row for row in rows}
