# rocAVO 指令重排机制记录

> 记录对象：`/home/feifei/repo/feifeiAVO`（rocAVO，AVO 论文在 AMD gfx942 / MI325X 上的复现）。
> 主题：kernel 主循环（内层 K-loop）的**指令顺序优化**是如何实现的。

---

## 1. 一句话结论

指令重排是一个**人机协作流程**，不是全自动算法：

> **固定逻辑（代码）选方向并产出"策略标签 + 文字指导" → AI（Agent）或人工 patch 据此生成重排后的 `.s` → 固定逻辑自动编译、做正确性校验和 TFLOPS 打分。**

唯一**没有内置自动算法**的环节是"产生重排后的具体代码"，要么 AI 来，要么人预先写成 patch。框架本身不会根据指令间的数据依赖自动搜索/生成合法的新指令顺序。

---

## 2. 固定逻辑代码 与 AI 的分工

| 环节 | 执行者 | 输入 | 输出 | 对应代码 |
|------|--------|------|------|----------|
| 选父版本、拷贝工作区 ASM | 固定逻辑 | 种群最优 `best_id` | `kernels/workspace/*.s` | `evolution.py: prepare_step()` |
| 静态分析（指令统计、占用率） | 固定逻辑 | 工作区 `.s` / `.co` | MFMA/VALU/VMEM/LDS 占比、waitcnt/nop 数、occupancy | `profiler.analyze_asm_static` / `estimate_occupancy` |
| **选策略方向** | **固定逻辑** | 瓶颈、占用率、历史成功率、停滞状态 | **策略标签**（如 `mfma_overlap`） | `supervisor.suggest_strategy()` |
| 生成 Agent 上下文 | 固定逻辑 | 策略标签 + 文字指导 + 知识库片段 | `agent_context.md` | `agent_context.generate_agent_context()` |
| **生成重排后的代码** | **AI / 人工 patch** | 上述上下文 + 当前 `.s` | 修改后的 `.s` 指令序列 | Cursor Agent 手改，或 `scripts/avo_20_rounds.py` 硬编码 patch |
| 汇编 `.s → .co` | 固定逻辑 | 工作区 `.s` | 工作区 `.co` | `evolution.py: compile_workspace()` → `asm_tools.assemble_asm` |
| 正确性校验 + TFLOPS 计时 | 固定逻辑 | `.co` | all_correct / weighted_tflops / peak_tflops | `scoring.quick_score` / `score_kernel` |
| 对比 baseline、入库、更新种群 | 固定逻辑 | 打分结果 | 新版本 + `population.json` | `evolution.py: evaluate_workspace()` |
| 记录步骤、统计策略成功率、停滞检测 | 固定逻辑 | 每步结果 | `supervisor_state.json` | `supervisor.record_step()` |

**关键边界**：固定逻辑的输出粒度止于"标签 + 文字建议"，它**不决定"哪一条指令往哪里挪"**。具体动 `.s` 文件中指令顺序的，是 AI（默认路径）或人工预写的 patch（`avo_20_rounds.py` 路径，该路径不含 AI）。

`src/evolution.py` 注释明确说明了这一点：

```text
In practice, the Cursor agent IS the variation operator.
The actual ASM editing is performed by the Cursor agent in the IDE.
```

---

## 3. 自动决策逻辑：标签是怎样产生的

核心函数：`supervisor.suggest_strategy(bottleneck, current_occupancy_pct, excluded)`。
它是一个**有状态的策略调度器**，决策顺序如下：

### 步骤 0：构造候选集
从 `STRATEGY_POOL`（16 个策略）中剔除 `enabled=False` 和被 `excluded` 排除的策略。
（`evolution.py` 默认把"最近 2 步用过的策略"放进 `excluded`，避免连续重复。）

### 步骤 1：停滞检测优先（diversification）
- 触发条件：`stagnation_count >= stagnation_threshold`（默认阈值 3）。
  `stagnation_count` 在每次"未改进"时 +1，"改进"时清零（见 `record_step`）。
- 行为：调用 `_diversify()` —— 统计最近 5 步用过的**类别**（category），优先从**未用过的类别**里**随机**挑一个策略，强制换方向跳出局部最优。

### 步骤 2：按瓶颈过滤（若已知瓶颈且未停滞）
`_filter_by_bottleneck()` 按下表把候选集收窄到相关类别：

| 瓶颈 bottleneck | 保留的策略类别 category |
|------|------|
| `compute` | scheduling, misc |
| `memory` | memory, tiling |
| `latency` | scheduling, register |
| `lds` | lds |
| `mixed` | scheduling, memory, lds |

瓶颈来自上一次 profile 结果（`state.last_profile` 里的 `bottleneck`）。

### 步骤 3：探索 vs 利用（exploration vs exploitation）
在过滤后的候选集中，以概率 `exploration_ratio`（默认 0.3）二选一：

- **探索 `_explore()`**：挑**尝试次数最少**的策略（`strategy_stats[...]['attempts']` 最小），保证覆盖面。
- **利用 `_exploit()`**：挑**历史成功率最高**的策略（`successes / attempts`，未尝试过的给 0.5 的中性先验），偏向已被证明有效的方向。

### 兜底
候选集为空时 `_fallback_strategy()` 返回 `instruction_interleave`。

### 决策流程图

```text
suggest_strategy()
  │
  ├─ 构造候选集（排除 disabled + excluded）
  │
  ├─ 停滞? (stagnation_count >= 3)
  │     └─ 是 → _diversify(): 选最近未用过的类别里随机一个  ──► 返回标签
  │
  ├─ 否 → 已知瓶颈? → _filter_by_bottleneck() 收窄候选集
  │
  └─ random() < 0.3 ?
        ├─ 是 → _explore(): 尝试次数最少的策略           ──► 返回标签
        └─ 否 → _exploit(): 历史成功率最高的策略         ──► 返回标签
```

> 注：决策含 `random.choice` / `random.random()`，因此**结果非确定性**；同样状态下多次调用可能给出不同标签。

---

## 4. 支持的全部策略标签

数据来源：`src/supervisor.py` 的 `STRATEGY_POOL`（共 16 个）。
`difficulty`：1=易，3=难。带 ★ 的策略在 `src/agent_context.py` 的 `STRATEGY_GUIDANCE` 中有配套的详细编辑指导文字。

### 4.1 指令调度类（scheduling）—— 与"主循环指令顺序"最相关

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `mfma_overlap` ★ | 2 | 把 global load 插到连续 `v_mfma` 之间，用计算延迟掩盖访存延迟（利用 co-issue 窗口）。 |
| `software_pipeline` ★ | 3 | 软件流水：在算第 N 块 MFMA 的同时发起第 N+1 块的加载；加深现有的三缓冲流水。 |
| `waitcnt_optimization` ★ | 2 | 优化 `s_waitcnt` 位置/计数（vmcnt/lgkmcnt），让更多 load 在飞行中重叠，减少 stall。 |
| `nop_elimination` ★ | 1 | 用有用指令（地址计算等）填充 `s_nop` 延迟槽；注意保留 MFMA 后强制要求的 NOP。 |

### 4.2 访存类（memory）

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `prefetch_tuning` ★ | 1 | 调预取距离（提前几块 tile 加载），权衡延迟掩盖 vs 寄存器压力。 |
| `coalesced_access` ★ | 2 | 让相邻 lane 访问相邻地址，使全局访存按 128B cache line 合并。 |
| `vectorized_load` ★ | 1 | 用更宽的向量加载（dwordx4 替代 dwordx2/dword），提升单指令带宽。 |

### 4.3 寄存器类（register）

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `vgpr_reduction` ★ | 2 | 减少 VGPR 占用以提高 occupancy（复用临时寄存器、去死代码）。 |
| `accum_register_reuse` ★ | 3 | 调整 `.amdhsa_accum_offset`，优化 ArchVGPR / AccVGPR 边界。 |

### 4.4 LDS 类（lds）

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `lds_bank_conflict_free` ★ | 2 | 给 LDS 数组加 padding 消除 bank 冲突（gfx942 共 32 banks，每 bank 4B）。 |
| `lds_double_buffer` ★ | 3 | LDS 双/三缓冲：算一块的同时往另一块写，掩盖 LDS 写延迟。 |

### 4.5 分块类（tiling）

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `tile_size_increase` ★ | 2 | 增大宏块（如 64x64→128x64）提升数据复用，代价是寄存器压力上升。 |
| `tile_size_decrease` ★ | 1 | 减小宏块换更高 occupancy（寄存器受限时）。 |
| `split_k_tuning` ★ | 2 | 调 split-K 因子（factor 在 host 端决定；ASM 侧优化 reduction epilogue / 信号量同步）。 |

### 4.6 其他类（misc）

| 标签 | 难度 | 说明 |
|------|:----:|------|
| `instruction_interleave` ★ | 3 | 交错 VALU / VMEM / LDS / MFMA，使各功能单元同时忙起来（也是兜底策略）。 |
| `loop_unroll` ★ | 2 | 把内层 K-loop 展开 2~4 倍，减少分支开销、增加 ILP，代价是代码膨胀。 |

> 直接关于"主循环指令顺序"的标签主要是 4.1 调度类（`mfma_overlap` / `software_pipeline` / `waitcnt_optimization` / `nop_elimination`）以及 4.6 的 `instruction_interleave`、`loop_unroll`。

---

## 5. 两条"产生重排代码"的路径对比

| | 路径 A：AI 变异（默认） | 路径 B：硬编码 patch |
|--|--|--|
| 谁出重排代码 | Cursor Agent（LLM） | 人工预先写好（`scripts/avo_20_rounds.py`） |
| 是否含 AI | 是 | 否 |
| 重排怎么落地 | Agent 直接编辑工作区 `.s` | `str.replace` 字符串替换 patch（匹配不到则跳过） |
| 合法性/依赖校验 | 仅靠"编译 + 数值正确性测试"事后兜底 | 同左，无 ISA 级依赖校验 |
| 自动化程度 | 半自动（需 Agent 介入每步） | 可全自动批量跑 N 轮，但变体内容写死 |

`avo_20_rounds.py` 的典型 patch 形式：把 `ds_read_b128` 从 `buffer_load` / `s_add` **之后**上提到第一条 `v_mfma` **之后**，即一种典型的主循环指令重排。

---

## 6. core loop（主循环）块是如何被定位的

> 关键结论：**固定逻辑代码本身完全不识别、不定位 core loop**，它没有任何控制流分析或循环检测。"定位到哪个循环块去重排"被完全外包给 AI（文字规则）或人工（硬编码 label）。

需要把"判断"拆成两个不同的问题，AVO 对二者处理方式完全不同：

| 问题 | 谁来判断 | 怎么判断 | 输出粒度 |
|------|----------|----------|----------|
| **要不要 / 朝哪个方向重排**（选策略） | 固定逻辑 | 全局瓶颈分类 + 占用率 + overhead 指标 | 整 kernel，只到"做哪类优化" |
| **重排哪一段代码**（定位 core loop） | **AI 或人工** | AI 读 `.s` 按文字规则找；或 patch 硬编码 label | 具体到指令块 |

### 6.1 第一层："判断需要重排" —— 固定逻辑，仅整 kernel 粒度

固定逻辑只产出"这个 kernel 整体瓶颈是什么、该用哪类策略"，**不指向任何具体代码行**。依据全是**全局聚合指标**：

1. **硬件计数器瓶颈分类**（`profiler._classify_bottleneck`）：用整个 kernel dispatch 的聚合计数（`SQ_INSTS_MFMA`、`SQ_BUSY_CYCLES` 等）+ 由 M/N/K 算的算术强度，分类为 `memory / compute / lds / latency / mixed`。得到 `latency` 或 `compute` 时才暗示"主循环调度可能有问题"，并给 hints（如 "check for excessive s_waitcnt stalls"），但**不定位是哪个 stall、哪个循环**。
2. **静态指令统计**（`profiler.analyze_asm_static`）：**逐行全文件**统计 MFMA/VALU/VMEM/LDS/waitcnt/nop/barrier 的总数与占比，并算 overhead 占比 `(waitcnt+nop+barrier)/total`。它会数 `s_cbranch`/`s_branch`，但**只计入 `branch_count`，绝不用分支圈定循环体**。
3. **supervisor** 拿 bottleneck + occupancy 选出策略标签（如 `software_pipeline`）。

➡️ 这一层最细只到"该做指令调度类优化"，**到不了"在 label_05AF 这个块做"**。

### 6.2 第二层："定位 core loop 块" —— 固定逻辑不做，外包出去

代码里所有 "main loop / K-loop / label" 字样**全部在 `agent_context.py` 的 `STRATEGY_GUIDANCE` 文字里**，是写给 AI 看的自然语言"找法"，不是可执行的定位代码。例如：

- `mfma_overlap` 指导：「找以 `label_` 开头、后面跟着连续 `v_mfma_f32_16x16x16_bf16` 的块」。
- `loop_unroll` 指导：「找 `s_cmp + s_cbranch` 模式的主 K-loop」。
- 通用编辑规则第 7 条：「Focus on the main loop：性能主要由内层 K-loop 决定」。

真正的"定位"靠两条途径：

- **途径 A（AI）**：把上述文字规则交给 Cursor Agent，由 AI 读 `.s` 时凭语义识别主循环（`label_` + 连续 MFMA，或带 `s_cmp/s_cbranch` 回边的块）。
- **途径 B（人工 patch）**：`scripts/avo_20_rounds.py` 直接把 label 名（`label_05AF`、`label_0266`）和指令上下文写死做字符串匹配，根本不"找"；匹配不到则 `napp==0` 跳过。

### 6.3 小结

- **"要不要重排 / 做哪类重排"** = 固定逻辑根据**整 kernel 的瓶颈 / 占用率 / overhead** 判断 → 给策略标签。
- **"重排哪个 core loop 块"** = 固定逻辑**完全不参与**；由 AI 按文字规则在 `.s` 里语义识别，或由人工 patch 硬编码 label 定位。

AVO **没有"core loop 自动识别器"**。若要把"定位"也纳入固定逻辑，需自行补一个 CFG 分析：解析 `s_cmp/s_cbranch` 的回边（back-edge）识别循环，再按 MFMA 密度挑出内层 K-loop。

---

## 7. 重要注意事项 / 局限

1. **没有自动的指令顺序生成器/搜索器**：无 list scheduler、无随机重排、无遗传算子来自动产生合法新顺序。
2. **没有静态依赖/合法性分析**：重排是否破坏数据依赖、`s_waitcnt` 是否仍正确，**只靠"编译 + 数值正确性测试"事后判断**；错误的重排表现为编译失败或结果错，框架不会主动规避。
3. **决策非确定性**：`suggest_strategy` 含随机成分，相同状态可能给出不同标签。
4. 若要升级为"全自动调指令顺序"，建议在现有自动测试闭环上补一个真正的变异算子：解析内层 K-loop 的指令读写寄存器、构建依赖图、在保依赖前提下做合法重排（list scheduling / 随机扰动）自动生成候选 `.s`，再复用 `compile_workspace + evaluate_workspace` 筛选，用 `supervisor` 的成功率/停滞统计驱动迭代。
