# testcase 对接方式（三阶段评测的落地依据）

> 对象：`client/poc_kl/fp8_blockscale_gemm/`（fp8 block-scale GEMM 样例，poc_kl/mi300/fp8_blockscale_gemm 的副本；
> 历史上曾在 `testft/testcase/`、`tune_case/poc_gemm/`）。
> 用途：作为 `harness/Evaluator` 三阶段真机评测（正确性 / 性能 / ATT 线程跟踪）的标准对接样例。M4 据此实装 GPU 评测器。
> **注意：GEMM 只是一个 client 的一个 case。本框架要适配各种项目，对接方式必须 client 无关——先读 §0 的工程红线。**
> client 契约与新增方法见 [`client/README.md`](../client/README.md)。

---

## 0. 工程红线：client 无关，**严禁在引擎里硬编码任何项目的命令 / test 参数**

本调优项目要适配**各种各样的项目、kernel 与各自的 test 方式**（poc_kl GEMM 的 exe + `m/n/k`、其他项目的 pytest 扫参或 op benchmark…）。**曾经犯过的错误**：在 tools 链路里把 GEMM 的 `gemm.exe` 和 `m/n/k` 当成
默认/写死，导致换 kernel 就得改引擎代码；之后又用"被测程序一定是 exe"的 `--testcase` 统一接口，项目一换测试方式就接不进来。
**以后不得再犯。** 红线如下：

1. **项目用 client 接入，不写死**：`tune.mjs` / `agent_session.py` / `validate_skills.py` / `eval_candidate.py`
   用 `--client <client/ 下的路径>` 选择项目；**怎么构建、怎么判正确、怎么计时只写在 `client/<项目>/client.py` 里**，
   引擎只消费 `EvalResult`。没有默认 client，**任何通用逻辑都不得假设它是 GEMM 或 exe**。
2. **test 入参原样透传，引擎不认识它们**：项目需要的 shape/形参一律放在 **`--` 哨兵之后**，由工具链
   **逐 token 原样透传**给 client（`ClientContext.params`）。引擎**不解析、不默认、不校验** `m/n/k`
   等任何 shape 参数。换 kernel 只改透传内容，例如 `-- m=2560 n=2560 k=256` → `-- --qhead 64 --ctx_len 128`。
3. **协议开关属于 client**：exe 协议的 `dump_result`（正确性 vs 性能模式）、`total_loop`（计时迭代数）、
   ATT 的 `KERNEL=<自动检测的符号>` 由 `harness.evaluator.GpuTestcaseEvaluator` 实现，只有选用它的 client 才会碰到；
   其它协议的 client 自己实现 `evaluate`。
4. **入口脚本跟着 client 走**：`client/<项目>/tune_script/*.sh` 的 CONFIG 块用 `CLIENT` / `SEED_REL` / `PARAMS`
   三个变量描述调优对象；换 case 只改这三行，脚本本体与 GEMM 无任何硬编码耦合。
5. **输出跟着 client 走**：运行时输出落 `client/<项目>/tune_out/`，不同项目互不混写。
6. **允许保留 GEMM 专用的，只有**：`client/poc_kl/` 内的 client 与样例本身、以及明确标注为 GEMM 实验/诊断的 dev 工具
   （如 `tools/search_loop.py`、`tools/hw_validate*.sh`）和单测 fixture。**通用 tune 流水线不在此列。**

> 校验自己有没有再犯：在 `tools/`、`harness/`、`agent/`、`search/` 里 grep `gemm`、`m=`、`n=`、`k=`、`poc_kl`、`.exe`，
> 通用链路里出现的应当只有"示例/注释"，绝不能是写死的业务逻辑。
> 设计原则同步登记在 `proj/README.md` v2 评审结论 §7；用法/参数全解见 `tools/sdk/README.md` 与根 `README.md`「调优用法」。

---

## 1. 文件清单

> 以下为 GEMM **样例**的具体文件/命令/常量（`client/poc_kl/fp8_blockscale_gemm/`）。它们描述的是
> "一个 exe 协议的 case 长什么样"，**不是框架对 GEMM 的硬编码**——通用链路如何无关地驱动任意 client，见 §0。

```
client/poc_kl/fp8_blockscale_gemm/
  cmd                                       # 编译/运行命令（见 §2）
  fp8gemm.cpp                               # host 测试程序（加载 .co、跑 kernel、判正确、计时）
  gemm.hpp                                  # check_result / check_result_eps 等
  common/                                   # 头文件（half.hpp、common_*.h 等）
  shader/fp8gemm_blockscase_32mx1_32nx4.s   # 被优化对象（重排引擎的输入/输出 .s）
  gemm.co                                   # 由 shader 汇编出的 code object
  gemm.exe                                  # 编译好的测试程序
  cpu_result.hex / gpu_result.hex           # CPU 参考 / GPU 输出（正确性比对）
```

## 2. 编译 / 运行命令（来自 `cmd`）

```bash
# 1) 汇编 shader -> gemm.co
/opt/rocm/llvm/bin/clang++ -x assembler -target amdgcn--amdhsa --offload-arch=gfx942 \
    ./shader/fp8gemm_blockscase_32mx1_32nx4.s -o gemm.co

# 2) 编译 host 测试 -> gemm.exe（只需一次；改 shader 不必重编）
/opt/rocm/bin/hipcc --offload-arch=gfx942 fp8gemm.cpp -o gemm.exe

# 3) 运行
./gemm.exe

# 4) perf 采集：ATT 高级线程跟踪（逐指令时间线）
rocprofv2 -i input.txt --plugin att auto -d ./att ./gemm.exe
```

> 第 4 步的"perf counter"实质是 **ATT / SQTT 线程跟踪**（逐指令 issue cycle / duration /
> stall / category），不是经典 SPM 累加计数器。解析方式见 `proj/amdgpu-dump-parsing.md`。

`input.txt`（ATT 采集配置）实测内容：

```
att: TARGET_CU=F
SE_MASK=0x0F
SIMD_SELECT=0xF
ISA_CAPTURE_MODE=2
BUFFER_SIZE=100
#KERNEL=
DISPATCH=1
```

`-d ./att` 把产物 dump 到 case 目录下的 `att/`，包含三类文件：

| 文件 | 含义 | 解析用途 |
|------|------|----------|
| `<kernel>.kd_v<N>_se<S>.att` | 各 Shader Engine 的 ATT 二进制 | 交 `librocprofiler-sdk.so` 解码出逐指令事件 |
| `memory<pid>#offset=0x<base>&size=<size>.out` | code object ELF（**文件名直接编码 load_base/size**） | 解码所需 code object；无需 results.db |
| `<kernel>.kd_v<N>_kernel.txt` | kernel 元信息 | 辅助定位 |

关键常量（`fp8gemm.cpp`）：
- kernel 符号 `HSA_KERNEL = "gemm_kernel_func"`；code object `HSACO = "gemm.co"`。
- 固定 `hipSetDevice(1)`（第 2 张卡）。
- 默认 shape `m=n=k=128`，`sub_m=32 / sub_n=128`（**须与 kernel 对应**），`ks=1`。
- 启动维度：`gdx=(n+sub_n-1)/sub_n * ks`，`gdy=(m+sub_m-1)/sub_m`，block `256x1x1`。
- 命令行可传 `m= n= k= sub_m= sub_n= ks= dump_result= total_loop=` 覆盖默认值。

## 3. 三阶段评测映射（Evaluator 实现依据）

| 阶段 | 怎么做 | 判据 / 解析 |
|------|--------|-------------|
| **assemble** | 跑 §2 步骤 1（用候选 `.s` 覆盖 shader 路径后汇编） | clang++ 退出码非 0 = 汇编失败 |
| **1 正确性** | `dump_result=1`（默认；此时强制 `total_loop=1`）运行 `./gemm.exe` | stdout 含 `#TEST PASSED` → 通过；含 `#TEST FAILED` → 失败。亦可比对 `gpu_result.hex` vs `cpu_result.hex`。当前用 `check_result_eps`（ks≠0，容差 0.001） |
| **2 性能** | `dump_result=0`（保持 `total_loop=20`、无 CPU 参考、计时更干净）运行 | 解析 stdout 行 `m:%d,n:%d,k:%d,time: %.6f,gflops:%.3f` 取 `time`(ms/loop) 与 `gflops` |
| **3 ATT dump** | `rocprofv2 -i input.txt --plugin att auto -d ./att ./gemm.exe` | 产物在 `./att/`；`analysis/perf.py` 用 `librocprofiler-sdk.so`（ctypes）把 `*_se*.att` + `memory*#offset=&size=.out` 解码成逐指令事件（issue/duration/stall/category），`analysis/bottleneck.py` 按 category+stall 分布给瓶颈分类与方向 hints |

> 计时说明：`fp8gemm.cpp` 在 `dump_result=1` 时把 `total_loop` 钉成 1 且 `warm_ups=0`，只适合判正确；测性能应单独以 `dump_result=0 total_loop>=20` 跑一遍。
>
> ATT 解析说明：code object 的 `load_base`/`load_size` **直接从 `.out` 文件名解析**（`offset=`/`size=`），无需 `results.db`；解码协议、结构体布局、category 枚举详见 `proj/amdgpu-dump-parsing.md`。

## 4. 重排引擎如何接入（不改 host 程序）

引擎只改 **shader `.s`**，host 测试与 `.co` 名字不变：

1. 引擎产出候选 `cand.s`（无损回写 + FixupPass 流水线）。
2. 用 `cand.s` 跑 §2 步骤 1 汇编成 `gemm.co`（覆盖）。
3. `gemm.exe` 已编译好，直接跑：先阶段 1 判正确，再阶段 2 计时，必要时阶段 3 dump counter。
4. 把 `(correct, time_us/tflops, counters, direction)` 装进 `EvalResult` 回流搜索/agent。

→ 即 `harness/evaluator.py` 的 GPU 实现：`assemble()` = 步骤 1；`check_correctness()` = 运行 `gemm.exe`(dump_result=1, 抓 `#TEST PASSED`)；`measure_perf()` = 运行(dump_result=0, 抓 `time:`/`gflops:`)；`dump_counters()` = 步骤 4 的 `rocprofv2 ... -d ./att`，返回 `./att` 目录路径供 `analysis/perf.py` 解码。

## 5. 前置条件 / 注意

- 需要安装 ROCm（`/opt/rocm`）与可用 GPU；本机 `python3` 默认 3.6（用 `python3.8` 跑引擎/测试）。
- ATT 解码需 `/opt/rocm/lib/librocprofiler-sdk.so` 且 `LD_LIBRARY_PATH` 含 `/opt/rocm/lib`；
  结构体布局随 ROCm 版本可能变化，升级后须按 `proj/amdgpu-dump-parsing.md` §4 重新核对。
- `input.txt` 用 ATT 模式（非经典 counter 列表），现为**纯参数模板**：kernel 由 `evaluator` 从候选 `.s` 自动检测后注入
  `_att_input.txt`，**不在 `input.txt` 写死**（工程面向各种 kernel，gemm 只是开发期样例）。
- `sub_m/sub_n` 必须与 kernel 内部 tiling 对应，换 kernel 时同步改。
- M0 解析器已对该 shader（1120 行）验证 **parse→emit 逐字节无损**；kernel 符号 `gemm_kernel_func` 解析一致。

## 6. 三阶段闭环（真机打通，rocm-7.2.1）

`tools/eval_candidate.py <cand.s> [--k] [--loop] [--counters]` 一条命令跑通 assemble→correct→perf→ATT→`direction`：

```
$ python3.8 tools/eval_candidate.py /tmp/cfg.s --k 2048 --loop 5 --counters
  assembled : True
  correct   : True
  perf      : 5429.5 GFLOPS  (12.360 us/loop)
  insts     : 6788  total_stall=15376
== DIRECTION (phase-3 analysis -> search/agent) ==
  bottleneck: latency (35% of stalls)
  stall by dimension: none 38.3% / memory 35.4% / compute 25.5% / lds 0.8% ...
  next-round hints: - latency-bound ... distribute_evenly fillers across more MFMA gaps
```

打通过程踩到三个真机坑（已在代码里消化）：

1. **抓错 kernel**：`DISPATCH=1` 抓的是 gemm 前的 `__amd_rocclr_copyBuffer`。**正解是按 kernel 名过滤，且名字自动检测**——
   `evaluator` 从候选 `.s` 的 `.amdhsa_kernel` 检测 kernel 符号（`target.kernel_symbols`），注入 `KERNEL=<name>` 到一份
   生成的 `_att_input.txt`（`input.txt` 仅作 att 参数模板，**不写死 kernel**）。换任何 kernel 都无需改配置。详见 `proj/att_parsing_and_ai_usage.md` §1。
2. **解码后端是独立包**：`rocprofiler_thread_trace_decoder_create(path)` 要在 `path` 下找 `librocprof-trace-decoder.so`，
   它**不随 rocprofiler-sdk 安装**（本机在 `/mnt/sixifang/rtd-install/opt/rocm/lib`）。`analysis.perf.resolve_decoder_dir`
   按 `$TESTFT_ATT_DECODER_DIR` → 候选目录搜索；缺失时报清晰错误。
3. **rocprofv2 自带后处理崩溃**：其 `att.py` 加载 `librocprofv2_att.so` 失败（缺包），但**在原始 `.att` 落盘之后**——
   我们用自己的 SDK 解码器，故 `evaluator.dump_counters` 以「`.att` 是否存在」判成功，忽略 rocprofv2 退出码。

> `direction` 即 M6 搜索 / M7 agent 的【先验】输入：`{bottleneck, share, hints, stats, total_stall, informative_stall, none_fraction}`。
> 其中 `share` 用**信息维度口径**（分母剔除 `none`，M6b 修复，见 `proj/if/direction_signal_validation.md`）。当前 `category 9=IMMED`
> （s_nop/s_waitcnt 等显式等待）归入 `none` 维度（core loop 上常 ~60%），故 `none_fraction` 偏高；剔除后才有区分度。
> `direction` 可错、需多次投票、可被 AI 无视（改用 `ai_interface.md` §2.3 只读接口）——最终以实测 GFLOPS 拍板。
