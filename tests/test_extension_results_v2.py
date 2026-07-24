from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_extension_results_v2.py"
SPEC = importlib.util.spec_from_file_location("validate_extension_results_v2", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_completed_v2_extension_results_validate() -> None:
    errors, summary = MODULE.validate_results(ROOT)

    assert errors == []
    assert summary["execution_status"] == "completed_once"
    assert summary["question_count_per_method"] == 23
    assert summary["qa_invocation_count"] == 92


def test_forbidden_persisted_model_keys_are_detected() -> None:
    assert MODULE.find_forbidden_keys({"safe": [{"thinking": "hidden"}]}) == [
        "$.safe[0].thinking"
    ]
