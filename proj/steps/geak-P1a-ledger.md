# P1-a：版本绑定的假设账本与实际诊断

日期：2026-10-13。软件实现不改变 ISA 规则、修补流水线或 client 正确性容差。

`prepare` 可选 `--hypothesis-file FILE`，JSON 字段为 `hypothesis`、`expected_observable`、
`source`（observation/profile/knowledge/history/replay）、`direction`（稳定的小写标识）及
`evidence_refs`（`[{"kind":"observation","id":"..."}]`）。不提供时仍支持原入口，记录 unspecified。
所有引用必须属于本 run，未知字段、虚构引用和越界文本拒绝，拒绝仍占提案预算。

提案拥有独立 ID，并记录由父字节、spec、区域、冻结构建策略与 client 契约共同确定的 `intent_id`。
重复请求可以共享 intent_id，但保留各自 prepared/duplicate/no_change/rejected 记录。
`python3 tools/tune_run.py ledger RUN` 从权威状态关联提案、筛选批次、配对比较与 final。
`annotate RUN --file FILE` 接收 `{"text":"解释","evidence_refs":[...]}`，仅追加非权威解释；
不能修改静态结果、样本或晋升状态。账本不会因一次失败就断言整个 layout/order 或某方向无效。

`agent/diagnostics.py` 重新运行现有 Verifier，分别记录原始、父版本、候选的完整告警与位置。
告警身份去除位置噪声、保留指令操作数及 hazard 数量；歧义或截断摘要保守处理。
所有告警豁免固定来自 original，不能从父版本扩张。normalized 和新候选都必须同时通过原构建器
和 `ok_vs_original` 检查。诊断不是等价性证明，也不代替 client 数值验证。

实际差分记录字节摘要、唯一可识别的 payload 移动、增加/删除、重复指令歧义、wait/nop/hazard 修补差分。
这些字段描述 materialized 汇编，不能把声明意图直接当作已发生的动作。
静态拒绝仍保留诊断，且不注册可评测候选。

`agent/knowledge.py` 的 layout/order 签名细化为具体 spec 摘要。含裸 IID 的旧实验不再归纳成全局
prefer/avoid skill；可复用的具体失败保留在版本绑定的 run 账本中。没有自动写入或晋升 `knowledge/`。

CPU 聚焦回归：`test_run_ledger.py`、`test_tuning_run.py`、`test_run_diagnostics.py`、
`test_knowledge.py` 共 **65 passed**。覆盖实际移动/修补、固定 original 门槛、歧义告警、重复提案、
解释与计算结论隔离、虚构引用拒绝及细粒度签名。目标 GPU 正确性与性能尚待验证。

报告 JSON/Markdown 和 SDK 提示已接入账本及假设文件。联合回归 **77 passed**（9.66 秒），Node **15 passed**。
