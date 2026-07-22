from scripts.probe_llm_structured import (
    AnswerPayloadProbe,
    ProbeClaim,
    QueryPlanPayload,
    summarize_results,
    validate_answer,
    validate_query_plan,
)


def test_query_plan_semantics_accept_expected_route() -> None:
    plan = QueryPlanPayload(
        intent="relation",
        entities=["随机森林"],
        retrieval_mode="graph",
        query_en="random forest model family",
        required_aspects=["模型族"],
        confidence=0.9,
    )

    assert validate_query_plan(plan) == []


def test_query_plan_semantics_reject_wrong_route() -> None:
    plan = QueryPlanPayload(
        intent="definition",
        entities=["随机森林"],
        retrieval_mode="vector",
        query_en="random forest model family",
        required_aspects=["模型族"],
        confidence=0.9,
    )

    errors = validate_query_plan(plan)

    assert "intent must be relation" in errors
    assert "retrieval_mode must be graph" in errors


def test_answer_semantics_reject_unknown_references() -> None:
    answer = AnswerPayloadProbe(
        answer="随机森林属于集成学习。",
        claims=[
            ProbeClaim(
                claim="随机森林属于集成学习。",
                text_evidence_ids=["E2"],
                graph_path_ids=["P2"],
            )
        ],
    )

    errors = validate_answer(answer)

    assert "unknown text evidence IDs: ['E2']" in errors
    assert "unknown graph path IDs: ['P2']" in errors


def test_summary_separates_generator_and_planner_gates() -> None:
    results = []
    for scenario, successes in (
        ("simple_status", 20),
        ("query_plan", 18),
        ("nested_answer", 20),
    ):
        for index in range(20):
            success = index < successes
            results.append(
                {
                    "scenario": scenario,
                    "success": success,
                    "content_nonempty": True,
                    "thinking_empty": True,
                    "schema_valid": True,
                    "wall_ms": 100.0,
                }
            )

    summary = summarize_results(
        results,
        scenario_names=["simple_status", "query_plan", "nested_answer"],
        minimum_success_rate=0.95,
        target_gate="generator",
    )

    assert summary["total_schema_successes"] == 60
    assert summary["total_semantic_successes"] == 58
    assert summary["per_scenario"]["query_plan"]["semantic_success_rate"] == 0.9
    assert summary["structured_output_gate_passed"] is True
    assert summary["generator_gate_passed"] is True
    assert summary["planner_gate_passed"] is False
    assert summary["full_agent_gate_passed"] is False
    assert summary["gate_passed"] is True
