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
用法和当前限制见 [P0-b 记录](../proj/steps/geak-P0b-persistent-run.md)；默认 SDK 已使用这个持久化入口。
后续 [P0-c](../proj/steps/geak-P0c-paired-validation.md) 增加显式配置的 `confirm` / `final`：
每个配对侧都会使用新工作 `.s` 和新 evaluator 对象，但 client 仍须保证每次构建/装载所给候选。
新对象不能替代 `.co` 装载证明，协议通过也不意味着硬件环境与统计假设已获验证。

## client.py 契约

```python
def make_evaluator(ctx):          # 必须
    """返回一个 Evaluator：至少实现 evaluate(s_path, with_counters=False) -> EvalResult"""

def describe(ctx):                # 可选：一句话说明这个 case 测什么、参数什么意思
    ...

def agent_profile(ctx):           # 可选、只读：技能、workload 和必需验证
    ...

def publication_candidate(report): # 可选、只读：定位 final 实测产物；不编译、评测或提交 Git
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

## 为通用 agent 声明工作流与验证

可选的 `agent_profile(ctx)` 将项目经验和硬性验收分开声明。它只读文件，不启动 evaluator、
编译或 GPU。外部 manager 与 SDK 使用同一个入口：

```bash
# 准备环境与选择 workload 前，读取规划技能
python3 -m client guidance aiter/hsa/gfx942
# 已选择 workload 后，读取实际技能与必需验证；仍不执行 GPU
python3 -m client guidance aiter/hsa/gfx942 --seed path/to/seed.s -- --manifest path/to/workload.json
```

client hook 可返回以下字段，均可省略：

```python
return {
    "arch": "gfx942",  # 必须与 seed 和显式 --arch 一致
    "skills": ["knowledge/skills/my-project-tuning/SKILL.md"],
    "workload": {"inputs": {"size": 1024}},  # 项目自己的参数与来源
    "instructions": ["先验证原始 seed；按所选 workload 比较"],
    "validation": {
        "metrics": {"benchmark": {"unit": "us", "direction": "lower"}},
        "primary_metric": "benchmark",
        "required_checks": ["reference_output"],
        "recommendation_scope": "workload",
        "associated_workloads": "not_applicable",
    },
}
```

尚未绑定 workload 时可以返回 `requires_workload: True`，省略 validation；规划入口仍返回技能，
但不能初始化调优 run。这样新环境可以先按 skill 准备依赖、生成 workload，再绑定严格契约。
aiter 已使用此机制；通用层不解析 CSV、MNK、HIP graph 或 op_test。

`knowledge/architectures.json` 将目标 gfx 映射到架构技能列表。目标从 seed、client 声明或
guidance 的显式 `--arch` 获取，冲突报错；没有登记的架构标记 unavailable，不借用 gfx942 技能。
声明的技能文件必须存在，路径相对仓库根。增加此映射不代表引擎新增了 ISA 支持；当前仍为 gfx942。

run 将所选技能的路径、正文、SHA256，以及 workload 和验证要求冻结到
`manifest.evaluation_contract.agent_profile`。SDK 自动将正文注入提示词；外部 manager
可以读取相同的 guidance 输出。每次评测前后重新比较契约，技能或要求发生漂移时停止评测。
环境准备、多 workload 的任务编排和关联尺寸验收由外层 manager 按 client skill 完成；
SDK worker 只执行本次已冻结 workload 的单 run。

声明 validation 后，每次 client 评测在 `EvalResult.detail` 中提供规范化证据，例如：

```python
{"validation": {
    "metrics": {"benchmark": 12.3},
    "checks": {"reference_output": True},
}}
```

指标必须与声明完全一致、为正有限数，所有必需检查必须为 `True`。缺项会使本次测量无效，
原始结果仍保存并计费。`tflops` 仍用于筛选；confirm/final 使用声明指标，逐项执行同一冻结策略，
只有全部 `confirmed_gain` 才推荐当前 workload。`lower` 指标转换成倒数参与比较；报告保留原始单位。
多指标目前只支持固定样本 `paired_sign_v1`，不支持 sequential policy，初始化时明确拒绝。
`associated_workloads: required_for_artifact_adoption` 表示采用整份产物前还需要 client 的关联验证；
单 run 记录 `artifact_adoption: not_assessed`，不会自动完成跨尺寸验收。

没有 hook 或没有 validation 的 client 保留原有标量评分流程，不需要 CSV、op_test 或 HIP graph。
新增 client 的技能按根 `AGENTS.md` 登记；既有 `identity(ctx)` 继续负责测试资源身份。

需要自动交付的 client 可在 profile 额外声明
`publication={"mode":"git_commit_push","output_dir":"client/<名>/co_out","readme":"README.md"}`，
并提供 `publication_candidate(report)`。hook 返回 `relative_path`、实测 `code_object` 字节、
`co_sha256` 和 `original_co_sha256`；可选 `display_inputs` 指定表格展示的尺寸字段，完整输入仍保存到记录。
二进制与原版相同则返回 None。输出目录必须在本 client 下。
SDK 只在正常结束、final 推荐且报告成功后调用通用 `tools/publish_run.py`；它重算确认／final
统计和必需指标，client hook 校验实际产物来源，之后固定程序导出、追加 README、commit/push。
没有声明的 client 不执行发布。aiter 的产物布局、记录和失败重试见 SDK 文档。

指令调度候选生成由通用引擎和 ISA Target 提供，与 client 验证声明分开维护。
可选 `Target.candidate_providers()` 返回 `{稳定名称: generator}`；生成函数接收
`(editor, anchors, region)`，只产生 `spec`、`direction`、`hypothesis` 和可选 `details`。
它不能执行评测或修改 editor，合法性与候选构造仍由公共路径处理。使用 `--search-policy`
选择生成器，默认按实际架构展开；配置和记录格式见 [SDK 搜索策略](../tools/sdk/README.md#搜索方向停滞与可选-profiling)。

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
| `sdk-inputs/<run-id>/attempt-*/` | SDK 初始化前的原始 `.s` 输入快照 |
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
已有单算子真机验证记录；新环境仍需先验证 seed，见 [aiter 操作步骤](aiter/docs/validation.md)。
