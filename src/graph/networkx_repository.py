from __future__ import annotations

import csv
from collections import deque
from pathlib import Path

import networkx as nx


class NetworkXGraphRepository:
    def __init__(self, entities_path: Path, relations_path: Path, approved_only: bool = True):
        self.entities_path = entities_path
        self.relations_path = relations_path
        self.approved_only = approved_only
        self.graph = nx.MultiDiGraph()
        self.alias_index: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        with self.entities_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                entity_id = row["entity_id"]
                self.graph.add_node(entity_id, **row)
                names = [row["name_en"], row["name_zh"], entity_id]
                names.extend(x for x in row.get("aliases", "").split("|") if x)
                for name in names:
                    self.alias_index[name.lower()] = entity_id

        with self.relations_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if self.approved_only and row.get("review_status") != "approved":
                    continue
                self.graph.add_edge(
                    row["source_id"],
                    row["target_id"],
                    key=row["relation_id"],
                    **row,
                )

    def find_entity(self, name: str) -> dict | None:
        entity_id = self.alias_index.get(name.lower())
        if not entity_id or entity_id not in self.graph:
            return None
        data = dict(self.graph.nodes[entity_id])
        data["entity_id"] = entity_id
        return data

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: list[str] | None = None,
        include_incoming: bool = True,
    ) -> list[dict]:
        if entity_id not in self.graph:
            return []
        relation_filter = set(relation_types or [])
        rows: list[dict] = []
        for _, target_id, _key, edge in self.graph.out_edges(entity_id, keys=True, data=True):
            if relation_filter and edge["relation"] not in relation_filter:
                continue
            rows.append(self._triple(entity_id, target_id, edge))
        if include_incoming:
            for source_id, _, _key, edge in self.graph.in_edges(entity_id, keys=True, data=True):
                if relation_filter and edge["relation"] not in relation_filter:
                    continue
                rows.append(self._triple(source_id, entity_id, edge))
        rows.sort(key=lambda row: (row["relation_id"], row["source_id"], row["target_id"]))
        return rows

    def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        if source_id not in self.graph:
            return []

        paths: list[dict] = []
        queue = deque([(source_id, [], {source_id})])
        while queue:
            node_id, triples, visited = queue.popleft()
            if triples and (target_id is None or node_id == target_id):
                paths.append({"triples": triples})
            if len(triples) >= max_hops:
                continue
            for _, next_id, _key, edge in self.graph.out_edges(node_id, keys=True, data=True):
                if next_id in visited:
                    continue
                queue.append((
                    next_id,
                    [*triples, self._triple(node_id, next_id, edge)],
                    {*visited, next_id},
                ))
        return paths

    def validate_path(self, triples: list[dict]) -> bool:
        for triple in triples:
            source_id = triple["source_id"]
            target_id = triple["target_id"]
            relation = triple["relation"]
            matched = False
            for _, _, edge in self.graph.out_edges(source_id, data=True):
                if edge["target_id"] == target_id and edge["relation"] == relation:
                    matched = True
                    break
            if not matched:
                return False
        return True

    def _triple(self, source_id: str, target_id: str, edge: dict) -> dict:
        source = self.graph.nodes[source_id]
        target = self.graph.nodes[target_id]
        chunks = [x for x in edge.get("evidence_chunk_ids", "").split("|") if x]
        return {
            "source_id": source_id,
            "source_name": source["name_zh"],
            "relation": edge["relation"],
            "target_id": target_id,
            "target_name": target["name_zh"],
            "relation_id": edge["relation_id"],
            "evidence_source_id": edge.get("evidence_source_id") or None,
            "evidence_chunk_ids": chunks,
            "review_status": edge.get("review_status", ""),
        }
