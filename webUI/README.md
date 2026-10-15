# FACK 交互式控制台 · Web UI

按 CSV workload 管理的交互控制台：生成计划、验证原始代码、创建持久化调优任务、执行 op_test 配对比较与跨尺寸汇总。
子进程输出实时显示；结果直接标注测试尺寸、CSV 文件和行号，产物路径信息默认折叠。
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
| `index.html` | **主控制台**：调优 / CSV 工作负载 / 技能·静态挖掘 / 测试·验证 / 结果 / 远端进度 + 作业监控 |
| `help.html` | **使用说明**（原文档页，含全部命令与参数），控制台右上角「使用说明 →」进入 |

### 控制台能做什么（点按钮 = 真正执行）

- **CSV 工作负载**：读取 `dispatch.py` 生成的计划，按 .co、尺寸、CSV、行号和状态筛选；同一 .co 保留多个 workload。
- **调优**：选择计划和 workload → 导出 seed → 原始派发/op_test 验证 → `tune_run.py init`；随后按 run 执行 status/observe/suggest/prepare/eval/confirm/final。创建任务不等于已经调优。
- **测试 / 验证**：沿用选定 workload 的冻结 manifest，执行候选 op_test、原始/候选独立配对比较和跨尺寸覆盖汇总；CPU 测试用 pytest。
- **结果 / 技能**：统一展示本机记录、远端同步实测和归档结果。尺寸与 CSV 来源直接可见，产物路径默认折叠。
- **技能 / 静态挖掘**：默认读取已审核 aiter/MFMA skill 与固定 selfstudy 导出。静态语料挖掘是独立可选任务，不自动启动自学。
- **高级 SDK**：可使用所选 manifest 启动 SDK agent；筛选结论仍需独立比较。

执行按钮使用 **Web UI 所在环境**。GPU 操作需要该环境的 ROCm Python/工具链，并明确限制单卡；远端进度页只读本机同步数据，不隐式 SSH。端口上的旧服务需要重启才会加载新后端代码。
详细 workflow 见 [dispatch 操作](../client/aiter/docs/dispatch-workloads.md) 和 [aiter 验证](../client/aiter/docs/validation.md)。

## 架构

```
浏览器 (index.html / help.html)
   │  fetch /api/*
server.py (Python3 stdlib, 绑定 0.0.0.0)
   │  subprocess (argv 白名单, 无 shell 注入)
   └─ dispatch.py / prepare.py / tune_run.py / compare.py …  (cwd = 仓库根)
        输出 → webUI/.runs/<id>.log → 页面轮询实时展示
```

### API 一览

| 方法 · 路径 | 作用 |
|---|---|
| `POST /api/run` | 启动作业 `{action, params}`，返回 job |
| `GET /api/jobs` | 列出全部作业 |
| `GET /api/job?id=&offset=` | 拉某作业状态 + 增量日志 |
| `POST /api/stop` | 停止作业 `{id}` |
| `GET /api/workloads` | 只读 dispatch 计划、逐尺寸任务和 CSV 行来源 |
| `GET /api/results` | 返回 `{results, errors}`：调优对象、最终状态和分项性能；单个坏记录不影响其他结果 |
| `GET /api/campaigns` | 读取本机任务快照，展示远端调优进度、同步状态、全部 .co 和待完成清单 |
| `GET /api/campaign/export?campaign=&file=` | 下载已取回且列入确认清单的本机产物；下载前再次核验 SHA256 和字节数 |
| `GET /api/skills` | 列出技能库 |
| `GET /api/health` / `GET /api/defaults` | 健康检查 / 表单默认值 |

`action` 白名单：`dispatch_plan`、`dispatch_prepare`、`dispatch_validate`、`dispatch_init`、
`run_step`、`dispatch_evaluate`、`dispatch_compare`、`dispatch_assess`，以及高级 `tune`、`mine`、`articulate`、`test`。
旧 poc_kl 快跑、尾段与 hw_validate 操作明确拒绝，不再指向已移除的 client。

### Workload 元数据

前端共用 `workload_view.js` 展示完整测试输入、CSV 文件/行号和正常入口验证状态。
后端 `workloads.py` 从记录中的 workload 或 SHA 匹配的冻结 manifest 提取；早期 dispatch manifest
缺行号时只在它记录的源 SHA 和完整行均匹配时恢复。不会用最新 CSV 反查给历史实验补来源。
旧实验可显示记录中的 MNK；无 CSV 证据时显示“未记录”，缺尺寸时保持未知。
新导出的 dispatch manifest 和 runner 结果携带源行元数据，便于远端同步和迁移后展示。
工作负载执行进度按 workload ID 关联验证、run 和比较记录；不按 `.co` 合并尺寸。
单次验证读取 client 在所有构建/身份检查之后保存的 `evaluation.json`，不会把原始 runner 的成功当成 client 最终通过。

### 结果数据来源

结果页全宽显示，每条记录包含 client、gfx、原始 .co、最终选择、测量方法、基线/候选中位数、
配对提升及其统计界限。µs 越低越好，吞吐量越高越好；配对提升不一定等于两列中位数的直接比值。
client、gfx、.co 从记录中的身份信息提取，缺失时显示“未记录”，不套用当前 manifest。

| 位置（相对 `client/<名>/`） | 展示方式 |
|---|---|
| `tune_out/runs/<id>/manifest.json` + `state.json` | 读取当前权威状态并复用报告的完整性检查，展示最终配对结果；不依赖可能过期的 `report.json` |
| `tune_out/comparisons/<id>/comparison.json` | 固定两份代码的比较；HIP graph 与各 op_test 分布分别展示，不自动标记为采用候选 |
| `tune_out/eval-*/evaluation.json` | client 完整校验后的单次验证结果，显示输入/CSV 和耗时；不生成配对收益 |
| `tune_out/tune_result/*.summary.json` | 兼容旧版筛选记录，明确标记“仅筛选结果”，不据此生成最终收益 |
| `docs/validated-runs/*.json` | 随仓库保存的实测证据，标记“归档实测”；同 seed 的迁移验证标记“同代码流程自检” |

读取结果不会启动调优、GPU 测试或写出报告。未完成、测量失败、原始代码未经测量的回退等状态，
显示缺失的最终对比，不填造 0% 收益。最终保留 original 时，表中候选数据仍表示被比较的候选，
不表示它已被采用。点击“产物路径信息与记录来源”可查看来源路径、symbol 和候选 ID。

页面读取启动服务所在 checkout 的记录，不自动连接远端机器或扫描 JIT/临时 clone 目录。
在远端运行的任务可在对应 checkout 启动 Web UI；归档实测无需旧 `tune_out/` 即可显示。

### 远端任务进度

打开 `/#campaigns` 可查看本机同步的远端调优任务。页面每 15 秒读取一次本地快照；
同步程序独立运行，每分钟通过 SSH 读取控制文件指定任务目录的 `inventory.json`、
`progress.json` 和 `remaining.json`，附带读取任务目录中的 watchdog 两份状态文件，
不扫描 JIT、clone 或执行 GPU 工作：

```bash
python3 tools/aiter_campaign_monitor.py --control client/aiter/tune_out/campaigns/<任务>/control.json
```

控制文件需要 `campaign_id`、UTC `started_at` / `deadline`、`remote` SSH 目标、
`remote_output` 和 `local_output`；`report_interval_seconds` 默认 600。
远端三份 JSON 使用 `{campaign_id, updated_at, kernels: [...]}`，每条 kernel 包含
`co`、`category`、`status`、`reason`、`run_id`、`metrics`、`artifacts`，进度文件另含
`phase`、`current_co` 和 `counts`。同一 .co 以 progress 字段优先。

本机保存 `remote/` 原始状态副本、`snapshot.json`，以及每 10 分钟的
`report-<UTC>.md/.json` 和 `reports.jsonl`。周期按开始时间的墙钟刻度计算，
不叠加同步耗时。达到 deadline 后留 5 秒让外部 watchdog 发布停止结果，
再发起最后一次同步；若控制文件含 `container`，只读核验该专用容器的 Docker 状态。
输出 `final-report.md/.json` 和 `remaining.csv` 后退出。报告分别标注监控结束
和 GPU 停止核验；没有停止证据时明确显示 `stop_unverified`。进程锁避免重复监控。
最终另保存 `remaining-by-stage.csv`，区分未开始、seed/适配失败、候选/复测未完成、
模型覆盖待核实和阶段证据不足；`completed-original-retained.csv` 单列已完成但保留原始的对象。
这些分类只读现有 run/阶段/原因字段，不改远端 status，blocked 不统一等同未尝试。

产物列明确展示远端路径：容器 `/workspace/FACK/` 和仓库相对路径映射到控制文件的
`remote_workspace`，不表示文件已经复制到本机。截止报告先写出，再按远端任务目录
`export/manifest.json` 的固定清单取回已确认采用的 `selected.co`、`selected.s` 和小型
比较摘要，双端核验 SHA256 / 字节数；每文件不超过 16 MiB，总量不超过 128 MiB。
本机产物存入任务的 `exports/`，取回结果见 `exports-sync.json` 及最终报告。
不会追踪 kernel 任意 artifact 路径或复制未采纳候选的完整目录。
已完成的 checkpoint 取回会立即显示本机文件和下载链接；坏导出元数据不会隐藏任务进度。
后续清单更新同名文件时，原本机字节先按 SHA 保存到 `export-history/`，并在
`export-history.jsonl` 记录旧 SHA、新 SHA 及旧文件是否曾核验，避免更新比较元数据时丢失旧证据。

性能摘要区分原始筛选与独立配对测量。最终配对优先显示，确认阶段配对收进详情；
参考代码只有在 `reference_id=original` 时标为“原始”，否则称“参考”，并显示两侧代码 ID。
配对收益使用记录中的统计量，不用两列中位数重新计算。明确 `valid_for_adoption=false`
的记录显示“候选验证失败，不可采用”，历史配对值仅在完整字段中保留；正常保留原始代码
的记录可省略该字段或填 null，不会因此被误判失败。

独立诊断使用 `progress.diagnostic`，历史记录放在 `diagnostic_history`；诊断完成不计入
候选采用或 `.co` 完成数。监控只取 `summary_path` 和其中明确列出的同一诊断目录内
`result_path` / `comparison_path` JSON，限制每文件 2 MiB、合计 16 MiB、最多 64 文件，
双端核验 SHA256 和大小。不会递归抓取 workdir、core 或目录外引用；未变化的诊断跳过重复传输。
页面展示本机摘要、各次正确性检查和原始耗时，null 正确性保持未知。
相关检查：`python3 -m pytest -q unittests/test_campaign_diagnostics.py unittests/test_campaign_monitor.py unittests/test_campaign_exports.py`
与 `node --test webUI/campaign_view.test.cjs`。

页面分别显示远端状态更新时间、最近成功通信时间和本机同步尝试时间；SSH 或文件读取失败
不会把旧记录当作新进度。范围外对象单列；blocked 和没有实测的对象保留在待完成清单。
仅从任务快照展示性能字段，“结果 / 技能”页也展示远端快照中的逐 workload 实测，同时保留本机记录与归档实测。

CPU 回归检查：

```bash
python3 -m pytest -q unittests/test_webui_workloads.py unittests/test_webui_results.py unittests/test_run_report.py
node --test webUI/results.test.cjs webUI/campaign_view.test.cjs webUI/workload_view.test.cjs
```

## 文件

| 文件 | 作用 |
|---|---|
| `workloads.py` / `workflow.py` / `workloads.js` / `workload_view.js` | CSV 计划、来源提取、逐 workload 操作和通用展示 |
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
