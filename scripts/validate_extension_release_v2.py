from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release_v2 import (
    load_v2_release_artifacts,
    validate_v2_effective_release_status,
    validate_v2_release_record,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the immutable v2 release")
    parser.add_argument("--check-runtime-model", action="store_true")
    parser.add_argument("--require-unexecuted", action="store_true")
    args = parser.parse_args()
    try:
        implementation, release = load_v2_release_artifacts(PROJECT_ROOT)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    errors = validate_v2_release_record(
        PROJECT_ROOT,
        release,
        implementation,
        check_runtime_model=args.check_runtime_model,
        require_unexecuted=args.require_unexecuted,
    )
    status_errors, execution_status = validate_v2_effective_release_status(
        PROJECT_ROOT,
        release,
    )
    errors.extend(status_errors)
    if args.require_unexecuted and execution_status != "authorized_not_executed":
        errors.append(
            "v2 extension is not authorized_not_executed: " + execution_status
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"OK: release_id={release['release_id']}")
    print(f"OK: effective_execution_status={execution_status}")
    print(f"OK: implementation_commit={implementation['implementation_commit']}")
    print(f"OK: runtime_bundle_sha256={implementation['runtime_bundle_sha256']}")
    print(f"OK: model_digest={implementation['runtime_model']['model_digest']}")


if __name__ == "__main__":
    main()
