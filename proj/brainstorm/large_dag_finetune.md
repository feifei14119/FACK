# 脑洞：大 DAG（如 prologue 入循环段）难以高效微调的解决办法

> **落地状态（见 `proj/large_dag_prologue_finetune.plan.md`）**：方向 1（可调子集 `tunable`）、
> 方向 8（`--compact` 紧凑视图 + 全量 dag 落 jsonl）、方向 2（fence 分段 `segments` + 段级 est_cycles）、
> 方向 3（`critical`：关键路径 top_k + dominant_wait）、方向 4（引擎自动种子候选 `suggest_orders`）
> **均已实现**（observe 只增只读字段，引擎裁决零改动）；方向 9（propose 降复杂度）见下篇同步落地；
> 方向 5/6（超级节点聚簇 / `cluster` 高层动作）暂缓（视收益再定）。

> 类型：brainstorm（头脑风暴 + 落地备选，非现状、非已落地设计）。
> 命题：对**入循环部分（prologue）**调优时，固定逻辑引擎为该区域生成的 **DAG 非常庞大**（实测 **426 个节点**），
> 导致 agent 难以高效做指令微调：上下文爆炸、推理慢、还诱导它构造全量 `--order`（触发 propose 的 O(n²) 塌方）。
> 本篇头脑风暴：可以有哪些解决 / 优化办法？
>
> 关联：`proj/brainstorm/anchorless_fullorder_propose_perf.md`（同一现象的 propose 性能侧；本篇是更本质的"搜索/
> 推理空间太大"侧）。本篇大量复用引擎**已有**能力：`search/list_scheduler.py`（fence 分段 `_segments` + 关键路径
> `_critical_path` + 加权 list 调度）、`agent/session.py` 的 `NodeView.movable/legal_window`、`est_share`。

---

## 0. 一句话结论

**"DAG 大"是表象，根因是"缺裁剪 + 缺聚焦 + 缺高层落点"三者叠加。** 解决思路不是让 agent 去啃 426 个节点，而是
**层层缩小它面对的空间**：先用 `est_share` 判断值不值得深入，再按 fence 分段定位最贵的小段，最后在该小段里由引擎
自动出候选、agent 只在"可调子集"上用高层动作微调。多数办法只改 observe 层 / 复用搜索层，引擎裁决零改动。

---

## 1. 为什么"庞大且难微调"（根因拆解）

prologue 在已优化 GEMM 里要做大量地址计算、descriptor 初始化、首批 global load / prefetch、LDS 写——本次实测
426 个节点。但"大"不等于"都要调"，真正的障碍是三件事叠加：

1. **绝大多数节点不可动**：地址计算是紧链（`s_add → s_lshl → … → buffer_load`），`legal_window` 往往只有 1，
   `movable=false`。真正可调的（vmem load、少量可推迟的 salu/valu）只有几十个。
2. **agent 面对的是全量 JSON**：observe 把 426 个 NodeView 全吐给模型，上下文爆炸、推理慢，还诱导它构造全量
   `--order`（即 `anchorless_fullorder_propose_perf.md` 记录的 O(n²) 塌方）。
3. **缺少"该调哪"的聚焦信号**：anchor-less 区没有 MFMA anchor 那样的天然落点，agent 只能盲搜。

> 结论：**"庞大"是表象，"缺裁剪 + 缺聚焦 + 缺高层落点"才是根因。** 下面所有办法都围绕这三点。

---

## 2. 解决方向（按性价比 / 复用现有能力排序）

### 方向 1：把"全量 DAG"裁成"可调子集"（最快见效，改 observe）

observe 已算出 `movable` 与 `legal_window`。只需额外返回一个 `tunable` 子集：满足
`movable==true` **且** `legal_window` 宽度 > 阈值 **且**（在关键路径上 **或** `bumps_counter ∈ {vm, lgkm}`，
即真正影响延迟掩盖的访存类）。

- 效果：agent 面对的从 426 → 几十；全量 dag 仍可按需展开，默认只喂可调子集。
- 代价：纯 observe 层加字段，引擎裁决零改动。**建议第一步就做。**

### 方向 2：按 fence 分段，一次只调一段（引擎已有 `_segments`）

指令本就**不能跨 fence**（barrier / waitcnt / exec 写 / 分支）移动，真正的优化单元是 **fence 围出的小段**。
`search/list_scheduler.py::_segments` 已实现该切分。

- 让 observe 把 prologue 再切成若干 fence-bounded 段，**每段报自己的 `est_cycles`**；agent 只挑代价最大的段做
  order，段内规模骤降到十几个。
- 等于把"426 元素的一维重排"变成"在最贵的小段里重排"。

### 方向 3：关键路径聚焦（引擎已有 `_critical_path`）

`list_scheduler.py::_critical_path` 已能算每个节点的关键路径长度。observe 可暴露 **top-K 关键路径节点** +
**当前主导 `est_cycles` 的那个 wait**（哪个 waitcnt 在等、哪些 load 喂它）。

- agent 直接拿到"瓶颈在哪、动哪几个最有用"的提示，而非盲找。
- 把现在 anchor-less 的 `direction`（噪声先验）升级成可操作的"候选清单"。

### 方向 4：引擎自动出种子候选，agent 只挑 / 微调（最大杠杆，复用 list scheduler）

最看好的一招：**别让 agent 从零构造全量 order**。引擎用现成 list scheduler（`critical_path` / `latency` 权重）
**自动生成 2~3 个合法重排候选**（如"关键路径优先""同计数器 async 聚簇优先"），连同各自 `est_cycles` 返回。

- agent 的任务从"构造 426 维序列"降级为"在 3 个候选里选一个，可能微调几个 iid"，组合负担骤降。
- `search/driver.py` 已在用 `listsched` 候选，等于把搜索层能力借给交互式 agent。

### 方向 5：把紧链聚簇成"超级节点"，按簇重排（降维）

把"地址准备链 + 它喂的那条 load"整体当成**一个可移动单元**。426 个细节指令 → 几十个簇。agent 在簇粒度重排
（"把这条 load 连同其地址准备整体前移"），既符合硬件直觉，又天然避免拆散紧链导致的非法 / 错误。

### 方向 6：用"高层动作词汇"替代全量线性 order（易用性）

给 anchor-less 区定义参数化变换：`hoist(load, k)`（前移 k 槽）、`cluster([loads])`（聚簇）、`sink(nops)`（下沉）。
agent 发少量带参动作，引擎翻译成合法 order。

- 比"列一串 iid"更贴近意图，参数空间小，也根除全量 order 的诱惑。
- 与 `anchorless_fullorder_propose_perf.md` 的"默认 partial order"是同一思路的形式化。

### 方向 7：用 est_share 做"值不值得调"的闸门（避免在 prologue 过度投入）

prologue **只跑一次**，loop 跑 `trip_count` 次。`est_share = trip_count * est_cycles` 通常显示 prologue 占比极小。

- 建议：observe 先报各区 `est_share`，**若 prologue 占比很低，只允许少量粗粒度动作（前移首批 load）**，不逐指令精调，
  把预算让给 loop。
- 这是"要不要调"层面的优化，往往比"怎么调"更省事。

### 方向 8：observe 负载压缩（上下文成本）

即使裁成子集，也别把每个 NodeView 的全字段塞给模型。给一个**紧凑视图**（只 iid / kind / window / bumps_counter /
关键邻居），全量留在 `.jsonl`。减少 token、加快推理。

### 方向 9：引擎 propose 复杂度 O(n²)→O(n)（治本，另一篇已记录）

即使子集变小，`propose_orders` 的 `list.index()` / 元素搬移仍应优化（见
`anchorless_fullorder_propose_perf.md` 方向 B：用 `iid→位置` dict 替换线性查找）。与本篇方向叠加最稳。

---

## 3. 两级分层调优（把上面串起来）

```
Level 0  est_share 闸门：prologue 占比够大才深入，否则只做粗动作            （方向 7）
   │
Level 1  fence 分段 + est_cycles：定位最贵的小段                          （方向 2 / 3）
   │
Level 2  在该小段内：引擎自动出 2~3 个 list-sched 候选                     （方向 4），
         agent 在可调子集上用高层动作微调                                 （方向 1 / 5 / 6）
```

每一级都缩小 agent 面对的空间，DAG 再大也只在最后一级、最贵的小段里展开。

---

## 4. 建议落地顺序

1. **方向 1（可调子集）+ 方向 8（紧凑视图）**：纯 observe 改动，立刻把 426 → 几十，最快缓解。
2. **方向 2 / 3（fence 分段 + 关键路径聚焦）**：复用 `list_scheduler.py` 的 `_segments` / `_critical_path`，
   中等成本、收益大。
3. **方向 4（引擎自动种子候选）**：最大杠杆，把搜索层能力接给交互式 agent。
4. **方向 7（est_share 闸门）** 贯穿始终；**方向 9** 作为引擎治本同步推进。

> 关联文档：`proj/brainstorm/anchorless_fullorder_propose_perf.md`（propose 性能侧）、
> `proj/brainstorm/nl_repl_frontend.md`（自然语言前门）、`proj/testcase_integration.md`（testcase 无关红线）。
> 涉及代码：`agent/session.py`（observe / NodeView / est_share）、`search/list_scheduler.py`
> （`_segments` / `_critical_path` / 加权调度）、`reorder/depgraph.py`（legal_window）、`reorder/editor.py`
> （propose_orders）。引擎裁决与现有 CLI 均可保持零改动、增量并存。
