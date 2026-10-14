# selfstudy submodule 与 gfx942 skill 导出

`selfstudy/` 使用 https://github.com/feifei14119/gfx_hw_prob.git，
本次与 testft 同步，固定到提交 `16a0a16214374e8d99e462102b41a26a76622b9c`。
之后使用的版本以 FACK 的 gitlink 为准，不自动跟随远端更新。
FACK 原先没有 Git 仓库，本次为接入 submodule 初始化了独立的本地 Git 仓库。

## 默认流程

初始化依赖 → 阅读 gfx942 已有 skill → 在 FACK 中调优。
**默认不执行自学阶段**，不运行 pipeline、study、fit、硬件探测、探针汇编或 skill 生成。
导出目录的实际名称是 `skills_out`。

| 入口 | 路径 |
|---|---|
| 上游导出 | `selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/` |
| FACK skill 入口 | `knowledge/skills/mfma-interleave-gfx942`，相对软链接指向上游导出 |
| 编辑器入口 | `.cursor/skills` 继续指向 `knowledge/skills` |

不复制或重写生成物，不修改软链接目标。gfx942 的 skill 用于 Agent 阅读和需要时的离线查询，
不将其中的实验性模拟器接入引擎作精确时序裁决。FACK 继续只支持 gfx942，SDK 和 Web UI 继续接受 `.s` 输入。
导出缺失时报告依赖不可用，不自动生成替代数据。

## 初始化与稀疏检出

在 FACK 根目录执行：

```bash
bash tools/init_selfstudy.sh
git submodule status selfstudy
git -C selfstudy sparse-checkout list
```

脚本只做 Git 操作：检出 gitlink 锁定的提交，再将子模块工作区设为仅展开 `gfx942/`。
Git 的 cone 模式还保留上游根目录文件，例如 README.md。上游仍是完整仓库，其对象库可以包含其他架构，
但 FACK 的子模块工作区不展开 gfx1100/gfx1250，也不接入对应后端或 skill。

稀疏检出设置属于本地 Git 配置，不随 gitlink 传播。**新 clone 后使用上述脚本**；
仅执行 `git submodule update --init` 或 `git clone --recurse-submodules` 不会在新机器自动设置稀疏规则。
脚本可重复执行；它不会启动项目、生成 skill 或修改上游成果。

## 更新版本

普通调优不执行 `git submodule update --remote`。需要升级时先在上游完成研究、审核并提交导出，
再在 FACK 中选择明确的上游提交：

```bash
git -C selfstudy fetch origin
git -C selfstudy checkout <已审核的上游提交>
git -C selfstudy sparse-checkout set --cone gfx942
git add selfstudy
```

审核后将 gitlink 变更随 FACK 提交。暂存新 gitlink 后再运行初始化脚本，才会使用这个新版本。
不要在更新后、暂存前运行初始化脚本，否则它会恢复到原先锁定的提交。

## 执行与维护边界

本次接入只做文件、Git 状态、链接及语法等静态检查，没有运行项目、测试、构建、自学或 GPU 任务。
原有“先审查，再执行”的约定继续适用。
自学实现和探针测试由上游维护，不加入 FACK 默认测试集合；只有用户明确提出自学任务时，
才按上游对应 prob 的 AGENTS.md 执行。
