# P1-b：SDK 搜索方向与可选 profiling 接入

日期：2026-10-13。承接 P1-a 账本接口；本记录只描述 SDK 入口与提示词。
控制器实现位于 agent/search_control.py / agent/run.py，SDK 不另建计费或裁决状态。
本批未修改 run 控制器、CLI、client、报告器或 ISA。

## 显式初始化

`node tools/sdk/tune.mjs ... --search-policy FILE -- <opaque client params>`
将 JSON 文件路径绝对化后交给 `tune_run.py init --search-policy FILE`，只在 init 传一次。
文件内容由 Python 控制器校验并冻结；后续 prompt 使用 init 返回的 manifest.search_policy，
不读取原文件来覆盖已有 run。

comparison policy 继续独立控制 confirm/final；search policy 不提供统计阈值或确认权限。
SDK 也不因 profile 额度自动增加总 eval 预算。每次 profile 和其他阶段共用初始化时的总上限。

## 模型操作约定

- 用 `suggest RUN --n N --region SEL` 获取小批方向建议；N 默认取 rounds 与 6 的较小值。
  该命令为 CPU 建议，返回新的 observation。prepare 必须使用这份 observation_id/base_sha256，
  不能把新建议套在之前的指令 ID 或父版本上。
- 在可用方向中先对未尝试的独立方向各做少量实验，再对产生已确认候选的方向局部细化。
  方向标签保持稳定；具体候选的确认不能推广为整个方向必然有效。
- 读取 `status.search` 的方向调用量、profile 调用量、停滞计数与停止状态。
  按完整 perf_repeats batch 估算方向剩余额；拒绝、失败和重复的裁决依控制器状态处理。
- `search_stopped` 时停止新搜索动作；合格的待确认候选可以确认一次，随后结束模型会话，
  由 SDK 的既有单次 final 收尾逻辑处理。
- 只有冻结的 profile_call_limit 为正整数或显式 null 时，prompt 才提供 profile 命令。
  0、缺字段或没有 search policy 均不提供此入口。
- profile 原始输入和目标候选均须已有有效筛选。每次消耗一个 eval 调用和一个 profile 调用，
  final reserve 与 independent_eval_reserve 不可被占用。
- profile 计时/分数不参与 screen、confirm、final 的性能裁决，只用 counters 检验调度假设。
  profile_needs_refresh/current_profile_id 依候选与 parent_revision 判断；换父版本后旧 profile 不沿用。
- SDK 每个 parent revision 最多请求一次可选 profile；失败、缺 counters 或 unavailable 都不自动重试。
  显式 null 只取消 profile 专项次数上限，不取消总预算或这条模型执行约定。

这些提示词约定不能隔离任意 shell；硬预算、身份检查与实际裁决由控制器执行。
历史导入与 replay 尚未接入本阶段 SDK。

## CPU 验证

```bash
node --test tools/sdk/run_workflow.test.mjs
node --check tools/sdk/run_workflow.mjs
```

当前 Node **19 passed**，其中本批新增覆盖：

- search policy 路径只传给 init，opaque client token 不受同名参数影响，既有硬预算不改变。
- suggest 命令包含数量与区域，提示词绑定返回 observation，并呈现方向额度和停滞状态。
- 没有授权的 profile 命令不进入 prompt；正数/null 允许时保留独立计费、无性能裁决及不重试约束。
- 实际 driver 配临时假 SDK/假 Python：用户策略到达 init，prompt 来自其返回 manifest，驱动器没有自动 profile。

未请求真实模型、运行真实 client 或 GPU；不据此声称方向策略有真机收益。
