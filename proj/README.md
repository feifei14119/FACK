# proj/avo — AVO 指令重排与 Kernel 调优笔记

> 本目录保留 testft 的通用设计与历史实施记录；FACK 复制范围见 [复制说明](copy-from-testft.md)。历史测试数据不代表本次验证结果。

本目录汇集围绕 **AVO（Agentic Variation Operator）kernel 自动调优** 的分析、设计与工具规划，并作为 **testft 工程**（一套指令级 AI 辅助优化引擎）的设计源头。

> **testft 工程定位（v2 评审结论）**：借鉴 AVO 思想，但**完全独立**实现——**不引用、不对接** rocAVO/`feifeiAVO`，也不复用 `amdgpu-asm-tool`。目标架构 AMD gfx942（MI300/MI325X），ISA 事实参考只读 codebase `amdgpu-asm-codebase/llvm-isa/gfx942`。`instruction_reorder.md` 记录的 rocAVO 现状仅作**外部背景/动机**，testft 不依赖它。

---

## 文档索引

| 文档 | 类型 | 内容摘要 |
|------|------|----------|
| [`selfstudy-submodule.md`](selfstudy-submodule.md) | 当前接入 | gfx_hw_prob submodule、gfx942 稀疏检出、默认跳过自学、直接读取已有 skills_out。 |
| [`instruction_reorder.md`](./instruction_reorder.md) | 现状记录 | rocAVO 当前指令重排机制：固定逻辑与 AI 的分工、自动决策逻辑如何产生策略标签、全部 16 个策略标签、core loop 如何被定位。 |
| [`core_loop_scheduler_design.md`](./core_loop_scheduler_design.md) | 设计草案 | 把"AI 直接改 ASM"重构为**结构无关、细粒度、可自动搜索**的调度器：CFG+DAG 区域调度、逐位置 move-DSL、可调权重 list scheduler、AI 角色再定位、落地顺序。**范围覆盖 prologue / core loop / epilogue 三区，各区独立重排、指令不跨界**（唯一跨界动作是只读校验/重算边界 waitcnt）。 |
| [`reorder_engine_api.md`](./reorder_engine_api.md) | 接口设计 | 上一份设计里"重排引擎"这一**固定逻辑组件**的框架与接口：数据模型、依赖图、gap-layout / move 移动接口、**score-based `s_waitcnt` 自动重算算法**（含 wave specialization 的 CFG 数据流版）、校验与回写、端到端调用。 |
| [`knowledge_agent_design.md`](./knowledge_agent_design.md) | 设计草案 | 在固定逻辑搜索之上引入 **Cursor agent 当"元层调优师"**：调优前注入用户 skill / ISA 手册做先验，调优后从记忆归纳新 skill 反哺知识库。核心原则"知识只导航、不裁决合法性"，含知识/记忆三层架构、自进化回路与防 skill 污染纪律。 |
| [`geak_lessons_for_instruction_tuning.md`](./geak_lessons_for_instruction_tuning.md) | 改进设计（分步实施） | 保持**现有单 kernel 指令重排**目标，借鉴 GEAK 的独立复测、程序化预算与跨轮状态、假设账本、多方向探索、有效重排组合和历史复用；含当前代码依据、接口/数据结构建议、P0–P2 实施顺序与验收标准。 |
| [`steps/geak-P0a-screening-evidence.md`](./steps/geak-P0a-screening-evidence.md) | 实施记录 | P0-a 首批：汇编摘要快照、逐次筛选证据、失败分型和筛选/确认语义；记录 CPU 回归、原项目历史失败与真机待验证项。 |
| [`steps/geak-P0b-persistent-run.md`](./steps/geak-P0b-persistent-run.md) | 实施记录 / 使用说明 | P0-b 首批：独立 run CLI、冻结契约、硬预算、候选版本与去重、原始 baseline 门槛、逐次持久化和中断恢复；确认/final 尚未实现。 |
| [`steps/geak-P0c-paired-validation.md`](./steps/geak-P0c-paired-validation.md) | 实施记录 / 使用说明 | P0 后续：显式固定配对规则、确认预算、incumbent 推进、单次 final 与回退；记录 CPU 验证、统计假设和待补的 client/真机证据。 |
| [`geak_rollout_status.md`](./geak_rollout_status.md) | 实施总表 | P0–P2 分阶段软件验收、提交与真机待办。 |
| [`steps/geak-P0d-client-evidence.md`](./steps/geak-P0d-client-evidence.md) | 实施记录 | client 稳定资源冻结、全新构建产物、逐次文件证据与漂移拒绝。 |
| [`steps/geak-P0e-sdk-run.md`](./steps/geak-P0e-sdk-run.md) | 实施记录 | SDK 默认持久化 run、输入来源归档、筛选/确认/final 分层报告。 |
| [`steps/geak-P1a-ledger.md`](./steps/geak-P1a-ledger.md) | 实施记录 | 版本绑定假设、实际指令/修补差分、固定原始告警基准和非权威解释。 |
| [`steps/geak-P1b-search-control.md`](./steps/geak-P1b-search-control.md) | 实施记录 | 多方向 CPU 建议、冻结方向预算、独立 profile、停滞与刷新状态。 |
| [`steps/geak-P2a-replay.md`](./steps/geak-P2a-replay.md) | 实施记录 | 从共同原始字节重建谱系、精确指令映射与组合、冲突和中断恢复。 |
| [`steps/geak-P2b-history.md`](./steps/geak-P2b-history.md) | 实施记录 | 历史证据校验、完整谱系 warm start、来源粘性与知识/历史额度。 |
| [`steps/geak-hardware-acceptance.md`](./steps/geak-hardware-acceptance.md) | 真机执行手册 | gfx942 的 H0–H7 工作顺序、命令模板、预算计算、装载与计时证据、组合/历史复用、同预算消融和验收包；尚未运行 GPU。 |
| [`amdgpu-dump-parsing.md`](./amdgpu-dump-parsing.md) | 技术文档 | 离线解析 AMDGPU **ATT/SQTT 线程跟踪** dump：用 `librocprofiler-sdk.so`（ctypes）流式解码逐指令事件、C 结构体内存布局、category 枚举、PC→反汇编、code object base/size 来源。`analysis/perf.py` 据此实现（第三阶段评测）。 |
| [`anchorless_region_scheduling.md`](./anchorless_region_scheduling.md) | 设计草案(M9) | **无锚点区（prologue/epilogue）调优**：无 MFMA 锚点时改用「按依赖关系自由重排 + 精确 waitcnt」，给 Agent 一套 DAG 观测词汇（节点依赖/合法窗口/计数器语义/waitcnt 预览）+ 线性顺序意图动作（权重/move-DSL/新增 `propose_orders`）。**目标函数 shape 自适应**：真机 TFLOPS 永远裁决，静态代价模型仅作 GPU-less 预筛 + 噪声内平局；小 trip shape 下尾段直接由真机反映，大 trip 下代价模型补梯度。含 `est_share` 选区先验与 Phase 1–4 落地分期。 |
| [`brainstorm/mcp_decision_surface.md`](./brainstorm/mcp_decision_surface.md) | brainstorm | **要不要把 observe/propose/eval 决策面包成一层 MCP**：现状是 agent 用 shell 工具调 `agent_session.py`、读 stdout JSON，ATT 由引擎内解码成 `direction`（非 MCP）。结论：默认维持现状（简单/透明/可复现）；仅当"交互式复用"或"CLI 参数拼写错误"成痛点时，加一层**薄 MCP 适配器**（复用 `agent_session`、`layout/order` 结构化入参、`exe_params` 仍原样透传、ATT 仍留引擎内），与 shell **并存不替换**。 |

> 进度报告在 [`steps/`](./steps/) 下逐里程碑（M0…M7）归档。经审核的经验见 [`../knowledge/`](../knowledge/README.md)。
>
> 真机评测对接样例见 [`testcase_integration.md`](./testcase_integration.md)（`client/poc_kl/fp8_blockscale_gemm/` 的 fp8 GEMM 例子如何映射到三阶段 Evaluator；**§0 是"client 无关、禁止硬编码"工程红线**）。
> 项目接入层（每个调优项目一个 client）见 [`../client/README.md`](../client/README.md)。

---

## v2 评审结论（testft 实现决策，已并入下列各设计文档）

1. **完全独立**：testft 自包含，零外部工程依赖（详见本文件顶部定位）。
2. **架构无关核心 + 独立 ISA 层**：核心引擎（词法/解析/CFG/依赖图框架/重排/waitcnt 框架/pass 框架/校验/回写）架构无关；一切硬件指令集知识收敛到 `isa/Target` 接口，首个实现 `isa/gfx942`，加新架构=新增 `isa/<arch>/`（见 `reorder_engine_api.md` §0 / §1）。
3. **修补 = 可扩展 FixupPass 流水线**：取代写死的 NopFixer；`Target.fixup_pipeline()` 提供有序 pass（gfx942=`[WaitcntRecompute, ForcedNop]`），其他架构可加 `RegDependency`/`RegBankSwitch`/`DelayAlu`/`Clause` 等 pass，连 waitcnt 重算也是其中一个 pass（见 `reorder_engine_api.md` §6）。
4. **gfx942 计数器修正**：4 个计数器 `vmcnt/lgkmcnt/expcnt/`**`vscnt`**——**store 走 vscnt**、**MFMA 写回靠硬件 scoreboard 不进 vmcnt/不插 waitcnt**、`s_barrier` 非 memory fence（见 `reorder_engine_api.md` §5）。
5. **三阶段真机评测 + 反哺方向**：正确性 → 性能（执行时间→TFLOPS）→ **ATT 线程跟踪**（`rocprofv2 --plugin att`，逐指令 issue/duration/stall/category）dump 到 `./att` → `analysis` 用 `librocprofiler-sdk.so` 解码、按 category/stall 分类 → 反哺下一轮（解码细节见 `amdgpu-dump-parsing.md`；映射见 `testcase_integration.md`）。
6. **冷启动算子 `distribute_evenly`**：把某类指令平均分到第 N..M 个 MFMA 间隙，给未手调 kernel 一键初始重排（见 `core_loop_scheduler_design.md` §4 / `reorder_engine_api.md` §4）。
7. **testcase 无关 = 工程红线（严禁硬编码 GEMM / 任何 test 参数）**：调优框架要适配**各种 kernel 与各自的 test 参数**（GEMM 的 `m/n/k`、MLA 的 `qhead/ctx_len/pagesize`、MoE 的专属入参…）。因此 **tools 链路（`tune.mjs` / `agent_session.py` / `harness/evaluator.py` / `tune_script/*.sh`）一律不得写死 `gemm.exe`、`m/n/k` 或任何 shape 参数**：调优项目用 `--client <client/ 下的路径>` 选择，构建/判正确/计时只写在 `client/<项目>/client.py`，它需要的入参用 `--` 哨兵之后**原样透传**，引擎本身**不解析、不默认** shape 参数。`poc_kl/fp8_blockscale_gemm` 只是一个开发样例，与将来的 `poc_kl/<其它 kernel>`、`aiter/...` 并列。详见 `testcase_integration.md` §0。

---

## 阅读顺序建议

1. 先读 [`instruction_reorder.md`](./instruction_reorder.md) —— 理解 AVO **现在**怎么做指令重排，以及它的局限（AI 逐字改 ASM、无自动循环识别、无依赖校验）。
2. 再读 [`core_loop_scheduler_design.md`](./core_loop_scheduler_design.md) —— 理解**未来**怎么改进（反转分工：AI 出结构化策略，固定逻辑做合法重排 + 重算 waitcnt，真机测量打分）。
3. 然后读 [`reorder_engine_api.md`](./reorder_engine_api.md) —— 上一份设计里"重排引擎"的**具体框架与接口**（数据模型 / 依赖图 / 移动接口 / `s_waitcnt` 重算算法），可直接照此实现。
4. 再读 [`knowledge_agent_design.md`](./knowledge_agent_design.md) —— 在固定逻辑搜索之上加一层 **agent + 知识/记忆**（注入经验做先验、自我归纳 skill），让系统越用越聪明。


---

## 一句话脉络

> AVO 现状（外部背景）：**固定逻辑选策略标签 + AI 逐字改 ASM + 实测兜底**（`instruction_reorder.md`）。
> 改进方向：**AI 发细粒度结构化操作（针对稳定指令 ID，含 `distribute_evenly` 冷启动算子）+ 固定逻辑保合法 + 可扩展 FixupPass 流水线（含 waitcnt 重算）+ 三阶段真机评测**，范围覆盖 prologue / core loop / epilogue 三区且各区独立重排（指令不跨界），并从 GEMM 泛化到 MLA/MoE（`core_loop_scheduler_design.md`）；引擎接口（架构无关核心 + `isa/Target` 层）见 `reorder_engine_api.md`。
> 智能层：**agent 注入用户经验/ISA 做先验 + 用 perf counter 分析指引方向 + 从记忆归纳 skill 反哺知识库**，但"知识只导航、不裁决合法性"（`knowledge_agent_design.md`）。
> 工程纪律：**完全独立、架构可插拔（`isa/Target`）、client 无关（`--client` 选调优项目 + `--` 之后原样透传 test 参数，严禁在通用链路写死 GEMM/`m/n/k`，见 v2 §7 / `testcase_integration.md` §0）**，ISA 参考 `amdgpu-asm-codebase`。

---

## 维护说明

- 新增文档请在上方「文档索引」表登记一行。
- 现状类与设计类文档分开维护：`instruction_reorder.md` 跟随 rocAVO 实际代码变化更新；`core_loop_scheduler_design.md` 随设计演进更新。
