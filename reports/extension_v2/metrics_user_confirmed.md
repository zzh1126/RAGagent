# Extension 自动与用户确认指标

92 行匿名评分由 Codex 辅助初评并经用户逐行审核确认。解盲只在确认后进行；该流程不是独立双人标注，23 题结果只作描述性比较。

| Method | Auto Decision | Correctness | Faithfulness | Hallucination | Over-refusal | Readability | Mean E2E |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule_baseline | 0.9130 | 0.5870 | 0.8810 | 0.0000 | 0.0000 | 3.56 | 5.46 ms |
| llm_strict_v2 | 0.3043 | 0.3043 | 1.0000 | 0.0000 | 0.8421 | 5.00 | 11891.29 ms |
| llm_no_verifier_v2 | 0.8261 | 0.7826 | 0.8182 | 0.2727 | 0.0000 | 4.32 | 5207.65 ms |
| llm_partial_pass_v2 | 0.6957 | 0.5217 | 0.9375 | 0.0000 | 0.2632 | 3.73 | 7607.35 ms |

指标口径：Correctness 与 Faithfulness 归一化到 0-1；Hallucination 和 Over-refusal 为比例；Readability 是 1-5 原始均值。拒答不进入 Faithfulness 和 Readability 分母。

正式解释必须同时保留自动决策、人工答案质量、延迟、样本规模和单一确认流程限制，不能只选取单个优势指标。
