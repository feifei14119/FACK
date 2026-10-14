# 脑洞：把"命令行启动调优"换成自然语言对话前门（Claude Code 式 REPL）

> 类型：brainstorm（头脑风暴 + 落地备选，非现状、非已落地设计）。
> 命题：现在启动一次调优靠 **命令行**（`tune_quick.sh` 里 `exec node tune.mjs <seed> --testcase … --region …
> --rounds … -- m=… n=… k=…`）。能否利用已经接入的 agent，把这个"前门"换成**自然语言对话**，类似 Claude Code：
> 启动后输入"帮我调优 tune_case 下的 gemm kernel 的主循环"，agent 自己把 testcase / region / 参数补齐并开跑？
>
> 本篇是 `proj/brainstorm/mcp_decision_surface.md` 的延伸：那篇结论"当你开始**频繁在交互式对话里手动驱动**
> observe/eval 时，才值得上 MCP"——本需求正是那个触发条件。

---

## 0. 一句话结论

**可行，且自然语言模式天然适合"对话式补全参数"，反而比 CLI 更安全。** 难点不在"读懂中文"，而在于哪些参数能猜、
哪些**绝不能猜**（见 §1）。建议分两步：**先做最小的"会话式启动器"（方案 A）验证体验，再演进到长驻多轮 REPL
（方案 B/C）+ 可选 MCP**。无论哪种，**引擎与 observe/propose/eval 工具零改动，只换前门**；testcase 专属 shape
参数**必须对话反问、绝不默认**（testcase 无关红线）。

---

## 1. 关键认知：CLI 参数分两类（能猜 vs 绝不能猜）

把命令行换成自然语言，真正的设计点是这些参数到底能不能从仓库 / NL 推断：

| 参数 | 能否推断 | 说明 |
|---|---|---|
| `--testcase`（哪个 exe） | ✅ 可推断 | "gemm kernel" → 扫 `tune_case/*/` 找 `gemm.exe`，唯一即定；多个则反问 |
| `seed.s`（种子 shader） | ✅ 可推断 | 由 testcase 目录下 `shader/*.s` 推断，多个则反问 |
| `--region`（主循环/序言…） | ✅ 可推断 | "主循环"→`loop`、"序言"→`prologue`、"收尾"→`epilogue`、"自动"→`auto` |
| `--rounds` / `--loop`（预算） | ⚠️ 可默认 | NL 不提就用默认值，可后续追问 |
| **`-- m=… n=… k=…`（shape 参数）** | ❌ **绝不能猜** | testcase 无关红线：参数因 kernel 而异（GEMM 是 m/n/k，MLA 是 qhead/ctx_len…），**必须由用户给**，否则跑了也没意义 |

> 因此自然语言模式天然适合 **slot-filling（槽位填充）**：能推断的 agent 自己填，唯一不能猜的 shape 参数**停下来反问**，
> 集齐才允许开跑。这比 CLI 更安全——CLI 写错 shape 不会被任何人拦住。

---

## 2. 三种实现形态（由轻到重）

### 方案 A：会话式启动器（NL → 结构化配置，最小改动）

新增 `tools/sdk/tune_repl.mjs`：readline 读一句 NL → 用一次轻量 LLM 调用（或规则）解析成现有的
`{testcase, seed, region, rounds, params}` → **回显"解析计划"让用户确认** → 复用现有一次性 `tune.mjs` 流程跑。

```
> 帮我调优 tune_case 下的 gemm kernel 的主循环
[已解析] testcase=tune_case/poc_gemm/gemm.exe  region=loop  seed=…fp8gemm…32mx1_32nx4.s
[缺参数] 这个 GEMM 需要 shape：请给 m / n / k（例：m=256 n=256 k=512）
> m=256 n=256 k=512
[计划] rounds=5 region=loop params=(m=256 n=256 k=512)，开始？(y/n)
```

- 优点：改动小；**确定性保留**（解析后落到与 CLI 完全一致的结构，transcript/results 流程不变）；红线不破（缺 shape 必问）。
- 缺点：仍是"一句话配一次任务"，不是连续对话；多轮 follow-up（"再试 epilogue"）要重起。

### 方案 B：长驻多轮 REPL（真正的 Claude Code 体感）

保留**一个长生命周期的 agent 会话**：system prompt = 现在 `tune.mjs` 里那套（区域词汇、testcase 无关纪律、
anchor-less 用 partial order…），但**不烤死**具体 testcase/region/params；然后进入 readline 循环，每句输入用
`agent.send` / `Agent.resume` 续同一会话。

- agent 自行决定何时调 `observe/propose/eval`（工具不变）、何时反问参数。
- 支持自然 follow-up：
  - "刚才主循环到瓶颈了，换 epilogue 再调 3 轮"
  - "把 shape 换成 m=4096，重测最佳那个 layout"
  - "为什么第 4 轮被拒？" → agent 直接读 results 解释
- 技术对接点：`tune.mjs` 已用 `Agent.create` + `run.stream()`；REPL 只是把"单次 send"改成"循环 send + 复用
  agentId(resume)"，并把退出逻辑从 `process.exit` 改成等下一句输入。

- 优点：体感最接近 Claude Code，多轮探索 / 解释 / 改参一气呵成，最大化 agent 价值。
- 缺点：①**可复现性下降**（NL 历史不如一行 CLI 可复述）；②会话状态 / 预算管理更复杂；③长会话上下文膨胀。

### 方案 C：混合——slash 命令 + 自然语言（推荐的最终形态）

REPL 同时支持两种输入，各取所长：

- **确定性 slash 命令**（可复现、给脚本 / CI）：`/tune --testcase … --region loop -- m=256 n=256 k=512`，等价今天的 CLI。
- **自然语言**（给人探索）：`帮我调优 gemm 主循环` → 走方案 B 的对话补全。
- 辅助命令：`/last`（复跑上次解析出的配置）、`/save`（把当前 NL 任务固化成一行可复现命令写回脚本）。

这与 `mcp_decision_surface.md` 的结论呼应：**当频繁在交互式对话里手动驱动 observe/eval 时，正是上 MCP 的时机**。
所以 B/C 落地时，可顺势把 observe/propose/eval 包成 MCP 工具（类型化 schema，省掉 `--layout '{...}'` 的引号地狱），
让对话里的工具调用更稳。

---

## 3. 必须想清楚的设计点

1. **shape 参数强制反问（红线）**：NL 模式缺 testcase 专属参数时**必须停下来问**，绝不默认。做成槽位填充：
   testcase/region 能推就推，params 槽空着就追问，集齐才允许开跑。
2. **解析后"确认 + 回显等价命令"**：NL 有歧义（"gemm" 匹配到多个 exe / 多个 seed）时先列候选让用户选；确认时打印
   等价 CLI，既防跑错 shape，又顺手补回可复现性。
3. **工具与引擎零改动**：无论哪种方案，`agent_session.py {observe|propose|eval}` 与裁决 / 归档完全不动，只换前门，
   保持"知识只导航、引擎才裁决"的纪律。
4. **会话边界与预算**：一次 NL 任务结束后，best/worst 汇总照旧落 `tune_out/tune_result/`；REPL 不退出，可接着下一句；
   预算（rounds）可对话调整。
5. **落地最小增量**：先做方案 A（`tune_repl.mjs` + 解析 + 确认），用现有 `tune.mjs` 当后端，最快可见效果；验证体验后
   再演进到 B/C（长驻会话 + 可选 MCP）。

---

## 4. 建议落地顺序

1. **方案 A 先行**：几乎不碰核心、不破红线、保留可复现，先把"自然语言开跑"体验跑通。
2. **演进到 B/C**：长驻多轮会话才是真正的 Claude Code 式价值；同步引入"等价命令回显"补回可复现性。
3. **视交互频率上 MCP**：当对话里手动驱动 observe/eval 变频繁，按 `mcp_decision_surface.md` 的判据加一层薄 MCP 适配器。

> 关联文档：`proj/brainstorm/mcp_decision_surface.md`（决策面是否上 MCP）、`proj/testcase_integration.md`
> （testcase 无关红线，§0 工程红线）。本需求只新增"前门"（`tools/sdk/tune_repl.mjs` + 提示词），引擎与现有 CLI 均零改动、可并存。
