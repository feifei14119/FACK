"""Parse an ATT (thread-trace) dump directory into normalized per-category stats.

Two layers:
  - pure helpers (filename parsing, code-object discovery, aggregation) -- always
    available and unit-tested without ROCm.
  - SDK decode (``decode_att``) -- delegates the .att binary decode to
    ``librocprofiler-sdk.so`` via ctypes (see proj/amdgpu-dump-parsing.md). Only
    runs where ROCm is installed.

``parse(dump, schema)`` accepts the ``-d ./att`` directory produced by
``rocprofv2 ... --plugin att`` and returns a counter dict consumed by
analysis/bottleneck.py. The architecture-specific category meanings come from
``Target.perf_counter_schema()`` (passed in as ``schema``).
"""
from __future__ import annotations

import ctypes as _C
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# code-object dump filename: memory<pid>#offset=0x<base>&size=<size>.out
_CODEOBJ_RE = re.compile(r"#offset=(0x[0-9A-Fa-f]+|\d+)&size=(\d+)\.out$")

# The ATT decode backend (``librocprof-trace-decoder.so``) is a SEPARATE package
# from rocprofiler-sdk and is NOT always installed under /opt/rocm/lib. The SDK's
# ``rocprofiler_thread_trace_decoder_create(path)`` searches ``path`` for it, so
# we must hand it a directory that actually contains the .so.
_DECODER_SO = "librocprof-trace-decoder.so"
_DECODER_DIR_CANDIDATES = (
    "/opt/rocm/lib",
    "/opt/rocm/lib/rocprofiler-sdk",
    "/mnt/sixifang/rtd-install/opt/rocm/lib",
)


def _pip_devel_lib(root: Optional[str]) -> Optional[str]:
    """pip ROCm (``_rocm_sdk_core``) ships only versioned ``.so.N`` decoder and
    aqlprofile libraries; the unversioned names that rocprofiler and the HSA
    runtime dlopen live in the sibling ``_rocm_sdk_devel/lib``. Without them
    ``--att`` aborts and the abort handler deadlocks the profiled process."""
    if not root:
        return None
    core = os.path.realpath(root)
    if os.path.basename(core) != "_rocm_sdk_core":
        return None
    return os.path.join(os.path.dirname(core), "_rocm_sdk_devel", "lib")


def resolve_decoder_dir(explicit: Optional[str] = None) -> str:
    """Find a directory containing the ATT trace-decoder backend .so.

    Order: explicit arg -> $TESTFT_ATT_DECODER_DIR -> $ROCM_PATH/lib -> the pip
    devel sibling -> known candidates. Falls back to /opt/rocm/lib (the SDK then
    reports NOT_AVAILABLE with a clear error). Callers put the result first on
    LD_LIBRARY_PATH, which also resolves the unversioned aqlprofile library.
    """
    rocm = os.environ.get("ROCM_PATH")
    for d in (explicit, os.environ.get("TESTFT_ATT_DECODER_DIR"),
              os.environ.get("AMDGPU_ATT_DECODER_DIR"),
              os.path.join(rocm, "lib") if rocm else None,
              _pip_devel_lib(rocm), _pip_devel_lib("/opt/rocm")):
        if d and os.path.isfile(os.path.join(d, _DECODER_SO)):
            return d
    for d in _DECODER_DIR_CANDIDATES:
        if os.path.isfile(os.path.join(d, _DECODER_SO)):
            return d
    return "/opt/rocm/lib"


@dataclass(frozen=True)
class DecodedInst:
    cu: int
    simd: int
    slot: int
    issue: int
    duration: int
    stall: int
    category: int
    marker_id: int
    pc: int


# --- pure discovery helpers ------------------------------------------------
def parse_codeobj_filename(name: str) -> Optional[Tuple[int, int]]:
    """Return (load_base, load_size) parsed from a code-object dump filename,
    or None if it is not a code-object file."""
    m = _CODEOBJ_RE.search(name)
    if not m:
        return None
    return int(m.group(1), 0), int(m.group(2))


def discover_dump(att_dir: str) -> Dict[str, List]:
    """Scan an ATT dump directory; classify the three file kinds."""
    att_files: List[str] = []
    code_objects: List[Tuple[int, int, int, str]] = []  # (id, base, size, path)
    kernel_txt: List[str] = []
    for fn in sorted(os.listdir(att_dir)):
        path = os.path.join(att_dir, fn)
        if fn.endswith(".att"):
            att_files.append(path)
        elif fn.endswith(".out"):
            bs = parse_codeobj_filename(fn)
            if bs is not None:
                code_objects.append((len(code_objects), bs[0], bs[1], path))
        elif fn.endswith("_kernel.txt"):
            kernel_txt.append(path)
    return {"att_files": att_files, "code_objects": code_objects,
            "kernel_txt": kernel_txt}


# --- aggregation (pure) ----------------------------------------------------
def aggregate(insts: List[DecodedInst], schema: Dict) -> Dict:
    """Fold decoded instructions into per-category and per-dimension stats."""
    by_cat_count: Dict[int, int] = {}
    by_cat_stall: Dict[int, int] = {}
    by_dim_count: Dict[str, int] = {}
    by_dim_stall: Dict[str, int] = {}
    total_stall = 0
    total_issue = 0
    for ins in insts:
        by_cat_count[ins.category] = by_cat_count.get(ins.category, 0) + 1
        by_cat_stall[ins.category] = by_cat_stall.get(ins.category, 0) + ins.stall
        dim = (schema.get(ins.category) or {}).get("dimension", "none")
        by_dim_count[dim] = by_dim_count.get(dim, 0) + 1
        by_dim_stall[dim] = by_dim_stall.get(dim, 0) + ins.stall
        total_stall += ins.stall
        total_issue += 1
    return {
        "n_inst": total_issue,
        "total_stall": total_stall,
        "by_category_count": by_cat_count,
        "by_category_stall": by_cat_stall,
        "by_dimension_count": by_dim_count,
        "by_dimension_stall": by_dim_stall,
    }


# --- SDK decode (ROCm only) ------------------------------------------------
class _Pc(_C.Structure):
    _fields_ = [("addr", _C.c_size_t), ("marker_id", _C.c_size_t)]


class _Inst(_C.Structure):
    _fields_ = [("_catstall", _C.c_uint32), ("duration", _C.c_int32),
                ("time", _C.c_int64), ("pc", _Pc)]


class _Wave(_C.Structure):
    _fields_ = [
        ("cu", _C.c_uint8), ("simd", _C.c_uint8), ("wave_id", _C.c_uint8),
        ("contexts", _C.c_uint8), ("_r1", _C.c_uint32), ("_r2", _C.c_uint32),
        ("_r3", _C.c_uint32), ("begin_time", _C.c_int64), ("end_time", _C.c_int64),
        ("timeline_size", _C.c_size_t), ("instructions_size", _C.c_size_t),
        ("timeline_array", _C.c_void_p), ("instructions_array", _C.POINTER(_Inst)),
    ]


class _DecoderHandle(_C.Structure):
    _fields_ = [("handle", _C.c_uint64)]


_ROCPROF_OK = 0
_RECORD_GFXIP, _RECORD_WAVE, _RECORD_INFO = 0, 3, 4
_CB = _C.CFUNCTYPE(None, _C.c_int, _C.c_void_p, _C.c_uint64, _C.c_void_p)


def decode_att(att_path: str, code_objects: List[Tuple[int, int, int, str]],
               decoder_lib_dir: Optional[str] = None,
               sdk_so: str = "/opt/rocm/lib/librocprofiler-sdk.so"
               ) -> Tuple[int, List[DecodedInst]]:
    """Decode one .att file via librocprofiler-sdk. Requires ROCm + the ATT
    trace-decoder backend (resolved via ``resolve_decoder_dir``)."""
    decoder_lib_dir = resolve_decoder_dir(decoder_lib_dir)
    sdk = _C.CDLL(sdk_so, mode=_C.RTLD_GLOBAL)
    create = sdk.rocprofiler_thread_trace_decoder_create
    create.argtypes = [_C.POINTER(_DecoderHandle), _C.c_char_p]; create.restype = _C.c_int
    destroy = sdk.rocprofiler_thread_trace_decoder_destroy
    destroy.argtypes = [_DecoderHandle]; destroy.restype = None
    codeobj_load = sdk.rocprofiler_thread_trace_decoder_codeobj_load
    codeobj_load.argtypes = [_DecoderHandle, _C.c_uint64, _C.c_uint64, _C.c_uint64,
                             _C.c_void_p, _C.c_uint64]; codeobj_load.restype = _C.c_int
    trace_decode = sdk.rocprofiler_trace_decode
    trace_decode.argtypes = [_DecoderHandle, _CB, _C.c_void_p, _C.c_uint64, _C.c_void_p]
    trace_decode.restype = _C.c_int

    handle = _DecoderHandle()
    if create(_C.byref(handle), decoder_lib_dir.encode()) != _ROCPROF_OK:
        raise RuntimeError(
            "decoder_create failed: no {} under {!r}. Install the ATT trace-"
            "decoder package or set $TESTFT_ATT_DECODER_DIR.".format(
                _DECODER_SO, decoder_lib_dir))

    buffers = []
    for (load_id, base, size, path) in code_objects:
        with open(path, "rb") as f:
            data = f.read()
        buf = (_C.c_ubyte * len(data)).from_buffer_copy(data)
        buffers.append(buf)
        codeobj_load(handle, load_id, base, size or len(data),
                     _C.cast(buf, _C.c_void_p), len(data))

    gfxip = [0]
    out: List[DecodedInst] = []

    @_CB
    def cb(record_type, events_ptr, n, _user):
        if record_type == _RECORD_GFXIP and events_ptr and n:
            gfxip[0] = int(_C.cast(events_ptr, _C.POINTER(_C.c_size_t))[0]); return
        if record_type != _RECORD_WAVE or not events_ptr or not n:
            return
        waves = _C.cast(events_ptr, _C.POINTER(_Wave))
        for wi in range(int(n)):
            w = waves[wi]
            insts = w.instructions_array
            for ii in range(int(w.instructions_size)):
                it = insts[ii]
                cs = int(it._catstall)
                out.append(DecodedInst(
                    cu=int(w.cu), simd=int(w.simd), slot=int(w.wave_id),
                    issue=int(it.time), duration=int(it.duration),
                    stall=(cs >> 8) & 0xFFFFFF, category=cs & 0xFF,
                    marker_id=int(it.pc.marker_id), pc=int(it.pc.addr)))

    with open(att_path, "rb") as f:
        att_bytes = f.read()
    att_buf = (_C.c_ubyte * len(att_bytes)).from_buffer_copy(att_bytes)
    st = trace_decode(handle, cb, _C.cast(att_buf, _C.c_void_p), len(att_bytes), None)
    destroy(handle)
    if st != _ROCPROF_OK:
        raise RuntimeError("trace_decode failed status={}".format(st))
    return gfxip[0], out


def parse(dump: str, schema: Optional[Dict] = None,
          decoder_lib_dir: Optional[str] = None) -> Dict:
    """Decode every .att in ``dump`` (a directory) and aggregate per ``schema``.

    Requires ROCm to actually decode; raises a clear error otherwise. The pure
    discovery/aggregation helpers above are usable without ROCm.
    """
    schema = schema or {}
    if not os.path.isdir(dump):
        raise ValueError("expected the rocprofv2 ATT dump directory, got: {}".format(dump))
    found = discover_dump(dump)
    if not found["att_files"]:
        raise FileNotFoundError("no .att files in {}".format(dump))
    all_insts: List[DecodedInst] = []
    for att in found["att_files"]:
        _gfxip, insts = decode_att(att, found["code_objects"],
                                   decoder_lib_dir=decoder_lib_dir)
        all_insts.extend(insts)
    return aggregate(all_insts, schema)
