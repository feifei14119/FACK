# skill 挖掘 —— 当前状态 & 后继条目

> 配套设计见同目录 [`ai_assisted_skill_mining.md`](./ai_assisted_skill_mining.md)。
> 最近更新:2026-07-01。

---

## 一、已完成(Layer 1:固定逻辑·细粒度量化提取)

- [x] `tools/mine_corpus.py::quant_profile()` —— 对 MFMA 锚定区域逐 gap **实测**:
      `mfma_gap_size` / `per_slot_capacity[kind]` / `burst_runlen[kind]` /
      `intra_gap_order` / `adjacent_cooccur[kind]`;anchor-less 区域返回 `None`(不臆造)。
- [x] `_stats()` —— 紧凑分布摘要(n/min/p25/median/p75/max/mean),空样本返回 `None`。
- [x] `build_quant_skills()` + `_pool_quant()` —— 按 `(arch,kernel_class,region)`
      跨语料池化,产出带 `action.constraints`(每条 `weight`)+ `conflict_groups`
      的量化约束 skill(`gold-<class>-<region>-quant.json`),`status=candidate`。
- [x] 冲突组规则:`per_slot_capacity.median ≥ 2` 且 `adjacent_cooccur.rate ≤ 0.34`
      → `["per_slot_capacity:<kind>","adjacent_cooccur:<kind>"]`。
- [x] `render_report()` 新增"fine-grained quant layout skills"小节 + `_fmt_constraint()`。
- [x] `main()` 串接:`build_skills + build_quant_skills` 一并写出。
- [x] `unittests/test_mine_corpus.py::TestQuantProfile`(5 条新断言,全套 15 用例通过):
      量化可测、数字源自 gold 流(gap ≤ 区域长度)、约束带权重且无 shape/kernel 泄漏、
      容量高+相邻低时生成冲突组、相邻高时不生成。
- [x] README 挖掘小节 + 本目录两份文档。
- [x] **D(噪声过滤)**:`intra_gap_order` 限制到可调度 filler(`_QUANT_KIND_VALUES`),
      滤掉 `branch/barrier/waitcnt/set_m0` 等栅栏指令的同义噪声(真实语料上由 19 条降为
      `salu→vmem_load→ds_read` 3 条有效序),配套断言测试。
- [x] **A(在线透传)**:`agent/knowledge.py::seed_search_plan` 聚合 applicable 技能的
      `constraints` + `conflict_groups`(新增 `_constraint_id` 去重)并随返回字典进入
      `Observation.prior_plan`(`session.py` 无需改动),配套 `test_knowledge.py` 两条断言。
- [x] **Layer 3 约束消费器**:新增 `agent/layout_planner.py`(纯函数)——把
      `constraints`+`conflict_groups` 转成排好序的候选 gap layout:按 `per_slot_capacity`
      定每槽容量、按 `adjacent_cooccur` 定摊开步长、按 `intra_gap_order` 定槽内先后,
      `conflict_groups` 展开成"打包 vs 摊开"变体,按 `weight×confidence` 打分排序。
      `AgentSession.plan_layouts()` 由真实 `Observation`+`prior_plan` 调用它并经 `propose()`
      附合法性(纯 CPU,无真机)。配套 `test_layout_planner.py`(10 例)+ `test_session.py`
      `TestPlanLayouts`(3 例)。**无约束则返回空**(不臆造 layout)。
- [x] **真机验证开关**:`AgentSession.learn_layouts(validate=...)` 带开关闭环——
      `validate=False`(默认)只产候选、**绝不调用 evaluator**(可在一台 CPU 机器上为任意
      架构总结);`validate=True` 才 `commit_and_eval` 真机裁决并可 `induce` 晋升 `trusted`。
      独立入口 `tools/validate_skills.py`(evaluator 可注入/惰性),开关在 `mine_skills.sh`
      的 `VALIDATE`(默认 0)。配套 `test_session.py` 3 例(OFF 不碰 evaluator / ON 提交+晋升 / 工具 dry+注入)。
- [x] **Layer 2(离线 AI 归纳)**:两段确定性轨道 + 中间外部 agent(仓内不内嵌 LLM)。
      - 导出 `tools/ai_skill_brief.py`:把 Layer 1 的量化 skill 打包成 `ai_brief.json`/`.md`
        ——`measured` 为 ground truth + 可引用的 `measured_refs` + 红线 + 提案 schema。
      - 摄入 `tools/ingest_ai_skills.py`:**严格闸门**校验外部 agent 的 `ai_proposal.json`——
        `extrapolated=false` 的约束按 ref 回查 Layer 1 并**逐字复制权威数字**(agent 改不动数字,
        查无此 ref 即丢弃);`extrapolated=true` 必须带 `note`、`weight` 封顶 `EXTRAP_CAP=0.3` 且
        标 `source:ai-hypothesis`;scope 只取组内结构键;`confidence` 封顶(纯实测重述 ≤0.6、含外推 ≤0.3,
        恒低于 gold 量化 ~0.89,故 `seed_search_plan` 去重永远保留实测项);产物恒 `candidate`、
        `source=gold_corpus(modeB-ai)`。支持 `--dry-run`。
      - 真实语料跑通:`ai-mfma_dense-loop-pipeline`(9 实测 + 3 外推约束 + 1 冲突组,c=0.30)。
      - `mine_skills.sh` 中 Layer 2 **常开、无开关**(GPU-free):每次挖掘后自动导出 brief,若已有 proposal 则校验摄入。
      - **无头自动产 proposal**:`tools/sdk/articulate.mjs`(`@cursor/sdk`)端到端跑 Layer 2——导出简报 →
        程序化 Cursor agent 产 `ai_proposal.json` → 闸门摄入(摄入前清旧 `ai-*.json`),**脱离 Cursor IDE 即可**
        (需 `CURSOR_API_KEY`)。已用真实语料实跑:agent 产 3 个技能、全部过闸门(candidate,c=0.30)。
      - 配套 `unittests/test_ai_skill_layer2.py`(10 例:导出只取量化 skill / 实测权威复制 /
        臆造 ref 丢弃 / 外推须带 note 且封顶 / 重述封顶低于 gold / 未知 base 丢弃 / scope 仅结构键 /
        冲突组成员须可解析 / 与 `seed_search_plan` 集成时不覆盖实测)。
- [x] **指令子类型细分(按 MFMA 形状 + 访存位宽)**——修"默认只有一种 mfma / 一种 lds"的抹平问题:
      - `quant_profile` 抽出 `_gap_block_metrics`,按**开启 gap 的 MFMA 形状**归类,`by_mfma_class[shape]`
        下独立重算 gap/容量/相邻/顺序;`per_slot_capacity[kind].by_width` 再按位宽(`32b/64b/128b`,
        由 `access_width_bits` 把 `b128`/`dwordx4` 统一)拆分;新增 `mfma_class_hist`。顶层旧字段全部保留(向后兼容)。
      - `_pool_quant_by_class` + `_class_constraints`:在池化约束之上,>1 形状时每形状各出一套约束(带 `mfma_class`)
        与**按形状冲突组**(`per_slot_capacity@shape:kind` ⟷ `adjacent_cooccur@shape:kind`);**按位宽容量**约束始终产出。
      - `agent/knowledge._constraint_id` 纳入 `mfma_class`/`width`(两者缺省时 id 不变,ref 唯一)。
      - `agent/layout_planner`:导出共享 `mfma_shape_class`;`_capacity`/`_gap_size` 按形状优先、缺失回退池化;
        新增 `_distribute_perslot` + `gap_classes` 入参(按各 gap 形状定容,32x32x8 gap 比 16x16x16 塞得更满);
        打分只用池化约束避免重复计数;默认路径(不传 `gap_classes`)行为逐字不变。
      - `agent/session.plan_layouts` 从 anchors 真实 opcode 推导 `gap_classes` 透传;ingest 保留并渲染 `mfma_class`/`width`。
      - 真实语料验证:该 GEMM 语料 MFMA 全是 `16x16x16`(单形状),但 lds/vmem 位宽异质
        (`vmem_load` `32b:max5` vs `128b:max1`、`ds_read` b128 vs b32)——位宽维已带来区分;端到端 mine→brief→ingest 跑通。
      - 配套单测:`test_mine_corpus.py`(`TestInstructionSubTyping` / `TestQuantSkillMfmaClass`:形状/位宽解析、
        `by_mfma_class` 拆分、per-class+width 约束、按形状冲突组、ref 唯一、顶层向后兼容)+ `test_layout_planner.py`
        (`TestMfmaClassAware`:按形状容量优先/回退、大形状 gap 塞更多、无 `gap_classes` 均分、长度不匹配回退)。

### 红线自检(已满足)
- 数字一律来自 gold 实测,Layer 1 无任何外推/臆造;Layer 2 的 AI 也**改不动实测数字**
  (摄入按 ref 逐字复制权威值),其外推项强制标注 + 封顶低置信。
- 产物恒 `candidate`,永不自动晋升 `trusted`(含 AI 产物)。
- scope 仅结构键(`arch`/`loop_kind`/`region`),无 shape、无 kernel 名(AI 提案的 scope 由组内强制接管)。
- 不跑真机、不写 `knowledge/engine`,产物落 `study_case/study_out`。

---

## 二、进行中

- 无。离线挖掘(L1)+ 噪声过滤(D)+ 在线透传(A)+ 约束消费器(L3 候选生成)+
  **真机验证开关**(`learn_layouts(validate=...)` / `validate_skills.py` / `mine_skills.sh::VALIDATE`)+
  **Layer 2 离线 AI 归纳**(`ai_skill_brief.py` 导出 / `ingest_ai_skills.py` 闸门摄入 / 在 `mine_skills.sh` 中常开)
  已打通并通过测试。闭环代码完备;**剩下的只是"在真正的 GPU 机器上把 `VALIDATE=1` 跑一次"** 取得真机 delta
  并晋升 `trusted`(本机无 GPU,只能用假 evaluator 验证逻辑)。

---

## 三、后继条目(优先级从高到低)

### A. 在真实语料上验证 Layer 1
- [x] 在 23 个真实 bf16 GEMM gold kernel 上运行 `bash study_case/study_script/mine_skills.sh`,
      量化字段被充分填满(`gold-mfma_dense-loop-quant`,n=23,conf≈0.89);`intra_gap_order`
      经 D 过滤后为 `salu→vmem_load→ds_read`,符合直觉。
- [ ] 据真实分布调参:冲突组阈值(`median≥2` / `rate≤0.34`)、`intra_gap_order` 的 0.7 定向阈值、
      `weight` 的 agreement 口径。**当前 GEMM 语料 ds_read 偏稀疏,未触发冲突组**;需用
      LDS 密集类(`lds_bound`)语料校准。

### B. Layer 2 —— AI 离线归纳/表达
- [x] 设计"画像 → agent 提示"打包格式:`tools/ai_skill_brief.py` → `ai_brief.json`/`.md`
      (池化量化约束作 ground truth + `measured_refs` 供引用 + 红线 + 提案 schema)。
- [x] 外部 agent 产出条件化/加权 skill;`tools/ingest_ai_skills.py` 闸门校验:**外推项**强制
      `source: ai-hypothesis` + 封顶低 `confidence` + `status: candidate`;**实测项按 ref 复制权威数字,改不动**。
- [x] 落盘到 `study_case/study_out/skills/`,与 Layer 1 量化 skill 以 `id`(`ai-*` vs `gold-*`)+
      `source`(`modeB-ai` vs `modeA-quant`)区分;真实语料已生成 `ai-mfma_dense-loop-pipeline`。
- [ ] (可选)接外部 LLM/SDK 自动产 `ai_proposal.json`(当前由 agent 人在环手写);用 `lds_bound`
      等更多类语料检验外推规则质量。

### C. Layer 3 —— 在线冲突权衡 + 候选生成
- [x] 扩展 `agent/knowledge.py::seed_search_plan`,把 `action.constraints` +
      `conflict_groups` 透传进 `Observation.prior_plan`(已随返回字典自动进入,`session.py` 无需改)。
- [x] 约束消费器:给定目标 kernel 实际资源数(`Observation` 的 slots/fillers)+
      冲突约束,按 `weight × confidence` 枚举 N 种候选排布(`agent/layout_planner.py` +
      `AgentSession.plan_layouts()`,经 `propose()` 校验合法性)。
- [x] 真机验证**开关**:`learn_layouts(validate=...)` → `validate=True` 时
      `commit_and_eval` 真机评估、`log_experiment` 记录 delta、可 `induce_and_save` 晋升;
      `validate=False` 时纯 CPU 产候选(不碰 evaluator)。入口 `tools/validate_skills.py`、
      脚本开关 `mine_skills.sh::VALIDATE`。
- [ ] **在真正 GPU 机器上实跑 `VALIDATE=1`**:取得真机 delta、验证晋升 `trusted` 的实际效果(本机无 GPU)。
- [ ] (可选)把 `plan_layouts`/`learn_layouts` 接进 CLI 桥 `tools/agent_session.py` 或 SDK,让外部 agent 直接取候选。

### D. 收尾
- [ ] 端到端示例(裸 kernel → 量化先验 → 候选排布 → 真机评估 → 回写)写入文档。
- [ ] 评估约束先验对搜索预算/最终 GFLOPS 的实际收益。

---

## 四、关键文件索引

| 用途 | 路径 |
|---|---|
| 挖掘器(Layer 1 实现) | `tools/mine_corpus.py` |
| Layer 2 导出/摄入(离线 AI) | `tools/ai_skill_brief.py` + `tools/ingest_ai_skills.py` |
| 约束消费器(Layer 3) | `agent/layout_planner.py` + `AgentSession.plan_layouts()` |
| 真机验证开关 + 入口 | `AgentSession.learn_layouts(validate=...)` + `tools/validate_skills.py` |
| 挖掘入口脚本(含 VALIDATE 开关) | `study_case/study_script/mine_skills.sh` |
| 挖掘产出 | `study_case/study_out/`(`skills/` + `mine_report.md`,gitignore) |
| 测试 | `unittests/test_mine_corpus.py` + `unittests/test_ai_skill_layer2.py` |
| 技能 schema / 消费 | `agent/knowledge.py` |
| 在线决策面 | `agent/session.py` |
| 评估边界 | `harness/evaluator.py` |
| 设计文档 | `proj/skill/ai_assisted_skill_mining.md` |
| 上游静态挖掘原理 | `proj/gold_corpus_mining.md` |
