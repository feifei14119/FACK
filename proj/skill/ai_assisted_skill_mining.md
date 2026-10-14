# AI 辅助的细粒度 skill 挖掘（设计目的 · 思路 · 步骤）

> 范围:在已落地的 Mode A 静态语料挖掘（`tools/mine_corpus.py`,见
> [`../gold_corpus_mining.md`](../gold_corpus_mining.md)）之上,引入 **AI 辅助**,
> 把"粗粒度区域 spec"升级为"细粒度、量化、可冲突权衡"的调度指导,使调优 agent
> 拿到一个**完全未排序**的 kernel 时,能据此高效排出接近 roofline 的指令顺序。

---

## 1. 设计目的（Why）

现有 Mode A 只产出区域级的粗 spec(`compact` / `listsched` / `distribute_evenly`),
告诉 agent "在循环里把 vmem/ds 往 MFMA 间隙里铺"。这对**已大致排好**的 kernel够用,
但对一个**裸 kernel**(指令顺序未经任何优化)远远不够——agent 需要更具体的量化指导:

- 两条 MFMA 之间**大概能插多少条**指令?(gap 容量)
- vmem / lds 指令**能连续发射多少条**?(连发上限)
- **不同** MFMA 间隙插入的指令数是否一致?(均匀 vs 模式化)
- 插入指令的**类型有没有先后顺序**?(如 `ds_read` 先于 `vmem_load`)
- 相邻的 MFMA 槽位**能不能都塞同一类**指令?(相邻约束)
- **不同类型**的 MFMA(`16x16x16` vs `32x32x8` …)执行周期不同,间隙容量随之不同;
  lds / vmem 也有**位宽变体**(`b32/b64/b128`、`dword/dwordx2/dwordx4`),延迟/带宽各异——
  必须**按指令子类型分别实测**,不能把它们混算成"一种 mfma / 一种 lds"。

这些都是从"人工调好(roofline 级)的 gold kernel"里**可以实测**出来的结构事实。
把它们提炼成 skill,调优 agent 就能把"先验布局"作为起点,大幅压缩搜索空间。

### 1.1 为什么需要"冲突 + 权重"

不同 gold kernel / 不同区域提炼出的约束之间会**天然冲突**。典型例子:

- **skillA**:每个 MFMA 槽可发射 4 个 `ds_read`(`per_slot_capacity` 高)。
- **skillB**:相邻 MFMA 槽**不应**都填 `ds_read`(`adjacent_cooccur` 低)。

当目标 kernel 里有 16 个 `ds_read`、4 个 MFMA 槽时,A 和 B 给出的布局并不相容。
此时调优 agent 需要按 `weight × confidence` **权衡**这组冲突,枚举若干**满足度不同**
的候选排布,再交**真机评估**裁决,胜出者的 delta 回写权重/置信度。

> 这与本仓的核心红线一致:**知识只导航(试什么),引擎裁合法性(什么有效),
> 真机裁优劣**。即便冲突权衡判断错了,也只会浪费搜索预算,绝不产出错误 kernel。

---

## 2. 关键决策（已与用户确认）

| 决策点 | 选择 | 含义 |
|---|---|---|
| AI 的数字边界 | **允许外推** | AI 可在实测之外提出假设性数值/规则,但**必须标注**"未实测·低置信·需真机验证";第 1 层固定逻辑产出的数字仍**只测不造**。 |
| 首个里程碑 | **先做第 1 层** | 先用纯固定逻辑把细粒度量化画像测出来(可单测、可复现),再叠加 AI。 |
| AI 接入方式 | **外部 agent** | 沿用现有架构:由外部 LLM agent(Cursor agent 或任意模型)读画像 + `Observation`,产出 skill 措辞并在线权衡冲突;**仓内不内嵌 LLM 客户端**(无 API key/网络依赖)。 |

---

## 3. 总体架构(三层)

```
            gold kernels (.s, roofline 级)
                       │
   ┌───────────────────▼─────────────────────┐
   │ Layer 1  固定逻辑·细粒度量化提取(已落地)   │  无 AI、可单测、数字只测不造
   │ tools/mine_corpus.py: quant_profile +    │
   │ build_quant_skills                       │
   └───────────────────┬─────────────────────┘
                       │  gold-<class>-<region>-quant.json
                       │  (action.constraints + weight + conflict_groups)
   ┌───────────────────▼─────────────────────┐
   │ Layer 2  AI 离线归纳/表达(已实现)         │  外部 agent(仓内不内嵌 LLM)
   │ ai_skill_brief.py  → ai_brief.json/.md   │  导出:measured=ground truth
   │   (外部 agent 写 ai_proposal.json)        │  agent:选权重 + 外推(须标注)
   │ ingest_ai_skills.py → ai-*.json(闸门)    │  摄入:实测复制·外推封顶·恒 candidate
   └───────────────────┬─────────────────────┘
                       │  注入 Observation.prior_plan
   ┌───────────────────▼─────────────────────┐
   │ Layer 3  约束消费器(候选生成,已实现)       │  agent/layout_planner.py
   │ 读约束+目标 kernel 资源数 → 按              │  + AgentSession.plan_layouts()
   │ weight×confidence 枚举 N 种排布 →           │
   │ propose() 校验合法性                        │
   │   │ 真机验证开关 learn_layouts(validate)    │  validate=False:纯 CPU(默认)
   │   ▼ validate=True(需 GPU+testcase)         │  validate=True :真机裁决+晋升
   │ commit_and_eval → delta → induce 晋升 trusted│
   └──────────────────────────────────────────┘
```

### 3.1 Layer 1:固定逻辑·细粒度量化提取(已实现)

代码:`tools/mine_corpus.py` 的 `quant_profile()`(逐 kernel/区域)与
`build_quant_skills()`(跨语料池化)。仅对 **MFMA 锚定**的区域(`anchors(MFMA) ≥ 2`)
计算;anchor-less 区域(prologue/epilogue)**不编造** gap 画像。

逐 gap 实测指标(`signature.quant`):

| 字段 | 含义 | 对应用户问题 |
|---|---|---|
| `mfma_gap_size` | 相邻 MFMA 间指令数分布(min/p25/median/p75/max + raw) | 两条 MFMA 间能插几条 |
| `gap_sizes`(raw) | 逐槽序列 | 不同间隙是否一致(均匀 vs 模式化) |
| `per_slot_capacity[kind]` | 每个 gap 内某 Kind 的数量分布 | 每槽能塞几个 lds/vmem |
| `burst_runlen[kind]` | 整区域内某 Kind 的最长连发长度分布 | vmem/lds 能连发几条 |
| `intra_gap_order` | gap 内类型先后(P(a 先于 b\|两者都在),仅在 ≥0.7 时定向) | 插入类型有无先后 |
| `adjacent_cooccur[kind]` | 相邻 gap 对中两者都含该 Kind 的比例 | 相邻槽能否都填同类 |
| `by_mfma_class[shape]` | **按开启该 gap 的 MFMA 形状**(`16x16x16`/`32x32x8`…)分桶,重算以上全部指标 | 不同 MFMA 类型间隙容量不同 |
| `per_slot_capacity[kind].by_width` | 某 Kind 容量再**按访存位宽**(`32b/64b/128b`)拆分 | lds/vmem 位宽变体各异 |
| `mfma_class_hist` | 每个 gap 由哪种 MFMA 形状开启的计数 | 语料实际用了哪些 MFMA 类型 |

跨语料**池化**(同 `arch/kernel_class/region`):把各 kernel 的 raw 列表合并后重算
统计量;`weight = min(0.9, agreement × (1 − 1/(n_kernels+1)))`,随独立 kernel 数与
一致性上升。产出 skill:

```json
{
  "id": "gold-mfma_dense-loop-quant",
  "when": {"arch":"gfx942","loop_kind":"mfma_dense","region":"loop"},
  "action": {
    "constraints": [
      {"metric":"mfma_gap_size","stat":{"min":3,"median":5,"max":7,...},"weight":0.8},
      {"metric":"per_slot_capacity","kind":"ds_read","stat":{"median":4,"max":4,...},"weight":0.7},
      {"metric":"burst_runlen","kind":"vmem_load","stat":{"median":2,"max":3,...},"weight":0.7},
      {"metric":"adjacent_cooccur","kind":"ds_read","value":0.1,"polarity":"avoid","weight":0.6},
      {"metric":"intra_gap_order","before":"ds_read","after":"vmem_load","freq":0.9,"weight":0.6},

      // ↓ 按 MFMA 形状 / 位宽细分(见 3.1.1):池化约束之上的精修,ref 用 @shape、/width 区分
      {"metric":"mfma_gap_size","mfma_class":"32x32x8","stat":{"median":8,"max":9,...},"weight":0.8},
      {"metric":"per_slot_capacity","kind":"ds_read","mfma_class":"32x32x8","stat":{"median":6,...},"weight":0.7},
      {"metric":"per_slot_capacity","kind":"ds_read","mfma_class":"16x16x16","width":"128b","stat":{"median":2,"max":2,...},"weight":0.7}
    ],
    "conflict_groups": [["per_slot_capacity:ds_read","adjacent_cooccur:ds_read"],
                        ["per_slot_capacity@16x16x16:ds_read","adjacent_cooccur@16x16x16:ds_read"]]
  },
  "evidence": {"kernels":[...],"n_samples":9,"source":"gold_corpus(modeA-quant)"},
  "confidence": 0.6,
  "status": "candidate"
}
```

**冲突组生成规则**:某 Kind 同时满足 `per_slot_capacity.median ≥ 2`(能多塞)与
`adjacent_cooccur.rate ≤ 0.34`(相邻不宜都填)时,生成
`["per_slot_capacity:<kind>","adjacent_cooccur:<kind>"]`,交由 Layer 3 权衡。

**红线**:所有数字源自 gold 顺序实测;`status` 恒 `candidate`;scope 只含结构键
(`arch`/`loop_kind`/`region`),无 shape、无 kernel 名。

#### 3.1.1 指令子类型细分:按 MFMA 形状 + 访存位宽(已实现)

**动机**:一条粗粒度 `Kind`(`mfma`/`ds_read`/`vmem_load`…)会抹掉硬件相关的差异——
不同 MFMA 形状(`16x16x16` vs `32x32x8`)**结果延迟不同**,因此开启的 gap 大小、能塞的指令数
都不同;lds/vmem 又有 `b32/b64/b128`、`dword/dwordx4` 等**位宽变体**。把它们混算,`mfma_gap_size`
的 `[0..20]` 只是把 3 周期 gap 和 6 周期 gap 平均出来的假象。引擎其实早已知道每种 MFMA 的延迟
(`isa/gfx942/classify.mfma_read_latency` + `edges.py` 从 seed 自校准),`Line.opcode` 也保留真实
mnemonic——**信息一直都在,只是挖掘时被抹平**。

**做法**(不改 parser):

- **形状分桶**:`quant_profile` 里每个 gap 按**开启它的 MFMA** 的形状 token(`16x16x16`…)归类,
  在 `by_mfma_class[shape]` 下**独立重算** gap_size / capacity / adjacency / order。形状解析
  `mfma_shape_class(opcode)` 由 `agent/layout_planner.py` 提供,**挖掘器与规划器共用同一真源**。
- **位宽拆分**:`access_width_bits(opcode)` 把 `b128`、`dwordx4` 统一成位宽(`128b`…),
  `per_slot_capacity[kind].by_width` 按位宽再拆容量分布。
- **约束产出**(`_class_constraints`):在池化约束之上**增发**——当出现 >1 种 MFMA 形状时,
  每种形状各出一套 gap/容量/相邻/顺序约束(带 `mfma_class`)与**按形状的冲突组**
  (`per_slot_capacity@shape:kind` ⟷ `adjacent_cooccur@shape:kind`);**按位宽的容量约束**
  (带 `mfma_class`+`width`)则始终产出(b32 vs b128 对单形状语料也是新信号)。
- **引用键**:`agent/knowledge._constraint_id` 纳入可选的 `mfma_class`/`width`
  (`per_slot_capacity@32x32x8:ds_read/128b`),使每条精修约束在 brief↔proposal 间**唯一可引用**;
  两者都缺省时 id 与历史完全一致(**向后兼容**,池化约束/旧冲突组不受影响)。
- **消费**(Layer 3):`plan_candidate_layouts(..., gap_classes=[每个 gap 的形状])` 按**各 gap 自己的
  形状**取容量给每槽定容(高延迟的 32x32x8 gap 比 16x16x16 gap 塞得更满);打分仍只用池化约束
  以免重复计数。`AgentSession.plan_layouts` 从 anchors 的真实 opcode 推导 `gap_classes` 透传。

> **红线不变**:数字仍只测不造;新维度只是"分得更细",不引入任何外推。真实 bf16 GEMM 语料实测:
> 该语料 MFMA **全是 `16x16x16`**(单形状,故形状维暂无区分),但 lds/vmem 位宽高度异质
> (`ds_read` b128 vs b32、`vmem_load` `32b:max5` vs `128b:max1`),位宽维已带来实打实的区分。

### 3.2 Layer 2:AI 离线归纳/表达(已实现)

仓内**不内嵌 LLM 客户端**:Layer 2 做成"两段确定性轨道 + 中间外部 agent"。AI 就是外部
agent(可以是我、也可以是任何 LLM/SDK),代码只提供进出两条轨道与**严格闸门**。

```
ai_skill_brief.py  ──►  ai_brief.json/.md  ──►  (外部 agent)  ──►  ai_proposal.json  ──►  ingest_ai_skills.py  ──►  ai-*.json
   导出 Layer1 量化约束          measured=ground truth            选约束/权重+外推                          闸门校验、落盘
```

**STAGE 1 导出(`tools/ai_skill_brief.py`)**:读 `gold-*-quant.json`,把每个
`(arch,kernel_class,region)` 组打包为 `ai_brief.json`(+ 人读 `ai_brief.md`):

- `measured` = Layer 1 实测约束(ground truth)+ `measured_refs`(`metric[:kind]` /
  `intra_gap_order:before>after`)供 agent 按 ref 引用;
- 内嵌**红线**与**提案 schema**:实测项按 ref 引用(数字不可改)、实测外的任何规则必须
  `extrapolated:true` + `note`、scope 固定为组内结构键、产物恒 `candidate`。

**STAGE 2 摄入(`tools/ingest_ai_skills.py`)**:读 `ai_brief.json` + agent 写的
`ai_proposal.json`,**纯函数闸门** `validate_proposal()` 逐条裁决:

| 提案约束 | 闸门动作 |
|---|---|
| `extrapolated:false` | 按 ref 回查 Layer 1,**逐字复制权威 stat/value**(agent 改不动数字);查无此 ref ⇒ **丢弃**;`weight` 封顶为实测权重 |
| `extrapolated:true` | 必须带非空 `note`;`weight` 封顶 `EXTRAP_CAP=0.3`、标 `source:ai-hypothesis`;否则丢弃 |
| scope | 只取组内 `arch/loop_kind/region`,agent 无法加 shape/kernel 名 |
| `confidence` | 封顶:纯实测重述 ≤ `0.6`、含外推 ≤ `0.3`(**恒低于 gold 量化 ~0.89**,故 `seed_search_plan` 去重时实测项永远胜出) |
| `conflict_groups` | 成员须能解析到留存/实测约束,否则丢弃该组 |
| `status` / `source` | 恒 `candidate` / `gold_corpus(modeB-ai)`;`evidence.based_on` 指回源量化 skill |

支持 `--dry-run`(只打印不落盘)。Layer 2 在 `mine_skills.sh` 中**常开、无开关**(GPU-free):
每次挖掘后自动导出 brief,若已存在 `ai_proposal.json` 则校验摄入(置于 `VALIDATE` 之前,使 AI
产物也能被真机验证)。**只有真机验证 `VALIDATE` 是开关且默认关闭。**

**写 `ai_proposal.json` 的两条路**:① 人/agent 手写;② 无头 SDK agent 自动产——
`tools/sdk/articulate.mjs`(`@cursor/sdk`)端到端:导出简报 → 程序化 Cursor agent 产 proposal →
闸门摄入(摄入前清旧 `ai-*.json`)。这样**脱离 Cursor IDE** 也能全自动产出离线 AI 技能(需 `CURSOR_API_KEY`)。
注意这解决的是"脱离 IDE"而非"脱离大模型";闸门红线对模型输出同样强制(实测复制、外推封顶、恒 candidate)。

真实语料已跑通(23 个 bf16 GEMM):`ai-mfma_dense-loop-fill-pipeline`(9 实测 + 3 外推 + 1 冲突组)
与 `ai-mfma_dense-loop-wide-gap-spill`(4 实测 + 2 外推),均 `c=0.30`;外推项如"窄 gap 只放
salu+1 memory、宽 gap(≥4)作 spill、salu 领跑、ds_read 连发对跨 gap 拆分"——均标注未验证。

### 3.3 Layer 3:AI 在线冲突权衡 + 候选生成(后续)

复用 `agent/session.py` 的 `AgentSession` 闭环:

1. **(已实现)** `seed_search_plan` / `Observation.prior_plan` 把适用的量化约束(含
   `conflict_groups`)注入 agent 的"事实地图"。
2. **(已实现)** 约束消费器 `agent/layout_planner.py::plan_candidate_layouts`:读目标 kernel
   的**实际资源数**(由 `Observation` 的 slots/fillers 给出,如 16 个 `ds_read`、4 个 MFMA 槽),
   按 `per_slot_capacity` 定每槽容量、`adjacent_cooccur` 定摊开步长、`intra_gap_order` 定槽内先后;
   `conflict_groups` 展开成"打包(满足容量) vs 摊开(满足相邻约束)"两种变体,按
   `weight × confidence` 打分排序,产出 N 个候选 layout。`AgentSession.plan_layouts()` 调用它并经
   `propose()` 附合法性(纯 CPU,不臆造:无约束则返回空)。
3. **(已实现,带开关)** `AgentSession.learn_layouts(validate=...)`:
   - `validate=False`(默认)= **OFFLINE**,只产候选 + `propose` 合法性,**绝不调用 evaluator**;
     于是可在一台 CPU 机器上为**任意架构**总结 candidate skill,无需分别登陆每台 GPU 机器。
   - `validate=True` = **ONLINE**,把最有希望的合法候选交 `commit_and_eval` 真机评估
     (`harness/evaluator.py`,真机实现由测试用例注入),`log_experiment` 记录 delta;
     `promote=True` 时再 `induce_and_save` 把被真机佐证的候选晋升 `trusted`。
   - 开关入口:脚本 `study_case/study_script/mine_skills.sh` 的 `VALIDATE`(默认 0),
     独立工具 `tools/validate_skills.py`(`--validate/--no-validate`,evaluator 惰性构造、可注入)。
4. **(后续,需 GPU)** 在真正的 GPU + 可运行 testcase 上实跑 `VALIDATE=1`,取得真机 delta 并验证
   `trusted` 晋升的实际效果。

---

## 4. 实现步骤与状态

| # | 步骤 | 层 | 状态 |
|---|---|---|---|
| 1 | `quant_profile()`:逐 gap 实测 gap_size/capacity/burst/order/cooccur | L1 | ✅ 已完成 |
| 2 | `build_quant_skills()`:跨语料池化 + 约束 skill + 冲突组 | L1 | ✅ 已完成 |
| 3 | `mine_report.md` 量化画像小节 + `_fmt_constraint` | L1 | ✅ 已完成 |
| 4 | `unittests/test_mine_corpus.py` 量化/冲突断言(全过) | L1 | ✅ 已完成 |
| 5 | D 噪声过滤:`intra_gap_order` 仅保留可调度 filler(`_QUANT_KIND_VALUES`) | L1 | ✅ 已完成 |
| 6 | A 在线透传:`seed_search_plan` 聚合 `constraints`+`conflict_groups` → `prior_plan` | L3 | ✅ 已完成 |
| 7 | Layer 3 约束消费器:`agent/layout_planner.py` + `AgentSession.plan_layouts()`(候选生成+合法性校验) | L3 | ✅ 已完成 |
| 8 | 真机验证**开关** `learn_layouts(validate=...)` + `tools/validate_skills.py` + `mine_skills.sh::VALIDATE`(OFF=纯 CPU 任意架构总结;ON=真机裁决+晋升) | L3 | ✅ 已完成 |
| 9 | Layer 2:`ai_skill_brief.py` 导出 + `ingest_ai_skills.py` 闸门摄入(在 `mine_skills.sh` 中常开;实测复制·外推封顶·恒 candidate)+ `test_ai_skill_layer2.py`(10 例) | L2 | ✅ 已完成 |
| 10 | **指令子类型细分**:按 MFMA 形状(`by_mfma_class`)+ 访存位宽(`by_width`)分别实测;`_class_constraints` 增发按形状/位宽约束 + 按形状冲突组;`_constraint_id` 纳入 `mfma_class`/`width`;`layout_planner` `gap_classes` 按 gap 形状定容;`session.plan_layouts` 透传 | L1+L3 | ✅ 已完成 |
| 11 | 在真正 GPU 机器上实跑 `VALIDATE=1` 取得真机 delta、验证 `trusted` 晋升效果 | L3 | ⏳ 后续(需 GPU) |
| 12 | (可选)接外部 LLM/SDK 自动产 `ai_proposal.json`;用更多类语料检验外推质量;用含**多种 MFMA 形状**的语料检验形状维区分 | L2 | ⏳ 后续 |

> 详细的"当前状态 / 后继条目"清单见同目录 [`STATUS.md`](./STATUS.md)。

---

## 5. 相关代码与文档

- 挖掘(L1):`tools/mine_corpus.py`(`quant_profile` / `_gap_block_metrics` / `build_quant_skills` / `_pool_quant` / `_pool_quant_by_class` / `_class_constraints` / `access_width_bits` / `_fmt_constraint`)
- 子类型细分(L1+L3):`by_mfma_class` / `per_slot_capacity.by_width` 数据面;共享形状解析 `agent/layout_planner.py::mfma_shape_class`;引用键 `agent/knowledge.py::_constraint_id`(纳入 `mfma_class`/`width`);消费 `layout_planner` 的 `gap_classes` + `session.plan_layouts` 透传
- 入口脚本:`study_case/study_script/mine_skills.sh`(每次运行前清空 `study_case/study_out/skills`,再挖掘)
- 产出:`study_case/study_out/`(`skills/gold-<class>-<region>-quant.json` + `mine_report.md`)
- 离线 AI 归纳(L2):`tools/ai_skill_brief.py`(导出 `ai_brief.json/.md`)+
  `tools/ingest_ai_skills.py`(`validate_proposal` 闸门 → `ai-*.json`)+ 在 `mine_skills.sh` 中常开;
  无头自动产 proposal:`tools/sdk/articulate.mjs`(`@cursor/sdk`,见 `tools/sdk/README.md`)
- 在线透传(A):`agent/knowledge.py::seed_search_plan`(`constraints`/`conflict_groups` → `prior_plan`)
- 约束消费器(L3):`agent/layout_planner.py::plan_candidate_layouts` + `agent/session.py::AgentSession.plan_layouts`
- 真机验证开关(L3):`agent/session.py::AgentSession.learn_layouts(validate=...)` + `tools/validate_skills.py` + `mine_skills.sh::VALIDATE`
- 测试:`unittests/test_mine_corpus.py`(`TestQuantProfile`)、`unittests/test_ai_skill_layer2.py`(L2 闸门 10 例)、
  `unittests/test_knowledge.py`(透传)、`unittests/test_layout_planner.py`、`unittests/test_session.py`(`TestPlanLayouts`)
- 技能 schema 与消费:`agent/knowledge.py`(`Skill` / `seed_search_plan` / `induce_skills`)
- 在线决策面:`agent/session.py`(`Observation` / `propose_orders`)
- 评估边界:`harness/evaluator.py`
- 上游静态挖掘原理:`proj/gold_corpus_mining.md`
- 动机脑洞:`proj/brainstorm/mine_skills_from_gold_kernels.md`
