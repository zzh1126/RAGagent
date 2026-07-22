from __future__ import annotations

import json
import pickle
import shutil
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_tfidf_fallback(chunks: list[dict], index_dir: Path) -> None:
    from sklearn.feature_extraction.text import TfidfVectorizer

    index_dir.mkdir(parents=True, exist_ok=True)
    texts = [chunk["embedding_text"] for chunk in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=50000,
    )
    matrix = vectorizer.fit_transform(texts)
    with (index_dir / "tfidf_vectorizer.pkl").open("wb") as f:
        pickle.dump(vectorizer, f)
    with (index_dir / "tfidf_matrix.pkl").open("wb") as f:
        pickle.dump(matrix, f)
    with (index_dir / "chunks_snapshot.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"OK: built TF-IDF fallback index docs={len(chunks)} dir={index_dir}")


def build_chroma(chunks: list[dict], index_dir: Path, collection_name: str) -> None:
    try:
        import chromadb
    except Exception as exc:
        print(f"WARN: Chroma backend unavailable ({exc}); building TF-IDF fallback only")
        build_tfidf_fallback(chunks, index_dir / "tfidf")
        return

    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [chunk["embedding_text"] for chunk in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=8192,
    )
    matrix = vectorizer.fit_transform(texts)
    dense_embeddings = matrix.toarray().tolist()

    index_dir.mkdir(parents=True, exist_ok=True)
    with (index_dir / "tfidf_vectorizer.pkl").open("wb") as f:
        pickle.dump(vectorizer, f)
    with (index_dir / "tfidf_matrix.pkl").open("wb") as f:
        pickle.dump(matrix, f)
    with (index_dir / "chunks_snapshot.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
    existing = [collection.name for collection in client.list_collections()]
    if collection_name in existing:
        client.delete_collection(collection_name)
    collection = client.create_collection(collection_name)
    collection.add(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=texts,
        metadatas=[
            {
                "source_id": chunk["source_id"],
                "page_title": chunk["page_title"],
                "heading_path": " > ".join(chunk["heading_path"]),
                "url": chunk["url"],
                "language": chunk["language"],
            }
            for chunk in chunks
        ],
        embeddings=dense_embeddings,
    )
    print(f"OK: built Chroma collection={collection_name} docs={len(chunks)} dir={index_dir / 'chroma'}")


def main() -> None:
    settings = yaml.safe_load((PROJECT_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    chunks_path = PROJECT_ROOT / settings["paths"]["chunks"]
    index_dir = PROJECT_ROOT / settings["paths"]["chroma"]
    collection_name = settings["retrieval"]["collection"]
    chunks = read_jsonl(chunks_path)
    build_chroma(chunks, index_dir, collection_name)


if __name__ == "__main__":
    sys.exit(main())
