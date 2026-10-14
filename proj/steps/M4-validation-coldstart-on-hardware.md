# M4 验证报告：cold-start waitcnt 重算的真机验证（gfx942）

> 对象：`testft/testcase/` 真实 fp8 block-scale GEMM（shader `fp8gemm_blockscase_32mx1_32nx4.s`）。
> 环境：gfx942 实机 + ROCm（`clang++` 汇编、`gemm.exe` 跑正确性/性能）。
> 结论：**from-scratch loop-aware 重算在大 k 下欠同步（不安全）；安全默认（保留手写 wait 当 fence）稳健。**
> 日期：2026-06-05

---

## 1. 方法

用 `tools/make_candidate.py` 从真实 shader 生成候选 `.s`，`clang++` 汇编成 `gemm.co`，跑 `gemm.exe`：

| 候选 | 含义 |
|------|------|
| baseline | 原始手写 shader（未改） |
| recompute_only | **丢弃 loop 手写 wait，loop-aware 重算**（寄存器记分牌 + 保守 LDS 守卫），不重排 |
| reorder_only | `distribute_evenly(ds_read)` + **保留手写 wait 当 fence**（安全默认） |
| reorder_recompute | 重排 + 重算 + forced nop（全 cold-start） |

正确性判据：stdout `#TEST PASSED`（默认 `dump_result=1`，容差 rtol/atol=0.01，允许 5% 失配）。
关键：**用更大的 `k` 增加循环迭代数**以逼出稳态/跨迭代同步问题。

---

## 2. 结果

### 2.1 默认 k=128（循环迭代少）—— 全部通过、性能持平

| 候选 | 正确性 | 性能 (GFLOPS) |
|------|--------|---------------|
| baseline | PASS | ~845–854 |
| recompute_only | PASS ×5 | ~842–854 |
| reorder_only | PASS ×3 | ~855 |
| reorder_recompute | PASS ×3 | ~848 |

→ 小 k 下重算“看起来对”，且性能与手写持平。**但这是假象**（循环没跑够轮数）。

### 2.2 加大 k（逼出稳态）—— from-scratch 重算暴露欠同步

通过率（同一二进制重复跑 10 次）：

| 候选 | k=2048 | k=4096 |
|------|--------|--------|
| baseline（手写） | **10/10** | 10/10 |
| **recompute_only（from-scratch）** | **2/10 ❌（不确定性失败=竞态）** | — |
| recompute 但 `vmcnt` 截到 ≤10（手写值） | **10/10 ✅** | 10/10 ✅ |
| reorder_only（保留手写 wait/安全默认） | **10/10 ✅** | 10/10 ✅ |

---

## 3. 根因

- 重算给循环顶部 MFMA 生成的是 `vmcnt(19/18/13)`，而手写是 `vmcnt(10)`。**我的 vm 值偏松**
  （允许在飞过多），大 k 稳态下变成**竞态**（间歇性失败，2/10）。把 `vmcnt` 截到手写的 ≤10 即恢复
  10/10 —— 锁定 bug 在 **vm 计数（LDS 往返）**，与 `lgkmcnt(3)` 无关（截 vm 后 lgkm 仍为 3 也全过）。
- 机理：循环顶 `vmcnt` 的真正约束是 **“上一段 `buffer_load…lds` → 本段 `ds_read`” 的 LDS 往返**
  （手写 `vmcnt(10)`），它比“`acc`-load → MFMA”的寄存器距离（我算的 19）**更紧**。
- 我的“保守 LDS 守卫”**实际失效**：24 条 `ds_read` 全部没拿到任何 vm wait。原因是前面 MFMA 那条偏松的
  `vmcnt(19)` 已把记分牌的 `done[vm]` 推过了相关 lds-load，守卫据此误判“已完成”，于是不再加紧 wait。
  即——**一条无关的、更松的 wait“盖住”了本应更紧的 LDS 约束**。要修必须做 **LDS slot 精确建模**
  （按 m0 offset 知道每条 `ds_read` 到底依赖哪条 `lds`-load，且不允许被无关 wait 顶替）。

---

## 4. 结论与处置

1. **from-scratch loop-aware 重算（寄存器 + 当前保守 LDS）= 不安全**，禁止用于真机产出，直到 M5
   做出 LDS slot 精确建模。已在 `fixup_pipeline()` 中设为**非默认**（需显式 `recompute_waitcnt=True`），
   并标注“需真机验证”。本验证即为该警示提供了硬证据。
2. **安全默认成立**：`reorder_only`（保留手写 wait 当 fence，仅段内重排）在 k=2048/4096 **10/10**，
   性能持平。这是当前可信赖的产出路径。
3. **寄存器侧机制本身是对的**（合成双缓冲循环稳态算出正确的 `vmcnt(1)`；真实 kernel 手写 wait 通过
   loop-aware 寄存器充分性校验）。问题仅在**经 LDS 的内存依赖**未被精确建模。

---

## 5. 复现实验

```bash
# 生成候选
PYTHONPATH=. python3.8 tools/make_candidate.py recompute_only testcase/c.s
# 汇编 + 大 k 压测（重复 10 次看通过率）
cd testcase && /opt/rocm/llvm/bin/clang++ -x assembler -target amdgcn--amdhsa \
    --offload-arch=gfx942 c.s -o gemm.co
for i in $(seq 10); do ./gemm.exe m=128 n=128 k=2048 | grep -ao "TEST PASSED"; done
```

`tools/tweak_waits.py` 可把候选里的 `lgkmcnt(N)→0` 或 `vmcnt(N)` 截顶，用于二分定位（如上 §3）。
