from src.retrieval.vector_rag import build_vector_answer
from src.schemas import TextEvidence


def test_vector_answer_contains_citation_metadata():
    evidence = [
        TextEvidence(
            evidence_id="E1",
            chunk_id="C1",
            source_id="S4",
            page_title="Ensembles",
            heading_path=["Ensembles", "Random forests"],
            url="https://scikit-learn.org/stable/modules/ensemble.html#random-forests",
            display_text="Random forest evidence",
            score=0.9,
        )
    ]

    answer = build_vector_answer("随机森林为什么更稳定", evidence)

    assert "随机森林" in answer
    assert "[E1]" in answer
    assert "https://scikit-learn.org" in answer
