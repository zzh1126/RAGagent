from src.retrieval.query_rewrite import rewrite_query_to_english


def test_query_rewrite_extracts_random_forest_terms():
    rewritten = rewrite_query_to_english("随机森林为什么更稳定")

    assert "random forest" in rewritten
    assert "variance" in rewritten


def test_query_rewrite_extracts_imbalanced_metric_terms():
    rewritten = rewrite_query_to_english("类别不平衡时用什么指标")

    assert "imbalanced" in rewritten
    assert "metric" in rewritten
