# Cold-start 验证：引擎对「未手调 kernel」的真机收益与限度

> 目的：证明固定逻辑引擎不只在手调 gemm 上「打平」，而是能对一个**未手调**(naive)
> kernel 做合法、正确的重排；并**诚实量化**它能恢复多少、剩下的差距来自什么。
> 工具：`tools/coldstart_demo.py`（真机，MI308X，k=4096/loop=20/repeats=3，2026-06）。

## 1. 实验构造

以已验证的 gemm seed 为参照，用引擎**合法地**造一个「冷」kernel：把每条访存值令
(`vmem_load` / `ds_read`) 用 `compact_kind(kind, earliest=False)` 下沉到其**最晚合法位**
——即「用之前才 load」的朴素调度，**没有 compute/memory overlap**，正是一个只为正确性
而写的 kernel 会有的样子。相对 seed，cold 改动了 loop 内 **414/451** 个位置（重度重排）。

随后让引擎把访存值令重新铺回 MFMA 流，测恢复幅度。所有候选都过
`waitcnt.recompute(L1) + ForcedNopPass + Verifier`，并经真机 `#TEST PASSED` 数值门控。

## 2. 真机结果

| 调度 | correct | median TFLOPS | vs seed |
|---|---|---|---|
| seed_L1（手调，跨迭代预取流水） | ✅ | **8.86** | — |
| cold（访存下沉，naive） | ✅ | 7.45 | **−16.0%** |
| cold + `distribute_evenly`(load+ds_read) | ✅ | 7.43 | −16.2%（vs cold −0.3%） |
| cold + `compact_kind`(earliest, load+ds_read) | ✅ | 7.74 | −12.7%（vs cold **+3.9%**） |
| cold 当 seed 跑完整 `search()` | ✅ | 7.47（基线） | 无候选超过冷基线 |

## 3. 结论（M7 skill 证据）

1. **正确性在重度重排下成立**：改了 414/451 位置、−16% 性能的 cold 版本仍 `#TEST PASSED`，
   印证 legal-by-construction + waitcnt 重算 + Verifier + 真机数值门的多层兜底。
2. **主杠杆是跨迭代软件流水预取（≈16%）**：seed 的优势在于「上一轮迭代就发出本轮要用的 load」。
   单 loop body 内的重排（distribute/compact/listsched）**只能恢复约 4%**（hoist：7.45→7.74）。
   ⇒ **范围澄清（重要）**：预取深度（预取一轮/两轮）是 kernel **设计阶段定死**的，本引擎**不合成、
   不重构流水、不改 tile size**。引擎的职责是**识别**已有的预取——哪几条 load 是为后续迭代取数——
   从而 (a) 算对 loop-carried `s_waitcnt`，(b) 重排时**别把预取打散**。
   - 识别已实现：`reorder/prefetch.py`（reg 直达路径 + LDS band 路径），真机 gemm 识别出 18 条预取
     load（triple-buffer）。这正是 waitcnt 记分牌跨 back-edge 绑定的显式化。
   - 保护已实现：`RegionEditor(protect_prefetch=True)` 把识别出的预取 load 限为 **hoist-only**
     （可前移=增大重叠，不可下沉=缩小重叠），新增 `SkipReason.PREFETCH_PROTECTED`。这正好阻止
     上面 cold 实验里「把 load 下沉贴使用点」那类破坏预取的动作。
   - 所以 cold 的 −16% 的正确解读不是「引擎该新增流水变换」，而是「**重排必须保住已有预取，绝不能
     把它下沉打散**」。冷 kernel 上最有效的单体动作仍是「load 连同 ds_read 一起 hoist 到最早」。
3. **单类提前发射可能净负**：只 `compact(vmem_load, earliest)` 不带 ds_read，在冷基线上反而 −3%
   （需 load 与其消费 ds_read 一起前移，否则 ds_read 仍卡住）。
4. **搜索不误纳劣解**：手调 seed 上 search 返回 baseline；冷 seed 上 search 也未接受任何更差候选
   ——正确性 + 噪声门控如实工作。

> 这些是 M7 知识层的首批「带证据 + 置信度 + 验证门」的 skill 来源（见 `agent/knowledge.py`、
> `proj/knowledge_agent_design.md`）。知识层只**导航**（建议先试什么），合法性/正确性仍由引擎裁决。
