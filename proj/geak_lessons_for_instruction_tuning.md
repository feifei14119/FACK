# 从 GEAK 借鉴的单 kernel 指令调优改进设计

> 实施状态：P0–P2 的 CPU 可验证软件入口已落地，默认 SDK 使用同一持久化 run。
> 具体提交和验收见 [实施总表](./geak_rollout_status.md)，调用接口以各阶段记录为准；
> 本文保留设计动机，草拟接口不等同于最终 CLI 的逐字规范。
> 已实现 client/构建证据、假设账本、多方向建议、独立 profile、组合重放与历史 warm start。
> 目标 GPU 正确性、真实装载身份、统计校准和性能收益仍待 [真机验收](./steps/geak-hardware-acceptance.md)。
>
> 整理日期：2026-10-13。testft 代码审阅基点：`814f8c5`；GEAK 参考版本：
> [v4 主分支提交 ba509ef31d416350269266b626ec455e9d9475d1](https://github.com/AMD-AGI/GEAK/commit/ba509ef31d416350269266b626ec455e9d9475d1)
> （2026-10-10）。结论来自文档和代码阅读，未进行两框架的 GPU 性能对比。

## 1. 目标与范围

**testft 的目标保持为：对现有单个 kernel 做指令级重排，通过真机评测找到更快且正确的版本。**

借鉴 GEAK 的实验组织机制，增强现有引擎外层的搜索与验证。实现继续沿用以下职责：

- Agent 决定试什么，提交 layout、order、move 或调度器权重等结构化意图。
- `reorder/`、`search/` 和 `isa/Target` 实现受约束重排、等待与 hazard 修补和静态检查。
- 真机构建、正确性、计时与可选 profiling 仍由 `client/` 完成。
- 运行证据写入 `client/<名>/tune_out/`；经验晋升遵守人工审核流程。

本轮设计不扩展到算法改写、tile/数据布局变更、算子融合、跨语言生成、host/runtime 或模型服务调优；
也不增加重排引擎目前不能表达的循环变换。既有修补 pass 为保持正确性而插入、删除、重建等待等指令的职责保留。
GEAK 仅作为设计参考，不引入运行依赖或对接要求；第一版采用单 Agent 与串行 GPU 评测。

静态检查只在当前 ISA 模型覆盖范围内提供保障，不能替代真机数值检查。
`build_candidate` 对 seed 已有静态告警的兼容策略必须如实记录，不能包装成完整语义等价证明。

## 2. 值得借鉴的机制与优先级

| 编号 | GEAK 的可取之处 | 在 testft 中的落地 | 优先级 |
|---|---|---|---|
| G1 | 独立复测、固定原始参考、最终验证 | 分离原始/规范化 baseline；筛选、确认、最终复测分阶段 | P0 |
| G2 | 程序管理预算、当前最佳版本和跨轮状态 | 持久化调优控制器；版本绑定；可恢复、可累积的搜索 | P0 |
| G3 | Hypothesis ledger 与失败记忆 | 记录假设、实际变换、证据和结论；精确去重与失败分类 | P1 |
| G4 | 不同专项方向探索、获益后重新 profiling | 单 Agent 提出不同调度假设；先比较方向，再局部细化 | P1 |
| G5 | Integrator 组合有效补丁 | 引擎重放、重建和验证有效重排的组合 | P2 |
| G6 | 历史补丁 warm start、限制知识引导额度 | 历史最佳重新验证；策略按版本匹配；保留独立探索预算 | P2 |

P0 先解决结果可信和收益累积；P1 提高每次真机实验的信息量；P2 在前两者稳定后提高复用效率。
多 Agent 层级本身不列为改进目标。实验控制和验证用固定程序实现即可。

## 3. 当前实现依据

下表区分现有能力和待补充的部分，描述的是上述代码基点，尤其是 `tools/sdk/tune.mjs` → CLI 通路。

| 位置 | 当前已实现 | 本文要补充的能力 |
|---|---|---|
| [`agent/session.py`](../agent/session.py) `observe/propose/commit_and_eval` | 结构化事实、非提交试排、候选构建、真机裁决 | 跨调用的运行状态、明确的候选谱系与分阶段裁决 |
| 同文件 `_measure_baseline` | 测量经过 L1 重算的 seed | 原始输入和规范化版本分别留存、分别比较 |
| 同文件 `_verdict` | 正确性门槛；性能噪声区间；区间内静态代价打破平局 | 探索价值与真机确认收益分开表示；最终独立确认 |
| [`tools/agent_session.py`](../tools/agent_session.py) `main` | 每次 CLI 调用创建 session；eval 权威写结果 | 统一 run 状态、预算入口与版本检查 |
| [`tools/sdk/tune.mjs`](../tools/sdk/tune.mjs) `PROMPT` | 提示 Agent 最多执行指定轮数，使用同一入口 seed | 由程序强制执行预算与最佳版本推进 |
| [`search/driver.py`](../search/driver.py) `build_candidate/search` | 确定性候选构建、有限 spec 搜索、重复测量取中位数 | 将构建后候选作为不可变评测对象；实际候选去重 |
| [`tools/tune_summarize.py`](../tools/tune_summarize.py) `main` | 从正确候选记录中选择 TFLOPS 最高者并归档 | 区分筛选最高、已确认最佳与最终推荐 |
| [`agent/knowledge.py`](../agent/knowledge.py) | 实验日志、先验召回、按组归纳经验 | 假设和候选级身份、失败分类、细粒度的条件化结论 |

两个需要保留的实现细节：

1. `_verdict` 有噪声区间逻辑，但 `AgentSession.noise_margin` 默认 `0.0`，当前 CLI 未显式传入非零值。
   “已有噪声参数”不等于当前默认运行已经做了统计确认。
2. `_transform_id` 对 layout/order 等形式目前主要退化为 `kind`，适合粗粒度导航，不能作为具体候选身份。
   一个 layout 的反例不足以说明所有 layout 都应被避开。

## 4. G1：建立独立复测与最终结果契约

### 4.1 借鉴与价值

GEAK 用独立 Verify 在干净工作目录重新运行候选，最终再与原始 baseline 验证。
testft 借鉴的是独立构建、独立样本和统一裁决协议；不需要让另一个 LLM 判断性能。

指令调度常在已有较快 kernel 上寻找小收益。大量候选中最高的一次测量容易包含偶然波动，
因此“筛选最高分”应是复测入口，不能直接成为最终推荐。

### 4.2 明确四个版本身份

| 身份 | 含义 | 生命周期 |
|---|---|---|
| `original` | 用户输入的原始 `.s`，或保留原始 `.co` 并关联经过 round-trip 检查的 `.s` | 全程不可变，最终比较参考 |
| `normalized` | 原始 seed 经本次明确记录的引擎策略生成的规范化版本 | 不可变，记录策略、作用区域与版本 |
| `incumbent` | 已通过确认门槛的当前最佳版本 | 仅由控制器更新 |
| `exploration_parent` | 下一次变换基于哪个版本，可为 incumbent 或受预算限制的探索候选 | 每次提案显式指定 |

先通过 client 测量并检查 original，再检查 normalized。不能假设规范化一定正确或更快；
规范化失败、退化或无法稳定测量时，应保留 original 并记录结论。
改变 region、修补配置或工具链生成的新规范化版本具有新身份，不能沿用旧 baseline 数值。
规范化本身若有确认收益，也可成为 incumbent，但报告应标明收益来自规范化。

original 不能构建或不能通过正确性时，该运行不能声称已相对原始 kernel 提速；
先将其记为基线建立失败，而不是静默更换参考。`.co` 来源同时记录原对象与转换后汇编的身份。

### 4.3 三阶段测量

| 阶段 | 对象 | 处理 |
|---|---|---|
| `screen` | 新的合法、非重复候选 | 通过 client 检查正确性和较低成本计时，筛选值得确认的候选 |
| `confirm` | 领先候选 | 与 incumbent 交错 A/B，平衡先后次序，使用新样本决定是否更新 incumbent |
| `final` | 搜索结束时的少量候选 | 独立重新构建，与 original 交错 A/B；保留最终确认通过的推荐版本 |

比较使用现有 `EvalResult.tflops` 所表示的“越大越好”的正值分数，避免引擎硬编码 FLOPS 或 shape。
对相同评测契约，一组匹配测量的比例为 `candidate_score / reference_score`。
仅在分数确实等于吞吐或 `1/time` 时，该比例才等价于执行时间加速比；其他 client 指标应使用其声明的语义。
保存每次原始 `EvalResult`、配对关系、样本顺序和汇总方法，不能只存一个最大值。

确认规则在运行开始前写入 manifest：最低有意义收益、样本数/上限、区间估计方法和预算。
建议以配对比例的区间下界超过 `1 + min_gain` 为确认条件，并使用独立完整评测轮次作为样本单位；
client 内部计时循环不能冒充独立样本。样本或环境不足以支持确认时，结果是 `inconclusive`。
第一版可采用固定样本方案；以后增加自适应复测时，须预先定义停止规则，避免反复测到“赢”为止。
具体阈值需用目标 client 的波动评估确定，不照搬 GEAK 的阈值，也不在本文中声称统计方法已经校准。

已实施子集采用 `paired_sign_v1`：固定偶数对、AB/BA 交替、总体中位数的单侧非参数界，
确认的 alpha 按预设确认上限分配；final 仅比较当前 incumbent 与 original。
无默认确认参数，同一候选/参考不重复确认，final 结束 run。完整规则、统计假设和当前限制见
[P0-c 实施记录](./steps/geak-P0c-paired-validation.md)。

所有真机调用均走 client；A/B 的两侧使用同一测试契约和正确性标准。
同一 GPU 的计时与 ATT 串行执行。GPU 锁只约束遵守锁的任务，不能据此断言没有外部干扰。
client 负责候选 `.s` 实际装载，建议在 `detail` 中返回构建产物路径/摘要和可用的环境信息；
无法提供的字段标记未知，不能伪造装载证明。最终复测使用独立构建产物或由 client 明确刷新被加载对象。

### 4.4 分开搜索裁决和最终裁决

- `promising`：低成本筛选显示可能更快，等待确认。
- `exploration_only`：真机差异未确认，但静态代价等证据支持继续有限探索。
- `confirmed_gain`：通过确认，允许更新 incumbent。
- `inconclusive`：样本不足或波动过大，不能确认收益。
- `regression`：有效测量支持退化。
- `final_recommended`：最终独立复测确认优于 original。

保留现有“噪声内用模型提供搜索梯度”的思想，但 `exploration_only` 不覆盖已确认的 incumbent。
搜索中发现明显退化或错误结果时，模型不能把它升级为 confirmed gain。
确认通过但最终未复现的候选，记录最终失败证据并撤销推荐；若没有候选通过 final，推荐 original。

### 4.5 改动入口与验收

主要入口为 `agent/session.py`、`harness/evaluator.py`、`tools/tune_summarize.py`，以及可选的 client 证据字段。
旧 `accepted` 字段保留兼容语义，新运行使用显式 stage/verdict；旧日志只能作为历史筛选结果，不能自动升级为 confirmed。

验收：一次异常高分不直接成为最终推荐；静态模型改善不冒充实测收益；没有正确且确认更快的候选时返回 original。
报告分别给出最终相对 original、normalized 的收益，比较所用样本与构建身份可追溯。

## 5. G2：用持久化控制器组织跨轮搜索

### 5.1 控制器职责

控制器位于 `agent/run.py`；以下为完整目标，当前子集见 [P0-b 实施记录](./steps/geak-P0b-persistent-run.md)：

- 创建并冻结运行 manifest，建立 original 与 normalized。
- 验证提案父版本；调用现有重排引擎；登记实际候选。
- 统一分配 CPU 提案、client 评测、ATT、确认和最终复测预算。
- 推进 incumbent，保留探索分支，触发下一轮 observation。
- 根据预算、停滞与错误状态结束搜索；中断后恢复。

Agent 仍通过现有 CLI 决策面工作。SDK 负责模型会话，控制器负责接受哪个动作、评测哪个不可变候选。
确定性指流程、版本和裁决规则可重放，不表示 Agent 提案或 GPU 测量每次完全相同。

### 5.2 预算按实际支出计数

| 字段 | 定义 |
|---|---|
| `proposal_limit` | CPU 提案次数上限，包含被拒绝的请求，避免无效提案无限循环 |
| `eval_call_limit` | 控制器调用 client `evaluate` 的总次数，包含 baseline、候选、确认、final 和重试 |
| `profile_call_limit` | 请求 counters/ATT 的调用上限；若同次调用也做评测，它同时属于 eval 总量 |
| `final_eval_reserve` | 从 eval 总量中预留给最终比较的额度，包含参考侧测量，不是额外预算 |
| `wall_time_limit` | 总耗时上限；启动新任务前检查并为收尾留余量 |
| `stagnation_limit` | 连续有效、非重复实验无确认收益的停止/换方向条件 |

兼容现有 client 只提供 `evaluate` 的契约，不要求首版拆出每个 client 的内部计时循环。
client 内部重试和 GPU 执行次数如可观测则放入 `detail`，同时记录墙钟开销；
控制器的调用计数不能被描述成精确的 GPU launch 数。GEAK 的“优化方向预算”也不能直接当作 testft 的真机次数。

### 5.3 版本绑定与候选累积

每次提案必须携带 `base_sha256` 与 `observation_id`，其中 observation 绑定父汇编、Target/策略版本与选区。
指令 ID 只在对应解析版本内稳定。父版本变化后重新 observe；过期提案返回 `stale_observation`，不能猜测 ID 的新含义。

例如，loop 优化 A 获得确认收益后，以 A 为父版本重新观察 epilogue，再生成 B；
最终 B 同时保留 A 的有效改动，original 仍作为全程比较参考。候选必须记录 `parent_id`，可恢复整个变换链。
改变 `loop#N` 等选择器所对应的实际区域时，也必须重新确认选区身份。

### 5.4 原子状态与恢复

候选文件写入归档并计算摘要后，先登记 `prepared`，再启动评测。
每次外部调用前登记 attempt 和预算占用，返回后持久化原始结果，最后原子替换状态快照。
第一版每个 run 只有一个写入控制器，并使用锁避免两个恢复进程同时推进。

恢复时检查 manifest、候选摘要和未完成 attempt；不能把未完成调用当作通过，也不能自动重新执行以绕过预算。
进程中断后无法确定调用是否已执行的 attempt 保守计入预算，重试生成新 attempt。
环境、client 参数、工具链或引擎策略改变时，旧样本只作历史证据，需要重新建立比较条件。

验收：超预算请求被程序拒绝；确认赢家后下一轮基于其版本；旧 ID 被拒绝；
中断恢复不会丢失最佳候选、重复采用同一结果，或把旧环境的性能当成当前确认值。

## 6. G3：假设账本、失败分类和实际候选去重

### 6.1 假设与证据分别保存

提案除结构化操作外，增加简短的 `hypothesis`、`expected_observable`、`source` 和 `evidence_refs`。
`source` 区分当前 observation、profile、历史实验和 knowledge；Agent 的因果解释标为解释，实测数值由程序填写。

一次实验的记录应回答：基于哪个版本、想验证什么、实际改了什么、观察到什么、下一步是否值得继续。
ATT 缺失时允许只得出“该候选更快/未更快”，不能从性能变化自动推导出已经证实的 stall 原因。

### 6.2 失败类型影响下一轮行动

| 结果类别 | 含义 | 后续行动 |
|---|---|---|
| `illegal` | 违反引擎约束 | 提供依赖/窗口原因；调整意图，不上机 |
| `partial` / `no_change` | 请求仅部分实现，或修补后没有有效变化 | 回传实际变换；不得声称已完整检验原假设 |
| `duplicate` | 同一评测条件下已有相同实际候选 | 复用记录；仅显式复测可再次花预算 |
| `compile_failed` | 候选构建失败 | 保存诊断，检查引擎/工具链问题 |
| `incorrect` | 构建成功，数值检查失败 | 拒绝该候选，记录具体反例 |
| `measurement_invalid` | 未装载候选、输出缺失、环境干扰等导致测量无效 | 修复或重试；不归纳性能退化 |
| `inconclusive` | 有效但无法确认差异 | 按剩余预算复测或保留未知 |
| `regression` / `confirmed_gain` | 有效测量支持性能结论 | 更新假设和搜索优先级，或推进 incumbent |

这些是不同阶段的结果，不压成单一布尔字段。构建失败不能被解释成数值错误；
没有正确性结论的样本不能进入确认。环境失败也不能变成永久避开的优化规律。

### 6.3 按构建后的真实内容去重

保存两种身份：`intent_id` 标识绑定父版本的提案，`artifact_sha256` 标识全部修补完成后的精确 `.s` 字节。
同一运行内以“artifact + 评测契约”识别重复评测；跨环境命中只能作为历史信息。
首版采用保守的字节身份，不删除未知 directive、metadata 或指令后再声称语义相同。
以后可增加经验证的可执行内容指纹，提高仅格式不同候选的命中率。

不同意图可能因合法窗口限制而生成同一候选，应关联同一 artifact。
与父版本完全相同的候选标为 no-change；只改变了修补指令时，明确标记修补变化。
必须在昂贵评测之前保存实际变换摘要，避免“想移动成功”与“真的移动成功”混淆。

### 6.4 经验必须保留适用条件

扩展 `agent/knowledge.py` 的记录与归纳入口，避免只按 `layout` 或 `order` 聚合正反例。
具体证据至少绑定架构、父版本、区域、操作模式和 client 评测契约。
可迁移的经验需要结构化模式与适用条件，不能将裸 IID 作为跨 kernel 技能。
知识产生的候选继续写运行输出目录，按 `knowledge/README.md` 审核后晋升。

验收：两种意图落成同一汇编只评测一次；被跳过的关键移动不被误认为已验证；
一次特定 layout 的失败不会生成“所有 layout 都不可取”的结论。

## 7. G4：多方向探索与按需重新观察

借鉴 GEAK 的专项思路，在单 Agent 中提出不同调度假设。候选方向可围绕异步操作提前量、
计算/访存交错、关键依赖链、同一区域内不同阶段的排布等形成；具体动作仍由已有引擎表达和裁决。
这些只是方向类别，不是新的 ISA 性能规则，也不硬编码某类 kernel 的固定排布。

建议搜索流程：

1. 从当前 observation 的合法窗口、可动集合、关键段与可用性能证据提出少量不同假设。
2. CPU 试排、构建、去重后，再为不同假设分配少量真机筛选机会。
3. 对出现确认收益的方向做局部细化；有效实验持续无收益时转向其他假设或区域。
4. incumbent 明显变化、瓶颈解释失效、或实测与模型持续冲突时，重新采集可用 profile。

复用现有 `suggest_orders`、`plan_layouts`、合法窗口和 `est_cycles`，不新建另一套调度引擎。
模型主要用于排序与预筛；除硬约束外，保留少量不受模型排名支配的候选，防止模型盲区排除真机赢家。
ATT 缺失或置信度低时仍可搜索；计时与采样使用不同调用并记录不同目的。

验收关注相同 GPU 预算下的独立候选数量、首次确认收益所需次数，以及重复无效方向是否减少。
单 Agent 先验证这些收益；如未来引入并行，CPU 构建与 GPU 计时的并发策略须分别设计。

## 8. G5：组合已验证的有效重排

GEAK 的 Integrator 用于组合源码补丁；testft 的对应操作是基于版本的受约束变换重放。

- **增量组合**：以获益后的 A 为父版本，重新 observe，再生成 B。首版优先支持此形式。
- **兄弟候选组合**：A、B 都来自 O 时，需要在 A 上重新表达 B 的意图，不能直接把 O 的 IID 套到 A。
  无可靠匹配时返回需重新提案，不做模糊自动映射。

组合候选重新经过 parse、区域/依赖建模、变换、修补、静态校验与 client 评测。
不改变既有移动边界，不拼接独立 `.s` 文本 diff。即使位于不同区域，等待状态和性能也可能产生交互。
不得为每个新父版本重新“豁免”更多告警；记录 original 已有告警、候选新增告警与通过的策略，防止沿变换链累积未审视的模型缺口。

预算允许时对少量有希望的组合比较 O、A、B、A+B；不枚举所有组合。
收益用实测计算，不能将 A、B 的百分比相加。组合未优于 incumbent 时保留已确认的单独方案。

验收：A+B 的证据和谱系完整；组合失败可回退；旧 IID、文本补丁和新增静态告警不会绕过引擎约束。

## 9. G6：历史复用与知识引导额度

### 9.1 复用分三个层级

| 匹配程度 | 允许复用 | 采用前处理 |
|---|---|---|
| 相同 seed 和评测契约 | 历史最佳 artifact 和操作链 | 校验摘要，在当前机器重新检查和确认 |
| 同 kernel 的新版本 | 已保存的假设、操作模式、可明确匹配的结构 | 重新 observe、构建和验证，不复用旧 IID |
| 不同 kernel | 带适用条件的知识和调度策略 | 仅作为新提案先验，完整通过本次引擎和 client |

历史命中身份包含 source/kernel、ISA、client 参数、工具链、引擎/修补策略和已知设备信息。
字段缺失意味着匹配置信度不足，不意味着自动通配可直接采用。
历史排名只决定先测谁，不决定当前赢家；失败则在剩余预算内回到正常搜索。

### 9.2 给当前证据保留探索机会

借鉴 GEAK 的 `KB_DIR_CAP` / `KB_COLD_DIRECTION`：每批候选限制纯知识引导的方向数量，
并在预算允许时保留依据当前 observation/profile 独立提出的方向。
具体比例作为可调配置，用消融实验决定，不照搬 GEAK 的数值。
候选记录实际引用的知识，便于检查效果；文本来源声明不能严格证明没有受到其他上下文影响。

既有 ISA 硬约束始终生效；可限制的是性能经验对探索预算的占用，不能把合法性检查当成可关闭的先验。
一条历史负面经验只降低同条件方向的优先级，不能变成新的硬合法性约束。

历史 artifact 留在运行归档；归纳 skill 留在候选输出。保留人工审核晋升流程，
也不照搬 GEAK 对知识卡绝对数值的统一限制：testft 的受控周期测量可有复用价值，但必须附硬件、条件和出处。

验收：历史赢家不能跳过当前确认；版本不匹配不套 IID；开启知识后仍有独立探索机会；
运行不会自动修改 `knowledge/`。

## 10. 最小接口与数据结构建议

以下接口、文件和 JSON 均为拟议形式，示例数值/ID 不代表真实实验结果。

### 10.1 引擎与控制器的连接

```text
Agent: hypothesis + base identity + existing transform spec
  → RunController: version / budget / proposal checks
  → existing engine: materialize + fixups + static verification
  → immutable candidate: bytes + digest + actual-change report
  → client: screen → confirm
  → RunController: ledger / incumbent / next observation
  → client: final comparison with original → final report
```

建议将现有 `_commit_spec` 的构建与评测拆为可复用步骤，例如：

```python
# 拟议接口；不是当前可调用 API。
prepared = prepare_candidate(parent_src, spec, policy)
result = evaluate_prepared(prepared, client_evaluator, measurement_plan)
```

`prepare_candidate` 复用 `build_candidate`，扩展返回静态诊断、原有告警、实际移动与修补摘要。
`evaluate_prepared` 评测已归档的确切字节，不再基于 Agent 意图重建一个可能不同的候选。
现有 `commit_and_eval` 和无状态 CLI 可保留为兼容包装；新增 run 模式统一经过控制器。

### 10.2 提案示例

```json
{
  "schema_version": 1,
  "run_id": "run-example",
  "base_sha256": "<parent source sha256>",
  "observation_id": "obs-example",
  "hypothesis_id": "h-example",
  "hypothesis": "提前当前区域中的独立异步操作，尝试增加与消费者之间的重叠",
  "expected_observable": "实际移动完成；整核计时改善；有 profile 时检查相关等待变化",
  "source": "observation",
  "evidence_refs": ["obs-example"],
  "spec": {"kind": "order", "region": "epilogue", "order": [120, 124, 122]}
}
```

`expected_observable` 是待检验预测。IID 仅为示例，必须从对应 observation 取得。
`spec` 沿用已有动作词汇；协议本身不授权任意改写汇编或删除计算。

### 10.3 文件布局与职责

下列为完整设计布局。P0-b 首批将所有状态和记录原子保存在单一 `state.json`，汇编放 `artifacts/`，
没有独立 events/measurements/hypotheses 日志。后续 P0-c 将比较与 final 结果也放入 `state.json`，
尚未生成本示意中的独立 final 目录；不能按本示意推断全部功能已经实现。

```text
client/<name>/tune_out/runs/<run_id>/
  manifest.json       # 不可变：输入身份、client 契约、软件/硬件信息、预算和测量规则
  state.json          # 可恢复快照：incumbent、探索父版本、预算、待处理任务、状态版本
  events.jsonl        # 顺序事件：动作请求、预算占用、状态转移、恢复决定
  hypotheses.jsonl    # 假设与带证据的结论事件
  baseline/           # original、normalized 及其摘要/转换/构建信息
  candidates/<id>/    # candidate.s、父版本、意图、实际变换、静态检查记录
  measurements.jsonl  # 每次 client 调用原始结果、attempt、阶段、比较组和摘要
  final/              # 最终报告、比较证据、推荐 .s 或 original 回退说明
```

manifest 中 `client_params` 按 argv 列表原样保存，不解析、不排序、不合并重复参数。
`loop` 提示、kernel 选择、client 版本、外部评测资源版本和已知环境设置另行记录；
秘密凭证不写日志，无法固定的外部条件标明未知。
实际 `.co`、ATT 等贴着 kernel 的产物仍遵循 client 自己的目录契约；运行目录可记录引用和摘要。

各层标识建议如下：

| 对象 | 关键字段 |
|---|---|
| 候选 | `candidate_id`、`parent_id`、`artifact_sha256`、`intent_id`、`hypothesis_id`、`region_identity`、`build_policy` |
| 构建/检查 | `requested_spec`、`realized_changes`、`skipped`、`fixup_changes`、`static_findings`、`inherited_findings` |
| 测量 | `attempt_id`、`stage`、`candidate_id`、`reference_id`、`pair_id`、`eval_contract_id`、时间戳、原始 `EvalResult` |
| 裁决 | `verdict`、使用的 attempt 列表、汇总值、区间与阈值、是否更新 incumbent |
| 状态 | `state_version`、`incumbent_id`、`exploration_parent_id`、预算占用/消耗、pending attempts、停止原因 |

`experiments.log` 和旧 results 文件可继续作为兼容输出，由同一权威事件派生，避免两个独立写入者给出不同结论。

## 11. 实施顺序与验收

| 阶段 | 具体工作 | 主要位置（新增项标“拟议”） | 完成标准 |
|---|---|---|---|
| P0-a：结果身份 | 分离 original/normalized，保存确切候选与原始测量，明确筛选/最终结果 | `agent/session.py`、`tools/tune_summarize.py`、client 可选证据 | 任一结果能追到实际输入；无确认时不会输出“确认提速” |
| P0-b：可靠控制 | 独立入口已实现 run 状态、硬预算、版本检查、恢复、配对确认与 final；装载身份/真机校准待验证 | `agent/run.py`、`harness/measurement.py`、`harness/comparison.py`、`tools/tune_run.py`；默认 SDK 已接入 | 可累积收益、可恢复、不超额；final 不通过时保留 original |
| P1-a：实验质量 | 假设账本、失败分型、实际候选去重 | 控制器、`agent/knowledge.py`、`search/driver.py` | 不重复测相同新候选，不将环境故障归纳成性能规律 |
| P1-b：搜索效率 | 多方向提案、获益方向细化、按需 ATT | Agent 提示与控制器、现有 observation/suggest | 相同预算下首次收益更早或最终收益更高 |
| P2-a：收益组合 | 增量组合，再考虑兄弟候选重放 | 控制器与现有 editor | 组合完整验证；不能套旧 IID 或相加收益 |
| P2-b：经验复用 | 历史候选匹配、重新确认、知识额度 | 运行归档、`agent/knowledge.py` | 可回退正常搜索，人工晋升边界保持 |

第一批实现以 P0-a/P0-b 为最小闭环：先把“最终哪份 kernel 更快”及“怎样继续优化它”做可靠，
再增加搜索策略。不得为外层控制器顺带改动 ISA 规则或调整 client 的正确性容差。

### 11.1 实现时应覆盖的 CPU 回归

使用可控的假 evaluator 测状态和裁决语义，真实汇编 fixture 测候选身份和版本绑定：

- 原始 baseline 构建/正确性失败，或 normalized 回退时的处理。
- 单次异常高分、噪声内平局、静态代价改善、最终复测退化的结果归类。
- 预算临界点、最终额度预留、profile 计数、未知完成状态 attempt 的恢复。
- 过期 observation、候选文件摘要不符、父版本推进后的重新观察。
- 不同意图落成同一 artifact、显式复测与重复探索的区分。
- 数值失败与测量无效不混淆；归纳经验保留具体条件。
- 组合回退、历史版本不匹配、没有最终赢家时输出 original。

代码落地后的仓库回归命令为 `python3 -m pytest -q unittests`。
实现已覆盖这些 CPU 协议测试；阶段结果见实施总表。此处不启动 GPU 实验。

### 11.2 小规模真机验证与消融

在用户安排的真机验证范围内，选少量已有 client/seed 固定输入和原始 baseline，
比较现有流程、加入 P0 的流程，以及逐项启用 P1/P2 的流程。所有测量继续通过 client；不擅自扩大成批量 GPU campaign。

对比使用相同的总 eval 调用额度，baseline、确认、final、历史方案复测均计入；另报墙钟时间与 profiling 成本。
记录 Agent/配置/随机种子，并在预算允许时重复独立运行，不只比较单次最幸运的结果。
评估历史知识效果时区分冷启动、同 seed 重复调优和留出 kernel；留出样本不反写到下一次对照所读取的知识快照。

| 指标 | 说明 |
|---|---|
| 最终确认收益 | 相对 original 的 client 指标提升；未确认时最终保留 original |
| 首次收益成本 | 找到第一个 confirmed gain 所需的 eval 次数及墙钟时间 |
| 搜索有效性 | 非重复且实际发生变换的候选数，占候选提案/评测的比例 |
| 复现率 | 筛选领先候选通过独立 final 的比例 |
| 成本构成 | baseline、screen、confirm、final、profile 和重试分别消耗多少 |
| 复用效果 | 历史方案确认命中率、节省次数、知识引导与独立探索各自的收益 |

能否提高最终确认收益、缩短首次收益时间，需要这些实验回答；本文不预先承诺加速幅度。

## 12. 参考来源与已有设计的关系

GEAK 参考链接固定在本次审阅版本：

- [kernel workflow README](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/README.md)：总体流程、预算、独立验证、跨轮记忆、Integrator。
- [kernel_lane.js](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/kernel_lane.js)：程序控制循环、incumbent、验证筛选、warm start、知识引导额度。
- [verify_engineer.md](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/roles/verify_engineer.md)：干净环境复测、固定参考、无效测量分类。
- [tech_lead.md](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/roles/tech_lead.md)：跨轮假设账本、方向规划与状态恢复。
- [learned/README.md](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/knowledge/learned/README.md)：经验作为先验、条件化负面经验、经验与原始证据分层。
- [gpu_lock.sh](https://github.com/AMD-AGI/GEAK/blob/ba509ef31d416350269266b626ec455e9d9475d1/kernel_workflow/scripts/gpu_lock.sh)：GPU 使用串行化、构建隔离与实际源码身份检查的动机。

本文是在 [`knowledge_agent_design.md`](./knowledge_agent_design.md)、
[`anchorless_region_scheduling.md`](./anchorless_region_scheduling.md) 和
[`if/ai_interface.md`](./if/ai_interface.md) 上补充实验控制与证据管理。
既有设计中的模型导航、结构化变换和 client 边界继续复用；
知识晋升以当前 [`knowledge/README.md`](../knowledge/README.md) 和根 [`AGENTS.md`](../AGENTS.md) 为准。

本文新增的预算字段、配对确认方法、状态布局和候选身份设计，是针对 testft 的适配建议，
不表示 GEAK 已逐项实现同样的协议，也不把其仓库中的效果数字当作 testft 的预期收益。
