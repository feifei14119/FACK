# ATT 文件的读取/解析实现，及 AI 如何使用（testft）

> 本文记录 **testft 工程内**「ATT 逐指令跟踪 → 结构化 stall 统计 → 瓶颈方向 `direction`」这条链路的**具体实现**，
> 以及 **AI/搜索层如何消费 `direction` 决定下一步移动**。
>
> - 通用的 `.att` 二进制解码协议（SDK 函数签名、C 结构体内存布局、category 枚举、PC→反汇编）见 `proj/amdgpu-dump-parsing.md`，本文不重复，只标注 testft 的差异点。
> - 重排/重算/验证等「移动接口」见 `proj/if/ai_interface.md`。本文是其 §6「真机评测 + 方向」的展开。

链路总览：

```
候选 cand.s
  └─ assemble ─► gemm.co
       └─ correctness / perf ─► (PASS, GFLOPS)
            └─ rocprofv2 --plugin att ─► testcase/att/  (*.att + *.out + *_kernel.txt)
                 └─ analysis/perf.py  discover_dump → decode_att(SDK,ctypes) → aggregate(schema)
                      └─ analysis/bottleneck.py  classify ─► direction {bottleneck, share, hints, stats}
                           └─ AI/搜索：按 bottleneck 选下一个移动算子 ─► 下一轮
```

代码落点：`harness/evaluator.py`（编排）、`analysis/perf.py`（解码+聚合）、`isa/gfx942/perf_schema.py`（category→维度）、`analysis/bottleneck.py`（分类）、`tools/eval_candidate.py`（CLI）。

---

## 1. 采集：rocprofv2 ATT dump

`GpuTestcaseEvaluator.dump_counters`（`harness/evaluator.py`）执行：

```bash
rocprofv2 -i input.txt --plugin att auto -d testcase/att ./gemm.exe k=<K>
```

产物落在 `testcase/att/`，三类文件（命名见 `proj/testcase_integration.md` §2）：

| 文件 | 含义 | 用途 |
|------|------|------|
| `<kernel>.kd_v0_se<S>.att` | 每个 Shader Engine 的 ATT 二进制 | 交 SDK 解码出逐指令事件 |
| `memory<pid>#offset=0x<base>&size=<size>.out` | code object ELF（**文件名直接编码 load_base/size**） | 解码所需 code object；**无需 results.db** |
| `<kernel>.kd_v0_kernel.txt` | kernel 元信息 | 辅助 |

### 关键：采集哪个 kernel 是**自动检测的，不写死**

> ⚠️ 本工程**面向各种 kernel/算法**，testcase 下的 gemm 只是开发期测试样例。**绝不能**把 kernel 名写死。

`dump_counters` 不依赖 `input.txt` 里固定的 kernel 过滤，而是：

1. 从**被优化的候选 `.s`** 自动检测 kernel 符号 —— `target.kernel_symbols(program)` 扫 `.amdhsa_kernel <name>` 指令
   （`harness/evaluator.py::detect_kernel_name`；也可用 `kernel_name=` 显式指定 / CLI `--kernel`）；
2. 把 `input.txt` 当作**纯 att 参数模板**（`TARGET_CU/SE_MASK/SIMD_SELECT/BUFFER_SIZE`…），剔除其中任何 `KERNEL=`/`DISPATCH=`/注释，
   注入 `KERNEL=<检测到的名字>`，写到 `_att_input.txt`，再 `rocprofv2 -i _att_input.txt`（`_write_att_config`）。

```python
ev = GpuTestcaseEvaluator(dir, target=Gfx942Target())   # kernel_name=None -> 自动检测
# dump_counters: detect_kernel_name(cand.s) -> "any_kernel" -> _att_input.txt: KERNEL=any_kernel
```

因此**换任何 kernel 都无需改配置**：检测到谁就抓谁。`input.txt` 现为模板（kernel 行是注释占位）。
> 若用 `DISPATCH=1`（最初的错误配置），会抓到 gemm 之前 HIP 运行时的 `__amd_rocclr_copyBuffer` 预拷贝、解码出 0 条有用指令——
> 这正是「按 kernel 名过滤」而非「按 dispatch 序号」的原因。

### 真机其余两个坑（已在代码里消化，rocm-7.2.1 实测）

1. **ATT 采样是非确定的，需重试**。单次采集随机，常常近乎空（同参数实测：一次 106KB、两次各 ~600B）。
   `dump_counters` 因此**重试至拿到真实 wave 数据**（`att_retries=6`，总 `.att` 字节 ≥ `att_min_bytes=8192` 即停），否则方向分析一半时间拿到空数据。

2. **rocprofv2 自带后处理会崩，但不影响我们**。rocprofv2 的 `att.py` 在采集完成后尝试加载 `librocprofv2_att.so` 做可视化，
   该库本机缺失 → 进程**退出码非 0**。但原始 `.att` 在崩溃**之前**已落盘，而我们用**自己的 SDK 解码器**，不依赖 rocprofv2 的后处理。
   因此 `dump_counters` **以「`.att` 是否存在」判成功**，忽略 rocprofv2 退出码。

3. **ATT 解码后端是独立包，要单独定位**（见 §3.1）。

---

## 2. 发现 dump 文件：`discover_dump` + 文件名解析 code object

`analysis/perf.py` 的纯函数（无需 ROCm，可单测）：

- `parse_codeobj_filename(name)`：用正则 `#offset=(0x..|\d+)&size=(\d+)\.out$` 从 `.out` 文件名直接解析 `(load_base, load_size)`。
  **这是 testft 相对通用文档的关键简化**：不读 `results.db`，code object 的 load 元信息全部来自文件名。
- `discover_dump(att_dir)`：扫描目录，分出三类文件，返回
  `{"att_files": [...], "code_objects": [(id, base, size, path), ...], "kernel_txt": [...]}`。
  `id` 用 `code_objects` 的出现序号（0,1,...），作为 `codeobj_load` 的 `load_id` 与 `Inst.pc.marker_id` 对应。

---

## 3. 解码：`decode_att`（SDK + ctypes）

机制与 `proj/amdgpu-dump-parsing.md` §3–§5 完全一致（`create → codeobj_load → trace_decode(callback) → destroy`，回调流式吐 `GFXIP/WAVE/INFO` 记录，`Inst._catstall` 低 8 位为 category、高 24 位为 stall）。testft 的差异/要点如下。

### 3.1 解码后端目录解析 `resolve_decoder_dir`（testft 新增）

`rocprofiler_thread_trace_decoder_create(handle, path)` 的 `path` 是**解码后端库 `librocprof-trace-decoder.so` 所在目录**——
它是**独立于 rocprofiler-sdk 的包**，**不一定**在 `/opt/rocm/lib`。找不到时 `create` 返回 `NOT_AVAILABLE`（即旧代码里的 `decoder_create failed`）。

`analysis/perf.py::resolve_decoder_dir(explicit=None)` 按以下顺序找到含该 `.so` 的目录：

```
explicit 入参  →  $TESTFT_ATT_DECODER_DIR  →  候选列表 _DECODER_DIR_CANDIDATES  →  兜底 /opt/rocm/lib
```

候选列表当前含 `/opt/rocm/lib`、`/opt/rocm/lib/rocprofiler-sdk`、`/mnt/sixifang/rtd-install/opt/rocm/lib`（本机实测后端所在）。
**换机器时**：把后端 `.so` 所在目录设进 `$TESTFT_ATT_DECODER_DIR` 即可，无需改代码。缺失时 `decode_att` 抛清晰错误并提示该环境变量。

### 3.2 结构体布局 / 生命周期

- 结构体（`_Pc/_Inst/_Wave/_DecoderHandle`）布局见 `amdgpu-dump-parsing.md` §4，**升级 ROCm 后须按头文件
  `/opt/rocm/include/rocprofiler-sdk/experimental/thread-trace/trace_decoder*.h` 重新核对**。本机 7.2.1 实测布局未变、解码正常。
- code object / att 字节缓冲、`@_CB` 回调对象在 `trace_decode` 期间必须保持引用（防 GC）。
- `librocprofiler-sdk.so` 用 `RTLD_GLOBAL` 加载。

### 3.3 输出

`decode_att(att, code_objects, decoder_lib_dir=None) -> (gfxip, [DecodedInst])`，
`DecodedInst = {cu, simd, slot, issue, duration, stall, category, marker_id, pc}`。
`parse(dump_dir, schema, decoder_lib_dir=None)` 对目录里每个 `.att` 解码并 `aggregate`。

---

## 4. 聚合 + 分类：从 stall 到 `direction`

### 4.1 `aggregate`（`analysis/perf.py`）

把所有 `DecodedInst` 按 **category** 和 **维度（dimension）** 折叠 stall：

```python
{
  "n_inst": 总指令数,
  "total_stall": 总 stall,
  "by_category_count" / "by_category_stall": 按 category(0..12),
  "by_dimension_count" / "by_dimension_stall": 按维度(下表),
}
```

### 4.2 category → 维度 schema（`isa/gfx942/perf_schema.py`）

`Target.perf_counter_schema()` 提供 gfx942 的映射（category 枚举见 `amdgpu-dump-parsing.md` §6）：

| category | name | dimension |
|---|---|---|
| 1 | SMEM | `scalar_mem` |
| 2 | SALU | `scalar` |
| 3 VMEM / 4 FLAT | | `memory` |
| 5 | LDS | `lds` |
| 6 | VALU（含 MFMA/WMMA） | `compute` |
| 7 | JUMP | `flow` |
| 0 NONE / 8 NEXT / 9 IMMED / 10 CONTEXT / 11 MESSAGE | | `none` |
| 12 | BVH | `compute` |

> **`IMMED(9)` 归入 `none` 是有意为之**：它是 `s_nop`/`s_waitcnt` 等「显式等待」本身，把「等待」当成瓶颈维度会循环论证。
> 因此一个已经调好的 kernel 常呈现「`none` 占比高、无单一热点」——这与 L3 搜索「重排难显著超 L1」的结论一致。

### 4.3 `classify`（`analysis/bottleneck.py`）→ `direction`

```python
direction = {
  "bottleneck": "lds"|"memory"|"scalar"|"scalar_mem"|"compute"|"flow"|"latency"|"none",
  "share":  top 维度占【信息维度】stall 的比例(0..1),   # 分母剔除 none（见下）
  "hints":  [针对该瓶颈的具体算子建议, ...],
  "stats":  {维度: stall, ...},                       # 原始，含 none
  "total_stall":      总 stall,
  "informative_stall":剔除 none 后的 stall,
  "none_fraction":    none 占总 stall 的比例,           # 透明展示
}
```

规则：忽略 `none` 维度后，stall 占比最大的维度即瓶颈；**若最大占比 < 40%（stall 弥散、无单一热点）→ `bottleneck="latency"`**（泛化建议）。

> ⚠️ **`share` 用「信息维度」口径（分母 = 剔除 `none` 后的 stall），不是 `total_stall`**（M6b 修复，见
> `proj/if/direction_signal_validation.md`）。早期 bug 用了含 `none`（GEMM core loop 上 `none` ~60%）的总分母，
> 导致任何真实维度都越不过 40% 阈值、`bottleneck` **恒为 `latency`、零区分度**。改为信息维度口径后区分度恢复
> （seed→`memory`、hoist/sink→`compute`）。验证还表明：**单次采集会抖、与 perf 相关性弱**——`direction` 只配当
> 先验，决策需**多次投票**（`search.driver.vote_direction`）、低置信回退固定阶梯，最终以实测 GFLOPS 拍板。

---

## 5. AI 怎样使用

### 5.1 一条命令拿 `direction`

```bash
python3.8 tools/eval_candidate.py testcase/shader/fp8gemm_blockscase_32mx1_32nx4.s --k 4096 --loop 20 --counters
```
真机实测输出（gemm seed，MI308X，2026-06 单次采集）：
```
  correct   : True
  perf      : 8770.1 GFLOPS  (15.304 us/loop)
  insts     : 11452  total_stall=62236
== DIRECTION (phase-3 analysis -> search/agent) ==
  bottleneck: compute (53% of stalls)           # 信息维度口径(剔除 none)
  stall by dimension:
    none     47124 (75.7%)   compute 8024 (12.9%)   memory 7036 (11.3%)   lds 52 (0.1%)
  next-round hints:
    - compute(MFMA/VALU)-bound: limited reorder gains; check MFMA packing/occupancy
```
> 注：`bottleneck=compute(53%)` 是**信息维度**占比（`8024 / (8024+7036+52) ≈ 53%`），
> 不是占 `total_stall` 的 12.9%——正是 M6b 修复后的口径。`none_fraction=75.7%`（多为 s_nop/s_waitcnt 显式等待，
> 这块手调 kernel 已塞满 MFMA），故 `compute` 瓶颈也只给出「重排收益有限、查 MFMA packing/occupancy」的诚实提示。

### 5.2 程序内拿 `direction`

```python
from harness.evaluator import GpuTestcaseEvaluator
from isa.gfx942.target import Gfx942Target
ev  = GpuTestcaseEvaluator("testcase", target=Gfx942Target(), total_loop=20, k=2048)
res = ev.evaluate("cand.s", with_counters=True)
d   = res.direction          # 见 §4.3
```

### 5.3 瓶颈 → 移动算子（AI 的决策表）

`direction.bottleneck` 直接映射到 `proj/if/ai_interface.md` §3 的移动原语：

| bottleneck | 含义 | 建议算子（在对应 region 上） |
|---|---|---|
| `lds` | ds_read 等 LDS 访问 stall 多 | `compact_kind(DS_READ, earliest=True)` 把读拉进更早的 MFMA 间隔；或冷 kernel 用 `distribute_evenly(DS_READ)` |
| `memory` | 全局 load stall 多 | `compact_kind(VMEM_LOAD, earliest=True)` 提早发 load，拉长 load→use 距离，增大与 MFMA 的重叠 |
| `scalar_mem` | s_load stall | 把 `s_load` 往 prologue 提早 / 合并标量 load |
| `scalar` | 标量 ALU 瓶颈 | 削减 loop 内冗余地址运算 / `s_*` |
| `compute` | MFMA/VALU 占满 | 重排收益有限——查 MFMA packing / occupancy（非纯序问题） |
| `flow` | 控制流开销 | 查 loop trip count / 分支密度 |
| `latency` | 弥散、无单一热点 | 提 ILP：`distribute_evenly` 把填充物铺到更多 MFMA 间隔 |

`direction.hints` 已经把上面这些写成可读建议；`direction.stats` 给各维度占比供更细的权衡。

> **AI 可以无视 hint**：`direction`/`hints` 是「性能启发（可错）」。若 AI 有自己的硬件知识库，
> 可完全不依赖它，改用**只读分析接口**（`ed.kind_of` 取每条类型、`ed.anchors`+`ed.order` 看逐 slot 间隔、
> `graph.legal_window`/`dist`/`latency_edges` 看可动区间与最小间距）自行决策布局——详见
> `proj/if/ai_interface.md` §2.3「只读现场」。合法性仍由 `legal_window` 拒非法 + `Verifier` + 真机数值兜底。

### 5.4 闭环

```
挑 region/算子(按 direction)
  → RegionEditor / span_editor 逐条移动        (ai_interface.md §3)
  → recompute(_cfg)                            (§4)
  → Verifier 静态校验                          (§5)
  → evaluate(with_counters) → 新 direction      (本文)
  → 比较 GFLOPS，接受/回退，进入下一轮
```

要点：
- **移动绝不会产出违反依赖的 kernel**（合法窗口兜底）；激进但合法的移动由 `recompute` + `Verifier` + **真机数值**三层兜底。
- ATT 是 **逐指令 stall 时间线**（不是经典 SPM 累加计数器），反映的是「这条指令等了多久」，正好用来定位**调度**瓶颈——与重排引擎天然对口。
- 已调好的 kernel 上 `direction` 多为 `latency`（弥散），说明纯重排空间已小；冷/未调 kernel 上瓶颈维度更突出，算子选择更有的放矢。

---

## 6. 环境前置 / 排错 checklist

1. [ ] ROCm 可用，`/opt/rocm/lib/librocprofiler-sdk.so` 存在（导出 `rocprofiler_thread_trace_decoder_*` 符号）。
2. [ ] **解码后端** `librocprof-trace-decoder.so` 可达：设 `$TESTFT_ATT_DECODER_DIR` 指向其目录（否则 `decode_att` 抛 `decoder_create failed`）。
3. [ ] kernel 名能从候选 `.s` 检测到（`.amdhsa_kernel`）或用 `--kernel`/`kernel_name=` 指定——**不要写死在 `input.txt`**。
4. [ ] rocprofv2 退出码可忽略，只看 `testcase/att/*.att` 是否生成。
5. [ ] 解码出 `n_inst > 0`；若为 0，多半是抓错 kernel（坑：kernel 名）或采样太空（已靠重试缓解）。
6. [ ] 升级 ROCm 后按 `trace_decoder*.h` 复核结构体布局（`amdgpu-dump-parsing.md` §4）。

> 纯逻辑（`parse_codeobj_filename` / `discover_dump` / `aggregate` / `classify` / `resolve_decoder_dir`）都有单测，
> 见 `tests/test_m4.py`，无需 GPU 即可跑。
