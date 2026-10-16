# FACK — 架构可插拔的指令级 AI 辅助优化引擎

把"AI 逐字改 ASM"反转为 **AI 发结构化操作 / 固定逻辑保合法重排 + 修补 pass 流水线 / 真机测量** 的指令级优化引擎。**独立实现**(自学成果通过 submodule 引用),核心引擎架构无关,硬件指令集收敛到 `isa/Target` 层(首个实现 gfx942)。

设计文档见 [`proj/`](./proj/);逐里程碑进度报告见 [`proj/steps/`](./proj/steps/);经审核的经验见 [`knowledge/`](./knowledge/README.md)(任何 Agent 的入口是 [`AGENTS.md`](./AGENTS.md))。

本项目从 `/home/feifei/repo/testft` 复制，保留 gfx942 与通用框架。
已排除 gfx1250 后端、WMMA 自学工程、专属 skill、MLA 用例及对应测试。
SDK 和 Web UI 的 seed 使用 `.s` 汇编；原始 testft 未修改。复制范围见 [复制说明](proj/copy-from-testft.md)。
此次仅做静态检查，未运行测试、构建、调优或模型会话。

## 自学成果：直接读取已有 skill

`selfstudy/` 是 [gfx_hw_prob](https://github.com/feifei14119/gfx_hw_prob.git) 的 submodule，
与 testft 同步锁定上游提交，工作区仅稀疏检出 `gfx942/`。
**默认跳过自学阶段**，直接读取 `gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/`。
`knowledge/skills/mfma-interleave-gfx942` 是指向该导出的相对软链接。

新 clone 或恢复依赖时，在 FACK 根目录运行：

```bash
bash tools/init_selfstudy.sh
```

脚本只初始化固定版本的子模块并配置 gfx942 稀疏检出，不运行自学、拟合或生成 skill。
普通调优不自动更新依赖。Git 稀疏设置不会随 gitlink 传播，所以新 clone 后也需要上述脚本。
详见 [selfstudy submodule 接入](proj/selfstudy-submodule.md)。

## 目录结构

```
reorder/      架构无关核心引擎:
              model / lexer / parser / emitter  (M0: parse->emit 逐字节无损)
              regions(区段切分) / depgraph(依赖图+合法移动窗口) / editor(reorder + propose/commit)
              waitcnt(计分板模拟与重算) / passes(修补流水线) / verifier(合法性校验)
              cost(区段级代价模型) / prefetch / optlevel
isa/          硬件指令集抽象层: target(架构契约) / registry / counters
              isa/gfx942/  具体实现(M1): classify / edges / operands / counters / lds /
                           invariants / passes / perf_schema / target
harness/      自带评测: toolchain(llvm-mc/clang) +
              evaluator(三阶段: 汇编->编译->真机+对拍; gfx942 ATT)
analysis/     perf counter 解析 + 瓶颈分类 -> 优化方向 (M4): perf / bottleneck
search/       搜索/策略层 (M6): movedsl / list_scheduler / driver(layout|order 候选)
agent/        元层知识/记忆 (M7): session(observe/propose/commit + 自适应裁决) /
              knowledge(技能归纳与召回; 读 knowledge/engine, 运行时产出写 client/<名>/tune_out) / tuner
selfstudy/    gfx_hw_prob Git submodule，仅检出 gfx942；直接读取 prob 的 skills_out
knowledge/    与工具无关的知识库(git 跟踪, 只收人工审核过的经验, 见 knowledge/README.md):
              skills/       给 Agent 读的经验(SKILL.md 格式; .cursor/skills 是指向它的软链接)
              engine/       给引擎读的结构化技能: skills/*.json(seed 阶段读取的先验)
tools/        CLI 工具: agent_session(CLI 桥) / tune_summarize(收尾汇总最好/最坏 kernel) /
              mine_corpus(从已优化 gold kernel 语料静态挖掘按区域 skill, Mode A) /
              eval_candidate / make_candidate / seed_knowledge / coldstart_demo / search_loop /
              diag_* / hw_validate*.sh
tools/sdk/    Cursor SDK 集成: tune.mjs(Node 驱动) / cursor.config.json(API key) / README.md(参数与用法全解)
unittests/    单元测试(标准库 unittest, 零安装) + 两种风格的 .s fixtures
client/       调优项目接入层(契约见 client/README.md): 每个项目一个 client, 自己决定怎么构建/判正确/计时,
              引擎只看 EvalResult。用 --client <client/ 下的路径> 选择; python3 -m client list 列出全部
              __init__.py  加载器(resolve / list_clients; 最近的 client.py 生效)
              poc_kl/      poc_kl 仓库的 kernel: client.py(exe 协议, 复用 harness.GpuTestcaseEvaluator)
                fp8_blockscale_gemm/  fp8 block-scale GEMM(poc_kl/mi300/fp8_blockscale_gemm 副本):
                           fp8gemm.cpp / gemm.exe / shader/*.s(被调优 kernel) / common/ / 编译产物 gemm.co /
                           att/(ATT trace) / *_result.hex(对拍) —— "贴着 kernel"的运行产物留在 case 目录
                tune_script/ 调优入口脚本(均"不接受任何参数", 调参写在脚本顶部 CONFIG 块):
                           tune_quick.sh(快跑 5 轮) / tune_prologue_epilogue.sh(无锚点尾段, 各 N 轮)
                tune_out/  该 client 的所有运行时输出(gitignore): experiments.log(评测日志) /
                           skills/(归纳出的技能, 人工审核后再复制进 knowledge/engine/skills) / transcripts/(SDK 会话+结果表) /
                           tune_shaders/(每轮候选 .s 存档, 文件名带时间/区段/裁决/TFLOPS) /
                           tune_result/(每次运行收尾: 最好/最坏 kernel 汇总 + 最好 .s 副本)
              (将来并列 aiter/、poc_kl 的其它 case 等)
study_case/   离线 skill 挖掘(静态, 不跑真机, 与 client 调优工作流分离):
              gold_corpus/ (可选)已人工优化(roofline 级)kernel 语料: 每子目录一个 kernel
                           (kernel.s + 可选 meta.json 边车), 或裸 *.s; 供 tools/mine_corpus 静态挖掘 skill
              study_script/ 挖掘入口脚本("不接受任何参数", 配置写在脚本顶部 CONFIG 块):
                           mine_skills.sh(每次运行前清空 study_out/skills, 再从 gold 语料挖掘)
              study_out/   挖掘产出(gitignore): skills/(gold-<class>-<region>.json 粗粒度 +
                           gold-<class>-<region>-quant.json 细粒度量化约束 +
                           ai-<class>-<region>-*.json 离线 AI 归纳) / mine_report.md /
                           ai_brief.json+.md(L2 导出)/ ai_proposal.json(外部 agent 写)
proj/         设计文档: 核心设计 + steps/(M0-M9 里程碑报告) + if/(AI 接口与验证) + brainstorm/ + skill/
```

## 输出与存放

为保持代码目录纯净,**所有运行时输出与代码分离**:

- **`client/<名>/tune_out/`** —— 该 client 调优产生的全部输出都落在这里(整目录 gitignore;例如 `client/poc_kl/tune_out/`):
  - `experiments.log`:每次真机评测一行 JSON(权威记录)。
  - `skills/`:`induce_skills` 归纳出的技能 JSON(在线实验)。**人工审核后**,自行复制进 `knowledge/engine/skills/`。
    (`tools/mine_corpus` 的**静态**挖掘产物改落 `study_case/study_out/`,见下。)
  - `runs/<run-id>/transcript.jsonl` / `.md`：默认 SDK 会话记录；结构化结果从权威 run 状态导出到 `report/`。
    结果表由 `agent_session.py eval` **确定性**写入(每次 eval 一行),不依赖解析 LLM 事件流。
  - `tune_shaders/`:每轮提交评测的候选 `.s` 存档(临时工作目录里的 `.s` 会被下一轮覆盖,这里留全量副本)。文件名 `<时间戳>_<kernel>_<region>_<verdict>_tf<TFLOPS>_pid<pid>.s`,可直接据此回溯/重放某轮 kernel。
  - `artifacts/`:原始 seed、规范化 baseline、候选的 SHA-256 汇编快照；结果 JSONL 的 `evidence` 保留每次 client 测量返回值。原始 seed 此阶段只归档，未单独测量。
  - `runs/<run-id>/`:独立 `tools/tune_run.py` 模式的 manifest、权威状态、汇编归档和批次工作文件；具备硬预算与恢复，并要求先测 original。默认 SDK 已接入同一控制器，报告位于 `runs/<run-id>/report/`，详见 [SDK 使用说明](./tools/sdk/README.md) 与 [实施总表](./proj/geak_rollout_status.md)。
  - `tune_result/`:**每次运行收尾自动生成**(`tools/tune_summarize.py`):`<stem>.summary.md/.json`(筛选最高/最低分及相对规范化 baseline 的差异)与 `<stem>.screening_best_tf<TFLOPS>.s`(待独立复测的候选)。兼容字段 `best` / `best_shader` 仍表示筛选最高分，尚无最终确认推荐。
- **`client/<名>/<case>/`** —— 只保留"贴着 kernel"的运行产物:编译出的 `<exe stem>.co`、`att/` 的 ATT trace 与代码对象 dump、`*_result.hex` 对拍文件(GEMM 用例为 `client/poc_kl/fp8_blockscale_gemm/`)。
- **`study_case/study_out/`** —— **静态 skill 挖掘**的产出(整目录 gitignore,与调优的 `tune_out` 分离):
  `skills/`(`tools/mine_corpus` 从 gold 语料挖掘的 `gold-<class>-<region>.json` 粗粒度 spec 先验 +
  `gold-<class>-<region>-quant.json` 细粒度量化约束 + Layer 2 离线 AI 归纳出的 `ai-<class>-<region>-*.json`)、
  `mine_report.md`,以及 Layer 2 的 `ai_brief.json/.md`(导出)与 `ai_proposal.json`(外部 agent 写)。
  `study_case/study_script/mine_skills.sh` 每次运行前会先清空 `study_out/skills`,再重新挖掘。**人工审核后**,自行复制进 `knowledge/engine/skills/`。
- **`knowledge/`** —— **只读的策展知识**(git 跟踪,与具体 Agent 工具无关,见 `knowledge/README.md`):
  `engine/skills/*.json` 由引擎在 seed 阶段读取作先验;`skills/<name>/SKILL.md` 给任何 Agent 读(入口 `AGENTS.md`)。
  调优和挖掘运行**不会**写入它。

机制:知识层读(`load_skills`/`seed_search_plan`)默认 `knowledge/engine`(`agent/knowledge.py` 的 `DEFAULT_STORE`),在线调优写(`log_experiment`/`save_skill`/`induce`)由 CLI 桥 `tools/agent_session.py` 显式路由到 `--client` 的 `tune_out`(不带 client 的纯 CPU 运行落 `agent/knowledge.py` 的 `DEFAULT_OUT_STORE`,即系统临时目录下的 `fack_tune_out`);**静态挖掘** `tools/mine_corpus.py` 写默认 `study_case/study_out`(其 `DEFAULT_OUT`)。

## 调优用法 (client 无关)

框架**不绑定任何具体项目**:用 `--client` 选调优项目(`client/` 下的路径,如 `poc_kl/fp8_blockscale_gemm`),
用 `--` 哨兵之后的参数把该项目需要的入参**原样透传**给 client(引擎不认识 `m/n/k` 等 shape 参数)。
换 kernel 只需换 `--client`、seed 和透传参数;接一个新项目只需写一个 `client/<项目>/client.py`(见 `client/README.md`)。

默认 SDK 通过持久化控制器保存探索父版本、限制 client 调用预算并支持中断恢复。也可直接使用
[`tools/tune_run.py`](./tools/tune_run.py)：`init → observe → prepare → eval → select-parent`。
初始化时用 `--comparison-policy FILE` 显式冻结配对规则后，还可通过 `confirm` 推进已确认父版本，
最后用单次 `final` 与 original 复测；未配置时只有筛选结果。
`eval` / `profile` / `confirm` / `final` 会调用 client evaluator，其余命令可在 CPU 上运行。
`suggest` 提供小批方向建议，`ledger` 查看假设与实际改动，`replay` / `combine` 组合版本绑定的意图，
`history` / `warm-start` 校验并逐步重建历史候选。历史分数不进入本次确认；`--search-policy FILE` 冻结
方向/profile/复用上限、独立探索预留和停滞规则。profile 默认关闭。
确认参数和统计假设尚未在目标 GPU 校准，实际 `.co` 装载证据也仍需 client 补充。
参数、结果语义与恢复步骤见 [实施总表](./proj/geak_rollout_status.md) 和 [SDK 用法](./tools/sdk/README.md)。

**最简单的方式 —— 用入口脚本(不带任何参数,调参写在脚本顶部 CONFIG 块)**:

```bash
./client/poc_kl/tune_script/tune_quick.sh              # 快跑;改 CONFIG 即可换 kernel/规模/区域
./client/poc_kl/tune_script/tune_prologue_epilogue.sh  # 无锚点尾段(prologue+epilogue)
```

`tune_quick.sh` 顶部 CONFIG:`ROUNDS`(轮数) / `REGION`(区域) / `CLIENT`(client spec) /
`SEED_REL`(seed `.s`) / `PARAMS`(透传给 client 的入参,GEMM 即 `m=/n=/k=`)。

**直接调 Node 驱动**:

```bash
cd tools/sdk
node tune.mjs <seed.s> --client poc_kl/fp8_blockscale_gemm --rounds 5 \
      --region loop -- m=2560 n=2560 k=256
```

| 关键参数 | 默认 | 说明 |
|---|---|---|
| `<seed.s>` | 必填 | 待调优 kernel 的 `.s` |
| `--client SPEC` | 必填 | 调优 client(`client/` 下的路径);决定怎么评测候选,输出落其 `tune_out/` |
| `--region SEL` | `loop` | 调优区域:`loop`/`prologue`/`epilogue`/`inter`/`loop#1`;`all`/`auto` 让 agent 跨区 |
| `--rounds N` | `6` | agent 最多提交评测多少个候选 |
| `--loop N` | `20` | 真机测量循环次数(取中位数) |
| `--transcript`/`--no-transcript`、`--results`/`--no-results` | 均开 | 是否存会话 transcript / 每轮结果 |
| `-- <...>` | — | 哨兵之后原样透传给 client |

跑完会自动:每次 eval 权威落一行结果(`transcripts/*.results.{jsonl,md}`)、归档候选 `.s`
(`tune_shaders/`),并收尾汇总最好/最坏 kernel 与最好 `.s`(`tune_result/`)。

> **完整参数与输出说明见 [`tools/sdk/README.md`](./tools/sdk/README.md)。**

## 从已优化 kernel 语料挖掘 skill (Mode A, 静态, testcase 无关)

把一批**人工调好(roofline 级)** 的 kernel 当作"标准答案",静态分析出**按区域(prologue/loop/epilogue)** 的
调优先验,产出 `candidate` skill 指导后续未优化 kernel。**不跑真机、不改代码树**,产物落 `study_case/study_out`,
人工审核后再手工复制到 `knowledge/engine/skills`。

```bash
# 推荐:入口脚本(配置写在脚本顶部 CONFIG 块,每次运行前自动清空 study_out/skills)
bash study_case/study_script/mine_skills.sh
# 或直接调用挖掘器:
python3.8 tools/mine_corpus.py [--corpus DIR] [--out DIR]
```

脚本顶部有 `VALIDATE` 开关(默认 `0`):`0` 仅静态产出 candidate skill(**无 GPU、可在一台机器上为任意架构总结**);
设 `1` 时在配置的 GPU testcase 上**额外做真机验证**(见上"真机验证开关")。

- `--corpus` 默认 `study_case/gold_corpus/`:每 kernel 一个子目录(放 `*.s`,`kernel.s` 优先 + 可选 `meta.json`
  边车给 `arch`/`kernel_class`/`family`),也支持根目录下的裸 `*.s`;可指向任意外部路径(脚本默认指向
  `/data/feifei/poc_kl/mi300/bf16gemm/shaders`)。
- `--out` 默认 `study_case/study_out`,产出 `skills/gold-<class>-<region>.json`(粗粒度 spec 先验)、
  `skills/gold-<class>-<region>-quant.json`(细粒度量化约束) + `mine_report.md`。
- **kernel 无关**:特征只来自语义指令 `Kind` + CFG 区域 + 依赖 DAG,`kernel_class`
  (`mfma_dense`/`mfma_sparse`/`lds_bound`/`memory_streaming`/`vector_only`/`mixed`)由 op-mix 自动推导,
  **绝不假设 GEMM/shape**;产物一律 `candidate`(永不自动晋升)。
- **细粒度量化层(Layer 1)**:对 MFMA 锚定的循环逐 gap **实测**布局画像并按 `(arch,kernel_class,region)`
  跨语料池化,产出带 `action.constraints`(每条带 `weight`)+ `conflict_groups` 的量化约束 skill:
  `mfma_gap_size`(两条 MFMA 间可插指令数)/`per_slot_capacity[kind]`(每槽某类指令容量,如"几个 lds")/
  `burst_runlen[kind]`(连发长度)/`intra_gap_order`(gap 内类型先后)/`adjacent_cooccur[kind]`(相邻槽共现率)。
  这些指标再**按指令子类型细分**:按开启 gap 的 **MFMA 形状**(`by_mfma_class`,如 `16x16x16`/`32x32x8`,
  周期不同则容量不同)与**访存位宽**(`per_slot_capacity[kind].by_width`,如 `128b`/`32b`)分别实测,
  并据此产出带 `mfma_class`/`width` 的精修约束 + 按形状的冲突组(Layer 3 按各 gap 的形状定容)。
  **所有数字仅来自 gold 实测、绝不臆造**;供(外部 LLM)调优 agent 按权重权衡冲突、生成多种候选排布后真机裁决。
- **离线 AI 归纳(Layer 2)**:让外部 AI agent 把上面的实测约束**表达得更具体/条件化**,并允许**外推**。
  仓内不内嵌 LLM,只提供两段确定性轨道:`tools/ai_skill_brief.py` 把量化 skill 导出为 `ai_brief.json/.md`
  (`measured` 为 ground truth + 可引用 ref + 红线 + 提案 schema);外部 agent 据此写 `ai_proposal.json`;
  `tools/ingest_ai_skills.py` 经**严格闸门**摄入——`extrapolated=false` 的约束按 ref **逐字复制 Layer 1 权威数字**
  (agent 改不动、查无即丢弃),`extrapolated=true` 必带 `note` 且 `weight`/`confidence` 封顶并标 `source:ai-hypothesis`,
  scope 只取结构键,产物恒 `candidate`(`source=gold_corpus(modeB-ai)`、`id` 以 `ai-` 区分)。
  Layer 2 在 `mine_skills.sh` 中**常开、无开关**(GPU-free):每次挖掘后自动导出 brief,若已有 `ai_proposal.json` 则校验摄入;支持 `--dry-run`。
  写 `ai_proposal.json` 这一步可由**人手写**,也可用**无头 SDK agent 自动产出**——`node tools/sdk/articulate.mjs`(导出简报 → Cursor agent 产 proposal → 闸门摄入),**脱离 Cursor IDE 即可全自动**(需 `CURSOR_API_KEY`);详见 `tools/sdk/README.md`。
- **在线消费(Layer 3)**:`agent/knowledge.py::seed_search_plan` 把量化约束 + `conflict_groups` 透传进
  `Observation.prior_plan`;约束消费器 `agent/layout_planner.py`(`AgentSession.plan_layouts()`)据此为目标
  kernel 的实际 fillers 生成**排好序的候选 gap layout**(冲突组展开成"打包 vs 摊开"变体,按 `weight×confidence`
  打分),并经 `propose()` 校验合法性——**纯 CPU、无约束则返回空**。
- **真机验证开关(Layer 3)**:`AgentSession.learn_layouts(validate=...)` 带开关闭环——`validate=False`(默认)
  只产出候选(纯 CPU,**不碰 evaluator**),可在一台机器上为**任意架构**总结 candidate skill;`validate=True`
  才把合法候选交 `commit_and_eval` 真机裁决(同样的正确性/Verifier/噪声门,写实验日志),并可 `induce` 晋升
  `trusted`。开关在 `study_case/study_script/mine_skills.sh` 的 `VALIDATE`(默认 0);独立验证入口
  `tools/validate_skills.py`(`--validate/--no-validate`,evaluator 惰性构造、可注入)。
- **技术原理与实现细节见 [`proj/gold_corpus_mining.md`](./proj/gold_corpus_mining.md)**;AI 辅助细粒度方案的
  完整设计/思路/步骤见 [`proj/skill/ai_assisted_skill_mining.md`](./proj/skill/ai_assisted_skill_mining.md),
  当前进度与后继条目见 [`proj/skill/STATUS.md`](./proj/skill/STATUS.md);脑洞与按区域学习的动机见
  [`proj/brainstorm/mine_skills_from_gold_kernels.md`](./proj/brainstorm/mine_skills_from_gold_kernels.md)。
  Mode B(合成基线 diff + 真机佐证晋升 `trusted`)为后续。


## 运行测试 (零安装)

代码目标 Python 3.8+,测试用标准库 `unittest`,无需安装 pytest:

```bash
cd testft
python3.8 -m unittest discover -s unittests -t . -v
```

(若已安装 pytest 亦可: `python3.8 -m pytest`)

## M0 现状

- `reorder.parse(text)` / `parse_file(path)` -> `Program`(逐行分类: blank/comment/directive/label/instr/other)。
- `reorder.emit(program)` / `write(program, path)` -> **逐字节无损还原**原文件。
- 验收门: `tests/test_roundtrip.py` 对两种风格 fixtures(GEMM `label_XXXX:` / k_vadd `.label`+`.set`)验证 parse→emit 字节相等,并校验分类计数非平凡。

## aiter HSA client

通过 `client/aiter/upstream` submodule 接入 ROCm/aiter；先在目标机器运行 `bash tools/init_aiter.sh`。
架构入口、seed 转换、校验与调优命令见 [client/aiter/README.md](client/aiter/README.md)。
普通调优继续默认跳过自学，使用 selfstudy 的已有导出。

<!-- fack:tuning-results:start -->

以下为各输入尺寸下通过最终验证的候选，性能提升按配对比值计算；不表示整份 `.co` 的所有尺寸均可替换。

| 序号 | co 名字（含路径） | 输入尺寸 | 性能提升 | 调优时间（UTC） |
|---|---|---|---|---|
| 1 <!-- fack:result:6e782f668307041d2335bad4e56a0b17755ed679d5b2cd3b3c012869c0be50a1 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co](client/aiter/co_out/.versions/b409b1ba9c475edf195487999c715453fc7c638df0a8b8eb0c00dea07d7c17d3/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co) | M=32; N=8192; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +8.28%<br>op_test:constant/constant: +6.25%<br>op_test:uniform/auto: +6.17% | 2026-10-15T02:46:22+00:00（耗时 9.0 分钟） |
<!-- fack:tuning-results:end -->
