# Pilot 语义评分确认记录

## 确认结论

用户已确认 pilot 集四种方法共 160 行语义评分，包括：

- Answer Correctness；
- Evidence Faithfulness；
- Hallucination；
- Over-refusal。

确认动作只提升评审状态和说明文字，**没有修改任何题目、方法或评分数值**。当前正式状态为 `user_confirmed`。

## 当前正式文件

- `reports/human_scoring_pilot_confirmed.csv`
- `reports/experiments/pilot_human_metrics.json`
- `reports/experiments/{vector_rag,graph_only,proposed,no_verifier}_pilot.json` 中的用户确认语义指标
- `reports/metrics_summary.csv`
- `reports/metrics_summary.md`
- `reports/experiments/pilot_error_analysis.md`
- `reports/figures/pilot_semantic_confirmed.png`

## 审计留痕

确认前的原始文件仍保留，不参与当前报告的正式读取路径：

- `reports/human_scoring_pilot_preliminary.csv`
- `reports/experiments/pilot_human_metrics_preliminary.json`
- `reports/experiments/pilot_error_analysis_draft.md`

这些文件记录评分如何从 Codex 辅助初评进入用户确认流程。确认版仍如实说明：评分初稿由 Codex 辅助生成，随后由用户确认；本项目没有把它表述为独立双人标注或统计显著性检验。

## 可复验命令

```bash
python scripts/validate_scoring.py
python scripts/validate_report_claims.py
python scripts/generate_report_figures.py --check
```

## 文件指纹

| 文件 | SHA-256 |
| --- | --- |
| `human_scoring_pilot_preliminary.csv` | `D8B4CA6B02F34E7DD2BB701B4F11A731011DEDD0A80873D4AC51F0AB809ABAF1` |
| `human_scoring_pilot_confirmed.csv` | `12527F0F9EB6180C5C6A16889D7CB41F448DD6301C2598166476FA91BFDD8A63` |
| `pilot_human_metrics_preliminary.json` | `1DF10E84DB2C10A303DE0D501A147007A2DE127D028B85B9BCF486FE5EB0542B` |
| 当前 `pilot_human_metrics.json` | `25FD05EDC6CA975D941F2239BD4AE31BA20AB37579FC1AA24BCC3BB6FE128063` |
