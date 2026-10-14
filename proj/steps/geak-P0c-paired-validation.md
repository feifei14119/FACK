# GEAK 借鉴实施记录：P0 后续，配对确认与 final 协议

> FACK 复制说明：本文保留原始 testft 的通用实施记录，已省略不包含在本副本中的架构专属内容。
> 提交号、测试数量与耗时均为原项目历史记录；本次复制只做静态检查，没有执行 FACK 测试或 GPU 实验。

日期：2026-10-13。承接 `9661a0d` 的 [持久化 run 控制器](./geak-P0b-persistent-run.md)，
实现设计中 P0-b 尚缺的确认、incumbent 推进和 final 流程。为区分批次，本记录命名为 P0-c。

**本批完成程序协议和 CPU 验证，没有验证目标 GPU 上的正确性、提速或噪声假设。**
目标仍是现有单 kernel 的指令级重排；ISA、修补 pass、client 正确性容差和默认 SDK 流程没有调整。
新能力通过独立 `tune_run.py` 入口显式启用，不向既有 run 自动添加确认策略。

## 1. 本批落地

| 位置 | 变化 |
|---|---|
| [`harness/comparison.py`](../../harness/comparison.py) | 不依赖第三方统计库的固定样本配对裁决、完整策略校验、交错顺序 |
| [`agent/run.py`](../../agent/run.py) | 共用逐次持久化测量路径；confirm、final、incumbent 晋升、确认次数上限和恢复语义 |
| [`tools/tune_run.py`](../../tools/tune_run.py) | `init --comparison-policy FILE`、`confirm RUN CANDIDATE`、`final RUN` |
| [`unittests/test_paired_validation.py`](../../unittests/test_paired_validation.py) | 统计规则、跨轮推进、预算、失败、中断、旧 schema 与 CLI 的 CPU 测试 |

## 2. 初始化时冻结确认策略

不提供默认确认阈值。未指定 `--comparison-policy` 时，run 仍只能筛选，
`confirm` / `final` 返回 `comparison_not_configured`。策略 JSON 必须包含以下六项，不接受额外字段：

```json
{
  "method": "paired_sign_v1",
  "confirm_pairs": 8,
  "final_pairs": 8,
  "min_gain": 0.01,
  "alpha": 0.05,
  "max_confirmations": 3
}
```

这些数值是展示格式与计算方法的例子，**没有针对 gfx942 校准，不是推荐参数**。
策略文件的内容存入 manifest；修改原 JSON 文件不会改变已有 run 的规则。

| 字段 | 含义 |
|---|---|
| `method` | `paired_sign_v1`（固定 n 对）；分段停止见 §2.1 |
| `confirm_pairs` / `final_pairs` | 完整配对数，每对两次 client 调用；要求偶数，范围 2–1024，保证 A/B 与 B/A 数量相同 |
| `min_gain` | 相对分数门槛，例如 0.01 表示候选/参考大于 1.01；有限且非负 |
| `alpha` | 单侧名义错误率，0 < alpha < 0.5；依赖 §3 的统计假设 |
| `max_confirmations` | 本 run 最多启动的确认比较数，1–1024，包含失败和中断 |

确认阶段每次分配 `alpha / max_confirmations`，以 Bonferroni 分配控制本 run 中多次确认的
错误晋升风险；失败和中断不退还确认名额。final 只检验一个预先选定的候选，使用新的样本和 `alpha`。
这不提供跨 run 反复实验的总体错误率保证。

初始化要求 `final_eval_reserve >= 2 * final_pairs`，并满足既有总预算上限。
样本数若小到“所有配对均超过门槛也无法达到分配的 alpha”，直接拒绝配置。
上例的 confirm 使用 alpha=0.05/3，8 对中的最小比例必须超过 1.01；
final 使用 alpha=0.05，8 对中的第二小比例必须超过 1.01。

### 2.1 分段停止：`paired_sequential_v1`

固定 n 对时，n 必须按“最难判定的小收益”选，大收益也要付同样的代价；按大收益选，1–2% 的收益又判不出。
分段策略预先声明若干检查点，在第一个能下结论的检查点停止：

```json
{
  "method": "paired_sequential_v1",
  "statistic": "signed_rank",
  "confirm_looks": [{"pairs": 16, "alpha_share": 0.1}, {"pairs": 32, "alpha_share": 0.1},
                    {"pairs": 64, "alpha_share": 0.2}, {"pairs": 128, "alpha_share": 0.6}],
  "final_looks":   [{"pairs": 16, "alpha_share": 0.1}, {"pairs": 32, "alpha_share": 0.1},
                    {"pairs": 64, "alpha_share": 0.2}, {"pairs": 128, "alpha_share": 0.6}],
  "min_gain": 0.005,
  "alpha": 0.05,
  "max_confirmations": 3,
  "futility_stop": true
}
```

| 字段 | 含义 |
|---|---|
| `statistic` | `sign`：与 §3 相同的符号检验界；`signed_rank`：Wilcoxon 符号秩的 Hodges–Lehmann 界（Walsh 平均数的次序统计量，精确零分布） |
| `*_looks` | 递增的偶数配对数（≤512），每个检查点分得阶段 alpha 的 `alpha_share`，份额之和为 1 |
| `futility_stop` | 为 true 时，若上界已低于 `log(1+min_gain)`，停止并裁决 `inconclusive`（`stop_reason=futility`） |

每个检查点用 `阶段 alpha × alpha_share` 计算上下界，裁决规则同 §3；裁决为 `confirmed_gain` 或 `regression`
即停止，否则继续到下一个检查点，最后一个检查点仍不能下结论时为 `inconclusive`（`max_pairs`）。
各检查点 alpha 之和等于阶段 alpha（Bonferroni），无论检查点之间如何相关，误判晋升率都不超过阶段 alpha；
无望停止只会减少晋升，不增加误判。检查点、份额与门槛全部在初始化时冻结，不能根据中途结果追加配对。

`signed_rank` 比 `sign` 多一个假设：配对 log ratio 关于中位数对称。候选与参考噪声同分布时，
差值天然对称；A/B、B/A 交替带来的位置效应在偶数对下是两个对称平移的等权混合，仍然对称。
候选噪声明显大于参考时该假设不再严格成立，scope 字段会标出 `symmetric_pair_difference_assumed`。

预算按最后一个检查点预留：初始化要求 `final_eval_reserve >= 2 × final_looks 最后的 pairs`，
每次 confirm 前检查 `2 × confirm_looks 最后的 pairs`；提前停止时只计已测的调用，剩余额度留给后续搜索。
比较记录保存 `planned_pairs`；分析结果保存每个检查点的界、`stop_reason` 和 Hodges–Lehmann 估计 `estimate_ratio`。
历史校验会重算全部检查点，配对数必须恰好停在第一个能停的检查点。

实际确认率与停止配对数取决于 kernel、client 和机器，应按验收手册的 pilot 评估。

## 3. 采用什么统计规则，能说明什么

对每个完整配对计算 `z = log(candidate_score) - log(reference_score)`。
`score` 来自相同 client 契约中的正向指标 `EvalResult.tflops`，不是框架自行推导的 FLOPS。
只有该分数与吞吐或执行时间倒数对应时，其比例才可解释为执行时间加速比。

设完整配对数为 n，阶段分配的单侧概率为 a，取最大的 k，使得：

```text
P(Binomial(n, 0.5) <= k - 1) <= a
```

排序后的第 k 个 log ratio 为中位数的单侧下界，倒数第 k 个为单侧上界。
下界严格超过 `log(1 + min_gain)` 时裁决 `confirmed_gain`；上界低于
`-log(1 + min_gain)` 时裁决 `regression`；其余为 `inconclusive`。
比较额外留 `1e-12` 的 log 数值容差，避免浮点误差将恰好等于门槛的值算成通过。
上下界各自使用单侧 a，不能把两者组成的区间宣称为覆盖率 `1-a` 的双侧区间。

规则是对**配对分数比例总体中位数**的非参数界，不是均值吞吐或平均耗时的置信区间。
名义覆盖依赖配对之间独立且来自共同分布等条件；交错顺序有助于平衡先后影响，但不能证明
GPU 测量满足这些条件。相关噪声、热状态、频率漂移、顺序效应和选择后的分布变化仍需真机评估。

结果保存每个 log ratio、log 中位数及还原后的比例、单侧上下界、k、实际 alpha、门槛和方法版本。
极端有限输入可能使还原后的 ratio 超出浮点范围；这时 ratio 字段为 null，有限 log 字段仍保留，
不输出非法 JSON 数值。scope 字段明确标明依据为 client 返回值、统计假设未经目标硬件验证。

## 4. confirm 的状态与测量

1. 首次确认以 original 为参考；之后以当前 incumbent 为参考。original、参考与候选的最新
   screening batch 均须为 `measured`，归档摘要须正确，候选与参考不能是相同字节。
   original 字节始终作为原始参考和回退，不作为挑战者晋升，防止 final 退化为自比较。
2. 在完整比较开始前检查 2×配对数的预算，同时保护 final reserve；把候选、参考和全部配对顺序写入状态。
3. 第 0 对按 reference → candidate，第 1 对按 candidate → reference，依此交替。
   每侧使用新的 batch 和工作 `.s`，每侧恰好调用一次 client；不借用任何 screening 或旧确认样本。
4. 每次调用沿用明确编译通过、正确性通过、有限正分数与源摘要检查。首个失败停止整次比较，
   保留失败侧和全部已完成记录。无效侧不能丢弃后再凑满 n 对；只有 §2.1 预先声明的检查点可以停止，
   不根据“已经很快”在其他位置提前结束。
5. 只有全部样本有效且裁决为 `confirmed_gain`，才将候选、证据 ID 和新的探索父版本一起原子保存。
   `parent_revision` 递增，下一轮需重新 observe；失败或 inconclusive 保留原 incumbent。

同一候选 SHA / 参考 SHA 的确认最多启动一次。重复 `confirm` 返回原比较并标 `cached=true`，
包括失败和恢复后的中断比较；没有确认用的 `--repeat`。参考更换后可形成新的比较，但仍计入总确认名额。
已是 incumbent 的候选返回其晋升证据，不创建自比较。

缓存返回的是历史证据，不意味着在新的筛选失败后又验证了一遍。后续新比较和 final 仍检查最新 screening。
`select-parent` 可以继续选择筛选通过的探索分支，但不能改变 incumbent。
confirmation batch 不会覆盖 `eval` 的 screening 缓存。

## 5. final 的选择、推荐和回退

`final RUN` 固定选择当前 incumbent，与 **original** 使用全新样本比较。
不接受临时指定另一候选，不将探索父版本或筛选最高分自动作为最终选择。
final 可以使用预留预算；screen 和 confirm 始终不能消费这部分额度。

| 情况 | `final_result` |
|---|---|
| 完整 final 比较通过 | `status=final_recommended`，`recommendation_id=候选` |
| 没有 incumbent、最新筛选失败、截止时间/预算不足 | `status=original_retained`，记录原因，不调用 client |
| final 测量失败、有效但未达到门槛、或中断 | `status=original_retained`，保留比较/失败证据 |

回退时 `recommendation_id=null`、`fallback_id=original`、`selected_id=original`。
这表示保留输入，不声称 original 刚通过了 final 正确性或性能复测；`original_screen_status` 仅指历史最新筛选。
归档损坏、环境身份改变等错误仍拒绝继续，不绕过校验给出推荐。

所有正常 final 结果都将 run 置为 `finished`；之后不能 prepare、eval、confirm、observe 或换父版本。
重复 `final` 只返回已有结果。`status` / `source` 和 `resume` 仍可访问保存的状态。
已确认 incumbent 和证据链作为历史保留；最终是否推荐以 `final_result` 为准。

输出包含选中归档的路径与 SHA-256，以及 `comparison_id`。`state.json` 中保留完整结果，
不额外创建第二套权威日志。旧 `tune_summarize.py` 仍汇总旧筛选日志，不负责读取本 run 的 final 结果。
本批 final 只给出相对 original 的配对结论；相对 normalized 的独立配对报告仍未接入。

## 6. 持久化、恢复与客户端边界

三个测量阶段共用 `_measure`，每次调用前保存预算和 attempt，返回后立即保存原始结果。
新增字段把 attempt/batch 关联到 `stage`、`comparison_id`、`pair_index` 和 `role`。
引擎指纹和已记录运行环境在每次调用前后检查；若调用中改变，先保留原始返回值，再把该次测量判无效。

中断恢复保持保守语义：

- confirm 中断：不退还调用预算或确认名额，不晋升，不重放部分比较。
- final 中断：标记原比较 interrupted，保留原始输入并关闭 run，不重新开始 final。
- 即使所有样本已返回但聚合裁决尚未提交，也不从残留样本自动补出确认结论。

schema 升为 2。schema 1 的 manifest/state 可通过 `status` 查看，不能继续变更；需创建新 run。
没有自动迁移旧样本或为旧运行追加阈值。

CLI 的 confirm/final 在每次配对侧调用时创建新的 evaluator，并使用全新工作 `.s` 路径，
继续持有本 checkout 的共享评测锁。**新对象与新路径不能证明 client 实际刷新/装载了新的 `.co`**。
外部构建缓存、测试资源、驱动/GPU 身份和 client 私有环境仍遵循上一批所记录的未知边界。
这里的 `final_recommended` 是配置协议对 client 返回值的结论，没有额外的装载证明。
真正使用新接口的 client 仍须遵守每次 `evaluate` 构建并装载所给 `.s` 的原有契约。

## 7. 用法

在仓库根运行；本机没有 Python 3.8，使用 `python3`。先将自己选择的策略保存为 JSON。
下例的路径/参数须替换为实际任务；策略数值不能从示例推断为已校准：

```bash
python3 tools/tune_run.py init path/to/seed.s \
  --client poc_kl/fp8_blockscale_gemm --run-id paired-demo \
  --eval-calls 80 --perf-repeats 3 --final-reserve 16 \
  --comparison-policy path/to/policy.json \
  -- m=256 n=256 k=256
RUN=client/poc_kl/tune_out/runs/paired-demo
python3 tools/tune_run.py observe "$RUN"
```

本机可执行 init / observe / prepare 等 CPU 步骤。prepare 用法见 [上一批文档](./geak-P0b-persistent-run.md)。
有目标 GPU 时，在目标机器上新建 run，再通过该 client 建立 original 和候选 screening：

```bash
python3 tools/tune_run.py eval "$RUN" original
python3 tools/tune_run.py eval "$RUN" CANDIDATE_ID
python3 tools/tune_run.py confirm "$RUN" CANDIDATE_ID
# 确认成功后重新 observe，可在新父版本上继续生成并确认候选
python3 tools/tune_run.py observe "$RUN"
# 搜索结束时：final 固定选择当前 incumbent，结束该 run
python3 tools/tune_run.py final "$RUN"
python3 tools/tune_run.py status "$RUN"
```

命令成功退出不等于候选通过；读取 `status`、`verdict`、`analysis` 或 `final_result`。
参数错误、预算拒绝等仍是结构化 error 和退出码 2。执行测量的入口只有 eval / confirm / final。

## 8. CPU 验证记录

新增测试覆盖名义统计界、全部独立符号组合枚举、异常高分、门槛相等、先后偏差、极值和不完整样本；
以及配对顺序、增量晋升、final 原始参考、整批预算与保护额度、失败侧、子进程退出和中断恢复。
另检查完整样本尚未提交时的中断、运行环境改变、final 输入改写、schema 1 只读和 CLI 新建 evaluator。

针对性回归：
`python3 -m pytest -q unittests/test_paired_validation.py unittests/test_tuning_run.py unittests/test_tuning_evidence.py`
结果 **103 passed、13 subtests passed**，耗时 13.25 秒。

完整回归 `python3 -m pytest -q unittests`：
**524 passed、3 skipped、3 failed、13 subtests passed**，耗时 54.57 秒。
相比 `9661a0d` 新增 48 项通过测试。最终检查补测了 original 不能重新晋升并导致 final 自比较的边界。
原项目当时的 3 项失败属于本副本已排除的专属模块。
`git diff --check`、CLI `--help`、四个本批 Python
文件的 Python 3.8 AST 语法检查及设计/实施文档本地链接检查均通过。
实际运行解释器为 Python 3.12.3，未声称 Python 3.8 运行时验证或目标 GPU 验证。

## 9. 尚待推进

1. client 构建/装载证据与外部资源身份：使每侧都能追到实际执行的 `.co` 和测试契约。
2. 目标机小规模正确性/噪声试验：评估顺序、相关性、漂移和重复测量，再选择确认参数。
3. SDK 接入持久化 run 与最终报告，避免只在手动 CLI 中可用；补 normalized 对照和用户可读报告。
4. 假设账本与多方向探索。当前不调整 ISA、不自动晋升知识，也不引入 GEAK 运行依赖。
