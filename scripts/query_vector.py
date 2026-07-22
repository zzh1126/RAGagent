from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.vector_retriever import TfidfVectorRetriever


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "随机森林为什么更稳定"
    retriever = TfidfVectorRetriever(PROJECT_ROOT / "data" / "chroma" / "tfidf")
    results = retriever.query(query, top_k=5)
    print(f"QUERY: {query}")
    for item in results:
        heading = " > ".join(item.heading_path)
        print(f"{item.evidence_id} {item.chunk_id} score={item.score:.4f} {item.source_id} {heading}")
        print(f"URL: {item.url}")
        print(item.display_text[:240].replace('\n', ' ') + "...")


if __name__ == "__main__":
    main()
