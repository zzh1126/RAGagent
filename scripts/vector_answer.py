from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.vector_rag import build_vector_answer
from src.retrieval.vector_retriever import TfidfVectorRetriever


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "随机森林为什么更稳定"
    retriever = TfidfVectorRetriever(PROJECT_ROOT / "data" / "chroma" / "tfidf")
    evidence = retriever.query(query, top_k=5)
    print(build_vector_answer(query, evidence))


if __name__ == "__main__":
    main()
