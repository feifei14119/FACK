# 脑洞：用 Transformer / QKV attention 指导指令重排优化方向

> 类型：brainstorm（头脑风暴，非现状、非已落地设计）。
> 命题：Transformer 借 QKV attention 取得极好效果，testft 能否也用 QKV 的方式，
> **利用硬件信息 + 计算输入 tensor 尺寸（shape）来指导指令重排的优化方向**？
>
> 本篇是 `core_loop_scheduler_design.md` / `if/ai_interface.md` / `knowledge_agent_design.md` 的延伸思考：
> 前者讲"固定逻辑怎么合法重排 + LLM 怎么逐轮 observe→propose→commit"，本篇探讨**把 propose 这一层换成/补充成一个 attention 策略网络**。

---

## 0. 一句话结论

**能，而且 QKV/attention 几乎为这套架构量身定做——但它只能进"导航 / proposer"这一层，绝不能碰"裁决合法性"那一层。**

现有闭环：

```
observe（事实地图）→ propose（出 layout 意图）→ commit（引擎重算 + Verifier + 真机裁决）
```

LLM / 启发式现在站在 `propose` 位置。把 propose 换成/补充成一个 attention 策略网络，是顺理成章的替换——
合法性仍由 `legal_window` / `Verifier` / 真机三层兜底，与"知识只导航、不裁决合法性"的核心纪律 100% 一致。

---

## 1. 为什么是 attention（而不是普通 MLP / 规则）

问题本质有三个特征，恰好都是 attention 的强项：

1. **依赖图 = 天然的 attention 邻接矩阵**。已有的 `graph.preds/succs`、`graph.dist(a,b)`、
   `latency_edges()`、`legal_window`、`is_fence`，恰恰就是图注意力（Graph Attention）里的
   **边偏置 / 掩码**。让指令互相 attend、并用 DAG 边给注意力打 bias，模型就"看得见"和引擎一样的结构。
2. **变长集合**。不同 kernel / shape 下 loop 指令数、MFMA slot 数都不同。attention 原生吃变长 token 集合，
   不像模板 / 全局旋钮（`core_loop_scheduler_design.md` §2 已否决参数化模板）。
3. **全局条件化**。硬件信息 + tensor shape 是"全局上下文"，attention 用 cross-attention 或全局 token
   把它注入每条指令的决策——这正是"用硬件信息和输入 tensor 尺寸指导方向"。

---

## 2. QKV 的具体映射（核心脑洞）

把三类东西都变成 token：

| token 类别 | 来源 | 特征示例 |
|---|---|---|
| **指令 token** | `ed.order` 每个 iid | `kind`(mfma/vmem_load/ds_read/valu…)、`legal_window=(lo,hi)`、`movable`、`is_prefetch`、当前 slot、累加链 id |
| **slot token** | `ed.anchors(Kind.MFMA)` 的间隙 | slot 序号、当前填充物画像、容量富余 |
| **上下文 token** | 硬件 + shape + direction | 见 §3 |

QKV 这样分：

```
Query  (Q): "一个待决策" —— 每条可动指令 / 每个 MFMA 间隙 slot
Key    (K): 候选落点 / 其它指令 / 上下文 token —— "有什么、相关吗"
Value  (V): 被携带的内容 —— 指令语义 / slot 容量 / 硬件约束向量
注意力分数 = 学到的相关性  +  DAG 边偏置(dist / latency / fence / window)
输出 → 每个落点的 logits（用 legal_window 掩码）→ layout 意图 → 引擎 commit
```

**关键一招**：用 `legal_window` 当 attention / 输出掩码，模型在物理上就只能 attend / 输出到合法位置
→ "legal-by-construction 的提案"。非法的它根本算不出来，剩下的越界由 `propose_layouts` 的 `SkipReason` 兜。

---

## 3. 硬件 + shape 如何"指导方向"（shape 自适应）

`anchorless_region_scheduling.md` 已手写"目标函数 shape 自适应"（小 trip 看尾段、大 trip 靠代价模型）。
**attention 可以把这条手写规则变成学出来的条件化**。

**上下文 token 的内容**（即"硬件信息 + tensor 尺寸"的落点）：

- **硬件**（来自 `isa/Target`，架构常量）：MFMA 回写延迟表、counter 位宽 / 深度
  （vmcnt / lgkmcnt / expcnt / vscnt）、LDS 大小、VGPR/SGPR 数、带宽、CU 数。
- **shape**（来自 testcase 启动参数）：`M/N/K/sub_m/sub_n/ks`、**trip count**、dtype(fp8)、
  由 shape 推出的**算术强度**（先验地提示 memory-bound 还是 compute-bound）。
- **反馈**：`direction` 投票（bottleneck / share，当噪声先验）。

让指令 / slot 的 Q 去 **cross-attend 上下文 token**，模型能学到诸如：

- trip count 小（split-K / MLA decode）→ 自动抬高 **prologue / epilogue 区**编辑权重（各执行一次、占比大）。
- 由 shape 算出算术强度低（memory-bound）→ 倾向 hoist load、拉长预取距离。
- K 大 → 预算与注意力压在 loop 稳态。

这正是"用 tensor 尺寸指导优化方向"，且是**软的、可迁移的**：换 shape 不重训，靠 in-context 条件化即可——
这是 attention 相对硬规则的最大增量。

---

## 4. 四种候选架构（按"贴合度 / 落地风险"排序）

### ① 图注意力做 list-scheduler 的 priority 函数（最稳，先做）
`core_loop_scheduler_design.md` §4 机制 A 的 list scheduler 现用手调权重
`score = w1·critical_path + …`。把 score 换成一个**小图注意力网络**：输入就绪指令集 + DAG 边偏置 +
上下文 token，输出每条 priority。内层搜索仍是确定性贪心调度（保持"内层可复现"），只是打分器从线性权重
升级成 attention。风险低、改动小、直接吃现有接口。

### ② 指针网络解码器：直接生成合法排列（最优雅，中期）
decoder 逐步 emit 一个排列（= 一个合法拓扑序），每步用"就绪 + `legal_window`"做 action mask。
这就是组合优化里成熟的 Pointer Network，**天生 legal-by-construction**，emit 完引擎 `recompute_cfg`
重算 waitcnt、真机打分。与"引擎裁决合法性"哲学完美咬合。

### ③ Decision Transformer 吃 `experiments.log`（最有想象力，但需数据）
`experiments.log` 本质是离线 RL 数据集：`(state=observe, action=layout, return=TFLOPS delta, perf-counter)`。
用 Decision Transformer，**条件在"想要的 TFLOPS 提升"上**预测下一个 action。这是把 `knowledge_agent`
的"induce_skills 统计归纳"升级成"序列模型归纳"。**诚实讲：现在只有 ~12 条实测 / 1 个真实 kernel，
数据量远不够训 DT**——留到样本积累起来再上。

### ④ attention = 学出来的 skill 检索（最低风险的第一步）
`seed_search_plan` 现为"硬 scope 过滤 + trusted-first 排序"。换成**软注意力检索**：
Query = 当前 `(arch, shape, bottleneck)`，Key = 每条 skill 的 scope embedding，Value = skill 的 action 模板。
注意力权重 = 该 skill 现在多相关，天然带"置信度加权 + shape 相关性"，比硬过滤更平滑，可解释、可审计、改动极小。

**建议落地顺序**：④ → ① → ③（等数据），② 作为并行探索。

---

## 5. 训练数据 / reward 从哪来（真正的难点）

- **reward 信号已有**：真机 `tflops + correct`（强信号、慢 / 贵）+ `direction`（弱噪声先验）。
  引擎能"一秒上千合法候选"，真机度量当 reward → 现成的 RL 环境。
- **离线数据**：`experiments.log`（带 `decided_by`、perf-counter 摘要）就是回放缓冲。
- **真正的回报是"摊销 / 迁移"**：训一次，跨 shape、跨 kernel（GEMM 学到喂 MLA/MoE）复用——
  恰是 `knowledge_agent_design.md` 写的"跨 kernel 迁移复利"目标，也是 attention / in-context 的看家本领。
  **这才是值得上 transformer 的理由**；若只调一个固定 shape，退火 / 贪心就够，不必上模型。

---

## 6. 风险与必须守住的纪律

| 风险 | 对策 |
|---|---|
| 模型产出坏 kernel | **不可能**——合法性永远由 `legal_window` / `Verifier` / 真机裁决；模型只进 propose 层 |
| 破坏"内层可复现" | 内层搜索保持确定性；模型放**元层**当 proposer / prior（与现在 LLM 同位） |
| 数据饥饿 | 先用 attention 当**架构**（priority 函数 / 检索），用现有搜索数据训；DT 等样本够再上 |
| reward 噪声大 | 只用真机 tflops 当 reward，`direction` 仅作特征，绝不当目标函数（M6b 已验证，见 `if/direction_signal_validation.md`） |
| 过度工程 | 单 shape 场景不要上模型；只有要跨 shape / 跨 kernel 迁移时才值得 |

一句话纪律延续：**QKV 只导航，引擎裁决合法性。**

---

## 7. 一个最小可验证起点

不用一上来就 transformer。先做一个**单层 attention 的 priority 打分器**，挂到现有
`AgentSession` / list scheduler：

1. 特征：每条指令 `[kind one-hot, legal_window 宽度, movable, is_prefetch, slot]` + 全局拼
   `[shape 向量, 硬件常量, direction]`。
2. 一层 self-attention（QKV），attention bias = `dist(a,b)` / 是否 `latency_edge` / 是否 `fence`。
3. 输出 per-instr priority → 喂给确定性 list scheduler 生成布局 → 走**现成的**
   `propose_layouts → recompute_cfg → Verifier → evaluate` 管线打分。
4. 先用进化 / 退火更新 attention 权重（免梯度、规避数据少），验证"能否在 gemm 上稳定打过手调权重 +
   `distribute_evenly` 基线"。

跑通这个 → 得到 ①；再叠 shape 条件化（§3）验证"shape 真能指导方向"；最后才考虑指针网络 ② 和 DT ③。

---

## 8. 一句话总括

**把 Transformer 的 QKV attention 当"会读依赖图、能被硬件 / shape 条件化的 proposer"——
指令 / slot / 上下文(硬件+shape+direction) 三类 token 互相 attend，用 DAG 边做注意力偏置、
用 `legal_window` 做输出掩码，输出 layout 意图交引擎合法落位 + 真机打分。
它指导"先试什么方向"，绝不裁决"什么合法"。最大价值是跨 shape / 跨 kernel 的摊销迁移，
而非单 shape 调优。**
