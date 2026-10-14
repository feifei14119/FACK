# GEAK 借鉴实施记录：P0-b 首批，持久化筛选控制器

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

日期：2026-10-13。承接已提交的 `bb5ff06`（P0-a 首批）。
设计依据：[单 kernel 指令调优改进设计](../geak_lessons_for_instruction_tuning.md)。

> 本文记录 `9661a0d` 时的首批状态。后续 schema 2 已增加显式配对确认和 final，见
> [P0-c 记录](./geak-P0c-paired-validation.md)；下文“尚未实现”描述保留为历史记录。

本批完成可单独使用的 run 模式：冻结输入与契约、保存探索父版本、严格预算、逐次调用持久化、
中断恢复，以及候选去重。**仍只做 screening；完整 P0-b 中的确认、final、incumbent 推进尚未实现。**

目标保持为现有单 kernel 的指令级重排。没有更改 ISA 规则、重排合法性模型、修补 pass、
client 的正确性容差或性能阈值。默认 SDK / `agent_session.py` / `search()` 仍走原有流程；
下面的持久化约束仅适用于显式使用的新入口。本机没有目标 GPU，本批验证均在 CPU 上进行。

## 1. 入口与职责

新增 [`agent/run.py`](../../agent/run.py) 的 `RunController`，复用 `AgentSession.observe/propose/propose_orders`
和 `search.driver.build_candidate`。Agent 提交结构化意图，控制器检查身份与预算；
生成后的候选按精确 UTF-8 字节归档，评测时从归档复制，不重新执行提案构建。

新增独立入口 [`tools/tune_run.py`](../../tools/tune_run.py)：

| 命令 | 作用 | 调用 client evaluator |
|---|---|---|
| `init SEED --client SPEC ... -- PARAMS` | 归档 original / normalized，冻结运行契约 | 否；只加载 client 模块 |
| `status RUN` | 输出 manifest、完整状态及记录的引擎/运行环境是否匹配 | 否 |
| `observe RUN [--region SEL]` | 保存完整事实与身份，返回可用于提案的指令 ID | 否，禁用 direction capture |
| `prepare RUN --observation ID --base-sha256 HASH --spec-file FILE` | CPU 检查并生成不可变候选 | 否 |
| `eval RUN CANDIDATE [--repeat]` | 检查预算，通过 client 对归档字节做 screening | 是；缓存命中或前置检查失败时不创建 evaluator |
| `select-parent RUN CANDIDATE` | 显式选择筛选通过的探索父版本 | 否 |
| `resume RUN` | 验证归档，标记中断任务，保留预算消耗 | 否；不自动重试 |

CLI 正常输出为单个 JSON 对象，客户端 Python stdout 转到 stderr，方便脚本读取。
已处理的参数、IO、契约和状态错误返回 `{"error":{"code":...,"message":...}}`，退出码为 2。
评测本身失败会作为 batch 的 `status` 返回，命令可以正常退出；调用者必须检查结果字段，不能只看退出码。
`KeyboardInterrupt`、`SystemExit` 和进程退出不伪装成正常评测结果，后续需显式恢复。

## 2. 已实现的约束

### 2.1 冻结 manifest，区分已知和未知身份

`manifest.json` 记录原始汇编摘要、引擎指纹、Python 版本与可执行路径、白名单环境设置、
client 契约、选区、构建策略、重复次数和预算。

CLI 的 client 契约包含规范化 `SPEC`、`client.py` 的绝对路径和 SHA-256、`loop`、`kernel`，以及
`--` 后原样保存的 argv 列表。保留参数顺序、重复参数和包含空格的单个值，不由引擎解释 shape。
后续 `eval` 从 manifest 读取参数，不接受新的透传参数，并检查 client 路径与摘要。
直接使用 Python 控制器注入 evaluator 时，由调用方保证 evaluator 与契约一致；
`evaluation_contract` 参数可用于一致性检查，不能证明任意注入对象的实际行为。

FACK 的引擎指纹覆盖 `agent/`、`reorder/`、`isa/`、`search/`、`harness/` 的 Python 源码，
以及 client 加载器、新 CLI。环境白名单记录 ROCm 路径，不复制全部环境变量。
指纹或已记录运行环境变化时，后续变更操作拒绝继续，要求创建新 run；`status` 仍可查看历史状态。

**未固定的身份**：外部 client 资源与依赖模块、编译器二进制、驱动、真实 GPU、频率与功耗状态、
client 私有环境变量和实际装载 `.co`。即使 `environment_matches=true`，也只代表记录覆盖的部分匹配。
这些未知项是后续 client 证据集成与真机验证的任务，不能据此声称完整环境可复现。

### 2.2 版本绑定和候选谱系

`observe` 保存完整 facts，并返回 `observation_id`、`parent_id`、`base_sha256`、`parent_revision` 和 `region`。
`prepare` 必须匹配当前探索父版本；更换父版本后，旧 observation 一律报 `stale_observation`，
即使重新选回相同字节也需要重新观察。其他提案或测量不会单独使未换父版本的 observation 过期。

第一版接受 `layout` 和 `order`；二者都沿用现有引擎定义，可只列出需要移动的少量指令。
指令 ID 必须是非负整数，拒绝布尔、浮点、字符串和重复 ID；slot 键要求规范的非负整数字符串。
禁止 spec 覆盖 observation 选区或固定构建策略。允许先用新的 `observe --region` 切换观察选区。
引擎报告非法或存在 skipped placement 时，整条提案拒绝，不把部分成功包装成完整执行。

构建策略固定为 L1、初始化选择的 prefetch 保护以及 `strict_verify=false`，复用现有
“seed 已有静态告警”的兼容策略；`static_ok` 不是完整语义等价证明。本批尚无逐条静态告警、
实际修补差异和原有/新增告警归属报告。`order` 的长度限制沿用现有 session 默认值 64。

候选保存父 ID 和构建 spec；内容相同则返回已有 ID，避免登记重复候选。
无变化为 `no_change`，与已有其他候选相同为 `duplicate`。每个提案仍独立记录并消耗一次提案预算。
去重仅限本 run；original 和 normalized 是两个保留角色，即使字节相同，也允许分别建立各自的测量记录。

### 2.3 原始 baseline、重复测量和探索父版本

任何非 original 的评测之前，original 的**最新**完整 batch 必须为 `measured`。
original 失败不会静默换成 normalized。normalized 单独归档、单独评测，不假设它正确或更快；
本版也不强制先测 normalized 才能测其他候选。

screening 复用 [`harness/measurement.py`](../../harness/measurement.py) 的逐轮检查：
每次明确编译通过、数值正确，且返回有限正分数；首个失败停止；完整有效批次取中位数。
输入工作 `.s` 在调用前后检查摘要；检测到 client 改写时 batch 无效，归档源仍保留。

已测候选再次 `eval` 默认返回最新 batch 并标 `cached=true`，包括已经完成的失败 batch。
只有显式 `--repeat` 才会启动新 batch 并扣预算。原始 baseline 的新一轮失败会关闭后续候选门槛。
中断 batch 不返回普通缓存成功，须先 `resume`，再显式 `--repeat`。

`select-parent` 只要求候选最新 batch 完整通过 screening，不要求其分数优于 original。
这允许明确选择探索分支，随后在新事实和新 ID 上继续重排。
状态始终保留 `incumbent_id=null`、`confirmation_status=not_performed`；
既不自动选“最佳”，也不把筛选通过解释成确认收益。

### 2.4 硬预算和截止时间

| 参数 | 默认值 | 本批语义 |
|---|---|---|
| `--eval-calls` | 24 | client 外层 `evaluate` 尝试次数总上限，含 original、normalized、候选和显式重试 |
| `--proposal-limit` | 64 | 已接收的 JSON 提案上限，包含非法、过期、重复和无变化提案 |
| `--perf-repeats` | 3 | 每个完整 screening batch 需要的独立 client 调用次数 |
| `--final-reserve` | 0 | 总 eval 预算内的保护额度，screen 不得花费；当前没有 final 入口，非零额度暂不可使用 |
| `--wall-seconds` | 不限 | 从创建时刻开始的截止时间；启动提案/批次/每次 client 调用前检查 |

先检查预算是否足以完成整个 batch 并保留 final reserve，再开始测量；
逐次调用前保存 attempt 并扣一次额度。批次首个失败后的未调用轮次不消耗额度；
无法确定是否执行过的中断 attempt 保守计入消耗。
JSON 语法错误、无法序列化的 Python 请求和尚未进入控制器的 CLI 参数错误不计入提案额度。

截止时间不会强行终止正在运行的 client，也不自动管理 client 子进程；它限制的是之后的新调用。
跨进程 deadline 使用系统墙钟，假定时钟没有大幅调整。尚未实现 profile、停滞、模型 token 或专项方向预算。
eval 次数是外层 client 调用数，**不是 GPU launch 数**；client 内部循环、编译和重试仍遵循 client 契约。

### 2.5 原子状态、中断恢复和锁

```text
client/<name>/tune_out/runs/<run-id>/
  manifest.json             # 冻结配置；state 保存其摘要
  state.json                # 单一权威快照，包含所有记录和预算
  .lock                     # run 进程锁
  artifacts/<sha256>.s      # 原始、规范化与候选的不可变字节快照
  work/<batch-id>/candidate.s
```

`state.json` 包含 candidates、observations、proposals、batches、attempts、父版本与预算。
每次状态保存使用临时文件、文件 fsync、原子替换、目录 fsync。为避免多个日志间的双写一致性问题，
本批不另写设计中拟议的 events/measurements JSONL；所有历史记录保留在同一个状态快照内。
这适合当前有明确预算的小规模运行，大规模记录拆分和迁移尚未实现。

外部调用前持久化 `running` attempt 与预算；返回后立即保存原始结果，批次完成后再保存聚合结果。
`resume` 将遗留的 running attempt/batch 和 preparing proposal 标为 interrupted，
不推测结果、不退还预算、不启动 evaluator。即使所有单次结果已返回而聚合尚未落盘，也按中断批次处理。

run 锁采用非阻塞 `flock`，被占用时返回 `run_busy`。CLI 另使用
`study_case/study_out/run-eval.lock`，串行化本 checkout 中所有遵守该入口的 client 评测，
锁冲突返回 `evaluation_busy`，不扣评测预算。锁从进程退出后释放；本批不删除或替换锁文件。
旧 SDK、其他 checkout、其他 GPU 程序及控制器 Python API 直接调用不受此全局 CLI 锁保护。
异常退出后还需由操作者确认没有遗留的 client 子进程在使用同一 GPU/产物；`resume` 无法证明设备空闲。

归档文件沿用 P0-a 的原子保存；恢复检查缺失或损坏归档并拒绝继续。
本批验证进程退出恢复，没有做断电、网络文件系统或磁盘故障注入验证。
初始化中断可能留下不完整目录，无法自动修复，需使用新的 run ID。

## 3. 使用步骤

命令在仓库根执行。本机无 Python 3.8，使用 `python3`；有 Python 3.8 时可替换解释器。
下面初始化示例使用已有 client；实际 seed 和透传参数应对应自己的测试契约。

```bash
python3 tools/tune_run.py init path/to/seed.s \
  --client poc_kl/fp8_blockscale_gemm --run-id geak-p0b-demo \
  --eval-calls 24 --proposal-limit 64 --perf-repeats 3 \
  -- m=256 n=256 k=256

RUN=client/poc_kl/tune_out/runs/geak-p0b-demo
python3 tools/tune_run.py status "$RUN"
python3 tools/tune_run.py observe "$RUN"
```

从返回的 facts 选择本次要移动的 ID，保存 spec JSON 到运行目录。
例如 `{"kind":"layout","layout":{"0":[123]}}`，其中 `123` 必须替换为当前 observation 的真实 ID。
`prepare` 同时传入刚返回的 `observation_id` 和 `base_sha256`；返回的 `candidate_id` 用于后续评测。
本机可完成到这一步。

有目标卡的机器上，在该机器的代码和环境下新建 run，再执行：

```bash
python3 tools/tune_run.py eval "$RUN" original
python3 tools/tune_run.py eval "$RUN" normalized
# 后续 eval 和 select-parent 的 CANDIDATE_ID 使用 prepare 返回值
python3 tools/tune_run.py eval "$RUN" CANDIDATE_ID
python3 tools/tune_run.py select-parent "$RUN" CANDIDATE_ID
python3 tools/tune_run.py observe "$RUN"
```

上述每一步先检查返回状态，失败时按 `error.code` / batch `status` 处理。
运行中断后先 `resume "$RUN"`，检查保留的预算和记录，再决定是否显式 `eval ... --repeat`。
从本机搬去目标机时，Python 路径、client 路径和环境通常变化，因此应新建 run，不能复制旧状态后混用样本。

## 4. CPU 验证

测试使用现有 gfx942 合成汇编 fixture 和假 evaluator，不执行目标 GPU kernel。
新增 [`unittests/test_tuning_run.py`](../../unittests/test_tuning_run.py) 覆盖：

- 跨控制器实例恢复、原始 CRLF 字节、完整 observation、候选身份与去重。
- layout/order 的真实引擎重排，类型错误、越界、重复 ID、部分执行和提案上限。
- 原始 baseline 门槛、契约不匹配、失败缓存、显式重试、整批预算和 final 保护。
- 探索父版本切换、旧 observation 拒绝、无变化候选、不晋升 incumbent。
- 正常异常、KeyboardInterrupt、子进程 `os._exit`，已返回样本保存与在途扣费。
- 中断提案恢复、截止时间、manifest/归档损坏、引擎变化、client 改写工作汇编。
- 跨进程 run 锁、CLI 共享评测锁、client 文件变化、原样参数、延迟创建 evaluator 和路径校验。

针对性回归：
`python3 -m pytest -q unittests/test_tuning_run.py unittests/test_tuning_evidence.py`
结果 **55 passed、13 subtests passed**。

完整回归 `python3 -m pytest -q unittests`：
**476 passed、3 skipped、3 failed、13 subtests passed**，耗时 33.47 秒。
相比 `bb5ff06` 增加 37 项通过测试。原项目当时的 3 项失败属于本副本已排除的专属模块。
先前基线见 [P0-a 验证记录](./geak-P0a-screening-evidence.md)。

附加检查通过：`git diff --check`、新 CLI 的 `--help`、设计与进度文档的本地链接检查，
以及本批四个 Python 文件的 `ast.parse(..., feature_version=(3, 8))`。
实际测试解释器为 Python 3.12.3；语法检查不等于 Python 3.8 运行时验证。

## 5. 后续顺序

1. 在此控制器上实现可配置的独立 A/B 确认与 final 协议，包括两侧预算、配对顺序、原始样本和回退语义。
   先用合成噪声/假 evaluator 验证流程；阈值、样本数、真实提速仍需目标 GPU 校准。
2. 增加 client 的构建/装载身份、外部评测契约与隔离证据，再做小规模真机对照。
3. 协议稳定后接入 SDK，使默认调优能够走同一硬预算入口。
4. 再补假设账本、详细静态诊断、多方向探索与历史复用，不将本批候选记录自动晋升为知识。
