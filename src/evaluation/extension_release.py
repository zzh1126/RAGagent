from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


IMPLEMENTATION_MANIFEST_PATH = Path(
    "data/evaluation/extension_implementation_manifest.json"
)
HOLDOUT_MANIFEST_PATH = Path("data/evaluation/extension_holdout_manifest.json")
RELEASE_RECORD_PATH = Path("data/evaluation/extension_holdout_release.json")
TRACE_CONTRACT_PATH = Path("config/extension_trace_contract.yaml")
SCORING_CONTRACT_PATH = Path("config/extension_evaluation.yaml")
DATASET_PATH = Path("data/evaluation/extension_questions.jsonl")
EXECUTION_STATE_PATH = Path("reports/extension/execution_state.json")
EXECUTION_RECEIPT_PATH = Path("reports/extension/execution_receipt.json")
METHOD_ORDER = (
    "rule_baseline",
    "llm_generator",
    "llm_generator_no_verifier",
)
METHOD_REPORT_PATHS = {
    method_id: Path(f"reports/extension/{method_id}.json")
    for method_id in METHOD_ORDER
}
FINAL_OUTPUT_PATHS = {
    **METHOD_REPORT_PATHS,
    "combined_metrics": Path("reports/extension/combined_metrics.json"),
    "blind_review": Path("reports/extension/blind_review.csv"),
    "blind_method_key": Path("reports/extension/blind_method_key.json"),
}
STATIC_RUNTIME_PATHS = (
    Path("requirements.txt"),
    Path("config/settings.yaml"),
    SCORING_CONTRACT_PATH,
    TRACE_CONTRACT_PATH,
    DATASET_PATH,
    HOLDOUT_MANIFEST_PATH,
    Path("data/graph/entities.csv"),
    Path("data/graph/relations.csv"),
    Path("data/processed/chunks.jsonl"),
    Path("data/chroma/chunks_snapshot.jsonl"),
    Path("data/chroma/tfidf_matrix.pkl"),
    Path("data/chroma/tfidf_vectorizer.pkl"),
    Path("scripts/run_extension_evaluation.py"),
)
PACKAGE_NAMES = (
    "langgraph",
    "networkx",
    "pydantic",
    "PyYAML",
    "requests",
    "scikit-learn",
)
TEXT_HASH_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".py", ".yaml", ".yml"}
TEXT_HASH_NAMES = {"requirements.txt"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.suffix.lower() in TEXT_HASH_SUFFIXES or path.name in TEXT_HASH_NAMES:
        payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        return sha256_bytes(payload)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def relative_path(path: Path) -> str:
    return path.as_posix()


def runtime_paths(root: Path) -> list[Path]:
    paths = set(STATIC_RUNTIME_PATHS)
    paths.update(path.relative_to(root) for path in (root / "src").rglob("*.py"))
    return sorted(paths, key=relative_path)


def runtime_file_hashes(root: Path) -> list[dict[str, str]]:
    rows = []
    for relative in runtime_paths(root):
        absolute = root / relative
        if not absolute.is_file():
            raise FileNotFoundError(f"frozen runtime file does not exist: {relative_path(relative)}")
        rows.append({"path": relative_path(relative), "sha256": sha256_file(absolute)})
    return rows


def dependency_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in PACKAGE_NAMES}


def git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def current_commit(root: Path) -> str:
    return git_output(root, "rev-parse", "HEAD")


def tracked_worktree_is_clean(root: Path) -> bool:
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, check=False)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
    return unstaged.returncode == 0 and staged.returncode == 0


def is_ancestor(root: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def ollama_identity(base_url: str, model: str, timeout_seconds: float = 10.0) -> dict:
    normalized_url = base_url.rstrip("/")
    try:
        version_response = requests.get(
            f"{normalized_url}/api/version",
            timeout=timeout_seconds,
        )
        version_response.raise_for_status()
        tags_response = requests.get(
            f"{normalized_url}/api/tags",
            timeout=timeout_seconds,
        )
        tags_response.raise_for_status()
        version_payload = version_response.json()
        tags_payload = tags_response.json()
    except (requests.RequestException, TypeError, ValueError) as exc:
        raise RuntimeError("unable to inspect the local Ollama runtime") from exc

    models = tags_payload.get("models", []) if isinstance(tags_payload, dict) else []
    match = next(
        (
            item
            for item in models
            if isinstance(item, dict)
            and (item.get("name") == model or item.get("model") == model)
        ),
        None,
    )
    if match is None:
        raise RuntimeError(f"required Ollama model is not installed: {model}")
    digest = match.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError(f"Ollama did not return a full digest for model: {model}")
    return {
        "provider": "ollama",
        "base_url": normalized_url,
        "version": version_payload.get("version"),
        "model": model,
        "model_digest": digest,
        "model_size_bytes": match.get("size"),
    }


def prompt_contract() -> dict[str, str]:
    from src.agent.generators.llm_generator import (
        ANSWER_PROMPT_VERSION,
        LLMAnswerDraft,
        SYSTEM_PROMPT,
    )

    return {
        "version": ANSWER_PROMPT_VERSION,
        "system_prompt_sha256": sha256_bytes(SYSTEM_PROMPT.encode("utf-8")),
        "wire_schema_sha256": canonical_sha256(LLMAnswerDraft.model_json_schema()),
    }


def validate_static_contracts(root: Path) -> list[str]:
    errors: list[str] = []
    trace = yaml.safe_load((root / TRACE_CONTRACT_PATH).read_text(encoding="utf-8"))
    scoring = yaml.safe_load((root / SCORING_CONTRACT_PATH).read_text(encoding="utf-8"))
    holdout = read_json(root / HOLDOUT_MANIFEST_PATH)
    if trace.get("artifact") != "extension_trace_metric_contract":
        errors.append("invalid extension trace contract artifact")
    if trace.get("status") != "frozen_before_release":
        errors.append("extension trace contract is not frozen")
    if trace.get("method_order") != list(METHOD_ORDER):
        errors.append("extension trace method order mismatch")
    if trace.get("execution", {}).get("maximum_runs") != 1:
        errors.append("extension trace contract must permit exactly one run")
    if trace.get("execution", {}).get("generic_evaluation_runner_must_remain_locked") is not True:
        errors.append("generic extension runner lock is missing")
    scoring_methods = [item.get("id") for item in scoring.get("methods", [])]
    if scoring_methods != list(METHOD_ORDER):
        errors.append("extension scoring and trace method order differ")
    expected_hashes = {
        "dataset_sha256": sha256_file(root / DATASET_PATH),
        "scoring_contract_sha256": sha256_file(root / SCORING_CONTRACT_PATH),
    }
    for field, expected in expected_hashes.items():
        if holdout.get(field) != expected:
            errors.append(f"holdout {field} no longer matches its frozen manifest")
    return errors


def build_implementation_manifest(
    root: Path,
    *,
    implementation_commit: str,
    model_identity: dict,
    created_at: str | None = None,
) -> dict:
    contract_errors = validate_static_contracts(root)
    if contract_errors:
        raise ValueError("; ".join(contract_errors))
    files = runtime_file_hashes(root)
    holdout = json.loads((root / HOLDOUT_MANIFEST_PATH).read_text(encoding="utf-8"))
    settings = yaml.safe_load((root / "config/settings.yaml").read_text(encoding="utf-8"))
    return {
        "schema_version": "1.0",
        "artifact": "extension_implementation_freeze",
        "status": "frozen_before_extension_execution",
        "created_at": created_at or utc_now(),
        "implementation_commit": implementation_commit,
        "runtime_files": files,
        "runtime_bundle_sha256": canonical_sha256(files),
        "hash_normalization": "text_crlf_and_cr_normalized_to_lf; binary_raw_bytes",
        "prompt_contract": prompt_contract(),
        "settings_sha256": sha256_file(root / "config/settings.yaml"),
        "trace_contract_path": relative_path(TRACE_CONTRACT_PATH),
        "trace_contract_sha256": sha256_file(root / TRACE_CONTRACT_PATH),
        "dataset_sha256": holdout["dataset_sha256"],
        "scoring_contract_sha256": holdout["scoring_contract_sha256"],
        "method_order": list(METHOD_ORDER),
        "python_version": platform.python_version(),
        "dependency_versions": dependency_versions(),
        "runtime_model": model_identity,
        "agent_contract": {
            "planner_backend": settings["agent"]["planner_backend"],
            "generator_backend": settings["agent"]["generator_backend"],
            "generator_fallback": settings["agent"]["generator_fallback"],
            "graph_backend": settings["project"]["graph_backend"],
        },
    }


def build_release_record(
    root: Path,
    *,
    implementation_manifest: dict,
    released_at: str | None = None,
) -> dict:
    implementation_commit = implementation_manifest["implementation_commit"]
    release_id = f"extension-qwen3-4b-v1-{implementation_commit[:8]}"
    return {
        "schema_version": "1.0",
        "artifact": "extension_holdout_release",
        "status": "authorized_not_executed",
        "release_id": release_id,
        "released_at": released_at or utc_now(),
        "authorized_implementation_commit": implementation_commit,
        "implementation_manifest_path": relative_path(IMPLEMENTATION_MANIFEST_PATH),
        "implementation_manifest_sha256": sha256_file(
            root / IMPLEMENTATION_MANIFEST_PATH
        ),
        "dataset_sha256": implementation_manifest["dataset_sha256"],
        "scoring_contract_sha256": implementation_manifest[
            "scoring_contract_sha256"
        ],
        "trace_contract_sha256": implementation_manifest["trace_contract_sha256"],
        "runtime_bundle_sha256": implementation_manifest["runtime_bundle_sha256"],
        "prompt_contract": implementation_manifest["prompt_contract"],
        "runtime_model": implementation_manifest["runtime_model"],
        "method_order": list(METHOD_ORDER),
        "maximum_execution_runs": 1,
        "randomization_seed": secrets.randbits(63),
        "execution_state_path": relative_path(EXECUTION_STATE_PATH),
        "execution_receipt_path": relative_path(EXECUTION_RECEIPT_PATH),
        "output_paths": {
            key: relative_path(path) for key, path in FINAL_OUTPUT_PATHS.items()
        },
        "authorized_command": (
            "python scripts/run_extension_evaluation.py --execute-once "
            f"--release-id {release_id} --confirm-one-time-run"
        ),
        "final_result_policy": "v1.0_final_read_only_unchanged",
    }


def write_new_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return value


def validate_implementation_manifest(root: Path, manifest: dict) -> list[str]:
    errors: list[str] = validate_static_contracts(root)
    if manifest.get("artifact") != "extension_implementation_freeze":
        errors.append("invalid implementation manifest artifact")
    if manifest.get("status") != "frozen_before_extension_execution":
        errors.append("implementation manifest is not frozen")

    try:
        current_files = runtime_file_hashes(root)
    except (FileNotFoundError, OSError) as exc:
        errors.append(str(exc))
        current_files = []
    if manifest.get("runtime_files") != current_files:
        errors.append("frozen runtime file set or content hash has changed")
    if manifest.get("runtime_bundle_sha256") != canonical_sha256(current_files):
        errors.append("runtime bundle hash mismatch")
    if manifest.get("hash_normalization") != (
        "text_crlf_and_cr_normalized_to_lf; binary_raw_bytes"
    ):
        errors.append("implementation hash normalization contract mismatch")
    if manifest.get("prompt_contract") != prompt_contract():
        errors.append("prompt version, text, or wire schema hash has changed")
    expected_file_hashes = {
        "settings_sha256": sha256_file(root / "config/settings.yaml"),
        "trace_contract_sha256": sha256_file(root / TRACE_CONTRACT_PATH),
    }
    for field, expected in expected_file_hashes.items():
        if manifest.get(field) != expected:
            errors.append(f"implementation manifest {field} mismatch")

    holdout = read_json(root / HOLDOUT_MANIFEST_PATH)
    for field in ("dataset_sha256", "scoring_contract_sha256"):
        if manifest.get(field) != holdout.get(field):
            errors.append(f"implementation manifest {field} changed")
    if manifest.get("method_order") != list(METHOD_ORDER):
        errors.append("implementation method order mismatch")
    if manifest.get("python_version") != platform.python_version():
        errors.append("Python version differs from the implementation freeze")
    if manifest.get("dependency_versions") != dependency_versions():
        errors.append("dependency versions differ from the implementation freeze")
    commit = manifest.get("implementation_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        errors.append("implementation commit is invalid")
    elif not is_ancestor(root, commit):
        errors.append("implementation commit is not an ancestor of the current HEAD")
    return errors


def validate_release_record(
    root: Path,
    release: dict,
    implementation_manifest: dict,
    *,
    check_runtime_model: bool = False,
    require_unexecuted: bool = False,
) -> list[str]:
    errors = validate_implementation_manifest(root, implementation_manifest)
    if release.get("artifact") != "extension_holdout_release":
        errors.append("invalid extension release artifact")
    if release.get("status") != "authorized_not_executed":
        errors.append("extension release status is invalid")
    if release.get("authorized_implementation_commit") != implementation_manifest.get(
        "implementation_commit"
    ):
        errors.append("release commit does not match the implementation manifest")
    if release.get("implementation_manifest_sha256") != sha256_file(
        root / IMPLEMENTATION_MANIFEST_PATH
    ):
        errors.append("release implementation manifest hash mismatch")
    for field in (
        "dataset_sha256",
        "scoring_contract_sha256",
        "trace_contract_sha256",
        "runtime_bundle_sha256",
        "prompt_contract",
        "runtime_model",
        "method_order",
    ):
        if release.get(field) != implementation_manifest.get(field):
            errors.append(f"release {field} does not match the implementation freeze")
    if release.get("maximum_execution_runs") != 1:
        errors.append("extension release must authorize exactly one run")
    if release.get("execution_state_path") != relative_path(EXECUTION_STATE_PATH):
        errors.append("extension execution state path mismatch")
    if release.get("execution_receipt_path") != relative_path(EXECUTION_RECEIPT_PATH):
        errors.append("extension execution receipt path mismatch")
    expected_outputs = {
        key: relative_path(path) for key, path in FINAL_OUTPUT_PATHS.items()
    }
    if release.get("output_paths") != expected_outputs:
        errors.append("extension output path contract mismatch")

    if check_runtime_model:
        frozen_model = implementation_manifest.get("runtime_model", {})
        try:
            current_model = ollama_identity(
                frozen_model.get("base_url", ""),
                frozen_model.get("model", ""),
            )
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            if current_model != frozen_model:
                errors.append("Ollama version or model digest differs from the release")

    if require_unexecuted:
        existing = [
            relative_path(path)
            for path in [
                EXECUTION_STATE_PATH,
                EXECUTION_RECEIPT_PATH,
                *FINAL_OUTPUT_PATHS.values(),
            ]
            if (root / path).exists()
        ]
        if existing:
            errors.append("extension execution artifacts already exist: " + ", ".join(existing))
    return errors


def load_release_artifacts(root: Path) -> tuple[dict, dict]:
    implementation_path = root / IMPLEMENTATION_MANIFEST_PATH
    release_path = root / RELEASE_RECORD_PATH
    if not implementation_path.is_file():
        raise FileNotFoundError("extension implementation manifest does not exist")
    if not release_path.is_file():
        raise FileNotFoundError("extension release record does not exist")
    return read_json(implementation_path), read_json(release_path)


def validate_execution_artifacts(root: Path, release: dict) -> tuple[list[str], str]:
    errors: list[str] = []
    state_path = root / EXECUTION_STATE_PATH
    receipt_path = root / EXECUTION_RECEIPT_PATH
    existing_outputs = {
        key: path for key, path in FINAL_OUTPUT_PATHS.items() if (root / path).exists()
    }
    if not state_path.exists() and not receipt_path.exists() and not existing_outputs:
        return errors, "authorized_not_executed"
    if not state_path.is_file():
        return ["extension outputs exist without an execution state"], "invalid"

    try:
        state = read_json(state_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid extension execution state: {exc}"], "invalid"
    if state.get("artifact") != "extension_execution_state":
        errors.append("invalid extension execution state artifact")
    if state.get("release_id") != release.get("release_id"):
        errors.append("execution state release ID mismatch")
    status = state.get("status")
    if status in {"in_progress", "failed_requires_manual_audit"}:
        if receipt_path.exists():
            errors.append("incomplete extension execution must not have a completion receipt")
        return errors, str(status)
    if status != "completed":
        errors.append("unknown extension execution state status")
        return errors, "invalid"
    if not receipt_path.is_file():
        errors.append("completed extension execution is missing its receipt")
        return errors, "invalid"

    try:
        receipt = read_json(receipt_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid extension execution receipt: {exc}"], "invalid"
    if receipt.get("artifact") != "extension_execution_receipt":
        errors.append("invalid extension execution receipt artifact")
    if receipt.get("release_id") != release.get("release_id"):
        errors.append("execution receipt release ID mismatch")
    if receipt.get("status") != "completed_once":
        errors.append("execution receipt does not record one completed run")
    if receipt.get("qa_invocation_count") != 23 * len(METHOD_ORDER):
        errors.append("execution receipt QA invocation count mismatch")
    if receipt.get("execution_state_sha256") != sha256_file(state_path):
        errors.append("execution state hash does not match the receipt")
    recorded_outputs = receipt.get("output_hashes", {})
    if set(recorded_outputs) != set(FINAL_OUTPUT_PATHS):
        errors.append("execution receipt output set mismatch")
    for key, expected_path in FINAL_OUTPUT_PATHS.items():
        absolute = root / expected_path
        item = recorded_outputs.get(key, {})
        if not absolute.is_file():
            errors.append(f"completed extension output is missing: {relative_path(expected_path)}")
            continue
        if item.get("path") != relative_path(expected_path):
            errors.append(f"execution receipt path mismatch: {key}")
        if item.get("sha256") != sha256_file(absolute):
            errors.append(f"execution output hash mismatch: {key}")
    return errors, "completed_once" if not errors else "invalid"
