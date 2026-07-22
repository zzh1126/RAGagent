from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "v1.0-baseline"
RELEASE_DIR = PROJECT_ROOT / "reports" / "releases" / VERSION

PAYLOAD_FILES = {
    "reports/evaluation_final.json": "evaluation_final.json",
    "reports/evaluation_pilot_postfix.json": "evaluation_pilot_postfix.json",
    "reports/streamlit_desktop_final.png": "screenshots/streamlit_desktop_final.png",
    "reports/streamlit_mobile_final.png": "screenshots/streamlit_mobile_final.png",
    "reports/streamlit_refuse.png": "screenshots/streamlit_refuse.png",
    "requirements.txt": "config_snapshot/requirements.txt",
    "config/settings.yaml": "config_snapshot/settings.yaml",
    "config/sources.yaml": "config_snapshot/sources.yaml",
    "config/ontology.yaml": "config_snapshot/ontology.yaml",
    "data/graph/entities.csv": "data_snapshot/entities.csv",
    "data/graph/relations.csv": "data_snapshot/relations.csv",
    "data/chroma/chunks_snapshot.jsonl": "data_snapshot/chunks_snapshot.jsonl",
    "data/evaluation/dev_questions.jsonl": "data_snapshot/evaluation/dev_questions.jsonl",
    "data/evaluation/demo_questions.jsonl": "data_snapshot/evaluation/demo_questions.jsonl",
    "data/evaluation/pilot_questions.jsonl": "data_snapshot/evaluation/pilot_questions.jsonl",
    "data/evaluation/final_questions.jsonl": "data_snapshot/evaluation/final_questions.jsonl",
    "data/evaluation/README.md": "data_snapshot/evaluation/README.md",
}

PACKAGE_NAMES = [
    "chromadb",
    "langgraph",
    "networkx",
    "neo4j",
    "numpy",
    "pydantic",
    "PyYAML",
    "scikit-learn",
    "sentence-transformers",
    "streamlit",
]

RELEASE_NOTES = """# v1.0 Baseline Release Notes

Frozen on 2026-07-22 before the main ablation and technical-enhancement work.

## Scope

- Six scikit-learn official documentation pages, 180 text chunks, 50 graph entities, and 100 approved graph relations with chunk-level evidence.
- Vector, graph, and hybrid retrieval with dynamic routing in a real LangGraph `StateGraph` workflow.
- A shared `GraphRepository` contract with a verified NetworkX backend and an optional Neo4j backend.
- Claim-level evidence verification, one retry, conservative refusal, and a Streamlit demonstration UI.
- Offline rule/template answer generation. This release does not call a production LLM API.

This is a lightweight Knowledge-Graph-Enhanced RAG implementation. It does not implement the complete Microsoft GraphRAG community-detection, community-summary, or global-search pipeline.

## Frozen Evaluation

- Final holdout: 40 questions, run once after freezing the question set.
- Decision accuracy: 39/40 (`0.9750`).
- Citation rate: `0.9750`.
- Mean keyword coverage: `0.8375`.
- Mean entity coverage: `0.9208`.
- No-answer refusal accuracy: 4/4 (`1.0000`, with a small sample).
- Mean local workflow latency: `1.48 ms`; this is a hot local rule-path measurement, not online LLM latency.
- Known failure: `T-DF-01`, an AdaBoost definition question, was conservatively refused.

The earlier 40-question set is archived as `pilot`; it was used to find implementation gaps and is not reported as an unseen final test.

## Runtime Status

- LangGraph `1.0.10` is installed and the workflow reports `engine=langgraph`.
- NetworkX is the default, fully offline graph backend.
- The Neo4j repository implementation and import script are present; an external Neo4j server is optional and was not required for the frozen final evaluation.
- Streamlit was verified at `http://localhost:8501` on desktop and mobile viewports. Pass and refusal paths were both exercised.
- Vector retrieval uses local TF-IDF representations, including the Chroma collection build; no neural dense embedding model is active in v1.0.

## Known Limitations

- Sparse TF-IDF retrieval has limited semantic recall for paraphrases and mixed-language terminology.
- Answer wording is rule/template based, so fluency and synthesis are intentionally limited.
- The final holdout contains 40 questions, including only four no-answer cases.
- The knowledge base is restricted to six selected scikit-learn pages.
- Neo4j requires an external service and credentials; NetworkX remains the reproducible fallback.

## Integrity And Source State

The workspace was not a Git repository at freeze time, so no commit or tag could be recorded. `source_snapshot.zip` preserves the executable source, tests, and project entry files. `manifest.json` records byte sizes and SHA-256 hashes for every archived payload, and `MANIFEST_SHA256.txt` anchors the manifest itself.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_command(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return result.returncode, output


def validate_sources() -> None:
    missing = [source for source in PAYLOAD_FILES if not (PROJECT_ROOT / source).is_file()]
    additional = [
        "data/processed/sections.jsonl",
        "reports/evaluation_final.json",
    ]
    missing.extend(path for path in additional if not (PROJECT_ROOT / path).is_file())
    if missing:
        raise FileNotFoundError("Missing baseline files: " + ", ".join(sorted(set(missing))))


def build_data_statistics(frozen_at: str) -> dict:
    entities = read_csv(PROJECT_ROOT / "data" / "graph" / "entities.csv")
    relations = read_csv(PROJECT_ROOT / "data" / "graph" / "relations.csv")
    sections = read_jsonl(PROJECT_ROOT / "data" / "processed" / "sections.jsonl")
    chunks = read_jsonl(PROJECT_ROOT / "data" / "chroma" / "chunks_snapshot.jsonl")
    evaluations = {
        split: read_jsonl(PROJECT_ROOT / "data" / "evaluation" / f"{split}_questions.jsonl")
        for split in ("dev", "demo", "pilot", "final")
    }
    final_report = json.loads(
        (PROJECT_ROOT / "reports" / "evaluation_final.json").read_text(encoding="utf-8")
    )
    final_questions = {row["question"] for row in evaluations["final"]}
    return {
        "version": VERSION,
        "frozen_at": frozen_at,
        "knowledge_base": {
            "source_count": len({row["source_id"] for row in chunks}),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "chunks_by_source": dict(sorted(Counter(row["source_id"] for row in chunks).items())),
        },
        "graph": {
            "entity_count": len(entities),
            "entities_by_type": dict(sorted(Counter(row["type"] for row in entities).items())),
            "entities_by_review_status": dict(
                sorted(Counter(row["review_status"] for row in entities).items())
            ),
            "relation_count": len(relations),
            "relations_by_type": dict(sorted(Counter(row["relation"] for row in relations).items())),
            "relations_by_review_status": dict(
                sorted(Counter(row["review_status"] for row in relations).items())
            ),
            "relations_with_chunk_evidence": sum(
                bool(row["evidence_chunk_ids"].strip()) for row in relations
            ),
        },
        "evaluation": {
            "split_counts": {split: len(rows) for split, rows in evaluations.items()},
            "final_category_counts": dict(
                Counter(row["category"] for row in evaluations["final"])
            ),
            "dev_final_question_overlap": len(
                final_questions & {row["question"] for row in evaluations["dev"]}
            ),
            "pilot_final_question_overlap": len(
                final_questions & {row["question"] for row in evaluations["pilot"]}
            ),
            "final_metrics": {
                key: final_report[key]
                for key in (
                    "engine",
                    "question_count",
                    "decision_accuracy",
                    "citation_rate",
                    "mean_keyword_coverage",
                    "mean_entity_coverage",
                    "mean_latency_ms",
                )
            },
            "known_failure_ids": [
                row["question_id"]
                for row in final_report["results"]
                if not row["decision_correct"]
            ],
        },
    }


def build_environment(frozen_at: str) -> tuple[str, str]:
    package_versions = []
    for name in PACKAGE_NAMES:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = "NOT INSTALLED"
        package_versions.append(f"{name}=={version}")

    pip_check_code, pip_check_output = run_command([sys.executable, "-m", "pip", "check"])
    pip_freeze_code, pip_freeze_output = run_command([sys.executable, "-m", "pip", "freeze"])
    if pip_freeze_code != 0:
        raise RuntimeError(f"pip freeze failed: {pip_freeze_output}")

    environment = "\n".join(
        [
            f"version={VERSION}",
            f"frozen_at={frozen_at}",
            f"project_root={PROJECT_ROOT}",
            f"python_executable={sys.executable}",
            f"python_version={platform.python_version()}",
            f"platform={platform.platform()}",
            "workflow_engine=langgraph",
            "graph_backend=networkx",
            "vector_representation=tfidf",
            "streamlit_url=http://localhost:8501",
            "",
            "[key_packages]",
            *package_versions,
            "",
            "[pip_check]",
            f"exit_code={pip_check_code}",
            pip_check_output or "No broken requirements found.",
            "",
        ]
    )
    return environment, pip_freeze_output + "\n"


def build_git_status() -> str:
    code, output = run_command(["git", "rev-parse", "--show-toplevel"])
    if code == 0:
        commit_code, commit = run_command(["git", "rev-parse", "HEAD"])
        return "\n".join(
            [
                "Git repository: available",
                f"Repository root: {output}",
                f"Commit: {commit if commit_code == 0 else 'unavailable'}",
                "Tag: not created by freeze_baseline.py",
                "",
            ]
        )
    return "\n".join(
        [
            "Git repository: unavailable",
            "Commit: unavailable",
            "Tag: unavailable",
            f"Reason: {PROJECT_ROOT} was not initialized as a Git repository at freeze time.",
            "Integrity fallback: source_snapshot.zip plus manifest.json and MANIFEST_SHA256.txt.",
            "",
        ]
    )


def source_files() -> list[Path]:
    files: list[Path] = []
    for directory in ("app", "src", "scripts", "tests"):
        for path in (PROJECT_ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.append(path)
    for name in (".env.example", "PROGRESS.md", "README.md", "requirements.txt"):
        path = PROJECT_ROOT / name
        if path.is_file():
            files.append(path)
    files.extend((PROJECT_ROOT / "config").glob("*.yaml"))
    return sorted(set(files), key=lambda path: path.relative_to(PROJECT_ROOT).as_posix())


def write_source_snapshot(destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())


def copy_payload_files() -> None:
    for source_name, destination_name in PAYLOAD_FILES.items():
        source = PROJECT_ROOT / source_name
        destination = RELEASE_DIR / destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def write_manifest(frozen_at: str) -> None:
    payloads = []
    for path in sorted(RELEASE_DIR.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "MANIFEST_SHA256.txt"}:
            continue
        payloads.append(
            {
                "path": path.relative_to(RELEASE_DIR).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "version": VERSION,
        "frozen_at": frozen_at,
        "payload_file_count": len(payloads),
        "payloads": payloads,
    }
    manifest_path = RELEASE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (RELEASE_DIR / "MANIFEST_SHA256.txt").write_text(
        f"{sha256(manifest_path)}  manifest.json\n", encoding="ascii"
    )


def verify_release() -> None:
    manifest_path = RELEASE_DIR / "manifest.json"
    anchor_path = RELEASE_DIR / "MANIFEST_SHA256.txt"
    if not manifest_path.is_file() or not anchor_path.is_file():
        raise FileNotFoundError(f"Release manifest is incomplete: {RELEASE_DIR}")

    expected_manifest_hash = anchor_path.read_text(encoding="ascii").split()[0]
    actual_manifest_hash = sha256(manifest_path)
    errors = []
    if actual_manifest_hash != expected_manifest_hash:
        errors.append("manifest.json hash does not match MANIFEST_SHA256.txt")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["payloads"]:
        path = RELEASE_DIR / item["path"]
        if not path.is_file():
            errors.append(f"missing payload: {item['path']}")
            continue
        if path.stat().st_size != item["bytes"]:
            errors.append(f"size mismatch: {item['path']}")
        if sha256(path) != item["sha256"]:
            errors.append(f"hash mismatch: {item['path']}")
    if errors:
        raise RuntimeError("Release verification failed:\n- " + "\n- ".join(errors))
    print(f"OK: verified {manifest['payload_file_count']} payload files in {RELEASE_DIR}")
    print(f"OK: manifest_sha256={actual_manifest_hash}")


def create_release() -> None:
    if RELEASE_DIR.exists():
        raise FileExistsError(
            f"Release already exists and will not be overwritten: {RELEASE_DIR}. "
            "Use --verify to check it."
        )
    validate_sources()
    frozen_at = datetime.now(timezone.utc).astimezone().isoformat()
    data_statistics = build_data_statistics(frozen_at)
    environment, pip_freeze = build_environment(frozen_at)
    git_status = build_git_status()

    RELEASE_DIR.mkdir(parents=True)
    copy_payload_files()
    (RELEASE_DIR / "config_snapshot" / "pip_freeze.txt").write_text(
        pip_freeze, encoding="utf-8"
    )
    (RELEASE_DIR / "data_statistics.json").write_text(
        json.dumps(data_statistics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (RELEASE_DIR / "environment.txt").write_text(environment, encoding="utf-8")
    (RELEASE_DIR / "git_commit.txt").write_text(git_status, encoding="utf-8")
    (RELEASE_DIR / "release_notes.md").write_text(RELEASE_NOTES, encoding="utf-8")
    write_source_snapshot(RELEASE_DIR / "source_snapshot.zip")
    write_manifest(frozen_at)
    verify_release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify the immutable v1.0 baseline archive")
    parser.add_argument("--verify", action="store_true", help="verify an existing release archive")
    args = parser.parse_args()
    if args.verify:
        verify_release()
    else:
        create_release()


if __name__ == "__main__":
    sys.exit(main())
