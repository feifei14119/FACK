# aiter HSA client

用 Git submodule 引用 [ROCm/aiter](https://github.com/ROCm/aiter)，上游代码位于
`client/aiter/upstream/`，适配层在该目录外维护。初始锁定 main 的提交
`2abf8aaa44f9d81c88d6153024b21e6931c7f906`；普通初始化按 gitlink 检出，**不使用 `--remote` 自动追踪 main**。

| client SPEC | 默认 kernel | 约束 |
|---|---|---|
| `aiter/hsa/gfx942` | FP8 blockscale BF16 GEMM，BpreShuffle 32×128 | splitK=1，N/K 为 128 的倍数 |

这是一个可供真机验证的具体算子驱动，其他 HSA kernel 通过 manifest + driver 扩展。
仅替换 symbol 并不能给不同算子自动生成参数和正确性参考。
默认为 M=N=256、K=1024；正式性能测量应指定实际 workload 的 shape。

## 在目标机器准备

本次接入只做静态检查，尚未运行这些命令、构建或验证 GPU 结果。以下命令均在仓库根执行。

```bash
bash tools/init_aiter.sh
bash tools/init_selfstudy.sh
```

`init_aiter.sh` 初始化锁定的 aiter 及其嵌套依赖，并设置 HSA 稀疏检出规则；不安装 Python 包、不编译、不自学。
FACK 只检出 `upstream/hsa/gfx942/` 与 HSA 根目录的构建脚本，保留上游共享 Python/C++ 源码。
稀疏检出限制的是 HSA 工作区；上游 Git 对象及共享源码仍可能包含其他架构定义，FACK 不提供其调优入口。
按锁定版本的 [上游安装说明](upstream/README.md) 准备 ROCm PyTorch、Triton、aiter 的 Python/JIT
依赖（包括 pandas、numpy、ninja、pybind11 等）。可使用已有兼容环境；runner 始终从 submodule
导入 aiter 源码，不能用另一个已安装版本替代。引擎可用 Python 3.8；`--python` 指向满足上游要求的
Python（推荐与上游 CI 一致的 3.12 环境）。首次评测可触发 aiter JIT 构建。

ROCm LLVM 工具通过 `ROCM_LLVM_BIN` 指定，需要 clang、ld.lld、llvm-readelf、llvm-objdump。

先在相应 GPU 机器准备 seed，下面以 gfx942 为例：

```bash
export ROCM_LLVM_BIN=/opt/rocm/llvm/bin
python3 client/aiter/prepare.py gfx942 \
  --out client/aiter/tune_out/seeds/gfx942.s
```

prepare 从 manifest 指定的上游 `.co` 导出包含 KD 和 metadata 的 `.s`，回编并比较指令、KD、metadata，
成功才发布 seed，并记录 `.s.json` 来源摘要。`--exact` 要求 `.text` 字节一致；默认允许反汇编一致的
编码差异。不会覆盖已有 seed，不改写上游 `.co`。通用 ELF/回编逻辑在 `tools/co2s.py`，
FACK 的转换入口只接受 gfx942。回编通过后仍需做真机数值校验。

## 校验与调优

先评估未修改的 seed，查看 `correct=True` 和有效时间，再进入调优：

```bash
HIP_VISIBLE_DEVICES=0 python3 tools/eval_candidate.py \
  client/aiter/tune_out/seeds/gfx942.s --client aiter/hsa/gfx942 -- \
  --python /path/to/rocm-env/bin/python --m 256 --n 256 --k 1024
```

SDK 可以直接使用同一 SPEC 和参数，不需要修改已有工作流：

```bash
HIP_VISIBLE_DEVICES=0 node tools/sdk/tune.mjs \
  client/aiter/tune_out/seeds/gfx942.s --client aiter/hsa/gfx942 --rounds 5 -- \
  --python /path/to/rocm-env/bin/python --m 256 --n 256 --k 1024
```

默认继续跳过自学，引用 selfstudy 已导出的 skills_out。

`--` 后的参数：`--manifest PATH`（默认架构目录内的 manifest）、`--python PATH`、
`--m/--n/--k`、`--seed`（123）、`--warmup`（5）、`--iters`（采用引擎 loop，通常 20）、
`--samples`（5）、`--timeout`（1800 秒，每个构建/runner 子进程的上限）。
运行时输出统一保留在 `client/aiter/tune_out/eval-*/`：候选 `.co`、build.log、runner.log、request.json、result.json。
JIT 缓存在 `tune_out/jit/`，按架构、已声明上游资源和工具摘要隔离，可跨候选复用。
候选数较多时可在调优结束后自行归档/清理 tune_out。

## 评测约定

- 每次评测新建 HSA overlay，选定 `.co` 从候选 `.s` 编译而来，其余同架构 HSA 文件指向上游。
  使用新 runner 进程，避免复用已装载的候选。汇编按 seed 的完整 target id 与 code-object version 进行。
- runner 导入 submodule 的 aiter 后修正环境变量和已导入模块的 `AITER_ASM_DIR`，在调用算子前生效。
  显式传入 manifest symbol，并要求 aiter C++ `LoadKernel` 日志指向该候选路径。
  这是主机加载路径证据，`build_evidence.loaded_code_object` 仍为 `unverified`，不宣称完成 GPU dispatch 证明。
- 两组固定种子的有符号随机输入，使用未 shuffle 数据构造独立 FP32 参考再转 BF16，比较完整输出。
  比较前将输出填为 NaN，未写出、非有限值、shape 错误或超出 manifest 容差均不能通过。
  当前容差是显式的起始配置，尚待真机验证，不会自动放宽。
- 数值通过后预热并捕获 HIP graph，以 event 测量重复调用，取多组中位数除以调用次数。
  输入生成、参考计算、shuffle、JIT 和正确性检查不计时；返回的是 driver `run()` 的 GPU graph 时间。
  计时后清空输出再 replay，重复完整校验。TFLOPS = driver FLOP 数 / 时间。
- crash、timeout、缺失日志/报告、构建或资源摘要变化均不给出可接受的性能结果。
  timeout 会终止 runner/JIT 的进程组。数值失败不重试。
- 当前不采硬件 counters/ATT；请求 counters 时明确返回不可用。图捕获不受支持也会明确失败，
  不静默切换到计量口径不同的方式。
- identity 只哈希显式声明的文件、工具和允许的环境变量，不启动 Python GPU 环境。
  它不覆盖整个 Python 环境、所有传递依赖、JIT 二进制或硬件状态；正式比较需固定真机环境。

## 扩展其他 HSA kernel

在架构目录旁维护自定义 manifest 和 driver，通过 `--manifest` 选取（prepare 也传同一个 manifest）。
`co` 是相对 `upstream/hsa/<gfx>/` 的路径；`symbol` 必须与 `.s` 的 descriptor 一致。
可选 `catalog` 验证上游 CSV 的 symbol/co 对应关系，`selection` 校验 dtype/preshuffle 等字段。
`driver` 路径相对 manifest；`inputs` 原样传给 driver，CLI shape 参数可覆盖对应键。
`resources` 映射 driver 的附加输入文件（相对 manifest），`upstream_resources` 列出相关上游源码，加入 identity。

driver 只需实现：

```python
def prepare(inputs, symbol, seed):
    # 在这里构造输入、独立参考和输出缓冲区；run() 必须调用明确选定的 symbol。
    return {
        "run": launch_selected_kernel,       # 无参数，不包含输入生成或参考计算
        "outputs": [output_tensor],           # 所有浮点 GPU 输出，支持 NaN 填充
        "reference": [independent_reference], # 与输出同 shape，独立存储
        "flops": operation_count_per_call,    # 正数，用于 TFLOPS
    }
```

driver 必须支持重复调用和 HIP graph capture；涉及额外 kernel、临时缓冲、split reduction 的算子，
应在 driver 中完整实现并说明计时范围。参考不得调用被替换的候选路径。
更新上游 gitlink 后重新核对 driver API、CSV 和 symbol；不能假定 main 的未来版本兼容。
