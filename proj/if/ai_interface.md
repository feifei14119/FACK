# 固定逻辑提供给 AI 的接口（指令重排引擎）

> 设计契约：**固定逻辑只保证两件事**——(1) 可信的「逐条移动」接口；(2) 移动后**正确重算 waitcnt / barrier / nop**。
> 优化方向与策略由 AI 决定，策略可以非常激进；**结果错误的 kernel 由验证逻辑 + 真机数值剔除**。
> 固定逻辑面向各种 kernel / 算法，不追求全覆盖最优。

接口分 6 层：解析 → 分析/依赖模型 → 重排（移动原语）→ 重算 → 验证 → 真机评测/方向。

---

## 1. 无损解析 / 还原

```python
from reorder import parser, emitter
prog = parser.parse(text)            # text -> Program（保留原文，可逐字还原）
prog = parser.parse_file(path)
text = emitter.emit(prog)            # Program -> text
```

- `Program.instr_lines()` / `label_lines()`：取指令 / 标号行。
- 每条 `Line` 有稳定身份 `idx`（= 源文件行号），所有移动/依赖都以 `idx`（下文称 `iid`）为准，与当前位置无关。

---

## 2. 分析 + 依赖模型（只读：回答「能不能动、动到哪合法」）

### 2.1 region 分析
```python
from reorder import regions
a    = regions.analyze(prog, target)                 # RegionAnalysis
loop = [r for r in a.regions if r.kind.value == "loop"][0]
lines = regions.region_instr_lines(prog, loop)       # 该 region 的指令行
```

### 2.2 依赖图与合法窗口
依赖图可由 `DepGraph.build(lines, target)` 构造，或直接用 `editor.graph`。

| 接口 | 含义 |
|---|---|
| `graph.legal_window(iid) -> (lo, hi)` | 该值令可合法占据的位置区间（**已综合** RAW/WAR/WAW、隐式 scc/m0、fence、**MFMA 最小间距**） |
| `graph.is_movable(iid) -> bool` | 窗口是否 > 1（有移动空间） |
| `graph.preds(iid)` / `graph.succs(iid)` | 直接依赖前驱 / 后继 |
| `graph.is_fence(iid)` | 是否调度栅栏（barrier / **exec 写（含 `v_cmpx`）** / 分支 / 现存 waitcnt） |
| `graph.dist(a, b) -> int` | 边 a→b 要求的最小位置间距（普通顺序边=1；**MFMA 写→非 MFMA 读** = 回写延迟） |
| `graph.latency_edges() -> [(a,b,dist)]` | 所有 dist>1 的延迟边 |
| `graph.is_order_legal(order) -> bool` | 整个顺序是否满足全部依赖 + fence 段 + 间距 |

> **隐式寄存器**也已建模（无需 AI 关心）：scc、m0、以及 vcc 的 carry-out/in（`v_add_co`/`v_addc`/`v_cndmask`…）。
> 这些隐式 def/use 都进了 RAW/WAR/WAW，因此合法窗口对它们一并收敛。
>
> **MFMA 回写延迟从 seed 自动标定**（`isa/gfx942/edges.py` 两阶段）：seed 已知正确，故取它自身**每个 MFMA opcode
> 最紧的「写→非 MFMA 读」间距**作为延迟（真机 kernel 自动还原 `16x16x32 == 3`，与 MI308X 实测一致）。
> `classify.py::MFMA_READ_LATENCY` 仅作「该 opcode 在 seed 中无消费者」时的兜底。合法窗口已含该约束，
> 因此**重排不会把 MFMA 的消费者拉进延迟窗口**，且 **seed 本身永远合法**。

### 2.3 只读现场：自定策略的「事实地图」（可完全不依赖 `direction`/hint）

> §6 的 `direction`/`hints` 只是固定逻辑顺手给的**性能启发（可错、可无视）**。
> AI 如果有自己的硬件知识库，**完全可以忽略 hint**，只用下面这些**精确、可信的只读事实**，
> 自己读「每条值令的类型 + 当前间隔」并自定布局，再用 §3 的移动原语下发。

| 想知道什么 | 接口 | 说明 |
|---|---|---|
| 当前顺序 | `ed.order` | iid 列表（稳定身份） |
| **每条值令的类型** | `ed.kind_of(iid) -> Kind` | mfma / vmem_load / ds_read / valu / salu / set_m0 … |
| 间隔锚点 | `ed.anchors(Kind.MFMA)` | 把 loop 切成 MFMA slot 的边界 |
| 必须同移的块 | `ed.unit(iid)` | m0-bundle 等 |
| **单条可动区间** | `graph.legal_window(iid) -> (lo,hi)` / `is_movable` | 能合法占据的位置 |
| 依赖前后驱 | `graph.preds/succs(iid)` | 直接依赖 |
| **两条最小间距** | `graph.dist(a,b)` | MFMA 写→读=回写延迟，普通边=1 |
| 所有延迟边 | `graph.latency_edges() -> [(a,b,dist)]` | 全部 dist>1 |
| 是否栅栏 | `graph.is_fence(iid)` | barrier / exec 写 / 分支 / 现存 waitcnt |
| 顺序整体合法性 | `graph.is_order_legal(order)` | 校验自拟顺序 |

**示例：AI 自己读「逐 slot 当前布局」（不碰 direction）**

```python
from reorder.model import Kind
mfma = ed.anchors(Kind.MFMA)
pos  = {i: k for k, i in enumerate(ed.order)}
for g in range(len(mfma) - 1):
    lo, hi = pos[mfma[g]], pos[mfma[g + 1]]
    fillers = [ed.kind_of(ed.order[p]) for p in range(lo + 1, hi)]   # 这个 slot 里塞了什么
    # 真实 gemm loop 实测即异构：slot0={set_m0,vmem_load}, slot1={ds_read}, slot3={valu,valu,ds_read}...
```

> 即：`direction`/hint 是“导航建议”，本节这些只读接口是“地图与路况”。AI 可丢掉建议、自己看地图开车——
> 且无论怎么开都**撞不了**：非法移动被 `legal_window` 拒绝（§3.2），错 kernel 由 `Verifier` + 真机数值剔除（§5）。

---

## 3. 重排引擎 —「逐条移动」接口（`RegionEditor`）

```python
from reorder.editor import RegionEditor
ed = RegionEditor(prog, target, region, treat_waitcnt_as_fence=False)
```
- `treat_waitcnt_as_fence=False`：把现存 `s_waitcnt` 当可跨越（因为之后会重算 wait）。
  手调 kernel 想保留原 wait 当栅栏时用 `True`。
- **区通用**：`region` 传 prologue / epilogue / loop 任一都可，`compact_kind` 等接口在**非 loop 区一样工作**
  （已真机验证：prologue `compact_kind(VMEM_LOAD)` + `recompute_cfg` → k=512/2048/4096 **60/60 PASS**）。

#### 跨区移动（`span_editor`）
```python
from reorder.editor import span_editor
ed = span_editor(prog, target, [prologue, loop, epilogue], treat_waitcnt_as_fence=False)
```
在连续 span 上建编辑器，并把 span 内**每个 loop 体的首/尾指令钉成栅栏**，从而只允许在**同执行次数**的相邻区之间安全移动。
> ⚠️ 把 prologue 预取 **sink 进 loop 体**会改变其执行次数（loop 跑 N 次），属**软件流水**变换（需为第 0 次迭代留补偿副本/轮转稳态），
> **纯序模型无法表达**，`span_editor` 会被 loop 栅栏挡住——这是有意为之的安全边界，不是缺陷。

### 3.1 看现场
| 接口 | 含义 |
|---|---|
| `ed.order` | 当前指令顺序（iid 列表） |
| `ed.anchors(Kind.MFMA)` | 按当前顺序取某类值令的 iid（默认 MFMA，作为间隔锚点） |
| `ed.kind_of(iid)` | 该值令的语义类别（`Kind`） |
| `ed.unit(iid)` | 必须随它一起移动的块（它的 m0-bundle，或它自己） |

### 3.2 移动原语（核心）
| 接口 | 含义 |
|---|---|
| `ed.move_after(iid, anchor_iid, strict=False) -> Diff` | 把 iid（及其 unit）移到 anchor 之后 |
| `ed.move_before(iid, anchor_iid, strict=False) -> Diff` | 移到 anchor 之前 |
| `ed.swap(a, b)` | 交换两条（两侧都合法才生效） |
| `ed.compact_kind(kind, earliest=True) -> Diff` | 把某类值令整体滑到合法窗口端点（hoist/sink），保相对顺序；末尾自带**有界 distance-repair** |
| `ed.set_gap_layout(anchors, layout)` | 往 MFMA 间隔里批量摆放填充值令 |
| `ed.distribute_evenly(kind, lo, hi)` | 把某类均匀铺进 MFMA 间隔（**仅用于冷 kernel 自举**，非优化等级） |
| `ed.lock_bundle(iids)` | 额外把若干值令粘成一个整体移动 |

> **正确性保证**：所有移动都按合法窗口校验。
> - `strict=True`：非法移动抛 `IllegalMove`。
> - `strict=False`（推荐）：非法则**跳过不改动**，记入 `Diff.skipped`，`Diff.note` 给出合法窗口 `[lo,hi]`。
>
> 即 AI 只需选「哪条 + 放到哪」，**绝不会因接口产出违反依赖的 kernel**。

### 3.3 Diff / 回滚 / 提交
```python
d.changed     # 是否真的改变了顺序
d.skipped     # 被拒绝（越界）的 iid 列表
d.note        # 文字说明（含合法窗口）
ed.revert(d)  # 撤销一次操作
ed.is_legal() # 当前顺序整体是否合法
ed.materialize()   # 把当前顺序写回 program（就地）
```

---

## 3.4 AI 指导逐 slot 精细布局（结构化候选提交 + 原因码反馈）

> 目标：AI 不止做 tile/pipeline 决策，更能对**值令做极致精细化的逐 slot 调整**——
> 例如 core loop 有 5 条 MFMA + 4 条访存值令，固定搜索给出「每个间隙各 1 条」的均匀基线后，
> AI 依据硬件知识库判断「slot0 之后那条 MFMA 占用长、带宽有富余，可吞 2 条 load」，于是想试
> `{slot0:2, slot1:1, slot2:1}` 或 `{slot0:2, slot1:0, slot2:2}` 这类**非均匀**布局。

### 3.4.1 底层原语已就绪：`set_gap_layout`（逐 slot 异构摆放）

`set_gap_layout` 本身就支持逐 slot 异构计数（不止均匀分配），`distribute_evenly` 只是它的「等分」特例：

```python
ed   = RegionEditor(prog, target, loop, treat_waitcnt_as_fence=False)
mfma  = ed.anchors(Kind.MFMA)                                    # 5 个 slot 边界
loads = [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD] # 4 条访存

# AI 意图：slot0 放 2 条、slot1 放 1 条、slot2 放 1 条
layout = {0: [loads[0], loads[1]], 1: [loads[2]], 2: [loads[3]]}
d = ed.set_gap_layout(mfma, layout, strict=False)
d.changed     # True；结果序：MFMA LD LD  MFMA LD  MFMA LD  MFMA  MFMA
d.skipped     # 放不进去的 filler iid（越界即跳过，不污染顺序）
```

> 已真机验证：均匀基线 / `{slot0:2,1,1,0}` / `{slot0:2,0,2}` 三种布局对真实 GEMM core loop 均 `is_legal()==True`。

### 3.4.2 结构化候选提交（M6 封装：`propose_layouts`）

`set_gap_layout` 一次只摆一个布局、失败只回「一串 iid + 文字窗口」。M6 在其上加一层让 AI **批量提交意图**并拿到**结构化失败原因**以迭代：

```python
reports = ed.propose_layouts(anchors=mfma, candidates=[
    {0: [loads[0], loads[1]], 1: [loads[2]], 2: [loads[3]]},   # 方案一
    {0: [loads[0], loads[1]],               2: [loads[2], loads[3]]},  # 方案二
])
# 引擎对每个候选 try-摆放 → 校验 → revert，互不污染，返回每候选一份 LayoutReport
```

```python
class SkipReason(Enum):
    LDS_ROUNDTRIP   # ds_read 要等填它那条 band 的 buffer...lds
    MFMA_LATENCY    # 违反 MFMA 写->读最小间距窗口
    FENCE_BLOCKED   # 目标间隙与当前位置间隔着 barrier/exec 写/分支/waitcnt 栅栏
    RAW / WAR / WAW # 数据依赖
    M0_BUNDLE       # m0-bundle 整体性要求
    WINDOW_EMPTY    # 合法窗口塌缩（lo>hi）
    SLOT_OOR        # slot 序号 >= MFMA 锚点数

@dataclass
class Placement:                  # 单条 filler 的落位结果
    iid: int; slot: int; ok: bool
    reason: SkipReason | None     # 失败原因码（ok=False 时给出）
    window: tuple[int, int]       # 合法窗口 [lo, hi]
    bound_iid: int | None         # 卡住它的那条指令（pred/succ/fence）

@dataclass
class LayoutReport:
    layout: dict[int, list[int]]
    placed:  list[Placement]      # ok=True
    skipped: list[Placement]      # ok=False，带 reason + window + bound_iid
    legal:   bool                 # 全部落位后整体合法性
```

- **原因码怎么来**：复用 `_move_unit_to` 的失败路径——目标 index `k<lo` 看下界绑定者
  （pred 的 `graph.dist`>1 ⇒ `MFMA_LATENCY`；fence-left ⇒ `FENCE_BLOCKED`；否则 RAW），
  `k>hi` 看上界绑定者（succ / fence-right）。即把现有 `note` 里的 `[lo,hi]` 升级成「**谁、因什么约束**挡住了它」。

### 3.4.2b LLM 决策面：`AgentSession`（M7，把上面闭环做成可调用对象）

`propose_layouts` 是「校验一批 layout」的原语；`agent/session.py::AgentSession` 在其上把
`ai_interface §3.4.3` 的闭环封成 LLM（Cursor agent 或任意大模型）**逐轮驱动**的三个方法——
**LLM 只导航（读现场 / 提 layout），合法性与性能仍由引擎 + Verifier + 真机裁决**：

```python
from agent.session import AgentSession
sess = AgentSession(seed_src, evaluator, context={...}, protect_prefetch=True)

obs  = sess.observe()                       # 1) 读「事实地图」（JSON-able，喂给 LLM）
rep  = sess.propose([{0:[ld0,ld1], 2:[ld2]}])  # 2) 试布局（非提交，回 SkipReason）
res  = sess.commit_and_eval({0:[ld0,ld1], 2:[ld2]})  # 3) 真机度量（门控 + 记日志）
```

- **observe → `Observation`**（`to_dict()` 可序列化）：`anchors`（MFMA 锚点）、逐 slot 当前布局
  `slots`、可动填充 `fillers`(每条带 `kind`/`legal_window`/`movable`/**`is_prefetch`**)、`latency_edges`、
  `prefetch_loads`（保护集，见 §4.3）、`direction`（投票先验）、`prior_plan`（知识层播种）。这就是 §2.3 的事实地图整体打包。
- **propose → `ProposeOutcome[]`**：每个候选回 `placed` / `skipped(reason+window+bound_iid)` / `legal`，**不改 seed**。
- **commit_and_eval → `CommitResult`**：走 `build_candidate({"kind":"layout"})` 同一门控管线（重算+Verifier+真机中位数+噪声门），
  并把决策（`decided_by:"llm_agent"`）追加进 `experiments.log`，让非确定性的 LLM 决策**可追溯**（设计 §4）。

CLI 桥（外部大模型逐轮调用）：`python3.8 tools/agent_session.py {observe|propose|eval} <seed.s> [--layout '{...}']`。
`observe`/`propose` 不需 GPU。真机 gemm 实测：observe 出 96 锚点 / 355 可动填充 / 18 条受保护预取；
propose 把预取 load 下沉即回 `prefetch_protected` + 跨迭代消费者 iid。

> 注：按设计 §4，LLM **不进固定逻辑内层循环**（内层保持可复现）；它在**元层**逐轮 observe→propose→commit。
> 每候选塞一次 LLM-API 的「全自动在环」是可选的上层 driver，再加即可，不改本决策面。

### 3.4.2c 分区独立调优（M8：循环前 / 循环体 / 循环结束）

kernel 被 `regions.analyze` 静态切成 **PROLOGUE**（进循环前）、一个或多个 **LOOP**（core loop 主循环体）、
可选 **INTER**（多循环之间）、**EPILOGUE**（循环结束后）。LLM 可对**每个区域分别调优**：

- `reorder/regions.select_region(regions, sel)` 选区：`"loop"`（默认）/ `"prologue"` / `"epilogue"` /
  `"inter"` / `"body"`，或带序号 `"loop#1"`（第 2 个循环），或整数下标；`region_summaries` 列出每区
  `index/kind/行号区间/header/指令数`。
- `AgentSession(seed, ev, region="epilogue")` 与 `build_candidate(seed, {... "region":"epilogue"})`
  按所选区构建 `RegionEditor`；`observe` 额外回 `regions`（全部区）+ `region`（当前选中 kind）。
- **正确性关键**：改 **loop** 区用 loop-aware `waitcnt.recompute(region=)`；改**非循环区**自动改用整核
  `waitcnt.recompute_cfg` 跨区穿 scoreboard，保证「循环内发起、epilogue 才 drain」的异步访存 waitcnt 正确。
  baseline 与候选走**同一**重算路径，对比公平。
- CLI：三个子命令均支持 `--region SEL`；`observe` 永远打印全部 `regions` + 选中 `region`。真机 gemm 实测三区：
  `prologue` 426 指令 / `loop` 451 指令(96 MFMA) / `epilogue` 140 指令。

### 3.4.2d SDK 驱动的程序化 Cursor agent（M8）

`tools/sdk/tune.mjs`（`@cursor/sdk`）起一个**本地** Cursor agent（`cwd=testft`），由它用 shell 工具调
`python3.8 tools/agent_session.py {observe|propose|eval}` 自己跑 observe→propose→eval 闭环——即「用真正的
Cursor agent，但程序化/无人值守」。`--region` 钉死单区（默认 `loop`）或 `all/auto` 放开自由选区；
`--rounds/--k/--loop/--model`；`--transcript/--results` 双开关把每轮提示词+输出+工具 I/O 与每轮性能行
（含 region 列）落盘。根目录 `tune_quick.sh` 是「2 轮 / 不存提示词 / 存结果」的快捷封装，默认主循环区。
key 走 env `CURSOR_API_KEY` 或 `cursor.config.json`(0600+gitignore)。详见 `proj/sdk_agent_integration.md`
与 `tools/sdk/README.md`。

### 3.4.3 与固定搜索的分工 / 闭环

- **AI 出「逐 slot 布局意图」**（来自 `direction` + 硬件知识库的语义判断）；
  **固定逻辑负责合法落位 + waitcnt 重算 + 真机度量**，并把放不进去的值令连同原因码回报。
- 两者**复用同一个 `set_gap_layout` 原语**：固定搜索探「均匀/移项」可枚举空间，AI 接管「非均匀/靠语义」的点位，互不覆盖、天然互补。
- 闭环：

```
direction.bottleneck
   → AI 生成若干非均匀 candidates
   → propose_layouts 批量校验（得 placed / skipped+SkipReason）
   → 选合法者 materialize → recompute_cfg → Verifier → evaluate(with_counters)
   → 比较 TFLOPS / 新 direction；被 skip 的候选带原因码回流
   → AI 调整下一版意图（M7 把「何种 direction/指令形态下哪种非均匀布局有效」沉淀进知识库）
```

---

## 4. 移动后正确重算（waitcnt / barrier / nop）

```python
from reorder import waitcnt
waitcnt.recompute(prog, target, region=loop, opt_level=1)   # 只重算单区（loop 自动 fixpoint）
waitcnt.recompute_cfg(prog, target, opt_level=1)            # 整程多区重算（prologue+loop+epilogue）
```
- **`recompute`**：只重算传入的 region，其余区保留原 wait。改过 loop 用它最省。
- **`recompute_cfg`**：从零重算**整个 kernel**，用一块 scoreboard 按程序序穿过各区并**跨区携带在飞 counter 状态**
  （prologue 线性 → loop fixpoint → epilogue 用 loop 出口状态作入口）。**改了非 loop 区、或同时改多区时必须用它**
  ——否则孤立重算 epilogue 看不到 loop 内发出的 lds-load，会欠同步。已真机验证 **60/60 PASS**。
- `opt_level`（见 `reorder.optlevel`）控制 barrier LDS-release 栅栏激进度：L0 排空全部 lds-load（最稳）；L1+ 只排空本段读到的 band（默认）。
- MFMA 延迟兜底（当 seed 自身间距过紧时补 `s_nop`）：
```python
from isa.gfx942.passes import ForcedNopPass
ForcedNopPass().run(prog, target)
```
- 一把梭（推荐）：
```python
from reorder.passes import PassPipeline
pipe = PassPipeline(target.fixup_pipeline(region=loop, recompute_waitcnt=True, opt_level=1))
pipe.run(prog, target)
```

---

## 5. 验证（剔除错误）

```python
from reorder.verifier import Verifier
res = Verifier(target, reference=orig_prog,
               analysis=regions.analyze(prog, target)).verify(prog)
res.ok           # bool
res.violations   # 文字列表（依赖顺序 / waitcnt 充分性 / LDS-barrier / 不变量）
```
静态 verify 通过后，最终仍以**真机数值结果**为准（cycle 级延迟等少数硬件冒险不在纯顺序模型内，由真机兜底）。

---

## 6. 真机评测 + 方向（AI 决定下一步的输入）

三阶段评测（正确性 → 性能 → ATT 逐指令跟踪）封装在 `harness/evaluator.py`，并由 `tools/eval_candidate.py` 一条命令跑通：

```bash
python3.8 tools/eval_candidate.py cand.s --k 2048 --loop 20 --counters [--kernel NAME]
```
```python
from harness.evaluator import GpuTestcaseEvaluator
from isa.gfx942.target import Gfx942Target
ev  = GpuTestcaseEvaluator("testcase", target=Gfx942Target(), total_loop=20, k=2048)
res = ev.evaluate("cand.s", with_counters=True)     # EvalResult
res.correct        # bool（#TEST PASSED）
res.tflops         # 性能
res.direction      # {"bottleneck","share","hints","stats","total_stall",
                   #  "informative_stall","none_fraction"} —— 下一步【先验】
```

- `res.direction` 由 ATT 逐指令 stall 按维度聚合后分类得到（`analysis/bottleneck.py::classify`）：
  - `bottleneck`：`lds` / `memory` / `scalar` / `scalar_mem` / `compute` / `flow` / `latency`（弥散无热点）/ `none`；
  - `share`：top 维度占【信息维度】stall 的比例（**剔除 `none`**，见下方 ⚠️）；`< 40%` → `latency`；
  - `hints`：对应的具体算子建议；`stats`：各维度 stall；`none_fraction`：`none` 占总 stall 的比例（透明）。
- **kernel 无关**：ATT 采集自动检测候选 `.s` 的 kernel 符号（`target.kernel_symbols`，`.amdhsa_kernel`）并注入过滤，不写死 gemm；多 kernel 对象用 `--kernel` 指定。
- ATT 文件的读取/解析技术细节见 `proj/att_parsing_and_ai_usage.md`。

> ⚠️ **`direction` 是「性能启发」——可错、可无视、且噪声大**（验证见 `proj/if/direction_signal_validation.md`）：
> - `share` 用**信息维度口径**（分母剔除 `none`）。早期 bug 用了含 `none`(~60%) 的总分母，导致 bottleneck 恒为 `latency`/零区分度，已修。
> - ATT 采样**单次会抖**：决策应**多次投票取众数**（`search.driver.vote_direction(ev, s, n=5)` → `DirectionVote.trusted()`），低置信（`latency`/`none` 或频率 <60%）**回退固定阶梯**。
> - 它与 perf 相关性弱，**只配当「先试什么」的先验，绝不当目标函数**；真正拍板的是实测 `tflops` + `correct` + `Verifier`。
> - AI 若有自己的判断，**可完全忽略 `direction`/`hints`**，改用 §2.3 的只读事实接口自行决策。

> 闭环：`挑 region/算子（按 direction 或自定）→ RegionEditor 移动 → recompute(_cfg) → Verifier → evaluate(with_counters) → direction → 下一轮`。

---

## 端到端示例：把循环内第 2 条 `ds_read` 移到「前一个 MFMA 间隔」

```python
from reorder import parser, regions, waitcnt, emitter
from reorder.editor import RegionEditor
from reorder.verifier import Verifier
from reorder.model import Kind
from isa.gfx942.target import Gfx942Target
from isa.gfx942.passes import ForcedNopPass

src  = open("testcase/shader/fp8gemm_blockscase_32mx1_32nx4.s").read()
prog = parser.parse(src)
t    = Gfx942Target.from_program(prog)
ref  = parser.parse(src)                       # 验证基准

loop = [r for r in regions.analyze(prog, t).regions if r.kind.value == "loop"][0]
ed   = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)

# 1) 选中第 2 条 ds_read（按当前顺序）
ds   = [i for i in ed.order if ed.kind_of(i) is Kind.DS_READ]
tgt  = ds[1]

# 2) 求“前一个 MFMA 间隔”的锚点：
#    tgt 当前所在间隔的起始 MFMA 的“上一个” MFMA，移到它之后 = 进入前一个间隔
pos        = ed.order.index(tgt)
prev_mfmas = [m for m in ed.anchors(Kind.MFMA) if ed.order.index(m) < pos]
gap_anchor = prev_mfmas[-2]

# 3)（可选）先看合法窗口，判断可行性
print("legal_window:", ed.graph.legal_window(tgt))

# 4) 逐条移动；非法则被拒绝并给出原因
d = ed.move_after(tgt, gap_anchor, strict=False)
print(d.changed, d.note, d.skipped)            # skipped 非空 => 越界，未改动

# 5) 合法则提交 -> 重算 -> 兜底 nop -> 验证 -> 落盘
if d.changed:
    ed.materialize()
    waitcnt.recompute(prog, t, region=loop, opt_level=1)
    ForcedNopPass().run(prog, t)
    res = Verifier(t, reference=ref, analysis=regions.analyze(prog, t)).verify(prog)
    print("verify:", res.ok, res.violations[:3])
    open("cand.s", "w").write(emitter.emit(prog))
```

### 要点
- 精确放到某条 MFMA 后/前：`move_after(tgt, anchor)` / `move_before(tgt, anchor)`，`anchor` 取自 `ed.anchors(Kind.MFMA)`。
- 若该 `ds_read` 因 **LDS round-trip**（要等填它那条 band 的 `buffer...lds`）或它喂的 **MFMA / barrier 栅栏** 而进不去那个间隔，
  `move_after` 会直接拒绝：`d.changed=False`、`d.skipped=[tgt]`、`note` 写明窗口 `[lo,hi]`——AI 不会拿到错误 kernel。
- 移动合法但激进时，正确性仍由 `recompute` + `Verifier` + 真机数值三层兜底。

> 端到端可运行范例见 `tools/make_candidate.py`（本文件即其接口的精简说明）。
