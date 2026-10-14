# GEAK 借鉴实施记录：P0-d，client 身份与构建证据

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

日期：2026-10-13。承接 [P0-c 配对确认](./geak-P0c-paired-validation.md)，补充稳定外部测试资源身份、
独立构建产物与逐次文件校验。目标仍为现有单 kernel 的指令重排；没有修改 ISA、修补规则或正确性容差。

**本批只验证 CPU 协议。文件摘要说明磁盘上观察到的字节，不证明 GPU 实际装载了该 `.co`。**
没有 gfx942 真机正确性、性能、噪声或装载验证。

## 1. 可选 client 身份接口

旧 client 只实现 `make_evaluator(ctx)` 仍可工作。新 client 可以声明只读身份输入：

```python
def identity(ctx):
    return {
        "resources": {
            "test_executable": os.path.join(ctx.case_dir, "test.exe"),
            "reference_script": "/external/project/check.py",
            "optional_tool": None,
        },
        "environment": ["ROCM_LLVM_BIN", "HIP_VISIBLE_DEVICES"],
    }
```

[`Client.identity(**context_kw)`](../../client/__init__.py) 调用该 hook，再通过
[`harness.evidence.collect_identity`](../../harness/evidence.py) 生成稳定 JSON 快照。
hook 接受与 `make_evaluator` 相同的 ctx；必须只声明显式文件与公共环境输入，不执行 GPU/测试/版本命令，
不导入外部测试代码，也不声明凭证文件。这是可信 client 的接口约定，并不是 Python 沙箱。

loader 只接受 `resources` 和可选 `environment` 两个字段。环境变量名必须在
`ENVIRONMENT_ALLOWLIST` 中；超出白名单直接拒绝，不读取其值。不保存整个进程环境。
环境变量不存在时记录 `status=missing`，存在时记录 `status=present` 与值。

文件记录包括绝对路径、解析符号链接后的路径、SHA-256 与大小。只哈希明确声明的普通文件，不遍历目录；
文件摘要分块读取，前后核对文件属性与路径，避免把读取途中变化当成稳定身份。文件时间戳不进入稳定身份。
文件状态为 `present`、`missing`、`unresolved`（路径为 None）、`unreadable`、`not_regular` 或
`changed_during_read`。所有资源存在时顶层为 `available`，否则为 `partial`。

无 hook 的 client 返回 `schema_version=1, status=unavailable, reason=client_identity_not_declared`。
未知信息保持未知；不会为了补齐身份而触发 GPU、安装依赖或自动修复外部仓库。
单纯缺失资源不自动等于数值失败，也不阻止 CPU 初始化/观察；真正评测仍取决于 client 的构建和正确性返回值。

`tools/tune_run.py` 将快照纳入冻结的 `evaluation_contract`。run 的每次 client 调用前，以及原始结果持久化后，
都重新验证契约。稳定资源字节、路径、存在性或所记录的公共环境改变时，旧样本不能继续作为同契约样本。
新建 run 使用新身份；没有把旧 run 的未知资源自动补认成已验证。

## 2. poc_kl 声明的范围

[`client/poc_kl/client.py`](../../client/poc_kl/client.py) 声明：

| 范围 | 资源 |
|---|---|
| 公共 | client 实现、按 seed 架构实际选择的 assembler/linker 路径与字节、运行时公共环境 |
| GEMM | `gemm.exe` 与稳定 ATT 模板 `input.txt` |

FACK 工具选择沿用 gfx942 的 clang++ 路径；优先 `/opt/rocm/llvm/bin/clang++`，缺失时查找 PATH。
身份采集不运行 `--version`，也不执行外部 Python。
生成的 `.co`、临时输入、`att/` 与日志不进入冻结资源列表，否则正常评测自身会改变契约。

这是显式资源集，不是完整依赖闭包。torch/aiter 的动态导入、原生共享库、驱动、GPU 身份/频率以及其他
未声明依赖仍未知。修改未声明依赖可能不被这些摘要检测；不能把 `available` 理解为完整环境证明。

## 3. 每次 evaluate 的构建证据

[`GpuTestcaseEvaluator`](../../harness/evaluator.py) 每次在 case 目录下创建新的临时构建目录，
将输出写入初始不存在的临时文件。成功产生普通文件后，原子替换被测程序约定加载的 `.co` 路径；
构建失败或编译器返回成功但没有生成输出时，不启动正确性/计时，也不复用旧 `.co`。
临时目录在调用结束时清理，失败不会破坏旧产物。

每个返回的 `EvalResult.detail.build_evidence` 包含：

| 字段 | 意义 |
|---|---|
| `source_before` / `source_after_build` / `source_after_evaluation` | 构建前、构建后、评测后的源文件身份 |
| `identity_before` / `identity_after_build` / `identity_after_evaluation` | 对应时点的稳定 client 资源快照 |
| `artifact_after_build` / `artifact_after_evaluation` | 实际返回构建产物路径的摘要 |
| `build.strategy` | 内置 GPU evaluator 为 `fresh_output_atomic_replace`；自定义 assemble 为 `client_defined` |
| `build.staged_artifact` | 本次临时构建文件的路径与摘要；该路径随后已被移动/清理，不是永久归档 |
| `checks` / `status` | 源稳定、身份稳定、产物存在且稳定、安装产物与临时输出一致；`consistent` 或 `invalid` |
| `loaded_code_object` / `scope` | 固定标明 `unverified` 和磁盘证据范围 |

源文件在构建时改变、产物未生成或资源在构建时改变，会在正确性启动前停止。
评测期间变化会使该次样本无效：保留 `reported_result` 中原始 correct/time/score，清空对外有效的
correct/time/score，并写 `evidence_error`。因此身份变化不归为 `incorrect`，也不能进入有效性能汇总。
稳定条件下真正的 `correct=False` 仍短路并保留原有数值失败语义。计数器异常依旧是可选失败，证据仍保存。
`CompileOnlyEvaluator` 同样记录源/产物摘要，correct 与性能仍为空。

不同字节的产物可能来自同源不同工具链；相同摘要的产物也可能由多次独立构建产生。
临时目录路径区分构建调用，SHA 区分内容。`.co` 的最终固定路径会被下一次调用覆盖，日志中保存的是
当时摘要与路径，不是所有 `.co` 字节的永久归档；源汇编仍遵循 run 的不可变归档机制。

这些检查只比较观察时点，无法排除文件在两个检查之间被改写后又恢复，也不能证明测试进程没有内部缓存、
没有选择另一份 `.co`，或 GPU 确实执行了所记录的产物。final 的含义仍是配置协议对 client 返回值的结论。

## 4. CPU 验证

[`unittests/test_client_evidence.py`](../../unittests/test_client_evidence.py) 使用真正的子进程调用，
用临时 Python 可执行文件模拟 clang++ 和 GEMM exe；不访问 GPU、不改工具链安装、不导入外部测试。
覆盖每轮新构建、无输出时拒绝旧 `.co`、构建期间源改写、评测期间源/产物/脚本/环境变化、数值失败短路、
异常后的证据保留、缺失资源、普通文件边界、只读身份、秘密环境不收集以及旧 client 兼容。

针对性命令：

```bash
python3 -m pytest -q unittests/test_client_evidence.py unittests/test_client.py unittests/test_m4.py
```

原项目原始测试集合的历史结果（范围大于上述 FACK 命令）：**101 passed，1 skipped**，耗时 1.61 秒。实际解释器为 Python 3.12.3。
完整仓库回归与控制器契约集成测试由本阶段主代理汇总；不以这些 CPU 检查声称目标 GPU 收益或正确性。

主代理集成验收：控制器在调用前及原始返回持久化后校验冻结的 client 契约；新增 2 项契约测试通过。
完整 CPU 回归：**590 passed，3 skipped，13 subtests passed，3 failed**（62.23 秒）。
原项目当时的 3 项失败属于本副本已排除的专属模块。
稳定资源哈希在 client 性能计时之外进行，但会增加整体调优的墙钟开销。
