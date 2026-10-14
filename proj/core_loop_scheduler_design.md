# Core Loop 指令重排：自动化调度器设计草案

> 目标：把 AVO 当前"AI 直接逐字编辑 ASM"的指令重排方式，重构为**结构无关、细粒度、可自动搜索**的调度器。
>
> **优化范围：prologue / core loop / epilogue 三个区域，各自独立做区域内重排，指令绝不跨区域边界。** 不做跨区域代码移动（那样任务重、易出错，已否决）。能从 GEMM 泛化到 MLA / MoE 等其他 kernel。
>
> 本文档是设计草案（brainstorm 结论），非现状记录。现状见同目录 `instruction_reorder.md`。
>
> **v2 评审补充（testft 工程化原则）**：
> - **完全独立 + 架构无关核心 + 独立 ISA 层**：testft 不依赖任何外部工程；核心引擎架构无关，硬件指令集知识收敛到 `isa/Target` 接口（首个实现 gfx942），加新架构=新增 `isa/<arch>/`。接口细节见 `reorder_engine_api.md` §0/§1。
> - **修补做成可扩展 FixupPass 流水线**：不写死 NopFixer；waitcnt 重算、强制 nop、（其他架构的）寄存器依赖/寄存器组切换指令都是 pass，由 `Target.fixup_pipeline()` 提供。见 `reorder_engine_api.md` §6。
> - **三阶段真机评测 + counter 反哺**：正确性 → 性能 → perf counter dump → 分析得方向。见本文 §9。
> - **新增冷启动编辑算子 `distribute_evenly`**：见本文 §4。

---

## 0. 背景与动机

当前 AVO 的指令重排是"固定逻辑出策略标签 → AI 逐字改 `.s` → 编译+实测兜底"（详见 `instruction_reorder.md`）。最薄弱的一环是 **AI 逐字编辑 3000 行 ASM**：

- AI 改 ASM 易错（寄存器号、offset、`s_waitcnt` 计数、`m0` 配对），合法性**只能靠编译+数值测试事后兜底**，浪费编译/测试周期。
- AI 调用慢、贵、非确定性，**无法做大规模自动搜索**（每个候选都要一次 AI 调用）。
- 指令重排本质是**有硬件约束的调度问题（list scheduling）**，是固定逻辑的强项：建依赖图、保证合法、自动重算 waitcnt、一秒生成上千候选。

**核心思路：反转分工。** AI 只输出"结构化策略/操作"，**绝不直接写 ASM**；固定逻辑负责"合法重排 + 重算 waitcnt"；testft 自带 harness 负责真机实测（三阶段：正确性/性能/counter dump，见 §9）。

---

## 1. 重新划分的分工

| 层 | 谁做 | 输入 | 输出 |
|----|------|------|------|
| 定位 + 建图 | 固定逻辑 | `.s` | prologue / loop / epilogue 三区 + 各区依赖 DAG + 稳定指令 ID |
| 合法重排 + 重算 waitcnt + 插 nop | 固定逻辑 | DAG + 变换请求 | 合法候选 `.s`（**legal-by-construction**） |
| 真机测量（三阶段：正确性/性能/counter dump） | testft 自带 harness | `.co` | 正确性 / TFLOPS / counter 文件→方向 |
| **搜索方向 / 出策略** | **AI 或经典优化器** | profile + 历史 | **结构化变换请求（move-DSL / 权重），不碰 ASM** |

关键原则：**AI 永远不直接发射指令文本**，只发"做哪种变换、对哪条指令、参数多少"。

---

## 2. 被否决的方案：参数化模板调度器（及原因）

曾考虑把 loop 抽象成若干 phase，只暴露少量全局旋钮（`prefetch_distance`、`ds_read_interleave_ratio`、`waitcnt_relax`…）。**已否决**，两个死穴：

1. **结构假设**：模板写死了"MFMA + load + ds_read"，把 GEMM 的先验焊进调度器。MLA 有 softmax/exp/转置/多次 matmul，MoE 有 gather/scatter/分支，loop 体根本不是这个形状。
2. **全局旋钮太粗**：`ratio=N` 强制每个间隙塞一样多，而最优往往是**异构**的——例如"间隙1插1条 ds_read、间隙2不插、间隙3插3条"。标量旋钮表达不了这种自由度。

结论：**放弃结构假设（回到纯依赖图）；放弃全局旋钮（改为逐位置细粒度表示）。**

---

## 3. 泛化设计：结构无关的 CFG + DAG 区域调度器

不对 loop 体做任何形状假设，三步对任意 kernel 成立：

1. **建 CFG**：在 label / 分支 / `s_barrier` 处切块，得到若干"可调度区域"（直线段）。barrier、分支、循环回边作为**调度栅栏（fence）**——不跨栅栏移动指令。
2. **逐区域建 DAG**：每条指令解析 defs/uses，连边：
   - RAW / WAR / WAW 寄存器依赖
   - `m0` 依赖
   - counter 顺序语义（vmcnt / lgkmcnt）
   - **保守的访存别名依赖**
3. **DAG 内重排**：任何合法拓扑序都是候选。

### 3.1 对未知 kernel 的正确性：靠"保守"保证

- 访存别名拿不准 `buffer_load X` 与 `ds_write Y` 是否冲突时，**默认连一条依赖边**（宁可不重排，也不出错）。先保正确，别名分析以后精化。
- 调度器无需"理解" MLA/MoE 在算什么，只要依赖边正确，就能对任意 kernel 产生合法变体。

### 3.2 哪些是"按架构一次性做"（非按 kernel）

counter 语义、`m0` 规则、MFMA 强制 nop、寄存器区间解析——都是 gfx942 级别的，做一次所有 kernel 通用。

### 3.3 唯一按 kernel 变的：指令延迟表，且不需精确

> 我们在真机上测量，不需要 MLA 的静态性能模型。调度器只负责"生成多样的合法序"，性能由 HW 实测决定。**不必为每种 kernel 建 cost model**——这是泛化的核心。

### 3.4 优化范围：三区独立重排，指令不跨界

只优化 core loop 是**局部最优**——进 loop 前的 prologue（算地址、初始化 LDS、发射首批 load 填流水线）和出 loop 后的 epilogue（累加器转换、scale/bias、global_store、split-K 的 atomic 归约 + 信号量同步）也有大段指令，对性能有实质影响。**在 trip count 小的场景（split-K / 小 K / MLA decode）尤其致命**，因为 prologue/epilogue 各执行一次，占比很大。

因此把同一个区域内调度器**分别独立地作用于 prologue / core loop / epilogue 三个区域**：

- **指令绝不跨区域边界**——这是本方案安全的根本。不做 loop-invariant 上提、不做跨边界 sink、不做流水线深度/剥离这类跨区域宏变换（那些需要很重的合法性证明、易出错，**明确否决**）。
- 对纯重排（不改流水线深度、不改剥离）而言，三区**几乎解耦**：prologue 仍发射同一批 load，只是内部顺序变；loop 结构不变；epilogue 同理。丢失的耦合收益很小，却换来极大的简单性与隔离性（epilogue 的错排不会污染 loop 语义）。
- 实现上几乎免费：CFG 已经切出这三个区域（见 3.1），把调度器**多跑两次**即可，不引入新机制。

### 3.5 区域识别：基于 CFG 的 N 区切分（含 wave specialization）

"三区"是单循环 GEMM 的简化说法。通用做法是**基于 CFG 切成 N 个区域**，不写死 3 个：

- 建完整 CFG → 用支配树 / 回边（back-edge）找出**所有自然循环** → 每个循环体自成一区；循环之间、分支臂内的直线段也各自成区。
- **prologue / epilogue 只是其中两个直线段特例**。区域识别必须**基于 CFG**，不能用"入口到第一个 loop = prologue"这种位置假设——有分支后位置假设立即失效。
- 基本判据：**loop 区** = 含回边的块（`s_cbranch` 跳回更早的 label）；其余直线段按入口/出口/分支/汇合切块。

**wave specialization（warp specialization）**：有些 kernel 按 wave_id 分支，wave0/2 走 core_loop 块 A、wave1/3 走块 B（甚至 4 个 wave 各走不同块）——FlashAttention / MLA 的 producer-consumer、ping-pong 都这样。这**不是根本性问题**：每个 specialized loop 块只是又一个 loop 区，各自独立建 DAG、独立 gap-layout、独立重排，完全符合"区域独立"哲学，只是区域更多（甚至每个 wave-arm 可差异化调度）。但有两点必须处理对：

1. **barrier 是跨 wave 收敛点，规则更严**（见 `reorder_engine_api.md` §3）：
   - **barrier 数量绝对不可增删**——`s_barrier` 是整个 workgroup 的收敛点，各 wave 必须执行相同次数、一一配对，任何一臂多/少一个就**死锁**。
   - **LDS 读写不可跨 barrier 移动**——wave A 写 LDS、wave B 读 LDS 的依赖在单区域 DAG 里看不见（跨 wave、无寄存器依赖）。正确性靠"barrier 硬栅栏 + LDS 不跨 barrier + 保守 MEM 边"兜住，**不显式建模跨 wave 依赖**。
2. **waitcnt 重算要走 CFG 数据流**（见 `reorder_engine_api.md` §5.2）：有分支后 counter 状态要在分支处分叉、在汇合点取最坏情况 meet，单条线性扫描不再成立。

**优化目标选择**：多 loop 时引擎**暴露所有 loop 区**，由搜索 / AI 按 MFMA 密度或实测时间挑要优化哪个（甚至每个 wave-arm 分别调）。

### 3.6 边界 counter 契约（纯区域内方案里唯一的跨界考量）

即使指令不越界，**async counter（vmcnt / lgkmcnt）的计数是跨区域累积的**：prologue 发射的 load 是在 loop 里被 `s_waitcnt` 等到的。

- 在 prologue **内部**重排 load 发射顺序，会改变"进 loop 时哪些 load 还在飞行"。若 loop 首条 wait 是 `vmcnt(0)`（等全部），随意重排都安全；若是 `vmcnt(M>0)`（故意留几个在飞行做预取），则"留下的是哪几个数据"会随 prologue 内部顺序而变。
- 处理办法很轻：**把区域边界的 counter 状态当成一份"契约"**，调度器在区域出/入口**只读地**校验或重算边界 `s_waitcnt` 数值是否仍正确——**不搬移任何指令**。
- 一句话：**指令不跨界，但 counter 校验要看一眼邻区**。这只是"校验/重算 waitcnt 数值"，不是"移动代码"，依然轻、依然安全。

---

## 4. 灵活性设计：用"逐位置"表示替代全局旋钮

四种互补机制，从粗到细：

### 机制 A0：`distribute_evenly`（冷启动均匀铺设，最粗）

针对**完全未经手动调整**的 kernel（filler 全堆在一起、没有插进 MFMA 流），提供一个一键初始算子：

```
distribute_evenly(region, kind=ds_read, anchor_lo=N, anchor_hi=M)
  → 把该 region 内某类指令（如所有 ds_read）平均分配到第 N..M 个 MFMA 锚点之间的间隙
```

- 内部换算为机制 B 的 `set_gap_layout`（尽量等分，逐项过 `legal_window`，非法跳过），等价于"先给一个合理的均匀分布起点"。
- 价值：把"冷 kernel"一步带到一个非平凡的基线布局，再交给机制 A/B/C 细调，避免搜索从最差点起步。
- 接口见 `reorder_engine_api.md` §4。

### 机制 A：可调权重的 list scheduler（粗，搜索空间小）

调度器每步从"就绪指令"里挑 score 最高的：

```
score(instr) = w1·critical_path + w2·latency + w3·(-reg_pressure)
             + w4·is_load_hoist + w5·dist_to_consumer + ...
```

- 异构插入模式**自然涌现**（每个间隙插几条由依赖+权重决定，无需手指定）。
- 搜索维度仅是几个权重 `w`，泛化性好（这是真实编译器的做法）。

### 机制 B：逐位置 move-DSL（细，AI 在此发力）

AI 发"对某条具体指令做什么"的清单，固定逻辑校验+落地+重算 waitcnt：

```json
[
  {"op": "hoist", "target": "ds_read#a48", "after": "mfma#0"},
  {"op": "keep",  "gap": "mfma#1..#2"},
  {"op": "hoist", "target": ["ds_read#a56", "ds_read#a60", "ds_read#a64"], "after": "mfma#2"}
]
```

这就**精确表达了"1/0/3 异构插入"**：间隙1插1条、间隙2不动、间隙3插3条。AI 负责"想法"，固定逻辑负责"合法性 + waitcnt"。

### 机制 C：随机局部扰动（STOKE 式，补盲区）

- 候选表示为一个合法序，move = "把指令 i 挪到合法位置 j"（用 DAG 校验合法性）。
- 用模拟退火 / MCMC，以**实测性能**为目标接受/拒绝。
- 能逼近权重函数和 AI 都想不到的细粒度组合。

---

## 5. 稳定的指令寻址（泛化前提）

细粒度操作要能"指名道姓"，因此解析后给 loop 内每条指令一个**稳定 ID / 指纹**：

- `opcode + 关键操作数 + 第几次出现`，或
- 语义锚点（如"产出 `a[48:51]` 的那条 ds_read"）。

AI 和搜索都只对 ID 操作，与具体 kernel 无关。

---

## 6. gfx942 上必须正确建模的硬骨头

这些正是现有 `scripts/avo_20_rounds.py` 手工 patch 小心保持的约束：

- **`m0` 隐藏依赖**：`buffer_load_dword ... lds` 的目标 LDS 地址由前面的 `s_add_u32 m0, ...` 决定。重排必须让每个 `buffer_load→lds` 与对应 `m0` 设置**成对移动**。
- **MFMA 累加链**：连续 MFMA 累加到同一 `v[36:39]` 是严格 RAW 链，链内不可重排；不同累加组（`v[36:39]` vs `v[40:43]`）相互独立，可交错。
- **MFMA 强制 `s_nop` / 读写延迟**：某些 MFMA 后有 ISA 强制 NOP，调度器要正确插入。
- **counter 顺序语义**：vmcnt（VMEM）/ lgkmcnt（LDS/SMEM）按发射顺序计数，重排会改变"第 N 个 load"的含义，必须连带**重算所有相关 waitcnt**。

---

## 7. AI 角色的再定位

| 任务 | 由谁 |
|------|------|
| 提议 priority 权重 / 调整方向 | AI（粗调） |
| 发**逐位置 move 清单**（指名指令 ID） | AI（细调，表达异构方案） |
| 校验合法性 + 应用 + 跑 FixupPass 流水线（含 waitcnt 重算 / nop） | 固定逻辑 |
| 真机测量（三阶段：正确性/性能/counter dump） | testft 自带 harness |
| 读 perf counter 分析 + 把测量结果转成下一步洞察/方向 | analysis + AI |
| 兜底盲搜细粒度组合 | 固定逻辑（退火 / 进化） |

AI 始终**不发射 ASM 文本**，只发"对 ID 的操作"或"权重"。

---

## 8. 搜索可行性（细粒度会不会爆炸？）

- 纯"任意拓扑序"是阶乘级；真机每候选要 ms~s，预算约 10²~10⁴ 个。
- 分层控制规模：**权重搜索（低维、平滑）定大方向 → move / 退火（细粒度）做精修 → AI 用 profile 剪枝并提定向 move**。
- 三者叠加，既细又不盲。

**三区独立带来的搜索结构**（见 3.4）：现在是 3 个近似独立的子问题。

- **坐标下降**：固定其他两区，单独优化一区，轮流；因弱耦合而有效。
- **按时间占比分配预算**：大 K → loop 占绝大部分，预算砸 loop；小 K / split-K / MLA decode → prologue/epilogue 各自值得搜。
- **按区域归因收益**：harness 测整 kernel 时间，想看某区净效果可"只重排该区、冻结其余"再测 delta（A/B）。

---

## 9. 正确性兜底 + 三阶段真机评测（含 counter 反哺）

### 9.1 正确性兜底

- 无论多"legal-by-construction"，**永远保留编译 + 数值正确性测试**当最后防线（counter / m0 / 别名模型都可能不完美）。
- HW 测试前再加一道**静态合法性检查（DAG + counter 模拟）**过滤废候选，省测试时间。

### 9.2 三阶段真机评测（前序失败即短路）

候选 `.s` 编译通过后，按顺序跑三阶段，任一前序失败即短路、不浪费后续开销：

1. **正确性测试**：数值对比参考结果；不通过直接丢弃（不测性能）。
2. **性能测试**：读 kernel 执行时间 → 换算 TFLOPS。
3. **perf counter dump**：把显卡硬件 perf counter dump 到一个文件。

### 9.3 counter 分析反哺下一轮方向

第 3 步的 counter 文件交给 `analysis` 模块：解析（计数器语义由 `isa/Target` 提供，架构相关）→ 瓶颈分类（compute / memory / lds / latency / …）→ 产出**方向 hints**。该方向回流给搜索层 / agent，指引下一轮"优化哪个区、用哪类编辑算子（冷 kernel 先 `distribute_evenly`，再细调）、调哪些权重"。这就把"盲搜"变成"被硬件实测指标导航的定向搜索"。评测接口与 `EvalResult` 字段见 `reorder_engine_api.md` 与实现计划。

---

## 10. 落地顺序

1. **结构无关解析器**：CFG 切出 prologue / loop / epilogue 三区 + 逐区 DAG 构建 + 稳定指令 ID + waitcnt 静态校验器（含 3.6 的跨区边界 counter 校验；先只读，验证能正确解析 GEMM 和一个 MLA seed）。
2. **合法重排引擎** + 自动 waitcnt 重算 + nop 插入，接现有 `compile_workspace / evaluate_workspace`。先支持 move-DSL（机制 B），**先只跑 core loop 区**验证管线。
3. 把同一调度器**扩到 prologue / epilogue 两区**（几乎免费），三区独立重排，先用坐标下降 + 随机搜索验证收益。
4. 加 **list scheduler + 权重搜索**（机制 A）。
5. 加 **AI 元层**：发权重 + 逐位置 move + 分析（方案 C 混合）。
6. 视需要加 **退火 / 进化**（机制 C）做极致精修。

---

## 11. 一句话总括

**别用模板：用"结构无关的 DAG 区域调度器"解决泛化，用"逐位置 move-DSL + 可调权重 list scheduler"解决灵活性；范围覆盖 prologue / core loop / epilogue 三区，但各区独立重排、指令绝不跨界（唯一跨界动作只是只读校验/重算边界 waitcnt）；AI 发细粒度操作（针对稳定指令 ID），固定逻辑保合法 + 重算 waitcnt，真机测量打分。** 这样 GEMM / MLA / MoE 一视同仁，既能表达"间隙1插1条、间隙2不插、间隙3插3条"这类异构重排，又能在 split-K / 小 K / MLA decode 等 trip count 小的形状上吃到 loop 外的收益。
