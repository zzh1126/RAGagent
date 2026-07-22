from __future__ import annotations


TERM_MAP = {
    "随机森林": "random forest",
    "决策树": "decision tree",
    "逻辑回归": "logistic regression",
    "线性回归": "linear regression",
    "岭回归": "ridge regression",
    "ridge": "ridge",
    "lasso": "lasso",
    "支持向量机": "support vector machine",
    "svm": "support vector machine",
    "svc": "support vector classification",
    "kmeans": "k-means clustering",
    "k-means": "k-means clustering",
    "dbscan": "dbscan clustering",
    "bagging": "bagging",
    "装袋法": "bagging",
    "boosting": "boosting",
    "adaboost": "adaboost boosting",
    "梯度提升": "gradient boosting",
    "正则化": "regularization",
    "过拟合": "overfitting",
    "核函数": "kernel function",
    "高维": "high dimensional",
    "特征缩放": "feature scaling",
    "缩放特征": "feature scaling scale",
    "剪枝": "pruning",
    "bootstrap": "bootstrap",
    "方差": "variance",
    "偏差": "bias",
    "类别不平衡": "imbalanced classes class imbalance",
    "准确率": "accuracy",
    "平衡准确率": "balanced accuracy",
    "精确率": "precision",
    "召回率": "recall",
    "f1": "f1 score",
    "roc": "roc auc",
    "auc": "roc auc",
    "均方误差": "mean squared error",
    "轮廓系数": "silhouette coefficient",
    "聚类": "clustering",
    "分类": "classification",
    "回归": "regression",
    "稳定": "stable variance averaging ensemble",
    "指标": "metric scoring evaluation",
    "区别": "difference compare",
    "为什么": "why reason advantage limitation",
    "属于": "belongs family",
    "解决": "solve task",
}


def rewrite_query_to_english(query: str) -> str:
    lowered = query.lower()
    terms: list[str] = []
    for zh, en in TERM_MAP.items():
        if zh.lower() in lowered:
            terms.append(en)
    if not terms:
        return query
    return " ".join(dict.fromkeys(terms))
