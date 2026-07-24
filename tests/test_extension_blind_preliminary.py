from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_extension_blind_preliminary.py"
SPEC = importlib.util.spec_from_file_location("build_extension_blind_preliminary", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

VALIDATOR_PATH = ROOT / "scripts" / "validate_extension_blind_preliminary.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_extension_blind_preliminary", VALIDATOR_PATH
)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def test_preliminary_score_map_matches_immutable_blind_source() -> None:
    source = MODULE.read_csv(MODULE.SOURCE_PATH)
    scores = MODULE.read_csv(MODULE.SCORES_PATH)
    MODULE.validate_scores(source, scores)
    assert len(source) == 92
    assert "blind_method_key" not in MODULE_PATH.read_text(encoding="utf-8")
    receipt = json.loads(MODULE.RECEIPT_PATH.read_text(encoding="utf-8"))
    assert MODULE.sha256_file(MODULE.SOURCE_PATH) == receipt["output_hashes"]["blind_review"]["sha256"]


def test_preliminary_output_keeps_method_identity_hidden() -> None:
    rows = MODULE.read_csv(MODULE.OUTPUT_PATH)
    assert len(rows) == 92
    assert all("method_id" not in row for row in rows)
    assert all("expected_behavior" not in row for row in rows)
    assert {row["answer_label"] for row in rows} == {"A", "B", "C", "D"}
    assert {row["review_status"] for row in rows} == {
        "preliminary_pending_user_confirmation"
    }
    manifest = json.loads(MODULE.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["method_identity_read"] is False
    assert manifest["expected_answer_fields_read"] is False


def test_preliminary_artifacts_validate_without_unblinding() -> None:
    assert VALIDATOR.validate(ROOT) == []
