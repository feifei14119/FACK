# M2 步骤报告：通用依赖图框架 + gfx942 建边规则 + legal_window

> 里程碑：**M2 依赖图**
> 状态：**已完成**（62/62 测试通过，无 lint 错误；真实 kernel 三区全部建图、窗口自洽）
> 日期：2026-06-04

---

## 1. 目标与验收门

在 M1"读懂语义"之上，建立**架构无关的依赖图框架**与**每条指令的合法移动窗口**，
为 M3 重排引擎提供 legal-by-construction 的判定基座。

**验收门（已达成）**：

1. `reorder/depgraph.py` 通用框架：`Node`/`DepGraph`/`add_edge`/`preds`/`succs`/
   `legal_window`/`mark_fence`，**零 ISA 知识**。
2. 全部边类型（RAW/WAR/WAW/MEM/M0/ACC/FENCE）由 `isa/gfx942/edges.py` 提供。
3. m0 Bundle（`s_add m0` 紧贴其 `buffer_load ... lds` 消费者）正确成对。
4. MFMA 写回**不计任何 memory counter**，累加链只用 ACC/RAW 边保序。
5. `legal_window` 受 fence（barrier / exec 写 / 分支 /（保守）现有 waitcnt）夹紧。
6. **在真实 `testcase/` kernel 上**建图：prologue/loop/epilogue 三区全部成功，
   所有指令满足 `lo ≤ pos ≤ hi`。

---

## 2. 交付物

```
testft/
  reorder/
    depgraph.py            # Node / DepGraph / add_edge / preds / succs /
                           #   mark_fence / legal_window / build(instr_lines,target)
    regions.py             # 新增 region_instr_lines(program, region) 提取区内指令行
  isa/gfx942/
    edges.py               # build_edges(target,nodes,graph) 全部边规则 + bundles()
    classify.py            # 新增 implicit_defs/uses(scc) + reads_m0 + writes_exec
                           #   + has_register_dest(精确目的判定，修 def/use 正确性 bug)
    target.py              # def_use() 合成显式+隐式操作数; build_edges/bundles 接入
  tests/
    test_depgraph.py       # 合成用例 + fixtures + 真实 kernel 三区(18 例)
```

---

## 3. 建边规则（gfx942，`edges.py`）

单趟正序扫描区内指令，维护 `last_def` / `readers` / 内存状态 / m0 状态 / MFMA 累加表：

- **RAW/WAR/WAW**：基于 `def/use` 寄存器单元集（含隐式 `scc`）。`m0` 不走通用寄存器
  通道，专由 M0 规则处理（边带 M0 类型而非 RAW/WAR/WAW）。
- **MEM（保守别名）**：按地址空间分离 `vmem` / `lds` / `smem`；load 之间可互换，
  任何 store 与同空间的所有访问保序。`buffer_load ... lds` 同时算 **vmem-load + lds-store**。
- **M0（即 m0 Bundle）**：`s_add/s_mov m0`（LDS 写偏移）→ 其 `buffer ... lds` 消费者（RAW），
  消费者 → 下一个 m0 写者（WAR），m0 写者 → 下一个 m0 写者（WAW）。
- **ACC**：连续写同一累加器的 MFMA 链。**MFMA 写回靠 scoreboard，不进 counter**，
  排序仅由 ACC/RAW 边承担（与 M1 `WaitType.NONE` 一致）。
- **FENCE（以位置标记，非 O(n²) 边）**：`s_barrier` / `exec` 写者 / 分支 /（M2 保守）
  现有 `s_waitcnt` 标为 fence，`legal_window` 据此夹紧、且 fence 本身被钉死。

## 4. legal_window 语义

```
若 iid 是 fence       -> (pos, pos)             # 钉死
否则 lo,hi = 所在 fence 区间
       lo = max(lo, 每个直接前驱.pos + 1)
       hi = min(hi, 每个直接后继.pos - 1)
```
只用**直接**前驱/后继即足够（图与当前顺序一致时，传递前驱已被直接前驱覆盖）。

---

## 5. 修正的正确性缺陷：def/use 目的判定

M1 的 `parse_operands` 用"operand[0] = 目的"的粗启发式。M2 发现这在两类指令上**会漏掉读**
（漏读 = 漏 RAW 边 = 不安全，可能把消费者排到生产者之前）：

- `s_cmp_* / s_cmpk_* / s_bitcmp*`：operand[0] 是**比较源**，只隐式写 `scc`。
- `s_store* / s_buffer_store*`（SMEM）：operand[0] 是**待存数据**（源）。

新增 `classify.has_register_dest(opcode, kind)` 精确判定 operand[0] 是否为写寄存器：
store/ds_write/分支/barrier/nop/waitcnt 无寄存器目的；SMEM 仅 `s_load*`/`_rtn` 有；
SALU 中 `s_cmp*` 无；其余（load/ds_read/valu/mfma/set_m0）有。修正后 `s_cmp s50, s76`
正确地把 `s50` 当**读**、`scc` 当写。（过度标 def 仅多加边、安全；漏标 def 才危险——本修复消除后者。）

真实 kernel loop 区 RAW 边因此从 792 升到 822，三区窗口仍全部自洽。

---

## 6. 在真实 kernel 上的结果

| 区 | 指令数 | 边数 | RAW | WAR | WAW | MEM | M0 | ACC | bad_window |
|----|-------:|-----:|----:|----:|----:|----:|---:|----:|-----------:|
| prologue | 426 | 1486 | 645 | 397 | 395 | 15 | 34 | 0 | 0 |
| loop | 451 | 2365 | 822 | 854 | 457 | 70 | 70 | 92 | 0 |
| epilogue | 140 | 340 | 148 | 96 | 74 | 22 | 0 | 0 | 0 |

- loop 区识别出 24 个 m0 Bundle（每个 = 1 个 `s_add m0` + 其 `buffer_load ... lds` 消费者），
  92 条 ACC 边（MFMA 累加链），19 个 fence（waitcnt + barrier）。
- 全部三区每条指令满足 `lo ≤ pos ≤ hi`（原序天然合法，重排有可用空间）。

---

## 7. 测试

`python3.8 -m unittest discover -s tests` → **62 passed**（M0 18 + M1 27 + M2 17）。
按用户要求，M2 测试**不止跑 tests/ 的简单 kernel**，还在 `testcase/` 真实 shader 上：

- 合成用例：RAW/WAR/WAW、隐式 scc 链、compare/store 的 operand[0] 是源、
  MEM(store→load 保序 / load-load 可换)、MFMA ACC 链、m0 边+Bundle、barrier 钉死与禁跨越。
- fixtures：gemm loop 建图含 ACC、窗口自洽。
- **真实 kernel**：三区建图、边类目齐全、窗口全自洽、m0 Bundle 头是 m0 写者且成员含 lds-load、
  MFMA `WaitType.NONE`、fence 存在。

---

## 8. M2 边界与遗留（交给 M3+）

- M2 只建图、给窗口，**不移动任何指令**。M3 `editor.py` 用 `legal_window` + `bundles`
  实现 `move_*/swap/lock_bundle/set_gap_layout/distribute_evenly`，返回可回滚 Diff。
- 现有 `s_waitcnt` 在 M2 被保守当作 fence；M4 `WaitcntRecomputePass` 接管重算后将放开，
  允许跨越旧 waitcnt 重排（waitcnt 由 pass 删除并重新生成）。
- def/use 仍是"operand[0] 目的 + 隐式 scc/m0"的近似；少数特殊写法（`v_cmpx` 写 exec、
  多目的指令）后续按需细化（过度标 def 安全，不影响正确性）。
