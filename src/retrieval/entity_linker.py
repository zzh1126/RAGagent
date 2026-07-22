from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EntityCandidate:
    entity_id: str
    name_en: str
    name_zh: str
    type: str
    matched_text: str
    score: float


class EntityLinker:
    def __init__(self, entities_path: Path):
        self.entities_path = entities_path
        self.entities = self._load_entities()

    def _load_entities(self) -> list[dict]:
        with self.entities_path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def link(self, query: str, top_k: int = 3) -> list[EntityCandidate]:
        lowered = query.lower()
        scored: list[EntityCandidate] = []
        for entity in self.entities:
            names = [entity["name_zh"], entity["name_en"], entity["entity_id"]]
            aliases = [x for x in entity.get("aliases", "").split("|") if x]
            names.extend(aliases)
            matched: list[str] = []
            score = 0.0
            for name in names:
                if not name:
                    continue
                normalized_name = self._normalize_variant(name)
                if name.lower() in lowered or (normalized_name and normalized_name in self._normalize_variant(lowered)):
                    matched.append(name)
                    score += max(1.0, min(4.0, len(normalized_name or name) / 3.0))
            if matched:
                scored.append(
                    EntityCandidate(
                        entity_id=entity["entity_id"],
                        name_en=entity["name_en"],
                        name_zh=entity["name_zh"],
                        type=entity["type"],
                        matched_text="|".join(dict.fromkeys(matched)),
                        score=score,
                    )
                )
        if scored:
            return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

        fallback_terms = self._fallback_terms(query)
        for entity in self.entities:
            haystack = " ".join(
                [entity["name_zh"], entity["name_en"], entity.get("aliases", ""), entity.get("description_zh", "")]
            ).lower()
            score = sum(1.0 for term in fallback_terms if term and term in haystack)
            if score > 0:
                scored.append(
                    EntityCandidate(
                        entity_id=entity["entity_id"],
                        name_en=entity["name_en"],
                        name_zh=entity["name_zh"],
                        type=entity["type"],
                        matched_text="|".join(fallback_terms),
                        score=score,
                    )
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def canonical_name(self, entity_id: str) -> str | None:
        for entity in self.entities:
            if entity["entity_id"] == entity_id:
                return entity["name_zh"]
        return None

    @staticmethod
    def _fallback_terms(query: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query.lower())
        return [token for token in tokens if len(token) > 1]

    @staticmethod
    def _normalize_variant(text: str) -> str:
        """Treat common Chinese type suffixes as optional for entity linking."""
        return re.sub(r"(问题|方法|模型|算法|指标)$", "", text.lower())
