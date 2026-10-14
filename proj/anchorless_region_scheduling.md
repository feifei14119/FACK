# 无锚点区调优：prologue / epilogue 的 DAG 重排 + 精确 waitcnt + shape 自适应目标

> 类型：设计草案（M9）
> 目标：让 Agent 能对**不含 MFMA 的区段**（典型为 prologue / epilogue，也包括循环极少次执行时的整核）
> 做「按依赖关系自由重排 + 精确 waitcnt 重算」，并用一套**对输入尺寸自适应**的目标函数驱动，
> 使该工程从「GEMM 大 K」泛化到任意算法 / 任意尺寸（含主循环只跑 1~2 次甚至不执行的 shape）。
> 守住全工程铁律：**Agent 只导航「试什么」，`legal_window` + `Verifier` + 真机数值裁决「行不行 / 多快」。**

---

## 1. 动机：两类区段，两套调优词汇

主循环（LOOP 区）的调优模型是「**以 MFMA 为锚的 slot 填充**」：把 v/s 访存指令上移/下移一个 MFMA
间隙（`anchors()` / `set_gap_layout` / `propose_layouts` / `distribute_evenly`）。这套词汇的前提是
**区内有 MFMA 锚点**。

但 prologue（进循环前的设置）与 epilogue（循环后的收尾/写回）**往往一条 MFMA 都没有**。此时：

- 没有锚点 → slot 模型整个失效（`anchors=[]`，`slots=[]`）。
- 优化目标变成：**把整段指令按依赖关系重新排序**（隐藏访存延迟、聚拢同类访存让一次等待覆盖多条、
  把独立计算填进 load→use 的空泡），**再精确计算每条 `s_waitcnt` 的值**。

这与 loop 区是**两套不同的观测/动作词汇**，但**复用同一套合法性与 waitcnt 基础设施**。

---

## 2. 关键判断：引擎「能做」，缺的是「Agent 词汇 + 目标函数」

读现有代码后的结论——底层能力基本就绪，不必另起炉灶：

1. **`RegionEditor` 不依赖 MFMA。** `anchors()`/`set_gap_layout`/`distribute_evenly` 只是 loop 区的特例；
   底层的 `DepGraph` + `legal_window` + `move_before/after` / `swap` + fence 分段，对**任何区**都成立
   （`reorder/editor.py`）。
2. **通用 DAG 调度器已存在且架构无关。** `search/list_scheduler.schedule(graph, order, fences, weights,
   kind_of)` 在 fence 分段内做合法构造的贪心调度，**不需要锚点**。
3. **非 loop 区的 waitcnt 已经算对。** `reorder/waitcnt.recompute_cfg` 整核穿 scoreboard，已处理
   「循环里发起、epilogue 才 drain」的跨区在飞访存（M8 已落地）。
4. **`build_candidate` 已支持选区。** `build_candidate(seed, {"kind":"listsched"/"compact"/"movedsl",
   "region":"prologue"})` 今天即可对 prologue/epilogue 重排 + `recompute_cfg` + Verifier（M8 已落地）。

> 因此真正缺的是三块：**(A) 无锚点区的 Agent 观测词汇；(B) 无锚点区的 Agent 动作 + 结构化反馈；
> (C) 一套对 shape 自适应的目标函数。**

---

## 3. 目标函数：测量优先、shape 自适应（本设计的核心决策）

### 3.1 一个被否决的错误假设

初版设计曾按**区类型**绑定目标：loop→真机 TFLOPS，prologue/epilogue→静态代价模型（理由是「尾段一次性
执行、贡献埋在噪声里」）。**这是错的**：「哪个区主导耗时」**不取决于区类型，而取决于运行时 trip count，
trip count 又取决于输入尺寸**。

- K 大、循环跑几百次 → loop 主导，尾段的 TFLOPS 信号埋在噪声下。
- **K 小、循环跑 1~2 次甚至 0 次 → prologue/epilogue 直接主导整核 TFLOPS**，真机就能拍板，无需代价模型。

该工程要适配各种算法 / 各种尺寸，**绝不能把「尾段贡献小」写死进架构**。

### 3.2 统一规则：真机裁决，代价模型仅作辅助

裁决永远是 **真机 TFLOPS + 正确性**，对所有区一视同仁（守住铁律）。静态代价模型（§5.3）降级为两个**辅助**角色：

1. **GPU-less 预筛**：提交真机前，先用 `est_cycles` 砍掉一眼变差的候选，省真机预算。
2. **噪声内的梯度 / 平局打破**：**仅当**候选 ΔTFLOPS 落在 baseline 噪声带内（真机分不出胜负）时，
   才用 `est_cycles` 当次级排序键。一旦 ΔTFLOPS 超过噪声门，**真机说了算，代价模型无权翻盘**。

regime 判定是**经验的**（「这次改动在**当前 shape** 上有没有撬动真机超过噪声」，复用现有
`noise_margin` / `perf_repeats`），**不是结构的**（不判断「这是不是 prologue」）。自动适配：

| 当前 shape | candidate ΔTFLOPS vs 噪声 | 实际生效信号 |
|---|---|---|
| 小 trip（尾段主导） | 超过噪声 | **真机 TFLOPS**（直接反映）|
| 大 trip（loop 主导，尾段贡献微小）| 落在噪声内 | 代价模型 `est_cycles` 提供梯度，避免空转 |

### 3.3 shape-aware「该调哪个区」先验

既然 trip count 决定区权重，就显式算出来，指导 Agent 把预算花在**当前 shape 真正主导耗时的区**：

```
est_share(region) ≈ trip_count(region) * est_cycles(region)
   # loop 区 trip_count = 实际循环次数(来自 harness --loop/--k 或运行时探测)
   # prologue/epilogue trip_count = 1; 不执行的区 = 0
```

把 `est_share` 放进 `observe` 的 `regions[]`，SDK prompt 让 Agent「先看哪个区占耗时大头，再决定调哪块」——
**选区决策随尺寸自适应**：大 K 主攻 loop，小 K 自动转向尾段且真机可验证。

---

## 4. 引擎接口设计（固定逻辑侧）

### 4.1 观测：无锚点区的 DAG 视图

当所选区**无 MFMA 锚点**时，`observe` 自动从「slot 视图」切到「DAG 视图」。要让 Agent 能对 waitcnt
推理，关键是**把计数器语义一并暴露**：

```python
@dataclass
class NodeView:
    iid: int
    kind: str
    pos: int                       # 当前顺序中的位置
    legal_window: (int, int)       # 拓扑最早/最晚可放位置(来自 DepGraph)
    preds: [(iid, dist)]           # 依赖前驱 + 最小距离(dist>1 = 延迟边)
    succs: [(iid, dist)]
    is_fence: bool
    # —— 让 Agent 看懂 waitcnt 的关键(来自 Target.counter_model) ——
    bumps_counter: str | None      # 这条指令增加哪个计数器(vmcnt/lgkmcnt/vscnt/expcnt)
    waits_on: {counter: target}    # 若它本身触发等待, 等到几

@dataclass
class WaitcntPreview:              # 当前顺序下 recompute 出来的等待 + 代价
    waits: [{at_iid, counter, target}]
    cost: RegionCost               # 见 §5.3
```

数据来源全为现成：`preds/succs/dist/legal_window/fences` ← `DepGraph`；`bumps_counter/waits_on/
WaitcntPreview` ← `waitcnt` 模拟器只读导出。`Observation` 增加可选字段 `dag`/`waitcnt_preview`，
与现有 `slots/fillers` 并列；`regions[]` 每项增 `est_share`。

### 4.2 动作：无锚点区的「线性顺序意图」

slot 区动作是 `propose_layouts({slot:[filler]})`；无锚点区的自然对应是**线性顺序意图**，给三种粒度
（从粗到细，复用现有三机制）：

| 机制 | Agent 动作 | 复用 | 适用 |
|---|---|---|---|
| A 权重 | 给一组 `Weights` | `list_scheduler.schedule` ✅已有 | 整体重排，一发入魂、最稳 |
| B 移动 | 在稳定 handle 上 `hoist/sink/before/after` | `search/movedsl` ✅已有 | 外科手术式，只挪某几条 |
| C 全序 | 提交一个(部分/完整)iid 线性序 | **新增 `propose_orders`** | 表达力最强，Agent 直接「排好队」 |

新增 C 是 `propose_layouts` 的无锚点版，签名对称、同样 try/revert 不污染：

```python
def propose_orders(self, candidates: List[List[int]], strict=False) -> List[OrderReport]:
    """每个候选是一个(部分或完整的)iid 线性序意图。引擎按序贪心落位:
       每条过 legal_window + fence; 落不进的记 SkipReason + window + bound_iid;
       未提及的指令保持相对序填空。返回 placed / skipped / legal + RegionCost。"""
```

Agent 拿 `OrderReport` 看哪条因什么(RAW/FENCE/latency)排不到想要位置 → 改下一版。
合法性永远引擎裁决。

> `span_editor`（`reorder/editor.py`）已能把 prologue↔epilogue（同执行次数的非 loop 区）合成一个可跨界
> 重排的 span，并自动把 loop 体首尾钉成 fence——「跨尾段协同重排」有现成承载（Phase 4）。

### 4.3 代价模型 `reorder/cost.py`（新增，架构无关）

跑在 `Target` 的 `CounterModel` + 延迟边上，复用 waitcnt scoreboard 模拟，**无需 GPU**：

```python
@dataclass
class RegionCost:
    issue_cycles: int    # 区内指令数 * 各 kind 粗略发射周期
    wait_stalls: int     # 沿顺序模拟 scoreboard: 每条 s_waitcnt 实际 drain 深度之和
    n_waits: int         # 插入的 s_waitcnt 条数
    est_cycles: int      # issue + 等待空泡累加(主排序键, 给 §3.2 预筛/平局)

def estimate(program, target, region) -> RegionCost: ...
```

### 4.4 waitcnt 精确性：已解决，对 Agent 透明

Agent **永远不写 waitcnt**。任何重排提交后：非 loop 区走 `recompute_cfg` 整核穿 scoreboard，loop 区走
loop-aware 重算。Agent 只管顺序；正确性由 `recompute_cfg + Verifier + 真机` 三层兜底。观测里只是把
「重排后 waitcnt 会变成什么」预览给 Agent（§4.1 `WaitcntPreview`）。

---

## 5. Agent 闭环

`AgentSession` / CLI / SDK prompt 增加「按区自适应词汇」：

1. `observe --region epilogue` → 引擎发现该区**无 MFMA 锚点** → 自动返回 **DAG 视图 + WaitcntPreview +
   RegionCost**（而非 slots/fillers）；`regions[]` 带 `est_share`。
2. Agent 读 DAG + 当前 `est_cycles` + waitcnt，形成假设（如「把两条独立 `s_load` 提到 `ds_read` 前成组，
   使一次 `lgkmcnt` 等待覆盖两条」）。
3. `propose`（机制 A/B/C 之一）→ 引擎回 `placed/skipped + 新 RegionCost`。Agent 看 `est_cycles` 降没降
   （快、无 GPU）即可迭代。
4. `commit_and_eval` → `recompute_cfg` + 真机：按 §3.2 规则裁决（ΔTFLOPS 超噪声→真机说了算；噪声内→
   看 `est_cycles`）；正确性恒为门。
5. M7 知识层照常沉淀：scope 加 `region_kind: prologue/epilogue`，归纳「什么形态尾段、哪种重排稳定降
   `est_cycles` / 真机」。

SDK prompt 按 `region` 切换说明：loop 区讲 slot/anchor 填充；prologue/epilogue 区讲「读 DAG + waitcnt
预览，用权重/移动/全序重排，目标降区内 `est_cycles`，且别让整核数值错/变慢」。

---

## 6. 不变量 / 铁律（不得违反）

- Agent 只发「对稳定 iid 的结构化意图」，**不写 waitcnt、不改 ASM 文本**。
- 合法性：每步过 `legal_window` + fence；最终 `Verifier`（DepGraph + counter 模拟 + 不越界 + Target 不变式）。
- 性能：真机 TFLOPS + 正确性是**唯一裁决**；代价模型仅预筛 + 噪声内平局，**永不翻盘已测出的真机回归**。
- 错误的 Agent 决策只浪费预算，**绝不产坏 kernel**。

---

## 7. 落地分期（按杠杆 / 风险递增）

> 状态（进度见 `steps/M9-anchorless-region.md`，全套 223 passed）：Phase 1–3 **已实现**，Phase 4 暂缓。

- **Phase 1（最小闭环，零新核心代码）✅**：`observe` 对无锚点区暴露 **DAG 视图**（复用 `DepGraph`）；Agent
  直接用**已有的** `listsched`/`movedsl` spec（带 `region`）跑 `commit_and_eval`。离线已验证 epilogue/
  prologue 重排过 Verifier；**真机首点（gfx942, k=256, 2026-06-18）**：小 K 下 prologue ~+1.05% /
  epilogue ~+0.31% 真机可量出正向收益，印证 §3.2 的 shape 自适应假设（详见 `steps/M9-anchorless-region.md`）。
- **Phase 2（shape 自适应目标）✅**：`reorder/cost.py`（`RegionCost`/`estimate`）+ `waitcnt_preview`
  进 observe；`_verdict` 实现 §3.2 规则（真机优先、噪声内用 `est_cycles`）+ `regions[].est_share`。
- **Phase 3（表达力）✅**：`editor.propose_orders`（全序意图）+ `build_candidate` `order` kind +
  CLI `--order` + SDK prompt 按区词汇切换 + M7 scope 加 `region`。
- **Phase 4（跨尾段协同，可选）暂缓**：用 `span_editor` 暴露 prologue↔epilogue 跨界重排，视前三期收益再定。

---

## 8. 涉及文件一览

| 文件 | 改动 |
|---|---|
| `reorder/regions.py` | 已有 `select_region`/`region_summaries`（M8）；Phase 2 加 `est_share` 计算 |
| `reorder/cost.py` | **新增**（Phase 2）：`RegionCost` + `estimate` |
| `reorder/editor.py` | Phase 3 加 `propose_orders` + `OrderReport`（`propose_layouts` 的无锚点版）|
| `agent/session.py` | `observe` 按区切 DAG 视图 + `WaitcntPreview` + `est_share`；commit 走 §3.2 裁决 |
| `search/driver.py` | `build_candidate` 已支持 `region`（M8）；Phase 2 加 `est_cycles` 预筛/平局 |
| `tools/agent_session.py` / `tools/sdk/tune.mjs` | 按区切换 observe 词汇 + prompt 说明 |
| `tests/` | DAG observe / `propose_orders` / cost 估算 / 无锚点区 build 合法 / shape 自适应裁决 |

> 设计上承接 `core_loop_scheduler_design.md`（三区独立重排）与 `reorder_engine_api.md`（waitcnt 重算）；
> 接口面承接 `if/ai_interface.md` §3.4.2c–d（分区调优 / SDK 驱动）。
