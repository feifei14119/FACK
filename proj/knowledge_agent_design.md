# 知识注入与自进化 Agent 设计

> 目标：在自动指令重排调优之上，引入一个 **Cursor agent 当"元层调优师"**：调优前由用户注入调优经验（skill）、并能读 ISA codebase / 硬件手册做先验；调优中由固定逻辑搜索；调优后由 agent 从记忆中归纳新 skill 反哺知识库，让系统越用越聪明。
>
> 本文档是 `core_loop_scheduler_design.md` / `reorder_engine_api.md` 的延伸：前两者讲"固定逻辑怎么合法重排"，本篇讲"知识与 agent 怎么引导搜索、并自我进化"。

---

## 1. 结论

- **有用**：用领域先验剪枝巨大的搜索空间，比盲调效率高一个量级；跨 kernel 迁移（GEMM 学到的喂给 MLA）复利增值；自我总结 skill 让系统越用越聪明。
- **可实现**：Cursor agent 能读 codebase / skill / ISA、调工具（重排引擎、编译、评测）、写文件（回写 skill）。"记忆"通过持久化文件实现，契合 Cursor 的 Skills / Rules 机制。
- 它本质是现有 rocAVO 已有机制（`knowledge_base/*.md` + supervisor 的 `strategy_stats` 成功率记忆）的**强化版**。
- **但必须守住一个核心原则**（见 §2），否则自进化会反受其害。

---

## 2. 核心安全原则：知识只"导航"，绝不"裁决合法性"

把知识严格分成两类：

| 类别 | 例子 | 来源 | 作用 |
|------|------|------|------|
| **合法性知识**（不可破坏） | MFMA 后强制 nop、m0 配对、barrier 计数、数据依赖 | **硬编码进固定逻辑引擎** | 裁决"什么不能做" |
| **性能启发**（可以错） | "MFMA 后第 N 拍插 v/s 最好"、"两条 ds 间隔不超过 X"、"MFMA 延迟约 K 周期" | 用户 skill / ISA 手册 / 记忆 | 引导"先试什么" |

> **agent 读手册、读 skill 得到的知识，只影响"试什么"，永远不影响"什么合法"。**
> 即便它读错手册、总结出错误 skill，最坏只是浪费搜索预算，**绝不可能产出坏 kernel**——合法性由引擎硬编码 + 编译/数值测试双重兜底（见 `reorder_engine_api.md` §3、§6）。

判别口诀：**正确性相关 → 硬编码；性能相关 → 当启发、由实测验证。**
例如 MFMA 强制 nop（正确性）必须硬编码；MFMA 后最佳插入拍数（性能）当启发即可。

---

## 3. 用户经验如何落到引擎（具体映射）

agent 的活儿之一是把自然语言经验"翻译"成引擎能吃的结构化形式：

| 自然语言经验 | 落地形式 |
|--------------|----------|
| "MFMA 后第 N 拍插 v/s 指令最好" | **move 模板 / priority 特征**（倾向把填充物放在间隙第 N 位） |
| "两条 ds 不能间隔超过 X" | **layout 软/硬约束**（间距上下限），搜索时遵守 |
| "MFMA 延迟约 K 周期" | **延迟表参数**，喂给调度器关键路径打分 |
| "某类访存优先合并" | **priority 权重** |

即 skill 最终变成四种东西：**硬约束 / priority 权重 / move 模板 / 延迟参数**。
（move 模板、gap-layout、priority 权重的接口见 `reorder_engine_api.md` §4 与 `core_loop_scheduler_design.md` §4。）

---

## 4. 知识与记忆架构（三层持久化 + agent 元角色）

```
knowledge_base/   ISA 笔记、硬件手册摘录、硬件真值规则
skills/           用户给的 + agent 总结的调优启发（每条带证据 + 置信度 + 适用范围）
experiments.log   结构化原始记忆：(kernel, shape, 变换, 实测 delta, perf counter 摘要)
```

agent 的三个时机：

- **调优前**：读 user skill + ISA + knowledge_base → 产出"搜索计划"（初始权重、候选 move 族、参数范围、要遵守的约束）→ **给固定逻辑搜索播种**。冷启动 kernel 可先发 `distribute_evenly` 给一个均匀基线。
- **调优中**：内层搜索是**纯固定逻辑**（经典优化器 / 退火），agent **不进内层循环**（快、便宜、可复现）。每轮评测产出的 **perf counter 经 `analysis` 解析成瓶颈分类 + 方向 hints**（compute / memory / lds / latency …），用来**导航下一轮**选哪个区、用哪类编辑算子、调哪些权重——把盲搜变成被硬件实测指标导航的定向搜索。
- **调优后**：读 `experiments.log`（含 perf counter 摘要）→ 归纳候选 skill → 验证 → 回写 skills 库。

> perf counter 的**字段语义是架构相关的**，由 `isa/Target.perf_counter_schema()` 提供；`analysis` 据此把原始计数器映射到瓶颈维度。这与"知识只导航、不裁决合法性"一致：counter 分析只影响"试什么方向"，绝不影响"什么合法"。

Cursor 特定点：

- **跨会话记忆 = 文件**（skill `.md` / knowledge_base / 结构化日志），agent 开场读、收尾写——干净、可审查，正是 Skills / Rules 的设计意图。
- agent 放在**元层、低频调用**：做"播种 + 高层归因 + 回写 skill"这类高价值的事；每个候选的评测交给固定逻辑。
- agent 决策非确定 → 把它的决策也记进日志，保证可追溯；固定逻辑搜索本身可复现。

---

## 5. 自我进化回路 —— 及其最大的坑

"从记忆总结 skill 反哺 skill 库"是最有价值、也最危险的部分。

**最大风险：skill 污染 / 伪泛化**——一条在某 shape 上有效的规律，写进库后可能在别的 kernel 上有害，污染所有后续调优。

要安全，回写必须有纪律——每条 skill 带元数据：

```yaml
skill: "hoist ds_read 到累加组首条 MFMA 之后"
evidence: { kernels: [bf16gemm_96x64, ...], shapes: [...], n_samples: 17 }
effect: { mean_delta: +2.8%, win_rate: 14/17 }
scope: { arch: gfx942, loop_kind: mfma_dense }
confidence: 0.7          # 随证据增减
status: candidate        # candidate -> trusted（跨 N 个独立案例/留出 kernel 验证后才晋升）
```

配套机制：

- **证据 / 出处**：每条 skill 记录支撑它的实验、效应量、样本数。
- **验证门槛**：跨 N 个独立案例（或留出 kernel）确认后才从 `candidate` 升 `trusted`。
- **置信度 + 衰减**：被反例打脸就降级；冲突的 skill 由实测仲裁。
- **可选人工 review**：因为是写进库的知识。

本质上是个"带统计背书的经验库"，类似 library-learning / 元学习——可实现，但需要这套纪律。

---

## 6. 风险小结

| 风险 | 对策 |
|------|------|
| skill 污染 / 过拟合 | 证据 + 置信度 + 验证门槛 + 衰减 |
| 手册规则幻觉 | 只导航不裁决；关键规则与硬编码引擎交叉核对 |
| skill 过时（换架构 / kernel） | 标 scope，超范围不用 |
| skill 冲突 | 置信度加权，实测仲裁 |
| 成本 / 复现 | agent 只在元层；内层固定逻辑可复现 |

---

## 7. 落地节奏

1. **只读知识注入**：把 user skill + ISA 摘录喂给搜索做播种（无回写）。验证"有先验 vs 盲调"的效率差。
2. **结构化实验日志**：记忆的原料 `experiments.log`。
3. **agent 归纳 + 带门槛的回写**：`candidate → trusted`，先人工 review 再自动。
4. **逐步放开自动晋升**。

> **落地状态（2026-06，首版）**：`agent/knowledge.py` 已实现 Skill schema（`statement/when/action/`
> `evidence/effect/confidence/status`）+ 文件持久化（`knowledge/engine/skills/*.json`，原 `agent/store/skills` + `experiments.log` JSONL）、
> `seed_search_plan`（调优前播种：scope 过滤 + trusted-first 排序 → 先验 specs + avoid + note）、
> `log_experiment`/`induce_skills`（调优后归纳：按 arch/loop_kind/bottleneck/scenario/transform 分组算
> mean_delta/win_rate/n，正收益→prefer、回归/恒错→avoid，**跨 ≥2 独立 kernel 才 candidate→trusted** 的防污染门）；
> `agent/tuner.py` 串起 before→during→after 闭环（`search()` 加纯增量 `extra_specs` 先验入口）。
> 已用真机 cold-start/搜索的 12 条实测播种出 13 条 candidate skill（仅 1 真实 kernel，门正确地未放行 trusted）。
> **本步骤 1–3 的「统计归纳」已落地。**
>
> **LLM 决策面已接（2026-06，`agent/session.py::AgentSession`）**：把 `reorder_engine_api §3.4.3` 的
> observe→propose→commit 闭环封成 LLM（Cursor agent / 任意大模型）逐轮驱动的三个方法——
> `observe()` 出 JSON 事实地图（逐 slot 布局 + 类型 + 合法窗口 + 延迟边 + **受保护预取集** + direction 投票 + 知识播种），
> `propose()` 非提交校验一批 layout 回 `SkipReason`，`commit_and_eval()` 走 `build_candidate({"kind":"layout"})`
> 同一门控管线（重算+Verifier+真机+噪声门）并把 `decided_by:"llm_agent"` 的决策记入 `experiments.log`。
> CLI 桥 `tools/agent_session.py {observe|propose|eval}`。真机 gemm 验证：observe 出 96 锚点/355 可动/18 受保护预取，
> propose 下沉预取即回 `prefetch_protected`。**LLM 严格只导航、不进内层、不裁决合法性。**
>
> **全自动在环已接（2026-06，`tools/sdk/`）**：用 **Cursor SDK** 起一个**本地 Cursor agent** 程序化驱动调优——
> `node tune.mjs <seed.s>` 让 agent 用 shell 工具调 `tools/agent_session.py {observe|propose|eval}`，自己跑
> observe→propose（看 SkipReason 迭代）→eval（只收 `accepted` 的更快且正确布局）。即"决策=Cursor agent、裁决=引擎+真机"。
> 选 TS/Node SDK 因 Python SDK 要 ≥3.10（本机仅 3.8），引擎仍跑 3.8、agent 通过 shell 调它。决策入 `experiments.log` 可追溯。
>
> **仍待办**：跨第二个真实 kernel 晋升 trusted、ISA 笔记播种仍占位；真实带 GPU+API key 的端到端跑（本环境无 key/无 ≥3.10 Python，
> 已做参数/无-key/import 冒烟验证）。守住「知识只导航、合法性由引擎裁决」。

---

## 8. 一句话总括

**用 Cursor agent 当"元层调优师"——读 skill/ISA 播种、归纳记忆反哺 skill 库；但必须守住"知识只导航、不裁决合法性"，且回写 skill 要有证据 + 置信度 + 验证门槛防污染。内层搜索仍是固定逻辑。** 这正是现有 rocAVO `knowledge_base` + supervisor 记忆的强化版。
