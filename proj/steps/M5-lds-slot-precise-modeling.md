# M5：LDS-slot 精确建模 + barrier 释放栅栏（gfx942 真机验证通过）

> 目标：把 M4 判定为「不安全」的 **from-scratch waitcnt 重算** 做正确，使 cold-start /
> 激进重排可安全产出。
> 对象：`testft/testcase/` 真实 fp8 block-scale GEMM（`fp8gemm_blockscase_32mx1_32nx4.s`）。
> 环境：AMD Instinct **MI308X（gfx942）** + ROCm 6.4.2（`clang++` 汇编、`gemm.exe` 跑正确性）。
> 结论：**recompute_only 在 k=2048/4096 50/50、k=8192/16384 100/100 全过**（M4 broken 重算
> k=2048 仅 2/10）。性能与手写持平（~3000 GFLOPS @ k=4096）。
> 日期：2026-06-05

---

## 1. 先纠正 M4 的根因判断（实测）

M4 报告 §3 推测「一条更松的 `vmcnt(19)` 盖住了 LDS 约束」。M5 用 `tools/diag_lds.py` 实测后发现
**更直接的根因**：

1. **保守 LDS 守卫是个 no-op（运算 bug）**。`waitcnt._is_lds_direct_load` 判 `操作数字段 == "lds"`，
   但解析后字段是 `"0 offen lds"`（逗号分割、修饰符在字段内）。实测：循环体 24 条 `buffer_load…lds`
   经该函数命中 **0/24**；经 `target.is_lds_load`（按 token 切分）命中 **24/24**。
   → 24 条 `ds_read` 从 LDS 路径**完全没拿到 vm wait**，纯靠寄存器跟踪（而 `ds_read` 源是 `v34`，
   同步写，无 vm producer）→ 也没有 → **彻底欠同步**。

2. 修好 LDS 检测后仍有 **~5–7% 的高 k 间歇失败**（k=8192：49/50）。二分定位发现真正的残留竞态是
   **barrier 缺少 LDS 释放栅栏**（详见 §3），而非 per-`ds_read` 的 vm 值。

---

## 2. LDS 多缓冲结构（实测，三缓冲）

`tools/diag_lds.py` 解析出 LDS 写/读寻址：

- **写**：`s_add_u32 m0, IMM, sBASE` + `buffer_load…lds`；前导链
  `s58=root+0 ; s59=root+0x1080 ; s60=root+0x2100`（步距 `0x1080=4224`）。
  → 三个缓冲基址寄存器 s58/s59/s60，组内 imm slot ∈ `{0,0x100,0x200,0x300}`（< 步距）。
- **读**：`ds_read_b128 acc[..], v34 offset:N`；读基址恒为 `v34=v4<<2`，`N` 选择缓冲带：
  band = `N // 4224`，组内 slot ∈ `{0,64,512,576}`。

二者**步距一致（4224）**，故缓冲带可静态对齐：写 band = `基址常量 // 步距`，读 band = `offset // 步距`。
循环体（6×展开、三缓冲轮转）每组写 band `(g-1)%3`、读 band 比写**滞后 2 组**——典型 triple-buffer。

`isa/gfx942/lds.py::build_lds_model` 用**标量常量折叠**还原 m0 基址链（前导在 prologue，需对整段 `.text`
折叠、只在 scope 内记录 load/read），得：`resolved=True, stride=4224, n_buffers=3`，读/写 band 完全对齐。

> 关键修正：缓冲步距取自 **m0 基址寄存器之差**，**不**与组内 imm slot 做 gcd（否则 `gcd(256,4224)=128`
> 误判 73 个缓冲）。`base` 与 `imm` 分开跟踪。

---

## 3. 真正的根因：barrier 的 LDS 释放栅栏

手写每个子迭代顶部是 `s_waitcnt vmcnt(10) & lgkmcnt(0) ; s_barrier`。其中 **`lgkmcnt(0)` 是跨 wave 的
LDS 释放栅栏**：`s_barrier` 同步整个 workgroup，barrier 后本 wave 会读**别的 wave** 在 barrier 前写入
LDS 的数据，故每个 wave 必须在 barrier 前完成自己的 LDS 访问（`ds_write→lgkm`、`buffer_load…lds→vm`）。

这是**控制/内存序约束，不是寄存器依赖**——记分牌看不到。重算把 `lgkmcnt(0)` 换成了按寄存器算出的
`lgkmcnt(3)` → barrier 前 LDS 未排空 → 跨 wave 竞态（间歇、数据轻微损坏，常在容差内，故 ~5% 偶发失败）。

**修法**（`reorder/waitcnt.py::_Scoreboard.step`，按 `Kind.BARRIER`）：barrier 前强制
- `lgkmcnt(0)`（排空全部 `ds_*`/smem），
- `vmcnt(排空全部在飞 lds-direct load)`（其数据经 barrier 被别的 wave 读）；普通 VMEM-load 预取可留在飞。

该栅栏自然复现手写的 `vmcnt(N) & lgkmcnt(0)` 组栅栏（本 kernel 实算 `vmcnt(4)`，比手写 10 更紧、安全）。
注意：因为 barrier 在 `ds_read` 之前已排空 lds-load，per-`ds_read` 的 LDS 绑定在本 kernel 多被栅栏吸收；
但在「读前无排空 barrier」的结构里 per-read 绑定仍是唯一保护，二者互补。

---

## 4. 实现

| 文件 | 改动 |
|------|------|
| `isa/gfx942/lds.py`（新） | LDS 缓冲解析器：标量常量折叠 m0 基址链 → 每条 lds-load/ds_read 的缓冲带；`resolved` 失败回退保守单桶 |
| `isa/gfx942/target.py` | `lds_roundtrip_model(instr_lines, scope_idxs)`；更新 `fixup_pipeline` 文档（移除 KNOWN-UNSAFE） |
| `reorder/waitcnt.py` | 修 lds-load 检测（用 `target.is_lds_load`）；`_Scoreboard` 增 per-band `lds_bufs` + barrier 释放栅栏；`compute_waits*`/`recompute` 透传 `lds_model`（core 仍 arch-agnostic，靠 `hasattr` 能力探测） |
| `reorder/verifier.py` | 新增 `_lds_barrier_sufficiency`：① `ds_read` LDS 往返充分性（band-precise/保守）② barrier `lgkmcnt(0)` 栅栏；循环体两遍法暴露跨迭代 |
| `tests/test_m5.py`（新） | 13 项：缓冲解析/步距、band 精确绑定、barrier 栅栏插入与校验、回退、真机 kernel 结构不变量 |
| `tools/diag_lds.py`、`tools/hw_validate.sh`、`tools/diag_verify.py`（新） | 诊断/真机压测/校验复现脚本 |

---

## 5. 真机结果（MI308X / gfx942）

`recompute_only`（丢弃 loop 手写 wait，loop-aware 重算 + LDS 模型 + barrier 栅栏；**不重排**）：

| 候选 | k=512 | k=2048 | k=4096 | k=8192 | k=16384 |
|------|-------|--------|--------|--------|---------|
| baseline（手写） | — | 50/50 | 50/50 | 50/50 | — |
| **M4 broken 重算** | — | **2/10 ❌** | — | — | — |
| 仅修 LDS 检测（无 barrier 栅栏） | 20/20 | 50/50 | 50/50 | **56/60 ❌** | 58/60 ❌ |
| **M5（LDS band + barrier 栅栏）** | 20/20 | **50/50 ✅** | **50/50 ✅** | **100/100 ✅** | **100/100 ✅** |

性能（k=4096，与手写同区间）：手写 ~3020–3708 GFLOPS；M5 recompute_only ~2824–3113 GFLOPS。

**整程多区重算 `recompute_cfg`（边界 counter 契约）** —— `recompute_only` 只重算 loop 区、保留 prologue/epilogue
的手写 wait；`recompute_cfg` 从零重算**整个 kernel（prologue+loop+epilogue）**。关键在**跨区边界 counter 契约**：
用一块 scoreboard 按程序序穿过各区——

- prologue / inter / epilogue：直线 pass，**用前一区出口 scoreboard 作为入口**（prologue 从空入口=kernel 起点）；
- loop：自洽的 fixpoint（已真机验证，保持不变），其**稳态出口 scoreboard 馈入下一区**。

这正好修复 epilogue 的 `ds_read` / barrier LDS-release 栅栏——它们依赖的 lds-load 是**在 loop 内发出的**，孤立重算
epilogue 看不到 → 欠同步（探针实测 line 932 barrier + 943-946 ds_read 违例）。边界契约把 loop 出口在飞状态带入后即修复。
真机：`cfg` 候选 **k=512/2048/4096 各 20/20 = 60/60 PASS**。

> 推广：契约对一般 region DAG 成立——分支 join / wave-specialization meet 处取各前驱出口在飞集合的**保守并**
> （done-frontier 取交、outstanding 取并）。当前已实现并验证的是**线性单环 CFG**（本 kernel 的结构）；含分叉/汇合的
> kernel 需要相应样本才能真机标定 meet。

校验器（`tools/diag_verify.py`）：手写 / recompute_only **0 违例**；蓄意破坏（barrier `lgkmcnt(0)→(8)`、
删 `ds_read` vmcnt）→ barrier 栅栏 + LDS 往返检查**精确命中**，对正确代码**无误报**。

---

## 6. 复现

```bash
# 诊断 LDS 结构 / 模型 / 每条 ds_read 重算值
PYTHONPATH=. python3.8 tools/diag_lds.py
# 生成 recompute_only 候选并真机压测（脚本内含 clang++ 汇编 + N 次跑通过率）
PYTHONPATH=. python3.8 tools/make_candidate.py recompute_only /tmp/cand.s
bash tools/hw_validate.sh /tmp/cand.s 50 2048 4096 8192
# 校验器健全性（手写/重算过、破坏被抓）
PYTHONPATH=. python3.8 tools/diag_verify.py
PYTHONPATH=. python3.8 -m pytest tests/ -q     # 123 passed
```

---

## 7. barrier 栅栏 band 前瞻优化（已实现并真机验证）

初版 barrier 栅栏排空**全部** lds-load（`vmcnt(4)`），比手写 `vmcnt(10)` 偏紧、预取重叠少。已实现
**band 前瞻**（`reorder/waitcnt.py::_barrier_read_bands` + `_Scoreboard.barrier_bands`）：在每个 barrier
处向前（循环体内**环绕**到下一个 barrier）扫描，只收集该段内 `ds_read` 实际读的 band，barrier 的 `vmcnt`
**只排空这些 band** 的 lds-load，其余 band 的预取留在飞。每个 wave 各自排空自己读的 band，barrier 保证
所有 wave 都排空，故跨 wave 充分。段内有未解析的 `ds_read` 或模型未 resolved 时回退「排空全部」。

- 真实 kernel：每个组顶 barrier 由 `vmcnt(4)` 放松到 **`vmcnt(15)`**（手写 10）；
- 真机：**k=2048/4096 50/50、k=8192/16384 100/100 全过**（与初版同样 100% 正确）；
- 性能（k=4096，best-of-6）：手写 ~3663 GFLOPS，优化版 **~3879 GFLOPS**（预取重叠更多，略超手写）；
- 正确性兜底：verifier 的 per-`ds_read` LDS 往返检查会校验每条读的 band producer 已排空——若 band 前瞻
  算漏，必被该检查抓到（已由 `tests/test_m5.py::test_verifier_flags_missing_ds_read_roundtrip` 等覆盖）。

## 7.1 优化等级开关（`reorder.optlevel`，已实现）

把 §3 的初版（排空全部）与 §7 的 band 前瞻做成**单一等级开关**，由 AI / 搜索 / 用户选一个数字，
等级越高越激进（每级都已验证正确，是下一级变换的超集）：

| 等级 | barrier 栅栏 / 重排 | 真机（best-of-20 GFLOPS, k=8192）|
|---|---|---|
| **L0 CONSERVATIVE**（§3 初版）| 排空全部 lds-load（`vmcnt(4)`）| 4581 |
| **L1 BALANCED**（§7，默认）| band 前瞻（`vmcnt(15)`）| 6057–6123 |
| **L2 SCHEDULED** | L1 + 逐条重排（`compact_kind` hoist load）| seed 上逐条滑动，见下 |
| **L3 SEARCH** | 真机自动调优（`search_schedule.py`）| L1（噪声内最优）|
| **L4 AGGRESSIVE** | L2 + 把 VALU/SALU 也纳入逐条重排（RAW/WAR/WAW/scc/m0 约束）| HW 剔除错误变体，见下 |

> **设计契约（用户定调）**：固定逻辑只保证「**逐条移动接口** + 移动后**正确重算 waitcnt/barrier**」；优化方向/策略
> 交给 AI，策略可以非常激进，**结果由验证逻辑（dep-order + waitcnt/barrier 充分性 + 真机数值）剔除错误 kernel**。
> 调优面向各种 kernel/算法，固定逻辑不追求全覆盖最优。

> **L4 移动 v/s 值令**：依赖图本就对**每个寄存器 def/use**（含隐式 scc/m0）建 RAW/WAR/WAW 边，故一条 v 值令
> 的合法窗口被其消费者收紧——例如算出某 VGPR、后面 `buffer_load` 用它作地址，则该 v 值令**绝不会**滑到该 load
> 之后（用户要求的语义，已由 `legal_window` 天然保证；新增 `tests/test_m5.py::test_l4_valu_cannot_cross_address_consumer`）。
> 接口：`make_candidate level 4`（默认 hoist vmem_load+valu+salu），或 `--reorder-kind valu|salu --reorder-dir hoist|sink`。
>
> **真机实测（k=4096/8192，各 20 次）**：baseline/L1 全 PASS；**L4-SALU-hoist 20/20 正确**、**L4-sink 20/20 正确**；
> 但 **L4-VALU-hoist 0/20（数值错误）**——隔离确认是 VALU（非 SALU）。根因：loop 内 VALU 主要是读 MFMA 输出
> （`v[36:39]`…）的 `v_pk_fma`，hoist 把它们紧贴到产出 MFMA 之后，触发 **MFMA 回写延迟（cycle 级硬件冒险）**，
> 这**不是纯顺序依赖图能表达的**（RAW 顺序已满足，故静态 verify 仍 ok）。**这恰好印证契约**：激进变体由真机数值
> 校验剔除。L4 要求的「对 v/s 目的操作数的 RAW 依赖」本身完全正确（SALU/sink 全 PASS）。

> **MFMA 结果「最小间距」静态约束（已实现并标定）**：依赖图的边现在带 per-edge **最小位置间距**
> （`DepGraph.add_edge(..., dist=N)` / `dist()` / `latency_edges()`）。`edges.py` 给 **MFMA 写 → 非 MFMA 读**
> 的 RAW 边挂上 MFMA 回写延迟；`legal_window` / `editor._block_insert_range` / `is_order_legal` 全部尊重该间距，
> 故重排**不会**把消费者拉进延迟窗口。
> **延迟值从 seed 自动标定**（`edges.py` 两阶段）：seed 已知正确，故其**每个 MFMA opcode 最紧的「写→非 MFMA 读」
> 间距**即经验安全值；`classify.MFMA_READ_LATENCY` 降级为「该 opcode 在 seed 中无消费者」时的兜底（`ForcedNopPass`
> 仍用它补 nop）。这样 **seed 永远合法**且对任意 kernel/形状自校准，无需为每种形状硬编码猜测。真机 kernel 上自动还原
> `16x16x32 == 3`（与手动标定一致：间距 2 在 MI308X 失败、3 既必要又充分）。多单元 hoist 会把填充指令搬出某个间距 → `compact_kind`
> 末尾做**有界 distance-repair**（把违例消费者下沉回其合法最早位、单调向下、必收敛；真不可行则整体回退到合法序）。
> **真机复测（k=4096/8192，各 16 次）**：baseline / L1 / **L4full / L4-VALU-hoist / L4-VALU-sink 全部 16/16 PASS**
> ——其中 **L4-VALU-hoist 从 0/20 → 16/16**（过度 hoist 现被静态约束判为不可行而回退，绝不再把错误 kernel 送上真机）。
> 即：这类「纯顺序图表达不了的 cycle 级延迟冒险」现在**在上真机前就被静态拦下**。

> **L3 自动调优 + 诚实结论**：`tools/search_schedule.py` 枚举 L2 变换（kind×方向×组合×顺序），每候选静态
> 校验 → **交错 round-robin** best/median-of-N → 以 L1 自身运行间 CoV 作噪声地板判定。24 轮实测：L1 自身
> **CoV≈5.5%**，所有重排候选 median 落在 ±5% 内（L1 反而居首）。**结论：在这个已手工调优的 kernel 上，
> 逐条重排无法可靠超过 L1**——之前 best-of-N/非交错看到的「+4~8%」是噪声假象，加大样本+交错后消失。
> 自调优器正确地报「within noise，保持 L1」。要榨出更细信号需锁 GPU 频率（降低 CoV）。L3 在「尚未调优」
> 的冷 kernel 上才会有超过噪声的真实增益。

> **L2 逐条重排**：以**当前已优化 kernel 为 seed**，把异步访存逐条滑到其合法窗口端点（默认 hoist
> buffer_load → 增大 load→use 距离/重叠）；只挪单条、保相对顺序、不打散，重算再补最小 wait。方向/对象可调
> （`make_candidate level 2 --reorder-kind/--reorder-dir`）。注：单条变换的真机增益需用 L3 交错测量甄别噪声
> （见下）——初期 best-of-20 看似 hoist +8% 实为噪声。

> **seed = 优化起点 kernel 本身**：testcase 这个 shader 已优化过，它**自己就是 seed + 性能基准**，
> 直接在其上跑优化等级即可。**均匀铺开（`distribute_evenly`）不是优化等级、也不是 seed**——只用于把
> 一个完全没优化、指令按类型聚堆的 kernel 自举成可用 seed。真机实测「在已手调好的 shader 上再均匀
> 重排 ds_read/VMEM」反而更慢（打散了已有预取距离），印证它只适合 bootstrap 冷 kernel、不进优化等级。

- 贯穿：`waitcnt.recompute(..., opt_level=N)` → `compute_waits*` / `_Scoreboard.barrier_band_scoped`；
  `fixup_pipeline(recompute_waitcnt=True, opt_level=N)` → `WaitcntRecomputePass(opt_level=)`。
- 驱动：`tools/make_candidate.py level <N> <out.s>`（**只重算 waitcnt，不重排**）；seed 由 `seed` 模式驱动。
- L0 与 L1 真机均 100% 通过（runs=20 @ k=2048/4096/8192）；正交的「零风险」档仍是 `recompute_waitcnt=False`。
- 覆盖：`tests/test_m5.py` 新增 4 项（policy 解码 / L0 比 L1 紧 / 真实 kernel L0&L1 均 verify / 各 barrier L0≤L1）。
- 真机对比（best-of-20 GFLOPS，k=2048/4096/8192）：baseline 2964/3875/5939；L0 2350/3492/4581；
  **L1 3078/4444/6123**（全面≥baseline）。在已调度 shader 上再均匀重排 ds_read/VMEM 反而更慢（见 §7.1 注）。

## 8. 处置 / 后续

1. **from-scratch 重算（recompute_waitcnt=True）现判定 HW-safe**（gfx942），`fixup_pipeline` 文档已更新；
   仍为非默认（warm kernel 默认保留手写 wait 当 fence，零风险）。
2. LDS 模型解析失败时回退保守单桶 / barrier 排空全部，正确性不受影响（已测）。
3. **优化等级开关已落地**（§7.1）：L0 保守 / L1 band 前瞻（默认），单数字可选；L2+ 预留给逐条重排。
   均匀铺开已解耦为独立 seed 步骤（`make_candidate seed`），不进优化等级。
