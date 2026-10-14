# 调优会话 transcript 段落说明（`client/<名>/tune_out/transcripts/`）

本文解释一次调优运行产出的 **transcript（会话实录）** 里每个段落的含义，以
`tune-2026-06-28T09-06-26-309Z.md` 为例。这些文件由 `tools/sdk/tune.mjs` 的 `renderEvent()`
把 Cursor agent 的事件流渲染而成。

---

## 0. 一次运行产出哪些文件

同一时间戳前缀下有 4 个文件，各司其职：

| 文件 | 内容 | 用途 |
|---|---|---|
| `tune-<ts>.md` | **可读版会话实录**（本文主角） | 人眼回看 agent 的思考/动作/结果 |
| `tune-<ts>.jsonl` | **忠实全量事件流**（每行一个 SDK 事件） | 程序解析 / 复原 / 调试，`.md` 是它的精简渲染 |
| `tune-<ts>.results.jsonl` | **权威逐次评估结果**（每次 eval 一行） | 由 `agent_session.py eval` 确定性写入，非事件流抓取 |
| `tune-<ts>.results.md` | 上面的表格版 | 人眼看每轮 tflops/accepted |

> `.md`（实录）回答"agent 怎么想、怎么做"；`.results.*`（结果）回答"每次评估测出了什么"。两者口径不同，
> 详见本文 §4 对 `round` 字段的说明。

---

## 1. 文件头（元信息）

```
# tune transcript
- agent: agent-a86b521c-…        ← 本次 Cursor agent 的唯一 ID（可用于 resume/排查）
- seed: …/fp8gemm_…_32mx1_32nx4.s ← 被调优的种子 shader（.s）
- client: poc_kl/fp8_blockscale_gemm ← 调优 client（client 无关：这里恰好是 GEMM）
- model: auto  loop=20 rounds=5 region=prologue params=[m=256 n=256 k=512]
```

最后一行是本次运行的全部关键参数：`model`（模型）、`loop`（评测循环次数）、`rounds`（采纳轮软预算）、
`region`（本次锁定调优的代码区域）、`params`（透传给 client 的参数，**因 kernel 而异**）。
（旧 transcript 的这一行写的是 `testcase: <exe 路径>`。）

---

## 2. `## 初始输入提示词 (System/Task Prompt)`

这是发给 agent 的**唯一一段系统/任务提示词**（`tune.mjs` 里的 `PROMPT`）。它本身分为几块，理解它就理解了
agent 后续所有行为的"规则书"：

1. **角色与边界**：agent 是"元层调优器"，**只负责导航**（试什么），合法性由引擎裁决、性能由真机裁决——
   "错误选择只浪费预算，永远不会产出坏 kernel"。
2. **REGION SCOPE（区域范围）**：本次锁定哪个区域（如 `prologue`），要求每条命令都带 `--region`；
   若是 `auto`/`all` 则允许跨区域漫游。
3. **TWO VOCABULARIES（两套词汇）**：告诉 agent 按 observe 返回的内容二选一——
   - **ANCHORED 区**（含 MFMA）：用 `--layout '{"<slot>":[<iid>…]}'` 往 MFMA 间隙塞填充指令；
   - **ANCHOR-LESS 区**（无 MFMA，prologue/epilogue 常见）：用 `--order '[<iid>…]'` 按依赖重排，降低 `est_cycles`。
4. **TOOLS（工具三件套）**：observe / propose / eval 的确切命令模板（含 `--client`、`--region`、`--` 透传参数）。
5. **LOOP（工作循环）**：observe → propose（先做便宜的合法性预检）→ eval（真机裁决）→ 只保留 accepted 的，
   否则回退；最多 `rounds` 轮。
6. **Report（收尾要求）**：最后报告最佳 layout、tflops 对比、一行原理。

---

## 3. 之后反复出现的 4 类段落（agent 的工作循环）

提示词之后，文件就是 agent 一轮轮"思考→动作→拿到结果→再思考"的循环。每类段落对应 `renderEvent()` 的一种事件：

### 3.1 `#### LLM 思考`
agent 的**内部思考**（thinking）。流式 token 已被合并成可读段落。这里是它的推理：读 observe 事实、
判断瓶颈、决定下一步试什么、解释为什么某候选被拒。**不影响引擎**，仅供理解决策。

### 3.2 `#### LLM 输出(文本)`
agent 面向用户的**正式文本输出**（text）。通常是阶段性结论或最终报告。与"思考"的区别：这是它"说出口"的话。

### 3.3 `#### LLM 工具调用(动作): shell`
agent 实际执行的**动作**，几乎都是一条 shell 命令，内容就是调用引擎三件套之一：

```bash
cd /home/feifei/repo/FACK && python3.8 tools/agent_session.py observe … --region prologue -- m=256 n=256 k=512
```

看这一段就知道 agent 这一步在 observe / propose / eval 哪个动作、用了什么 layout/order。

### 3.4 `#### 工具结果 -> 下一轮输入 (shell, exit=0)`
上一条命令的 **stdout（引擎返回的 JSON）**，会作为下一轮喂回给 agent 的输入。`exit=0` 表示命令成功。
内容按调用的动作不同而不同，见 §4。（渲染时截断到 4000 字符，全量在 `.jsonl`。）

> 另有少量其它段落：`#### LLM 工具调用(动作)`（非 shell 的工具，如 read/grep）、`#### LLM 输出(其它块)`、
> `#### 事件: <type>`、`#### 用户/工具消息`。它们是 SDK 其它事件类型的兜底渲染，信息量低，扫读即可。

---

## 4. 工具结果 JSON 的关键字段

### 4.1 observe 的返回（事实地图）
- **ANCHORED 区**：`anchors`（MFMA 锚点）、`slots`（可填的间隙）、`fillers`（候选填充指令，每个带
  `iid/kind/legal_window/movable…`）。
- **ANCHOR-LESS 区**：`dag`（每个节点含 `iid/kind/pos/legal_window/movable/is_fence/bumps_counter/waits_on/preds/succs`）
  + `waitcnt_preview`（当前各 wait 计数 + `cost.est_cycles`）。
- **总是返回**：`regions`（各区域的 index/kind/行范围/指令数/`est_cycles`/`trip_count`/`est_share`）、
  `region`（本次选中的区域）、`direction`（瓶颈方向**噪声先验**，仅参考）、`prior_plan`（历史计划）。

### 4.2 propose 的返回（不提交的合法性预检，便宜）
- `legal`：整体是否合法（无 skip）。
- `placed[]`：成功放置的指令。
- `skipped[]`：被拒的指令，带 `reason`（如 `prefetch_protected`/`raw`/`war`/`mfma_latency`…）、合法窗口
  `legal_window` 和阻塞者 `bound_iid`——agent 据此修正后再试。
- `cost.est_cycles`：该候选的代价模型估计（`--order` 路径用它判断是否值得真机评测）。

### 4.3 eval 的返回（真机裁决，唯一权威）
```json
{ "correct": true, "tflops": 10.69302, "baseline_tflops": 10.62…,
  "accepted": true, "note": "accepted: faster beyond noise",
  "est_cycles": 462, "baseline_est_cycles": 462 }
```
- `correct`：结果是否通过正确性验证（**最高优先级**，false 直接拒）。
- `tflops` / `baseline_tflops`：候选 vs 基线的实测性能。
- `accepted`：是否被采纳（需"正确 **且** 快过基线超出噪声"）。
- `note`：裁决说明。`est_cycles` / `baseline_est_cycles`：代价模型估计（辅助参考）。

> **关于 `round`**：`.results.*` 里的 `round` 是"每次 eval +1"的序号，**不是** `rounds` 软预算。
> 一轮可能 propose 多次、eval 多次，所以 results 行数常多于 `rounds`。

---

## 5. 怎么快速读一份 transcript

1. 先看**文件头**：确认 region / params / rounds，知道这次在调什么。
2. 跳读 **`初始输入提示词`** 的 REGION SCOPE 与 TWO VOCABULARIES，确认是 layout 还是 order 路径。
3. 沿着 **`工具调用(动作): shell`** 段落看 agent 的动作序列（observe→propose→eval→…）。
4. 每个 **`工具结果`** 段落里，propose 看 `legal`/`skipped`，eval 看 `correct`/`tflops`/`accepted`。
5. 配合 **`LLM 思考`** 理解"为什么这么试 / 为什么被拒 / 下一步改什么"。
6. 最终结论看文件末尾的 **`LLM 输出(文本)`**，或直接看 `tune_result/<ts>.summary.md` 的 best/worst。

> 关联：渲染逻辑见 `tools/sdk/tune.mjs::renderEvent()`；参数与输出文件说明见 `tools/sdk/README.md`；
> 区域 / 词汇的设计见 `reorder/regions.py` 与 proj 文档。
