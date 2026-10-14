# M4 步骤报告：FixupPass 流水线 + waitcnt 重算 + 校验 + 三阶段评测/分析

> 里程碑：**M4 修补流水线 / 同步重算 / 校验兜底 / 评测与瓶颈分析**
> 状态：**已完成**（93/93 测试通过，无 lint 错误；真实 kernel 重排→pass→校验端到端跑通；
> 含跨循环 loop-carried waitcnt 修正，见 §8）
> 日期：2026-06-05

---

## 1. 目标与验收门

M3 的纯重排只改顺序、不改文本。M4 在其后接上**架构无关的修补/校验/评测框架**，把"重排后的非法
中间态"修回合法可执行，并打通三阶段真机评测 + ATT 瓶颈分析的回流。

**验收门（已达成）**：

1. `reorder/passes.py`：`FixupPass` 协议 + `PassPipeline` + 可回滚 `LineDiff`（行级插/删/改，整盘快照回滚）。
2. `reorder/waitcnt.py`：通用 **score-based waitcnt 重算**框架，跨 `CounterModel` + 依赖图，零 ISA 常量。
3. `isa/gfx942/passes.py`：`WaitcntRecomputePass`（重算 s_waitcnt/s_waitcnt_vscnt）+ `ForcedNopPass`
   （MFMA 写后用延迟补 nop，**不增删 barrier/branch**）。
4. `reorder/verifier.py`：通用三查（依赖序 / waitcnt 充分性 / 架构不变式）+ `Target.invariants()`
   （gfx942 = barrier 数锁定、waitcnt 可编码）。
5. `Gfx942Target`：`fixup_pipeline(region)` / `perf_counter_schema()` / `invariants()` 实装。
6. `harness`：`toolchain.assemble_codeobject`（clang++ → .co，对齐 `testcase/cmd`）+
   `GpuTestcaseEvaluator` 三阶段（正确性 / 性能 / ATT dump）。
7. `analysis`：`perf.py`（ATT ctypes 解码 + `.out` 文件名解析 base/size + 聚合）+
   `bottleneck.py`（category/stall 分布 → 瓶颈维度 + 重排方向 hints）。
8. **端到端骨架**：真实 kernel 上「重排 core loop → 全局 waitcnt 重算 + forced nop → 校验通过 →
   emit → 重 parse、barrier 数锁定」离线跑通。

---

## 2. 交付物

```
testft/
  reorder/
    passes.py        # FixupPass 协议 + PassPipeline + LineDiff(可回滚) + snapshot
    waitcnt.py       # 新增 compute_waits() + recompute()（通用 score-based 重算）
    verifier.py      # Verifier: 依赖序 / waitcnt 充分性 / 架构不变式
  isa/gfx942/
    passes.py        # WaitcntRecomputePass + ForcedNopPass(+ MFMA 延迟表，可调)
    invariants.py    # BarrierCountLocked + WaitcntEncodable
    perf_schema.py   # ATT category(0..12) -> 瓶颈维度
    target.py        # fixup_pipeline()/invariants()/perf_counter_schema() 实装
  harness/
    toolchain.py     # 新增 assemble_codeobject(clang++ --offload-arch -> .co)
    evaluator.py     # GpuTestcaseEvaluator(三阶段) + 纯 stdout 解析器
  analysis/
    perf.py          # ATT 解码内核(ctypes) + discover_dump + aggregate
    bottleneck.py    # 维度级 stall 占比 -> bottleneck + hints
  tests/test_m4.py   # 13 例（重算/pass/校验/分析/评测解析 + 真实 kernel）
```

---

## 3. 核心：通用 waitcnt 重算（架构无关）

入口 `reorder.waitcnt.recompute(program, target, region=None)`：

1. 丢弃 scope 内的旧 `s_waitcnt*`（重排后语义已变，pass 接管同步）。
2. 在「非 wait 指令流」上建依赖图，按发射序走一遍，用**就地完成（in-order）模型**算每个消费者
   所需的最小计数目标。

规则（对每个计数器 T = vm/lgkm/exp/vs）：消费者 C 依赖的异步内存生产者 P（按 `Target.wait_type`
判定，MFMA = scoreboard → `NONE` → 不插 wait）。设到 C 之前已发射 `seq[T]` 个 T 类操作、P 的发射
序号为 `tidx[P]`，则需要 `waitcnt T(seq[T]-1-tidx[P])`（= P 之后、C 之前发射的 T 类操作数）。多个
生产者取最小目标；并维护 `drained[T]` 前沿跳过已保证完成的生产者，得到**最小够用**的 wait 集。

3. 重建行表：vm/lgkm/exp 合成一条 `s_waitcnt`，vs 单独 `s_waitcnt_vscnt null,N`，缩进沿用消费者行。

> 单元测试钉死语义：两连续 load 后消费**两者** → `vmcnt(0)`；只消费**第一条** → `vmcnt(1)`；重算幂等。

---

## 4. ForcedNopPass（gfx942 特有，架构隔离）

对每条 MFMA：若其 ACC 目标在 `MFMA_USE_LATENCY[shape]` 个发射槽内被**非 MFMA** 指令读取，则在 MFMA
后补足 `s_nop`。遇到下一条 MFMA / barrier / branch 即停（链式由硬件保证，不补）。**只插 s_nop，绝不
增删 barrier/branch**。延迟表是**可调占位**（机制精确，数值待按 gfx942 ISA §08 校准），未知 shape 取 0
即安全空操作。其它架构（s_delay_alu / s_clause / bank-switch …）按相同协议各自挂 pass，核心零改动。

---

## 5. 校验兜底 Verifier（GPU 之前的静态闸门）

- **依赖序**：在最终行表上重建图，`is_order_legal` 检查每条边 a→b 仍满足。
- **waitcnt 充分性**：按发射序走，遇真实 wait 更新 `drained[T]`；任一消费者的内存前驱
  `tidx[P] > drained[T]` → 记违例。与重算同模型 → 全局重算后自洽通过。
- **架构不变式**：`Target.invariants()` 逐项 `check(program, reference)`。gfx942：barrier 数相对
  参考程序锁定、所有 wait 目标 ≤ 计数器位宽。

测试覆盖：缺 wait 被判违例、重算后转通过；删掉 barrier 触发 barrier-count-locked。

---

## 6. 三阶段评测 + ATT 瓶颈分析

对接 `testcase/cmd`（详见 `proj/testcase_integration.md`、`proj/amdgpu-dump-parsing.md`）：

| 阶段 | 实现 | 说明 |
|------|------|------|
| assemble | `toolchain.assemble_codeobject` | `clang++ -x assembler -target amdgcn--amdhsa --offload-arch=gfx942 cand.s -o gemm.co` |
| 1 正确性 | `gemm.exe dump_result=1` | stdout 抓 `#TEST PASSED` |
| 2 性能 | `gemm.exe dump_result=0 total_loop=N` | 正则抓 `time:`/`gflops:` |
| 3 ATT | `rocprofv2 -i input.txt --plugin att auto -d ./att ./gemm.exe` | 产物交 `analysis` |

`analysis/perf.py`：`librocprofiler-sdk.so`（ctypes）把 `*_se*.att` 解码成逐指令事件
（issue/duration/stall/category）；code object 的 `load_base/size` **直接从 `.out` 文件名**
（`#offset=..&size=..`）解析，无需 results.db；`aggregate` 折成 category/维度级 stall 统计。
`analysis/bottleneck.py`：取 stall 占比最大的维度为瓶颈（<40% 视为弥散 latency），映射成方向 hints
（如 lds 瓶颈 → `distribute_evenly(loop, DS_READ)`）。

> GPU/ROCm 不在本机，故评测器的命令编排与 ATT 解码为「可导入、需真机执行」；其**纯逻辑**
> （stdout 解析、文件名 base/size、category 聚合、瓶颈分类）均已离线单测；`discover_dump`
> 在 `testcase/att/` 实测样本上验证。

---

## 7. 端到端骨架（真实 kernel，离线）

`重排 core loop（distribute_evenly ds_read）→ materialize → 全局 waitcnt 重算 + forced nop →
Verifier 通过 → emit → 重 parse`：真实 1120 行 kernel 上跑通，barrier 数 10→10 锁定，wait 全部可编码，
输出可重解析。

---

## 8. 跨循环 waitcnt 修正（M4 后续，关键）

> 评审指出：**所有 kernel 的循环体都涉及跨 loop 的 waitcnt**（软件流水：第 n 轮等 n-1 轮的
> load、用 n-1 的数据算、同时发 n+1 的 load）。最初的线性单遍重算对此**根本错误**（见
> `reorder_engine_api.md` §5.1.2）。已修正：

- **寄存器记分牌 + 虚拟展开定点迭代**（`reorder/waitcnt.py`：`_Scoreboard` / `compute_waits_loop`）：
  寄存器 use 自然绑定到**上一轮**的 producer；body 反复处理到 wait 值收敛（典型 2 拍）得稳态。
  实测：双缓冲循环稳态 `vmcnt(1)`（非 `vmcnt(0)`）；真实 kernel 的**手写 waitcnt 通过本引擎的
  loop-aware 寄存器充分性校验**。
- **Verifier 改为 loop-aware**（按 code-item 位置识别 loop，对 body 走两趟，第二趟检查），
  能抓出跨迭代欠同步；单测 `test_verifier_loop_carried_detects_missing_wait` 覆盖。
- **安全默认**：`fixup_pipeline()` 默认**不重算 waitcnt**（warm kernel 保留手写 wait 当 fence），
  `recompute_waitcnt=True` 才启用 loop-aware 重算（cold-start / 激进重排）。

### 真机验证结论（gfx942 实测，见 `M4-validation-coldstart-on-hardware.md`）

- **from-scratch loop-aware 重算 = 不安全**：小 k 假通过；加大 k 逼出稳态后 **recompute_only 在
  k=2048 仅 2/10 通过（竞态欠同步）**。根因是循环顶 `vmcnt` 偏松（算成 19，手写 10）——把 `vmcnt`
  截到 ≤10 即恢复 **10/10**，锁定 bug 在 **LDS 往返的 vm 计数**。
- **保守 LDS 守卫实测失效**：24 条 `ds_read` 全部没拿到 vm wait，因前面偏松的 `vmcnt(19)` 把记分牌
  `done[vm]` 推过、误判 lds-load 已完成。**必须做 LDS slot 精确建模（按 m0 offset）**，且不允许无关
  wait 顶替——交给 M5。
- **安全默认成立**：`reorder_only`（保留手写 wait 当 fence）在 **k=2048/4096 均 10/10**、性能持平。
  → 已把 `fixup_pipeline()` 的 waitcnt 重算设为**非默认**（`recompute_waitcnt=True` 才启用，并标注
  “须真机验证”）。寄存器侧机制本身正确（合成双缓冲得 `vmcnt(1)`、真实 kernel 手写 wait 过校验）。

### 其它遗留

- 多基本块循环体（带内部菱形而非仅 early-exit）的线性化前提；本 kernel 是直链 b1..b7 + 侧向 exit，满足。
- `MFMA_USE_LATENCY` 占位数值须按 gfx942 ISA 校准；评测/ATT 解码需真机实跑。
