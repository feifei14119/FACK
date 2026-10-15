# AGENTS.md

FACK：面向 gfx942 的 AMDGPU 汇编指令调度调优框架。
引擎（`reorder/`、`search/`、`agent/`）判定重排是否合法，真机评测由各项目的 client 完成。
总体说明见 `README.md`，设计文档见 `proj/`。

## 知识库

经过审核的经验保存在 [knowledge/](knowledge/README.md)。
`knowledge/engine/skills/*.json` 是引擎读取的结构化先验，`knowledge/skills/` 提供适用于 gfx942 的阅读资料。

| skill | 什么时候读 |
|---|---|
| [`mfma-interleave-gfx942`](knowledge/skills/mfma-interleave-gfx942/SKILL.md) | gfx942 MFMA 穿插、实测窗口查询与汇编覆盖检查；直接引用 submodule 已有导出，模型只提供估计 |
| [`aiter-gfx942-validation`](knowledge/skills/aiter-gfx942-validation/SKILL.md) | aiter 远端/Docker 环境、GPU 选择、CSV workload/.co 正反查、派发与 seed 验证、op_test 和跨尺寸对比 |

## 自学成果依赖

[`selfstudy/`](selfstudy/README.md) 是 [gfx_hw_prob](https://github.com/feifei14119/gfx_hw_prob.git)
的 Git submodule，与 testft 接入时锁定的上游提交一致。FACK 的子模块工作区只稀疏检出 `gfx942/`。

**默认跳过自学阶段，直接读取 `selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/`。**
`knowledge/skills/mfma-interleave-gfx942` 是相对软链接，不维护另一份 skill，不修改链接目标。

- 初始化或恢复依赖：在 FACK 根目录运行 `bash tools/init_selfstudy.sh`，检出固定提交并设置 gfx942 稀疏规则。
- 普通调优不自动更新 submodule，不运行 pipeline、study、fit、硬件探测、探针汇编、skill 生成或 sync 安装。
- 缺少导出时报告依赖缺失，不通过自学补齐。即使 `--dry` 也可能调用汇编器，不作为默认准备步骤。
- 只有用户明确提出自学任务时，才在上游对应 prob 项目中按其 AGENTS.md 执行；成果在上游提交后再更新 gitlink。
- 自学实现与探针测试由上游维护，不加入 FACK 默认测试集合。

路径、初始化和更新方法见 [`proj/selfstudy-submodule.md`](proj/selfstudy-submodule.md)。

## 本次复制

从 testft 复制通用框架与 gfx942 支持；随后通过 submodule 引用 gfx942 的已有自学成果。
复制与整理期间只做静态检查；在用户要求执行前，不运行项目、测试、构建或 GPU 调优。
SDK 与 Web UI 接受 `.s` 汇编作为 seed。

## 约定

- 命令都在仓库根执行；引擎入口用 `python3.8`（没有时用 `python3`）。
- 测试：`python3 -m pytest -q unittests`（只用 CPU）。不要擅自跑大规模 GPU 测试。
- 真机评测必须通过 client：`--client <client/ 下的路径>`，参数放在 `--` 之后原样透传（见 `client/README.md`）。
- 运行输出写到 `client/<名>/tune_out/` 或 `study_case/study_out/`，**不要直接写 `knowledge/`**；
  候选经验经人工审核后再晋升，流程见 `knowledge/README.md`。
- 新增 skill：放在 `knowledge/skills/<name>/SKILL.md`，用相对仓库根的路径，并在本文件登记。

## aiter client 依赖

- `client/aiter/upstream` 是 ROCm/aiter 的固定版本 submodule；初始化使用 `bash tools/init_aiter.sh`，不自动追踪 main。
- 适配层、manifest 和 driver 维护在 submodule 外；候选编译到 `client/aiter/tune_out/`，不覆盖上游 HSA 文件。
- 使用架构对应的 `aiter/hsa/<gfx>` SPEC；先在目标真机验证 seed，再调优。使用说明见 [client/aiter/README.md](client/aiter/README.md)。
- 新环境按 [操作步骤](client/aiter/docs/validation.md) 执行；已验证环境与案例随仓库保存。用户要求运行或验证任务后按授权范围执行；仅整理资料时不启动 GPU 实验。
