# 限时串行调优 campaign

`client/aiter/campaign_runner.py` 在已准备的隔离 checkout / 容器中协调 `tools/tune_run.py`。
它不初始化远端环境、不选择 GPU，也不自动创建状态或恢复损坏的任务。环境准备和 seed 验证要求见
[validation.md](validation.md)。远端 campaign 的控制文件必须记录固定上游提交、GPU PCI/UUID、输出目录和绝对截止时间。

所有 GPU 评测都通过 `--client aiter/hsa/gfx942 -- ...`。输出目录包含：

- `inventory.json`：全部发现的 `.co` 及分类；`progress.json`：状态、简短原因、当前任务和指标。
- `plan.json`：有实际 adapter 的任务、manifest、shape、seed 和阶段截止时间；`adapter-audit.json`：未适配原因。
- `kernels/<run-id>/`：命令、stdout/stderr、MFMA 已有导出查询、候选机制、原始筛选、最终决定。
- `runs/<run-id>/`：`tune_run` 的完整状态及冻结产物；`evaluations/`：每次实际评测的 overlay、日志及证据。
- `remaining.json/csv`：尚未完成的目标内核；`out_of_scope.csv` 单独保存非本次目标的 `.co`。
- `export/manifest.json`：仅实际采用的候选，逐项列出 `.s`、`.co`、比较摘要的 SHA256 与大小。

启动前，`client/aiter/tune_out/runs` 必须在这个隔离 checkout 中解析到 campaign 的 `runs/`。
导出器拒绝从 campaign 以外的位置读取选中产物。示例使用调用者事先设置的输出、计划和截止时间：

```bash
python3 client/aiter/campaign_runner.py --output "$AIT_CAMPAIGN_OUT" \
  --plan "$AIT_CAMPAIGN_OUT/plan.json" --deadline "$AIT_CAMPAIGN_DEADLINE"
```

另启 `client/aiter/campaign_export.py --output ... --deadline ...`，它只做 CPU 文件归档。
导出器每 30 秒检查最终决定；单核 SHA、路径或证据错误写入清单的 `errors`，不发布该核的部分文件，
也不阻止其他已采用候选导出。没有确认加速时空 `files` 正确。

阶段按 GEMM → MoE → MLA 单向推进。每个内核先验证原始 seed 三次，然后评测有不同内容 SHA 的合法候选。
筛选只挑选待确认的候选；固定八对独立交替评测用于确认，另八对用于最终比较。
要求至少 1% 收益，并且 HIP graph 与声明的上游 op_test 计时都给出确认加速，才采用候选。
缺失计时方法、数值失败、方法不一致或没有足够证据时保留原始对象。

数值筛选通过的候选还要经过 `campaign_audit.py` 的全内核静态审计，保存首轮与稳态 verifier 结果、
LDS 模型覆盖、未知 opcode 及引擎源码指纹。只有覆盖完整且 verifier 通过的候选进入确认；
LDS 无法解析等情况列为 `coverage_pending`，不计完成，也不据此断言原版非法。
导出要求选中汇编、审计文件和当前引擎的 SHA 全部匹配。引擎修复后的历史复核不得覆盖冻结 run；
失效的候选计时作为历史保留，campaign 决定回退原版，并用新 run-id 重新评测。

BF16/INT8 GEMM 使用固定 SHA 的指定上游 benchmark wrapper，不宣称覆盖整份多后端测试。
INT8 catalog 的内核会无条件读取 FP32 bias；adapter 必须提供有效偏置并在独立参考中包含它，
同时保留上游测试的 A 行尾 128 字节 padding。MoE adapter 仅覆盖 gate/up 与激活的 stage1；
MLA adapter 仅覆盖唯一 catalog tuple 选出的非 persistent、split=1 低层 stage1 输出。
每个新家族都需要先通过实际 seed 验证，静态 catalog 匹配或回编成功不代表已通过 GPU 验证。
新的 MLA 计划仅自动生成 [MLA 专用验证](mla-stage1-validation.md) 表中已核查固定 workload
内存边界的契约，显式绑定 page1、各对象的 KV 尾部、输出类型和四份固定 schema CSV；
BF16 QH8/QH16 还保留独立 scratch-LSE 的使用范围限制，其他目标列为待适配。
输入生成、原版验证及单目标比较命令见 [MLA 专用验证](mla-stage1-validation.md)。
生成器保留计划中已有任务及其 manifest；旧分页/存储契约不会被原地迁移。
修复后的验证应在新输出目录中生成新契约，保留旧任务的完整记录。

修复运行中发现的 adapter 契约错误时，先保存完整计划并原子清空后续 `tasks`，等待当前任务结束，
确认没有评测进程后停止 runner。保留原 run/evaluation，修复后用新 run-id 重新验证 seed；不要在冻结的
评测期间替换 driver/manifest。已失败尝试可以保存在 `attempt_history`，不可把可修适配问题当作性能结论。

runner 有每命令和阶段时间限制，但独立宿主 watchdog 仍是硬截止保证。watchdog 只停止本 campaign 容器，
结束后应核验 Docker 实际状态，并保留精确未完成列表。普通调优只读取已有 selfstudy 导出，不启动自学或探针。
