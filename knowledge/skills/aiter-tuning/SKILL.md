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

## SDK 成果发布

绑定的 aiter profile 声明 `publication.mode=git_commit_push`。SDK worker 正常结束、final 推荐候选、
报告成功后，由固定程序 `tools/publish_run.py RUN` 自动复制实测 `.co`，追加根 README，commit 并 push。
worker 不自行编辑 README、复制发布文件或执行 Git 写操作。此流程已获项目用户授权，后续按此执行。

输出为 `client/aiter/co_out/<gfx>/<原 co 相对路径>`，纳入 Git；`.versions/<CO SHA>/` 保留同结构的
不可变版本，`.sources/` 保存汇编，`records/` 保存逐项结果、输入、CSV 来源、SHA 和调优时间。
README 每行包含序号、co 路径、输入尺寸、所有必需方法的配对提升、UTC 完成时间及 run 耗时。
发布表示所记录 workload 的性能提升，不表示已经通过所有关联尺寸的通用替换验收。

只发布 final 的全部必需指标均确认提升、且实际 `.co` 与原版不同的候选；保留 original、筛选、
仅 confirm、验证缺项或失败均不追加。复制的必须是参与 final 的同 SHA 产物，不为发布重新编译。
同候选／原版／输入重复发布不重复记行；同名新版本保留旧文件，README 链接固定版本。
Git 使用独立暂存区，不带入其他文件或 README 的既有编辑；推送失败保留本地 commit，
显式重跑 `python3 tools/publish_run.py RUN` 重试，不自动 force push、pull 或 rebase。
