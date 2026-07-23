from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
EVALUATION_DIR = PROJECT_ROOT / "data" / "evaluation"
DATASET_PATH = EVALUATION_DIR / "extension_questions.jsonl"
CONTRACT_PATH = PROJECT_ROOT / "config" / "extension_evaluation.yaml"
MANIFEST_PATH = EVALUATION_DIR / "extension_holdout_manifest.json"
RELEASE_PATH = EVALUATION_DIR / "extension_holdout_release.json"
EXPECTED_COUNTS = {
    "single_hop": 4,
    "multi_hop": 4,
    "definition": 3,
    "comparison": 3,
    "principle_pros_cons": 3,
    "metric_selection": 2,
    "no_answer": 4,
}
REQUIRED_FIELDS = {
    "question_id",
    "split",
    "category",
    "question",
    "expected_behavior",
    "gold_entities",
    "gold_relations",
    "expected_keywords",
    "expected_route",
    "required_aspects",
    "forbidden_claims",
    "notes",
}
EXPECTED_METHODS = {
    "rule_baseline",
    "llm_generator",
    "llm_generator_no_verifier",
}

from src.evaluation.extension_release import (
    EXECUTION_RECEIPT_PATH,
    EXECUTION_STATE_PATH,
    FINAL_OUTPUT_PATHS,
    IMPLEMENTATION_MANIFEST_PATH,
    load_release_artifacts,
    validate_execution_artifacts,
    validate_release_record,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv_ids(path: Path, field: str) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row[field] for row in csv.DictReader(handle)}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_question(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


def question_fingerprint(rows: list[dict]) -> str:
    payload = "\n".join(
        f"{row['question_id']}\t{normalize_question(row['question'])}" for row in rows
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def closest_prior_question(rows: list[dict], prior_rows: list[dict]) -> tuple[float, str, str]:
    closest = (0.0, "", "")
    for row in rows:
        current = normalize_question(row["question"])
        for prior in prior_rows:
            ratio = SequenceMatcher(None, current, normalize_question(prior["question"])).ratio()
            if ratio > closest[0]:
                closest = (ratio, row["question_id"], prior["question_id"])
    return closest


def main() -> None:
    rows = read_jsonl(DATASET_PATH)
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entity_ids = read_csv_ids(PROJECT_ROOT / "data" / "graph" / "entities.csv", "entity_id")
    relation_path = PROJECT_ROOT / "data" / "graph" / "relations.csv"
    relation_rows = read_csv_rows(relation_path)
    relation_types = {row["relation"] for row in relation_rows}
    errors: list[str] = []

    if len(rows) != 23:
        errors.append(f"extension holdout must contain 23 questions, got {len(rows)}")
    observed_counts = Counter(row.get("category") for row in rows)
    if dict(observed_counts) != EXPECTED_COUNTS:
        errors.append(f"category distribution mismatch: {dict(observed_counts)}")
    if sum(row.get("expected_behavior") == "refuse" for row in rows) != 4:
        errors.append("extension holdout must contain four no-answer questions")

    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            errors.append(f"line {index}: missing fields {sorted(missing)}")
            continue
        question_id = row["question_id"]
        if not re.fullmatch(r"X-(?:SH|MH|DF|CM|PC|MS|NA)-\d{2}", question_id):
            errors.append(f"invalid extension question ID: {question_id}")
        if question_id in seen_ids:
            errors.append(f"duplicate extension ID: {question_id}")
        if row["question"] in seen_questions:
            errors.append(f"duplicate extension question: {row['question']}")
        if row["split"] != "extension":
            errors.append(f"{question_id}: split must be extension")
        if row["expected_behavior"] not in {"answer", "refuse"}:
            errors.append(f"{question_id}: invalid expected_behavior")
        if row["expected_route"] not in {"vector", "graph", "hybrid"}:
            errors.append(f"{question_id}: invalid expected_route")
        if not row["required_aspects"] or not row["forbidden_claims"]:
            errors.append(f"{question_id}: scoring aspects and forbidden claims must be non-empty")
        unknown_entities = set(row["gold_entities"]) - entity_ids
        unknown_relations = set(row["gold_relations"]) - relation_types
        if unknown_entities:
            errors.append(f"{question_id}: unknown entities {sorted(unknown_entities)}")
        if unknown_relations:
            errors.append(f"{question_id}: unknown relations {sorted(unknown_relations)}")
        if row["expected_behavior"] == "refuse" and row["expected_keywords"]:
            errors.append(f"{question_id}: refusal question must not define answer keywords")
        if row["expected_behavior"] == "answer" and not row["gold_entities"]:
            errors.append(f"{question_id}: answerable question must define gold entities")
        if row["expected_behavior"] == "answer" and not row["expected_keywords"]:
            errors.append(f"{question_id}: answerable question must define expected keywords")
        if row["category"] == "no_answer" and row["expected_behavior"] != "refuse":
            errors.append(f"{question_id}: no_answer category must refuse")
        if row["category"] != "no_answer" and row["expected_behavior"] != "answer":
            errors.append(f"{question_id}: answerable category must use expected_behavior=answer")
        gold_entities = set(row["gold_entities"])
        for relation_type in row["gold_relations"]:
            related = any(
                relation["review_status"] == "approved"
                and relation["relation"] == relation_type
                and {relation["source_id"], relation["target_id"]}.issubset(gold_entities)
                for relation in relation_rows
            )
            if not related:
                errors.append(
                    f"{question_id}: no approved {relation_type} relation is contained in gold entities"
                )
        seen_ids.add(question_id)
        seen_questions.add(row["question"])

    prior_rows: list[dict] = []
    for split in ("dev", "demo", "pilot", "final"):
        prior_rows.extend(read_jsonl(EVALUATION_DIR / f"{split}_questions.jsonl"))
    prior_questions = {row["question"] for row in prior_rows}
    exact_overlap = seen_questions & prior_questions
    if exact_overlap:
        errors.append(f"exact overlap with prior datasets: {sorted(exact_overlap)}")
    max_similarity, extension_id, prior_id = closest_prior_question(rows, prior_rows)
    threshold = float(manifest.get("near_duplicate_threshold", 0.82))
    if max_similarity >= threshold:
        errors.append(
            f"near-duplicate threshold exceeded: {extension_id}/{prior_id} "
            f"ratio={max_similarity:.4f} threshold={threshold:.4f}"
        )

    methods = {item.get("id") for item in contract.get("methods", [])}
    if methods != EXPECTED_METHODS:
        errors.append(f"scoring contract methods mismatch: {sorted(methods)}")
    if contract.get("status") != "frozen_locked":
        errors.append("scoring contract must remain frozen_locked")
    if contract.get("question_count") != 23 or contract.get("answerable_count") != 19:
        errors.append("scoring contract question counts are invalid")
    if contract.get("category_distribution") != EXPECTED_COUNTS:
        errors.append("scoring contract category distribution mismatch")
    if contract.get("execution_lock", {}).get("status") != "locked":
        errors.append("extension execution lock is not active")
    if contract.get("claim_policy", {}).get("route_accuracy") != "not_applicable_planner_no_go":
        errors.append("scoring contract must not claim Planner route accuracy")

    expected_hashes = {
        "dataset_sha256": sha256(DATASET_PATH),
        "scoring_contract_sha256": sha256(CONTRACT_PATH),
        "question_fingerprint_sha256": question_fingerprint(rows),
    }
    for field, actual in expected_hashes.items():
        if manifest.get(field) != actual:
            errors.append(f"manifest {field} mismatch: {manifest.get(field)} != {actual}")
    if manifest.get("status") != "frozen_locked":
        errors.append("manifest status must remain frozen_locked")
    if manifest.get("dataset_path") != str(DATASET_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"):
        errors.append("manifest dataset path mismatch")
    if manifest.get("scoring_contract_path") != str(CONTRACT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"):
        errors.append("manifest scoring contract path mismatch")
    if manifest.get("question_count") != 23 or manifest.get("answerable_count") != 19:
        errors.append("manifest question counts are invalid")
    if set(manifest.get("method_ids", [])) != EXPECTED_METHODS:
        errors.append("manifest method IDs do not match the scoring contract")
    if manifest.get("execution_status") != "locked":
        errors.append("manifest execution status must remain locked")
    if manifest.get("release_record_present") is not False:
        errors.append("manifest must record that no release record exists")
    if manifest.get("extension_outputs_present") is not False:
        errors.append("manifest must record that no extension outputs exist")
    if manifest.get("baseline_commit") != contract.get("freeze", {}).get("baseline_commit"):
        errors.append("manifest and scoring contract baseline commits differ")
    if manifest.get("category_distribution") != EXPECTED_COUNTS:
        errors.append("manifest category distribution mismatch")
    if manifest.get("max_prior_similarity") != round(max_similarity, 4):
        errors.append("manifest maximum prior similarity does not match recomputation")
    if manifest.get("closest_question_pair") != {
        "extension_question_id": extension_id,
        "prior_question_id": prior_id,
    }:
        errors.append("manifest closest question pair does not match recomputation")

    execution_status = "locked"
    legacy_output_paths = [
        PROJECT_ROOT / "reports" / "evaluation_extension.json",
        *sorted((PROJECT_ROOT / "reports" / "experiments").glob("*_extension.json")),
    ]
    existing_legacy_outputs = [str(path) for path in legacy_output_paths if path.exists()]
    if existing_legacy_outputs:
        errors.append(f"extension outputs exist outside the controlled runner: {existing_legacy_outputs}")

    if RELEASE_PATH.exists():
        try:
            implementation, release = load_release_artifacts(PROJECT_ROOT)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid extension release artifacts: {exc}")
        else:
            errors.extend(
                validate_release_record(
                    PROJECT_ROOT,
                    release,
                    implementation,
                    check_runtime_model=False,
                    require_unexecuted=False,
                )
            )
            execution_errors, execution_status = validate_execution_artifacts(
                PROJECT_ROOT,
                release,
            )
            errors.extend(execution_errors)
    else:
        if (PROJECT_ROOT / IMPLEMENTATION_MANIFEST_PATH).exists():
            errors.append("implementation manifest exists without a release record")
        controlled_outputs = [
            EXECUTION_STATE_PATH,
            EXECUTION_RECEIPT_PATH,
            *FINAL_OUTPUT_PATHS.values(),
        ]
        existing_controlled_outputs = [
            path.as_posix() for path in controlled_outputs if (PROJECT_ROOT / path).exists()
        ]
        if existing_controlled_outputs:
            errors.append(
                "extension outputs exist before release: "
                + ", ".join(existing_controlled_outputs)
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("OK: extension holdout is frozen and structurally valid")
    print(f"OK: questions=23 distribution={dict(observed_counts)}")
    print(f"OK: dataset_sha256={expected_hashes['dataset_sha256']}")
    print(f"OK: scoring_contract_sha256={expected_hashes['scoring_contract_sha256']}")
    print(
        f"OK: max_prior_similarity={max_similarity:.4f} "
        f"closest_pair={extension_id}/{prior_id}"
    )
    print(f"OK: effective_execution_status={execution_status}")


if __name__ == "__main__":
    main()
