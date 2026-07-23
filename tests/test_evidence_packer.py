from __future__ import annotations

from src.agent.generators import EvidencePacker
from src.schemas import (
    GraphPath,
    GraphTriple,
    LinkedEntity,
    RetrievalResult,
    TextEvidence,
)


def evidence(
    evidence_id: str,
    chunk_id: str,
    *,
    title: str,
    heading: str,
    text: str,
    score: float = 0.5,
) -> TextEvidence:
    return TextEvidence(
        evidence_id=evidence_id,
        chunk_id=chunk_id,
        source_id="S1",
        page_title=title,
        heading_path=[heading],
        url=f"https://scikit-learn.org/stable/modules/example.html#{chunk_id}",
        display_text=text,
        score=score,
    )


def entity(entity_id: str, name_en: str, name_zh: str) -> LinkedEntity:
    return LinkedEntity(
        entity_id=entity_id,
        name_en=name_en,
        name_zh=name_zh,
        type="Algorithm",
        matched_text=name_zh,
    )


def path(path_id: str, chunk_id: str) -> GraphPath:
    return GraphPath(
        path_id=path_id,
        triples=[
            GraphTriple(
                source_id=f"SRC_{path_id}",
                source_name=f"Source {path_id}",
                relation="USES",
                target_id=f"DST_{path_id}",
                target_name=f"Target {path_id}",
                relation_id=f"R_{path_id}",
                evidence_chunk_ids=[chunk_id],
                review_status="approved",
            )
        ],
        evidence_chunk_ids=[chunk_id],
    )


def test_packing_is_deterministic_deduplicated_and_non_mutating() -> None:
    retrieval = RetrievalResult(
        intent="general",
        mode="vector",
        text_evidence=[
            evidence(
                "E1",
                "C1",
                title="Random forests",
                heading="Overview",
                text="Random forests average randomized trees.",
                score=0.8,
            ),
            evidence(
                "E2",
                "C1",
                title="Duplicate random forests",
                heading="Duplicate",
                text="This duplicate must not enter the packed context.",
                score=0.9,
            ),
            evidence(
                "E3",
                "C3",
                title="Decision trees",
                heading="Overview",
                text="Decision trees partition the feature space.",
                score=0.7,
            ),
        ],
    )
    original = retrieval.model_dump(mode="json")
    packer = EvidencePacker(max_text_evidence=2, max_context_chars=2500)

    first = packer.pack("随机森林", retrieval)
    second = packer.pack("随机森林", retrieval)

    assert first.context == second.context
    assert first.trace.selected_evidence_ids == second.trace.selected_evidence_ids
    assert first.trace.selected_chunk_ids == second.trace.selected_chunk_ids
    assert first.trace.reason_codes_by_evidence == second.trace.reason_codes_by_evidence
    assert first.trace.coverage_gaps == second.trace.coverage_gaps
    assert retrieval.model_dump(mode="json") == original
    assert first.trace.input_evidence_count == 3
    assert first.trace.deduplicated_evidence_count == 2
    assert len(first.trace.selected_chunk_ids) == len(set(first.trace.selected_chunk_ids))
    assert set(first.trace.selected_evidence_ids) <= {"E1", "E2", "E3"}
    assert "E2" not in first.trace.selected_evidence_ids
    assert "E2" in first.trace.dropped_evidence_ids


def test_definition_prioritizes_entity_title_over_unrelated_high_score() -> None:
    retrieval = RetrievalResult(
        intent="definition",
        mode="vector",
        entities=[entity("ALG_RF", "Random Forest", "随机森林")],
        text_evidence=[
            evidence(
                "E1",
                "C1",
                title="General ensemble notes",
                heading="Overview",
                text="Ensemble estimators combine predictions.",
                score=0.99,
            ),
            evidence(
                "E2",
                "C2",
                title="Random Forests",
                heading="Definition",
                text="A random forest is an ensemble of randomized decision trees.",
                score=0.4,
            ),
            evidence(
                "E3",
                "C3",
                title="Tree ensembles",
                heading="Description",
                text="Random forest estimators average multiple trees.",
                score=0.3,
            ),
        ],
    )
    packed = EvidencePacker(max_text_evidence=2).pack("什么是随机森林", retrieval)

    assert packed.trace.selected_evidence_ids[0] == "E2"
    assert "definition_direct" in packed.trace.reason_codes_by_evidence["E2"]
    assert packed.trace.entity_coverage["ALG_RF"] == 2
    assert not any(
        gap.startswith("definition_direct_evidence_missing")
        for gap in packed.trace.coverage_gaps
    )


def test_entity_title_matching_ignores_hyphen_variants() -> None:
    retrieval = RetrievalResult(
        intent="definition",
        mode="vector",
        entities=[entity("ALG_KMEANS", "KMeans", "KMeans")],
        text_evidence=[
            evidence(
                "E1",
                "C1",
                title="Clustering",
                heading="K-means",
                text="The KMeans algorithm separates samples into groups.",
            )
        ],
    )

    packed = EvidencePacker(max_text_evidence=1).pack("什么是 KMeans", retrieval)

    assert packed.trace.selected_evidence_ids == ["E1"]
    assert "definition_direct" in packed.trace.reason_codes_by_evidence["E1"]
    assert packed.trace.coverage_gaps == []


def test_comparison_reserves_two_evidence_items_for_each_entity() -> None:
    retrieval = RetrievalResult(
        intent="comparison",
        mode="hybrid",
        entities=[
            entity("ALG_BAG", "Bagging", "装袋法"),
            entity("ALG_ADA", "AdaBoost", "AdaBoost"),
        ],
        text_evidence=[
            evidence(
                "E0",
                "C0",
                title="Unrelated high score",
                heading="Overview",
                text="A generic ensemble paragraph.",
                score=1.0,
            ),
            evidence(
                "E1",
                "CB1",
                title="Bagging",
                heading="Training",
                text="Bagging trains estimators on random subsets.",
                score=0.5,
            ),
            evidence(
                "E2",
                "CB2",
                title="Bagging",
                heading="Properties",
                text="Bagging combines independent estimator predictions.",
                score=0.4,
            ),
            evidence(
                "E3",
                "CA1",
                title="AdaBoost",
                heading="Training",
                text="AdaBoost trains weak learners sequentially.",
                score=0.3,
            ),
            evidence(
                "E4",
                "CA2",
                title="AdaBoost",
                heading="Properties",
                text="AdaBoost forms a weighted classifier ensemble.",
                score=0.2,
            ),
        ],
    )
    packed = EvidencePacker(max_text_evidence=4).pack(
        "Bagging 和 AdaBoost 有什么区别",
        retrieval,
    )

    assert set(packed.trace.selected_evidence_ids) == {"E1", "E2", "E3", "E4"}
    assert packed.trace.entity_coverage == {"ALG_BAG": 2, "ALG_ADA": 2}
    assert not any(
        gap.startswith("comparison_entity_under_quota")
        for gap in packed.trace.coverage_gaps
    )
    assert all(
        "comparison_entity_balance" in packed.trace.reason_codes_by_evidence[item]
        for item in packed.trace.selected_evidence_ids
    )


def test_explanation_balances_mechanism_advantage_and_limitation() -> None:
    retrieval = RetrievalResult(
        intent="explanation",
        mode="hybrid",
        entities=[entity("ALG_RF", "Random Forest", "随机森林")],
        text_evidence=[
            evidence(
                "E1",
                "CM",
                title="Random Forest mechanism",
                heading="How it works",
                text="The algorithm works by training randomized trees and averaging predictions.",
            ),
            evidence(
                "E2",
                "CA",
                title="Random Forest advantages",
                heading="Variance reduction",
                text="Averaging can reduce variance and improve robustness.",
            ),
            evidence(
                "E3",
                "CL",
                title="Random Forest limitations",
                heading="Computational cost",
                text="A limitation is increased memory and computational cost.",
            ),
            evidence(
                "E4",
                "CU",
                title="Unrelated",
                heading="Other",
                text="This paragraph has the highest retrieval score.",
                score=1.0,
            ),
        ],
    )
    packed = EvidencePacker(max_text_evidence=3).pack(
        "随机森林为什么更稳定，有什么局限",
        retrieval,
    )

    assert set(packed.trace.selected_evidence_ids) == {"E1", "E2", "E3"}
    assert packed.trace.coverage_gaps == []
    assert "explanation_mechanism" in packed.trace.reason_codes_by_evidence["E1"]
    assert "explanation_advantage" in packed.trace.reason_codes_by_evidence["E2"]
    assert "explanation_limitation" in packed.trace.reason_codes_by_evidence["E3"]


def test_multi_hop_prioritizes_one_bound_chunk_per_path() -> None:
    retrieval = RetrievalResult(
        intent="multi_hop",
        mode="hybrid",
        graph_paths=[path("P1", "C1"), path("P2", "C2")],
        text_evidence=[
            evidence(
                "E0",
                "C0",
                title="Unrelated",
                heading="High score",
                text="This evidence is not bound to a graph path.",
                score=1.0,
            ),
            evidence(
                "E1",
                "C1",
                title="First hop",
                heading="Evidence",
                text="Evidence for the first graph path.",
                score=0.2,
            ),
            evidence(
                "E2",
                "C2",
                title="Second hop",
                heading="Evidence",
                text="Evidence for the second graph path.",
                score=0.1,
            ),
        ],
    )
    packed = EvidencePacker(max_text_evidence=2, max_graph_paths=2).pack(
        "算法与指标之间有什么关系路径",
        retrieval,
    )

    assert packed.trace.selected_evidence_ids == ["E1", "E2"]
    assert packed.trace.selected_graph_path_ids == ["P1", "P2"]
    assert not any(
        gap.startswith("multi_hop_path_uncovered")
        for gap in packed.trace.coverage_gaps
    )
    assert all(
        "multi_hop_path_coverage" in packed.trace.reason_codes_by_evidence[item]
        for item in ("E1", "E2")
    )


def test_zero_graph_path_budget_exposes_no_path_ids() -> None:
    retrieval = RetrievalResult(
        intent="relation",
        mode="graph",
        graph_paths=[path("P1", "C1")],
        text_evidence=[
            evidence(
                "E1",
                "C1",
                title="Relation evidence",
                heading="Uses",
                text="The source uses the target.",
            )
        ],
    )

    packed = EvidencePacker(max_graph_paths=0).pack("使用关系", retrieval)

    assert packed.trace.selected_graph_path_ids == []
    assert "AVAILABLE_GRAPH_PATH_IDS: (none)" in packed.context


def test_path_removed_by_character_budget_is_removed_from_reason_trace() -> None:
    oversized_path = path("P1", "C1")
    oversized_path.triples[0].source_id = "X" * 1500
    retrieval = RetrievalResult(
        intent="relation",
        mode="graph",
        graph_paths=[oversized_path],
        text_evidence=[
            evidence(
                "E1",
                "C1",
                title="Relation evidence",
                heading="Uses",
                text="The source uses the target.",
            )
        ],
    )

    packed = EvidencePacker(
        max_text_evidence=1,
        max_graph_paths=1,
        max_context_chars=1000,
    ).pack("使用关系", retrieval)

    assert packed.trace.selected_graph_path_ids == []
    assert "graph_path_bound" not in packed.trace.reason_codes_by_evidence["E1"]
    assert "context_budget_dropped_path:P1" in packed.trace.coverage_gaps


def test_recommendation_keeps_metric_definition_and_usage_scenario() -> None:
    retrieval = RetrievalResult(
        intent="recommendation",
        mode="hybrid",
        text_evidence=[
            evidence(
                "E0",
                "C0",
                title="Unrelated",
                heading="Overview",
                text="A high-scoring paragraph without metric guidance.",
                score=1.0,
            ),
            evidence(
                "E1",
                "CD",
                title="Balanced accuracy score",
                heading="Definition",
                text="Balanced accuracy is a metric defined as average recall across classes.",
                score=0.3,
            ),
            evidence(
                "E2",
                "CS",
                title="Choosing a score",
                heading="Usage",
                text="This score is useful when classes are imbalanced.",
                score=0.2,
            ),
        ],
    )
    packed = EvidencePacker(max_text_evidence=2).pack(
        "类别不平衡时用什么指标",
        retrieval,
    )

    assert packed.trace.selected_evidence_ids == ["E1", "E2"]
    assert packed.trace.coverage_gaps == []
    assert "recommendation_definition" in packed.trace.reason_codes_by_evidence["E1"]
    assert "recommendation_scenario" in packed.trace.reason_codes_by_evidence["E2"]


def test_context_budget_is_strict_without_cutting_structural_blocks() -> None:
    retrieval = RetrievalResult(
        intent="general",
        mode="vector",
        text_evidence=[
            evidence(
                f"E{index}",
                f"C{index}",
                title=f"Evidence {index}",
                heading="Long text",
                text=(f"token{index} " * 1000),
                score=1.0 / index,
            )
            for index in range(1, 7)
        ],
    )
    packed = EvidencePacker(
        max_text_evidence=4,
        max_chars_per_evidence=900,
        max_context_chars=2000,
    ).pack("general evidence question", retrieval)

    assert len(packed.context) <= 2000
    assert packed.trace.packed_character_count == len(packed.context)
    assert len(packed.trace.selected_evidence_ids) == 4
    assert set(packed.trace.selected_evidence_ids) <= {
        item.evidence_id for item in retrieval.text_evidence
    }
    assert set(packed.trace.truncated_evidence_ids) == set(
        packed.trace.selected_evidence_ids
    )
    assert packed.trace.dropped_evidence_ids == ["E5", "E6"]
    assert "AVAILABLE_TEXT_EVIDENCE_IDS: E1, E2, E3, E4" in packed.context
    for evidence_id in packed.trace.selected_evidence_ids:
        assert f"[{evidence_id}]" in packed.context


def test_intent_target_limits_noise_below_the_hard_item_ceiling() -> None:
    retrieval = RetrievalResult(
        intent="general",
        mode="vector",
        text_evidence=[
            evidence(
                f"E{index}",
                f"C{index}",
                title=f"Candidate {index}",
                heading="General",
                text=f"General evidence candidate {index}.",
                score=1.0 / index,
            )
            for index in range(1, 9)
        ],
    )

    packed = EvidencePacker(max_text_evidence=8).pack("general question", retrieval)

    assert packed.trace.max_text_evidence == 8
    assert packed.trace.selection_target == 6
    assert len(packed.trace.selected_evidence_ids) == 6


def test_empty_retrieval_produces_explicit_coverage_gap() -> None:
    retrieval = RetrievalResult(intent="definition", mode="vector")

    packed = EvidencePacker(max_context_chars=2000).pack("什么是未知概念", retrieval)

    assert packed.text_evidence == []
    assert packed.trace.selected_evidence_ids == []
    assert packed.trace.coverage_gaps == ["no_text_evidence"]
    assert "AVAILABLE_TEXT_EVIDENCE_IDS: (none)" in packed.context
