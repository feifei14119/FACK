

name: testft 大 DAG（入循环 prologue 段）指令级微调
overview: 解决对入循环阶段(anchor-less prologue, 实测 426 个 DAG 节点)做指令级调优时的两个痛点——(1) propose --order 传全量线性序触发 O(n²) 塌方(单次 propose 卡 8 分钟, 见 proj/brainstorm/anchorless_fullorder_propose_perf.md); (2) agent 面对 426 个全量 NodeView 上下文爆炸、缺聚焦、缺高层落点(见 proj/brainstorm/large_dag_finetune.md)。解法不是让 agent 去啃全量 DAG, 而是层层缩小它面对的空间: est_share 闸门 -> fence 分段定位最贵小段 -> 段内引擎自动出 list-sched 种子候选 + agent 只在可调子集上高层微调; 同时把 propose_orders 复杂度降到 O(n) 并加长度护栏。守住铁律: 引擎裁决/合法性零改动, observe 只增只读字段, agent 仍只发结构化意图。
todos:




id: p0-prompt-guard
content: "Phase 0(止血, 极低引擎改动): (a) tools/sdk/tune.mjs 的 anchor-less 段(§244-251)加硬规则『对 anchor-less 区只把要移动的少量 iid(典型 2~15 个)列进 --order, 未列出的自动保持相对序填空; 禁止构造覆盖整段区域的全量 order——会让 propose 极慢』。(b) agent/session.py::propose_orders(或 editor.propose_orders 入口)对 len(intent) 设阈值(默认 64), 超限秒级拒绝并回结构化提示 {error:'order too long, use partial order (<=N iids)', n:len, limit:N}, 而非干等。阈值可配(AgentSession 参数/CLI flag)。单测 tests/test_editor.py: 超长 intent 秒级返回拒绝且 order 不变; 边界值(=N 通过, N+1 拒绝)。"
status: completed




id: p1-tunable-subset
content: "Phase 1a(裁剪, 纯 observe 层): agent/session.py::observe 的无锚点 DAG 分支为返回增加 tunable:[iid,...] 子集。判据 = movable==true 且 legal_window 宽度(hi-lo)>阈值(默认>1) 且 (在关键路径 top-K 上 或 bumps_counter∈{vm,lgkm})。全量 dag 仍保留(按需展开), 默认引导 agent 只对 tunable 操作。关键路径复用 search/list_scheduler._critical_path(g, ed.order)。Observation 增字段 tunable, to_dict 带上。单测 tests/test_session.py: 426 级/合成大 DAG 的 tunable 远小于 dag; 紧链(window 宽度 1)不入 tunable; vmem_load 入 tunable。"
status: completed




id: p1-compact-view
content: "Phase 1b(紧凑视图, 上下文压缩): tools/agent_session.py observe 增 --compact 开关(默认关, 保持向后兼容)。开启时 dag 只吐紧凑 NodeView(iid/kind/pos/window/movable/bumps_counter), 省略 preds/succs/waits_on 等重字段; 全量 dag 落到 out_store 下 <kernel>_<region>_dag.jsonl 供按需读取。session 层加 observe(compact=False) 参数或在 to_dict 时按 flag 裁字段。单测: compact 模式 dag 节点无 preds/succs 字段且 jsonl 落盘; 非 compact 行为不变。"
status: completed




id: p2-fence-segments
content: "Phase 2a(fence 分段聚焦, 复用 _segments): observe 无锚点分支新增 segments:[{seg_id, iids:[...], est_cycles}]。切分复用 list_scheduler._segments(ed.order, ed._fences)(fence 单例段跳过)。段级 est_cycles: 在 reorder/cost.py 加轻量入口 estimate_iids(program, target, iids)(或对段内子序列跑 scoreboard 估), 复用现有 cost 基础设施。agent 只挑 est_cycles 最大的段做 order, 段内规模骤降。Observation 增 segments。单测 tests/test_session.py + tests/test_cost.py: 分段并集=区内可动指令; 段级 est_cycles 有区分度; 全 fence 区 segments 合理退化。"
status: completed




id: p2-critical-focus
content: "Phase 2b(关键路径聚焦, 复用 _critical_path): observe 无锚点分支新增 critical:{top_k:[iid,...], dominant_wait:{at_iid,counter,target}}。top_k 复用 _critical_path 取路径最长的前 K(默认 8)个可动节点; dominant_wait 从 waitcnt_preview.waits 里取当前 drain 深度最大/最靠前的那条(哪个 waitcnt 在等、由哪些 load 喂)。给 agent『瓶颈在哪、动哪几个最有用』而非盲找。Observation 增 critical。单测: 合成链式 DAG 的 top_k 落在真实关键路径上; 有 wait 的区 dominant_wait 非空。"
status: completed




id: p3-suggest-orders
content: "Phase 3(引擎自动种子候选, 最大杠杆): agent/session.py 新增 suggest_orders(n=3)->[{order, weights, est_cycles}]: 用 2~3 组 Weights 预设(critical_path 偏重 / latency 偏重 / load_hoist 偏重)跑 search/list_scheduler.schedule(graph, order0, fences, weights, kind_of), 每个产出 order 用 editor._materialized_region_cost() 或 cost.estimate 出 est_cycles, 按 est_cycles 排序返回。agent 从『构造 426 维序列』降级为『3 个候选选一 + 微调几个 iid』。tools/agent_session.py 增 suggest 子命令; tune.mjs anchor-less 段引导『先 suggest 拿种子, 再在 tunable 上用部分 --order 微调』。单测 tests/test_session.py/test_search.py: suggest_orders 每个 order 合法(is_order_legal)且带 est_cycles; 不同权重给出不同序。"
status: completed




id: p4-propose-perf
content: "Phase 4(治本, propose_orders O(n²)->O(n)): reorder/editor.py::propose_orders(约 line 604)去掉双 self.order.index() 线性查找——维护 iid->当前位置 dict 增量更新, 每步 O(1); 评估 move_after 底层 list 搬移成本, 若仍是瓶颈换更适合频繁移动的结构(位置键/链表+位次缓存)。目标: 全量 order(n=426)也亚秒级返回, 使部分/全量都可接受。行为(placed/skipped/legal/cost)与现状完全一致。配套单测 tests/test_editor.py: 大 n 计时上界(如 <1s)断言 + 与旧实现结果逐字段等价(回归)。"
status: completed




id: p4-cluster-op
content: "Phase 4(可选, 降维/高层动作): (a) search/movedsl.py 增 cluster([handles]) 高层动作, 把一组指令聚簇成整体移动; (b) 探索把『地址准备紧链 + 它喂的 load』识别为超级节点按簇重排(426->几十)。视前几期收益与真实调优频率决定是否做。单测: cluster 合法聚簇被应用、拆散紧链的非法聚簇被拒。"
status: deferred




id: dag-docs-tests
content: "收尾: 全套 pytest 通过(298 passed); 在 proj/brainstorm/large_dag_finetune.md 与 anchorless_fullorder_propose_perf.md 顶部标注对应 Phase 落地状态; tools/sdk/tune.mjs 提示词补大 DAG 区的 suggest/tunable/segments/critical/部分 order 用法。"
status: completed
isProject: false




背景与设计来源

命题来自两篇 brainstorm:
- proj/brainstorm/anchorless_fullorder_propose_perf.md: 全量 order 触发 propose O(n²) 塌方(性能/易用性侧)。
- proj/brainstorm/large_dag_finetune.md: 大 DAG(426 节点)难高效微调(更本质的搜索/推理空间太大侧)。

复用引擎已有能力(几乎不改裁决):
- search/list_scheduler.py: _segments(fence 分段) / _critical_path(关键路径) / schedule(加权贪心种子)。
- agent/session.py: observe / NodeView / est_share(已算)。
- reorder/depgraph.py: legal_window / preds / succs / dist。
- reorder/editor.py: propose_orders(全序意图, 待降复杂度) / _materialized_region_cost。

关键设计决策

- 根因是「缺裁剪 + 缺聚焦 + 缺高层落点」三者叠加, 「DAG 大」只是表象。解法层层缩小 agent 面对的空间, 而非让它啃全量。
- 两级分层调优: Level 0 est_share 闸门(prologue 占比够大才深入, 已有 est_share) -> Level 1 fence 分段定位最贵小段(_segments) -> Level 2 段内引擎自动出 list-sched 种子候选(schedule), agent 只在 tunable 子集上用高层动作/部分 order 微调。
- 铁律不变: 引擎裁决/合法性零改动; observe 只增只读字段; agent 只发结构化意图(部分 order / 选种子 / 高层动作), 不写 ASM、不写 waitcnt; 真机 TFLOPS + 正确性唯一裁决。

执行顺序

Phase 0(止血: 提示词 + 长度护栏, 立刻消塌方) -> Phase 1(裁剪 tunable + 紧凑视图, 426->几十, 纯 observe) -> Phase 2(fence 分段 + 关键路径聚焦, 复用 _segments/_critical_path) -> Phase 3(引擎自动种子候选 suggest_orders, 最大杠杆) -> Phase 4(propose_orders 降 O(n) 治本; 可选 cluster 降维) -> 收尾固化。每期自带单测; 涉及真机步骤无 GPU 时退化为「过 Verifier / is_order_legal + 计时上界」。
