# 脑洞：把 observe/propose/eval 决策面包成一层 MCP（可选前端）

> 类型：brainstorm（头脑风暴，非现状、非已落地设计）。
> 命题：现在 agent 是用**内置 shell 工具**调 `python3.8 tools/agent_session.py {observe|propose|eval}`、读
> stdout 的 JSON；ATT 性能文件由 Python 引擎内部解码成 `direction` 摘要。**要不要给这套决策面再加一层 MCP？**
>
> 本篇是 `sdk_agent_integration.md` / `knowledge_agent_design.md` / `if/ai_interface.md` 的延伸：
> 前者讲"SDK 起本地 agent、agent 用 shell 驱动固定逻辑引擎"，本篇探讨**把同一套 observe/propose/eval
> 决策面再额外暴露为 MCP 工具/资源**，作为与 shell 并存的可选前端。

---

## 0. 一句话结论

**现在不需要为无人值守的 `tune.mjs` 流程改用 MCP；shell+CLI 已够用且更透明、可复现。** 仅当出现下面两类需求时，
才值得加一层**薄 MCP 适配器**（复用现有 `agent_session` 函数，引擎逻辑零改动），且是**并存、不替换**：

1. 你开始**频繁在交互式 Cursor 对话里手动调** observe/eval（不止跑无人值守脚本）；或
2. 你观察到**因 CLI 参数拼写/引号（尤其 `--layout '{...}'` 的 JSON）导致的调用失败**，想用类型化 schema 消除。

无论是否上 MCP，**ATT 解码必须继续留在引擎内**——agent 消费的是已消化的 `direction` 摘要，绝不让模型去 parse 原始 `.att`。

---

## 1. 现状机制（先讲清楚现在不是 MCP）

```
node tune.mjs (SDK 驱动)
  └─ 本地 Cursor agent (cwd=repo)
       └─ [内置 shell 工具] python3.8 tools/agent_session.py {observe|propose|eval} ...
            └─ AgentSession → 固定逻辑引擎（重排/重算/Verifier/真机评测）
                 └─ evaluator.dump_counters → rocprofv2 -d ./att
                      └─ analysis/perf.py (ctypes→librocprofiler-sdk.so) 解码逐指令事件
                           └─ analysis/bottleneck.py → direction 摘要（回流给 observe/eval 的 JSON）
```

- **agent → 引擎**：靠 agent 的 **shell 工具**跑 CLI，结果是 **stdout 上的 JSON**。仓库内**无任何 MCP server**。
- **读 ATT**：agent **从不直接碰** `.att`/`memory*…out` 原始文件；这些由 **Python 引擎**解码，agent 只拿到 `direction`
  （`{bottleneck, share, hints, stats, …}`）。这一职责划分是刻意的，符合"知识只导航、不裁决"的纪律。

---

## 2. shell+CLI vs MCP：各自得失

| 维度 | 现状 shell + CLI（stdout JSON） | 加一层 MCP（tools + resources） |
|---|---|---|
| 接入成本 | 0（已跑通） | 需起/维护一个 MCP server 进程 + schema |
| 调用正确性 | agent 自己拼 CLI 字符串，`--layout '{...}'` 的引号/JSON 易错 | **类型化参数 schema**，模型少拼错；结果是结构化对象 |
| 可追溯/复现 | **强**：transcript 记录精确命令，可手动原样重放 | 工具调用也可记录，但"手敲复现"不如一条 shell 命令直接 |
| 调试直观度 | **强**：shell 里敲同一条命令即复现 | 需经 MCP 客户端/协议 |
| 交互式复用 | 仅限会跑 shell 的 agent | **任意 MCP 客户端/交互式 Cursor** 都能直接调 |
| 校验/约束 | 在 Python 里手动校验 | schema 层可强约束参数类型/枚举 |
| schema 维护 | 无 | 引擎演进时要同步 schema |
| 运行时形态 | 一个无状态 CLI 进程/次调用 | 常驻 server（或按需拉起） |

**净判断**：MCP 的核心收益是「**类型化参数** + **可被交互式/多客户端复用**」；核心代价是「**多一个要维护的 server/schema**」。
对一次性无人值守 run，收益小于代价；对交互式/多端使用或受够了参数拼写错误，则反过来。

---

## 3. 若要做：建议的 MCP 层设计（薄适配器，零改引擎）

原则：**MCP 只是 `agent_session` 的第二个前端**。同一套 `AgentSession.observe/propose/commit_and_eval`，
shell CLI 和 MCP server 都只是"调用方"，**业务逻辑不下沉进 MCP，也不在 MCP 里复制**。

### 3.1 暴露为 MCP **tools**（与三个子命令一一对应）

| tool | 入参（schema） | 返回 | 备注 |
|---|---|---|---|
| `tune_observe` | `seed`(str), `testcase`(str), `region`(enum: loop/prologue/epilogue/inter/`loop#1`/all), `loop`(int), `with_direction`(bool), `exe_params`(string[]) | 事实地图 JSON（anchors/slots/fillers 或 dag+waitcnt_preview，外加 regions/direction/prior_plan） | 等价 `observe` |
| `tune_propose` | `seed`, `region`, `layout`(object) **或** `order`(int[]) | `{legal, placed[], skipped[](reason+window+bound_iid), cost?}` | 不需 GPU；非提交合法性预检 |
| `tune_eval` | `seed`, `testcase`, `region`, `loop`, `layout`/`order`, `exe_params`(string[]), `results_path`(str?) | `{correct, tflops, baseline_tflops, accepted, note, est_cycles}` | 需 GPU；仍走真机门控 + 权威结果落盘 |

要点：
- `layout`/`order` 用**结构化对象/数组**（而非字符串），从根上消灭 shell 里 `--layout '{...}'` 的引号坑——**这是 MCP 最大的实打实收益**。
- `testcase`/`exe_params` 维持 **testcase 无关红线**（`testcase_integration.md` §0）：`exe_params` 是**原样透传**的字符串数组，schema **不**枚举 `m/n/k`，server **不解析/不默认** shape 参数。
- `region` 用 enum 限定，避免拼错。

### 3.2 暴露为 MCP **resources**（只读、可被订阅/读取）

| resource URI（示例） | 内容 | 来源 |
|---|---|---|
| `tune://results/<run>` | 该次运行的每轮结果表（`*.results.jsonl`） | `agent_session` 权威写入 |
| `tune://summary/<run>` | 最好/最坏 kernel 汇总（`tune_result/*.summary.json`） | `tools/tune_summarize.py` |
| `tune://direction/<seed>` | 最近一次 observe/eval 的 `direction` 摘要 | `analysis/bottleneck.py` |

**注意**：resource 暴露的是 `direction`/结果**摘要**，**不是**原始 ATT。ATT 解码仍在引擎内（见 §4）。

### 3.3 实现形态

- 一个薄 server：`tools/mcp/tune_server.py`（或 Node），**import 现有 `agent_session`/`AgentSession` 的函数**，把入参映射过去、把返回透传出来。预计**几十行**，不碰 `reorder/`、`harness/`、`agent/` 任何逻辑。
- Python 3.8 限制：若 MCP Python SDK 要 ≥3.10，则用 **Node MCP server**（与 `tune.mjs` 同栈），server 内部仍 shell-out 到 `python3.8 tools/agent_session.py`——即"MCP 包 CLI"，零引擎改动、最稳妥。
- **与 shell 并存**：保留 prompt 里的 shell 路径不动；MCP 仅作可选前端，按场景二选一。

---

## 4. ATT 这一侧：无论是否上 MCP，都**留在引擎内**

- agent/模型消费的永远是 `direction` 摘要，而不是几十 MB 的 `.att`/code-object dump。
- 让模型直接读原始 ATT 会：① 爆 token；② 把"性能归因"这种确定性分析交给非确定性的 LLM，违背"固定逻辑裁决、知识只导航"。
- 因此 MCP 最多把 `direction`/结果当 **resource** 暴露（§3.2），解码链（`analysis/perf.py` + `librocprofiler-sdk.so`）**不动、不外移**。

---

## 5. 风险 / 反模式（别踩）

1. **把业务逻辑搬进 MCP**：MCP 必须是薄适配器，逻辑留在 `agent_session`/引擎，否则两个前端会逻辑漂移。
2. **借 schema 偷偷写死 shape 参数**：`exe_params` 必须保持自由透传字符串数组，**不得**在 schema 里枚举 `m/n/k`——否则又违反 testcase 无关红线。
3. **用 MCP 让模型读原始 ATT**：见 §4，禁止。
4. **丢掉可复现性**：即便上 MCP，也要继续把"等价的可手敲命令/调用参数"记进 transcript，保住"手动重放某轮"的能力。
5. **多一个要维护的进程**：server 崩了/版本漂了会成为无人值守的新故障点；若上线要有健康检查与"退回 shell"的兜底。

---

## 6. 分期落地（若决定做）

- **Phase 0（先量化必要性）**：在现有 shell 流程里统计"因 CLI 参数/引号导致的调用失败率"。若可忽略，且无交互式需求 → **不做**，结论停在这里。
- **Phase 1（最小可用）**：Node MCP server 包 `tune_observe/tune_propose/tune_eval` 三个 tool，内部 shell-out 到 `agent_session.py`；`layout`/`order` 用结构化入参。手动在 Cursor 里验证一轮 observe→propose→eval。
- **Phase 2（资源面）**：加 `tune://results|summary|direction` resources，交互式查看跑批结果。
- **Phase 3（可选收敛）**：若 MCP 路径稳定且更省心，可把 `tune.mjs` 的 prompt 从"shell 命令模板"切到"MCP 工具"，但**保留 shell 作兜底**。

---

## 7. 一句话脉络

> 现状：agent 用 **shell 工具调 CLI**、读 stdout JSON；ATT 由**引擎内**解码成 `direction`，**不是 MCP**。
> 建议：**默认维持现状**（简单、透明、可复现）；仅当"交互式复用"或"CLI 参数拼写错误"成为真实痛点时，
> 加一层**薄 MCP 适配器**（复用 `agent_session`、`layout/order` 结构化、`exe_params` 仍原样透传、ATT 仍留引擎内），
> 与 shell **并存而非替换**。务必守住 testcase 无关红线（`testcase_integration.md` §0）与"知识只导航、不裁决"纪律。
