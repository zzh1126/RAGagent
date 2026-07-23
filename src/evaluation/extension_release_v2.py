from __future__ import annotations

import json
import platform
import re
import secrets
import subprocess
from pathlib import Path
from typing import Any

import yaml

from src.evaluation.extension_release import (
    DATASET_PATH,
    HOLDOUT_MANIFEST_PATH,
    IMPLEMENTATION_MANIFEST_PATH,
    RELEASE_RECORD_PATH,
    V2_METHOD_ORDER,
    V2_RELEASE_RECORD_PATH,
    V2_SCORING_CONTRACT_PATH,
    V2_TRACE_CONTRACT_PATH,
    canonical_sha256,
    dependency_versions,
    is_ancestor,
    ollama_identity,
    prompt_contract,
    read_json,
    relative_path,
    revocation_record_path,
    sha256_bytes,
    sha256_file,
    utc_now,
    validate_v2_protocol_contracts,
)
from src.evaluation.pilot_gate import (
    PILOT_GATE_CONTRACT_PATH,
    PILOT_GATE_DECISION_PATH,
    PILOT_REPORT_PATH,
    PILOT_STATE_PATH,
    evaluate_pilot_report,
    validate_gate_contract,
)


V2_IMPLEMENTATION_MANIFEST_PATH = Path(
    "data/evaluation/extension_implementation_manifest_v2.json"
)
V2_EXECUTION_DIRECTORY = Path("reports/extension_v2")
V2_EXECUTION_STATE_PATH = V2_EXECUTION_DIRECTORY / "execution_state.json"
V2_EXECUTION_RECEIPT_PATH = V2_EXECUTION_DIRECTORY / "execution_receipt.json"
V2_METHOD_REPORT_PATHS = {
    method_id: V2_EXECUTION_DIRECTORY / f"{method_id}.json"
    for method_id in V2_METHOD_ORDER
}
V2_FINAL_OUTPUT_PATHS = {
    **V2_METHOD_REPORT_PATHS,
    "combined_metrics": V2_EXECUTION_DIRECTORY / "combined_metrics.json",
    "blind_review": V2_EXECUTION_DIRECTORY / "blind_review.csv",
    "blind_method_key": V2_EXECUTION_DIRECTORY / "blind_method_key.json",
}
V1_RELEASE_ID = "extension-qwen3-4b-v1-bdedf7dc"
V1_REVOCATION_PATH = revocation_record_path(V1_RELEASE_ID)
V2_STATIC_RUNTIME_PATHS = (
    Path("requirements.txt"),
    Path("config/settings.yaml"),
    V2_SCORING_CONTRACT_PATH,
    V2_TRACE_CONTRACT_PATH,
    PILOT_GATE_CONTRACT_PATH,
    DATASET_PATH,
    HOLDOUT_MANIFEST_PATH,
    Path("data/graph/entities.csv"),
    Path("data/graph/relations.csv"),
    Path("data/processed/chunks.jsonl"),
    Path("data/chroma/chunks_snapshot.jsonl"),
    Path("data/chroma/tfidf_matrix.pkl"),
    Path("data/chroma/tfidf_vectorizer.pkl"),
    Path("scripts/run_extension_evaluation_v2.py"),
)
TEXT_HASH_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".py", ".yaml", ".yml"}
TEXT_HASH_NAMES = {"requirements.txt"}


def v2_runtime_paths(root: Path) -> list[Path]:
    paths = set(V2_STATIC_RUNTIME_PATHS)
    paths.update(path.relative_to(root) for path in (root / "src").rglob("*.py"))
    return sorted(paths, key=relative_path)


def v2_runtime_file_hashes(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for relative in v2_runtime_paths(root):
        absolute = root / relative
        if not absolute.is_file():
            raise FileNotFoundError(
                f"frozen v2 runtime file does not exist: {relative_path(relative)}"
            )
        rows.append({"path": relative_path(relative), "sha256": sha256_file(absolute)})
    return rows


def _payload_sha256(path: Path, payload: bytes) -> str:
    if path.suffix.lower() in TEXT_HASH_SUFFIXES or path.name in TEXT_HASH_NAMES:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(payload)


def v2_runtime_commit_mismatches(root: Path, commit: str) -> list[str]:
    mismatches: list[str] = []
    for relative in v2_runtime_paths(root):
        completed = subprocess.run(
            ["git", "show", f"{commit}:{relative_path(relative)}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            mismatches.append(f"{relative_path(relative)}: missing from implementation commit")
            continue
        committed_hash = _payload_sha256(relative, completed.stdout)
        current_hash = sha256_file(root / relative)
        if committed_hash != current_hash:
            mismatches.append(f"{relative_path(relative)}: differs from implementation commit")
    return mismatches


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return value


def validate_pilot_gate_decision(root: Path, decision: dict[str, Any]) -> list[str]:
    errors = validate_gate_contract(root)
    if decision.get("artifact") != "llm_agent_v2_pilot_freeze_gate_decision":
        errors.append("invalid Stage 8.6 pilot gate decision artifact")
    if decision.get("protocol_version") != "v2":
        errors.append("Stage 8.6 pilot gate protocol mismatch")
    if decision.get("status") != "go":
        errors.append("Stage 8.6 pilot gate is not Go")
    if decision.get("pilot_consumed") is not True:
        errors.append("Stage 8.6 pilot gate did not record pilot consumption")
    if decision.get("rerun_authorized") is not False:
        errors.append("Stage 8.6 pilot gate must forbid reruns")
    if decision.get("per_question_tuning_authorized") is not False:
        errors.append("Stage 8.6 pilot gate must forbid post-pilot tuning")

    expected_paths = {
        "contract_path": PILOT_GATE_CONTRACT_PATH,
        "report_path": PILOT_REPORT_PATH,
        "state_path": PILOT_STATE_PATH,
    }
    for field, expected_path in expected_paths.items():
        if decision.get(field) != relative_path(expected_path):
            errors.append(f"Stage 8.6 pilot gate {field} mismatch")
        absolute = root / expected_path
        hash_field = field.replace("_path", "_sha256")
        if not absolute.is_file():
            errors.append(f"Stage 8.6 pilot artifact is missing: {relative_path(expected_path)}")
        elif decision.get(hash_field) != sha256_file(absolute):
            errors.append(f"Stage 8.6 pilot gate {hash_field} mismatch")

    report_path = root / PILOT_REPORT_PATH
    state_path = root / PILOT_STATE_PATH
    if report_path.is_file() and state_path.is_file():
        try:
            report = _load_json_object(report_path)
            state = _load_json_object(state_path)
            recomputed = evaluate_pilot_report(
                root,
                report,
                state,
                evaluated_at=decision.get("evaluated_at"),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"unable to recompute Stage 8.6 pilot gate: {exc}")
        else:
            if decision != recomputed:
                errors.append("Stage 8.6 pilot gate decision differs from recomputation")
    return errors


def load_pilot_gate_decision(root: Path) -> dict[str, Any]:
    path = root / PILOT_GATE_DECISION_PATH
    if not path.is_file():
        raise FileNotFoundError("Stage 8.6 pilot gate decision does not exist")
    return _load_json_object(path)


def _agent_contract(root: Path) -> dict[str, Any]:
    settings = yaml.safe_load((root / "config/settings.yaml").read_text(encoding="utf-8"))
    return {
        "planner_backend": settings["agent"]["planner_backend"],
        "generator_backend": settings["agent"]["generator_backend"],
        "generator_fallback": settings["agent"]["generator_fallback"],
        "generator_prompt_version": settings["agent"]["generator_prompt_version"],
        "evidence_packer": settings["agent"]["evidence_packer"],
        "verifier_decision_policy": settings["verification"]["decision_policy"],
        "graph_backend": settings["project"]["graph_backend"],
    }


def _v1_governance(root: Path) -> dict[str, Any]:
    return {
        "release_id": V1_RELEASE_ID,
        "release_record_path": relative_path(RELEASE_RECORD_PATH),
        "release_record_sha256": sha256_file(root / RELEASE_RECORD_PATH),
        "implementation_manifest_path": relative_path(IMPLEMENTATION_MANIFEST_PATH),
        "implementation_manifest_sha256": sha256_file(
            root / IMPLEMENTATION_MANIFEST_PATH
        ),
        "revocation_path": relative_path(V1_REVOCATION_PATH),
        "revocation_sha256": sha256_file(root / V1_REVOCATION_PATH),
        "effective_status": "revoked_before_execution",
    }


def build_v2_implementation_manifest(
    root: Path,
    *,
    implementation_commit: str,
    model_identity: dict[str, Any],
    pilot_gate_decision: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    contract_errors = validate_v2_protocol_contracts(root)
    gate_errors = validate_pilot_gate_decision(root, pilot_gate_decision)
    if contract_errors or gate_errors:
        raise ValueError("; ".join([*contract_errors, *gate_errors]))
    if pilot_gate_decision.get("implementation_commit") != implementation_commit:
        raise ValueError("pilot gate and v2 implementation commits differ")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("v2 implementation commit is invalid")
    if not is_ancestor(root, implementation_commit):
        raise ValueError("v2 implementation commit is not an ancestor of HEAD")
    mismatches = v2_runtime_commit_mismatches(root, implementation_commit)
    if mismatches:
        raise ValueError("; ".join(mismatches))

    files = v2_runtime_file_hashes(root)
    return {
        "schema_version": "2.0",
        "artifact": "extension_implementation_freeze",
        "protocol_version": "v2",
        "status": "frozen_before_extension_execution",
        "created_at": created_at or utc_now(),
        "implementation_commit": implementation_commit,
        "runtime_files": files,
        "runtime_bundle_sha256": canonical_sha256(files),
        "hash_normalization": "text_crlf_and_cr_normalized_to_lf; binary_raw_bytes",
        "prompt_contract": prompt_contract(),
        "settings_sha256": sha256_file(root / "config/settings.yaml"),
        "trace_contract_path": relative_path(V2_TRACE_CONTRACT_PATH),
        "trace_contract_sha256": sha256_file(root / V2_TRACE_CONTRACT_PATH),
        "scoring_contract_path": relative_path(V2_SCORING_CONTRACT_PATH),
        "scoring_contract_sha256": sha256_file(root / V2_SCORING_CONTRACT_PATH),
        "dataset_path": relative_path(DATASET_PATH),
        "dataset_sha256": sha256_file(root / DATASET_PATH),
        "holdout_manifest_path": relative_path(HOLDOUT_MANIFEST_PATH),
        "holdout_manifest_sha256": sha256_file(root / HOLDOUT_MANIFEST_PATH),
        "pilot_gate": {
            "contract_path": relative_path(PILOT_GATE_CONTRACT_PATH),
            "contract_sha256": sha256_file(root / PILOT_GATE_CONTRACT_PATH),
            "decision_path": relative_path(PILOT_GATE_DECISION_PATH),
            "decision_sha256": sha256_file(root / PILOT_GATE_DECISION_PATH),
            "report_path": relative_path(PILOT_REPORT_PATH),
            "report_sha256": sha256_file(root / PILOT_REPORT_PATH),
            "status": "go",
        },
        "method_order": list(V2_METHOD_ORDER),
        "python_version": platform.python_version(),
        "dependency_versions": dependency_versions(),
        "runtime_model": model_identity,
        "agent_contract": _agent_contract(root),
        "superseded_v1": _v1_governance(root),
    }


def build_v2_release_record(
    root: Path,
    *,
    implementation_manifest: dict[str, Any],
    released_at: str | None = None,
) -> dict[str, Any]:
    implementation_commit = implementation_manifest["implementation_commit"]
    release_id = f"extension-qwen3-4b-v2-{implementation_commit[:8]}"
    return {
        "schema_version": "2.0",
        "artifact": "extension_holdout_release",
        "protocol_version": "v2",
        "status": "authorized_not_executed",
        "release_id": release_id,
        "released_at": released_at or utc_now(),
        "authorized_implementation_commit": implementation_commit,
        "implementation_manifest_path": relative_path(
            V2_IMPLEMENTATION_MANIFEST_PATH
        ),
        "implementation_manifest_sha256": sha256_file(
            root / V2_IMPLEMENTATION_MANIFEST_PATH
        ),
        "dataset_sha256": implementation_manifest["dataset_sha256"],
        "scoring_contract_sha256": implementation_manifest[
            "scoring_contract_sha256"
        ],
        "trace_contract_sha256": implementation_manifest["trace_contract_sha256"],
        "runtime_bundle_sha256": implementation_manifest["runtime_bundle_sha256"],
        "prompt_contract": implementation_manifest["prompt_contract"],
        "runtime_model": implementation_manifest["runtime_model"],
        "pilot_gate": implementation_manifest["pilot_gate"],
        "superseded_v1": implementation_manifest["superseded_v1"],
        "method_order": list(V2_METHOD_ORDER),
        "maximum_execution_runs": 1,
        "randomization_seed": secrets.randbits(63),
        "execution_state_path": relative_path(V2_EXECUTION_STATE_PATH),
        "execution_receipt_path": relative_path(V2_EXECUTION_RECEIPT_PATH),
        "output_paths": {
            key: relative_path(path) for key, path in V2_FINAL_OUTPUT_PATHS.items()
        },
        "authorized_command": (
            "python scripts/run_extension_evaluation_v2.py --execute-once "
            f"--release-id {release_id} --confirm-one-time-run"
        ),
        "final_result_policy": "v2_final_read_only_after_execution",
    }


def validate_v2_implementation_manifest(
    root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    errors = validate_v2_protocol_contracts(root)
    try:
        decision = load_pilot_gate_decision(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid Stage 8.6 pilot gate decision: {exc}")
        decision = {}
    else:
        errors.extend(validate_pilot_gate_decision(root, decision))

    if manifest.get("artifact") != "extension_implementation_freeze":
        errors.append("invalid v2 implementation manifest artifact")
    if manifest.get("protocol_version") != "v2":
        errors.append("v2 implementation manifest protocol mismatch")
    if manifest.get("status") != "frozen_before_extension_execution":
        errors.append("v2 implementation manifest is not frozen")

    try:
        current_files = v2_runtime_file_hashes(root)
    except (FileNotFoundError, OSError) as exc:
        errors.append(str(exc))
        current_files = []
    if manifest.get("runtime_files") != current_files:
        errors.append("frozen v2 runtime file set or content hash has changed")
    if manifest.get("runtime_bundle_sha256") != canonical_sha256(current_files):
        errors.append("v2 runtime bundle hash mismatch")
    if manifest.get("hash_normalization") != (
        "text_crlf_and_cr_normalized_to_lf; binary_raw_bytes"
    ):
        errors.append("v2 implementation hash normalization contract mismatch")
    if manifest.get("prompt_contract") != prompt_contract():
        errors.append("v2 prompt version, text, or wire schema hash has changed")

    expected_hashes = {
        "settings_sha256": sha256_file(root / "config/settings.yaml"),
        "trace_contract_sha256": sha256_file(root / V2_TRACE_CONTRACT_PATH),
        "scoring_contract_sha256": sha256_file(root / V2_SCORING_CONTRACT_PATH),
        "dataset_sha256": sha256_file(root / DATASET_PATH),
        "holdout_manifest_sha256": sha256_file(root / HOLDOUT_MANIFEST_PATH),
    }
    for field, expected in expected_hashes.items():
        if manifest.get(field) != expected:
            errors.append(f"v2 implementation manifest {field} mismatch")

    expected_gate = {
        "contract_path": relative_path(PILOT_GATE_CONTRACT_PATH),
        "contract_sha256": sha256_file(root / PILOT_GATE_CONTRACT_PATH),
        "decision_path": relative_path(PILOT_GATE_DECISION_PATH),
        "decision_sha256": (
            sha256_file(root / PILOT_GATE_DECISION_PATH)
            if (root / PILOT_GATE_DECISION_PATH).is_file()
            else None
        ),
        "report_path": relative_path(PILOT_REPORT_PATH),
        "report_sha256": (
            sha256_file(root / PILOT_REPORT_PATH)
            if (root / PILOT_REPORT_PATH).is_file()
            else None
        ),
        "status": "go",
    }
    if manifest.get("pilot_gate") != expected_gate:
        errors.append("v2 implementation manifest pilot gate mismatch")
    if manifest.get("method_order") != list(V2_METHOD_ORDER):
        errors.append("v2 implementation method order mismatch")
    if manifest.get("python_version") != platform.python_version():
        errors.append("Python version differs from the v2 implementation freeze")
    if manifest.get("dependency_versions") != dependency_versions():
        errors.append("dependency versions differ from the v2 implementation freeze")
    if manifest.get("agent_contract") != _agent_contract(root):
        errors.append("v2 agent contract differs from the implementation freeze")
    if manifest.get("superseded_v1") != _v1_governance(root):
        errors.append("v2 manifest no longer binds the immutable v1 revocation")

    commit = manifest.get("implementation_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("v2 implementation commit is invalid")
    elif not is_ancestor(root, commit):
        errors.append("v2 implementation commit is not an ancestor of HEAD")
    else:
        mismatches = v2_runtime_commit_mismatches(root, commit)
        if mismatches:
            errors.append("v2 runtime differs from implementation commit: " + "; ".join(mismatches))
        if decision and decision.get("implementation_commit") != commit:
            errors.append("v2 implementation commit differs from the pilot gate")
    return errors


def validate_v2_release_record(
    root: Path,
    release: dict[str, Any],
    implementation_manifest: dict[str, Any],
    *,
    check_runtime_model: bool = False,
    require_unexecuted: bool = False,
) -> list[str]:
    errors = validate_v2_implementation_manifest(root, implementation_manifest)
    if release.get("artifact") != "extension_holdout_release":
        errors.append("invalid v2 extension release artifact")
    if release.get("protocol_version") != "v2":
        errors.append("v2 extension release protocol mismatch")
    if release.get("status") != "authorized_not_executed":
        errors.append("v2 extension release status is invalid")
    commit = implementation_manifest.get("implementation_commit")
    expected_release_id = f"extension-qwen3-4b-v2-{str(commit)[:8]}"
    if release.get("release_id") != expected_release_id:
        errors.append("v2 extension release ID mismatch")
    if release.get("authorized_implementation_commit") != commit:
        errors.append("v2 release commit does not match the implementation manifest")
    if release.get("implementation_manifest_path") != relative_path(
        V2_IMPLEMENTATION_MANIFEST_PATH
    ):
        errors.append("v2 release implementation manifest path mismatch")
    if release.get("implementation_manifest_sha256") != sha256_file(
        root / V2_IMPLEMENTATION_MANIFEST_PATH
    ):
        errors.append("v2 release implementation manifest hash mismatch")
    for field in (
        "dataset_sha256",
        "scoring_contract_sha256",
        "trace_contract_sha256",
        "runtime_bundle_sha256",
        "prompt_contract",
        "runtime_model",
        "pilot_gate",
        "superseded_v1",
        "method_order",
    ):
        if release.get(field) != implementation_manifest.get(field):
            errors.append(f"v2 release {field} does not match the implementation freeze")
    if release.get("maximum_execution_runs") != 1:
        errors.append("v2 extension release must authorize exactly one run")
    seed = release.get("randomization_seed")
    if not isinstance(seed, int) or seed < 0:
        errors.append("v2 extension release randomization seed is invalid")
    if release.get("execution_state_path") != relative_path(V2_EXECUTION_STATE_PATH):
        errors.append("v2 extension execution state path mismatch")
    if release.get("execution_receipt_path") != relative_path(
        V2_EXECUTION_RECEIPT_PATH
    ):
        errors.append("v2 extension execution receipt path mismatch")
    expected_outputs = {
        key: relative_path(path) for key, path in V2_FINAL_OUTPUT_PATHS.items()
    }
    if release.get("output_paths") != expected_outputs:
        errors.append("v2 extension output path contract mismatch")
    expected_command = (
        "python scripts/run_extension_evaluation_v2.py --execute-once "
        f"--release-id {release.get('release_id')} --confirm-one-time-run"
    )
    if release.get("authorized_command") != expected_command:
        errors.append("v2 extension authorized command mismatch")

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
                errors.append("Ollama version or model digest differs from the v2 release")

    if require_unexecuted:
        existing = [
            relative_path(path)
            for path in [
                V2_EXECUTION_STATE_PATH,
                V2_EXECUTION_RECEIPT_PATH,
                *V2_FINAL_OUTPUT_PATHS.values(),
            ]
            if (root / path).exists()
        ]
        if existing:
            errors.append(
                "v2 extension execution artifacts already exist: " + ", ".join(existing)
            )
    return errors


def load_v2_release_artifacts(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    implementation_path = root / V2_IMPLEMENTATION_MANIFEST_PATH
    release_path = root / V2_RELEASE_RECORD_PATH
    if not implementation_path.is_file():
        raise FileNotFoundError("v2 extension implementation manifest does not exist")
    if not release_path.is_file():
        raise FileNotFoundError("v2 extension release record does not exist")
    return read_json(implementation_path), read_json(release_path)


def validate_v2_execution_artifacts(
    root: Path,
    release: dict[str, Any],
) -> tuple[list[str], str]:
    errors: list[str] = []
    state_path = root / V2_EXECUTION_STATE_PATH
    receipt_path = root / V2_EXECUTION_RECEIPT_PATH
    existing_outputs = {
        key: path for key, path in V2_FINAL_OUTPUT_PATHS.items() if (root / path).exists()
    }
    if not state_path.exists() and not receipt_path.exists() and not existing_outputs:
        return errors, "authorized_not_executed"
    if not state_path.is_file():
        return ["v2 extension outputs exist without an execution state"], "invalid"

    try:
        state = read_json(state_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid v2 extension execution state: {exc}"], "invalid"
    if state.get("artifact") != "extension_execution_state":
        errors.append("invalid v2 extension execution state artifact")
    if state.get("protocol_version") != "v2":
        errors.append("v2 execution state protocol mismatch")
    if state.get("release_id") != release.get("release_id"):
        errors.append("v2 execution state release ID mismatch")
    status = state.get("status")
    if status in {"in_progress", "failed_requires_manual_audit"}:
        if receipt_path.exists():
            errors.append("incomplete v2 execution must not have a completion receipt")
        return errors, str(status)
    if status != "completed":
        errors.append("unknown v2 extension execution state status")
        return errors, "invalid"
    if not receipt_path.is_file():
        errors.append("completed v2 extension execution is missing its receipt")
        return errors, "invalid"

    try:
        receipt = read_json(receipt_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid v2 extension execution receipt: {exc}"], "invalid"
    if receipt.get("artifact") != "extension_execution_receipt":
        errors.append("invalid v2 extension execution receipt artifact")
    if receipt.get("protocol_version") != "v2":
        errors.append("v2 execution receipt protocol mismatch")
    if receipt.get("release_id") != release.get("release_id"):
        errors.append("v2 execution receipt release ID mismatch")
    if receipt.get("status") != "completed_once":
        errors.append("v2 execution receipt does not record one completed run")
    if receipt.get("qa_invocation_count") != 23 * len(V2_METHOD_ORDER):
        errors.append("v2 execution receipt QA invocation count mismatch")
    if receipt.get("execution_state_sha256") != sha256_file(state_path):
        errors.append("v2 execution state hash does not match the receipt")
    recorded_outputs = receipt.get("output_hashes", {})
    if set(recorded_outputs) != set(V2_FINAL_OUTPUT_PATHS):
        errors.append("v2 execution receipt output set mismatch")
    for key, expected_path in V2_FINAL_OUTPUT_PATHS.items():
        absolute = root / expected_path
        item = recorded_outputs.get(key, {})
        if not absolute.is_file():
            errors.append(f"completed v2 output is missing: {relative_path(expected_path)}")
            continue
        if item.get("path") != relative_path(expected_path):
            errors.append(f"v2 execution receipt path mismatch: {key}")
        if item.get("sha256") != sha256_file(absolute):
            errors.append(f"v2 execution output hash mismatch: {key}")
    return errors, "completed_once" if not errors else "invalid"


def validate_v2_effective_release_status(
    root: Path,
    release: dict[str, Any],
) -> tuple[list[str], str]:
    if release.get("status") != "authorized_not_executed":
        return ["v2 release status is not authorized_not_executed"], "invalid"
    return validate_v2_execution_artifacts(root, release)
