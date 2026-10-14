# M0 步骤报告：工程骨架 + 无损往返解析器

> 里程碑：**M0 脚手架 + 无损往返**
> 状态：**已完成**（14/14 测试通过，无 lint 错误）
> 日期：2026-06-04

---

## 1. 目标与验收门

搭起 testft 工程骨架（架构无关 `reorder` 核心 + `isa` 抽象层空壳 + `harness`/`analysis`/`agent`/`search` 占位 + 测试），并实现 `lexer`/`parser`/`emitter`。

**验收门（已达成）**：两种风格的 `.s` 都能 `parse → emit` **逐字节无损还原**：
- GEMM 风格：`label_XXXX:` 标签 / 2 空格缩进 / 裸寄存器 `s4`/`v[44:47]`/`a[0:3]`。
- k_vadd 风格：`.label_exit:` 点前缀标签 / Tab 缩进 / `.set` 别名 / `//` 与 `;` 注释。

---

## 2. 交付物（文件清单）

```
testft/
  pyproject.toml            # 独立打包；requires-python>=3.8；零运行期依赖
  README.md                 # 运行方式、模块结构、M0 现状
  .gitignore
  reorder/                  # 架构无关核心（M0 实装部分）
    __init__.py             # 导出 parse/parse_file/emit/write + 模型
    model.py                # LineKind / Kind / WaitType(含 VS) / EdgeType / Line / Program
    lexer.py                # 行级分类 + 顶层逗号切操作数 + 顶层注释定位
    parser.py               # text -> Program（按 '\n' 切分，逐行保真）
    emitter.py              # Program -> text（'\n'.join(raw)，无损）
  isa/                      # 硬件指令集抽象层（契约就位，实现待 M1）
    __init__.py
    target.py               # Target Protocol（架构契约，含 perf_counter_schema/fixup_pipeline）
    registry.py             # 名称->Target 注册表（M0 无注册项，get 抛清晰错误）
  harness/                  # 自带评测（接口就位）
    __init__.py
    toolchain.py            # llvm-mc/clang 包装（M0 仅定位+调用面，未被测试触达）
    evaluator.py            # 三阶段 Evaluator 协议 + EvalResult + CompileOnlyEvaluator
  analysis/                 # perf counter 解析/瓶颈分类（M4 实装，M0 stub）
    __init__.py  perf.py  bottleneck.py
  agent/                    # 元层知识/记忆（M7 实装，M0 stub）
    __init__.py  knowledge.py
  search/                   # 搜索层（M6 实装，M0 空包）
    __init__.py
  tests/
    __init__.py
    fixtures/gemm_style.s   # 自带的 GEMM 风格最小样例（不引用任何外部文件）
    fixtures/kvadd_style.s  # 自带的 k_vadd 风格最小样例
    test_roundtrip.py       # 14 个用例：无损往返 + 分类正确性 + lexer 辅助函数
```

---

## 3. 关键设计与实现要点

### 3.1 无损往返的保证方式
- `parser.parse` 用 **`text.split("\n")`** 切行，`emitter.emit` 用 **`"\n".join(raw)`** 回拼。二者互为精确逆运算，因此对 **CRLF、缺尾换行、纯空行、空文件** 都逐字节还原（不使用 `str.splitlines()`，避免它在 `\x0b/\x0c/\u2028` 等处误切）。
- 读写均用 `open(..., newline="")` 关闭通用换行翻译，确保 `\r\n` 原样保留。
- 每个 `Line` 持有 **`raw`（去掉行尾 `\n` 的原文）** 作为唯一真相；结构化字段（opcode/operands/label/comment…）是派生视图，M0 不参与回写。后续里程碑修改指令/waitcnt 行时才从结构化字段渲染，未改动的行永远回退到 `raw`。

### 3.2 词法分类（架构无关）
`lexer.classify` 把每行判为 `BLANK / COMMENT / DIRECTIVE / LABEL / INSTR / OTHER`：
- **先判 LABEL 再判 DIRECTIVE**：`.label_exit:` 是标签不是指令，正则要求整行 `^\s*[\w$.]+:\s*$`。
- 注释标记支持 `//` 与 `;`（`#` 故意不当注释，太歧义且无损性不依赖它）。
- **顶层逗号切操作数 / 顶层注释定位**都跟踪 `[]`/`()` 括号深度：`s[8:11]`、`ds_read_b128 a[0:3], v31` 不会被误判出注释或误切。
- 指令助记符须小写起首（`v_`/`s_`/`ds_`/`buffer_`/`global_`…），与 gfx942 约定一致。
- 不认识的行（YAML 元数据 `---`/`amdhsa.kernels:` 等）归 `OTHER`，仍 `raw` 回写。
- 语义类别 `Kind`（MFMA/VMEM_LOAD…）**M0 不赋值**，留给 M1 的 `isa/Target.classify`。

### 3.3 与评审决策对齐
- **完全独立**：fixtures 为 testft 自有，未引用 `feifeiAVO`/`amdgpu-asm-tool`/外部 `.s`；运行期零第三方依赖。
- **架构无关核心 + ISA 层**：`reorder/` 不含任何指令集常量；`isa/Target` 契约已定义（含 `counter_model`/`fixup_pipeline`/`perf_counter_schema`/`invariants`），`registry` 就位，gfx942 实现留 M1。
- **三阶段评测可插拔**：`Evaluator` 协议 = `assemble`/`check_correctness`/`measure_perf`/`dump_counters`/`evaluate`；`EvalResult` 含 `time_us`/`counter_dump_path`/`counters`/`direction`。

---

## 4. 测试结果

环境：`Python 3.8.x`（系统默认 3.6 过旧，3.8 可用），**未安装 pytest**，因此测试用标准库 `unittest`（零安装即可验证；pytest 也能发现）。

```
$ cd testft && python3.8 -m unittest discover -s tests -t . -v
Ran 14 tests in 0.015s
OK
```

覆盖：
- 两种风格 fixtures 的 `emit` 与 `write` **逐字节相等**；
- 8 个合成边界用例（空文件 / 纯换行 / 缺尾换行 / CRLF / 纯空行 / 尾随空格）round-trip；
- 分类正确性：GEMM 三个 `label_*`、MFMA 操作数 `["v[44:47]","a[96:97]","a[0:1]","v[44:47]"]` 括号保真、`.text/.global/.amdhsa_kernel/.amdgpu_metadata` 为指令性指令；k_vadd `.label_exit` 判为 LABEL、`.set` 判为 DIRECTIVE、trailing `//` 注释与操作数正确分离、`global_load_b32` 操作数 `["v[v_a]","v[2:3]","off"]`；
- lexer 辅助：`find_comment` 不被括号干扰、`split_operands` 顶层逗号切分。

补充冒烟：`reorder/isa/harness/analysis/agent/search` 全部可导入；`registry.get("gfx942")` 抛清晰的"M1 才实现"错误；`CompileOnlyEvaluator` 在无工具链时返回 `compiled=False` 的结果而非崩溃。

---

## 5. 运行方式

```bash
cd testft
python3.8 -m unittest discover -s tests -t . -v      # 零安装
# 或： python3.8 -m pytest                            # 若已装 pytest
```

---

## 6. 已知限制 / 顺延到后续里程碑

- 操作数中**空格分隔的修饰符**（如 `0 offen lds`）M0 仍附着在末个操作数字段里——结构化修饰符解析属 M1（`isa/Target.parse_operands`）。
- 语义类别 `Kind`、寄存器 `RegSet`、`.set` 别名展开、分支判定 → **M1**。
- `harness/toolchain.py` 仅有调用面，真机三阶段评测（正确性/性能/counter dump）接入需用户提供的测试用例 → **M4**。
- `analysis`/`agent` 为 stub（调用即 `NotImplementedError`）→ **M4 / M7**。
- 工程尚未初始化为 git 仓库（可按需 `git init`）。

---

## 7. 下一步（M1 预告）

定 `Target` 契约的具体行为 + 落 `isa/gfx942`（operands/classify/counters/registry 注册）+ `regions.py`（CFG / 回边找自然循环 / 切 N 区，分支判定走 Target）+ 只读 waitcnt 校验器（验证能正确读懂现有 `s_waitcnt`，含 `vscnt`）。
