# GEAK 借鉴实施记录：P0-e，默认 SDK 持久化 run 与报告

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

日期：2026-10-13。承接 [P0-c 配对协议](./geak-P0c-paired-validation.md)。
本批将 Cursor SDK 默认入口接到现有 run 控制器，并从权威状态导出可读报告。
仅用 CPU 和假 runner/client 验证，未运行模型会话、真实 client 或 gfx942 GPU 实验。

## 1. 实现

| 位置 | 变化 |
|---|---|
| [`tools/sdk/tune.mjs`](../../tools/sdk/tune.mjs) | 默认新建持久化 run；模型结束后受条件控制地 final；finally 导出报告 |
| [`tools/sdk/run_workflow.mjs`](../../tools/sdk/run_workflow.mjs) | 可独立测试的参数解析、预算构造、run 提示词、收尾、输入快照 |
| [`tools/tune_run_report.py`](../../tools/tune_run_report.py) | 从 RunController.status 一致快照生成 JSON/Markdown，按阶段导出摘要校验副本 |
| [`tools/sdk/run_workflow.test.mjs`](../../tools/sdk/run_workflow.test.mjs) | 纯 Node 测试及缺 key 的真实脚本/假 Python runner 测试 |
| [`unittests/test_run_report.py`](../../unittests/test_run_report.py) | 使用真实控制器、假 client 的报告测试 |
| [`tools/sdk/README.md`](../../tools/sdk/README.md) | 默认流程、预算、兼容参数和证据边界 |

没有修改 ISA、agent/run.py、tools/tune_run.py、harness 或 client。
旧 agent_session.py/tune_summarize.py 仍保留独立筛选接口，SDK 不再默认使用它们。

## 2. 冻结与模型职责

SDK 先调用 `init`，之后才导入 Cursor SDK 并启动模型。
seed、client token 数组、loop/kernel、构建策略、区域默认值、预算和可选比较策略由现有控制器冻结。
`--` 后的参数只通过 init 的 argv 传一次，不拼接成 shell 文本，不出现在后续 eval 命令。
模型读取 observation_id/base_sha256/parent_id，以结构化 layout 或 partial order 调用 prepare，
再 eval 不可变 candidate_id。晋升后重新 observe，不复用旧指令 ID。

默认 `rounds=6`、`perf_repeats=3`、`proposal_limit=4*rounds`、`wall_seconds=1800`。
无策略的 eval 硬上限为 `(rounds+2)*perf_repeats`，两个 batch 为 original 和 normalized。
有显式策略时，默认再加 `2*confirm_pairs*max_confirmations + final_reserve`，
其中 reserve 默认 `2*final_pairs`；可以显式覆盖硬上限与 reserve，最终由控制器校验。
`rounds` 是模型的候选筛选目标和默认预算推导输入，不是 shell 回合强制计数器。

这些硬约束只约束调用 run 控制器的操作。Cursor local runtime 仍有任意 shell 能力；
提示词要求不绕过 run、不改 client/引擎/归档，不能将这一约定描述为强隔离。
静态验证也不是完整 ISA 语义等价证明，数值检查仍由 client 执行。

## 3. 收尾规则

- 未提供 comparison policy：仅 screen，报告 confirmation/final 未完成，不调用 confirm 或 final。
- 显式 policy：模型可在筛选后 confirm；只有控制器 confirmed_gain 能更新 incumbent。
- 模型正常 `finished`：SDK 查询状态；仍为 search 且没有 final_result 时发起一次 final。
- 模型失败、缺 key、SDK 异常或中断：不自动 final，仅尝试导出已有状态。
- 已 final、正在 finalizing 或 final 返回错误：不重复 final，不自动 resume，不重复 confirm。
- finally 先尝试停止 SDK，再报告；锁仍被在途工作持有时报告返回 run_busy，保留恢复语义。

SIGINT/SIGTERM 触发上述保守收尾；SIGKILL、机器掉电等无法保证执行 finally。
SDK 目前只创建新 run；已有 run 的恢复与显式重试由 tune_run.py 处理。

## 4. 报告权威与导出

报告读取 `RunController.status()`，使用控制器锁和 manifest 摘要校验获取一致状态快照，
随后在报告中标出 state revision。它不运行 client，不扫描模型事件推断赢家。
JSON 包含冻结 manifest、候选谱系/spec、预算、所有 batches/attempts、配对样本、失败和 final_result。
Markdown 分别显示筛选、确认、final、失败与能力边界。

| 派生字段/副本 | 条件 |
|---|---|
| screening_best / screening_best.s | 每个候选最新 screen batch 有效，按分数选择；可以是 original |
| confirmed_best / confirmed_best.s | 权威 incumbent 有 completed confirmed_gain 的 confirm 证据 |
| recommendation | 仅完成 final_recommended，且 final、候选与归档身份一致 |
| selected / selected.s | 仅 final 后产生；成功选 incumbent，否则原始输入回退 |

没有 final 时，selected 和 recommendation 均为 null；筛选尖峰不升级为推荐。
final 回退 original 不表示原始输入刚通过 final 正确性或性能复测。
每个汇编归档校验路径在 run 内及 SHA-256，副本写完再次校验摘要。
同名旧派生副本先清理，避免本次失效后留下旧 selected.s。
摘要错误写入报告并返回非零，撤下选中/推荐副本；manifest 无法通过时拒绝导出。
自定义报告位置不得覆盖 run 权威文件，在 run 内只能写 RUN/report 下。

自定义 transcript 及派生 .md 同样在写入前校验用户路径和实际路径（包括符号链接父目录）。
run 内只有默认两个 transcript 文件及 transcripts/ 专用目录可写；输入准备目录、其他 run、
当前 run 的其他内容与配置的报告输出均禁止用作 transcript。拒绝悬空符号链接，
路径校验失败发生在启动 SDK 模型之前，仍尝试导出已有 run 报告。

final 相对 original 的报告使用对应配对 analysis；相对 normalized 的独立 final 比较尚未实现，
字段明确为 null。历史筛选分数不冒充配对样本。
正向 score 来自 client 的 EvalResult.tflops，只有吞吐/时间倒数语义才能解释为时间加速比。

## 5. 输入来源与兼容

FACK 仅接受 `.s`，先逐字节快照到 `client/<名>/tune_out/sdk-inputs/<run-id>/attempt-<随机后缀>/`。
每次初始化独占新建 attempt 目录；init 失败后同 run-id 重试保留旧输入并创建新目录。
run 内另存原始来源字节及 SHA、汇编 SHA；转换字段为 null。`.co` 在创建输出前拒绝。
`input_provenance.json` 是 SDK sidecar，**不是冻结 manifest 或实际装载证明**。

`--results-path` 兼容入口参数名称，但输出改为完整 JSON 快照（.json 或 .jsonl 扩展名），
同名 .md 为可读报告。`--no-results` 不关闭持久化证据与报告；`--no-transcript` 只关闭模型事件。
既有分析脚本若依赖“每次 eval 一行”，应继续使用旧独立筛选入口或改读新的报告结构。

## 6. 验证

```bash
node --test tools/sdk/run_workflow.test.mjs
python3 -m pytest -q unittests/test_run_report.py
node --check tools/sdk/tune.mjs
node --check tools/sdk/run_workflow.mjs
```

本批结果：Node **15 passed**；报告 **12 passed**。覆盖：

- opaque token、shell quoting、硬预算参数、显式策略的预留额度。
- 正常完成一次 final、无策略无 final、已结束无重试、异常/final 失败仍报告。
- 实际启动 SDK 脚本，在缺 key 且无 SDK/client 调用下，用假 Python runner 验证 init → report。
- 原项目包含输入转换的来源测试；FACK 调整为 `.s` 快照保持来源身份，以及 `.co` 输入提前拒绝。
- 未确认最高分、confirm 未 final、final 回退、未实测 original 回退、中断保留占额。
- 最新失败筛选不沿用旧最高分、归档损坏/越界、manifest 损坏、sidecar 摘要与输出位置保护。
- transcript 指向 state、派生 md 符号链接、尚不存在路径的符号链接父目录、报告 md 冲突。
- 实际 driver 配临时假 SDK/假 Python：路径拒绝发生在 SDK 启动前；init 失败后同 run-id 可重试成功，旧输入保留。

测试不验证Cursor 线上服务、GPU 装载身份、统计噪声假设或性能收益。
全套 CPU 回归与提交由主代理审查后执行。

主代理联合回归：报告、配对确认、client 契约测试共 **62 passed**（22.52 秒）；Node **15 passed**。
