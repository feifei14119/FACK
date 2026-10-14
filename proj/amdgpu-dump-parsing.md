# AMDGPU ATT/Trace Dump 解析技术文档

本文档抽取自 `vscode-att-viewer` 插件，目的是让**其他工程**也能复用同一套机制去解析 AMDGPU 的 dump 文件，而不必依赖 VS Code 插件本身。

> 适用对象：需要离线解码 ROCm ATT（Advanced Thread Trace / SQTT）dump、把逐指令时间线数据转成结构化数据（JSON / dataframe / 自定义格式）的工程。

---

## 0. 先搞清楚你的 dump 是哪一种

ROCm/rocprofiler 体系里有几类容易混淆的产物，**解码入口完全不同**，务必先确认：

| 类型 | 文件特征 | 数据含义 | 本文是否覆盖 |
| --- | --- | --- | --- |
| **ATT / Thread Trace（SQTT）** | `.att` 二进制 | 逐指令执行时间线：每条指令的 issue cycle、duration、stall、category | ✅ 本文 |
| **Perf Counter / SPM（counter collection）** | 多在 `*_results.db` / `rocpd` 表里，或 csv | 周期性采样的硬件计数器累加值（如 cache 命中率、占用率） | ❌ 走 rocpd/counter service，另一套 API |
| **Code Object** | `*_code_object_id_*.out`（GPU ELF） | GPU 二进制本体，用于 PC→指令反汇编 | 作为解码的辅助输入 |

如果你要的是**真正的 perf counter 累加值**，它通常已经是结构化的（在 SQLite `rocpd_*` 表或 CSV 里），直接用 SQL/读表即可，不需要本文这套二进制解码。本文解决的是 **ATT 二进制 dump → 结构化逐指令事件** 这条路径。

---

## 1. 核心思想：不要自己解析二进制格式

`.att` 的二进制格式**未公开且随硬件/驱动版本变化**。正确做法是把解码工作**完全委托给 ROCm 官方解码库** `librocprofiler-sdk.so`，自己只写一层 `ctypes`（或任意 FFI）桥接：

```
.att 字节流  ──►  librocprofiler-sdk.so (官方解码器)  ──►  回调流式吐出记录  ──►  你的语言里的结构体
```

你需要做的只有三件事：

1. 用 FFI 绑定 SDK 的几个 C 入口函数；
2. 在你的语言里**精确复刻** SDK 的 C 结构体内存布局；
3. 实现一个回调，把 SDK 吐出来的记录转成你想要的格式。

---

## 2. 运行环境前提

- 目标机器安装了 **ROCm**，且存在：
  - `/opt/rocm/lib/librocprofiler-sdk.so`（解码器入口）
  - `/opt/rocm/llvm/bin/llvm-objdump`（PC → 汇编文本，可选）
- 进程环境变量需包含解码库路径：
  ```bash
  export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH
  ```
- 解码需要的输入：
  - `.att` dump 本体
  - 对应的 code object ELF 文件（`*_code_object_id_*.out`）
  - 可选：`*_results.db`（SQLite，提供 code object 的 `load_base`/`load_size` 元信息）

---

## 3. SDK 调用协议（解码生命周期）

整套解码遵循固定的生命周期：

```
create(handle, lib_path)
   │
   ├── 对每个 code object:  codeobj_load(handle, id, base, size, buf, len)
   │
   ├── trace_decode(handle, callback, att_buf, att_len, user)
   │        └── callback 被多次调用，流式吐出 GFXIP / INFO / WAVE 记录
   │
   └── destroy(handle)
```

### 3.1 需要绑定的 SDK 函数

| 函数 | 作用 | 签名（C 语义） |
| --- | --- | --- |
| `rocprofiler_thread_trace_decoder_create` | 创建解码器句柄 | `(DecoderHandle* out, const char* lib_path) -> int` |
| `rocprofiler_thread_trace_decoder_destroy` | 销毁句柄 | `(DecoderHandle) -> void` |
| `rocprofiler_thread_trace_decoder_codeobj_load` | 注入一个 code object | `(DecoderHandle, uint64 id, uint64 base, uint64 size, void* buf, uint64 len) -> int` |
| `rocprofiler_trace_decode` | 解码 dump，触发回调 | `(DecoderHandle, callback, void* att_buf, uint64 att_len, void* user) -> int` |
| `rocprofiler_thread_trace_decoder_info_string` | 把 INFO 记录的 code 转成可读字符串 | `(DecoderHandle, int code) -> const char*` |

- 所有返回 `int` 的函数：`0` 表示成功（`ROCPROF_STATUS_SUCCESS`），非 0 表示失败。
- `create` 的第二个参数传的是**解码库所在目录路径**（如 `/opt/rocm/lib`），不是 `.att` 路径。

### 3.2 回调签名

```c
// void callback(int record_type, void* events_ptr, uint64 n, void* user)
```

- `record_type`：记录类型（见下表）
- `events_ptr`：指向一个数组的指针，元素类型取决于 `record_type`
- `n`：数组元素个数
- `user`：透传的用户指针（本实现未用）

### 3.3 记录类型（record_type）

| 值 | 名称 | `events_ptr` 指向 | 含义 |
| --- | --- | --- | --- |
| `0` | `RECORD_GFXIP` | `size_t[1]` | GPU 架构主版本号（如 9 表示 gfx9xx） |
| `3` | `RECORD_WAVE` | `Wave[n]` | **核心**：每个 wave 及其指令数组 |
| `4` | `RECORD_INFO` | `int[n]` | info/警告 code，需用 `info_string` 转字符串 |

> 注意：除 0/3/4 外可能还有其他 record_type，按需忽略即可。

---

## 4. C 结构体内存布局（必须精确复刻）

> ⚠️ **关键风险点**：这些结构体布局必须和你机器上的 SDK 版本严格一致，否则会读到错位/垃圾数据。升级 ROCm 后要重新核对头文件。下面是 `vscode-att-viewer` 验证过的布局（gfx9xx）。

### 4.1 `Pc`（程序计数器 + marker）

```
struct Pc {
    size_t addr;        // 指令在 code object 内的虚拟地址
    size_t marker_id;   // 对应哪个 code object（== codeobj_load 时传入的 id）
};
```

### 4.2 `Inst`（单条指令事件）

```
struct Inst {
    uint32_t _catstall;  // 打包字段: 低 8 位 = category, 高 24 位 = stall cycles
    int32_t  duration;   // 指令占用周期数
    int64_t  time;       // issue cycle（发射时刻）
    Pc       pc;         // 地址 + marker_id
};
```

`_catstall` 的解包：

```
category = _catstall & 0xFF;          // 指令类别，见 §6
stall    = (_catstall >> 8) & 0xFFFFFF;
```

### 4.3 `Wave`（一个 wavefront 及其全部指令）

```
struct Wave {
    uint8_t  cu;                 // Compute Unit 编号
    uint8_t  simd;               // SIMD 编号
    uint8_t  wave_id;            // wave slot
    uint8_t  contexts;
    uint32_t _rsvd1;
    uint32_t _rsvd2;
    uint32_t _rsvd3;
    int64_t  begin_time;
    int64_t  end_time;
    size_t   timeline_size;
    size_t   instructions_size;  // 指令数组长度
    void*    timeline_array;     // 本实现未使用
    Inst*    instructions_array; // 指向 Inst[instructions_size]
};
```

### 4.4 `DecoderHandle`

```
struct DecoderHandle { uint64_t handle; };
```

---

## 5. 参考实现（Python / ctypes）

以下是可直接复用、**不依赖 VS Code** 的最小内核（即 `python/att_decode_ctypes.py` 的等价物）。其他语言（C++/Rust 等）按相同协议绑定即可。

```python
from __future__ import annotations
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


class Pc(C.Structure):
    _fields_ = [("addr", C.c_size_t), ("marker_id", C.c_size_t)]


class Inst(C.Structure):
    _fields_ = [
        ("_catstall", C.c_uint32),
        ("duration", C.c_int32),
        ("time", C.c_int64),
        ("pc", Pc),
    ]

    @property
    def category(self) -> int:
        return int(self._catstall & 0xFF)

    @property
    def stall(self) -> int:
        return int((self._catstall >> 8) & 0xFFFFFF)


class Wave(C.Structure):
    _fields_ = [
        ("cu", C.c_uint8), ("simd", C.c_uint8),
        ("wave_id", C.c_uint8), ("contexts", C.c_uint8),
        ("_rsvd1", C.c_uint32), ("_rsvd2", C.c_uint32), ("_rsvd3", C.c_uint32),
        ("begin_time", C.c_int64), ("end_time", C.c_int64),
        ("timeline_size", C.c_size_t), ("instructions_size", C.c_size_t),
        ("timeline_array", C.c_void_p),
        ("instructions_array", C.POINTER(Inst)),
    ]


class DecoderHandle(C.Structure):
    _fields_ = [("handle", C.c_uint64)]


ROCPROF_STATUS_SUCCESS = 0
RECORD_GFXIP, RECORD_WAVE, RECORD_INFO = 0, 3, 4
_CB = C.CFUNCTYPE(None, C.c_int, C.c_void_p, C.c_uint64, C.c_void_p)


@dataclass(frozen=True)
class DecodedInst:
    lane: int; cu: int; simd: int; slot: int
    issue: int; duration: int; stall: int
    category: int; marker_id: int; pc: int


def decode_att(att_path: Path,
               code_objects: List[Tuple[int, int, int, Path]],  # (id, base, size, elf_path)
               decoder_lib_path: Path = Path("/opt/rocm/lib"),
               rocprofiler_sdk_path: Path = Path("/opt/rocm/lib/librocprofiler-sdk.so")
               ) -> Tuple[int, List[DecodedInst]]:
    sdk = C.CDLL(str(rocprofiler_sdk_path), mode=C.RTLD_GLOBAL)

    create = sdk.rocprofiler_thread_trace_decoder_create
    create.argtypes = [C.POINTER(DecoderHandle), C.c_char_p]; create.restype = C.c_int
    destroy = sdk.rocprofiler_thread_trace_decoder_destroy
    destroy.argtypes = [DecoderHandle]; destroy.restype = None
    codeobj_load = sdk.rocprofiler_thread_trace_decoder_codeobj_load
    codeobj_load.argtypes = [DecoderHandle, C.c_uint64, C.c_uint64, C.c_uint64, C.c_void_p, C.c_uint64]
    codeobj_load.restype = C.c_int
    trace_decode = sdk.rocprofiler_trace_decode
    trace_decode.argtypes = [DecoderHandle, _CB, C.c_void_p, C.c_uint64, C.c_void_p]
    trace_decode.restype = C.c_int
    info_string = sdk.rocprofiler_thread_trace_decoder_info_string
    info_string.argtypes = [DecoderHandle, C.c_int]; info_string.restype = C.c_char_p

    handle = DecoderHandle()
    if create(C.byref(handle), str(decoder_lib_path).encode()) != ROCPROF_STATUS_SUCCESS:
        raise RuntimeError("decoder_create failed")

    # 注入 code objects；注意保留 buffer 引用，防止被 GC 释放
    buffers = []
    for (load_id, load_base, load_size, elf_path) in code_objects:
        data = elf_path.read_bytes()
        buf = (C.c_ubyte * len(data)).from_buffer_copy(data)
        buffers.append(buf)
        if codeobj_load(handle, load_id, load_base, load_size,
                        C.cast(buf, C.c_void_p), len(data)) != ROCPROF_STATUS_SUCCESS:
            raise RuntimeError(f"codeobj_load failed id={load_id}")

    lane_map: Dict[int, int] = {}
    next_lane = 0
    gfxip_major = 0
    out: List[DecodedInst] = []

    def get_lane(cu, simd, slot):
        nonlocal next_lane
        key = (cu << 16) | (simd << 8) | slot
        if key not in lane_map:
            lane_map[key] = next_lane; next_lane += 1
        return lane_map[key]

    @_CB
    def cb(record_type, events_ptr, n, _user):
        nonlocal gfxip_major
        if record_type == RECORD_GFXIP and events_ptr and n:
            gfxip_major = int(C.cast(events_ptr, C.POINTER(C.c_size_t))[0]); return
        if record_type == RECORD_INFO and events_ptr and n:
            infos = C.cast(events_ptr, C.POINTER(C.c_int))
            for i in range(int(n)):
                msg = info_string(handle, int(infos[i]))
                if msg: import sys; sys.stderr.write("ATT info: " + msg.decode("utf-8", "replace") + "\n")
            return
        if record_type != RECORD_WAVE or not events_ptr or not n:
            return
        waves = C.cast(events_ptr, C.POINTER(Wave))
        for wi in range(int(n)):
            w = waves[wi]
            lane = get_lane(int(w.cu), int(w.simd), int(w.wave_id))
            insts = w.instructions_array
            for ii in range(int(w.instructions_size)):
                inst = insts[ii]
                out.append(DecodedInst(
                    lane=lane, cu=int(w.cu), simd=int(w.simd), slot=int(w.wave_id),
                    issue=int(inst.time), duration=int(inst.duration),
                    stall=int(inst.stall), category=int(inst.category),
                    marker_id=int(inst.pc.marker_id), pc=int(inst.pc.addr)))

    att_bytes = att_path.read_bytes()
    att_buf = (C.c_ubyte * len(att_bytes)).from_buffer_copy(att_bytes)
    st = trace_decode(handle, cb, C.cast(att_buf, C.c_void_p), len(att_bytes), None)
    destroy(handle)
    if st != ROCPROF_STATUS_SUCCESS:
        raise RuntimeError(f"trace_decode failed status={st}")
    return gfxip_major, out
```

### 实现要点 / 易踩坑

- **buffer 生命周期**：传给 SDK 的 code object / att 字节缓冲必须在 `trace_decode` 期间一直存活，不能被 GC 回收。示例中用 `buffers` 列表持有引用。
- **回调对象生命周期**：用 `@_CB` 装饰的回调要保持引用，否则可能在解码中途被回收导致崩溃。
- **`RTLD_GLOBAL`**：加载 SDK 时用 `mode=C.RTLD_GLOBAL`，便于其内部依赖符号解析。
- **lane 映射**：SDK 给的是 `(cu, simd, wave_id)`，可自己映射成连续的 lane 编号便于画时间线。
- **结构体对齐**：上面布局已含显式 `_rsvd` 填充字段；不要随意删，删了会错位。

---

## 6. 指令类别（category）枚举

`Inst.category`（`_catstall & 0xFF`）的取值含义：

| 值 | 名称 | 含义 |
| --- | --- | --- |
| 0 | NONE | 无 |
| 1 | SMEM | 标量内存 |
| 2 | SALU | 标量 ALU |
| 3 | VMEM | 向量内存 |
| 4 | FLAT | flat 访存 |
| 5 | LDS | local data share |
| 6 | VALU | 向量 ALU（**MFMA/WMMA 也被归到这里**） |
| 7 | JUMP | 跳转 |
| 8 | NEXT | — |
| 9 | IMMED | 立即数 |
| 10 | CONTEXT | 上下文 |
| 11 | MESSAGE | 消息 |
| 12 | BVH | 光追 BVH |

> **MFMA 拆分技巧**：矩阵指令（`v_mfma_*` / `v_wmma_*`）被 SDK 归为 `VALU`。若要单独统计/着色，需要拿到反汇编文本后用前缀启发式（`a.startswith("v_mfma")` 等）把它从 VALU 里拆出来。

---

## 7. PC → 汇编文本（可选但常用）

解码出来的每条指令只有 `(marker_id, pc)`，要拿到人类可读的汇编，需要反汇编对应 code object：

```bash
llvm-objdump -d --mcpu=gfx950 \
    --start-address=0x<min> --stop-address=0x<max> \
    your_code_object_id_N.out
```

解析输出时，靠每行行尾的 `// <十六进制地址>:` 注释建立 `地址 → 汇编文本` 映射：

```python
import re, subprocess
_ADDR_RE = re.compile(r"//\s+([0-9A-Fa-f]+):")

def disassemble_to_map(codeobj_path, gpu_arch, start=None, stop=None,
                       llvm_objdump="/opt/rocm/llvm/bin/llvm-objdump"):
    cmd = [llvm_objdump, "-d", f"--mcpu={gpu_arch}"]
    if start is not None: cmd.append(f"--start-address=0x{start:x}")
    if stop  is not None: cmd.append(f"--stop-address=0x{stop:x}")
    cmd.append(str(codeobj_path))
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    m = {}
    for line in out.splitlines():
        if "//" not in line: continue
        mm = _ADDR_RE.search(line)
        if not mm: continue
        text = line.split("//", 1)[0].strip()
        if not text or text.endswith(":"): continue
        m[int(mm.group(1), 16)] = text
    return m
```

性能提示：先收集所有 PC，只反汇编 `[min(pc)-0x200, max(pc)+0x400]` 这段区间，避免反汇编整个 code object。

---

## 8. 准备 code object 元信息（results.db）

`load_base` / `load_size` 从 `*_results.db`（SQLite）读取。表名形如 `rocpd_info_code_object_*`：

```python
import sqlite3
def read_codeobj_table(results_db):
    con = sqlite3.connect(str(results_db)); cur = con.cursor()
    cur.execute("select name from sqlite_master where type='table' "
                "and name like 'rocpd_info_code_object_%' limit 1")
    row = cur.fetchone()
    if not row: con.close(); return []
    table = row[0]
    cur.execute(f"select id, load_base, load_size from {table} order by id")
    rows = [(int(a), int(b), int(c)) for (a, b, c) in cur.fetchall()]
    con.close(); return rows
```

**降级方案**：没有 `results.db` 时，直接扫描目录里的 `*code_object_id_<N>.out`，从文件名解析 `id`，`load_base=0`、`load_size=文件大小`。解码器主要靠 `marker_id` + ELF 内部 vaddr，多数情况这样也能工作（PC 拼接可能不完整）。

---

## 9. 移植 Checklist

把这套机制搬到新工程时，按顺序确认：

1. [ ] 目标机有 ROCm，`/opt/rocm/lib/librocprofiler-sdk.so` 存在
2. [ ] `LD_LIBRARY_PATH` 含 `/opt/rocm/lib`
3. [ ] 拿到 `.att` + 对应 code object ELF（+ 可选 results.db）
4. [ ] 按 §4 复刻结构体布局，并**用你机器上的 SDK 头文件核对**（升级 ROCm 后必查）
5. [ ] 按 §3 绑定 5 个函数，实现回调，跑通 create→load→decode→destroy
6. [ ] 验证：解码出的指令数 > 0，`gfxip_major` 合理，`issue` 单调性大致正常
7. [ ] （可选）接 §7 反汇编、§6 类别着色

---

## 10. 文件对照（本插件里的实现）

| 本文档章节 | 插件中的源文件 |
| --- | --- |
| §3–§6 解码内核 | `python/att_decode_ctypes.py` |
| §7 反汇编 | `python/objdump_map.py` |
| §8 results.db / 编排 / JSON 输出 | `python/att2json.py` |
| VS Code 编排（定位文件、spawn、Webview） | `src/extension.js` |
