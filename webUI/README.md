# FACK 交互式控制台 · Web UI

一个可**真正操作**的网页控制台：点按钮就能启动 FACK 的调优 / 学习(挖掘) /
测试 / 验证作业，子进程输出**实时流回页面**；并内置一份**使用说明**帮助子页面。
可在局域网内被其它机器访问。

## 启动（局域网访问）

```bash
bash webUI/serve.sh            # 从仓库根启动，默认端口 8080
bash webUI/serve.sh 9000       # 自定义端口
```

启动后终端打印可访问地址，例如：

```
本机访问:   http://127.0.0.1:8080
局域网访问: http://10.67.77.162:8080
```

同一局域网的其它机器在浏览器打开**局域网访问**地址即可。

> 打不开多半是**防火墙**没放行端口：
> ```bash
> sudo firewall-cmd --add-port=8080/tcp        # firewalld（临时）
> # 或
> sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
> ```

后端 `server.py` 只用 **Python 3.8 标准库**，零第三方依赖。

## 页面

| 页面 | 说明 |
|---|---|
| `index.html` | **主控制台**：调优 / 学习 / 测试·验证 / 结果 四个标签 + 右侧实时运行监控 |
| `help.html` | **使用说明**（原文档页，含全部命令与参数），控制台右上角「使用说明 →」进入 |

### 控制台能做什么（点按钮 = 真正执行）

- **调优**：填 seed / testcase / 透传参数 / region / rounds 等，点「开始调优」→ 后端跑 `tune.mjs`。
  也有「快跑 tune_quick.sh」「尾段 tune_prologue_epilogue.sh」一键脚本按钮。
- **学习 / 挖掘**：填语料/产出目录跑 `mine_corpus.py`（Layer 1，无需 GPU）；
  或一键 `mine_skills.sh`（L1+L2）；或 `articulate.mjs`（Layer 2 离线 AI 归纳）。
- **测试 / 验证**：一键跑单元测试；填候选 .s 跑 `hw_validate.sh`（需 GPU）。
- **结果 / 技能**：按 client、gfx、.co / symbol / 任务筛选，查看最终选择和基线/候选性能对比；列出技能库。
- **运行监控**：多作业标签页，实时日志（可跟随滚动），随时「停止」。

> 需要 GPU / API key 的作业（调优、articulate、hw_validate）在无 GPU / 无 key 的机器上会失败，
> 日志里会给出原因。API key 可在表单里临时填（仅当次运行用、不保存），或用 env / `cursor.config.json`。

## 架构

```
浏览器 (index.html / help.html)
   │  fetch /api/*
server.py (Python3 stdlib, 绑定 0.0.0.0)
   │  subprocess (argv 白名单, 无 shell 注入)
   └─ node tune.mjs / mine_corpus.py / *.sh …  (cwd = 仓库根)
        输出 → webUI/.runs/<id>.log → 页面轮询实时展示
```

### API 一览

| 方法 · 路径 | 作用 |
|---|---|
| `POST /api/run` | 启动作业 `{action, params}`，返回 job |
| `GET /api/jobs` | 列出全部作业 |
| `GET /api/job?id=&offset=` | 拉某作业状态 + 增量日志 |
| `POST /api/stop` | 停止作业 `{id}` |
| `GET /api/results` | 返回 `{results, errors}`：调优对象、最终状态和分项性能；单个坏记录不影响其他结果 |
| `GET /api/skills` | 列出技能库 |
| `GET /api/health` / `GET /api/defaults` | 健康检查 / 表单默认值 |

`action` 白名单：`tune` · `tune_quick` · `tune_tail` · `mine` · `mine_full` ·
`articulate` · `test` · `hw_validate`。

### 结果数据来源

结果页全宽显示，每条记录包含 client、gfx、原始 .co、最终选择、测量方法、基线/候选中位数、
配对提升及其统计界限。µs 越低越好，吞吐量越高越好；配对提升不一定等于两列中位数的直接比值。
client、gfx、.co 从记录中的身份信息提取，缺失时显示“未记录”，不套用当前 manifest。

| 位置（相对 `client/<名>/`） | 展示方式 |
|---|---|
| `tune_out/runs/<id>/manifest.json` + `state.json` | 读取当前权威状态并复用报告的完整性检查，展示最终配对结果；不依赖可能过期的 `report.json` |
| `tune_out/comparisons/<id>/comparison.json` | 固定两份代码的比较；HIP graph 与各 op_test 分布分别展示，不自动标记为采用候选 |
| `tune_out/tune_result/*.summary.json` | 兼容旧版筛选记录，明确标记“仅筛选结果”，不据此生成最终收益 |
| `docs/validated-runs/*.json` | 随仓库保存的实测证据，标记“归档实测”；同 seed 的迁移验证标记“同代码流程自检” |

读取结果不会启动调优、GPU 测试或写出报告。未完成、测量失败、原始代码未经测量的回退等状态，
显示缺失的最终对比，不填造 0% 收益。最终保留 original 时，表中候选数据仍表示被比较的候选，
不表示它已被采用。点击“记录来源与算子信息”可查看数据来源、symbol 和候选 ID。

页面读取启动服务所在 checkout 的记录，不自动连接远端机器或扫描 JIT/临时 clone 目录。
在远端运行的任务可在对应 checkout 启动 Web UI；归档实测无需旧 `tune_out/` 即可显示。

CPU 回归检查：

```bash
python3 -m pytest -q unittests/test_webui_results.py unittests/test_run_report.py
node --test webUI/results.test.cjs
```

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | 后端：静态服务 + 作业管理 + 结果/技能读取 |
| `results.py` / `results.js` | 结果记录适配、筛选及性能表格渲染 |
| `index.html` / `console.css` / `console.js` | 控制台前端 |
| `help.html` / `app.js` / `data.js` | 使用说明帮助页（改 `data.js` 即可更新文档） |
| `styles.css` | 共享深色 UI 样式 |
| `serve.sh` | 一键启动 |
| `.runs/` | 作业日志（运行时生成） |

## 安全说明

- 后端只执行**固定白名单动作**，参数以 argv 列表传给子进程（不经过 shell，杜绝命令注入）。
- 但这些动作本身会在**本机以启动者身份**执行真实命令（编译、跑 exe、起 agent）。
  请**只在受信任的局域网**内开放；不要暴露到公网。
- API key 若在表单填写，仅作为该次子进程的环境变量传入，**不落盘、不回显**。
