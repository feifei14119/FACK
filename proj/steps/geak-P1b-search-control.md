# P1-b：多方向建议、独立 profile 与搜索预算

日期：2026-10-13。调度器、ISA 合法性和正确性容差保持原有实现。

`init --search-policy FILE` 将搜索策略冻结到 manifest。可省略的 JSON 字段：

| 字段 | 默认 | 含义 |
|---|---|---|
| direction_eval_call_limit | null | 每个方向的候选筛选 client 调用上限；original/normalized 单列 |
| profile_call_limit | 0 | 按需 profile 调用上限；0 禁用，null 显式不限，但总预算仍限制 |
| stagnation_limit | null | 上次 confirmed_gain 后首次有效筛选的不同非 original 字节数上限 |
| reuse_proposal_limit | null | 知识/历史提案额度，P2-b 接通来源继承 |
| reuse_eval_call_limit | null | 知识/历史非 final 调用额度，P2-b 接通来源继承 |
| independent_eval_reserve | 0 | 为本次 observation 独立候选保留的非 final 调用额度 |

没有代替用户预设统计阈值，也没有自动修改这些额度。null 表示无该项上限，总 eval/proposal/墙钟预算仍在。
方向是具体候选登记时的属性；同字节的重复请求不能通过换方向来重置其筛选额度。

`python3 tools/tune_run.py suggest RUN --region loop --n 6` 创建新 observation，返回与该版本绑定的
少量 `{direction,spec,hypothesis}`。原有 `prepare --observation ... --base-sha256 ...` 接收建议 spec，
不直接上机。模型建议不替代实际诊断、引擎校验或 client 检查。

有锚点区域从实际 anchor 位置计算间隙，交错尝试 memory/alu 的 early/late 小动作；无锚点区域复用
`suggest_orders`，提取两条指令的局部顺序意图。只返回完整接受且构建通过、产物不同的候选。
为避免 CPU 无界搜索，每类扫描和总试排次数均有上限；空列表不证明没有优化空间。
控制器按方向已消耗调用排序，让未试方向先获得机会。确认后的新父版本可重新观察并细化；
模型建议之外仍支持手工 observation 提案。不存在自动将一次失败推广成整方向禁用的规则。

`profile RUN CANDIDATE` 需要该候选和 original 已通过筛选，使用同一 client，明确传递
`with_counters=True`，调用前同时占用 eval/profile 额度。每次独立计费，不隐式重试，保护 final reserve。
profile 的原始结果和 counters 保存在 attempt；其计时不进入 screening 缓存、确认或 final 样本。
无 counters 时记录 unavailable，普通搜索仍可继续，不能把缺失解释成某类 stall 已被消除。
profile 随父版本 revision 绑定；推进/切换父版本后旧 profile 仍保留，但标记需要重新观察。

`status.search` 输出方向消耗、停滞计数、当前 profile ID 和刷新需求。
停滞只计不同汇编首次成功筛选，失败/重复调用不增加；达到上限后拒绝新的 prepare/suggest/eval/profile，
已有筛选证据仍可 confirm，final 仍可执行。confirmed_gain 清零此后计数，切换探索父版本不清零。
中断的 profile 与其它 attempt 一样，resume 不退还调用额度。

SDK 使用说明见 [P1-b SDK 接入](./geak-P1b-sdk-search.md)。CPU 聚焦回归：direction/search_control/paired_validation/tuning_run 共 **137 passed**（28.56 秒）。
涵盖停滞重置、profile 双预算/中断不退款、方向标签绕过拒绝、normalized 字节重复和旧记录读取。
真机待验收：相同总调用预算下的候选多样性、首次确认收益成本、profile成本和停滞阈值效果。

交叉审查修复：suggest 先取有界候选池、按方向可用额度过滤/排序后再截取 n，避免 n=1 反复返回耗尽方向；
到达墙钟期限时不再生成新建议。新增 CLI 全链路验证确实将 profile 的 with_counters=True 传到 client。
更新测试：search_control **17 passed**，SDK Node **19 passed**。
