---
name: aiter-tuning
description: 在 FACK 中按 aiter client 选择 workload、架构适配器及验证契约，执行配置派发验证、op_test 和关联尺寸验收。用于 aiter 调优与复现，不适用于其他 client。
---

# aiter 调优入口

命令在 FACK 根执行。先用 `python3 -m client guidance aiter/hsa/gfx942` 读取规划技能；
该步骤不加载 aiter 依赖或运行 GPU。生成 workload 后再获取绑定声明，参数和 seed 来自本次任务：

```bash
python3 -m client guidance aiter/hsa/gfx942 --seed path/to/seed.s -- --manifest path/to/workload.json
```

通用 SDK 和外部 manager 都使用这里返回的 `skills`、`workload`、`validation`。
`tools/tune_run.py init` 将它们冻结进 `manifest.evaluation_contract.agent_profile`。
读取已选择架构的技能；缺少目标 adapter 或声明的 skill 时报告缺失，不套用其他 gfx。
当前正式适配器只有 gfx942。环境与驱动细节由对应的架构验证 skill 说明。

## workload 与执行范围

- 按配置调优 GEMM 时，使用 `client/aiter/dispatch.py plan/lookup` 从真实 CSV 生成任务。
  阅读 `client/aiter/docs/dispatch-workloads.md`。保留 CSV 路径、SHA、物理行号、workload ID、
  MNK、dtype、布局、splitK 和 CU；CSV 选择不证明新机器上的全局最优。
- 不把一个 `.co` 的不同尺寸合并。其他 backend、缺少 `.co`、冲突或待适配的引用保留原因。
- 显式 manifest 可用于指定 workload 的单独验证，但不能据此声称来自 CSV 或覆盖整个 `.co`。
  MoE/MLA 使用各自的路由、stage、batch/KV 等参数，不猜测 GEMM 的 MNK。
- 环境准备完成后先验证原始 seed。所有真机评测通过所选 client，参数放在 `--` 后；
  不覆盖上游 HSA，不修改正在测量的 driver、manifest 或原始 CSV。

## 每个适配器自己的必需验证

以 `validation.metrics` 和 `validation.required_checks` 为准，不能按本次返回了什么指标来缩减要求。
当前适配器要求 HIP graph、完整输出、装载及构建身份，并分别要求：

| 适配器 | 必需 op_test 分布 |
|---|---|
| FP8 blockscale | constant/constant、uniform/auto |
| INT8 GEMM | signed_random/per_token |
| BF16 GEMM | signed_random/none |
| MoE stage1 | signed_random_routed/per_token |
| MLA stage1 | signed_random_channel_mean/unit_tensor |

CSV 绑定任务还必须通过正常入口派发验证。主机 loader/派发观察不是 GPU ATT 证明。
仅启用 graph 的基本 manifest 可做底层诊断；正式 agent 调优需使用带 op_test 的已审核 manifest。

比较策略在测量前选择并冻结；没有策略时只能报告筛选。各必需指标分别确认和 final，
缺项、数值失败或指标分歧均不能宣布获胜，不用多种分布的平均值代替逐项裁决。
当前多指标 run 必须选择固定样本的 `paired_sign_v1` 策略；sequential policy 尚不支持多指标。

## 关联尺寸与交付

单 run 的 final 只推荐当前 workload。扩大到 `.co` 采用之前，固定同一候选，使用
`client/aiter/compare.py` 比较该 `.co` 的全部可运行关联 workload，再由
`client/aiter/dispatch.py assess` 汇总。保留待适配和漏测范围；全局未通过时不得宣称通用替换。

记录已搜索、仅做关联比较、原版保留、待适配和未开始的区别。保存 `.s/.co`、SHA、原始记录、
逐方法结果和复现命令到 `client/aiter/tune_out/`。按用户要求报告进度；结束时停止本次专用容器并核对状态。
新实验经验先作为候选保存，不自动晋升知识库或启动自学。
