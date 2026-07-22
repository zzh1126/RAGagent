from __future__ import annotations

import json
import pickle
from pathlib import Path

from src.retrieval.query_rewrite import rewrite_query_to_english
from src.schemas import TextEvidence


class TfidfVectorRetriever:
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.chunks = self._read_jsonl(index_dir / "chunks_snapshot.jsonl")
        with (index_dir / "tfidf_vectorizer.pkl").open("rb") as f:
            self.vectorizer = pickle.load(f)
        with (index_dir / "tfidf_matrix.pkl").open("rb") as f:
            self.matrix = pickle.load(f)

    def query(self, query: str, top_k: int = 5) -> list[TextEvidence]:
        query_en = rewrite_query_to_english(query)
        results = self._query_once(query, top_k=top_k * 2)
        if query_en != query:
            results.extend(self._query_once(query_en, top_k=top_k * 2))
        return self._merge(results, top_k)

    def _query_once(self, query: str, top_k: int) -> list[tuple[float, dict]]:
        query_vec = self.vectorizer.transform([query])
        scores = (self.matrix @ query_vec.T).toarray().ravel()
        ranked = scores.argsort()[::-1][:top_k]
        return [(float(scores[i]), self.chunks[int(i)]) for i in ranked if scores[i] > 0]

    def _merge(self, rows: list[tuple[float, dict]], top_k: int) -> list[TextEvidence]:
        best: dict[str, tuple[float, dict]] = {}
        for score, chunk in rows:
            chunk_id = chunk["chunk_id"]
            if chunk_id not in best or score > best[chunk_id][0]:
                best[chunk_id] = (score, chunk)
        ranked = sorted(best.values(), key=lambda item: item[0], reverse=True)[:top_k]
        evidence = []
        for idx, (score, chunk) in enumerate(ranked, start=1):
            evidence.append(
                TextEvidence(
                    evidence_id=f"E{idx}",
                    chunk_id=chunk["chunk_id"],
                    source_id=chunk["source_id"],
                    page_title=chunk["page_title"],
                    heading_path=chunk["heading_path"],
                    url=chunk["url"],
                    display_text=chunk["display_text"],
                    score=score,
                )
            )
        return evidence

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
