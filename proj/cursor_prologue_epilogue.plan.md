

name: testft 无锚点区调优 (prologue/epilogue DAG 重排)
overview: 让 Agent 能对不含 MFMA 锚点的区段(典型 prologue/epilogue, 也含主循环极少次执行的 shape)做「按依赖关系自由重排 + 精确 waitcnt 重算」, 并用一套对输入尺寸自适应的目标函数驱动(真机 TFLOPS 永远裁决, 静态代价模型仅作 GPU-less 预筛 + 噪声内平局打破; shape-aware est_share 指导选区)。设计见 proj/anchorless_region_scheduling.md。守住铁律: Agent 只导航, legal_window+Verifier+真机裁决。
todos:





id: p1-dag-observe
content: "Phase 1(最小闭环, 零新核心代码): agent/session.py observe 对无 MFMA 锚点的区自动从 slot 视图切到 DAG 视图——为区内每条指令导出 NodeView(iid/kind/pos/legal_window/preds+dist/succs+dist/is_fence), 数据全来自现成 DepGraph(preds/succs/dist/legal_window/fences)。Observation 增可选字段 dag(无锚点时填, 有锚点时 None), to_dict 可序列化。tools/agent_session.py observe 不变(已透传 region)。验收: observe --region epilogue 在真机 gemm seed 上返回非空 dag(140 指令)、anchors 为空、JSON 可解析; 且 Agent 用已有 listsched/movedsl spec(带 region=epilogue) 经 build_candidate->recompute_cfg->Verifier 产出合法 kernel(单测断言 ok=True)。单测: tests/test_session.py 加 TestDagObserve(无锚点区出 dag/有锚点区 dag=None/window 合法)。"
status: pending



id: p1-smoke-realshape
content: "Phase 1 验证: 在一个主循环极少次执行的小 trip shape 上(如 k 取小值使循环跑 1~2 次, 复用 testcase/ 的 gemm 但调 --k/--loop), 用 tools/agent_session.py 对 epilogue/prologue 跑 listsched 候选, 确认(a)非 loop 区重排经 recompute_cfg 后真机数值正确(check_correctness 通过), (b)小 trip 下尾段改动能在整核 TFLOPS 上分辨出来。无 GPU 时退化为: build_candidate 产物过 Verifier + 与 baseline diff 非空。记录到 proj/steps/M9-anchorless-region.md(新建, 仿 M5 文风, 含真机/或离线数据)。"
status: pending



id: p2-cost-model
content: "Phase 2a: 新增 reorder/cost.py(架构无关): RegionCost(issue_cycles/wait_stalls/n_waits/est_cycles) + estimate(program, target, region)->RegionCost, 复用 waitcnt scoreboard 模拟(跑在 Target.counter_model + 延迟边上, 无需 GPU): 沿区内当前顺序走一遍, issue_cycles=Σ各 kind 粗略发射周期, wait_stalls=每条 s_waitcnt 实际 drain 深度之和, est_cycles=issue+等待空泡累加。单测 tests/test_cost.py: 同区两种顺序(聚拢 vs 打散同类访存)的 est_cycles 有区分度; 退化区(单指令/全 fence)不报错。"
status: pending



id: p2-waitcnt-preview
content: "Phase 2b: agent/session.py observe 增 WaitcntPreview(waits:[{at_iid,counter,target}] + cost:RegionCost)——从 waitcnt 模拟器只读导出当前顺序的重算等待 + RegionCost; NodeView 增 bumps_counter(vmcnt/lgkmcnt/vscnt/expcnt, 来自 Target.counter_model 的每指令增量规则)与 waits_on。Observation.to_dict 带 waitcnt_preview。单测: epilogue observe 的 waitcnt_preview.waits 非空且 counter 名合法; ds_read 节点 bumps_counter=lgkmcnt。"
status: pending



id: p2-est-share
content: "Phase 2c: reorder/regions.py 增 est_share 计算(或在 session 层组装): est_share(region)=trip_count*est_cycles, loop 区 trip_count 来自 harness --loop/--k 或运行时探测, prologue/epilogue=1, 不执行区=0。region_summaries/observe 的 regions[] 每项加 est_share。单测: 大 trip 下 loop est_share 占比最高; 把 trip_count 调到 1 时尾段 est_share 反超。"
status: pending



id: p2-adaptive-verdict
content: "Phase 2d: search/driver.py + agent/session.py 落地 shape 自适应裁决(§3.2): build_candidate 前用 cost.estimate 预筛(est_cycles 明显变差的候选可跳过真机, 可配开关); commit_and_eval/search 的接受判定: ΔTFLOPS 超 noise_margin -> 真机说了算(现状不变); 落在噪声带内 -> 用 est_cycles 当次级排序键打破平局; 永不因代价模型翻盘已测出的真机回归/不正确。单测(注入 FakeEval 制造噪声带内场景): 噪声内时 est_cycles 更优者被选; 超噪声时 TFLOPS 优先, 代价模型无权翻盘。"
status: pending



id: p3-propose-orders
content: "Phase 3a: reorder/editor.py 新增 propose_orders(candidates: List[List[int]], strict=False)->List[OrderReport](propose_layouts 的无锚点版): 每个候选是(部分/完整)iid 线性序意图, 按序贪心落位, 每条过 legal_window+fence, 落不进记 SkipReason+window+bound_iid, 未提及指令保持相对序填空, try/revert 不污染, 返回 placed/skipped/legal + RegionCost。OrderReport dataclass。AgentSession 增 propose_orders 透传; tools/agent_session.py 增子命令或 --order 参数。单测: 合法全序全 placed; 违反 RAW/FENCE 的序被正确 skip 带原因码; 调用后 order 不变。"
status: pending



id: p3-agent-wiring
content: "Phase 3b: SDK/CLI 按区切换 Agent 词汇: tools/sdk/tune.mjs PROMPT 在选中无锚点区时改讲『读 DAG + waitcnt_preview, 用 weights/move-DSL/propose_orders 重排, 目标降区内 est_cycles 且不让整核数值错/变慢』, 选中 loop 区仍讲 slot/anchor 填充; observe 输出已自带 regions[].est_share, prompt 指示『先看 est_share 占比大的区再决定调哪块』。M7 agent/knowledge.py scope 加 region_kind(prologue/loop/epilogue), induce/seed 按其分组。冒烟: pin epilogue 与 pin loop 两种 prompt 渲染正确; node --check 通过。"
status: pending



id: p4-span-coopt
content: "Phase 4(可选, 跨尾段协同): 用现成 span_editor 暴露 prologue<->epilogue(同执行次数非 loop 区)跨界重排——AgentSession 增 region='span:prologue+epilogue' 之类选择, build_candidate 支持 span。单测: span 内跨界合法移动被允许、跨 loop 体边界被 fence 挡住。视前几期收益决定是否做。"
status: pending



id: m9-docs-tests
content: "收尾: 全套 pytest 通过; 更新 proj/steps/M9-anchorless-region.md(真机/离线数据 + 结论); 在主 plan(testft_instruction_reorder_engine_24c474c7) 追加 M9 里程碑条目; proj/anchorless_region_scheduling.md 标注各 Phase 完成状态; tools/sdk/README.md 补无锚点区用法。"
status: pending
isProject: false



背景与设计来源

完整设计见 [anchorless_region_scheduling.md](anchorless_region_scheduling.md)（M9 设计草案）。
本 plan 是其「Phase 1–4 落地分期」的可执行拆解。承接：





proj/core_loop_scheduler_design.md：三区(prologue/loop/epilogue)独立重排、指令不跨界。



proj/reorder_engine_api.md：score-based waitcnt 重算。



proj/if/ai_interface.md §3.4.2c–d：分区调优 / SDK 驱动决策面（M8 已落地）。

关键设计决策（评审要点）





引擎已能做：RegionEditor 不依赖 MFMA；list_scheduler 通用；recompute_cfg 已处理非 loop 区

waitcnt（M8）；build_candidate 已支持 region。缺的是 Agent 观测/动作词汇 + 目标函数。



目标函数 shape 自适应（核心）：真机 TFLOPS + 正确性永远裁决（对所有区一视同仁）；静态代价模型

仅作 GPU-less 预筛 + 噪声内平局打破，永不翻盘已测出的真机回归。regime 判定是经验/噪声相对的
 （ΔTFLOPS 是否超 noise_margin），不是按区类型写死。小 trip shape 下尾段直接由真机反映；大 trip 下
 代价模型补梯度。



shape-aware 选区：est_share = trip_count * est_cycles 放进 observe 的 regions[]，驱动 Agent

按当前尺寸把预算投到主导耗时的区。



铁律不变：Agent 只导航；legal_window + Verifier + 真机 裁决；错误决策只浪费预算，绝不产坏 kernel。

执行顺序

Phase 1（p1-*）零新核心代码、先打通无锚点区闭环并真机/离线验证 → Phase 2（p2-*）补 shape 自适应
目标函数（代价模型 + waitcnt 预览 + est_share + 自适应裁决）→ Phase 3（p3-*）补表达力（propose_orders）
与 Agent 词汇切换 → Phase 4（p4-*，可选）跨尾段协同 → m9-docs-tests 收尾固化。

每个 Phase 自带单测；涉及真机的步骤无 GPU 时退化为「过 Verifier + 与 baseline diff 非空」并在
proj/steps/M9-anchorless-region.md 标注验证条件。
