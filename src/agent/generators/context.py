from __future__ import annotations

from src.retrieval.query_rewrite import rewrite_query_to_english
from src.schemas import GraphPath, RetrievalResult, TextEvidence


class EvidenceContextSerializer:
    def __init__(
        self,
        *,
        max_text_evidence: int = 8,
        max_graph_paths: int = 8,
        max_chars_per_evidence: int = 900,
        max_context_chars: int = 10000,
    ) -> None:
        self.max_text_evidence = max_text_evidence
        self.max_graph_paths = max_graph_paths
        self.max_chars_per_evidence = max_chars_per_evidence
        self.max_context_chars = max_context_chars

    def serialize(self, query: str, retrieval: RetrievalResult) -> str:
        paths = list(retrieval.graph_paths[: self.max_graph_paths])
        evidence = self._select_evidence(query, retrieval, paths)
        rendered = self._render(query, retrieval, paths, evidence)

        while len(rendered) > self.max_context_chars and len(evidence) > 1:
            evidence.pop()
            rendered = self._render(query, retrieval, paths, evidence)
        while len(rendered) > self.max_context_chars and paths:
            paths.pop()
            rendered = self._render(query, retrieval, paths, evidence)
        if len(rendered) > self.max_context_chars:
            rendered = rendered[: self.max_context_chars].rstrip()
        return rendered

    def _select_evidence(
        self,
        query: str,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
    ) -> list[TextEvidence]:
        by_chunk = {item.chunk_id: item for item in retrieval.text_evidence}
        selected: list[TextEvidence] = []
        selected_chunks: set[str] = set()
        graph_budget = max(1, self.max_text_evidence // 2) if paths else 0

        for path in paths:
            for chunk_id in path.evidence_chunk_ids:
                item = by_chunk.get(chunk_id)
                if item is None or chunk_id in selected_chunks:
                    continue
                selected.append(item)
                selected_chunks.add(chunk_id)
                if len(selected) >= graph_budget:
                    break
            if len(selected) >= graph_budget:
                break

        if len(selected) >= self.max_text_evidence:
            return selected[: self.max_text_evidence]

        query_terms = self._query_terms(query)
        indexed = list(enumerate(retrieval.text_evidence))
        ranked = sorted(
            indexed,
            key=lambda row: (
                -self._term_hits(row[1], query_terms),
                -row[1].score,
                row[0],
            ),
        )
        for _, item in ranked:
            if item.chunk_id in selected_chunks:
                continue
            selected.append(item)
            selected_chunks.add(item.chunk_id)
            if len(selected) >= self.max_text_evidence:
                break
        return selected

    def _render(
        self,
        query: str,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
        evidence: list[TextEvidence],
    ) -> str:
        entity_lines = [
            f"- {entity.entity_id}: {entity.name_zh} ({entity.name_en}); type={entity.type}"
            for entity in retrieval.entities
        ]
        path_blocks = [self._path_block(path) for path in paths]
        evidence_blocks = [self._evidence_block(item) for item in evidence]
        sections = [
            "QUESTION:\n" + self._truncate(self._normalize(query), 1000),
            f"INTENT: {retrieval.intent}\nRETRIEVAL_MODE: {retrieval.mode}",
            "LINKED_ENTITIES:\n" + ("\n".join(entity_lines) or "(none)"),
            "AVAILABLE_GRAPH_PATH_IDS: "
            + (", ".join(path.path_id for path in paths) or "(none)"),
            "GRAPH_PATHS:\n" + ("\n\n".join(path_blocks) or "(none)"),
            "AVAILABLE_TEXT_EVIDENCE_IDS: "
            + (", ".join(item.evidence_id for item in evidence) or "(none)"),
            "TEXT_EVIDENCE:\n" + ("\n\n".join(evidence_blocks) or "(none)"),
        ]
        return "\n\n".join(sections)

    @staticmethod
    def _path_block(path: GraphPath) -> str:
        triples = [
            (
                f"{triple.source_name} ({triple.source_id}) "
                f"-[{triple.relation}]-> {triple.target_name} ({triple.target_id})"
                + (f"; relation_id={triple.relation_id}" if triple.relation_id else "")
            )
            for triple in path.triples
        ]
        return f"[{path.path_id}]\n" + ("\n".join(triples) or "(empty path)")

    def _evidence_block(self, item: TextEvidence) -> str:
        heading = " > ".join(item.heading_path) or "(root)"
        text = self._truncate(self._normalize(item.display_text), self.max_chars_per_evidence)
        return (
            f"[{item.evidence_id}]\n"
            f"source_id={item.source_id}\n"
            f"page_title={item.page_title}\n"
            f"heading={heading}\n"
            f"url={item.url}\n"
            f"text={text}"
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip()

    @staticmethod
    def _query_terms(query: str) -> set[str]:
        rewritten = rewrite_query_to_english(query).casefold()
        return {
            term
            for term in rewritten.split()
            if len(term) >= 3 or term in {"f1", "r2"}
        }

    @classmethod
    def _term_hits(cls, item: TextEvidence, query_terms: set[str]) -> int:
        searchable = cls._normalize(
            " ".join([item.page_title, *item.heading_path, item.display_text])
        ).casefold()
        return sum(term in searchable for term in query_terms)
