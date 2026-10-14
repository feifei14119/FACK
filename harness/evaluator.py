"""Self-contained, pluggable evaluation boundary (three phases).

testft does NOT depend on any external project for evaluation. The three-phase
contract (correctness -> performance -> perf-counter dump) is defined here; a
real GPU-backed implementation is supplied later by the user's test case. M0
ships only the interface plus a compile-only default.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol




@dataclass
class EvalResult:
    compiled: bool
    correct: Optional[bool] = None            # None = not run (no GPU / compile-only)
    time_us: Optional[float] = None           # phase 2: kernel execution time
    tflops: Optional[float] = None            # derived from time_us + problem size
    counter_dump_path: Optional[str] = None   # phase 3: raw HW perf counter file
    counters: Optional[Dict] = None           # parsed counters (analysis.perf)
    direction: Optional[Dict] = None          # bottleneck + next-round hints (analysis.bottleneck)
    detail: Dict = field(default_factory=dict)


class Evaluator(Protocol):
    """Three-phase evaluation, with short-circuit on earlier-phase failure."""

    def assemble(self, s_path: str) -> str: ...                       # .s -> .o/.co (raises on failure)
    def check_correctness(self, s_path: str) -> bool: ...             # phase 1
    def measure_perf(self, s_path: str) -> float: ...                 # phase 2 -> microseconds
    def dump_counters(self, s_path: str, out_path: str) -> str: ...   # phase 3 -> file path
    def evaluate(self, s_path: str) -> EvalResult: ...                # orchestrates 1->2->3


class CompileOnlyEvaluator:
    """Default evaluator: only checks that the candidate still assembles.

    No GPU required. ``correct``/``time_us``/``tflops`` stay None. Useful for
    M0-M4 plumbing and for filtering candidates before any real-machine run.
    """

    def __init__(self, toolchain=None):
        # Imported lazily so M0 has no hard dependency on a working toolchain.
        self._toolchain = toolchain

    def assemble(self, s_path: str) -> str:
        if self._toolchain is None:
            from . import toolchain as _tc
            self._toolchain = _tc
        return self._toolchain.assemble(s_path)

    def evaluate(self, s_path: str) -> EvalResult:
        from .evidence import BuildEvidence
        evidence = BuildEvidence(s_path)
        try:
            artifact = self.assemble(s_path)
            evidence.after_build(artifact)
            data = evidence.finish()
            return EvalResult(compiled=data["status"] == "consistent",
                              detail={"mode": "compile-only", "build_evidence": data})
        except Exception as exc:  # noqa: BLE001 - report compile failure as result
            return EvalResult(compiled=False, detail={"error": str(exc),
                                                     "build_evidence": evidence.finish()})


# --- pure stdout parsing helpers (unit-tested without a GPU) ---------------
_PERF_RE = re.compile(
    r"time:\s*([0-9.]+).*?gflops:\s*([0-9.]+)", re.IGNORECASE | re.DOTALL)


def parse_correctness_stdout(text: str) -> Optional[bool]:
    if "#TEST PASSED" in text:
        return True
    if "#TEST FAILED" in text:
        return False
    return None


def parse_perf_stdout(text: str):
    """Return (time_ms_per_loop, gflops) from a gemm.exe perf line, or (None, None)."""
    m = _PERF_RE.search(text)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))




class GpuTestcaseEvaluator:
    """GPU-backed three-phase evaluator for any testft testcase (kernel-agnostic;
    fp8 GEMM is just the default exe_name).

    Mapping (see proj/testcase_integration.md); <exe>/<co> are exe_name/co_name:
      assemble        -> clang++ assemble candidate .s into <dir>/<co>
      check_correctness -> ./<exe> dump_result=1, look for '#TEST PASSED'
      measure_perf    -> ./<exe> dump_result=0 total_loop=N, parse time/gflops
      dump_counters   -> rocprofv2 -i input.txt --plugin att auto -d <out> ./<exe>
      evaluate        -> orchestrate with short-circuit + analysis (perf/bottleneck)

    Requires a GPU + ROCm; constructed with the testcase directory. The class is
    importable and its parsing helpers are testable without hardware.
    """

    def __init__(self, testcase_dir: str, target=None, device: int = 1,
                 total_loop: int = 20, gfx_target: Optional[str] = None,
                 k: Optional[int] = None, kernel_name: Optional[str] = None,
                 exe_params: Optional[list] = None,
                 exe_name: str = "gemm.exe", co_name: Optional[str] = None):
        self.dir = testcase_dir
        self.target = target
        self.device = device
        self.total_loop = total_loop
        self.gfx_target = gfx_target               # None = from the candidate's .amdgcn_target
        self.k = k                                 # legacy GEMM-only shortcut; None = exe default
        # Testcase params forwarded VERBATIM to the program under test. Kernel-
        # agnostic: GEMM uses ["m=..","n=..","k=.."], another kernel its own
        # tokens (e.g. ["--qhead","64","--ctx_len","128"]). The harness never
        # interprets these -- only dump_result/total_loop (its perf/correctness
        # mode toggles) are injected by the harness itself.
        self.exe_params = [str(p) for p in (exe_params or [])]
        # ATT capture must target the kernel UNDER TEST. The engine is kernel-
        # agnostic: when not given explicitly, the name is auto-detected from the
        # candidate .s in dump_counters (target.kernel_symbols). Never hardcoded.
        self.kernel_name = kernel_name
        # ATT is sampling-based: a single capture is nondeterministic (often
        # near-empty). Retry until the trace has real wave data, then stop.
        self.att_retries = 6
        self.att_min_bytes = 8192          # total .att bytes signalling a useful capture
        # Kernel-agnostic: the program under test is <dir>/<exe_name> and it loads
        # a code object named <co_name>. The harness assembles each candidate .s
        # into that .co so the exe picks it up. co_name defaults to the exe stem
        # (gemm.exe -> gemm.co, mla.exe -> mla.co), matching the testcase's HSACO.
        self.exe_name = exe_name
        self.co_name = co_name or (os.path.splitext(os.path.basename(exe_name))[0] + ".co")
        self.co_path = os.path.join(testcase_dir, self.co_name)
        self.exe_path = os.path.join(testcase_dir, self.exe_name)
        # Optional read-only client resource snapshot, supplied by the client.
        self.identity_provider = None
        self._last_build = None

    def arch(self, s_path: str) -> str:
        from . import toolchain as _tc
        return self.gfx_target or _tc.arch_of(s_path)

    def assemble(self, s_path: str) -> str:
        from . import toolchain as _tc
        from .evidence import file_identity
        # The output must be newly produced in this call. A failed/no-op compiler
        # cannot silently reuse an old .co left by a previous candidate.
        self._last_build = None
        with tempfile.TemporaryDirectory(prefix=".testft-build-", dir=self.dir) as stage:
            output = os.path.join(stage, os.path.basename(self.co_path))
            _tc.assemble_codeobject(s_path, output, self.arch(s_path))
            built = file_identity(output)
            if built["status"] != "present":
                raise RuntimeError("assembler did not produce a regular code object")
            os.replace(output, self.co_path)
            self._last_build = {"strategy": "fresh_output_atomic_replace",
                                "staged_artifact": built}
        return self.co_path

    def _evidence_identity(self, s_path):
        if self.identity_provider is not None:
            return self.identity_provider()
        from .evidence import collect_identity, codeobject_tools
        resources = codeobject_tools(self.arch(s_path))
        resources["test_executable"] = self.exe_path
        return collect_identity(resources, ["PATH", "ROCM_LLVM_BIN", "LD_LIBRARY_PATH",
                                            "LD_PRELOAD", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"])

    def _run_exe(self, extra_args):
        cmd = [self.exe_path] + list(extra_args) + list(self.exe_params)
        if self.k is not None:
            cmd.append("k={}".format(self.k))
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True)

    def check_correctness(self, s_path: str) -> Optional[bool]:
        out = self._run_exe(["dump_result=1"])
        return parse_correctness_stdout(out.stdout + out.stderr)

    def measure_perf(self, s_path: str):
        out = self._run_exe(["dump_result=0", "total_loop={}".format(self.total_loop)])
        return parse_perf_stdout(out.stdout + out.stderr)

    def detect_kernel_name(self, s_path: str) -> Optional[str]:
        """The kernel symbol to trace: explicit ``kernel_name`` wins, else it is
        auto-detected from the candidate .s (so ANY kernel works, not just gemm)."""
        if self.kernel_name:
            return self.kernel_name
        if self.target is not None and hasattr(self.target, "kernel_symbols"):
            try:
                from reorder import parser as _parser
                syms = self.target.kernel_symbols(_parser.parse_file(s_path))
                if syms:
                    return syms[0]
            except Exception:  # noqa: BLE001 - detection is best-effort
                pass
        return None

    def _write_att_config(self, kernel_name: Optional[str]) -> str:
        """Generate a per-run ATT config from ``input.txt`` (the att-PARAMS
        template), injecting ``KERNEL=<kernel_name>`` so capture targets the
        kernel under test. Returns the config filename (relative to self.dir)."""
        params: list = []
        template = os.path.join(self.dir, "input.txt")
        if os.path.exists(template):
            with open(template) as f:
                for raw in f:
                    s = raw.rstrip("\n")
                    low = s.strip()
                    # drop comments + any pre-existing kernel/dispatch SELECTION;
                    # we own which kernel/dispatch to capture.
                    if not low or low.startswith("#") \
                            or low.startswith("KERNEL=") or low.startswith("DISPATCH="):
                        continue
                    params.append(s)
        if not params:
            params = ["att: TARGET_CU=F", "SE_MASK=0x0F", "SIMD_SELECT=0xF",
                      "ISA_CAPTURE_MODE=2", "BUFFER_SIZE=100"]
        if kernel_name:
            params.append("KERNEL=" + kernel_name)
        cfg_name = "_att_input.txt"
        with open(os.path.join(self.dir, cfg_name), "w") as f:
            f.write("\n".join(params) + "\n")
        return cfg_name

    def dump_counters(self, s_path: str, out_path: str) -> str:
        rocprof = shutil.which("rocprofv2") or "rocprofv2"
        kernel = self.detect_kernel_name(s_path)
        cfg = self._write_att_config(kernel)
        exe_args = [self.exe_path] + list(self.exe_params)
        if self.k is not None:
            exe_args.append("k={}".format(self.k))
        cmd = [rocprof, "-i", cfg, "--plugin", "att", "auto",
               "-d", out_path] + exe_args
        from analysis import perf as _perf
        proc = None
        total = 0
        # ATT sampling is nondeterministic -> retry until we get real wave data.
        for _ in range(max(1, self.att_retries)):
            if os.path.isdir(out_path):
                shutil.rmtree(out_path, ignore_errors=True)
            proc = subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True)
            # rocprofv2's OWN att.py visualiser often fails (missing
            # librocprofv2_att.so) AFTER the raw trace is written; we decode the
            # .att ourselves, so success == .att present, not rocprofv2's rc.
            atts = _perf.discover_dump(out_path)["att_files"]
            total = sum(os.path.getsize(a) for a in atts)
            if total >= self.att_min_bytes:
                break
        if not _perf.discover_dump(out_path)["att_files"]:
            raise RuntimeError(
                "rocprofv2 att produced no .att files (rc={}, kernel={!r}): {}".format(
                    proc.returncode if proc else "?", kernel,
                    (proc.stderr or proc.stdout)[-500:] if proc else ""))
        return out_path



    def evaluate(self, s_path: str, with_counters: bool = False) -> EvalResult:
        from .evidence import BuildEvidence
        evidence = BuildEvidence(s_path, lambda: self._evidence_identity(s_path))
        self._last_build = None

        def finish(result):
            data = evidence.finish()
            data["build"] = self._last_build or {"strategy": "client_defined"}
            result.detail["build_evidence"] = data
            if result.compiled and data["status"] != "consistent":
                # Preserve raw client verdicts without classifying identity drift
                # as a numerical failure or allowing its score to be compared.
                result.detail["reported_result"] = {
                    "correct": result.correct, "time_us": result.time_us, "tflops": result.tflops}
                result.detail["evidence_error"] = "source, artifact, or declared resource identity is inconsistent"
                result.correct = result.time_us = result.tflops = None
            return result

        try:
            artifact = self.assemble(s_path)
        except Exception as exc:  # noqa: BLE001
            evidence.after_build()
            return finish(EvalResult(compiled=False, detail={"error": str(exc)}))

        evidence.after_build(artifact)
        if self._last_build is not None:
            staged = self._last_build["staged_artifact"]
            installed = evidence.data["artifact_after_build"]
            evidence.data["checks"]["artifact_matches_staged"] = (
                installed.get("sha256") == staged["sha256"] and
                installed.get("size") == staged["size"])
        if not all(evidence.data["checks"].values()):
            return finish(EvalResult(compiled=True, detail={"phase": "build_evidence"}))

        try:
            correct = self.check_correctness(s_path)
        except Exception as exc:  # noqa: BLE001
            return finish(EvalResult(compiled=True, detail={"phase": "correctness", "error": str(exc)}))

        if correct is False:
            return finish(EvalResult(compiled=True, correct=False, detail={"phase": "correctness"}))

        try:
            time_ms, gflops = self.measure_perf(s_path)
        except Exception as exc:  # noqa: BLE001
            return finish(EvalResult(compiled=True, correct=correct,
                                     detail={"phase": "performance", "error": str(exc)}))
        res = EvalResult(compiled=True, correct=correct,
                         time_us=(time_ms * 1000.0 if time_ms is not None else None),
                         tflops=(gflops / 1000.0 if gflops is not None else None),
                         detail={"gflops": gflops})
        if with_counters:
            try:
                out_dir = os.path.join(self.dir, "att")
                self.dump_counters(s_path, out_dir)
                res.counter_dump_path = out_dir
                from analysis import perf as _perf, bottleneck as _bn
                schema = self.target.perf_counter_schema() if self.target else {}
                res.counters = _perf.parse(out_dir, schema)
                res.direction = _bn.classify(res.counters, schema)
            except Exception as exc:  # noqa: BLE001 - counters are best-effort
                res.detail["counter_error"] = str(exc)
        return finish(res)
