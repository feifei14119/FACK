# M9：无锚点区调优（prologue / epilogue 的 DAG 重排）

> 目标：让 Agent 能对**不含 MFMA 锚点**的区段做「按依赖关系自由重排 + 精确 waitcnt」，
> 并用一套**对输入尺寸自适应**的目标函数驱动（真机 TFLOPS 永远裁决，静态代价模型仅作
> GPU-less 预筛 + 噪声内平局打破）。设计见 `proj/anchorless_region_scheduling.md`。
> 守住铁律：Agent 只导航，`legal_window + Verifier + 真机` 裁决。

---

## Phase 1（最小闭环，零新核心代码）——已完成

### 做了什么

1. **`agent/session.py` `observe` 增 DAG 视图**：当所选区**无 MFMA 锚点**时（`anchors == []`），
   `Observation.dag` 自动填充该区每条指令的 `NodeView`：
   `iid / kind / pos / legal_window / movable / is_fence / preds[(iid,dist)] / succs[(iid,dist)]`。
   数据全来自现成 `DepGraph`（`preds/succs/dist/legal_window/fences`），窗口口径与既有 fillers 视图一致
   （waitcnt 作 fence 的保守窗口；实际移动合法性仍由 propose/commit 校验）。
   loop 区（有 MFMA）`dag = None`，**slot/filler 视图与行为完全不变**（向后兼容）。
2. **动作复用既有引擎**：`build_candidate(seed, {"kind":"listsched"/"compact"/"movedsl", "region":"epilogue"})`
   配合 M8 的「非 loop 区自动走 `recompute_cfg`」，**无需新核心代码**即可对 prologue/epilogue 重排 +
   精确重算 + Verifier。

### 验证（本环境无 GPU → 离线：Verifier + 与 baseline 的实质差异；真机待后续）

- **真实 gemm seed `observe --region epilogue`**：`anchors=0 / slots=0 / dag=140 节点`，JSON 可序列化；
  样例节点 `{iid:893, kind:valu, pos:3, legal_window:[2,3], succs:[[894,1],[1002,1]]}`。
- **离线重排合法性**（`build_candidate` listsched，两组 Weights）：

  | 区 | listsched | Verifier ok | 相对 baseline 行变更 |
  |---|---|---|---|
  | prologue | ✅ | True | 1124 |
  | epilogue | ✅ | True | 91 |

  → 非 loop 区重排经 `recompute_cfg` 后过 Verifier，且确有改动（非 no-op）。
- **单测**（`tests/test_session.py::TestDagObserve`）：无锚点区出 `dag` / loop 区 `dag=None` /
  DAG 可 JSON 序列化 / prologue+epilogue listsched 构建合法。全套 **207 passed**。

---

## 首个真机数据点（MI3xx gfx942, k=256, 2026-06-18）

在**主循环极少次执行的小 shape**（`gemm.exe` 原生 `k=128*2=256`，循环只跑约 2 个 K-block，尾段占整核
耗时显著）上，用 SDK agent（`tune_prologue_epilogue.sh --k 256`，每区 50 轮上限）分别调 prologue /
epilogue，真机评测（每次 commit 都进 `agent/store/experiments.log`）：

| 区 | eval 次数 | correct | 正向/正确 | 最优 ΔTFLOPS | 最优 tflops vs 基线 | est_cycles |
|---|---|---|---|---|---|---|
| prologue | 32 | 31/32 | 21/31 | **+1.05%** | 48.19 vs 47.69 | 462 → **450** |
| epilogue | 29 | 29/29 | 15/29 | **+0.31%** | 47.85 vs 47.71 | 154（未变）|

- **prologue**：最优解把仅依赖 `iid 11` 的 16 条并行 `buffer_load`（iid 12–27）的发射顺序重排（28 之后
  保持原序），`est_cycles` 462→450，多次复测 ~48.2 稳定复现、超过噪声。
- **epilogue**：最优解是把相邻两条 `ds_read`（iid 940/939）对调（基线序上 index 49 的相邻交换），
  +0.31%，`est_cycles` 未变——属**噪声带内靠真机实测拉开**，多次复测 `accepted` 会摇摆。

**结论（验证设计假设）**：小 K 下两个尾段都能被**整核真机 TFLOPS 直接量出正向收益**（prologue ~1%、
epilogue ~0.3%，幅度有限但可分辨），印证了 §3.2「regime 由 trip count 决定、小 trip 尾段直接由真机
反映」而非按区类型写死。全程**未手改任何 `.s`**，重排经 `recompute_cfg` + Verifier，`correct` 恒真。

**离线（GPU-less）合法性**佐证（`build_candidate` listsched，两组 Weights）：prologue/epilogue 均
Verifier `ok=True` 且相对 baseline 有实质行变更（prologue 1124 / epilogue 91）。单测
`tests/test_session.py::TestDagObserve` + 全套 **223 passed**。

> 工具修复（本次真机跑出来的）：`tools/sdk/tune.mjs` 两处——(1) 运行结束 `agent[Symbol.asyncDispose]()`
> 会无限阻塞导致 node 不退出、多区 shell 循环卡死 → 改为 dispose 与 8s 超时竞速 + 强制 `process.exit`；
> (2) 结果记录器只认 `--layout` → 改为递归扫描事件里的 `eval` 命令（含 `--order`）与 verdict JSON、去重
> 逐行写 `.md`/`.jsonl`。注意：当 agent 把多次 `eval` 包进自写脚本批量跑时，单条 verdict 不逐个流出，
> `.md` 仅记到「干净单次 eval」；**逐次权威数据始终在 `experiments.log`**。

---

## Phase 2（shape 自适应目标）——已完成

- **`reorder/cost.py`**：`RegionCost(issue_cycles/wait_stalls/n_waits/est_cycles)` + `estimate(program,
  target, region)`，复用 waitcnt scoreboard 模拟、无需 GPU。`est_cycles = issue + wait_stalls +
  每条 wait 惩罚`（批量一次 wait 覆盖多条 优于 多次小 wait）。单测 `tests/test_cost.py`（批量 vs 交错有
  区分度、退化区不崩、可序列化）。
- **`observe` 增 `waitcnt_preview`**：当前顺序的 `waits[{at_iid,counter,target}]` + `RegionCost`；DAG 节点
  增 `bumps_counter`(vm/lgkm/exp/vs) 与 `waits_on`。
- **`regions[]` 增 `est_cycles`/`trip_count`/`est_share`**：`est_share = trip_count * est_cycles`，
  `loop_trips` 由调用方注入（未知则 `est_share=None`，诚实回退）；单测验证 trip 越小尾段相对占比越高。
- **shape 自适应裁决 `AgentSession._verdict`**（§3.2）：真机优先——ΔTFLOPS 超 `noise_margin` 真机说了算；
  落噪声带内才用 `est_cycles` 打破平局；**永不翻盘已测出的真机回归/不正确**。`CommitResult` 增
  `est_cycles`/`baseline_est_cycles`。单测覆盖四个分支。

## Phase 3（表达力 + Agent 词汇）——已完成

- **`editor.propose_orders(candidates)` + `OrderReport`**：`propose_layouts` 的无锚点版，接受(部分/完整)
  iid 线性序意图，按序贪心落位、过 `legal_window`+fence、try/revert 不污染，回 placed/skipped(原因码+窗口+
  bound_iid)/legal + `RegionCost`。`build_candidate` 增 `{"kind":"order","order":[...]}` 提交路径；
  `AgentSession.propose_orders` / `commit_and_eval_order`；CLI `--order '[...]'`（propose/eval 通用）。
  真机 seed epilogue CLI 冒烟：`legal=True placed=8 cost.est_cycles=156`。
- **SDK/CLI 按区词汇切换**：`tune.mjs` PROMPT 讲两套词汇（anchored→`--layout` 填 MFMA 间隙；
  anchor-less→`--order` 按依赖重排、目标降 `est_cycles`），并指示「优先 `est_share` 占比大的区」。
- **M7 知识 scope 加 `region`**：`induce_skills` 分组键 + `scope` 含 `region`；`seed_search_plan` 的 context
  并入 `region`。旧 13 条技能无 region 约束 → 仍是通配，向后兼容。

全套 **223 passed**。

## Phase 4（可选，跨尾段协同）——暂缓

`span_editor` 暴露 prologue↔epilogue 跨界重排，视前三期真机收益再定。

执行拆解见 plan `testft_anchorless_region_tuning_9b2f1a3c`。
