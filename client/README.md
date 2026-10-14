# client/ —— 调优项目接入层

FACK 引擎只认识一个评测契约（`harness/evaluator.py`）：给它一个候选 `.s`，
拿回一个 `EvalResult`（编译成功？结果正确？耗时 / TFLOPS？可选的计数器与方向）。
**某个项目怎么构建、怎么判正确、怎么计时，全部由 client 负责。** 不同项目差异很大：
poc_kl 的 GEMM 是一个带 `m=/n=/k=` 的 exe，其他项目可能采用 Python op benchmark。所以不为它们定统一的命令行接口，每个项目自己写一个 client。

```
client/
  __init__.py              加载器：resolve(spec) / list_clients()；python3 -m client list|resolve
  poc_kl/                  一个 client = 一个含 client.py 的目录
    client.py              make_evaluator(ctx) [+ describe(ctx)]
    fp8_blockscale_gemm/   一个 case：poc_kl/mi300/fp8_blockscale_gemm 的副本（exe、源码、seed shader）
    tune_script/           该 client 的一键调优脚本（CONFIG 块里写 CLIENT / SEED_REL / PARAMS）
    tune_out/              该 client 的全部运行输出（gitignore）
  aiter/                   HSA client，upstream/ 是 ROCm/aiter submodule；见 aiter/README.md
```

## 选择 client：spec

所有入口都用 `--client SPEC` 选择 client，SPEC 是 `client/` 下的相对路径：

| SPEC | client.py | ctx.case |
|---|---|---|
| `poc_kl/fp8_blockscale_gemm` | `client/poc_kl/client.py` | `fp8_blockscale_gemm` |
| `poc_kl` | `client/poc_kl/client.py` | `""`（poc_kl 会报"没有这个 case"） |
| `aiter/hsa/gfx942` | `client/aiter/client.py` | `hsa/gfx942` |

从 SPEC 目录往上找，**最近的 `client.py` 生效**。一个项目的多数 case 共用项目级 `client.py`，
某个 case 的协议与兄弟 case 不同时，可以在 case 目录里放自己的 `client.py`
（这时它就是一个独立的 client，输出落在 `<case>/tune_out/`）。
`client/` 前缀和绝对路径也都接受。查看已有 client：`python3 -m client list`。

独立持久化入口 `tools/tune_run.py init SEED --client SPEC ... -- PARAMS` 在初始化时冻结 SPEC 和
透传参数，后续 `eval RUN CANDIDATE` 从 manifest 读取，不重复接收 `--client` 或测试参数。
它检查 `client.py` 摘要，在 client 调用前扣预算并逐次保存结果；原始 baseline 必须先通过筛选。
用法和当前限制见 [P0-b 记录](../proj/steps/geak-P0b-persistent-run.md)，默认 SDK 流程暂未迁移。
后续 [P0-c](../proj/steps/geak-P0c-paired-validation.md) 增加显式配置的 `confirm` / `final`：
每个配对侧都会使用新工作 `.s` 和新 evaluator 对象，但 client 仍须保证每次构建/装载所给候选。
新对象不能替代 `.co` 装载证明，协议通过也不意味着硬件环境与统计假设已获验证。

## client.py 契约

```python
def make_evaluator(ctx):          # 必须
    """返回一个 Evaluator：至少实现 evaluate(s_path, with_counters=False) -> EvalResult"""

def describe(ctx):                # 可选：一句话说明这个 case 测什么、参数什么意思
    ...
```

`ctx`（`client.ClientContext`）提供：

| 字段 | 含义 |
|---|---|
| `spec` / `name` / `case` | 规范化的 SPEC；client 名（`client.py` 所在目录）；SPEC 在 client 目录下的剩余部分 |
| `client_dir` / `case_dir` / `out_dir` | `client.py` 目录；SPEC 目录；`<client_dir>/tune_out` |
| `seed_src` / `target` | seed kernel 文本；对应的 ISA Target（arch 取自 `.amdgcn_target`） |
| `params` | `--` 之后的参数，**原样**透传；引擎从不解析 |
| `loop` | 性能重复次数提示（`--loop`） |
| `kernel` | 显式指定的 kernel 符号（`--kernel`），否则 client 自己决定（通常从 `.s` 自动识别） |

`EvalResult` 的约定（引擎靠它做闸门和记录）：

- `compiled=False`：候选构建失败，`detail["error"]` 写原因。
- `correct`：`True` / `False`；`None` 表示没有跑正确性检查（引擎不会把它当成通过）。
- `tflops`：越大越好的性能指标，引擎用它和 baseline 比较。没有 FLOPS 概念的项目可以
  用 `1 / time` 之类的单调量，并在 `detail` 里写清楚。`time_us` 仅供展示。
- `with_counters=True` 时可选填 `counters` / `direction`（`analysis/bottleneck.py` 格式）。
  做不到就留空，并在 `detail["counter_error"]` 说明；引擎会把方向当成没有。

client 必须保证**评测前把候选 `.s` 装进被测程序**（例如汇编成 exe 加载的 `.co`），
并且多次评测之间互不干扰。引擎不关心这些产物放在哪里，但约定贴着 kernel 的运行产物
（`.co`、`att/`、`*.hex`）放在 case 目录里，其余输出放在 `out_dir`。

## 可复用的积木

- `harness.evaluator.GpuTestcaseEvaluator`：poc_kl 经典 exe 协议，即 `<case>/<exe>`
  加载 `<exe stem>.co`。正确性用 `dump_result=1` 判（看是否输出 `#TEST PASSED`），
  性能用 `dump_result=0 total_loop=N` 从 `time: .. gflops: ..` 解析；
  ATT 计数器在 gfx942 上用 rocprofv2。
  只要一个项目也遵循这套协议，它的 client 就是 `poc_kl/client.py` 那样的几行代码。
- `harness.toolchain`：`assemble_codeobject(s, co, arch)` / `arch_of(s)`。
- `harness.evaluator.parse_correctness_stdout` / `parse_perf_stdout`：可单测的 stdout 解析。

协议不同的项目（pytest 扫参、Python benchmark、远程机器……）自己实现 `evaluate` 即可。
建议把输出解析写成纯函数，在 `unittests/` 里离线测试。

## 新增一个 client（以 my_project 为例）

1. `mkdir client/my_project`，写 `client/my_project/client.py`，实现 `make_evaluator(ctx)`。
2. 需要随仓库携带的 case 资源（seed `.s`、小型驱动程序）放 `client/my_project/<case>/`。
   外部仓库里的大项目不用拷贝，在 `client.py` 里用路径或环境变量指过去即可。
3. 自检：`python3 -m client resolve my_project/<case>`，然后
   `python3.8 tools/eval_candidate.py <seed.s> --client my_project/<case> -- <params>`。
4. 可选：仿照 `poc_kl/tune_script/` 写一键脚本。

## 输出（`<client>/tune_out/`，gitignore）

| 路径 | 内容 |
|---|---|
| `experiments.log` | 每次 commit 的真机记录（`agent/knowledge.py` 的 `log_experiment`） |
| `tune_shaders/` | 每次 commit 的候选 `.s` 存档 |
| `runs/<run-id>/` | 默认 SDK / tune_run 的 manifest、权威状态、不可变汇编、工作批次及 transcript |
| `runs/<run-id>/report/` | 从状态导出的 JSON/Markdown、筛选/确认/final 分层副本；最终前没有 selected.s |
| `sdk-inputs/<run-id>/attempt-*/` | SDK 初始化前的原始输入快照与 .co 转换产物 |
| `tune_result/` | `tools/tune_summarize.py` 的汇总和最佳 kernel |
| `skills/` | 在线归纳的候选 skill（人工审核后再手工拷进 `knowledge/engine/skills/`） |
| `<kernel>_<region>_dag.jsonl` | `observe --compact` 的完整 DAG 旁路文件 |

不带 client 的纯 CPU 运行（`observe --no-direction`、库调用）写到
`agent/knowledge.py` 的 `DEFAULT_OUT_STORE`（系统临时目录下的 `fack_tune_out`），不进仓库。

## 可选 client 资源身份与持久化评测

client 可实现只读 `identity(ctx)`，声明稳定测试程序、脚本、编译器文件和允许记录的公共环境变量。
run 将解析后的路径/摘要/存在性冻结到契约，每次调用前后检查漂移；缺少 hook 明确记为 unavailable。
接口、环境白名单、fresh build 行为和磁盘证据边界见 [P0-d 记录](../proj/steps/geak-P0d-client-evidence.md)。
磁盘 `.co` SHA 不能代替 GPU 装载证明，外部依赖闭包与真实设备仍需 client/真机补充验证。

持久化模式中 profile 是显式、另计费的调用，必须沿用同一 client 和冻结参数；profile 数据不作为
screen/confirm/final 的性能样本。一次 evaluate 可能包含多次 launch、正确性程序内部重试与 profiling，
框架的 eval-call 计数不等同于精确 GPU launch 数。

## aiter HSA 接入

已实现 submodule、独立候选编译、完整数值比较和 GPU graph 计时。初始化、seed 准备、架构入口与扩展协议见 [aiter/README.md](aiter/README.md)。
本次只做静态检查；在目标真机校验 seed 后再开始调优。
