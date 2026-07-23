from __future__ import annotations

import re
import time
from dataclasses import dataclass

from src.retrieval.query_rewrite import rewrite_query_to_english
from src.schemas import (
    EvidencePack,
    EvidencePackingTrace,
    GraphPath,
    LinkedEntity,
    RetrievalResult,
    TextEvidence,
)


@dataclass(frozen=True)
class _Candidate:
    item: TextEvidence
    original_index: int
    path_ids: tuple[str, ...]
    title_entity_ids: tuple[str, ...]
    text_entity_ids: tuple[str, ...]
    query_hits: int
    intent_tags: tuple[str, ...]

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([*self.title_entity_ids, *self.text_entity_ids]))


class EvidencePacker:
    VERSION = "intent_aware_v2"
    _EXPLANATION_TAGS = (
        "explanation_mechanism",
        "explanation_advantage",
        "explanation_limitation",
    )
    _RECOMMENDATION_TAGS = (
        "recommendation_definition",
        "recommendation_scenario",
    )
    _EXPLANATION_MARKERS = {
        "explanation_mechanism": (
            "mechanism",
            "works by",
            "based on",
            "training",
            "algorithm",
            "averaging",
            "sampling",
        ),
        "explanation_advantage": (
            "advantage",
            "benefit",
            "reduce",
            "variance",
            "robust",
            "improve",
            "strength",
        ),
        "explanation_limitation": (
            "limitation",
            "drawback",
            "disadvantage",
            "overfit",
            "sensitive",
            "memory",
            "computational",
        ),
    }
    _RECOMMENDATION_MARKERS = {
        "recommendation_definition": (
            "metric",
            "score",
            "defined as",
            "definition",
            "function computes",
        ),
        "recommendation_scenario": (
            "when",
            "suitable",
            "useful",
            "imbalanced",
            "classification",
            "regression",
            "multiclass",
        ),
    }
    _INTENT_TARGETS = {
        "definition": 4,
        "relation": 4,
        "recommendation": 4,
        "comparison": 6,
        "explanation": 6,
        "multi_hop": 6,
        "general": 6,
    }
    _REASON_ORDER = (
        "multi_hop_path_coverage",
        "graph_path_bound",
        "comparison_entity_balance",
        "definition_direct",
        "explanation_mechanism",
        "explanation_advantage",
        "explanation_limitation",
        "recommendation_definition",
        "recommendation_scenario",
        "direct_relation",
        "entity_title_match",
        "entity_text_match",
        "query_term_match",
        "relevance_rank",
    )

    def __init__(
        self,
        *,
        max_text_evidence: int = 8,
        max_graph_paths: int = 8,
        max_chars_per_evidence: int = 900,
        max_context_chars: int = 10000,
        comparison_evidence_per_entity: int = 2,
    ) -> None:
        if max_text_evidence < 1:
            raise ValueError("max_text_evidence must be at least 1")
        if max_graph_paths < 0:
            raise ValueError("max_graph_paths cannot be negative")
        if max_chars_per_evidence < 1:
            raise ValueError("max_chars_per_evidence must be at least 1")
        if max_context_chars < 1000:
            raise ValueError("max_context_chars must be at least 1000")
        if comparison_evidence_per_entity < 1:
            raise ValueError("comparison_evidence_per_entity must be at least 1")
        self.max_text_evidence = max_text_evidence
        self.max_graph_paths = max_graph_paths
        self.max_chars_per_evidence = max_chars_per_evidence
        self.max_context_chars = max_context_chars
        self.comparison_evidence_per_entity = comparison_evidence_per_entity

    def pack(self, query: str, retrieval: RetrievalResult) -> EvidencePack:
        started_at = time.perf_counter()
        paths: list[GraphPath] = []
        seen_path_ids: set[str] = set()
        if self.max_graph_paths:
            for path in retrieval.graph_paths:
                if path.path_id in seen_path_ids:
                    continue
                paths.append(path.model_copy(deep=True))
                seen_path_ids.add(path.path_id)
                if len(paths) >= self.max_graph_paths:
                    break
        candidates = self._build_candidates(query, retrieval, paths)
        selected, reasons, selection_target = self._select_candidates(
            retrieval,
            paths,
            candidates,
        )

        dropped_for_structure: list[str] = []
        dropped_paths_for_structure: list[str] = []
        fixed_context = self._render(query, retrieval, paths, selected, {})
        while len(fixed_context) > self.max_context_chars:
            if len(selected) > 1:
                dropped_for_structure.append(selected.pop().item.evidence_id)
            elif paths:
                dropped_paths_for_structure.append(paths.pop().path_id)
            else:
                raise ValueError("max_context_chars cannot hold the fixed evidence metadata")
            fixed_context = self._render(query, retrieval, paths, selected, {})

        available_text_chars = self.max_context_chars - len(fixed_context)
        text_limits = self._allocate_text_limits(selected, available_text_chars)
        context = self._render(query, retrieval, paths, selected, text_limits)
        if len(context) > self.max_context_chars:
            raise RuntimeError("evidence packer exceeded its context character budget")

        selected_items = [candidate.item.model_copy(deep=True) for candidate in selected]
        selected_ids = [item.evidence_id for item in selected_items]
        selected_chunks = [item.chunk_id for item in selected_items]
        selected_path_ids = [path.path_id for path in paths]
        active_path_ids = set(selected_path_ids)
        reason_codes = {
            candidate.item.evidence_id: self._ordered_reasons(
                self._visible_reasons(
                    reasons.get(candidate.item.evidence_id, set()),
                    candidate,
                    active_path_ids,
                )
            )
            for candidate in selected
        }
        entity_coverage = {
            entity.entity_id: sum(
                entity.entity_id in candidate.entity_ids for candidate in selected
            )
            for entity in retrieval.entities
        }
        coverage_gaps = self._coverage_gaps(
            retrieval,
            paths,
            selected,
            entity_coverage,
        )
        coverage_gaps.extend(
            f"context_budget_dropped:{evidence_id}"
            for evidence_id in dropped_for_structure
        )
        coverage_gaps.extend(
            f"context_budget_dropped_path:{path_id}"
            for path_id in dropped_paths_for_structure
        )
        dropped_ids = [
            item.evidence_id
            for item in retrieval.text_evidence
            if item.evidence_id not in selected_ids
        ]
        truncated_ids = [
            candidate.item.evidence_id
            for candidate in selected
            if text_limits.get(candidate.item.evidence_id, 0)
            < len(self._normalize(candidate.item.display_text))
        ]
        latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
        trace = EvidencePackingTrace(
            intent=retrieval.intent,
            selected_evidence_ids=selected_ids,
            selected_chunk_ids=selected_chunks,
            selected_graph_path_ids=selected_path_ids,
            reason_codes_by_evidence=reason_codes,
            entity_coverage=entity_coverage,
            coverage_gaps=list(dict.fromkeys(coverage_gaps)),
            truncated_evidence_ids=truncated_ids,
            dropped_evidence_ids=dropped_ids,
            input_evidence_count=len(retrieval.text_evidence),
            deduplicated_evidence_count=len(candidates),
            input_character_count=sum(
                len(self._normalize(item.display_text))
                for item in retrieval.text_evidence
            ),
            packed_character_count=len(context),
            selection_target=selection_target,
            max_text_evidence=self.max_text_evidence,
            max_graph_paths=self.max_graph_paths,
            max_context_chars=self.max_context_chars,
            evidence_packing_latency_ms=latency_ms,
        )
        return EvidencePack(
            context=context,
            graph_paths=paths,
            text_evidence=selected_items,
            trace=trace,
        )

    def _build_candidates(
        self,
        query: str,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
    ) -> list[_Candidate]:
        unique_items: list[tuple[int, TextEvidence]] = []
        seen_chunks: set[str] = set()
        seen_evidence_ids: set[str] = set()
        for index, item in enumerate(retrieval.text_evidence):
            if item.chunk_id in seen_chunks or item.evidence_id in seen_evidence_ids:
                continue
            seen_chunks.add(item.chunk_id)
            seen_evidence_ids.add(item.evidence_id)
            unique_items.append((index, item))

        path_ids_by_chunk: dict[str, list[str]] = {}
        for path in paths:
            for chunk_id in path.evidence_chunk_ids:
                path_ids_by_chunk.setdefault(chunk_id, []).append(path.path_id)

        query_terms = self._query_terms(query)
        candidates: list[_Candidate] = []
        for original_index, item in unique_items:
            title_text = self._normalize(
                " ".join([item.page_title, *item.heading_path])
            ).casefold()
            full_text = self._normalize(
                " ".join([item.page_title, *item.heading_path, item.display_text])
            ).casefold()
            title_entities = tuple(
                entity.entity_id
                for entity in retrieval.entities
                if self._matches_entity(title_text, entity)
            )
            text_entities = tuple(
                entity.entity_id
                for entity in retrieval.entities
                if entity.entity_id not in title_entities
                and self._matches_entity(full_text, entity)
            )
            candidates.append(
                _Candidate(
                    item=item,
                    original_index=original_index,
                    path_ids=tuple(path_ids_by_chunk.get(item.chunk_id, [])),
                    title_entity_ids=title_entities,
                    text_entity_ids=text_entities,
                    query_hits=sum(term in full_text for term in query_terms),
                    intent_tags=self._intent_tags(retrieval.intent, full_text),
                )
            )
        return candidates

    def _select_candidates(
        self,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], dict[str, set[str]], int]:
        ranked = sorted(candidates, key=self._rank_key)
        selection_target = min(
            self.max_text_evidence,
            self._INTENT_TARGETS.get(retrieval.intent, self.max_text_evidence),
        )
        selected: list[_Candidate] = []
        selected_chunks: set[str] = set()
        reasons: dict[str, set[str]] = {}

        def add(candidate: _Candidate, reason: str) -> bool:
            evidence_id = candidate.item.evidence_id
            reason_set = reasons.setdefault(evidence_id, set())
            reason_set.update(self._intrinsic_reasons(candidate))
            reason_set.add(reason)
            if candidate.item.chunk_id in selected_chunks:
                return True
            if len(selected) >= selection_target:
                return False
            selected.append(candidate)
            selected_chunks.add(candidate.item.chunk_id)
            return True

        graph_slots = (
            selection_target
            if retrieval.intent == "multi_hop"
            else max(1, selection_target // 2)
        )
        for path in paths:
            bound = [candidate for candidate in ranked if path.path_id in candidate.path_ids]
            if not bound:
                continue
            if retrieval.intent != "multi_hop" and len(selected) >= graph_slots:
                break
            add(
                bound[0],
                "multi_hop_path_coverage"
                if retrieval.intent == "multi_hop"
                else "graph_path_bound",
            )

        if retrieval.intent == "definition":
            direct = [candidate for candidate in ranked if candidate.title_entity_ids]
            for candidate in direct[: min(2, selection_target)]:
                add(candidate, "definition_direct")

        if retrieval.intent == "comparison":
            for entity in retrieval.entities[:2]:
                matching = [
                    candidate for candidate in ranked if entity.entity_id in candidate.entity_ids
                ]
                for candidate in matching:
                    current = sum(
                        entity.entity_id in selected_candidate.entity_ids
                        for selected_candidate in selected
                    )
                    if current >= self.comparison_evidence_per_entity:
                        break
                    add(candidate, "comparison_entity_balance")

        if retrieval.intent == "explanation":
            for tag in self._EXPLANATION_TAGS:
                tagged = [candidate for candidate in ranked if tag in candidate.intent_tags]
                if tagged:
                    tagged.sort(
                        key=lambda candidate: (
                            candidate.item.chunk_id in selected_chunks,
                            len(candidate.intent_tags),
                        )
                    )
                    add(tagged[0], tag)

        if retrieval.intent == "recommendation":
            for tag in self._RECOMMENDATION_TAGS:
                tagged = [candidate for candidate in ranked if tag in candidate.intent_tags]
                if tagged:
                    tagged.sort(
                        key=lambda candidate: (
                            candidate.item.chunk_id in selected_chunks,
                            len(candidate.intent_tags),
                        )
                    )
                    add(tagged[0], tag)

        if retrieval.intent == "relation":
            direct = [candidate for candidate in ranked if candidate.title_entity_ids]
            if direct:
                add(direct[0], "direct_relation")

        for candidate in ranked:
            if len(selected) >= selection_target:
                break
            add(candidate, "relevance_rank")
        return selected, reasons, selection_target

    def _coverage_gaps(
        self,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
        selected: list[_Candidate],
        entity_coverage: dict[str, int],
    ) -> list[str]:
        gaps: list[str] = []
        if not selected:
            return ["no_text_evidence"]
        if retrieval.intent == "definition" and not any(
            candidate.title_entity_ids for candidate in selected
        ):
            target = retrieval.entities[0].entity_id if retrieval.entities else "unknown"
            gaps.append(f"definition_direct_evidence_missing:{target}")
        if retrieval.intent == "comparison":
            for entity in retrieval.entities[:2]:
                count = entity_coverage.get(entity.entity_id, 0)
                if count < self.comparison_evidence_per_entity:
                    gaps.append(
                        "comparison_entity_under_quota:"
                        f"{entity.entity_id}:{count}/{self.comparison_evidence_per_entity}"
                    )
        if retrieval.intent == "explanation":
            for tag in self._EXPLANATION_TAGS:
                if not any(tag in candidate.intent_tags for candidate in selected):
                    gaps.append(f"explanation_missing:{tag.removeprefix('explanation_')}")
        if retrieval.intent == "multi_hop":
            selected_chunks = {candidate.item.chunk_id for candidate in selected}
            for path in paths:
                if not selected_chunks.intersection(path.evidence_chunk_ids):
                    gaps.append(f"multi_hop_path_uncovered:{path.path_id}")
        if retrieval.intent == "recommendation":
            for tag in self._RECOMMENDATION_TAGS:
                if not any(tag in candidate.intent_tags for candidate in selected):
                    gaps.append(
                        f"recommendation_missing:{tag.removeprefix('recommendation_')}"
                    )
        if retrieval.intent == "relation" and paths:
            visible_path_ids = {path.path_id for path in paths}
            if not any(
                visible_path_ids.intersection(candidate.path_ids)
                for candidate in selected
            ):
                gaps.append("relation_path_evidence_missing")
        return gaps

    def _render(
        self,
        query: str,
        retrieval: RetrievalResult,
        paths: list[GraphPath],
        evidence: list[_Candidate],
        text_limits: dict[str, int],
    ) -> str:
        entity_lines = [
            (
                f"- {entity.entity_id}: {self._truncate(entity.name_zh, 100)} "
                f"({self._truncate(entity.name_en, 100)}); type={entity.type}"
            )
            for entity in retrieval.entities
        ]
        path_blocks = [self._path_block(path) for path in paths]
        evidence_blocks = [
            self._evidence_block(
                candidate.item,
                text_limits.get(candidate.item.evidence_id, 0),
            )
            for candidate in evidence
        ]
        sections = [
            "QUESTION:\n" + self._truncate(self._normalize(query), 1000),
            f"INTENT: {retrieval.intent}\nRETRIEVAL_MODE: {retrieval.mode}",
            "LINKED_ENTITIES:\n" + ("\n".join(entity_lines) or "(none)"),
            "AVAILABLE_GRAPH_PATH_IDS: "
            + (", ".join(path.path_id for path in paths) or "(none)"),
            "GRAPH_PATHS:\n" + ("\n\n".join(path_blocks) or "(none)"),
            "AVAILABLE_TEXT_EVIDENCE_IDS: "
            + (", ".join(candidate.item.evidence_id for candidate in evidence) or "(none)"),
            "TEXT_EVIDENCE:\n" + ("\n\n".join(evidence_blocks) or "(none)"),
        ]
        return "\n\n".join(sections)

    def _allocate_text_limits(
        self,
        evidence: list[_Candidate],
        available_chars: int,
    ) -> dict[str, int]:
        remaining = max(0, available_chars)
        limits: dict[str, int] = {}
        for index, candidate in enumerate(evidence):
            remaining_items = len(evidence) - index
            fair_share = remaining // remaining_items if remaining_items else 0
            text_length = len(self._normalize(candidate.item.display_text))
            limit = min(self.max_chars_per_evidence, text_length, fair_share)
            limits[candidate.item.evidence_id] = limit
            remaining -= limit
        return limits

    @classmethod
    def _intrinsic_reasons(cls, candidate: _Candidate) -> set[str]:
        reasons = set(candidate.intent_tags)
        if candidate.path_ids:
            reasons.add("graph_path_bound")
        if candidate.title_entity_ids:
            reasons.add("entity_title_match")
        if candidate.text_entity_ids:
            reasons.add("entity_text_match")
        if candidate.query_hits:
            reasons.add("query_term_match")
        return reasons

    @staticmethod
    def _visible_reasons(
        reasons: set[str],
        candidate: _Candidate,
        active_path_ids: set[str],
    ) -> set[str]:
        visible = set(reasons)
        if not active_path_ids.intersection(candidate.path_ids):
            visible.discard("graph_path_bound")
            visible.discard("multi_hop_path_coverage")
        return visible

    @classmethod
    def _ordered_reasons(cls, reasons: set[str]) -> list[str]:
        order = {reason: index for index, reason in enumerate(cls._REASON_ORDER)}
        return sorted(reasons, key=lambda reason: (order.get(reason, len(order)), reason))

    @staticmethod
    def _rank_key(candidate: _Candidate) -> tuple:
        return (
            -bool(candidate.path_ids),
            -len(candidate.title_entity_ids),
            -len(candidate.intent_tags),
            -candidate.query_hits,
            -candidate.item.score,
            candidate.original_index,
            candidate.item.evidence_id,
        )

    @staticmethod
    def _path_block(path: GraphPath) -> str:
        triples = [
            (
                f"{EvidencePacker._truncate(triple.source_name, 120)} "
                f"({triple.source_id}) "
                f"-[{triple.relation}]-> "
                f"{EvidencePacker._truncate(triple.target_name, 120)} "
                f"({triple.target_id})"
                + (
                    "; relation_id=" + triple.relation_id
                    if triple.relation_id
                    else ""
                )
            )
            for triple in path.triples
        ]
        return (
            f"[{path.path_id}]\n"
            + ("\n".join(triples) or "(empty path)")
        )

    def _evidence_block(self, item: TextEvidence, text_limit: int) -> str:
        heading = self._truncate(
            self._normalize(" > ".join(item.heading_path)),
            500,
        ) or "(root)"
        text = self._truncate(self._normalize(item.display_text), text_limit)
        return (
            f"[{item.evidence_id}]\n"
            f"source_id={item.source_id}\n"
            f"page_title={self._truncate(self._normalize(item.page_title), 300)}\n"
            f"heading={heading}\n"
            f"url={self._truncate(item.url, 500)}\n"
            f"text={text}"
        )

    @classmethod
    def _intent_tags(cls, intent: str, searchable: str) -> tuple[str, ...]:
        tags: list[str] = []
        if intent == "explanation":
            for tag, markers in cls._EXPLANATION_MARKERS.items():
                if any(marker in searchable for marker in markers):
                    tags.append(tag)
        if intent == "recommendation":
            for tag, markers in cls._RECOMMENDATION_MARKERS.items():
                if any(marker in searchable for marker in markers):
                    tags.append(tag)
        return tuple(tags)

    @classmethod
    def _query_terms(cls, query: str) -> set[str]:
        rewritten = rewrite_query_to_english(query).casefold()
        return {
            term
            for term in rewritten.split()
            if len(term) >= 3 or term in {"f1", "r2"}
        }

    @classmethod
    def _matches_entity(cls, searchable: str, entity: LinkedEntity) -> bool:
        phrases = {
            cls._normalize(entity.name_en).casefold(),
            cls._normalize(entity.name_zh).casefold(),
            cls._normalize(entity.matched_text).casefold(),
        }
        if any(phrase and phrase in searchable for phrase in phrases):
            return True
        compact_searchable = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", searchable)
        compact_phrases = {
            re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", phrase)
            for phrase in phrases
        }
        return any(
            len(phrase) >= 4 and phrase in compact_searchable
            for phrase in compact_phrases
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip()
