设计目标与边界

把 testft/proj 四篇设计落成一个完全独立且架构可插拔的可运行 Python 工程。核心: 调用方(AI/搜索)只发"对稳定指令 ID 的结构化操作", 引擎负责合法性校验 + 修补 pass 流水线(含 waitcnt 重算) + 无损回写, 真机测量由 testft 自带、可插拔的评测器完成。

关键设计决策(供评审):





完全独立, 零外部工程依赖: testft 不 import/不引用 feifeiAVO，也不复用 amdgpu-asm-tool。所有代码自包含于 testft/ 内。



架构无关核心 + 独立 ISA 层(本轮新增重点①): testft/reorder/ 是架构无关的引擎框架(词法/解析/CFG/依赖图框架/重排/waitcnt 框架/pass 框架/校验/回写)；一切与具体硬件指令集相关的知识(opcode 分类、寄存器模型、分支判定、计数器模型、建边规则、修补 pass、不变式)统统收敛到独立的 testft/isa/ 层，由 Target 接口暴露。加新架构 = 新增一个 isa/<arch>/ 实现，核心零改动。 首个实现是 isa/gfx942/。



修补能力 = 可扩展的 FixupPass 流水线(本轮新增重点②): 不存在写死的 NopFixer。改为 reorder/passes.py 定义 FixupPass 协议 + PassPipeline，各架构通过 Target.fixup_pipeline() 提供一组有序 pass。gfx942 的流水线 = [WaitcntRecomputePass, ForcedNopPass, ...]；其他架构可加 RegDependencyPass(插依赖消解指令，如 s_delay_alu)、RegBankSwitchPass(寄存器组切换)、ClauseGroupPass(s_clause) 等。连 waitcnt 重算本身也是流水线里的一个 pass——因为别的架构可能不用 counter，而用 delay/clause 等机制。



ISA 以 amdgpu-asm-codebase 为参考(只读, 不作代码依赖): 硬件事实对照 amdgpu-asm-codebase/llvm-isa/gfx942(详见"ISA 参考映射")。



首要验收门: 无损往返(round-trip): 重排前 parse(s) -> emit() 必须逐字节等于原文件。解析器同时吃下 GEMM 风格(label_XXXX:/2 空格/裸寄存器)与 k_vadd 风格(.label:/Tab/.set 别名)。



保守优先 + legal-by-construction: 别名拿不准就连依赖边; 每个 move 先过 DepGraph.legal_window，越界即拒绝。



评测自带、可插拔、分阶段(本轮新增重点③): 编译合法性用 testft 自带的 harness/toolchain.py(直接调 ROCm llvm-mc/clang)；真机评测分三阶段顺序执行、前序失败即短路: (1) 正确性测试 → (2) 性能测试(读 kernel 执行时间 → TFLOPS) → (3) perf counter dump(把显卡硬件计数器 dump 到文件)。第 (3) 步产出的计数器文件由 analysis/ 读取分析, 产出瓶颈分类/优化方向, 反哺下一轮搜索/agent。Evaluator 协议定义这三阶段, 你后期的测试用例实现该协议(如何跑、参考结果、如何计时、如何 dump counter)。



冷启动初始优化(本轮新增重点④): 编辑接口除"移动单条指令"外, 增加一个高层算子 distribute_evenly——把某一类指令(如所有 ds_read)平均分配到第 N 到第 M 个 MFMA 指令的间隙中。对完全未经手调的 kernel 可一键做最初始的均匀重排。

计数器模型(gfx942 实现, 放进 isa 层而非硬编码核心)

抽象的 CounterModel(命名计数器集合 + 位宽 + 每指令增量规则)由 Target 提供；核心的 waitcnt 重算框架对它泛化。gfx942 实现(来自 ISA codebase §13，修正了原 reorder_engine_api.md 只建模 vm/lgkm 的不足):





4 个计数器: vmcnt(VMEM load + atomic-return) / lgkmcnt(LDS ds_* + SMEM s_load_* + s_sendmsg) / expcnt / vscnt(VMEM store, 与 vmcnt 分离, 用 s_waitcnt_vscnt)。



MFMA/SMFMAC 写回不进任何 mem counter, 靠硬件 scoreboard → 累加链只用 ACC/RAW 依赖边保序，不为 MFMA 插 s_waitcnt。



s_barrier ≠ memory fence; barrier count-locked 不变式照旧。



位宽上限 vm 0..63 / lgkm 0..15 / exp 0..7(重算后校验不越界)——这些都是 gfx942 的 CounterModel 常量，换架构即换实现。

目录结构 (testft/)

testft/
  proj/                     # 现有设计文档(只读参考)
  reorder/                  # 架构无关核心引擎(不含任何具体 ISA 常量)
    __init__.py
    model.py                # Instr, RegSet, Region, EdgeType, Kind(通用类别枚举)
    lexer.py                # 通用 GAS 词法(标签/指令/注释/.set); 寄存器前缀集由 Target 提供
    parser.py               # .s -> 结构, 无损保真; 分类/操作数建模委托给 Target
    regions.py              # CFG/回边/切 N 区; 分支判定来自 Target
    depgraph.py             # 通用依赖图框架 + legal_window; 建边规则来自 Target
    editor.py               # RegionEditor: anchors/fillers/set_gap_layout/move_*/swap/lock_bundle/distribute_evenly + Diff
    waitcnt.py              # 通用 score-based 前向重算框架, 跑在 Target 的 CounterModel 上(架构无关)
    passes.py               # FixupPass 协议 + PassPipeline + Diff(取代固定 NopFixer)
    verifier.py             # 通用校验 + 调 Target 提供的不变式检查
    emitter.py              # 无损回写, 仅改顺序与被 pass 修改的行
  isa/                      # 硬件指令集抽象层(可扩展到其他架构)
    __init__.py
    target.py               # Target 抽象接口(架构契约, 见下)
    counters.py             # CounterModel 抽象基类(命名计数器+位宽+增量规则)
    registry.py             # 名称 -> Target 查找("gfx942" -> Gfx942Target), 选架构入口
    gfx942/
      __init__.py
      target.py             # Gfx942Target(Target): 组装下列各部件
      operands.py           # s/v/a/m0/vcc/exec/scc/null 解析 -> RegSet, .set 别名展开
      classify.py           # opcode -> Kind / WaitType; is_lds_load; 分支判定; m0 配对规则
      counters.py           # vm/lgkm/exp/vs 的 CounterModel(位宽 63/15/7/63, store->vs, MFMA 不计数)
      edges.py              # 建边规则: ACC 链 / m0 Bundle / MEM 保守别名 / FENCE
      passes.py             # gfx942 fixup 流水线: WaitcntRecomputePass, ForcedNopPass (+ 预留扩展位)
  search/                   # 搜索/策略层(后续里程碑)
    movedsl.py              # 解析/应用 move-DSL JSON (机制 B)
    list_scheduler.py       # 可调权重 list scheduler (机制 A)
    anneal.py               # 退火/MCMC 细粒度精修 (机制 C, 可选)
  harness/                  # testft 自带, 不依赖任何外部工程
    toolchain.py            # 调 llvm-mc/clang 把 .s -> .o/.co, 仅做编译合法性检查
    evaluator.py            # Evaluator 协议(三阶段: correctness/perf/counter-dump) + 编译-only 默认实现
  analysis/                 # perf counter 文件解析 + 瓶颈分类 -> 优化方向(反哺搜索/agent)
    perf.py                 # 读 counter dump 文件 -> 计数器字典(按 Target.perf_counter_schema 解读)
    bottleneck.py           # 计数器 -> 瓶颈分类(compute/memory/lds/latency/...) + 方向 hints
  agent/                    # 元层知识/记忆 + LLM 决策面
    knowledge.py            # M7: Skill schema + 持久化 + seed_search_plan/induce_skills
    tuner.py                # M7: before->during->after 闭环
    session.py              # M8: AgentSession(observe/propose/commit_and_eval) LLM 决策面
    store/                  # skills/*.json + experiments.log(JSONL, 决策可追溯)
  tools/                    # 命令行入口
    agent_session.py        # M8: 决策面 CLI(observe|propose|eval, 打印 JSON; 含 --region)
    search_loop.py          # M6c: 真机搜索入口
    validate_direction.py   # M6b: direction 信号真机去风险
    sdk/                    # M8: SDK 驱动的程序化 Cursor agent
      tune.mjs              # @cursor/sdk 起本地 agent 跑 observe->propose->eval(--region/--transcript/--results)
      README.md             # 用法 + 分区表 + 命令参数 + 共享机 key 安全
      cursor.config.json    # API key/model(0600, gitignore)
  tests/
    fixtures/               # 自带最小 .s 样例(两种风格各一份), testft 自有
    test_roundtrip.py / test_operands.py / test_regions.py
    test_depgraph.py / test_waitcnt.py / test_passes.py / test_reorder_e2e.py
  README.md
  pyproject.toml            # 独立打包, 仅标准库 + pytest
  tune_quick.sh             # M8: 2轮/不存提示词/存结果的 tune.mjs 快捷封装(默认主循环区)

Target 契约(架构可插拔的核心接口)

# isa/target.py  (核心引擎只认这个接口, 不认 gfx942)
class Target(Protocol):
    name: str
    # 词法/解析
    def register_prefixes(self) -> set[str]: ...            # {"s","v","a"} + 特殊名
    def parse_operands(self, opcode, operand_strs) -> tuple[RegSet, RegSet]:  ...  # (defs, uses)
    def classify(self, opcode, operands) -> Kind: ...
    # 控制流
    def is_branch(self, instr) -> bool: ...
    def is_conditional_branch(self, instr) -> bool: ...
    def branch_target(self, instr) -> str | None: ...
    # 依赖建边(供通用 DepGraph 调用)
    def build_edges(self, region, graph) -> None: ...        # ACC/M0/MEM/FENCE 等架构特有边
    def bundles(self, region) -> list[Bundle]: ...           # 如 [s_add m0, buffer_load lds]
    # 计数器 / 修补
    def counter_model(self) -> CounterModel: ...             # None 表示该架构不用 counter
    def fixup_pipeline(self) -> list[FixupPass]: ...         # 有序 pass; gfx942=[Waitcnt, ForcedNop]
    # perf counter 解读(硬件计数器名 -> 语义, 供 analysis/ 分析瓶颈)
    def perf_counter_schema(self) -> dict[str, "CounterMeaning"]: ...
    # 校验不变式
    def invariants(self) -> list[Invariant]: ...             # 如 barrier count-locked

FixupPass 流水线(取代固定 NopFixer)

# reorder/passes.py
class FixupPass(Protocol):
    name: str
    def run(self, program, target, depgraph) -> Diff: ...    # 就地修补, 返回可回滚 Diff

class PassPipeline:
    def __init__(self, passes: list[FixupPass]): ...
    def run(self, program, target, depgraph) -> list[Diff]:  # 依次执行 target.fixup_pipeline()
        ...





gfx942 当前 pass: WaitcntRecomputePass(用 reorder/waitcnt.py 的通用引擎 + gfx942 CounterModel)、ForcedNopPass(MFMA 强制 nop, 不动 barrier 数量)。



其他架构可注册: RegDependencyPass(插依赖消解指令)、RegBankSwitchPass(寄存器组切换)、ClauseGroupPass(s_clause)、DelayAluPass(s_delay_alu) 等——核心引擎无需改动, 只在对应 isa/<arch>/passes.py 增加 pass 并挂进 fixup_pipeline()。

编辑接口(RegionEditor 算子)





低层 move 原语(细粒度, 已有): move_before/move_after/swap(iid, anchor)、lock_bundle(ids)——移动单条指令/Bundle, 每步过 legal_window。



高层 gap-layout(逐间隙异构分配, 已有): set_gap_layout(region, anchors, layout)——layout[g] 指定第 g 个 MFMA 间隙放哪些填充物。



高层 distribute_evenly(本轮新增): 把某类指令平均铺到一段 MFMA 锚点间隙, 用于冷启动 kernel 的初始优化。

def distribute_evenly(self, region: str, kind: Kind,
                      anchor_lo: int, anchor_hi: int,
                      fillers: list[str] | None = None) -> Diff:
    """把 region 内某类填充物(默认该 region 全部该 kind, 或显式给 fillers)
       平均分配到第 anchor_lo..anchor_hi 个 MFMA 锚点之间的间隙中。
       内部换算为 set_gap_layout(尽量等分, 余数靠前/靠后可配), 逐项过 legal_window;
       非法项跳过或报错(可配 strict)。返回可回滚 Diff。
       场景: 完全未手调的 kernel, 一键把 ds_read 均匀插进 MFMA 流, 做最初始重排。"""



关键: distribute_evenly 只是 set_gap_layout 的一个「等分」特例; 后者本身已支持逐 slot 异构计数(slot0 放 2 条、slot1 放 0 条、slot2 放 2 条…), 是下节 AI 精细化调整的落地原语。

AI 指导逐 slot 精细布局(结构化候选提交 + 原因码反馈, M6)

动机: AI 不只做 tile/pipeline 级决策, 更要能对值令做极致精细化的逐 slot 调整——例如 core loop 有 5 条 MFMA + 4 条访存值令, 固定搜索给出「每个间隙各 1 条」的均匀基线后, AI 依据硬件知识库判断「slot0 之后这条 MFMA 占用周期长、issue/VGPR 带宽有富余, 可吞 2 条 load」, 于是想试 {slot0:2, slot1:1, slot2:1} 或 {slot0:2, slot1:0, slot2:2} 这类非均匀布局。底层 set_gap_layout 今已能表达并真机验证; 缺的是一层让 AI 批量提交意图、并拿到结构化失败原因以迭代的封装。





分工: AI 出「逐 slot 布局意图」(来自 direction + 知识库的语义判断); 固定逻辑负责合法落位(每条过 legal_window) + waitcnt 重算 + 真机度量, 并对放不进去的值令回报原因码。AI 与固定搜索复用同一个 set_gap_layout 原语, 因此天然互补——固定搜索探「均匀/移项」可枚举空间, AI 接管「非均匀/靠语义」的点位, 互不覆盖。



结构化候选提交 RegionEditor.propose_layouts(anchors, candidates) -> [LayoutReport]:





candidates: 一批意图, 每个为 {slot_index: [filler_iid, ...]}(给定 slot 放哪些值令、按什么顺序)。



引擎逐候选试摆 → 校验 → 回报(不污染彼此, 内部 try/revert), 返回每候选一份 LayoutReport。



便捷封装: 内部对每个 slot 依序调 move_after(已存在), 仅新增批量编排 + 报告聚合。



原因码反馈 LayoutReport:

  @dataclass
  class Placement:        # 单条 filler 的落位结果
      iid: int
      slot: int
      ok: bool
      reason: "SkipReason | None"     # 失败原因码
      window: tuple[int, int]         # 合法窗口 [lo, hi]
      bound_iid: int | None           # 卡住它的那条指令(pred/succ/fence)
  @dataclass
  class LayoutReport:
      layout: dict[int, list[int]]
      placed: list[Placement]         # ok=True
      skipped: list[Placement]        # ok=False, 带 reason
      legal: bool                     # 全部落位后整体合法性
  class SkipReason(Enum):
      LDS_ROUNDTRIP   # ds_read 要等填它那条 band 的 buffer...lds
      MFMA_LATENCY    # 违反 MFMA 写->读最小间距窗口
      FENCE_BLOCKED   # 目标间隙与当前位置间有 barrier/exec 写/分支/waitcnt 栅栏
      RAW / WAR / WAW # 数据依赖
      M0_BUNDLE       # m0-bundle 整体性要求
      WINDOW_EMPTY    # 合法窗口塌缩(lo>hi)
      SLOT_OOR        # slot 序号 >= MFMA 锚点数
  






原因码由 _move_unit_to 失败路径分类得到: k<lo 看下界绑定者(pred 的 dist=MFMA_LATENCY / fence-left=FENCE_BLOCKED / RAW), k>hi 看上界绑定者(succ / fence-right)。



闭环: direction.bottleneck → AI 生成若干非均匀 candidates → propose_layouts 批量校验 → 选合法者 materialize + recompute_cfg + evaluate(with_counters) → 比较 TFLOPS/新 direction; 被 skip 的候选带原因码回流, AI 据此知道「哪条因什么约束放不进哪个 slot」, 调整下一版意图。M7 把「什么 direction/指令形态下哪种非均匀布局有效」沉淀进知识库。

数据流

flowchart LR
  A[".s 源文件"] --> B[lexer + parser]
  B --> C["Target.parse_operands -> RegSet"]
  C --> D["RegionSplitter: CFG 切 N 区 (Target 分支判定)"]
  D --> E["DepGraph (Target.build_edges)"]
  E --> F[RegionEditor 重排引擎]
  G["调用方: move-DSL / 权重 / 搜索"] --> F
  F --> P["FixupPass 流水线 = Target.fixup_pipeline()"]
  P --> I["Verifier (+ Target.invariants)"]
  I --> J[Emitter 无损回写 .cand.s]
  J --> K["harness.toolchain: llvm-mc/clang 编译合法性"]
  K --> E1["evaluator 阶段1: 正确性"]
  E1 -->|correct| E2["evaluator 阶段2: 性能(执行时间->TFLOPS)"]
  E1 -->|wrong| X["短路丢弃"]
  E2 --> E3["evaluator 阶段3: perf counter dump -> 文件"]
  E3 --> AN["analysis: 读 counter 文件 -> 瓶颈/方向 hints"]
  AN --> L["(correct, tflops, counters, direction)"]
  L --> G
  subgraph pipe [gfx942 fixup_pipeline 示例]
    P1[WaitcntRecomputePass] --> P2[ForcedNopPass] --> P3["...其他架构: RegDependency / RegBankSwitch"]
  end

ISA 参考映射(开发 isa/gfx942 时对照, 均为只读文档)





操作数/寄存器/修饰符(isa/gfx942/operands.py+核心 lexer.py) → gfx942/02-notation-operands-modifiers.md



计数器/s_waitcnt/s_barrier/s_nop(isa/gfx942/counters.py+passes.py) → gfx942/13-waitcnt-sync.md



MFMA/SMFMAC(ACC 边/强制 nop)(isa/gfx942/edges.py+passes.py) → gfx942/08-vop3p-mfma-smfmac.md



LDS ds_*/lgkmcnt(isa/gfx942/classify.py+edges.py) → gfx942/10-ds.md



buffer/buffer_load ... lds/m0 配对(isa/gfx942/edges.py) → gfx942/12-mubuf-mtbuf.md + gfx942/11-flat-memory.md



标量控制流 s_branch/s_cbranch_*(isa/gfx942/classify.py 分支判定) → gfx942/04-scalar-alu.md



AMDHSA 汇编格式/directives(核心 parser.py 无损保真) → hsa-elf/docs/19-assembly_kernel_format.md + hsa-elf/docs/18-amdhsa-kernel-directives.md



GAS 语法(注释/.set/标签)(核心 lexer.py) → gun-asm/GNU_Assembler_GAS_Standard.md



说明: amdgpu-asm-codebase 还含 gfx906/gfx11/gfx12 同结构文档, 印证 isa/ 抽象足以横向扩展到其他 AMD 架构。

里程碑 (对齐 core_loop_scheduler_design.md §10)





M0 脚手架 + 无损往返: 搭 reorder/ 核心骨架 + isa/ 抽象层空壳 + lexer/parser/emitter; 验收门 = 两种风格 fixtures 都能 parse->emit 逐字节还原。



M1 ISA 层 + 区域切分 + 只读 waitcnt 校验: 定 Target 契约 + 落 isa/gfx942(operands/classify/counters/registry) + regions.py(CFG/回边/N 区, 分支判定走 Target) + 只读 counter 校验(验证能正确读懂现有 waitcnt, 含 vscnt)。



M2 依赖图: depgraph.py 通用框架 + legal_window; 边规则(全部边类型 + m0 Bundle + MFMA 不计 counter)由 isa/gfx942/edges.py 提供。



M3 重排引擎(纯): editor.py 各原语(move_*/swap/lock_bundle/set_gap_layout/distribute_evenly)过 legal_window, 返回可回滚 Diff。distribute_evenly 提供冷启动 kernel 的一键均匀重排。



M4 pass 流水线 + 校验 + 自带分阶段评测: reorder/passes.py(FixupPass/PassPipeline) + reorder/waitcnt.py 通用重算框架 + isa/gfx942/passes.py(WaitcntRecomputePass + ForcedNopPass) + Verifier; harness/toolchain.py + harness/evaluator.py(三阶段编排) + analysis/(perf 解析 + 瓶颈分类) + Target.perf_counter_schema; 先只重排 core loop 区跑通"重排→编译→正确性→性能→counter dump→方向"端到端骨架。



M5 三区独立 + 边界 counter 契约 + CFG 数据流: 扩到 prologue/epilogue; 边界 counter 只读校验; recompute_all_cfg 处理分支/wave specialization meet, barrier count-locked。



M6 搜索层(吃 analysis 方向) —— 拆三个有序子步骤, 按风险递增推进:





M6a 结构化 layout 接口(先做, 纯封装): propose_layouts + SkipReason/Placement/LayoutReport, 建在已验证的 set_gap_layout/move_after/legal_window 之上, 零新依赖; 让 AI 精修到单个 MFMA 间隙的逐 slot 计数/顺序(见上节)。带单测。



M6b 信号去风险(已完成): 真机验证 direction(tools/validate_direction.py)。修复致命 bug(旧 share 分母含 none~60% → bottleneck 恒为 latency/零区分度), 改信息维度口径后区分度恢复。结论(proj/if/direction_signal_validation.md): 稳定性中等(需 3–5 次投票)、与 perf 相关性弱 → direction 仅作算子选择先验, 目标仍是实测 GFLOPS + 正确性/Verifier。



M6c 搜索循环(已完成): search/movedsl.py(机制B 逐位置 move-DSL + 稳定 handle) + search/list_scheduler.py(机制A 可调权重贪心调度) + search/driver.py(投票 direction 先验 + 低置信回退固定阶梯 + build_candidate 复用引擎 + 真机 GFLOPS 拍板, evaluator 可注入便于无 GPU 单测) + tools/search_loop.py(真机入口)。按 m6b 结论：direction 多次投票取众数、低置信(latency/none 或频率<60%)回退、仅作先验, 目标=实测 GFLOPS+正确性门控。真机验证错误候选被正确剔除。可选 anneal.py 未做。



M7 元层(首版已实现): agent/knowledge.py(Skill schema + 文件持久化 + seed_search_plan 播种 + log_experiment/induce_skills 归纳, 带证据/置信度/跨 kernel 防污染晋升门) + agent/tuner.py(before→during→after 闭环, search 加 extra_specs 先验入口)。内层搜索仍纯固定逻辑; 知识只导航不裁决。已用真机 cold-start 数据播种 13 条 candidate skill。遗留: 跨 kernel 晋升 trusted 待第二个真实 kernel（真正 LLM 决策已由 M8 接上）。



M8 LLM 决策面 + 分区独立调优 + SDK Agent(已实现): 把引擎封成 LLM 可驱动的闭环, 并支持对循环前/循环体/循环结束分别调优。





决策面 agent/session.py AgentSession 三动作: observe(只读事实地图 JSON) / propose(非提交合法性试摆, 回 SkipReason+合法窗口+卡住者) / commit_and_eval(真机门控+记 experiments.log); tools/agent_session.py 是其 CLI。LLM 读 observe、按硬件知识提非均匀 layout、看 SkipReason 迭代、只提交引擎判合法者, 拍板=实测 TFLOPS+正确性。



分区独立调优 reorder/regions.py 增 select_region(loop/prologue/epilogue/inter/body 或 loop#1/整数下标) + region_summaries(每区元数据); AgentSession(region=...) 与 build_candidate(spec['region']) 按区构建 RegionEditor。正确性关键: 改 loop 区走 loop-aware recompute(region=); 改非循环区自动改用整核 recompute_cfg 跨区穿 scoreboard(保「循环内发起、epilogue 才 drain」的异步访存 waitcnt 正确); baseline 与候选同重算路径保证对比公平。



SDK 程序化 agent tools/sdk/tune.mjs(@cursor/sdk 起本地 Cursor agent, cwd=testft, 用 shell 调 agent_session.py 跑 observe→propose→eval): --region 钉死单区(默认 loop)或 all/auto 放开自由选区; --transcript/--results 双落盘开关(每轮提示词/输出/工具 I/O + 每轮性能行含 region 列); key 走 env 或 cursor.config.json(0600+gitignore)。根目录 tune_quick.sh = 2 轮/不存提示词/存结果的快捷封装, 默认主循环区。



守住铁律: LLM 只导航, legal_window+Verifier+真机数值裁决, 错误决策只浪费预算。单测 tests/test_session.py(observe/propose/commit + 分区: 列全部区/切区改变视图/三区 build 合法/缺失区报错), 全套 203 passed。文档: proj/sdk_agent_integration.md、proj/if/ai_interface.md §3.4.3、tools/sdk/README.md。遗留: 跨 kernel 晋升 trusted 待第二个真实 kernel; M5 精确 CFG meet 暂缓; search/anneal.py 可选未做。

评测边界(testft 自带, 可插拔, 三阶段)

# harness/evaluator.py
class Evaluator(Protocol):
    def assemble(self, s_path: str) -> str: ...                 # .s -> .o/.co, 失败抛异常
    def check_correctness(self, s_path: str) -> bool: ...       # 阶段1: 数值正确性
    def measure_perf(self, s_path: str) -> float: ...           # 阶段2: 返回执行时间(us)
    def dump_counters(self, s_path: str, out_path: str) -> str: ... # 阶段3: dump HW perf counter 到文件
    def evaluate(self, s_path: str) -> "EvalResult": ...        # 编排三阶段(错误即短路)

@dataclass
class EvalResult:
    compiled: bool
    correct: bool | None          # 无运行环境时为 None(仅编译合法性)
    time_us: float | None         # 阶段2 执行时间
    tflops: float | None          # 由 time_us + 问题规模换算
    counter_dump_path: str | None # 阶段3 dump 出的硬件计数器文件
    counters: dict | None         # analysis.perf 解析后的计数器字典
    direction: dict | None        # analysis.bottleneck 给出的瓶颈分类 + 下一轮方向 hints
    detail: dict

编排顺序与短路: evaluate 先 assemble(失败→compiled=False 返回) → check_correctness(失败→不跑性能, correct=False 返回) → measure_perf(得 time_us/tflops) → 可选 dump_counters → analysis.perf.parse() + analysis.bottleneck.classify() 填 counters/direction。direction 回流给 M6 搜索 / M7 agent 指引下一轮(选哪个区、用哪类编辑算子、distribute 还是细调)。





默认 CompileOnlyEvaluator 只到 assemble(无需 GPU), 其余阶段返回 None。



真机评测用例已就位: testft/testcase/(fp8 block-scale GEMM), 对接方式见 proj/testcase_integration.md。映射: assemble=clang++ 汇编 shader→gemm.co; check_correctness=dump_result=1 跑 gemm.exe 抓 #TEST PASSED; measure_perf=dump_result=0 跑 total_loop=20 抓 stdout time:/gflops:; dump_counters=rocprofv2 att。kernel 符号 gemm_kernel_func, 固定 device 1。



perf counter 文件的字段语义由 Target.perf_counter_schema() 提供(架构相关), analysis/ 据此把原始计数器映射到瓶颈维度——换架构即换 schema, 分析框架不变。

正确性兜底

即便 legal-by-construction, 永远保留编译 + 数值正确性测试作最后防线; HW 测试前先跑 Verifier(DepGraph + counter 模拟 + 不越界 + Target 不变式)过滤废候选。

测试用例（已提供）

testft/testcase/（fp8 block-scale GEMM，shader fp8gemm_blockscase_32mx1_32nx4.s + host fp8gemm.cpp + cmd）。对接方式见 proj/testcase_integration.md。M0-M3 用 testft 自带两种风格 fixtures + 该真实 shader 推进; M4 用该用例做三阶段真机端到端验收。