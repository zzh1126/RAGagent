from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_extension_blind_confirmation.py"
SPEC = importlib.util.spec_from_file_location("validate_extension_blind_confirmation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_user_confirmed_extension_scoring_validates() -> None:
    assert MODULE.validate(ROOT) == []


def test_user_confirmed_metrics_cover_all_methods() -> None:
    path = ROOT / "reports" / "extension_v2" / "human_metrics_user_confirmed.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    assert metrics["review_status"] == "user_confirmed"
    assert set(metrics["methods"]) == {
        "rule_baseline",
        "llm_strict_v2",
        "llm_no_verifier_v2",
        "llm_partial_pass_v2",
    }
    assert all(method["question_count"] == 23 for method in metrics["methods"].values())
