# 脑洞：anchor-less 区 `propose --order` 传全量 order 的性能塌方

> **落地状态（见 `proj/large_dag_prologue_finetune.plan.md`）**：A（提示词：anchor-less 默认部分 order +
> 禁止全量）、C（长度护栏：`AgentSession.max_order_intent` 默认 64，超限 O(1) 拒绝并回 `error` 提示）、
> B（引擎降复杂度：`RegionEditor._pos()` 位置缓存替换热路径 `self.order.index()`，`propose_orders`
> 大序亚秒级返回）**均已实现**，配套单测在 `unittests/test_editor.py` / `test_session.py`。

> 类型：brainstorm（问题记录 + 优化备选，非现状设计、非已落地方案）。
> 命题：在 **anchor-less 区**（prologue/epilogue/inter，无 MFMA 锚点）调优时，agent 第一反应是构造一个
> **覆盖整段区域的全量线性 order**（本例 prologue 有 **426 个 DAG 节点**）丢给 `propose --order`，结果
> **单次 propose 卡 8 分钟以上**，把一轮调优从分钟级拖到 20+ 分钟。
>
> 本篇记录这个真实复现的问题、根因，以及几种并存的优化备选，供后续取舍。**这是性能/易用性问题，不是正确性问题**
> ——裁决与归档始终正确。

---

## 0. 一句话结论

**anchor-less 区的 `propose --order` 应以"部分 order"（只列要移动的少量 iid）为默认用法**，并在引擎侧把
`propose_orders` 的实现复杂度从当前的 ~O(n²) 降下来；二者任择其一即可缓解，二者都做最稳。在此之前，**禁止 agent 对
大区域构造全量 order** 是性价比最高的止血手段（纯提示词，零引擎改动）。

---

## 1. 复现与现象

- 用例：`tune_quick.sh`，`REGION=prologue`，testcase = `tune_case/poc_gemm/gemm.exe`（m=256 n=256 k=512）。
- prologue 是 anchor-less 区（无 MFMA），observe 返回的是 `dag`（426 个节点），agent 需要用 `--order` 做依赖重排。
- agent 首个动作：把**全部 426 个 iid** 排成一个完整 order 调 `propose --order "[...]"`。
- 结果：**单次 propose 运行 > 8 分钟仍未返回**。transcript 中 agent 自述：

  > "The full-order search space contains 426 elements, making each proposal attempt very slow... I will kill it
  > and try partial orders instead."

- agent 自行 kill 掉卡住的 propose，改用**部分 order**（如 `[351, 393]`、`[351, 393, 394]`），propose 立刻恢复秒级，
  随后正常完成 9 次 eval、产出 +1.00% 的最佳方案。
- 代价：整轮耗时 **~23 分钟**（对比 loop 区的同规模运行约 16 分钟），多出来的时间几乎全耗在那次全量 order 的 propose 上。

---

## 2. 根因（引擎侧）

慢点在 `reorder/editor.py::Editor.propose_orders`。它对 intent 里**每一个** iid 顺序执行：

```python
for f in intent:                       # 全量时 len(intent) = n（本例 426）
    ...
    win = self._window_with_cause(self.unit(f))[:2]   # 扫描合法窗口
    d = self.move_after(f, prev, strict=False)        # 在 order 列表里移动元素
    after_prev = self.order.index(f) > self.order.index(prev)  # 两次 list.index → 各 O(n)
```

- `self.order.index(f)` / `self.order.index(prev)`：Python list 线性查找，**各 O(n)**，每个 iid 调两次。
- `move_after` 在底层 list 上做插入/删除（元素搬移），本身也是 **O(n)** 量级。
- `_window_with_cause` 计算合法窗口同样要扫依赖。

合起来，对**全量** order 是 **~O(n²)**（甚至更高）。n=95（loop 那种小区）时无感，n=426 时直接塌方到分钟级。
**部分 order**（n'≈2~13）则把代价压回到可忽略，这正是 agent 改用部分 order 后立刻恢复的原因。

> 注意：这是**纯算法复杂度**问题，不涉及真机评测。propose 本身是 GPU-less 的合法性/代价预检；卡住的全程没有跑硬件，
> 纯粹耗在 Python 列表操作上。

---

## 3. 优化备选（可并存，按性价比排序）

### A. 提示词止血：anchor-less 区默认用"部分 order"（零引擎改动，强烈建议先做）

在 `tools/sdk/tune.mjs` 给 anchor-less 区的提示词里加一条硬规则：

> 对 anchor-less 区，**只把你要移动的少量 iid 列进 `--order`**（典型 2~15 个），未列出的指令保持相对顺序自动填充。
> **禁止**构造覆盖整段区域的全量 order——这会让 propose 极慢。

收益：立刻消除塌方；不依赖引擎改动。缺点：靠模型遵守，属软约束。

### B. 引擎降复杂度：`propose_orders` 去掉 O(n) 的 `index()` / 搬移（治本）

- 维护一个 `iid -> 当前位置` 的 dict，替换 `self.order.index(...)`，把每步从 O(n) 降到 O(1)。
- 用更适合频繁移动的结构（如基于位置键的有序结构 / 链表 + 位次缓存）承载 `move_after`，避免每次 O(n) 搬移。
- 目标：全量 order 也能在亚秒级返回，使"部分/全量"都可接受。

收益：治本，agent 怎么用都不塌方。缺点：要动 `editor.py` 核心数据结构，需配套单测（`test_editor.py`/`test_session.py`）。

### C. 规模软超时 / 告警（兜底护栏）

在 `propose` 入口对 `len(intent)` 设阈值（如 > 64）：

- 要么直接拒绝并返回结构化提示"order 过长，请改用部分 order（建议 ≤ N 个 iid）"；
- 要么加超时（如 30s）中断并回同样提示。

收益：即使模型或脚本误用全量 order，也能秒级失败而非干等 8 分钟，且给出可执行的纠正建议。缺点：是护栏不是治本。

---

## 4. 建议落地顺序

1. **A（提示词）+ C（软超时/告警）** 先做：成本极低，立刻把"等 8 分钟"变成"秒级纠正"。
2. **B（引擎降复杂度）** 视后续真实大区域调优的频率再投入：如果以后经常调 prologue/epilogue/大 inter 区，
   B 的收益最大；只要把 `index()` 换成位置 dict，复杂度问题大概率就解决。

> 关联文档：`proj/testcase_integration.md`（testcase 无关红线）、`proj/brainstorm/mcp_decision_surface.md`
> （决策面形态）。本问题只触及 `reorder/editor.py` 与 `tools/sdk/tune.mjs` 提示词，引擎其它部分零改动。
