# 到目标 GPU 机器后的执行与验收手册

适用版本：从 testft 复制并整理的 FACK，当前目标架构为 **gfx942**。
本文是后续获准执行时使用的手册；本次复制没有运行项目、测试、构建或 GPU 实验。

目标仍是现有单 kernel 的指令级重排。先把 client、实际装载和计时链路验证可靠，再评价搜索效果。
**第一轮建议只选一个架构、一个已知可运行的 client/seed、一个固定输入，完成下面的最小闭环。**
成功后再按预先记录的范围增加第二个输入和消融实验，不直接启动大规模批量测试。

## 1. 工作顺序与完成条件

| 顺序 | 到机器后要做什么 | 需要留下的证据 / 完成条件 |
|---|---|---|
| H0 | 固定代码、设备、工具链、client 和输入；跑 CPU 回归 | 环境记录、源摘要、CPU 日志；无新的未解释失败 |
| H1 | 验证 original 的构建、实际装载和数值正确性 | client 原始返回、build evidence、装载证据；基线可稳定运行 |
| H2 | 独立运行小规模 original 重复测量，选择正式测量规则 | 完整时间序列、有效/无效计数、频率/热状态、策略选择依据 |
| H3 | 手动贯通 prepare → screen → confirm → final | 实际移动/修补诊断、独立配对样本、final 结果与对应汇编 SHA |
| H4 | 按需采一次原始版本与候选的 profile | 有效 wave/counters、版本与 dispatch 关联；不混入性能样本 |
| H5 | 验证兄弟候选组合与历史 warm start | O/A/B/A+B 谱系、导入重建记录、本轮重新筛选和确认 |
| H6 | 在同预算下做少量独立运行与消融 | 全部运行报告、失败记录、收益与搜索成本表 |
| H7 | 汇总验收结论与待修项 | 明确哪些功能已验证、哪些无收益/未知/受阻；保留原始证据 |

H3 的完整预算应事先包含 H4/H5 计划使用的调用；不能先耗完搜索预算，再追加 final 样本。
未出现 confirmed_gain 时，执行 final 得到 original_retained 也是一次完整协议验收，不能为“必须提速”反复重开 run。

## 2. H0：机器与工程准备

### 2.1 记录实际配置

在仓库根执行。先填写以下记录，保存到该 client 的 `tune_out/` 或 `study_case/study_out/`：

| 项目 | 要记录的内容 |
|---|---|
| 代码 | FACK 版本快照；建立 Git 仓库后记录 commit、工作区 diff；client/外部测试项目的版本和本地改动 |
| 设备 | GPU 型号、gfx 架构、UUID/PCI BDF、驱动版本、单卡选择方式、是否有其他负载 |
| 运行环境 | OS、内核、容器镜像（如有）、ROCm、Python、实际 clang++ 路径与版本 |
| 任务 | client spec、seed 绝对路径及 SHA、kernel 符号、region、完整 client argv、loop/预热设置 |
| 正确性 | 现有参考实现、输入数据/随机种子、检查范围、现有容差；不因候选失败放宽容差 |
| 测量 | 冷/热启动定义、计时边界、score 与时间的关系、设备频率/功耗策略、串行执行安排 |
| 外部资源 | 测试 exe、参考脚本、动态库/torch/aiter 等实际版本；未纳入 client identity 的依赖另行记录 |

设备查询使用目标机器已有的 `rocminfo`、`amd-smi` 或对应只读工具，保存输出；工具不可用时明确记录缺项。
用 PCI 地址核对 HIP 逻辑设备与 DRM card，不能假定 `HIP_VISIBLE_DEVICES=0` 就对应 `card0`。
只选择本次可用的设备，不擅自重置 GPU、调整全机功耗或中断其他任务。

先配置好设备可见性、ROCm 路径和 client 所需环境，再 init。它们中的已记录字段在 run 内冻结；
**换机器/路径/工具链/环境后新建 run，不继续本机生成的旧 run**。旧结果可作为资料保留，不能复制 state 冒充新测量。
同一 checkout 的评测锁只约束遵守 run 协议的调用，不能隔离其他进程或其他 checkout 的 GPU 工作。

### 2.2 选 client 与输出位置

现有接入样例：

- `poc_kl/fp8_blockscale_gemm`：现有 GEMM client；检查 seed 的架构声明、实际编译目标和 exe 支持范围。

样例存在不代表已在当前 GPU 验收。缺 `.amdgcn_target` 时工具链可能使用 gfx942 默认值，必须核实，
不能只改 target 字符串把 seed 移植到另一架构。FACK 接收已核实架构、可重建的 `.s`；
当前副本不提供 `.co` 转换工具。若汇编由外部工具准备，原始 `.co` 与 `.s` 分开归档并记录来源。

下面 Bash 模板中的任务值需要先填写；参数必须使用数组，保持 token 边界：

```bash
set -euo pipefail
if command -v python3.8 >/dev/null 2>&1; then TF_PY=python3.8; else TF_PY=python3; fi
TF_CLIENT='填写 client/ 下的路径'
TF_SEED='填写已核实架构的 seed.s 路径'
TF_REGION='loop'
TF_LOOP=20
TF_PARAMS=('填写该 client 的参数')
# 例如 GEMM 数值 token；以项目已知可通过的 case 为准，不替所有 client 默认 shape。
# TF_PARAMS=(m=256 n=256 k=512)
TF_TAG="gpu-accept-$(date -u +%Y%m%dT%H%M%SZ)"
TF_OUT=$("$TF_PY" -m client resolve "$TF_CLIENT" | "$TF_PY" -c 'import json,sys; print(json.load(sys.stdin)["out_dir"])')
TF_CASE="$TF_OUT/acceptance/$TF_TAG"
mkdir -p "$TF_CASE"
test -f "$TF_SEED"
# 本次复制不带 Git 历史；仅在 FACK 已独立建立 Git 仓库后记录版本。
if [ -e .git ]; then
  git rev-parse HEAD > "$TF_CASE/fack-commit.txt"
  git status --short > "$TF_CASE/worktree-status.txt"
fi
sha256sum "$TF_SEED" > "$TF_CASE/seed.sha256"
```

有明确 kernel 符号选择需求时，在后文 init/SDK 命令加入同一个 `--kernel NAME`。
机器环境信息写 `environment.md`，实际输入和范围写 `case.md`，两者放在 `$TF_CASE`。
不保存 API key 或整份进程环境。每个 case/run 用新名称，保留之前的输出。

**本次验收使用 `tools/tune_run.py` 或直接调用 SDK。不要用现有 `client/poc_kl/tune_script/tune_quick.sh`
收集连续验收/历史复用证据：其启动逻辑含清空 client tune_out 的 `rm -rf`。**

### 2.3 先执行软件回归

```bash
python3 -m pytest -q unittests > "$TF_CASE/cpu-tests.log" 2>&1
# 仅当准备使用 SDK 时，额外执行：
node --test tools/sdk/run_workflow.test.mjs > "$TF_CASE/sdk-tests.log" 2>&1
```

CPU pytest 若返回非零，先检查日志再继续，不通过更换断言或跳过测试隐藏差异。
原项目的历史测试结果不代表 FACK 的验收结果；逐项判断当前失败原因并记录处理结论。

## 3. H1–H2：原始基线与独立测量预试验

### 3.1 新建仅筛选的 pilot run

先不用比较策略、不用 profile、不改变汇编。下面的 **12 次**是有界的首轮运行性/噪声观察例子，
不是足以证明独立性或校准显著性门槛的样本量保证。若计划扩大，事先记录新范围与预算。

```bash
"$TF_PY" tools/tune_run.py init "$TF_SEED" --client "$TF_CLIENT" \
  --run-id "$TF_TAG-pilot" --region "$TF_REGION" --loop "$TF_LOOP" \
  --eval-calls 12 --perf-repeats 1 --proposal-limit 1 --wall-seconds 1800 \
  -- "${TF_PARAMS[@]}" > "$TF_CASE/pilot-init.json"
TF_PILOT=$("$TF_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_dir"])' "$TF_CASE/pilot-init.json")
"$TF_PY" tools/tune_run.py eval "$TF_PILOT" original > "$TF_CASE/pilot-01.json"
"$TF_PY" -c 'import json,sys; b=json.load(open(sys.argv[1])); print(b["status"]); sys.exit(b["status"] != "measured")' "$TF_CASE/pilot-01.json"
```

先检查第一次调用，再决定执行余下 11 次，不能只看进程 exit code。`eval` 可能返回合法 JSON、exit 0，
但 batch 为 `incorrect`、`compile_failed` 或 `measurement_invalid`。

第一轮检查：

- 原始字节摘要与 seed 对应；`compiled=True`、`correct=True`，score 有效，计时覆盖的是目标 kernel。
- `detail.build_evidence`（client 支持时）中的源、产物和稳定资源检查一致；声明缺失仍保持 unknown。
- 从 client/加载器日志或适用的运行时装载记录确认实际采用了哪份 `.co`、哪个符号、哪次 dispatch。
  若需补 client 证据接口，先修改并验证接口，再新建 pilot，旧 run 不继续混用新实现。
- **磁盘 SHA/fresh build 不能证明 GPU 装载身份。** 目前工具不自动提供这项证明；未取得时在结论中保持 unverified，
  不能把协议层的 measured/final_recommended 写成完整硬件证明。
- 若输入来自 `.co`，run original 实测的是“从 `.s` 重建的版本”；原始 `.co` 需另由支持该操作的 client 验证。
  当前接口没有通用的原始 `.co` 对照命令，不能绕过 client 或把两者等同。

```bash
for TF_I in $(seq 2 12); do
  "$TF_PY" tools/tune_run.py eval "$TF_PILOT" original --repeat > "$TF_CASE/pilot-$TF_I.json"
  "$TF_PY" -c 'import json,sys; b=json.load(open(sys.argv[1])); print(b["status"]); sys.exit(b["status"] != "measured")' "$TF_CASE/pilot-$TF_I.json"
done
"$TF_PY" tools/tune_run_report.py "$TF_PILOT" > "$TF_CASE/pilot-report-paths.json"
```

`--repeat` 在此是事先计划的独立原始调用；重复不带该选项的 eval 只会命中缓存，不能用来估计噪声。
错误返回及其已消耗额度照常保留，不丢掉失败点后补够“12 个好点”。pilot 没有 comparison policy，不调用 final。

### 3.2 分析 pilot，先写测量决定

从 run 的 `state.json` 中按 batch sequence/attempt 取出完整 `tflops`、`time_us`（如有）、开始时间、
调用耗时、错误及 build evidence，保存 `pilot-analysis.md`：

1. 有效/无效次数、分数/时间的中位数、范围及稳健离散度，按时间顺序的漂移与相邻相关性。
2. 预热是否足够、进程初始化/缓存状态是否稳定、其他负载及频率/温度是否解释了离群点。
3. 同一代码连续调用的顺序效应。它只能暴露部分风险，不能证明未来 A/B 配对独立同分布。
4. 选定的 `perf_repeats`、confirm/final 配对数、最小有用增益 `min_gain`、alpha、最多确认次数及选择依据。
   若证据不足以使用当前统计假设，继续标为探索性，不宣称严格置信保证。

gfx942 频率观测使用目标机器已有的只读工具，先核对设备与采样字段的含义。
若采样覆盖某次 client 评测，须计入既定 pilot 调用并检查该 batch 的状态。
毫秒级采样包含编译和进程启动期间的空闲时间，短 dispatch 可能采不到；
不能把整段频率中位数当作 kernel 实际频率。需要更长稳态采样时，
通过 client 配置独立、预先声明的 pilot，并保持正式任务的 loop 与输入不变。

## 4. H3：正式 run 的最小闭环

### 4.1 冻结策略与足够预算

把 H2 的决定保存为 `$TF_CASE/comparison-policy.json` 和 `$TF_CASE/search-policy.json`。
比较策略格式示例（**数值仅用于格式/预算演示，尚未针对目标 GPU 校准**）：

```json
{"method":"paired_sign_v1","confirm_pairs":8,"final_pairs":8,"min_gain":0.01,"alpha":0.05,"max_confirmations":3}
```

预期收益只有 1–2%（例如目标 `.co` 已做过优化）时，固定少量配对判不出来。改用分段策略
`paired_sequential_v1`（格式与假设见 [P0c §2.1](geak-P0c-paired-validation.md)）：大收益和明显退化在早期检查点停止，
小收益才用满最后一个检查点；预算按最后检查点预留。同时在 H2 用预先声明的 pilot 比较 client 计时长度
（使用该 client 支持的 `--loop`），选单次 CV 最低的设置并冻结进正式 run。


搜索策略格式与有界工作量示例：

```json
{"direction_eval_call_limit":6,"profile_call_limit":2,"stagnation_limit":6,"reuse_proposal_limit":8,"reuse_eval_call_limit":24,"independent_eval_reserve":6}
```

设 R=perf_repeats、K=计划筛选的非 original/normalized 候选数、P=profile 调用数、C=最多确认次数，
Nc/Nf 分别为 confirm/final 配对数。正常全完成路径的调用预算为：

```text
E = R × (2 + K) + P + 2 × Nc × C + 2 × Nf
final_eval_reserve >= 2 × Nf
```

例如 R=3、K=4、P=2、C=3、Nc=Nf=8，则 E=84，final reserve=16。
K 要包含组合和历史导入候选；额外显式复测、额外参考筛选另占预算。失败可能提前停止，因此这是计划额度而非必耗值。
一次 evaluate 可包含多次 GPU launch、client 内部重试/预热；额度不是 launch 数。
proposal 还要覆盖拒绝/重复、replay 的 1 次请求 + 1 次 prepare、warm-start 的 1 次请求 + N 个步骤。
方向额度至少要容纳一个完整 R 调用筛选；复用上限也要容纳其筛选和完整确认。独立预留按调用计，不保证候选数量。
墙钟从 init 开始计算，人工检查和归档也占用时间；按实际操作预留，不能事后延长同一 run 的期限。

以下正式命令与上述预算算例对应；实际采用不同策略时同步重算额度：

```bash
TF_COMPARISON="$TF_CASE/comparison-policy.json"
TF_SEARCH="$TF_CASE/search-policy.json"
test -f "$TF_COMPARISON"
test -f "$TF_SEARCH"
"$TF_PY" tools/tune_run.py init "$TF_SEED" --client "$TF_CLIENT" \
  --run-id "$TF_TAG-main" --region "$TF_REGION" --loop "$TF_LOOP" \
  --eval-calls 84 --perf-repeats 3 --proposal-limit 32 --final-reserve 16 \
  --wall-seconds 3600 --comparison-policy "$TF_COMPARISON" --search-policy "$TF_SEARCH" \
  -- "${TF_PARAMS[@]}" > "$TF_CASE/main-init.json"
TF_RUN=$("$TF_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_dir"])' "$TF_CASE/main-init.json")
"$TF_PY" tools/tune_run.py eval "$TF_RUN" original > "$TF_CASE/original-screen.json"
```

检查 original batch 为 measured 才继续：

```bash
"$TF_PY" tools/tune_run.py eval "$TF_RUN" normalized > "$TF_CASE/normalized-screen.json"
"$TF_PY" tools/tune_run.py status "$TF_RUN" > "$TF_CASE/main-status.json"
```

normalized 单列，可能无变化、静态不通过、数值失败或无收益。失败不替换 original 基准；如数值失败，
先诊断修补/构建问题，不能继续宣称该路径的重排可靠。正式 run 开始后不调整统计门槛、资源或环境。

### 4.2 选择一个小意图，记录实际改动

```bash
"$TF_PY" tools/tune_run.py suggest "$TF_RUN" --region "$TF_REGION" --n 4 > "$TF_CASE/suggestions.json"
```

先读建议的 spec/hypothesis 和 observation。下例把人工选中的第 0 项写到独立输入文件；
没有建议时停止该示例路径，基于新的 observe 手写一个小 layout/order，不硬造 IID：

```bash
"$TF_PY" - "$TF_CASE" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
suggestions = json.loads((root / 'suggestions.json').read_text())
assert suggestions['suggestions'], '没有自动建议：需要基于 observation 重新提案'
choice = suggestions['suggestions'][0]
for name, value in [('spec.json', choice['spec']), ('hypothesis.json', choice['hypothesis'])]:
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))
PY
TF_OBS=$("$TF_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["observation"]["observation_id"])' "$TF_CASE/suggestions.json")
TF_BASE=$("$TF_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["observation"]["base_sha256"])' "$TF_CASE/suggestions.json")
"$TF_PY" tools/tune_run.py prepare "$TF_RUN" --observation "$TF_OBS" --base-sha256 "$TF_BASE" \
  --spec-file "$TF_CASE/spec.json" --hypothesis-file "$TF_CASE/hypothesis.json" > "$TF_CASE/prepared.json"
TF_CANDIDATE=$("$TF_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["candidate_id"])' "$TF_CASE/prepared.json")
"$TF_PY" tools/tune_run.py ledger "$TF_RUN" > "$TF_CASE/ledger.json"
```

检查实际 payload moves、repair 差分、固定 original 的新增告警；不把 repair-only 当作原计划移动已实现。
rejected 不上机；duplicate/no_change 不算新的独立候选，缓存结果也不算新样本。

```bash
"$TF_PY" tools/tune_run.py eval "$TF_RUN" "$TF_CANDIDATE" > "$TF_CASE/candidate-screen.json"
```

每个候选的最新 screening 必须 measured，再依据预先约定的选择规则决定是否花确认预算：

```bash
"$TF_PY" tools/tune_run.py confirm "$TF_RUN" "$TF_CANDIDATE" > "$TF_CASE/confirm.json"
"$TF_PY" tools/tune_run.py status "$TF_RUN" > "$TF_CASE/after-confirm.json"
```

确认首轮对 original，后续对 incumbent；完整 AB/BA 配对使用新样本，不借筛选分数。
只有 confirmed_gain 晋升；inconclusive/regression/失败保留 incumbent。同一候选/参考的重复 confirm 是缓存，
没有 confirm --repeat，不能不断测到显著。晋升后旧 IID 失效，继续搜索必须重新 observe。
若要做 H4/H5，在预算内先做，再收尾：

```bash
"$TF_PY" tools/tune_run.py final "$TF_RUN" > "$TF_CASE/final.json"
"$TF_PY" tools/tune_run_report.py "$TF_RUN" > "$TF_CASE/report-paths.json"
```

final 固定当前 incumbent 对 original，使用独立样本；不通过/无 incumbent 时 original_retained。
final 后 run 关闭，不能继续调优。检查 `RUN/report/report.json`、`report.md`、`selected.s` 与记录 SHA 一致。
final 前只有 screening_best/confirmed_best，不能提前宣称最终推荐；对 normalized 的独立 final 配对比较目前未实现。

## 5. H4：profile 与频率证据（在 final 前按需做）

original 和目标候选都须先有有效 screening，且 frozen profile_call_limit 允许。每次 profile 消耗
1 次总 eval 和 1 次 profile 额度；client 内部可能还有 ATT 重试，记录真实成本。

先采原始版本：

```bash
"$TF_PY" tools/tune_run.py profile "$TF_RUN" original > "$TF_CASE/profile-original.json"
```

检查并按下述要求归档原始 dump 后，再采候选，避免第二次调用覆盖第一份证据：

```bash
"$TF_PY" tools/tune_run.py profile "$TF_RUN" "$TF_CANDIDATE" > "$TF_CASE/profile.json"
```

检查 `profile_status`、对应 attempt 的 `counters`、`counter_dump_path`、错误和候选 SHA。
将原始 dump 及时另存到 `$TF_CASE/` 的唯一目录，并记录 profile batch ID：client 的固定 ATT 目录可能在下一次采样被清理。
不要只保存一个以后会被覆盖的路径。profile 不可用时记录 unavailable，仍可从计时与静态事实继续，不无限重试。

gfx942 通过 client 的 `rocprofv2 --plugin att` 路径采集，使用
[`analysis/perf.py`](../../analysis/perf.py) 解码并由
[`analysis/bottleneck.py`](../../analysis/bottleneck.py) 分析，格式说明见
[AMDGPU dump 解析](../amdgpu-dump-parsing.md)。
必须检查有效 wave/指令数据和解码错误；进程成功或只有 `.att` 文件不代表有效采样。

只比较相同任务、采样方式和 dispatch 条件；父版本变化后旧 profile 只能作为历史证据。
ATT 时长不进入 screen/confirm/final，不由单 CU/wave 的 stall 直接推断全 kernel 的加速幅度。
本次使用原任务的驻留 trace；改变 LDS 申请、grid 或构造单 wave 的微基准属于另一实验，
不能混入本次固定 kernel 的验收。所有实际构建/数值验证/计时/采样仍通过 client。

## 6. H5：组合与历史复用

### 6.1 兄弟候选组合

在同一 original 上分别 prepare 小候选 A、B，并各自筛选。先取得两份有效筛选再 select-parent/confirm，
避免第二个意图误用旧 IID。记录原始 O、A、B，预算内再构造 A+B：

若前面已改变探索父版本，先执行 `select-parent "$TF_RUN" original`（通过 `tools/tune_run.py`），
再重新 observe/suggest 并 prepare A、B；不要复用晋升前的 observation。

```bash
TF_A='填写已筛选 A 的 candidate_id'
TF_B='填写已筛选 B 的 candidate_id'
"$TF_PY" tools/tune_run.py select-parent "$TF_RUN" "$TF_A"
"$TF_PY" tools/tune_run.py replay "$TF_RUN" "$TF_B" > "$TF_CASE/combined.json"
```

replay 将 B 的最后一步意图重表达在当前 A 上；多步 B 不表示自动导入整条 B 链。
成功消耗 2 次 proposal，不调用 client、不晋升。读取返回的新 candidate_id，再走 eval/confirm；
保存源/目标链、mapping、实际移动与拒绝原因。歧义/冲突可记录为拒绝，不能用文本 diff 拼接绕过。
select-parent 只改变探索父版本；组合失败不撤销已确认 incumbent。A+B 的收益独立测量，不能相加 A、B 的百分比。
O/A/B 的旧 screening 仅供筛选比较，不冒充同时重新采样的四路统计实验。

### 6.2 在目标机器新建 warm run

优先选该机器、同一代码/环境/输入契约下，已完成 final 且有推荐的正式 run 作为历史来源。
final 回退 original 的 run 不提供历史赢家；无赢家就记录“无可复用历史”，不把最高筛选分伪装成推荐。
读取器也支持未 final 的已确认候选，但这种来源需明确标注。

按 §4.1 的 init 参数创建新名字 `$TF_TAG-warm`，从返回 JSON 取得 `TF_WARM`。即使机器 GPU 型号相同，
路径、Python、engine、client 契约不匹配也可能被拒绝；不编辑旧 manifest 或放宽匹配绕过。

```bash
TF_WARM='填写新建 warm run 的 run_dir'
"$TF_PY" tools/tune_run.py eval "$TF_WARM" original > "$TF_CASE/warm-original.json"
"$TF_PY" tools/tune_run.py history "$TF_WARM" "$TF_RUN" > "$TF_CASE/history-offer.json"
# 检查匹配成功、chain 长度 N，以及 global/reuse 至少剩余 1+N 次提案后再执行：
"$TF_PY" tools/tune_run.py warm-start "$TF_WARM" "$TF_RUN" > "$TF_CASE/warm-import.json"
```

history/warm-start 均不调用 client。核对 imports 中的原始来源、每步重建 SHA、1+N 提案费用和
`measurements_imported=false`。导入后 parent/incumbent 不应自动改成历史赢家。
读取导入 candidate_id，再在 **TF_WARM** 中执行 eval、confirm、final 和报告导出；旧测量不能替代本轮结果。
检查 reuse 来源对重复/后代的继承，并实际保留至少一个基于当前 observation 的独立搜索方向。

不兼容历史、额度耗尽、冲突、硬中断等边界先使用 CPU 单测验证。若真机自然出现中断，按 §8 恢复；
不为了测试恢复而故意制造非法 GPU 指令、设备 fault 或杀死共享 GPU 工作。

## 7. H6：SDK 验证与同预算消融

先完成一次手动闭环，再用 SDK 新建独立 run 验证自动导航。下例仍使用 §4 的已选策略：

```bash
TESTFT_PYTHON="$TF_PY" node tools/sdk/tune.mjs "$TF_SEED" --client "$TF_CLIENT" \
  --run-id "$TF_TAG-sdk" --region "$TF_REGION" --loop "$TF_LOOP" --rounds 4 \
  --eval-calls 84 --proposal-limit 32 --final-reserve 16 --perf-repeats 3 --wall-seconds 3600 \
  --comparison-policy "$TF_COMPARISON" --search-policy "$TF_SEARCH" \
  -- "${TF_PARAMS[@]}"
```

先准备 SDK 依赖/认证，但凭据不写入验收记录。观察模型是否使用本 run 的版本化接口、稳定方向名及额度，
是否停止于预算/停滞；模型正常结束后由驱动器调用一次 final，异常则保留证据，不自动补测。
SDK warm 组另用新 run-id，并在 `--` 前追加 `--history-run "$TF_RUN"`；历史候选筛选仍计入 rounds/总调用。

消融建议先做下列对照，每组的正式 run 使用相同总调用/时间/确认预算及相同输入：

| 组 | 启用内容 | 控制事项 |
|---|---|---|
| A | P0 可靠测量 + 少量预先记录的基础重排策略 | 不用 profile/历史/组合；仍使用同一确认与 final 协议 |
| B | A + P1 多方向建议 | 固定可选方向、模型/提示及候选选择方式，记录首次确认成本 |
| C | B + 按需 profile | profile 计入相同总额度；允许结果无收益或因采样成本减少候选数 |
| D | B 或 C + P2 组合 | A/B/A+B 构建和计时都算进额度，限制组合数 |
| E | 与选定冷启动组相同 + 显式历史 | 历史命中后的本轮重新评测计入额度，另列生成历史的历史成本 |

没有一个现成开关能自动运行这整张对照表。使用手动控制器流程或预先固定的导航提示执行，保留提示/操作清单；
比较手工 A 与模型 B 时不能将全部差异只归因于多方向功能。不要让各组同时争用同一 GPU。
执行顺序事先安排并交错/随机化，独立运行次数在实验前确定，保留所有结果，不只挑最高分。
这里只规定实验方法，不默认启动多组或多 kernel 的 GPU campaign。

## 8. 停止条件与恢复

| 现象 | 行动 |
|---|---|
| original 编译/数值失败或 score 无效 | 停止该 case 的候选性能结论；保存原始错误，修好 client/基线后新建 run |
| 静态新增告警、illegal/skipped 或 intent conflict | 不执行该候选；记录具体意图与父版本，预算内重新 observe/prepare |
| client/engine/runtime 身份变化 | 不继续混测；记录差异、完成修复后新建 run |
| 频率/热漂移、其他负载、疑似缓存或实际装载不明 | 保留全部样本与证据；暂停性能结论，调查原因，不删离群点拼确认 |
| profile unavailable / 空 wave | 保留错误，不把原因猜测写成已证实 stall；预算内才可安排额外独立采样 |
| search_stagnated 或方向/复用预算耗尽 | 停止受限搜索动作；合格的待确认/最终比较仍按各自预算规则执行 |
| recovery_required / 进程中断 | 等 client/锁持有进程结束，status → resume → report；不直接改 state 或绕锁 |
| final 不通过或中断 | 保留 original；不在同 run 换一个候选再试 final |

```bash
"$TF_PY" tools/tune_run.py status "$TF_RUN"
"$TF_PY" tools/tune_run.py resume "$TF_RUN"
"$TF_PY" tools/tune_run_report.py "$TF_RUN"
```

resume 只标记中断状态，不退还已占预算，也不重新执行。screen 中断后的新尝试需要显式带 --repeat；
confirm/final 不补齐或重放部分比较。墙钟期限只在新操作/调用开始前检查，不会强制终止已经运行的 client。

## 9. H7：需要交回的验收包

每个 case 保存 `$TF_CASE`，连同对应的完整 `runs/<id>/` 和已归档的外部原始日志/dump：

```text
acceptance/<case-id>/
  environment.md, case.md, testft-commit.txt, worktree-status.txt, seed.sha256
  cpu-tests.log, sdk-tests.log（若使用 SDK）
  pilot-analysis.md, comparison-policy.json, search-policy.json
  pilot/main/warm 的 init、关键命令返回与 report-paths JSON
  实际装载证据、已保存的 .co 摘要/字节（可用时）、时钟 CSV、独立 ATT dump
  acceptance-result.md, comparison.csv
runs/<id>/
  manifest.json, state.json, artifacts/, work/, report/
  inputs/、input_provenance.json、transcript.*（由实际入口产生时）
```

不要只交 selected.s；某些 `.co`/ATT 路径会被下一次 client 调用覆盖，需要在覆盖前复制到唯一归档目录。
复制的证据记录原路径、采集时刻、candidate SHA 和 batch/attempt ID；不要把截图当作完整原始样本。

`comparison.csv` 至少包含：架构/设备、client/input ID、组别、run ID、original/selected SHA、
final 状态、配对比值及界、首次 confirmed_gain 时累计调用与墙钟、总调用/profile/复用消耗、
不同有效 artifact 数、拒绝/重复/无效比例、历史是否命中、装载证据状态。没有的指标填 unknown，不填 0。
首次收益成本从权威 attempts/comparisons 的时间和记录计算，不能使用报告导出时间。

`acceptance-result.md` 按 H0–H7 分别写 PASS / FAIL / UNKNOWN / NOT_RUN，附证据路径和下一步。
区分“协议运行通过”“该候选有确认收益”“搜索方法同预算更有效”三个结论。无收益和原始回退照实报告。
所有输出留在 client tune_out 或 study_out，候选经验经人工审核后才可晋升到 `knowledge/`。

相关说明：[实施总表](../geak_rollout_status.md)、[配对协议](./geak-P0c-paired-validation.md)、
[client 证据](./geak-P0d-client-evidence.md)、[SDK 用法](../../tools/sdk/README.md)。
