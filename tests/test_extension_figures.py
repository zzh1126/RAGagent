from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "generate_extension_figures.py"
SPEC = importlib.util.spec_from_file_location("generate_extension_figures", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_user_confirmed_extension_figures_are_current() -> None:
    MODULE.check(MODULE.DEFAULT_OUTPUT_DIR)


def test_extension_category_correctness_is_recomputed_from_confirmed_rows() -> None:
    metrics, rows = MODULE.load_inputs()
    scores = MODULE.category_correctness(rows)

    assert metrics["release_id"] == "extension-qwen3-4b-v2-e207cb91"
    assert len(rows) == 92
    assert len({row["question_id"] for row in rows}) == 23
    assert scores["rule_baseline"]["metric_selection"] == pytest.approx(0.25)
    assert scores["llm_strict_v2"]["no_answer"] == pytest.approx(1.0)
    assert scores["llm_no_verifier_v2"]["no_answer"] == pytest.approx(0.375)
    assert scores["llm_partial_pass_v2"]["principle_pros_cons"] == pytest.approx(1 / 6)
    assert scores["llm_partial_pass_v2"]["metric_selection"] == pytest.approx(0.0)
