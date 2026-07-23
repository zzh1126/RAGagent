from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import (
    load_release_artifacts,
    validate_effective_release_status,
    validate_release_record,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the extension implementation release")
    parser.add_argument("--check-runtime-model", action="store_true")
    parser.add_argument("--require-unexecuted", action="store_true")
    args = parser.parse_args()
    try:
        implementation, release = load_release_artifacts(PROJECT_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    status_errors, execution_status = validate_effective_release_status(
        PROJECT_ROOT,
        release,
    )
    if execution_status == "revoked_before_execution":
        if status_errors:
            for error in status_errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)
        print(f"OK: historical_release_id={release['release_id']}")
        print(f"OK: implementation_commit={implementation['implementation_commit']}")
        print(f"OK: runtime_bundle_sha256={implementation['runtime_bundle_sha256']}")
        print("OK: effective_execution_status=revoked_before_execution")
        print("OK: revocation audit is valid; this historical release is not executable")
        return
    if execution_status == "revocation_invalid":
        for error in status_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    errors = validate_release_record(
        PROJECT_ROOT,
        release,
        implementation,
        check_runtime_model=args.check_runtime_model,
        require_unexecuted=args.require_unexecuted,
    )
    errors.extend(status_errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"OK: release_id={release['release_id']}")
    print(f"OK: implementation_commit={implementation['implementation_commit']}")
    print(f"OK: runtime_bundle_sha256={implementation['runtime_bundle_sha256']}")
    print(f"OK: prompt_sha256={implementation['prompt_contract']['system_prompt_sha256']}")
    print(f"OK: trace_contract_sha256={implementation['trace_contract_sha256']}")
    print("OK: extension release is valid")


if __name__ == "__main__":
    main()
