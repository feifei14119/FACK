# P2-b：历史候选作为重新验证的 warm start

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

对应 [`geak_lessons_for_instruction_tuning.md`](../geak_lessons_for_instruction_tuning.md) 的 G6。
本阶段增加 [`agent/history.py`](../../agent/history.py) 和
[`agent/history_controller.py`](../../agent/history_controller.py)，依赖 [P2-a 重放模块](./geak-P2a-replay.md)。
历史读取器返回经过校验的 recipe；控制器使用本次 CPU gate 和提案预算重新注册每一步，不调用 client。

## 接口与身份

```python
from agent.history import load_history

recipe = load_history(history_run_directory, current_manifest)
# recipe["chain"] 必须在本次 original 上重新构建并走本次评测。
```

控制器入口为 `HistoryControllerMixin.history(directory, candidate_id=None)` 和
`warm_start(directory, candidate_id=None)`。`history` 对当前 run 持锁，先检查当前代码/运行环境、
run 状态、期限和 original 归档，再调用读取器；不能只拿旧 `manifest` 绕过本次环境校验。
`history` 为只读检查，不计提案。`warm_start` 在同一当前 run 锁内执行读取、全链重建和逐步注册。

读取完整 `manifest.json` / `state.json`，对历史 run 持共享非阻塞锁，不读取简化 summary 冒充证据。
必须与当前 run 精确匹配：支持的 schema、original SHA、engine identity、runtime identity、
client evaluation contract、build policy、default region。缺失字段拒绝，不是通配符。
预算和比较采样策略不必相同：旧策略用于校验历史证据，本次策略决定本次确认。

检查冻结 manifest 摘要、所有候选归档的路径边界/文件长度/SHA，拒绝未恢复的 in-flight 工作。
候选链中的每一步要求已有版本绑定 observation、成功 proposal、完整 spec、静态通过及可重新构建的 SHA。
只有 controller 规范化根步骤能使用 `ladder`，不能导入任意 `.s` 或无操作链的 artifact。
返回历史 manifest/state 摘要，便于本次记录准确追溯所读取的快照；摘要是完整性信息，不是历史文件的签名认证。

## 历史证据与当前评测的边界

优先取已完成 final 的推荐候选；尚未 final 时可取已确认 incumbent，或显式指定已有确认的候选。
final 回退 original 时不静默复用之前的筛选赢家。筛选最高但未经确认的候选不作为此入口的历史最佳。

检查 original、candidate、reference 的最新成功筛选，检查每个 A/B pair 的次序、样本个数、
batch/attempt/sample 关联、源 SHA、编译/正确性/有效分数和摘要数值。使用旧冻结 comparison policy
重新计算 `assess_pairs`，不单凭 `confirmed_gain` 字段接受证据。reference 若非 original，
继续验证它的构建链和更早的确认，直到 original；不能靠无来源参考支撑历史赢家。

返回候选 ID/SHA、重放链和历史 comparison 引用；显式标记 `requires_evaluation=True`、
`measurements_imported=False`，不返回可注入新 run 的测量数组。历史命中只是先试谁，
本次重新构建后仍需走当前 client screening、confirm 和 final，不能恢复历史 incumbent 状态。

`candidate_chain(state, candidate_id, build_policy)` 还可供持有当前 run 锁的控制器抽取组合来源链。
此辅助函数不替代归档校验，输出仍必须交给 `verify_chain` 验证。

## 当前 run 中的注册、预算和恢复

`warm_start` 先通过 `_charge_history_request` 保存并收费一个历史请求，再读取历史。
每个进入准备的重建步骤另计一次提案：完整 N 步导入的成本为 **1 请求 + N 步骤**，同时占用
全局 proposal 和 `reuse_proposal_limit`。历史路径不存在、身份不兼容或历史证据损坏也会消耗
请求额度；请求额度用完后不能重复扫描历史绕过 CPU 导航预算。只读 `history` 不注册候选。

读取器与控制器都重建完整 chain，随后从当前 `original` 逐步注册。普通步骤使用绑定当前
`parent_revision` 和该步骤 parent SHA 的 detached observation，再调用 `_prepare(detached=True)`；
仍检查冻结 policy、region、合法性和相对固定 original 的静态诊断。detached 允许观测链中的
中间候选，不改当前 exploration parent。根步骤若为 `ladder`，校验当前 `normalized` 的 SHA
和 `static_ok` 后，通过 `_charge_import_normalized` 把它计为一个 reuse 步骤。

`state.imports` 保存请求、状态、完整 recipe、每步 proposal/candidate/parent/SHA，以及
`source_evidence_ref`（历史 run、manifest/state 摘要、候选和 comparison 引用）。每个已注册
proposal 还保存结构化 `provenance`，含 import ID、步骤序号和相同证据引用。旧测量数值和
历史 incumbent 状态不写入当前 run；已有当前测量、incumbent、exploration parent、revision
保持不变。重复导入同字节候选仍收费，reuse 来源不能通过重命名或重复提案消除。

完成后 action 为 `prepared`，请求 proposal 为 `import_prepared`。验证失败、步骤预算耗尽或
中断时，保留已注册候选和已用预算，将 action 及请求标为 `rejected` / `interrupted`，不晋升
任何候选。`resume` 标记进程终止时遗留的 running import 和 `import_requested` 请求为中断，
不会自动重新导入或评测。未恢复的导入会阻断外部 observe/eval/warm 请求和作为历史来源读取；
只有同一锁内正在执行的 import ID 可通过内部步骤的 pending 检查，完成或异常后清除此豁免。
导入候选须先有本次 original baseline，再经本次 screen、confirm、
final 才能成为最终推荐；这些 client 调用遵循冻结 reuse 上限、独立探索预留和 final 预留。

模块不修改 `knowledge/`，不把历史反例升级为新的 ISA 硬约束。CLI 路由已连接：`history RUN HISTORY_DIR [--candidate ID]` 与
`warm-start RUN HISTORY_DIR [--candidate ID]`。两个命令均不构造 client evaluator。

SDK 通过 `--history-run DIR` 和可选 `--history-candidate ID` 显式给模型提供来源，默认不扫描
或导入历史。这两个参数不进入 init 的评测契约，不改变统计策略，也不增加总预算。
提示词要求当前 original 筛选通过后，最多检查一次、导入一次同一来源；新候选仍须当前
screen/confirm/final，并保护 reuse 上限、独立探索额度和 final 预留。该尝试次数是模型执行
约定，硬预算和恢复门槛由控制器实施。详见 [SDK README](../../tools/sdk/README.md)。

## CPU 验证

```bash
python3 -m pytest -q unittests/test_run_history.py unittests/test_history_controller.py
```

结果：39 passed（包含两处进程硬退出回归）。

SDK：`node --test tools/sdk/run_workflow.test.mjs`，23 passed；使用 fake SDK/子进程验证参数
不改变 init、提示词的显式来源与不重试规则，以及历史目录不能经 transcript 别名被覆盖。

使用真实重排 fixture 与 fake client 建立 run，覆盖成功 warm start、final 原始参考、
身份/摘要/归档路径不匹配、缺失 observation/proposal/参考样本、伪造分析摘要、
无 recipe artifact、失败 final、父版本缺失，以及参考 incumbent 的递归确认来源。
控制器测试覆盖当前环境漂移、完整两步链、结构化 provenance、保留已有当前确认和样本、
当前 baseline/screen/confirm 门槛、请求与步骤预算、无效路径反复请求封顶、半途失败和中断、
显式 resume、进程在请求收费后或第一步后硬退出的恢复门槛、规范化根步骤静态门槛，以及重复导入费用。
未进行 GPU 验证；实际环境一致性和历史知识的收益需要用户安排的 client 真机实验。

## 复用上限与独立探索

`--search-policy` 中的 reuse_proposal_limit 限制请求及每一步；reuse_eval_call_limit 限制来源候选
在非 final 阶段的调用（确认中按双方候选各自来源计数），方向筛选上限继续并行生效。
历史/知识来源对候选和后代保持粘性，重复请求改写 source/direction 不能消除已有身份。
普通知识提案使用 hypothesis.source=knowledge；文本声明不能证明模型是否受其他上下文影响。

independent_eval_reserve 为本 run 的独立 observation 候选预留非 final 调用。
profile 与复用候选不得占用尚未兑现的预留；确认涉及复用候选时，开始前检查完整配对成本。
基线不算独立新候选。final 使用独立预留，不因复用导航上限耗尽而被阻止。
这些额度默认不硬编码 GEAK 的比例，需显式配置并通过同预算真机消融评价。

## 集成收尾

主控制器和 CLI/SDK 已贯通；CLI + history controller + reuse budgets 联合 **22 passed**。
完整 CPU 回归 **704 passed，3 skipped，13 subtests passed，3 failed**（135.58 秒）；
3 项为原项目已记录、且本副本已排除的专属模块失败，详情见 [实施总表](../geak_rollout_status.md)。
最后增加跨 run 报告输出保护，解析默认及显式输出的符号链接，禁止把新报告写进历史 run；
报告聚焦 **15 passed**、SDK **23 passed**。没有真实 client/GPU/线上模型调用。
