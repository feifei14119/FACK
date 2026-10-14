---
name: aiter-gfx942-validation
description: 在 FACK 中准备本地或远端 gfx942 aiter Docker 环境，验证单个 .co 的 seed，执行固定 symbol 的上游 op_test 和配对比较。适用于 aiter client 接入验证、换机器复现及调优后的算子对比。
---

# aiter gfx942 环境与单算子验证

所有命令在目标机器的 FACK 仓库根执行。先读
[操作步骤](../../../client/aiter/docs/validation.md)，按当前任务选择环境准备、seed 验证或 op_test 比较。
环境配置和正式脚本随仓库维护，不能依赖已有 `tune_out/`、某个旧容器或固定机器目录。

## 操作顺序

1. 确认用户选择的机器和 GPU 范围；已获得的执行授权继续有效。仅整理资料时不启动 GPU 实验。
2. 用 `client/aiter/docker_env.py inventory` 查看设备；`start --gpu second-last` 或显式 PCI/UUID 创建本次容器。
   工具按 UUID 限定一个 GPU，并用容器内 PCI 地址核对。已有可见设备限制会明确报错，先弄清限制对应的授权范围。
3. `client/aiter/doctor.py` 检查解释器、依赖、固定 aiter 提交、工具链和 GPU 身份；它不执行 kernel/JIT。
   按 `client/aiter/env/gfx942.json` 选择已验证环境。缺依赖时修复镜像/环境，不随意替换 ROCm PyTorch 或禁用版本检查。
4. 初始化固定 submodule（缺失时才初始化），通过 `client/aiter/prepare.py` 导出 seed，再用
   `tools/eval_candidate.py --client aiter/hsa/gfx942 -- ...` 验证完整输出。回编失败或数值失败时停止调优。
5. 调优继续用已有 `tools/tune_run.py`，先验证 original；本 skill 不推断新候选或扩大 workload。
6. 要求 op_test 时，透传 `--manifest client/aiter/hsa/gfx942/optest_manifest.json`。
   正式 driver 调用上游单 shape 的 `test_gemm`，固定 symbol/splitK，检查所有完整输出比较。
7. 比较两个确定的 `.s` 用 `client/aiter/compare.py ... --client aiter/hsa/gfx942 -- ...`。
   事先指定配对次数和收益门槛，分别报告 op_test profiler 与 HIP graph 的结果。
8. 记录产物目录，停止本次创建的容器；不停止他人的容器，不覆盖上游 HSA 文件。

## 关键判断

- `correct=True`、有效计时和目标 symbol 的 LoadKernel 路径必须同时存在。主机装载日志不等于 GPU dispatch/ATT 证明。
- `op_test` 的 `checkAllclose` 正常返回不代表通过；正式 driver 要求错误率为 0，并检查非有限值。
- `optest_driver.py` 的 AST 加载边界与 symbol 绑定只对已审核上游文件有效。SHA 不匹配时复核接口，不能只更新散列绕过检查。
- 新 seed、shape、目录、run-id 都是参数；不复制历史脚本中的 `seed == 123`、GPU 6 或日期目录。
- 无显著收益、结果回退或证据不足时保留基线。不同计时方式有分歧时同时报告，不取一个最快数值作为推荐。
- 默认继续跳过自学。缺少 selfstudy 导出按根 AGENTS.md 处理，不运行探针或 pipeline 补齐。

[2026-10-14 实测记录](../../../client/aiter/docs/validated-runs/20261014.md)
给出已验证的环境组合、失败原因和结果边界；历史吞吐量不能作为其他机器的保证。
[正式入口的迁移验证](../../../client/aiter/docs/validated-runs/20261014-portability.md)
记录独立 checkout、新容器、非默认 seed 的实测，包含 UID/缓存问题的修复与适用范围。
