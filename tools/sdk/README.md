# SDK 驱动的元层调优 agent

`tools/sdk/tune.mjs` 用本地 Cursor SDK agent 决定单 kernel 的指令重排实验。
默认通过持久化 [`tools/tune_run.py`](../tune_run.py) 运行；控制器负责候选身份、硬预算、
client 调用记录和裁决，SDK 负责模型会话以及结束时导出报告。
[`articulate.mjs`](./articulate.mjs) 仍是独立的离线知识归纳入口，见文末。

```text
node tools/sdk/tune.mjs
  ├─ tune_run.py init                     程序先冻结契约、预算和原始汇编
  ├─ Cursor agent（本地 shell，cwd=仓库根）
  │    └─ status → eval original/normalized → observe/suggest → prepare → eval → confirm（显式策略）
  │         └─ profile（仅显式搜索策略允许，独立计费的导航证据）
  │         └─ history → warm-start（仅显式历史来源，CPU 重建后仍需当前评测）
  ├─ tune_run.py final                    正常结束且有显式策略时，由 SDK 发起一次
  └─ tune_run_report.py                   正常或异常结束均尝试导出已有证据
```

静态验证只覆盖引擎已建模的 ISA 约束，仍须通过 client 检查正确性和性能。
硬预算由 **run 控制器的调用路径**执行；本地 SDK 的任意 shell 权限不是安全隔离，
不能阻止恶意脚本绕开控制器直接调用 client。提示词要求只使用本 run，不改引擎、client 或归档。

## 自学成果的使用边界

默认直接读取 `selfstudy/` submodule 中 gfx942 的已有 `skills_out`，不执行自学或重新生成 skill。
`knowledge/skills/mfma-interleave-gfx942/` 是上游导出的软链接。依赖缺失时报告缺项，
不由模型运行 pipeline、fit、探针汇编或硬件探测补齐。SDK 提示词保留此约束，也不自动更新 submodule。
新 clone 后用 `bash tools/init_selfstudy.sh` 获取固定版本并配置 gfx942 稀疏检出；
详见 [submodule 接入说明](../../proj/selfstudy-submodule.md)。

## 前置

```bash
cd tools/sdk
npm install
```

提供 `CURSOR_API_KEY` 环境变量，或建立被 gitignore 的 `tools/sdk/cursor.config.json`：

```json
{ "apiKey": "cursor_...", "model": "auto" }
```

配置文件建议权限 `0600`；环境变量中的 key 优先。可用 `--config FILE` 指定配置路径。
Python 使用 `TESTFT_PYTHON`，否则优先 `python3.8`，没有则用 `python3`。
`--help`、CPU 单元测试和手动报告导出不需要 API key 或 SDK 模型访问。

## 运行

命令可以从任意目录启动，seed 和用户指定的输出路径相对当前 shell 解析。
引擎子进程和模型 shell 均在仓库根运行。

```bash
node tools/sdk/tune.mjs path/to/seed.s \
  --client poc_kl/fp8_blockscale_gemm --rounds 6 --region loop \
  -- m=2560 n=2560 k=256
```

`--client` 选择项目。`--` 后的 token（包括空字符串、空格、重复键、以 `--` 开头的参数）
通过子进程 argv 原样传给 **init 一次**，随后从 manifest 读取。SDK 不解析 shape 或拼接这些 token 为 shell 字符串。
默认输出位于 client 的 `tune_out/runs/<run-id>/`；实际路径以 client resolve 返回值为准。

没有 `--comparison-policy` 时，只筛选并生成未确认报告，不调用 confirm 或 final，不推荐筛选最高分。
模型可选择已测量的探索父版本，但它不会变成已确认 incumbent。

若需要配对确认，应先按目标 client 的测量波动选择策略，保存为 JSON，再显式传入：

```bash
node tools/sdk/tune.mjs path/to/seed.s \
  --client poc_kl/fp8_blockscale_gemm --rounds 6 \
  --comparison-policy path/to/chosen-policy.json --eval-calls 88 --final-reserve 16 \
  -- m=2560 n=2560 k=256
```

上例预算与 [P0-c 文档的示例策略](../../proj/steps/geak-P0c-paired-validation.md) 匹配，
不是已校准的 GPU 参数或收益保证。SDK 不提供默认统计策略、阈值或样本数。
控制器会在 init 时校验策略与预算，并把策略内容冻结进 manifest。

1. original 必须通过筛选，才允许测试其他候选。normalized 的失败不会替换原始参考。
2. observe 返回 observation_id、base_sha256 和父版本。prepare 校验这些身份并归档实际构建结果。
3. eval 是筛选；仅显式策略的 confirm 可以推进 incumbent。推进后必须重新 observe。
4. SDK 模型正常结束后，驱动器读取 status。有策略且仍在 search 阶段时调用一次 final，与 original 比较。
   已完成 final 或正在 finalizing 的运行不重复调用；失败不自动 resume、重试 confirm 或重试 final。
5. 模型异常、缺 key、鉴权失败或中断时，仅尝试报告已持久化证据，不自动补测。

`--region loop` 等具体区域通过提示词固定；`all` / `auto` / `any` 允许跨区重新 observe。
控制器校验每个 spec 与其 observation 区域一致。模型的 region 使用约定不等于 shell 权限限制。
锚点区域使用 layout，无锚点区域使用小范围 partial order，汇编修改由引擎完成。

### 搜索方向、停滞与可选 profiling

`--search-policy FILE` 将用户选择的 JSON 文件交给 init 校验并冻结，和比较策略相互独立：

```bash
node tools/sdk/tune.mjs path/to/seed.s --client poc_kl/fp8_blockscale_gemm \
  --search-policy path/to/search-policy.json --eval-calls 30 \
  -- m=2560 n=2560 k=256
```

搜索策略可包含 `direction_eval_call_limit`、`stagnation_limit`、`profile_call_limit` 等字段，
具体契约见 [`agent/directions.py`](../../agent/directions.py)。例如
`{"direction_eval_call_limit":6,"stagnation_limit":4,"profile_call_limit":2}` 只是可选预算格式示例。
profile 默认上限为 0；正整数或用户显式填写的 null 才允许 profiling。
null 仅表示不设 profile 专项上限，总 eval 预算、final reserve 和独立探索预留仍有效。
SDK 不因搜索策略自动扩充 eval 总预算；需要的调用额度应在初始化时明确安排。
该选项不启用 confirm/final；确认仍必须另传 `--comparison-policy`。

提示词让模型调用 `suggest RUN --n N --region SEL` 获取小批 CPU 建议，使用返回的
observation 身份、spec 和 hypothesis 调用 prepare。优先从可用、尚未尝试的独立方向各试少量候选，
再对已经产生 confirmed_gain 候选的方向作局部细化。确认收益属于具体候选，不是整个方向的定论。
方向名保持稳定，不能换名规避额度；一个筛选 batch 会消费 perf_repeats 个方向调用额度。
模型在每次新动作前读取 `status.search.direction_eval_calls`、`stagnation_count` 和 `search_stopped`。
停滞后停止新建议、提案、筛选和 profile；符合资格的待确认候选仍可确认一次，最后由 SDK 按策略 final。

仅在冻结策略允许时，提示词提供 `profile RUN CANDIDATE_ID`。original 和该候选均须先通过筛选。
每次 profile 是独立 client 调用，同时计入 eval 与 profile 两项预算；其中返回的计时或分数
不参与 screening、confirm 或 final 的性能裁决。计数器只用于检验调度假设。
`status.search.current_profile_id` / `profile_needs_refresh` 与当前探索父版本和 parent_revision 绑定，
晋升或换父版本后不能拿旧 profile 解释新父版本。
SDK 提示词约定每个 parent revision 最多请求一次可选 profile；无 counters、unavailable 或异常时记录后停止重试，
`profile_needs_refresh=true` 本身不表示获得新调用许可。控制器的显式手动 profile 入口仍按冻结额度执行。

方向选择和每父版本一次 profile 是模型执行约定，
控制器的预算与裁决仍是权威门槛；本地 shell 权限不构成强隔离。

### 显式历史 warm start 与候选组合

`--history-run DIR` 将一个既有 run 指定为导航来源。可选 `--history-candidate ID` 选择其中
已确认的候选；省略时由控制器选择有效 final 推荐或尚未 final 的已确认 incumbent。
没有 `--history-run` 时不扫描历史目录、不调用 history 或 warm-start。

```bash
node tools/sdk/tune.mjs path/to/seed.s --client poc_kl/fp8_blockscale_gemm \
  --history-run client/poc_kl/tune_out/runs/PRIOR_RUN \
  --search-policy path/to/search-policy.json \
  -- m=2560 n=2560 k=256
```

提示词要求先取得本次 original 的有效筛选，再调用一次 `history RUN HISTORY_DIR [--candidate ID]`。
该 CPU 入口校验原始 SHA、engine/runtime 身份、client 契约、构建策略以及历史证据与完整来源链。
兼容且额度足够时，最多尝试一次 `warm-start RUN HISTORY_DIR [--candidate ID]`，从当前 original
重新构建每一步，并交由本次静态门槛注册。读取和导入都不调用 client；驱动器也不代替模型自动执行它们。
详情见 [P2-b](../../proj/steps/geak-P2b-history.md)。

历史分数、旧确认和旧 incumbent 不进入本次测量或选择状态。导入返回的候选仍需本次 screen，
只有本次显式 `--comparison-policy` 才能允许 confirm/final；上例仍为筛选模式。
导入候选的筛选占 `--rounds` 目标次数，复用缓存不算新独立证据。

一次完整 N 步导入消费 **1 次请求 + N 次步骤提案**，同时计入全局提案和
`reuse_proposal_limit`；无效请求与重复步骤也按实际操作计费。筛选和完整确认须满足
`reuse_eval_call_limit`，保留 `independent_eval_reserve` 和 final reserve。
这些搜索额度可通过 `--search-policy` 显式配置，不改变统计政策，也不会自动增大 eval/proposal 总预算。
重复候选和后代保留 reuse 来源，不能改标签规避额度。

每个显式来源只检查一次、最多尝试一次 warm-start 是 SDK 提示词约定；错误、部分完成、中断或重复
都不自动重试，也不换历史路径或候选绕过限制。未完成导入须由用户显式 resume，恢复不会重跑步骤。
只有当前 run 仍允许搜索时才继续独立 observation 探索。控制器始终负责硬预算和恢复门槛。

可选重排组合：模型可调用 `tune_run.py replay RUN SOURCE_CANDIDATE_ID`（`combine` 同义）。
控制器从共同 original 重建两条谱系，把来源候选最后一步意图映射到当前父版本；歧义或冲突直接拒绝。
请求花 1 次提案，成功映射后的 prepare 再花 1 次，均不直接调用 client。输出候选仍需当前 run 的
screen/confirm/final。组合失败保持当前选择，各候选的收益不能相加。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `<seed.s>` | 必填 | 可编辑的汇编 seed；来源归档规则见下 |
| `--client SPEC` | 必填 | client 选择器，运行输出归属该 client |
| `--rounds N` | 6 | 模型目标候选筛选数；也用于推导默认硬预算，不是模型回合的强制计数 |
| `--proposal-limit N` | `4 * rounds` | 控制器硬提案上限，拒绝/重复 prepare 也占次数 |
| `--perf-repeats N` | 3 | 每个筛选 batch 的独立 client evaluate 调用数 |
| `--eval-calls N` | 见下 | 所有阶段的 client 调用总上限，包含参考侧 |
| `--comparison-policy FILE` | 无 | 用户显式选择的固定配对策略，默认仅筛选 |
| `--search-policy FILE` | 无 | 显式 JSON 搜索策略；方向/停滞/profile 等限制在 init 冻结，不自动增加总调用预算 |
| `--history-run DIR` | 无 | 一个显式历史来源目录；仅用于模型导航，兼容性由本次 history/warm-start 校验 |
| `--history-candidate ID` | 历史有效推荐/incumbent | 指定已确认历史候选；必须同时提供 history-run |
| `--final-reserve N` | 无策略 0；有策略 `2 * final_pairs`（分段策略取最后检查点） | 总预算内的 final 预留额度 |
| `--wall-seconds N` | 1800 | 控制器启动新工作前检查的总时限；不杀死已运行 client |
| `--loop N` | 20 | 冻结在 client 契约的 loop 参数，不是独立样本数 |
| `--kernel NAME` | 自动检测 | 冻结的 kernel 名称 |
| `--region SEL` | loop | 默认区域，或 all/auto/any 跨区域 |
| `--run-id ID` | 时间戳+随机后缀 | 新 run 的唯一名称；已有名称拒绝覆盖 |
| `--model ID` | 配置文件或 auto | 支持 `id,param=value,...` |
| `--config FILE` | tools/sdk/cursor.config.json | API key/model 配置 |
| `--transcript` / `--no-transcript` | 开 | 保存完整事件 JSONL 和可读 Markdown |
| `--transcript-path FILE` | RUN/transcript.jsonl | 自定义 .jsonl；自动创建父目录，校验实际路径与同名 .md 不覆盖运行证据或报告 |
| `--report-dir DIR` | RUN/report | JSON/Markdown 和派生汇编副本目录 |
| `--results-path FILE` | RUN/report/report.json | 兼容旧参数名称，现为完整 JSON 报告，接受 .json/.jsonl；同名 .md |
| `--results` / `--no-results` | 兼容接受 | 不再关闭权威证据或最终报告；只用 no-transcript 关闭模型事件记录 |

无策略的默认 eval 上限为 `(rounds + 2) * perf_repeats`；两个额外 batch 用于 original 与 normalized。
有策略时再加 `2 * confirm_pairs * max_confirmations + final_reserve`。
分段策略 `paired_sequential_v1` 中 `confirm_pairs` / `final_pairs` 取各自最后一个检查点的配对数；
提前停止时只消耗已测调用。
用户提供 `--eval-calls` 时直接采用指定值，控制器保护 final reserve；额度不足会拒绝操作。
预算计数是 client evaluate 调用数，不是底层 GPU launch 数或 client 内部计时循环数。

## 报告与恢复

[`tools/tune_run_report.py`](../tune_run_report.py) 从 `RunController.status()` 读取一致快照，
校验冻结 manifest。报告不运行 client，不从 SDK 事件、模型自述或旧 results JSONL 推断赢家。

| 文件 | 内容 |
|---|---|
| RUN/manifest.json | 冻结的 client 参数、引擎/runtime 身份、构建策略、预算、比较与搜索策略 |
| RUN/state.json | 权威状态：候选谱系、筛选 batch、逐次 attempt、配对样本和 final |
| RUN/artifacts/ | SHA 命名的输入、规范化版本、候选汇编归档 |
| RUN/input_provenance.json、RUN/inputs/ | SDK 记录的输入来源和原始字节；非冻结 manifest 的附注 |
| RUN/transcript.jsonl、RUN/transcript.md | 可关闭的模型提示词、事件和工具输入输出 |
| RUN/report/report.json、report.md | 筛选/确认/final 分开呈现；预算、失败、未完成工作与完整原始评测证据 |
| RUN/report/screening_best.s | 最新有效筛选分数最高者，可为 original；不是推荐 |
| RUN/report/confirmed_best.s | 完成 confirm 并晋升的 incumbent；不自动成为最终推荐 |
| RUN/report/selected.s | 仅 final 后生成；final 通过则为推荐，否则保留 original |

所有导出的汇编副本都校验归档及副本 SHA-256。报告重写时删除同名旧派生副本，
防止留下本次已撤销的 selected.s。归档异常写入错误报告，撤下推荐/选中副本，并返回非零。
final 未运行时 selected/recommendation 均为 null；original 回退不表示 original 刚经过 final 复测。
配对结果仅在有相应样本时报告；相对 normalized 的独立 final 比较目前未实施。
分数使用 client 的正向 tflops 字段，只有吞吐/时间倒数语义才可将比例解释为时间加速比。

```bash
# 随时 CPU 导出；不触发恢复或评测
python3 tools/tune_run_report.py client/poc_kl/tune_out/runs/RUN_ID
# 显式查看并恢复中断状态；恢复本身不重跑已占预算的调用
python3 tools/tune_run.py status client/poc_kl/tune_out/runs/RUN_ID
python3 tools/tune_run.py resume client/poc_kl/tune_out/runs/RUN_ID
```

SDK 只创建新 run，不自动续跑旧 run。后续动作按 [P0-c 协议](../../proj/steps/geak-P0c-paired-validation.md)
手动进行。中断时若客户端进程仍持有 run 锁，收尾报告可能被 `run_busy` 拒绝；待进程结束后重新导出，
不要绕过锁读写。SDK 不承诺 SIGKILL 或机器掉电时执行 finally；持久化证据仍由控制器负责。

transcript 的 JSONL 和派生 Markdown 都在写入前解析符号链接及已存在的父路径。
run 内只允许默认 `transcript.jsonl` / `transcript.md` 或 `transcripts/` 专用目录；
其他 run、显式指定的历史来源、输入准备目录、当前 run 的 authority/archives/report 和配置的报告输出均禁止用作日志。
run 外可自定义日志路径，但它们也不能经符号链接指回这些受保护位置。

旧 `tools/agent_session.py` 与 `tools/tune_summarize.py` 保留独立筛选接口，但本 SDK 默认不再调用它们。
旧 results JSONL 不是本报告的输入，也不会自动升级为确认结果。
既有 shell 入口的 `--results-path` 仍可指定输出位置，但文件格式变为完整 JSON 快照。

## 输入来源

SDK 接受 `.s` 汇编输入，在 `tune_out/sdk-inputs/<run-id>/attempt-<随机后缀>/input.s`
保存原始字节，并在 run 内保存汇编快照及 SHA。`.co` 输入会在创建输出目录前被拒绝。
每次初始化使用独立 attempt 目录；init 失败后可重新尝试，不覆盖之前的输入记录。
input_provenance.json 是 SDK sidecar，不证明 GPU 实际加载对象的身份。

## CPU 验证

```bash
node --test tools/sdk/run_workflow.test.mjs
python3 -m pytest -q unittests/test_run_report.py
```

测试使用假 runner/client，不调用模型或 GPU。目标 gfx942 的真实装载、性能收益与统计假设仍需真机验证。

| exit | 含义 |
|---|---|
| 0 | SDK 正常完成且收尾报告成功；不表示 final 一定通过 |
| 1 | 缺 API key 或 CursorAgentError |
| 2 | 参数错误或 SDK 非 finished 状态 |
| 3 | 初始化/运行/收尾异常 |
| 130 / 143 | 收到 SIGINT / SIGTERM，尝试导出已记录证据 |

---

# `articulate.mjs` —— 无头 Layer 2 离线 AI 归纳

把"读简报 → 写 `ai_proposal.json`"这一步从**人/Cursor IDE 里的 agent** 换成**程序化 Cursor agent**,
端到端跑完 Layer 2,**无需打开 Cursor IDE、无需 GPU**:

```
node articulate.mjs
   1. python3.8 tools/ai_skill_brief.py     ← 从挖出的量化技能导出简报(measured=ground truth)
   2. Cursor agent (local, cwd=FACK)       ← 读简报,产出 ai_proposal.json(选实测约束 + 标注外推)
   3. python3.8 tools/ingest_ai_skills.py    ← 闸门校验 + 落盘 ai-*.json
```

**红线由 Python 闸门强制,与模型输出无关**:实测数字按 ref 从 Layer 1 **逐字复制**(模型改不动/查无即丢弃),
外推项必带 `note` 且 `weight`/`confidence` 封顶并标 `source:ai-hypothesis`,scope 只取结构键,产物恒 `candidate`。
**模型输出再离谱,也只会被丢弃/封顶,绝不污染 store。** 摄入前会清掉旧的 `ai-*.json`(整套 AI 技能从新 proposal 重生成;`gold-*.json` 不动)。

## 前置

与 `tune.mjs` 相同:`npm install` 装 `@cursor/sdk`,并提供 `CURSOR_API_KEY`(env 或 `cursor.config.json`)。
另需先跑过挖掘(`bash study_case/study_script/mine_skills.sh` 或 `python3.8 tools/mine_corpus.py`),
`study_out/skills/` 下要有 `gold-*-quant.json`。

## 运行

```bash
cd /home/feifei/repo/FACK
node tools/sdk/articulate.mjs                       # 默认 --out study_case/study_out,产 proposal 并摄入
node tools/sdk/articulate.mjs --dry-run             # 摄入只打印不落盘(看闸门会接受/丢弃什么)
node tools/sdk/articulate.mjs --no-ingest           # 只产 ai_proposal.json,稍后手动 ingest
node tools/sdk/articulate.mjs --skip-brief          # 简报已在,跳过导出直接产 proposal
# 或: cd tools/sdk && npm run articulate
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--out P` | `study_case/study_out` | 挖掘产出目录(读 `ai_brief.*`、写 `ai_proposal.json`、落 `skills/ai-*.json`) |
| `--model ID` | `auto`(或 config 里的 `model`) | LLM 模型 id;`auto`=服务端选 |
| `--config P` | `tools/sdk/cursor.config.json` | API key/model 配置文件 |
| `--skip-brief` | — | 跳过导出简报(已存在时) |
| `--no-ingest` | — | 只产 proposal,不调闸门摄入 |
| `--dry-run` | — | 摄入走 `--dry-run`(只打印) |

模型的原始输出会存一份 `study_out/ai_articulate.out.txt` 备查。

## 错误码

| exit | 含义 |
|---|---|
| 0 | 正常完成(产出 + 摄入成功) |
| 1 | **没启动**:`CursorAgentError`(鉴权/配置/网络)或未设 `CURSOR_API_KEY` |
| 2 | run 启动了但失败(去 dashboard 查 `run.id`) |
| 3 | 其它异常 |
| 4 | 模型输出**解析不出** `{version,skills:[...]}` proposal(原始输出见 `ai_articulate.out.txt`) |

## 与 `mine_skills.sh` 的关系

`mine_skills.sh` 的 Layer 2 是"导出简报 + 若已有 `ai_proposal.json` 则摄入";`articulate.mjs` 正是
**自动产出那个 `ai_proposal.json`** 的一环。无头全自动流程:

```bash
bash study_case/study_script/mine_skills.sh   # 挖掘(产 gold-* + 简报;首次无 proposal 会提示)
node tools/sdk/articulate.mjs                 # SDK agent 产 proposal 并摄入 -> ai-*
```

> 仍是"脱离 IDE",不是"脱离大模型":`articulate.mjs` 背后是 Cursor 托管模型,要 key、要联网。
> 真正零 AI 的路是手写 `ai_proposal.json` 或干脆不跑 Layer 2(实测核心 `gold-*` 技能照常可用)。
