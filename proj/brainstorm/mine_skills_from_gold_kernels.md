# 脑洞：从已优化（roofline 级）kernel 语料中挖掘调优 skill，并按区域分块学习

> 类型：brainstorm（头脑风暴 + 落地备选，非现状、非已落地设计）。
> 命题：如果手上有几十~几百个**人工手工调优、性能已达 roofline** 的 kernel，能否通过阅读/分析它们，
> **总结出调优 skill**，用来指导后续其它**未优化 kernel** 的指令调优方向？并且——这些 gold kernel 本就按本项目
> 的分块方式（**入循环 prologue / 循环体 loop / 出循环 epilogue**）分别优化，三块策略不同，能否**按区域分块**
> 总结学习？
>
> 结论先行：**都可行，而且不必另起炉灶**——把 gold kernel 当作"合成实验"喂进现有
> `experiments.log → induce_skills → seed_search_plan` 管道即可；`region` 在现有 skill 体系里**已是一等作用域键**。
> 关联：`agent/knowledge.py`（Skill/seed_search_plan/induce_skills）、`proj/knowledge_agent_design.md`（知识只导航纪律）、
> `proj/brainstorm/large_dag_finetune.md`（挖出的模式可直接喂"自动候选生成器"）。

---

## 0. 一句话结论

**可行，难点在"从优化终态还原出可迁移、按特征条件化的导航先验"，而非裁决。** gold kernel 是优化的**终态**而非**过程**，
所以要么抽静态调度签名、要么用合成基线还原 move。挖出的 skill **永远只导航、不裁决**（合法性靠引擎、性能靠真机），挖错了
只浪费预算、不会产出坏 kernel。三块（prologue/loop/epilogue）策略不同、**词汇也不同**，应按区域分别抽特征、产出
region-scoped skill；少数跨区域策略（软件流水）单列一个 span 作用域。

---

## 1. 一个"已优化 kernel"里到底有什么信号

关键认知：**成品 kernel 是优化的"终态(end state)"，不是"过程(moves)"。** 看到的是最终调度，看不到人怎么一步步调过来的。
提取信号有两种模式：

### 模式 A：静态结构模式（只看成品 .s）
对每个 gold kernel 跑引擎现有分析器（`regions`→CFG、`depgraph`→DAG、`waitcnt`、`cost`），抽一组**调度签名
(schedule signature)** 特征，例如：
- global load 相对其 use 的**前移距离**分布；prefetch 的 hoist 距离；
- MFMA 间隙的**填充模式**（每个 gap 填几条、填什么 kind、均匀 vs 非均匀）；
- **同计数器 async 聚簇度**："平均每个 waitcnt 排空多少笔 load"（一拍盖多发）；
- ds_read/ds_write 与 MFMA 的交织比例。

纯从终态可观测，是"好 kernel 长什么样"的统计画像。

### 模式 B：监督式"还原 move"（成品 + 合成基线）
更强的一招：用引擎的 `make_candidate` even-distribution（它本就是"把按类型聚堆的冷 kernel 摊开成可用种子"的引导器）
**反向合成一个朴素基线**，再 `diff(gold, naive)` **还原出人做过的变换**。

- 得到一对 **(朴素基线 → gold) 的有标注样本**，等价于一次"成功的实验"。
- **妙处**：把它 `log_experiment` 写进现有 `experiments.log`，就能**直接复用现成的 `induce_skills`** 管道归纳成 skill
  ——语料挖掘变成"合成实验"喂给同一个归纳器，零新增归纳逻辑。
- **注意**：同一终态可能对应多条变换路径，diff 还原只是一种合理重构，不是唯一真值。

---

## 2. 如何变成现有 Skill（导航式、testcase 无关）

现有 `Skill` schema 已经够用，挖出的模式要落成它的形态才能即插即用：

```
when: Dict       # scope/applicability filter（适用范围）
action: Dict     # {"specs":[...]} | {"avoid":[...]} | {"note":...}（动作）
evidence: Dict   # {kernels:[...], shapes:[...], n_samples:int}
effect: Dict     # {mean_delta:float, win_rate:"k/n"}
confidence: float; status: "candidate" -> "trusted"
```

- **`when`（适用范围）**：必须用**可观测特征**做条件——`arch`/`region`/`loop_kind`/`bottleneck`/`dtype`/计数器类型。
  **绝不能**绑定具体 shape 或 kernel 名（否则破 testcase 无关红线、且无法迁移）。
- **`action`（动作）**：必须落到引擎已有词汇——`listsched` 权重预设（`critical_path`/`latency`）、gap-fill layout 模式、
  order 启发式、hoist 距离先验。这正是 `seed_knowledge.py` 已在做的"权重配置↔性能"映射。
- **`evidence`/`effect`/`confidence`/`status`**：记录由哪些 gold kernel 支撑、几例、效果多大；走现有的
  `candidate→trusted` 晋升闸门（≥2 个独立 kernel、≥3 样本）。

挖出的 skill 通过 `seed_search_plan` 在**开跑前**变成一份**有序候选先验**注入搜索/agent——只导航"先试什么"，引擎仍逐个用
正确性 + 真机噪声门裁决。

---

## 3. 按区域分块学习（用户补充的重点）

### 3.1 现有代码已支持"按区域分别学习"
`induce_skills` 的分组键里**本来就含 `region`**：

```python
key = (r.get("arch"), r.get("loop_kind"), r.get("bottleneck"),
       r.get("scenario"), r.get("region"), _transform_id(r["transform"]))
```

`Skill.when` 的 scope 也带 `region`，`seed_search_plan` 按 context 过滤。于是：

- 调 `region=prologue` 时，**只有 prologue 作用域的 skill 被激活**，loop/epilogue 的 skill 不会误用。
- "三块各有策略"正好对应**三组互不串扰的 skill**。基础设施已在，缺的只是"按区域抽取 gold 的不同特征"。

### 3.2 三块策略不同，连"词汇"都不同
项目提示词里的**两套词汇**正好沿区域划分：

| 区域 | 类型 | 调优词汇 | 典型人工策略（可挖掘方向） |
|---|---|---|---|
| **入循环 prologue** | ANCHOR-LESS（无 MFMA） | `--order`（依赖重排） | 首批 global load 尽早前移、在首个 barrier/lgkm wait 前聚簇、prefetch/地址准备摊开——"循环前把访存铺出去" |
| **循环体 loop** | ANCHORED（有 MFMA） | `--layout`（填 MFMA 间隙） | 间隙填访存、软件流水（算当前拍同时 prefetch 下一拍）、同计数器聚簇一拍盖多发、ds_read/write 与 MFMA 交织——"喂饱 MFMA、访存与计算重叠"。**est_share 最高、杠杆最大** |
| **出循环 epilogue** | ANCHOR-LESS | `--order` | 高效 drain、写回/归约排布、不再 prefetch——"把结果尽快排空写出" |

因为**动作空间天然按区域不同**，挖掘器也应**按区域抽不同特征向量**：prologue 看"前移距离/load 聚簇度"，loop 看
"间隙填充模式/流水深度/计数器聚簇"，epilogue 看"store 排布/drain 效率"。

### 3.3 分块学习的好处：迁移性更强
**"策略"比"具体调度"更普适**：具体 hoist 距离随 shape/trip_count 变、难迁移；但"循环体让访存与 MFMA 重叠"
"prologue 前置首批 load""epilogue 不做 prefetch"这类**区域级策略**跨 kernel 高度稳定，**最适合做成 region-scoped
的 trusted skill**。挖掘时按 region kind 分组聚合 → 得到"prologue/loop/epilogue 三张策略画像"，各落成
`when={region: ...}` 的 skill。

### 3.4 要留意：跨区域协同
三块独立学习覆盖大部分策略，但有些优化是**跨区域**的——典型是**软件流水**：prologue 发首拍 prefetch，loop 体消费并发
下一拍。纯单区域学会丢掉这种耦合。

- 建议：默认按三块独立学习（简单、可迁移），但保留一个**"跨区域/span"作用域**的 skill 类型
  （如 `when={region:"prologue+loop", pattern:"sw_pipeline"}`）专收协同策略。这呼应主 plan 里 `p4-span`
  （span_editor 跨尾段协同）那条暂缓任务——分块学习成熟后可再激活。

---

## 4. 两条学习回路如何互补

```
离线语料挖掘（本篇）              在线主动调优（现有体系）
gold kernel 语料                  未优化 kernel 的 observe→eval 实验
  │ 静态签名 / 还原 move（按区域）    │ 真实 transform→delta
  ▼                                 ▼
合成实验 → log_experiment ──┐    ┌── experiments.log
                            ▼    ▼
                      induce_skills（同一归纳器，按 region 分组）
                            │
                      agent/store/skills（人工审核晋升）
                            │
                      seed_search_plan（开跑前按 region 注入先验）
```

- **离线**给广覆盖的**正向先验**（哪个区域重要、哪类变换、权重预设、大致 hoist 距离）——快速冷启动。
- **在线**负责**验证 + 补"避免"知识**（gold 只有成功样本，学不到失败模式；在线实验补 `avoid`）。
- 两者汇入**同一个 skill 库 + 同一个注入口**，自然融合。

---

## 5. 能做到什么、做不到什么（诚实边界）

**能**：
- 给**方向性先验**：优先调哪个区域（配合 `est_share`）、先试哪族变换、list-sched 权重起点、gap 填充/聚簇风格、
  hoist 距离量级 → **砍搜索预算、提高首发命中率**。
- 直接喂给 `large_dag_finetune.md` 的"方向 4：引擎自动出种子候选"——gold 挖出的模式就是最好的候选生成器。

**做不到 / 风险**：
- **不替代裁决**：skill 只导航，合法性靠引擎、性能靠真机；挖错只浪费预算，不产坏 kernel。
- **迁移有限**：gold 对**自身 shape/arch/dtype** 最优，须按特征条件化，跨域要重新验证。
- **幸存者偏差**：成品只展示成功终态、无失败空间，单靠它学不到"别做什么"——需在线实验补。
- **还原 move 有歧义**：同一终态可能对应多条变换路径（见 §1 模式 B）。

---

## 6. 建议落地路径

1. **先做模式 A（静态签名，按区域）**：写 `tools/mine_corpus.py`，批量跑分析器、**按 region 抽各自调度签名**、
   按特征聚类，产出 `candidate` skill 草案——纯读取、零风险，先看能挖出什么规律。
2. **再做模式 B（合成实验）**：用 `make_candidate` 造朴素基线、diff 还原 transform、`log_experiment` →
   复用 `induce_skills`（已按 region 分组）。让语料直接接入现有晋升闸门。
3. **人工审核晋升**：按现有约定，把审核过的 skill 从 `study_out` 复制进 `agent/store/skills`。
4. **闭环验证**：在几个**故意未优化**的 kernel 上开 `seed_search_plan`，对比"有先验 vs 无先验"的预算消耗与首发命中率，
   量化 skill 价值。
5. **成熟后再上 span 作用域**：当三块独立 skill 稳定，激活跨区域协同（软件流水）的学习与 `p4-span`。

---

## 7. 已落地：Mode A 静态挖掘器（`tools/mine_corpus.py`）

第一期已实现 **Mode A（静态、零真机、零风险）**，作为 §1 模式 A 与 §3 按区域学习的落地：

- **入口**：`bash study_case/study_script/mine_skills.sh`（或 `python3.8 tools/mine_corpus.py [--corpus DIR] [--out DIR]`）
  - `--corpus` 默认 `study_case/gold_corpus/`（可指向任意外部路径）；每个 kernel 一个子目录（含 `*.s`，`kernel.s`
    优先）+ 可选 `meta.json` 边车；也支持 corpus 根目录下的裸 `*.s` 文件。
  - `--out` 默认 `study_case/study_out`，产物：`skills/gold-<class>-<region>.json` + `mine_report.md`。**不触碰
    `agent/store`**；人工审核后再手工晋升。
- **kernel 无关红线（已落实）**：所有特征只来自语义 `Kind` 直方图 + CFG 区域 + 依赖 DAG，**无任何 GEMM/shape 假设**；
  原先写死的 `loop_kind="mfma_dense"` 由 `classify_kernel` 通用结构分类器推导
  （`mfma_dense`/`mfma_sparse`/`lds_bound`/`memory_streaming`/`vector_only`/`mixed`），`meta.json` 可覆盖
  （`kernel_class`/`family`/`arch`）。
- **按区域产出**：每个区域抽调度签名（Kind 占比、anchored 与否、vmem-load hoist 距离、MFMA gap 填充模式与均匀度、
  waitcnt 聚簇度、prefetch 数），再经**区域感知映射**给出各自策略的候选 spec（loop→填 gap/聚簇访存；prologue→前置
  首批 load/hoist scalar；epilogue→按依赖 drain、不 prefetch），复用 `search.driver.build_candidate` 词汇。
- **安全**：产出**一律 `status="candidate"`**，Mode A 永不自动晋升 `trusted`（需 Mode B/在线真机佐证）；`when` 仅含
  `{arch, loop_kind, region}`，断言不含 shape/kernel 名（见 `unittests/test_mine_corpus.py`，含非 GEMM 的
  `kvadd_style.s`）。
- **后续（Mode B，未做）**：合成朴素基线 + diff 还原 move + 真机测量入 `experiments.log` → 复用 `induce_skills`
  晋升 `trusted`；以及跨区域 span 协同。

> 关联文档：`proj/knowledge_agent_design.md`（知识只导航、晋升闸门、自演化防污染）、
> `proj/brainstorm/large_dag_finetune.md`（自动候选生成器消费这些先验）、
> `proj/testcase_integration.md`（testcase 无关红线）。
> 涉及代码：`agent/knowledge.py`（Skill/when.region/seed_search_plan/induce_skills 已按 region 分组）、
> `tools/seed_knowledge.py`（权重↔性能映射）、`tools/make_candidate.py`（合成朴素基线）、
> `reorder/regions.py`（CFG 分区）、`reorder/depgraph.py`+`search/list_scheduler.py`（DAG/关键路径/分段，签名提取依赖）。
