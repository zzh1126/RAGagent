from src.retrieval.query_rewrite import rewrite_query_to_english


def test_query_rewrite_extracts_random_forest_terms():
    rewritten = rewrite_query_to_english("随机森林为什么更稳定")

    assert "random forest" in rewritten
    assert "variance" in rewritten


def test_query_rewrite_extracts_imbalanced_metric_terms():
    rewritten = rewrite_query_to_english("类别不平衡时用什么指标")

    assert "imbalanced" in rewritten
    assert "metric" in rewritten


def test_query_rewrite_covers_chinese_bagging_and_adaboost_comparison():
    rewritten = rewrite_query_to_english("请对比装袋法与 AdaBoost 的方法机制")

    assert "bagging" in rewritten
    assert "boosting" in rewritten


def test_query_rewrite_covers_reversed_feature_scaling_word_order():
    rewritten = rewrite_query_to_english("SVC 训练前为什么要缩放特征")

    assert "feature scaling" in rewritten
