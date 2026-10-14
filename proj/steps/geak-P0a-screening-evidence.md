# GEAK 借鉴改进：P0-a 第一批——筛选证据与结果身份

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

> 日期：2026-10-13。对应[改进设计](../geak_lessons_for_instruction_tuning.md)的 P0-a。
> 本机没有目标 GPU，本批使用真实汇编 fixture 与注入的假 evaluator 做 CPU 验证。
> 状态：已落地首批证据记录与筛选结果语义；完整 P0-a 和 P0-b 尚未完成。

## 1. 本批目标与边界

让现有 SDK → `agent_session.py` 调优链路能回答：原始输入是什么、实际测了哪个候选、
每次 client 返回了什么、最高分属于什么阶段。所有候选仍由现有引擎生成，真机评测仍走 client。

本批没有改变 ISA 指令规则、重排策略、等待/hazard 修补逻辑、client 正确性容差或搜索噪声阈值。
也没有在本机运行 GPU kernel。有效运行的 baseline/候选重复次数保持原样，不增加 original 或 final 的测量调用。

## 2. 已实现

### 2.1 原始输入、规范化 baseline 与候选快照

新增 [`agent/artifacts.py`](../../agent/artifacts.py)，在评测前将精确 UTF-8 汇编字节写入
`<out_store>/artifacts/<sha256>.s`。相同字节使用同一路径，已有文件摘要不匹配时报错，不覆盖损坏证据。
新文件通过临时文件加原子替换写入；返回路径、SHA-256 和字节数。

[`agent/session.py`](../../agent/session.py) 在结果中区分：

| 身份 | 本批记录 | 是否测量 |
|---|---|---|
| `original` | 原始 seed 字节快照与摘要 | **未单独测量**，显式记录 `measurement_status=not_measured` |
| `normalized` | L1 重算后的 baseline、构建 spec、静态检查结果、逐次测量 | 沿用现有 baseline 测量 |
| `candidate` | 完成重排与修补后的汇编、摘要、逐次测量 | baseline 通过后才测量 |

CLI 读取 seed 和写工作汇编时保留换行形式，不因文本模式自动将 CRLF 改成 LF。
目前 `.co` 经 SDK 转换后，session 看到的是转换后的 `.s`；原始 `.co` 身份贯通仍待实现。
输入摘要检查可以发现工作 `.s` 被修改，不能证明 client 实际装载了哪个 `.co`。

修正 `AgentSession` 默认写目录：读取默认策展知识时，输出落临时目录；
生产 CLI 仍显式传入 client 的 `tune_out`。显式自定义 `store` 的旧单目录用法保留兼容。
这不是对所有旧知识写入入口的全面迁移。

### 2.2 保留重复评测的原始返回值，严格检查每一轮

新增 [`harness/measurement.py`](../../harness/measurement.py) 的 `measure_screen`，
记录每次 client `evaluate` 的开始时间、耗时、输入摘要与 `EvalResult` 字段。
规范化 baseline 和候选的原始样本进入 `CommitResult.evidence`，再随结果 JSONL/实验日志持久化。
JSON 中 NaN/Infinity 等无效原值转成字符串留作诊断，不让无效数值进入排名。

每轮必须满足 `compiled is True`、`correct is True`，且性能分数为有限正数，整个重复测量批次才有效。
首个失败即停止并保留已尝试样本，区分 `compile_failed`、`incorrect` 和 `measurement_invalid`。
未知正确性的快分数，不能借用另一轮的 PASS 混成正确结果。
缺少必需的 `compiled` 字段也不再被当成通过；仓内假 evaluator 补齐现有 `EvalResult` 契约。

[`search/driver.py`](../../search/driver.py) 的 `_median_tflops` 复用同一检查规则；
search baseline 静态检查或筛选失败时停止，不继续测候选。
SDK/session 通路会保留完整证据，旧 `search()` 的结果接口仍只返回汇总值，没有一并改造成新 run 存储。

### 2.3 筛选阶段与最终确认明确分开

`CommitResult` 新增 `stage=screen`、`verdict` 和 `evidence`，保留 `accepted` 旧筛选策略语义。

| verdict | 本批含义 |
|---|---|
| `screening_gain` | 筛选分数超过配置噪声范围，尚未独立确认 |
| `screening_regression` | 筛选分数低于配置噪声范围 |
| `exploration_only` | 噪声范围内静态代价改善，可作继续探索依据 |
| `inconclusive` | 当前筛选没有足够的改善依据 |
| `illegal` | 候选未通过现有静态检查 |
| `baseline_failed` | 规范化 baseline 未通过检查/测量，候选未测 |
| `compile_failed` / `incorrect` / `measurement_invalid` | 候选测量过程对应阶段失败 |

失败 baseline 在同一 session 内缓存为失败，避免隐式反复调用 client；新 CLI session 仍会重新建立 baseline。
每次 commit 清空 `last_archive`，防止失败候选继承上一轮 shader 路径。
baseline 失败时，候选 `correct=None`，因为没有执行候选正确性检查。

[`agent/knowledge.py`](../../agent/knowledge.py) 继续保存失败记录，但新增的静态失败、基线失败、构建失败、
无效测量不进入性能 skill 归纳，避免将未建立性能结论的实验归纳为“应避免的优化”。
具体 layout/order 的细粒度归纳身份仍待 P1 实现。

### 2.4 CLI、汇总与显示贯通

[`tools/agent_session.py`](../../tools/agent_session.py) 的结果 JSONL 增加：

```text
schema_version: 2
stage: screen
verdict: ...
baseline_kind: normalized
artifact_sha256: ...
evidence:
  spec / static_ok
  evaluation_contract: client / params / loop / kernel / arch
  original / normalized / candidate
```

`params` 保持 argv 的顺序和重复参数，不由引擎解释 shape。Markdown 结果表增加 stage/verdict。
证据中旧 baseline 分数始终标为 normalized，不声称是 original 的测量。

[`tools/tune_summarize.py`](../../tools/tune_summarize.py) 输出：

- `selection_kind=screening`、`confirmation_status=not_performed`。
- `screening_best` / `screening_best_shader`；`best` / `best_shader` 作为兼容别名保留。
- `confirmed_best=null`、`recommendation=null`；不从 `accepted` 或最高分推断独立确认。
- 副本名改为 `<stem>.screening_best_tf<TFLOPS>.s`。有摘要时复制前检查；不匹配则不复制。
- 旧日志仍可读取，其结果按未确认筛选信息显示，无摘要的副本标为 `legacy_no_digest`。

SDK 提示词、使用文档及 Web UI 同步标明筛选语义，避免显示为已确认的最终赢家。
更改前已有的 `.best_tf*.s` 文件不会被自动删除，旧文件本身也不会自动升级为推荐。

## 3. CPU 验证记录

执行环境：Python 3.12.3；本机无 `python3.8`，按仓库约定使用 `python3`。
新增代码保持 Python 3.8 语法兼容；本机不能声称完成了 Python 3.8 运行时验证。

### 3.1 改动前基线

运行 `python3 -m pytest -q unittests`：**421 passed、3 skipped、3 failed**。
原项目当时的 3 项失败属于本副本已排除的专属模块，详情留在原项目。

### 3.2 本批针对性回归

新增 [`unittests/test_tuning_evidence.py`](../../unittests/test_tuning_evidence.py)，覆盖：

- 原始样本和中位数留存，正确性未知不能借用另一轮 PASS。
- 编译/数值/环境失败分型，非有限/非正/布尔等无效分数拒绝。
- 评测前/后源文件摘要检查，原始换行和内容保存，归档损坏检查。
- 三类汇编身份、baseline 失败短路、旧 shader 路径清理。
- client 参数原样透传及 CLI 结果记录贯通。
- 无效测量不污染性能经验，模型平局只标为 exploration。
- 旧日志高分不冒充确认，待复测副本摘要验证。

第一次针对性回归（新增 CLI 换行/参数用例前）：
`python3 -m pytest -q unittests/test_tuning_evidence.py unittests/test_session.py unittests/test_search.py unittests/test_knowledge.py unittests/test_client.py`
结果 **110 passed、13 subtests passed**。

最终完整回归 `python3 -m pytest -q unittests`：**439 passed、3 skipped、3 failed、13 subtests passed**，
耗时约 32 秒。相比改动前新增 18 项通过测试；三个失败仍为 §3.1 中相同的原项目测试。

附加检查全部通过：

- `git diff --check`。
- `node --check tools/sdk/tune.mjs`、`node --check webUI/console.js`、`node --check webUI/data.js`。
- 本批核心 Python 文件使用 `ast.parse(..., feature_version=(3, 8))` 检查语法兼容。
- 设计文档、实施记录和 `proj/README.md` 的本地 Markdown 链接存在性检查。

## 4. 尚未实施与真机待验证项

| 项目 | 原因 / 下一步 |
|---|---|
| 原始 baseline 的独立测量与相对 original 的收益 | 本批只保留精确身份；下一批接入明确预算与基线失败处理后再增加调用 |
| paired A/B、确认和最终推荐 | 待实现可配置协议；阈值、样本数与区间方法需要目标 client 的真实波动验证 |
| run manifest、硬预算、原子状态、恢复、incumbent 推进 | P0-b；当前 CLI 仍是每次新建 session |
| 崩溃时逐 attempt 的证据持久化 | 目前汇编在评测前落盘，测量结果在批次返回后写入；进程中途退出仍可能丢失未返回样本 |
| 实际装载 `.co` 身份、构建隔离 | 汇编摘要不能替代装载证明，需 client 集成和目标机验证 |
| 候选去重省评测、过期 observation 检查、假设账本 | 当前只复用相同内容的归档文件，**不会因此跳过 GPU 评测** |
| 完整静态诊断与原有告警身份 | 当前仍用 `build_candidate` 返回的布尔值；尚未输出每条继承/新增告警 |
| 重排组合、历史最佳复用、知识预算额度 | P1/P2 的后续工作 |

真实设备就绪后，先通过已有 client 做小规模 baseline/候选一致性检查，确认归档字节对应被加载代码、
原始结果解析一致、重复测量无交叉污染，再校准独立确认协议。不得从本批 CPU 测试推断 kernel 真机正确或性能提升。
