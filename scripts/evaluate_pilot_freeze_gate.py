from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.extension_release import read_json, write_new_json
from src.evaluation.pilot_gate import (
    PILOT_GATE_DECISION_PATH,
    PILOT_REPORT_PATH,
    PILOT_STATE_PATH,
    evaluate_pilot_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the predeclared Stage 8.6 pilot freeze gate"
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="create the immutable Go/No-Go decision from the consumed pilot",
    )
    args = parser.parse_args()
    if not args.evaluate:
        raise SystemExit("Refusing to evaluate the pilot without --evaluate.")

    report_path = PROJECT_ROOT / PILOT_REPORT_PATH
    state_path = PROJECT_ROOT / PILOT_STATE_PATH
    decision_path = PROJECT_ROOT / PILOT_GATE_DECISION_PATH
    if decision_path.exists():
        raise SystemExit("Refusing to overwrite the Stage 8.6 pilot gate decision.")
    if not report_path.is_file() or not state_path.is_file():
        raise SystemExit("The one-time Stage 8.6 pilot has not completed.")

    try:
        report = read_json(report_path)
        state = read_json(state_path)
        decision = evaluate_pilot_report(PROJECT_ROOT, report, state)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to evaluate the Stage 8.6 pilot gate: {exc}") from exc

    write_new_json(decision_path, decision)
    print(f"OK: decision={decision['status']}")
    print(f"OK: failed_checks={decision['failed_check_ids']}")
    print(f"OK: decision_path={PILOT_GATE_DECISION_PATH.as_posix()}")
    if decision["status"] != "go":
        raise SystemExit(
            "Stage 8.6 pilot is No-Go. The pilot is consumed and must not be rerun."
        )


if __name__ == "__main__":
    main()
