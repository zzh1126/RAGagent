# LLM Agent v2 Stage 8.8 用户确认盲评审计

## 1. 确认范围

用户已审核并明确确认 92 行 Codex 辅助初评分数。确认操作在评分锁定后才读取独立 `blind_method_key.json` 和 extension expected behavior，用于按方法解盲和计算分母；没有修改原始答案、自动指标、receipt、冻结 runtime 或初评分数。

```text
reviewer=User-confirmed review of Codex-assisted scoring
review_status=user_confirmed
scores_promoted_without_mutation=true
rows=92
methods=4
questions_per_method=23
```

该流程是 Codex 辅助初评加用户单一确认，不是独立双人标注，不能报告标注者一致性或统计显著性。

## 2. 自动与人工指标

| Method | Auto Decision | Correctness | Faithfulness | Hallucination | Over-refusal | Readability | Mean E2E |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rule Baseline | 0.9130 | 0.5870 | 0.8810 | 0.0000 (0/21) | 0.0000 (0/19) | 3.56 (n=18) | 5.46 ms |
| LLM Strict v2 | 0.3043 | 0.3043 | 1.0000 | 0.0000 (0/3) | 0.8421 (16/19) | 5.00 (n=3) | 11891.29 ms |
| LLM No Verifier v2 | 0.8261 | 0.7826 | 0.8182 | 0.2727 (6/22) | 0.0000 (0/19) | 4.32 (n=19) | 5207.65 ms |
| LLM Partial-pass v2 | 0.6957 | 0.5217 | 0.9375 | 0.0000 (0/16) | 0.2632 (5/19) | 3.73 (n=15) | 7607.35 ms |

Correctness 和 Faithfulness 归一化到 0-1；Readability 是 1-5 原始均值。拒答不进入 Faithfulness、Hallucination 和 Readability 分母，故不同方法的分母不同。

## 3. 可支持的结论

1. Partial-pass 相比 Strict 将 over-refusal 从 16/19 降至 5/19，同时保持用户确认 hallucination 为 0/16，说明逐 Claim 过滤缓解了整题拒答且没有观察到未支持专业事实泄漏。
2. Partial-pass 的 Faithfulness 为 0.9375，高于 Rule Baseline 的 0.8810 和 No Verifier 的 0.8182；但 Correctness 0.5217 低于 Rule Baseline 0.5870，更低于 No Verifier 0.7826，因此不能声称 Partial-pass 提高了总体回答正确性。
3. No Verifier 的 Correctness 和 Readability 最高，但 hallucination 为 6/22，且自动拒答准确率为 0/4。它说明放松验证能提高回答覆盖和表面可读性，同时显著损害证据边界。
4. Strict 的 Faithfulness=1.0000、Readability=5.00 只基于 3 条实质答案；16/19 over-refusal 导致 Correctness 仅 0.3043，不能把小分母上的高分解释为整体质量最好。
5. Rule Baseline 延迟最低、自动 Decision Accuracy 最高且用户确认 hallucination 为 0，但 Correctness 只有 0.5870，说明自动“是否拒答正确”不等于答案内容完整正确。

## 4. 不能支持的结论

- LLM Partial-pass 已全面优于规则基线；
- Verifier 越严格越好；
- No Verifier 因 Correctness 最高而可以安全部署；
- 本轮 0 hallucination 方法在其他问题上不会产生幻觉；
- 23 题单一确认结果具有统计显著性或可泛化到完整 scikit-learn；
- Readability 的跨方法差异可忽略有效评分分母。

## 5. 确认与输出哈希

| 产物 | SHA-256 |
| --- | --- |
| Immutable blind review input | `5e8ce394a76dd0ca4e2fd91decf80191f625c7024ea1dc3073301c0ab70a189e` |
| Confirmed blind CSV | `1bd59bcb619fda780d7dd4a0b6ff082a4a585747dca46995323df8f1acc1c353` |
| Unblinded confirmed CSV | `57bca45e49a6274659cb32ea4e0988db509712da9ec9177bc2daa577e6715898` |
| Human metrics | `d6e3183edecd146e0694c929a59e57d021f8fcdbdeea1c888dd608064f90a28c` |
| Combined automatic/human metrics | `45439c7dd78bdc48766ca5cfa2bce630058c9874723dbac04d62e012741cb920` |
| Markdown summary | `c79916938ea7ed854b836eadb13f4445efe5cdcbb4e26296beeadc4beb5294be` |

`scripts/validate_extension_blind_confirmation.py` 会重新计算所有方法指标、校验 92 行映射、分数签名、确认状态和输出哈希。

## 6. 下一步

用户确认盲评和四方法指标汇总已完成。下一小阶段生成用户确认指标图表、类别/错误分析并同步最终报告与答辩材料；仍禁止重跑 extension 或依据 holdout 结果修改冻结实现。
