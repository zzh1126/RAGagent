from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import (
    V2_RELEASE_RECORD_PATH,
    ollama_identity,
    validate_v2_protocol_contracts,
    write_new_json,
)
from src.evaluation.extension_release_v2 import (
    V2_EXECUTION_RECEIPT_PATH,
    V2_EXECUTION_STATE_PATH,
    V2_FINAL_OUTPUT_PATHS,
    V2_IMPLEMENTATION_MANIFEST_PATH,
    build_v2_implementation_manifest,
    build_v2_release_record,
    load_pilot_gate_decision,
    validate_pilot_gate_decision,
    validate_v2_release_record,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze v2 and authorize one future extension holdout run"
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="create immutable v2 implementation and release records",
    )
    args = parser.parse_args()
    if not args.create:
        raise SystemExit("Refusing to create a v2 release without --create.")

    protected_paths = [
        V2_IMPLEMENTATION_MANIFEST_PATH,
        V2_RELEASE_RECORD_PATH,
        V2_EXECUTION_STATE_PATH,
        V2_EXECUTION_RECEIPT_PATH,
        *V2_FINAL_OUTPUT_PATHS.values(),
    ]
    existing = [
        path.as_posix() for path in protected_paths if (PROJECT_ROOT / path).exists()
    ]
    if existing:
        raise SystemExit("Refusing to overwrite v2 extension artifacts: " + ", ".join(existing))

    contract_errors = validate_v2_protocol_contracts(PROJECT_ROOT)
    if contract_errors:
        raise SystemExit("Invalid v2 extension contract: " + "; ".join(contract_errors))
    try:
        pilot_gate = load_pilot_gate_decision(PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Stage 8.6 pilot gate is unavailable: {exc}") from exc
    gate_errors = validate_pilot_gate_decision(PROJECT_ROOT, pilot_gate)
    if gate_errors:
        raise SystemExit("Invalid Stage 8.6 pilot gate: " + "; ".join(gate_errors))

    settings = yaml.safe_load(
        (PROJECT_ROOT / "config/settings.yaml").read_text(encoding="utf-8")
    )
    required_settings = {
        "project.graph_backend": settings["project"].get("graph_backend") == "networkx",
        "agent.planner_backend": settings["agent"].get("planner_backend") == "rule",
        "agent.generator_backend": settings["agent"].get("generator_backend") == "llm",
        "agent.generator_prompt_version": settings["agent"].get(
            "generator_prompt_version"
        )
        == "v2",
        "agent.evidence_packer": settings["agent"].get("evidence_packer")
        == "intent_aware_v2",
        "verification.decision_policy": settings["verification"].get(
            "decision_policy"
        )
        == "partial_pass",
    }
    failed_settings = [name for name, valid in required_settings.items() if not valid]
    if failed_settings:
        raise SystemExit(
            "The v2 release settings are not frozen as required: "
            + ", ".join(failed_settings)
        )

    frozen_model = settings["llm"]["model"]
    model_override = os.environ.get("OLLAMA_MODEL")
    if model_override and model_override != frozen_model:
        raise SystemExit("OLLAMA_MODEL differs from the model in frozen settings.yaml.")
    base_url = os.environ.get("OLLAMA_BASE_URL", settings["llm"]["base_url"])
    model = ollama_identity(base_url, frozen_model)
    implementation_commit = pilot_gate["implementation_commit"]
    manifest = build_v2_implementation_manifest(
        PROJECT_ROOT,
        implementation_commit=implementation_commit,
        model_identity=model,
        pilot_gate_decision=pilot_gate,
    )
    write_new_json(PROJECT_ROOT / V2_IMPLEMENTATION_MANIFEST_PATH, manifest)
    release = build_v2_release_record(
        PROJECT_ROOT,
        implementation_manifest=manifest,
    )
    write_new_json(PROJECT_ROOT / V2_RELEASE_RECORD_PATH, release)

    errors = validate_v2_release_record(
        PROJECT_ROOT,
        release,
        manifest,
        check_runtime_model=True,
        require_unexecuted=True,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(
            "v2 release files were created but failed validation; do not execute extension."
        )
    print(f"OK: implementation_commit={implementation_commit}")
    print(f"OK: runtime_bundle_sha256={manifest['runtime_bundle_sha256']}")
    print(f"OK: prompt_sha256={manifest['prompt_contract']['system_prompt_sha256']}")
    print(f"OK: wire_schema_sha256={manifest['prompt_contract']['wire_schema_sha256']}")
    print(f"OK: model_digest={model['model_digest']}")
    print(f"OK: release_id={release['release_id']} status=authorized_not_executed")


if __name__ == "__main__":
    main()
