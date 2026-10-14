# M3 步骤报告：纯重排引擎 RegionEditor（含 distribute_evenly 冷启动）

> 里程碑：**M3 重排引擎（纯）**
> 状态：**已完成**（76/76 测试通过，无 lint 错误；真实 kernel 重排安全可逆、未编辑无损）
> 日期：2026-06-04

---

## 1. 目标与验收门

在 M2 依赖图 + legal_window 之上，实现**纯重排引擎**：只改指令**顺序**，不改文本、不重算同步。
每步过 `legal_window`，返回可回滚 `Diff`。

**验收门（已达成）**：

1. 低层原语 `move_before` / `move_after` / `swap`，每步过合法窗口；非法 strict 抛 `IllegalMove`，
   非 strict 跳过并记入 `Diff.skipped`。
2. `lock_bundle` 把用户指定组粘成一个整体移动；m0 Bundle 自动作为整体移动（不被拆散）。
3. `set_gap_layout`（逐 MFMA 间隙异构放填充物）+ `distribute_evenly`（某类指令均匀铺到
   第 anchor_lo..anchor_hi 个 MFMA 间隙，冷启动一键重排）。
4. `Diff` 可回滚（`revert`）；`materialize` 把当前顺序回写 program；**未编辑时 emit 逐字节无损**。
5. **在真实 `testcase/` kernel 上**：未编辑 materialize 与原文件逐字节相等；`distribute_evenly`
   即便因手调 kernel 把 ds_read 钉死而跳过，也始终保持合法且完全可逆；存在可在窗口内成功移动的指令。

---

## 2. 交付物

```
testft/
  reorder/
    editor.py              # RegionEditor + Diff + IllegalMove
                           #   move_before/after/swap/lock_bundle
                           #   set_gap_layout/distribute_evenly
                           #   revert/is_legal/materialize
    depgraph.py            # 新增 fences() + is_order_legal(order, fences=可覆盖)
  tests/
    fixtures/coldstart_mfma.s   # 冷启动样例: 5 条 MFMA 累加链 + 4 条游离 ds_read
    test_editor.py              # 冷启动/低层原语/bundle/真实 kernel(19 例)
```

---

## 3. 设计要点

### 单元（unit）= 单指令或 bundle，整体移动
`unit(iid)` 返回与 iid 必须同动的连续块（其 m0 Bundle 或自身）。所有移动以**单元为粒度**，
m0 Bundle（`s_add m0` + `buffer_load ... lds`）天然不被拆散。

### 单条移动的合法性 = 单元的插入窗口
`_block_insert_range(members)` 在"去掉该块"的序列里算出可重插入的下标区间 `[lo, hi]`：
- 依赖：每个块外直接前驱 → `lo`；块外直接后继 → `hi`；
- fence：块当前所在的 fence 段（被最近的左/右 fence 夹住）。

单元移动到窗口内的任何位置都合法（只有该单元动，其余相对序不变，故所有边继续满足）。

### materialize：固定脚手架模型
区内**指令行**按新顺序回填到它们原来的行槽位，**非指令行（标签/空行/注释）原位不动**。
`Line.idx` 作为稳定 ID 不重编号，emit 只按列表顺序输出 → 未编辑时逐字节无损。

### 冷启动放开 waitcnt fence
M2 把现有 `s_waitcnt` 保守当 fence。`RegionEditor(treat_waitcnt_as_fence=False)` 用于冷启动：
此时指令可跨越旧 waitcnt 自由重排（同步将由 M4 `WaitcntRecomputePass` 重算）。`is_order_legal`
接受 fence 覆盖集，保证合法性判定与编辑器选择一致。

---

## 4. distribute_evenly 实测（冷启动 fixture）

输入（5 条 MFMA 累加链在前，4 条游离 ds_read 在后）：

```
mfma mfma mfma mfma mfma  ds ds ds ds  (endpgm)
```

`distribute_evenly(Kind.DS_READ, 0, 4)` 后（4 个间隙各 1 条，合法、ACC 链保序）：

```
mfma ds mfma ds mfma ds mfma ds mfma  (endpgm)
```

---

## 5. 真实 kernel 行为

- **未编辑 materialize**：与原 1120 行 shader **逐字节相等**。
- **distribute_evenly(ds_read)**：该 kernel 已手工调度，24 条 ds_read 被 barrier + 依赖
  钉在各自消费 MFMA 附近（如某 ds_read 窗口 `[5,8]`：前驱在 4、消费 MFMA 在 9），
  故整段重铺时被安全跳过；引擎**保持合法且 `revert` 完全还原**——验证了"非法即跳过、绝不破坏"的契约。
- **窗口内移动**：仍存在可成功重定位的指令，移动后 `is_legal()` 为真；materialize→reparse 指令数不变。

> 这正是 legal-by-construction 的预期：对已优化 kernel，激进重排被依赖/屏障挡住而空转；
> 对冷启动 kernel（fixture），`distribute_evenly` 一键铺开。M4 放开 waitcnt 重算后，
> 真实 kernel 的可重排空间会进一步增大。

---

## 6. 测试

`python3.8 -m unittest discover -s tests` → **76 passed**（M0 18 + M1 27 + M2 17 + M3 14）。

- 冷启动 fixture：distribute 交错、可逆、materialize 后可重解析。
- 低层原语：合法 move_after 生效；非法移动（破坏 MFMA ACC 链）strict 抛错 / 非 strict 跳过；
  fence（s_endpgm）不可移动；独立指令 swap。
- bundle：m0 Bundle 整体移动后 setter 与 load 仍相邻；`lock_bundle` 粘合用户组。
- **真实 kernel**：未编辑无损、distribute 安全可逆、窗口内可移动、编辑后可重解析。

---

## 7. M3 边界与遗留（交给 M4）

- M3 只改顺序，**不重算 waitcnt、不插 nop、不编译**。M4 `passes.py`（FixupPass/PassPipeline）+
  `waitcnt.py` 通用重算 + `isa/gfx942/passes.py`（WaitcntRecomputePass / ForcedNopPass）+ `Verifier`
  接管同步重算与合法性兜底；`harness` 三阶段评测 + `analysis` 瓶颈方向端到端跑通 core loop。
- `materialize` 后 `Line.idx` 不再等于列表位置（idx 是稳定 ID）；如需对已编辑 program 再分析，
  应重新 parse（M4 流水线按"编辑→materialize→emit→重 parse→pass"组织即可）。
- `distribute_evenly` 余数默认靠前分配；如需靠后/自定义，后续可加 `remainder` 选项。
