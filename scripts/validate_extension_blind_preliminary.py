from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_extension_blind_preliminary as builder


def validate(root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    paths = {
        "source": root / "reports" / "extension_v2" / "blind_review.csv",
        "scores": root / "reports" / "extension_v2" / "blind_review_codex_preliminary_scores.csv",
        "output": root / "reports" / "extension_v2" / "blind_review_codex_preliminary.csv",
        "summary": root / "reports" / "extension_v2" / "blind_review_codex_preliminary.md",
        "manifest": root / "reports" / "extension_v2" / "blind_review_codex_preliminary_manifest.json",
        "receipt": root / "reports" / "extension_v2" / "execution_receipt.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return ["missing preliminary review artifacts: " + ", ".join(missing)]

    source = builder.read_csv(paths["source"])
    scores = builder.read_csv(paths["scores"])
    output = builder.read_csv(paths["output"])
    try:
        builder.validate_scores(source, scores)
    except ValueError as exc:
        errors.append(str(exc))

    if len(output) != 92:
        errors.append("preliminary output row count mismatch")
    if [row.get("review_item_id") for row in output] != [
        row.get("review_item_id") for row in source
    ]:
        errors.append("preliminary output order differs from immutable blind source")
    score_by_id = {row["review_item_id"]: row for row in scores}
    for row in output:
        score = score_by_id.get(row.get("review_item_id"))
        if score is None:
            errors.append("preliminary output contains an unknown review item")
            continue
        for field in builder.SCORE_FIELDS + ("review_notes",):
            if row.get(field) != score.get(field):
                errors.append(f"preliminary output score mismatch: {row['review_item_id']} {field}")
        if row.get("reviewer") != builder.REVIEWER:
            errors.append(f"preliminary reviewer mismatch: {row['review_item_id']}")
        if row.get("review_status") != builder.REVIEW_STATUS:
            errors.append(f"preliminary status mismatch: {row['review_item_id']}")
    forbidden = {
        key
        for row in output
        for key in row
        if key == "method_id" or key.startswith("expected")
    }
    if forbidden:
        errors.append("preliminary output exposes forbidden fields: " + ", ".join(sorted(forbidden)))

    manifest: dict[str, Any] = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    expected_hashes = {
        "source_blind_review_sha256": receipt["output_hashes"]["blind_review"]["sha256"],
        "score_map_sha256": builder.sha256_file(paths["scores"]),
        "output_sha256": builder.sha256_file(paths["output"]),
    }
    for field, expected in expected_hashes.items():
        if manifest.get(field) != expected:
            errors.append(f"preliminary manifest {field} mismatch")
    if manifest.get("release_id") != receipt.get("release_id"):
        errors.append("preliminary manifest release ID mismatch")
    if manifest.get("review_status") != builder.REVIEW_STATUS:
        errors.append("preliminary review status is not pending user confirmation")
    if manifest.get("method_identity_read") is not False:
        errors.append("preliminary manifest must record method identity as unread")
    if manifest.get("expected_answer_fields_read") is not False:
        errors.append("preliminary manifest must record expected fields as unread")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("ERROR: preliminary blind review validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: preliminary blind review is internally consistent")
    print("OK: rows=92")
    print("OK: method identity and expected-answer fields remain hidden")
    print("OK: status=preliminary_pending_user_confirmation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
