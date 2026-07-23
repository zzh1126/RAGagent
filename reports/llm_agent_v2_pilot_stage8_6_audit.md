# LLM Agent v2 Stage 8.6 Pilot 与冻结审计

## 范围

本阶段只完成一次 40 题 pilot 冻结前回归、预声明 Go/No-Go 判定，以及 v2 runtime/release 冻结。没有运行 final 或 extension QA，没有根据 pilot 逐题结果继续调参。

冻结实现 commit：

```text
e207cb9142ff0066bae58501185b157998abe68f
```

该 commit 已推送到 `origin/experiment/llm-agent-v2`。运行前确认 v2 runtime 与 commit 差异为 0，Prompt v2、wire Schema、Packer、Verifier、配置和模型 identity 均与 gate 合同一致。

## 一次性 Pilot

一次性状态文件记录：

```text
status=completed_once
run_number=1
completed_question_count=40
rerun_authorized=false
```

外层命令在 15 分钟时返回 timeout，但原 pilot 子进程没有被重复启动，而是在后台完成同一轮并原子写入 report/state。报告哈希与 state 中记录一致。因此该结果仍属于唯一一次已消费运行，不构成重跑。

| 指标 | 结果 |
| --- | ---: |
| Question Count | 40 |
| Decision Accuracy | 0.8250 |
| Mean Keyword Coverage | 0.6250 |
| Structured Output Success | 0.9750 |
| Fallback Rate | 0.0000 |
| Answerable Over-refusal | 7/36 (0.1944) |
| No-answer Refusal Accuracy | 4/4 (1.0000) |
| Retry Rate | 13/40 (0.3250) |
| Partial-pass | 25/40 |
| Generated Claims | 91 |
| Supported / Retained Claims | 49 / 49 |
| Removed Claims | 42 |
| Unsupported Claim Leakage | 0 |
| Mean End-to-end Latency | 34180.72 ms |

决策分布：`pass=4`、`partial_pass=25`、`refuse=11`。

## Go/No-Go

Go/No-Go 使用 pilot 执行前提交的 `config/pilot_freeze_gate_v2.yaml`。全部检查通过，最终状态为：

```text
status=go
failed_checks=[]
pilot_consumed=true
rerun_authorized=false
per_question_tuning_authorized=false
```

该 Go 仅表示候选满足预声明工程冻结门槛，不表示 LLM 已经优于规则基线，也不把已消费 pilot 重新解释为独立保留集。平均约 34.18 秒的端到端延迟仍是明显限制。

## v2 冻结与 Release

创建的 release：

```text
release_id=extension-qwen3-4b-v2-e207cb91
status=authorized_not_executed
```

冻结身份：

| 项目 | 值 |
| --- | --- |
| Runtime bundle SHA-256 | `ae639c6a51bdb65c3cd291db865485ffa8eb22ffcc0dd2c443e339cd0e00e44b` |
| Prompt SHA-256 | `e5c6fa6bbc992a9af2c66daffd8fcffeb2da1eae02202d932aef33fbbb774cad` |
| Wire Schema SHA-256 | `b11bf9c445d3aa37c98cd571b880a157387661fdebf63a11a43aef786c7087eb` |
| Ollama Version | `0.32.1` |
| Model | `qwen3:4b` |
| Model Digest | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |
| Model Size | `2497293931` bytes |

v1 release 仍为 `revoked_before_execution`。v2 受控 runner 的 preflight 已通过，但 `reports/extension_v2` 不存在，说明 extension 问题尚未送入 QA。

## 不可变产物

| 产物 | SHA-256 |
| --- | --- |
| Pilot report | `930f36017cd40bb8421c63bf3cfcc32fc46d512c95d53fc342eefe53868c60e8` |
| Pilot state | `34bac94048526c5ff5d19905e3e88967243f70f9d1f398120bfda8ad30a60a55` |
| Pilot gate decision | `c4a7870ef82e0d946fe365d3b0f2b53f02c2c7d7abb28ac2aee2e35dc4b5e8a4` |
| v2 implementation manifest | `4fbc310231a0aa16fd190df0b37c51df19b4d3d2817c7e89c80fac1567e90bd7` |
| v2 release record | `87b2b934f31ad3a7b6f7d11b0c56ad14759826f107a23337c90def5ef37d4f10` |

## 阶段结论

Stage 8.6 已完成，可以进入 Stage 8.7 的一次性 extension 实验准备。下一阶段仍需用户明确继续后，才可使用 release record 中的受控命令执行 4 方法 x 23 题；不得通过通用 runner、自动重试或覆盖输出绕过一次性协议。
