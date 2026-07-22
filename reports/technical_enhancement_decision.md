# 技术增强前置审计与决策记录

## 决策信息

| 项目 | 结论 |
| --- | --- |
| 审计日期 | 2026-07-22 |
| 审计分支 | `experiment/day6-main-ablation` |
| 当前生成器 | `GroundedAnswerGenerator`，离线规则/模板 |
| 理论首选增强 | 增强 A：可插拔真实 LLM 结构化生成 + 离线规则 fallback |
| 本阶段决定 | **No-Go：不实施增强 A 或 B，保留 v1.0** |
| final 处理 | 不重跑、不调参、不改变原始结果 |
| extension holdout | 当前不创建；只有增强重新获准后才冻结 |

## 前置条件审计

### 增强 A：真实 LLM 结构化生成

本机存在真实本地推理条件，而不是模拟接口：

- Ollama `0.32.1` 已安装并监听 `127.0.0.1:11434`；
- 已安装模型 `qwen3-vl:8b`，大小约 6.1 GB；
- 不需要把本地服务伪装成在线 API，也没有读取或输出任何密钥。

但当前模型与服务组合未通过生成器输出合同。初始 5 次手工探针加 1 次自动复验共 6 次，均出现：

```text
JSON Schema 内容本身可生成
    ↓
内容进入 thinking 字段
    ↓
正式 response / message.content 长度为 0
    ↓
AnswerPayload 无法从正式答案字段解析
```

关键测量：

| 项目 | 结果 |
| --- | ---: |
| 冷启动单次墙钟耗时 | 84.7 s |
| 其中模型加载耗时 | 67.2 s |
| 后续非首次调用探针 | 约 1.0～12.0 s |
| 正式答案字段结构化成功 | 0/6 |
| thinking 中观察到合法 JSON | 是 |

不能把 `thinking` 字段直接当作正式回答，原因是：

1. 这会依赖模型内部推理通道，而不是稳定的生成接口合同；
2. 后续模型或 Ollama 版本可能改变 thinking 格式；
3. 项目要求结构化答案进入可验证的正式字段，再交给同一个 Evidence Verifier；
4. 以临时解析补丁宣称“真实 LLM 增强已完成”会夸大当前成熟度。

因此，增强 A 当前判定为 No-Go。

### 增强 B：Sparse + Dense + Graph

`sentence-transformers` 和 PyTorch 已安装，但这只代表代码依赖存在。本机 Hugging Face 缓存中没有可直接加载的文本 Embedding 模型，现有缓存均为 CLIP/ViT 图像相关模型。根据冲刺方案“优先使用已能在本机加载的多语言模型”和“模型下载不稳定时止损”的规则，增强 B 也不具备立即实施条件。

此外，当前生成器仍是离线模板，按照原决策树应优先解决真实生成能力，不应为了绕开增强 A 的前置失败而临时切换到增强 B。

## 正式决定

本轮不实现任何技术增强，不生成伪造的 enhanced 指标，也不把预检结果写成科研贡献。项目继续以 `v1.0-baseline` 和已完成的主实验、No Verifier 消融、用户确认语义复核及误差分析作为可交付版本。

当前也不创建 `extension_holdout`。该数据集的用途是对一个已经选定且通过前置检查的增强做一次性独立比较；在 No-Go 状态下提前创建会增加调试或误用风险，没有实验价值。

## 重新进入条件

只有同时满足以下条件，才重新启用增强 A：

1. 使用适合纯文本指令的本地模型，或修复当前 Ollama/model 组合，使 JSON Schema 输出进入 `message.content`；
2. 在合成探针和 dev 上连续执行至少 20 次结构化输出，成功不少于 19 次；
3. 失败、超时和解析异常均能自动回退 `GroundedAnswerGenerator`；
4. 输出仍使用 `AnswerPayload`，并由现有 Evidence Verifier 复核；
5. 通过前置探针后，再冻结 23 题 `extension_holdout`，且只运行一次；
6. 不使用原 final 调参或重新报告成绩。

## 可复验命令

```bash
python scripts/check_enhancement_readiness.py
python scripts/check_enhancement_readiness.py --probe-ollama --model qwen3-vl:8b
```

脚本只输出环境变量名称和模型清单，不输出密钥值，也不会把 thinking 内容写入日志。
