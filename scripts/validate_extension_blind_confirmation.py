from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_extension_blind_preliminary as preliminary
import confirm_extension_blind_review as confirmation


def validate(root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    paths = [
        confirmation.CONFIRMED_CSV_PATH,
        confirmation.UNBLINDED_CSV_PATH,
        confirmation.HUMAN_METRICS_PATH,
        confirmation.COMBINED_METRICS_PATH,
        confirmation.SUMMARY_PATH,
        confirmation.CONFIRMATION_MANIFEST_PATH,
    ]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        return ["missing confirmed review outputs: " + ", ".join(missing)]

    preliminary_rows = preliminary.read_csv(preliminary.OUTPUT_PATH)
    confirmed_rows = preliminary.read_csv(confirmation.CONFIRMED_CSV_PATH)
    unblinded_rows = preliminary.read_csv(confirmation.UNBLINDED_CSV_PATH)
    if confirmation.score_signature(preliminary_rows) != confirmation.score_signature(confirmed_rows):
        errors.append("confirmed scores differ from the user-reviewed preliminary source")
    if any("method_id" in row or "expected_behavior" in row for row in confirmed_rows):
        errors.append("confirmed blind CSV must remain anonymous")
    if len(unblinded_rows) != 92:
        errors.append("unblinded confirmed row count mismatch")
    if {row.get("review_status") for row in confirmed_rows} != {confirmation.CONFIRMED_STATUS}:
        errors.append("confirmed blind CSV status mismatch")
    if {row.get("method_id") for row in unblinded_rows} != set(
        confirmation.read_json(confirmation.AUTO_METRICS_PATH)["method_order"]
    ):
        errors.append("unblinded method set mismatch")

    automatic = confirmation.read_json(confirmation.AUTO_METRICS_PATH)
    expected_human = confirmation.build_human_metrics(unblinded_rows, automatic["method_order"])
    human = confirmation.read_json(confirmation.HUMAN_METRICS_PATH)
    if human != expected_human:
        errors.append("confirmed human metrics do not recompute")
    combined = confirmation.read_json(confirmation.COMBINED_METRICS_PATH)
    if combined != confirmation.build_combined_metrics(automatic, human):
        errors.append("confirmed combined metrics do not recompute")

    manifest = confirmation.read_json(confirmation.CONFIRMATION_MANIFEST_PATH)
    if manifest.get("review_status") != confirmation.CONFIRMED_STATUS:
        errors.append("confirmation manifest status mismatch")
    if manifest.get("scores_promoted_without_mutation") is not True:
        errors.append("confirmation manifest does not preserve the score signature")
    expected_output_hashes = {
        path.name: preliminary.sha256_file(path)
        for path in confirmation.OUTPUT_PATHS
        if path != confirmation.CONFIRMATION_MANIFEST_PATH
    }
    if manifest.get("output_hashes") != expected_output_hashes:
        errors.append("confirmation manifest output hashes mismatch")
    receipt = confirmation.read_json(preliminary.RECEIPT_PATH)
    if manifest.get("input_hashes", {}).get("immutable_blind_review") != receipt[
        "output_hashes"
    ]["blind_review"]["sha256"]:
        errors.append("confirmation no longer binds the immutable blind review")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("ERROR: confirmed extension blind review validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: user-confirmed extension scoring is internally consistent")
    print("OK: rows=92 methods=4 questions_per_method=23")
    print("OK: score signature unchanged from the reviewed preliminary source")
    print("OK: review_status=user_confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
