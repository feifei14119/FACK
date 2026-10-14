# FACK 交互式控制台 · Web UI

一个可**真正操作**的网页控制台：点按钮就能启动 FACK 的调优 / 学习(挖掘) /
测试 / 验证作业，子进程输出**实时流回页面**；并内置一份**使用说明**帮助子页面。
可在局域网内被其它机器访问。

## 启动（局域网访问）

```bash
cd webUI
./serve.sh            # 默认端口 8080
./serve.sh 9000       # 自定义端口
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
- **结果 / 技能**：读取 `tune_out/tune_result/*.summary.json` 展示最好/最坏 TFLOPS；列出技能库。
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
| `GET /api/results` | 读取调优结果汇总 |
| `GET /api/skills` | 列出技能库 |
| `GET /api/health` / `GET /api/defaults` | 健康检查 / 表单默认值 |

`action` 白名单：`tune` · `tune_quick` · `tune_tail` · `mine` · `mine_full` ·
`articulate` · `test` · `hw_validate`。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | 后端：静态服务 + 作业管理 + 结果/技能读取 |
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
