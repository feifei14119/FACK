---
name: aiter-gfx942-validation
description: 在 FACK 中准备 gfx942 aiter Docker 环境，从 dispatch CSV 正反查 workload/.co，验证正常入口派发和 seed，执行上游 op_test 及跨尺寸配对比较。适用于 aiter client 接入验证、按配置调优和换机器复现。
---

# aiter gfx942 环境与单算子验证

先按 [aiter 调优入口](../aiter-tuning/SKILL.md) 选择 workload 和必需验证契约。
本技能补充 gfx942 环境及执行细节，不负责其他 client 或架构。

所有命令在目标机器的 FACK 仓库根执行。先读
[操作步骤](../../../client/aiter/docs/validation.md)，按当前任务选择环境准备、seed 验证或 op_test 比较。
环境配置和正式脚本随仓库维护，不能依赖已有 `tune_out/`、某个旧容器或固定机器目录。
按 CSV 选择调优尺寸时，读 [dispatch workload 操作](../../../client/aiter/docs/dispatch-workloads.md)，
使用 `client/aiter/dispatch.py plan/lookup/assess`，不临时重写解析、去重或尺寸猜测脚本。

## 操作顺序

1. 确认用户选择的机器和 GPU 范围；已获得的执行授权继续有效。仅整理资料时不启动 GPU 实验。
2. 用 `client/aiter/docker_env.py inventory` 查看设备；`start --gpu second-last` 或显式 PCI/UUID 创建本次容器。
   工具按 UUID 限定一个 GPU，并用容器内 PCI 地址核对。已有可见设备限制会明确报错，先弄清限制对应的授权范围。
3. `client/aiter/doctor.py` 检查解释器、依赖、固定 aiter 提交、工具链和 GPU 身份；它不执行 kernel/JIT。
   按 `client/aiter/env/gfx942.json` 选择已验证环境。缺依赖时修复镜像/环境，不随意替换 ROCm PyTorch 或禁用版本检查。
   对 CSV 调优读取实际 CU 数并生成新 dispatch plan；明确默认/model/env/显式配置来源，处理冲突后再执行任务。
4. 初始化固定 submodule（缺失时才初始化），通过 `client/aiter/prepare.py` 导出 seed，再用
   `tools/eval_candidate.py --client aiter/hsa/gfx942 -- ...` 验证完整输出。回编失败或数值失败时停止调优。
5. 调优继续用已有 `tools/tune_run.py`，先验证 original；使用用户指定或计划导出的 workload，不擅自修改 MNK/splitK。
   CSV 任务还要求 `dispatch_check.correct=True`；保留每个 workload ID，不按 `.co` 去重跳过其他尺寸。
6. 正式 agent 调优必须使用带 op_test 且与目标匹配的 manifest。CSV 导出的 manifest 已开启 GEMM op_test，不替换 driver。
   默认 blockscale 示例才使用 `client/aiter/hsa/gfx942/optest_manifest.json`。检查所有完整输出比较。
7. 比较两个确定的 `.s` 用 `client/aiter/compare.py ... --client aiter/hsa/gfx942 -- ...`。
   事先指定配对次数和收益门槛，分别报告 op_test profiler 与 HIP graph 的结果。
   同 `.co` 使用一份固定候选逐尺寸比较，再用 `dispatch.py assess` 汇总；漏测、待适配或回退不能被最快尺寸掩盖。
8. 记录产物目录，停止本次创建的容器；不停止他人的容器，不覆盖上游 HSA 文件。

## 关键判断

- `correct=True`、有效计时和目标 symbol 的 LoadKernel 路径必须同时存在。主机装载日志不等于 GPU dispatch/ATT 证明。
- CSV 引用只说明该配置选择该 kernel，不说明全局最优。运行时使用冻结的 gfx/CU 配置覆盖并验证正常入口；不宣称复现所有默认配置或 heuristic 输入。
- 不运行上游配置合并器修改原 CSV；冲突用显式来源解决。MoE/MLA 缺完整 workload 或匹配 adapter 时保留待办及原因，不套用 GEMM 参数。
- `op_test` 的 `checkAllclose` 正常返回不代表通过；正式 driver 要求错误率为 0，并检查非有限值。
- `optest_driver.py` 的 AST 加载边界与 symbol 绑定只对已审核上游文件有效。SHA 不匹配时复核接口，不能只更新散列绕过检查。
- 新 seed、shape、目录、run-id 都是参数；不复制历史脚本中的 `seed == 123`、GPU 6 或日期目录。
- 无显著收益、结果回退或证据不足时保留基线。不同计时方式有分歧时同时报告，不取一个最快数值作为推荐。
- 默认继续跳过自学。缺少 selfstudy 导出按根 AGENTS.md 处理，不运行探针或 pipeline 补齐。

[2026-10-14 实测记录](../../../client/aiter/docs/validated-runs/20261014.md)
给出已验证的环境组合、失败原因和结果边界；历史吞吐量不能作为其他机器的保证。
[正式入口的迁移验证](../../../client/aiter/docs/validated-runs/20261014-portability.md)
记录独立 checkout、新容器、非默认 seed 的实测，包含 UID/缓存问题的修复与适用范围。
