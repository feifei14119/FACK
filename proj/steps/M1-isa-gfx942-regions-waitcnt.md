# M1 步骤报告：ISA 抽象层 (gfx942) + 区域识别 + 只读 waitcnt 校验

> 里程碑：**M1 ISA 抽象层落地 + CFG 区域切分 + 只读同步语义读取**
> 状态：**已完成**（45/45 测试通过，无 lint 错误；真实 1120 行 shader 跑通）
> 日期：2026-06-04

---

## 1. 目标与验收门

在 M0 无损解析的基础上，让引擎第一次"读懂"指令语义——但**只读、不改写**。

**验收门（已达成）**：

1. 第一个具体 `Target`（gfx942）实现并注册，核心层只经 `Target` 契约访问它，零处直接引用架构。
2. 操作数解析能把寄存器写法归一为 `RegSet`（含 `acc` ≡ AGPR、`.set` 别名展开）。
3. 操作码分类给出语义 `Kind` 与 `WaitType`（MFMA 走记分板，不计 waitcnt）。
4. 计数器模型能解析 gfx942 **三种** waitcnt 写法 + `s_waitcnt_vscnt`。
5. CFG / 基本块 / 回边自然循环 / 区域切分（prologue / loop / inter / epilogue），分支判定全部走 `Target`。
6. 只读 waitcnt 模拟能在真实 shader 上正确读出全部同步指令，无误报。
7. 修复 M0 遗留：`.amdgpu_metadata` 块内 YAML 行不再被误判为 label。

---

## 2. 交付物（文件清单）

```
testft/
  isa/
    counters.py                 # CounterModel 抽象基类 + WaitSpec
    registry.py                 # get() 改为按需 import isa.<arch> 自注册（懒加载）
    gfx942/
      __init__.py               # import 即向 registry 注册 "gfx942"
      operands.py               # 操作数 -> RegSet；s/v/a(acc)/特殊寄存器；.set 别名展开
      classify.py               # opcode -> (Kind, WaitType)；分支/终结/写 m0/lds-load 判定
      counters.py               # Gfx942CounterModel：vm/lgkm/exp/vs 位宽 + waitcnt 解析/格式化
      target.py                 # Gfx942Target：实现 Target 契约 + from_program(别名扫描)
  reorder/
    parser.py                   # 新增 .amdgpu_metadata 块透传（块内强制 OTHER）
    regions.py                  # CFG/基本块/回边找自然循环/切 N 区
    waitcnt.py                  # 只读 waitcnt 解析 + 计数器前向模拟（含 vscnt）
  tests/
    test_isa_gfx942.py          # operands / classify / counters / registry（21 例）
    test_regions.py             # 循环检测 / 区域顺序 / metadata 修复 / 真实 shader（6 例）
    test_waitcnt.py             # 解析 / 模拟 / vscnt / 真实 shader 三种写法（4 例）
  pyproject.toml                # packages 增加 "isa.gfx942"
```

---

## 3. 关键设计决策（与真实测试用例对齐）

在实现前先扫了真实 shader `fp8gemm_blockscase_32mx1_32nx4.s`，据此校正了若干假设：

- **`acc[..]` 即 AGPR**：真实 shader 用 `acc[0:1]` 而非 `a[0:1]`。`operands.py` 把 `a`/`acc`
  前缀统一归一到寄存器类 `'a'`，二者 `RegSet` 完全等价。
- **waitcnt 有三种写法**，全部支持并解码到统一 `WaitSpec`：
  - 裸立即数 `s_waitcnt 0x0000`（按 gfx9/CDNA simm16 位域解码：vm=`{[15:14],[3:0]}`、
    exp=`[6:4]`、lgkm=`[11:8]`）；
  - `&` 分隔的符号式 `vmcnt(10) & lgkmcnt(0)`；
  - 单项 `lgkmcnt(0)` / 空格分隔。
- **`vscnt` 独立计数器**：`s_waitcnt_vscnt null, N` 单独解析，store 计 `WaitType.VS`，
  与 vmcnt 解耦（gfx942 必需）。
- **MFMA 不进 waitcnt**：`v_mfma*` / `v_smfmac*` 归 `Kind.MFMA`、`WaitType.NONE`，
  其写回由硬件记分板跟踪（与设计文档一致）。
- **写 m0 判定**：首操作数为 `m0`（如 `s_add_u32 m0, 0x100, s58`）即 `Kind.SET_M0`。

### 计数器"超宽"不是错误
gfx942 的 `lgkmcnt` 是 4-bit 字段（上限 15）。真实 shader 序章一次性发起 16 条标量 load，
随后一条 `s_waitcnt lgkmcnt(0)` 排空——计数器在硬件上是**饱和**语义，在途条数超过字段宽度是
**合法**的。因此只读校验器**不**对"在途数超宽"报警；仅当**解析出的 wait 目标值**超过字段宽度
（不可编码）时才告警。

---

## 4. 在真实 shader 上的运行结果（冒烟）

```
lines: 1120   instrs: 1017
code items: 1022   blocks: 20   loops: 1
loop headers: ['label_0243']
regions: [('prologue', 9, 436), ('loop', 437, 888), ('epilogue', 889, 1031)]
wait events: 12   warnings: []
final outstanding: {'vm':0, 'lgkm':0, 'exp':0, 'vs':12}
```

- 无损往返：`emit(parse(src)) == src` 仍逐字节成立。
- 单个主循环（`label_0243` 回边）被正确识别，区域三段干净切分。
- 12 条 waitcnt 全部正确读出，零误报。
- 结尾 `vs=12`（12 条已发起的 VMEM store 在 `s_endpgm` 前未显式 `vscnt` 排空）——
  属正常（endpgm 隐式收尾），作为信息保留，留待 M2 依赖图判断是否需要补 store 屏障。

---

## 5. 架构无关性自检

- `reorder/regions.py`、`reorder/waitcnt.py` 对分支/终结/计数器/wait 语义的全部判断
  **只经 `Target` 接口**，无任何 `gfx942` 直引用。
- 新增架构 = 新增 `isa/<arch>/` 包并实现 `Target` + `CounterModel`；
  `registry.get("<arch>")` 通过懒加载 `import isa.<arch>` 自动发现，核心层零改动。

---

## 6. 测试

`python3.8 -m unittest discover -s tests` → **45 passed**（M0 18 + M1 27）。

- operands：单寄存器/区间/`acc`归一/特殊寄存器/立即数/别名展开/字段取首 token/`RegSet.overlaps`。
- classify：MFMA/三类访存/lds-load 修饰/写 m0/控制流/ALU。
- counters：`&` 与空格符号式、单项、裸 simm16、simm16 编解码往返、vscnt。
- registry：懒加载 get、未知架构报错、`from_program` 别名扫描。
- regions：fixture 循环检测、区域顺序、仅取 .text、真实 shader 跑通、无 metadata 误判 label。
- waitcnt：解析既有 wait、前向模拟排空、vscnt 模拟、真实 shader 三种写法识别。

---

## 7. M1 边界与遗留（交给 M2）

M1 刻意**只读**。以下属 M2 范围：

- 精确 per-opcode 的 def/use 角色（当前 `parse_operands` 用"首操作数=目的"的启发式，
  对 MFMA 已特判 src2≡dst 累加链）。
- 依赖图（RAW/WAR/WAW/MEM/M0/ACC/FENCE 边）与可移动 bundle。
- 基于依赖图 + 本模拟器的 **waitcnt 重算**（把只读模拟升级为改写）。
- 支配树精确化（当前自然循环用程序序回边区间，对结构化单入口循环正确；
  非规约控制流留待引入支配关系后处理）。
