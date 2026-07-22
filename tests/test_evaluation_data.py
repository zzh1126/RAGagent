import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {
    "single_hop": 8,
    "multi_hop": 9,
    "definition": 7,
    "comparison": 5,
    "principle_pros_cons": 5,
    "metric_selection": 2,
    "no_answer": 4,
}
EXPECTED_EXTENSION_COUNTS = {
    "single_hop": 4,
    "multi_hop": 4,
    "definition": 3,
    "comparison": 3,
    "principle_pros_cons": 3,
    "metric_selection": 2,
    "no_answer": 4,
}


def read_questions(name: str) -> list[dict]:
    path = ROOT / "data" / "evaluation" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def test_final_evaluation_distribution_is_frozen():
    questions = read_questions("final_questions.jsonl")

    assert len(questions) == 40
    assert Counter(item["category"] for item in questions) == EXPECTED_COUNTS
    assert sum(item["expected_behavior"] == "refuse" for item in questions) == 4


def test_final_questions_do_not_overlap_tuning_sets():
    final_text = {item["question"] for item in read_questions("final_questions.jsonl")}
    dev_text = {item["question"] for item in read_questions("dev_questions.jsonl")}
    pilot_text = {item["question"] for item in read_questions("pilot_questions.jsonl")}

    assert not final_text & dev_text
    assert not final_text & pilot_text


def test_extension_holdout_distribution_is_frozen():
    questions = read_questions("extension_questions.jsonl")

    assert len(questions) == 23
    assert Counter(item["category"] for item in questions) == EXPECTED_EXTENSION_COUNTS
    assert sum(item["expected_behavior"] == "refuse" for item in questions) == 4


def test_extension_questions_do_not_overlap_prior_sets():
    extension_text = {item["question"] for item in read_questions("extension_questions.jsonl")}
    for name in (
        "dev_questions.jsonl",
        "demo_questions.jsonl",
        "pilot_questions.jsonl",
        "final_questions.jsonl",
    ):
        assert not extension_text & {item["question"] for item in read_questions(name)}
