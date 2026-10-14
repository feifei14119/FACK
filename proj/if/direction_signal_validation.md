# M6b：`direction` 信号可靠性验证（接入搜索前的去风险）

> 目的：M6c 的搜索循环会信任 `EvalResult.direction.bottleneck` 来挑下一个编辑算子。
> 在此之上动工前，先在真机上回答三个问题，并据此决定**怎么用 / 不怎么用**这个信号。

## 1. 方法

工具 `tools/validate_direction.py`（真机 + ROCm）：对一组**已知调度差异**的候选，
各测性能（GFLOPS，取中位数）并重复采集 R 次 `direction`，回答：

- **稳定性**：同一个二进制重复采 R 次，`bottleneck` / 各维 stall 占比是否抖动（ATT 采样噪声）。
- **区分度**：真正不同的调度（seed / vmem_load hoist / sink / even-distribute 打散）是否给出不同的 stall 画像。
- **相关性**：更差的 stall 画像是否真的对应更低的 GFLOPS。

候选矩阵：`seed_L1`（优化基线，cfg L1）、`hoist_L2` / `sink_L2`（L2 vmem_load 提前/下沉）、
`even_scramble`（在已优化 kernel 上强行均匀打散 ds_read，制造一个“坏”对照）。
环境：MI3xx，k=4096，total_loop=20，R=5，perf×3。

## 2. 关键发现

### 2.1 旧分类器是退化的（恒为 `latency`）—— 已修复

首轮（修复前）`bottleneck[current]` 对**四个候选全部 = `latency`**，零区分度：

| 候选 | GFLOPS | median_total_stall | bn[旧:含 none] | bn[新:仅信息维度] |
|---|---|---|---|---|
| even_scramble | 8823 | 43272 | **latency** | memory |
| seed_L1 | 8755 | 36336 | **latency** | memory |
| hoist_L2 | 7895 | 44856 | **latency** | compute |
| sink_L2 | 7823 | 44196 | **latency** | compute |

**根因**：ATT 的 `none` 桶（category 0/8/9/10/11）在 GEMM core loop 上占了 **~60%** 的 stall 周期，
而 `classify` 的 `share = top_dim_stall / total` 分母用的是**含 none 的总和**。于是任何真实维度都
无法越过 40% 阈值 → 永远 fallback 到 `latency`。**信号被结构性抹平，毫无指导价值。**

**修复**（`analysis/bottleneck.py`）：`share` 改为对**信息维度**（剔除 `none`）的占比计算；
原始 `none` 占比仍以 `none_fraction` 透明保留。修复后真机复测，生产 `classify` 恢复区分度：

| 候选 | GFLOPS | median_total_stall | bn[修复后] | 稳定性 |
|---|---|---|---|---|
| seed_L1 | 8830 | 36400 | **memory** | 60–100% |
| even_scramble | 8825 | 42168 | **compute** | 60% |
| hoist_L2 | 7955 | 41184 | **compute** | 100% |
| sink_L2 | 7880 | 37972 | **compute** | 100% |

→ 不同调度给出不同 bottleneck（seed=memory，hoist/sink=compute），信号活了。

### 2.2 稳定性：中等，需多次投票

单次采集的 `bottleneck` 在 R=5 次里 **60%–100%** 命中众数；`total_stall` 的变异系数 CV≈0.04–0.25。
即**单次采集会抖**，hoist/sink 较稳（100%），seed/even 较松（60%）。

> **后续复测（2026-06, k=4096, M6c 真机闭环）**：seed_L1 的 5 次投票变为 **`compute` 5/5（100%）**
> （单次明细 `compute 53% / memory 11% / none 75.7%`, total_stall≈62236），**与上表「seed=memory」不一致**。
> 跨日/跨规模 bottleneck 在 `memory↔compute` 间漂移，恰恰再次印证本文结论：`direction` **只配当先验、需投票、
> 绝不当目标函数**。M6c 据此设计——投票取众数 + 低置信回退 + 最终以实测 GFLOPS 拍板，故该漂移不影响搜索正确性。

### 2.3 相关性：弱，不能当目标函数

`Spearman(perf, total_stall)` 两轮分别为 **-0.6 / -0.2**：方向对（stall 越多越慢）但**弱且不稳**。
`even_scramble` 甚至 stall 偏高却 perf 不低——说明 `total_stall` / `direction` **不是性能的可靠代理**。

## 3. 结论与对 M6c 的接入决策

1. **修复已落地**：`classify` 用信息维度口径（本提交）。这是 m6b 唯一改动生产代码的地方，
   有真机证据支撑、且全套单测 156 passed 不破。
2. **direction 仅作“算子选择先验”，绝不作目标函数/reward**。
   优化目标仍是**实测 GFLOPS + 正确性/Verifier 三层兜底**（与既有「AI/搜索提议、真机度量」分工一致）。
3. **搜索必须多次采集投票**：M6c 取 `bottleneck` 时对 N（建议 3–5）次采集取众数，单次不可信；
   并可用 `none_fraction` / 稳定性作为“是否信任本轮 direction”的门槛。
4. **低置信回退**：当 `bottleneck ∈ {latency, none}` 或投票不集中（众数频率 < ~60%）时，
   M6c 不依赖 direction，退回固定逻辑阶梯（optlevel 梯度 + `compact_kind` 枚举）。

> 一句话：`direction` 是一个**有用但粗糙、需投票、只配当先验**的信号。修了 `none` 分母这个致命 bug 后
> 它能区分 memory/compute 类瓶颈，足以**指引先试哪类算子**；但**选不选得中仍由真机 GFLOPS 拍板**。

## 4. 复现

```bash
python3.8 tools/validate_direction.py --k 4096 --loop 20 --repeats 5 --perf-repeats 3
# 输出 per-candidate: perf / median_total_stall / stall_cv / bn[current] / bn[informative]
# + Spearman(perf,total_stall)，并落盘 /tmp/direction_validation.json
```
