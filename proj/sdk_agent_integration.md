# SDK 驱动的 Cursor agent 接入（元层调优师的程序化运行）

> 本篇承接 `knowledge_agent_design.md`（元层 agent 的角色与安全原则）与 `if/ai_interface.md` §3.4（LLM 决策面）。
> 前者讲"agent 该做什么"，本篇讲"用 **Cursor SDK** 把这个 agent **程序化、无人值守地跑起来**——它就是 Cursor 的 agent，但在脚本里自动驱动引擎"。

---

## 1. 全链路：谁在调 SDK、谁在做决策、谁在裁决

```
node tools/sdk/tune.mjs                                  ← 唯一调用 Cursor SDK 的地方
   └─ Agent.create({local:{cwd:testft}}) + agent.send(PROMPT)   ← 起一个本地 Cursor agent
        └─ Cursor agent（决策者，带 shell/文件工具）             ← “会思考的东西”
             └─ python3.8 tools/agent_session.py {observe|propose|eval}   ← 决策面 CLI（不碰 SDK）
                  └─ AgentSession → 固定逻辑引擎（重排/重算/Verifier/真机评测）  ← 裁决合法性 + 性能
```

- **决策（提哪个 layout）= Cursor agent**：读 `observe` 的 JSON 事实地图、推理、调 `propose`/`eval`、看 `SkipReason` 迭代。
- **裁决（合不合法 / 多快）= 固定逻辑引擎 + 真机**：agent 只导航，错误决策只浪费搜索预算，**绝不可能产坏 kernel**
  （见 `knowledge_agent_design.md` §2）。
- **唯一调 SDK 的文件是 `tools/sdk/tune.mjs`**；`agent/session.py`、`tools/agent_session.py`、`search/`、引擎全部**不依赖 SDK**，
  它们由 SDK 起的 agent 通过 shell 调用。

### SDK 调用点（`tools/sdk/tune.mjs`）

| 调用 | 作用 |
|---|---|
| `import { Agent, CursorAgentError } from "@cursor/sdk"` | 导入 SDK |
| `Agent.create({ apiKey, model:{id}, local:{cwd:REPO} })` | 起一个**本地** Cursor agent，工作目录 = testft 仓库 |
| `agent.send(PROMPT)` | 下发"元层调优师"任务（见 §4） |
| `run.stream()` | 流式读 agent 的助手文本输出 |
| `run.wait()` | 拿终态；`status=="error"` 表示**跑起来但失败了**（exit 2） |
| `catch CursorAgentError` | 表示**没启动**（鉴权/配置/网络），exit 1 |
| `finally agent[Symbol.asyncDispose]()` | 释放本地执行器/句柄 |

---

## 2. 为什么是 TypeScript/Node SDK 而不是 Python SDK

- Python SDK（`cursor-sdk`）要求 **Python ≥3.10**；本工程机器只有 **3.8.17 / 3.6.8** → 不可用。
- TS/Node SDK（`@cursor/sdk`）只要 **Node ≥18**；机器有 **Node v20** → 选它。
- 两者**互不冲突**：Node 脚本只负责"起 agent"；**引擎仍跑在 `python3.8`**，由 agent 通过 shell 调 `tools/agent_session.py`。
  即语言分层——编排用 Node，引擎用 Python。

---

## 3. 裸机前置条件（不装 Cursor IDE/app 也能跑）

`@cursor/sdk` 的 **local runtime 是自带的**，不依赖系统装没装 Cursor 桌面版：
`npm install` 会按平台拉运行时包（本机 = `@cursor/sdk-linux-x64`），其 `bin/` 自带执行器二进制
`cursorsandbox` + `rg`（ripgrep）——agent 的本地执行循环 / 文件 / shell / 沙箱都打包在 npm 依赖里。

| 需要 | 为什么 | 备注 |
|---|---|---|
| **Node ≥18** | 跑 `tune.mjs` + SDK 本地运行时 | 本机 v20 ✅ |
| **`npm install`（联网到 npm registry）** | 拉 `@cursor/sdk` + 平台运行时包 | 已装 ✅ |
| **`CURSOR_API_KEY` + 能联网到 Cursor 后端** | ⚠️ 见下方关键误解 | 鉴权 + 模型推理 |
| **工程运行时**（`python3.8` 等；`eval` 还要真机 GPU 链）| agent 用 shell 调引擎 CLI；`eval` 走 `harness/evaluator.py` | `observe`/`propose` 不需 GPU |

### ⚠️ 关键误解：local runtime ≠ 离线 / 本地大模型

`local` 指 **agent 的执行器和工具在本机跑（对着 `cwd`）**，但**大模型推理仍在 Cursor 云端**。
所以**必须有网 + 有效 key**；做不到完全脱离 Cursor 基础设施（那等于自带一个大模型）。

---

## 4. 元层调优 PROMPT 的约束（写在 `tune.mjs` 里）

agent 收到的任务严格编码了"只导航、不裁决"的纪律：

1. `observe` 读事实地图（MFMA 锚点 / 逐 slot 当前布局 / 每条可动指令的 `kind`+`legal_window`+`movable`+`is_prefetch` /
   延迟边 / **受保护预取集** / `direction` 投票 / 知识层先验）。
2. **先 `propose`（便宜）**：非法就读 `reason`+`window`+`bound_iid` 修正，不为非法布局付 `eval` 的钱。
   - `prefetch_protected`：试图**下沉**被识别的跨迭代预取 load——禁止；预取 load 只能 hoist。
   - `mem/raw/war/waw/mfma_latency/lds_roundtrip/fence_blocked`：尊重 `bound_iid` 与 `[lo,hi]`。
3. `propose` 全合法后才 `eval`。
4. **`direction` 只当噪声先验**（投票仍可能错）；唯一裁决是 `eval` 的实测 `tflops`+`correct`，只保留 `accepted==true`。
5. 跑满 `--rounds` 或没有候选超过当前最优即停。

---

## 5. 用法

```bash
# 1) 装依赖（联网 npm；约 27MB，含平台运行时）
cd tools/sdk && npm install

# 2) 注入 key —— 共享 root 机器务必看 §6 的安全约束
read -rs CURSOR_API_KEY && export CURSOR_API_KEY   # 静默输入，不进 history

# 3) 跑
node tune.mjs ../../testcase/shader/fp8gemm_blockscase_32mx1_32nx4.s \
      --k 8192 --loop 20 --rounds 6 --model auto

# 4) 用完立刻清掉
unset CURSOR_API_KEY
```

- `--model` 默认 `auto`（服务端选模型，避免写死无权限的 id）。
- 退出码：`0` 正常完成；`1` 没启动（`CursorAgentError`/缺 key，修环境重试）；`2` 用法错误或 run 启动后失败（去 dashboard 查 `run.id`）。
- 启动后先打印 `agent=<id> run=<id>`（stderr）再流式输出，便于流挂住时排查。

---

## 6. 共享 root 机器上的密钥安全（重要）

本工程机器实测为**共享 root 环境**（会话即 `uid=0`，`/proc` 无 `hidepid`，`umask 0002`）。结论：

- **共享 root = 无用户隔离**：其他同为 root 的人可读 `/proc/<pid>/environ`、读任意 `chmod 600` 文件、读 `~/.bash_history`、dump 内存。
  ⇒ **`export`、0600 文件、密钥文件，对其他 root 都无法真正保密。**
- 两个放大器：`/proc` 无 `hidepid` → **绝不能把 key 当命令行参数传**（`/proc/<pid>/cmdline` 全局可读，连非 root 都能看）；
  `umask 0002` → 新建文件默认世界可读，落文件前须 `umask 077` + `chmod 600`（但仍挡不住 root）。

可行的不是"保密"，而是**缩小爆炸半径**：

1. 用 **team service-account key**（最小权限），**别用个人长期 key**。
2. **别持久化**（不写 `~/.bashrc`、不写仓库、不建世界可读文件）；用 `read -rs` 注入，用完 `unset`。
3. **别进命令行参数**（见上）。
4. **用完立刻 rotate/revoke**——在共享 root 上最有效的保护是"泄露出去的 key 已失效"。
5. 更彻底：把 `tune.mjs` 放**你独占的机器**上跑（或用 cloud runtime），这台共享机只留不需要 key 的
   `observe`/`propose` CLI。

---

## 7. 分区调优（循环前 / 循环体 / 循环结束）

kernel 被静态切成 **PROLOGUE / LOOP（可多段）/ INTER / EPILOGUE**，agent 可分别调优。任何命令加 `--region SEL`：

| `--region` | 含义 |
|---|---|
| `loop`（默认） | core loop 主循环体，通常杠杆最大 |
| `prologue` / `epilogue` | 进循环前 / 循环结束后 |
| `inter` / `loop#1` | 两循环之间 / 第 2 个循环 |
| `all`/`auto`（仅 `tune.mjs`） | 不钉死，让 agent 自己在各区间切换 |

- `tune.mjs --region <X>` 把 agent **钉死**在某区（prompt 强制每条 `observe/propose/eval` 都带 `--region <X>`）；
  `--region all` 则放开。`tune_quick.sh [--region X]` 默认主循环区。
- `agent_session.py observe` 永远在 `"regions"` 列出全部区（index/kind/行号区间/指令数）、`"region"` 回显选中区。
- **正确性**：改 loop 区用 loop-aware 重算；改非循环区引擎自动改用整核 `recompute_cfg` 跨区穿 scoreboard，
  保证「循环内发起、epilogue 才 drain」的异步访存 waitcnt 正确——对 LLM 透明、无需关心。

详细决策面接口见 `proj/if/ai_interface.md` §3.4.2b–d；用法见 `tools/sdk/README.md`。

---

## 8. 现状与边界

- ✅ 已实现：`tools/sdk/`（`package.json` 锁 `@cursor/sdk@^1.0.18` + `tune.mjs` + `README.md` + `.gitignore`）；
  依赖安装、SDK import、参数解析、无-key 优雅退出（exit 1/2）、分区 `--region`（含 pin/roam 两种 prompt 渲染）均冒烟通过。
- ❌ 未做：**真实带 GPU + 有效 `CURSOR_API_KEY` 的端到端跑**——本环境无 key、无 ≥3.10 Python（Python SDK），
  且 `eval` 需真机 GPU 链。设好 key 后即可按 §5 运行。
- 决策可追溯：每次 `commit_and_eval` 已记入 `client/<名>/tune_out/experiments.log`（`decided_by:"llm_agent"`）。
