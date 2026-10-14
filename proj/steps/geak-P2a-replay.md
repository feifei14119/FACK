# P2-a：受约束意图重放与组合

对应 [`geak_lessons_for_instruction_tuning.md`](../geak_lessons_for_instruction_tuning.md) 的 G5。
本阶段增加独立 CPU 模块 [`agent/replay.py`](../../agent/replay.py) 及控制器入口
[`agent/replay_controller.py`](../../agent/replay_controller.py)，不修改 ISA、client 或 GPU 评测规则。
`RunController.replay(source_candidate_id)` 和 `combine` 同义入口均已接入常规持久化 prepare 流程。

## 接口

运行入口：

```bash
python3 tools/tune_run.py replay <run目录> <source_candidate_id>
python3 tools/tune_run.py combine <run目录> <source_candidate_id>
```

source 必须具有成功、版本绑定的 layout/order 提案，且最近一次 screening 成功。
控制器将 source 的最后一步意图重放到当前 exploration parent；两侧祖先都从 original 重新构建。
本操作只生成待评测候选，不调用 client，不改变当前 exploration parent 或 incumbent。
新的候选仍需本次 `eval`、`confirm` 和最终验证。

底层纯函数：

```python
from agent.replay import verify_chain, replay_intent

# 每一步来自已归档候选，不接受任意 descendant .s。
chain = [{"spec": full_build_spec,
          "source_sha256": parent_sha256,
          "candidate_sha256": candidate_sha256}]
checked = verify_chain(original_source, chain, build_policy)
combined = replay_intent(original_source, source_chain, target_chain,
                         source_parent_spec, build_policy)
```

`build_policy` 必须完整声明当前控制器支持的 `opt_level=1`、`protect_prefetch` 和
`strict_verify`。每个 spec 显式绑定 region；允许 `layout` / `order`，只有链首允许
控制器的 `ladder level=1` 规范化。共同原始来源由逐步重新构建、逐步比对源/结果 SHA 保证，
不能只提供相同的 original 字符串标识而导入任意候选汇编。

`replay_intent` 在 source parent 校验原意图，映射到 target parent，再经 `propose`、
`build_candidate` 和固定 original 告警集合检查。返回实际 `spec`、`mapping`、候选原文和 SHA、
原始/候选/新增静态告警及实际 placement 报告。返回值标明 `requires_evaluation=True`；
没有新建运行记录、调用 client、使用历史分数或推进 incumbent。

## 映射与组合边界

- 同字节父版本沿用其绑定 IID；跨版本使用“最近标签原文 + 完整指令原文”的双向唯一匹配。
  opcode、operands、缩进和尾注均属于原文。不会按相同 opcode、重复出现序号或近似文本猜测。
- 独立 `remap_spec` 也校验架构及完整 `.amdgcn_target` 声明，不能以相同指令文本跨架构套用 IID。
- 选区 kind、header、outlined 状态、标签序列、有效指令原文多重集合必须相同。
  由现有引擎负责的 waits / nops / hazard 修补行允许重建，但引用这些行仍要求精确唯一身份。
  选择器改指不同区域、操作数变化或重复原文无法唯一定位时，拒绝并要求重新 observe/propose。
- layout 的 anchors 一并映射，顺序必须不变；slot 不能被误解成另一个 gap。
- 所有 target 链上已记录的 order 相对顺序、layout gap 和 filler 顺序在组合后必须仍成立。
  重叠且互相覆盖的意图返回 `intent_conflict`。不会拼接汇编 diff，也不会相加独立收益。
- 原始静态告警是整条链唯一的豁免基准；后续步骤不能把新增告警当成新父版本的既有豁免。
  比对采用现有 verifier 的完整诊断字符串，行号变化也可能导致保守拒绝。
- 这是保守可复用子集。合法但重复身份不明确、anchor 重排、修改原文字节或故意覆盖先前意图的
  组合需要新提案。当前实现不做通用补丁合并、模糊匹配或多组合枚举。

控制器持有 run 锁、校验当前身份并先登记 `replay_requested`，再进行映射和重建。
映射成功的实际 spec 走常规 `_observe` / `_prepare`，保留其 diagnostics、归档和去重结果。
请求及最终提案保存 source/target SHA、完整来源链、实际映射和诊断；失败保留原候选和父版本。

采用两阶段 CPU 计费：规划请求占用 **1 次 proposal**，成功进入 `_prepare` 后再按正常规则占用
**1 次 proposal**，因此完整成功重放共占 **2 次 proposal**，没有 client 评测支出。
source 或 target 任一有知识/历史来源时，两阶段均占 reuse proposal 额度，并将来源传递给候选；
不能借独立 target 把历史 source 重命名为独立探索。映射失败也保留已支出的全局/reuse 额度。

请求在整个规划和构建期间保持 `replay_requested`。只有本控制器当前操作的内存 token 允许内部
observe/prepare 继续；进程硬退出后，其他写操作必须先 `resume`，将请求记为 `replay_interrupted`。
正常拒绝记为 `replay_rejected`，不阻止继续搜索；KeyboardInterrupt 清理 token 并保留预算。

## CPU 验证

```bash
python3 -m pytest -q unittests/test_run_replay.py unittests/test_run_replay_integration.py
```

覆盖兄弟候选成功组合、冲突不覆盖、原文身份/区域/策略不匹配、重复指令歧义、按标签唯一匹配、
anchorless order、wait 重建、伪造 SHA、非法/跳过 placement、固定原始告警豁免及规范化边界。
集成回归还覆盖正常prepare与映射来源留存、冲突/未测/篡改来源的计费、reuse传播及额度、
映射完成后硬退出的pending/resume语义、KeyboardInterrupt清理，确认没有client调用或父版本推进。
未进行 GPU 测试；静态通过不替代 client 的正确性及性能验证。

本阶段同时提交共享的 `history.candidate_chain` / 历史证据校验基础、复用预算与内部逐步注册接口，
供下一阶段 warm-start 入口复用。它们不会导入旧样本或自动设置赢家。
补充兼容检查修复了 schema 1 的 ledger/report 只读导出；报告测试 **13 passed**。
CLI combine 与控制器集成首轮 **15 passed**；子代理联合回归结果在提交前核对。
最终 replay integration + diagnostics + replay + history 联合回归：**67 passed**（17.64 秒）；Node **19 passed**。
