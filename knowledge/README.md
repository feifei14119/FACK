# knowledge/ —— 与工具无关的知识库

这里放 FACK 使用的、**经过人工审核**的经验：自学得到的、调优和挖掘中学到的、用户自己总结的。
任何 Agent（Cursor、Claude Code、Codex、自写脚本……）都应该能直接使用，所以这里只用两种通用格式：
给 Agent 读的 Markdown（SKILL.md），以及给引擎读的 JSON。入口索引在仓库根的 [`AGENTS.md`](../AGENTS.md)。

```
knowledge/
  README.md          本文件：格式、分类和晋升流程
  skills/            给 Agent 读的经验（SKILL.md 格式），每个主题一个目录
    <name>/SKILL.md  必需；可附 rules.md / examples.md / extending.md 等
  engine/            给引擎读的结构化知识（agent/knowledge.py 的 DEFAULT_STORE）
    skills/*.json    Skill(id, statement, when, action, evidence, effect, confidence, status)
```

`.cursor/skills` 是指向 `knowledge/skills` 的软链接，只是为了让 Cursor 照常自动发现 skill，
本身不存放内容。其他 Agent 通过 `AGENTS.md` 的索引找到这里。

`skills/mfma-interleave-gfx942/` 是指向
`selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/` 的相对软链接。
直接引用已锁定的上游导出，不复制、重新生成或手改其中的内容。

`skills/aiter-gfx942-validation/` 保存经用户同意整理的 aiter 操作流程，链接 `client/aiter/` 中维护的
Docker、op_test 脚本与验证记录。操作经验不作为引擎的指令调度先验；新实验输出继续保留在 client 的 `tune_out/`。

## skills/：给 Agent 读的经验

格式遵循通用的 SKILL.md 约定：

```markdown
---
name: my-topic                  # 与目录名一致，小写加连字符
description: >-                 # 第三人称：做什么 + 什么时候用（含用户可能说的关键词）
  ...
---

# 标题
正文：工作流、必须遵守的规则、命令、例子、出处。
```

写法要求：

- **路径相对仓库根**（例如 `isa/gfx942/...`），命令写明"在 FACK 仓库根执行"。不写 `/app/...`
  这样的本机绝对路径；必须引用外部仓库时，写仓库名并注明本机位置。
- **只写结论和做法，附上证据**：数字从哪个实验、哪个文件来，置信度如何，前提条件是什么（例如"单 wave、cache 热"）。
- SKILL.md 保持简短，细节放同目录的附属文件，并在 SKILL.md 里链接过去（只链接一层）。
- 新增或改名后，同步更新 `AGENTS.md` 的索引行。

## engine/：给引擎读的结构化知识

`agent/knowledge.py` 在 seed 阶段从 `engine/skills/*.json` 读取先验（`load_skills` / `seed_search_plan`），
用来引导搜索，**不参与裁决**（合法性由引擎判定，性能由真机判定）。调优运行**从不写入**这里。
格式见 `agent/knowledge.py` 的 `Skill`；`status` 只有经过真机证据确认才是 `trusted`。

## 知识从哪里来，怎么进来

所有自动产出先落在各自的输出目录当候选，**人工审核后**才进入 `knowledge/`：

| 来源 | 产出或引用位置 | 接入方式 |
|---|---|---|
| 上游自学成果（`selfstudy/` submodule） | `selfstudy/gfx942/mfma_issue/skills_out/skills/` | 用相对软链接直接引用；版本由 gitlink 固定，不在 FACK 中运行自学 |
| 在线调优（`tune.mjs` / `agent_session.py`） | `client/<名>/tune_out/skills/`、`experiments.log` | `engine/skills/`；可总结成文字的规律写进 `skills/` |
| 静态挖掘（`tools/mine_corpus.py`） | `study_case/study_out/skills/` | `engine/skills/` |
| 用户总结 | — | 直接写成 `skills/<主题>/SKILL.md` |

不要让任何程序直接写 `knowledge/`：一条错误经验进来，会同时误导所有 Agent 和引擎。

## 自学成果的维护边界

默认只阅读已有导出，或在用户要求执行后运行 skill 的离线查询；不运行 pipeline、study、fit、
探针汇编、硬件探测、skill 生成或 sync 安装。依赖缺失时报告缺项，不自动补跑自学。
更新成果由上游完成并提交，FACK 只更新锁定的 submodule 版本。

初始化和版本更新见 [接入说明](../proj/selfstudy-submodule.md)。
子模块工作区只展开 gfx942，其他架构的 skill 不登记到 FACK 的入口。
