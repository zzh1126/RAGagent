from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import (
    EXECUTION_RECEIPT_PATH,
    EXECUTION_STATE_PATH,
    FINAL_OUTPUT_PATHS,
    IMPLEMENTATION_MANIFEST_PATH,
    RELEASE_RECORD_PATH,
    build_implementation_manifest,
    build_release_record,
    current_commit,
    ollama_identity,
    tracked_worktree_is_clean,
    validate_static_contracts,
    validate_release_record,
    write_new_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the extension implementation and authorize one holdout run"
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="create the immutable implementation manifest and one-time release record",
    )
    args = parser.parse_args()
    if not args.create:
        raise SystemExit("Refusing to create a release without the explicit --create flag.")
    if not tracked_worktree_is_clean(PROJECT_ROOT):
        raise SystemExit(
            "Refusing to freeze an implementation with staged or unstaged tracked changes."
        )

    protected_paths = [
        IMPLEMENTATION_MANIFEST_PATH,
        RELEASE_RECORD_PATH,
        EXECUTION_STATE_PATH,
        EXECUTION_RECEIPT_PATH,
        *FINAL_OUTPUT_PATHS.values(),
    ]
    existing = [path.as_posix() for path in protected_paths if (PROJECT_ROOT / path).exists()]
    if existing:
        raise SystemExit("Refusing to overwrite extension artifacts: " + ", ".join(existing))

    contract_errors = validate_static_contracts(PROJECT_ROOT)
    if contract_errors:
        raise SystemExit("Static extension contract is invalid: " + "; ".join(contract_errors))

    settings = yaml.safe_load(
        (PROJECT_ROOT / "config/settings.yaml").read_text(encoding="utf-8")
    )
    if settings["project"].get("graph_backend") != "networkx":
        raise SystemExit("The extension release requires graph_backend=networkx.")
    if settings["agent"].get("planner_backend") != "rule":
        raise SystemExit("The extension release requires the rule planner.")
    if settings["agent"].get("generator_backend") != "llm":
        raise SystemExit("The extension release requires the LLM generator configuration.")

    frozen_model = settings["llm"]["model"]
    model_override = os.environ.get("OLLAMA_MODEL")
    if model_override and model_override != frozen_model:
        raise SystemExit("OLLAMA_MODEL differs from the model in frozen settings.yaml.")
    base_url = os.environ.get("OLLAMA_BASE_URL", settings["llm"]["base_url"])
    model = ollama_identity(base_url, frozen_model)
    commit = current_commit(PROJECT_ROOT)
    manifest = build_implementation_manifest(
        PROJECT_ROOT,
        implementation_commit=commit,
        model_identity=model,
    )
    write_new_json(PROJECT_ROOT / IMPLEMENTATION_MANIFEST_PATH, manifest)
    release = build_release_record(PROJECT_ROOT, implementation_manifest=manifest)
    write_new_json(PROJECT_ROOT / RELEASE_RECORD_PATH, release)

    errors = validate_release_record(
        PROJECT_ROOT,
        release,
        manifest,
        check_runtime_model=True,
        require_unexecuted=True,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit("Release files were created but failed validation; do not execute extension.")
    print(f"OK: implementation_commit={commit}")
    print(f"OK: runtime_bundle_sha256={manifest['runtime_bundle_sha256']}")
    print(f"OK: prompt_sha256={manifest['prompt_contract']['system_prompt_sha256']}")
    print(f"OK: trace_contract_sha256={manifest['trace_contract_sha256']}")
    print(f"OK: model_digest={model['model_digest']}")
    print(f"OK: release_id={release['release_id']} status=authorized_not_executed")


if __name__ == "__main__":
    main()
