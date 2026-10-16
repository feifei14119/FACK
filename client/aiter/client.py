"""Pinned aiter HSA kernels: assemble, check every output, then time graph replay."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from dataclasses import asdict

from client.aiter.common import HERE, UPSTREAM, options, source_target
from harness.evaluator import EvalResult
from harness.evidence import BuildEvidence, collect_identity
from harness import toolchain
from client.aiter.agent_profile import agent_profile, result_evidence
from client.aiter.publication import publication_candidate


def identity(ctx):
    opts, data, driver = options(ctx)
    resources = {
        "manifest": opts.manifest, "driver": driver,
        "client": HERE / "client.py", "runner": HERE / "runner.py",
        "configuration": HERE / "common.py",
        "agent_profile": HERE / "agent_profile.py",
        "publication": HERE / "publication.py",
        "original_co": UPSTREAM / "hsa" / data["arch"] / data["co"],
        "gitmodules": HERE.parent.parent / ".gitmodules",
        "python": shutil.which(opts.python),
        "assembler": toolchain._llvm_tool("clang"),
        "linker": toolchain._llvm_tool("ld.lld"),
    }
    for name in ("aiter/__init__.py", "aiter/jit/core.py", "aiter/jit/optCompilerConfig.json",
                 "aiter/ops/gemm_op_a8w8.py", "aiter/ops/shuffle.py",
                 "csrc/include/aiter_hip_common.h", "csrc/include/aiter_logger.h", "hsa/codegen.py"):
        resources["upstream:" + name] = UPSTREAM / name
    if "catalog" in data:
        resources["catalog"] = UPSTREAM / "hsa" / data["arch"] / data["catalog"]
    for name in data.get("upstream_resources", []):
        from client.aiter.common import inside
        resources["upstream:" + name] = inside(UPSTREAM, name)
    for name, path in data.get("resources", {}).items():
        resources["driver:" + name] = Path(opts.manifest).parent / path
    if "dispatch" in data:
        resources["dispatch_snapshot"] = Path(opts.manifest).parent / data["dispatch"]["snapshot"]
        resources["dispatch_code"] = HERE / "dispatch.py"
        resources["dispatch_gemm_driver"] = HERE / "hsa/gfx942/gemm_driver.py"
    gitfile = UPSTREAM / ".git"
    if gitfile.is_file():
        gitdir = (UPSTREAM / gitfile.read_text().strip()[8:]).resolve()
    else:
        gitdir = gitfile
    resources["upstream_HEAD"] = gitdir / "HEAD"
    if (gitdir / "HEAD").is_file():
        head = (gitdir / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = gitdir / head[5:]
            resources["upstream_ref"] = ref if ref.is_file() else gitdir / "packed-refs"
    return {"resources": resources, "environment": [
        "PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONPATH", "ROCM_PATH", "ROCM_LLVM_BIN",
        "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES",
        "GPU_DEVICE_ORDINAL", "HSA_XNACK", "HSA_USE_SVM", "HSA_ENABLE_SDMA",
        "HIP_FORCE_DEV_KERNARG", "HSA_FORCE_FINE_GRAIN_PCIE", "OMP_NUM_THREADS",
    ]}


def describe(ctx):
    _, data, _ = options(ctx)
    return "aiter {}: {}; params: --m/--n/--k --python --iters --samples --warmup --timeout --manifest".format(data["arch"], data["co"])


def run_process(argv, log, timeout, env=None, cwd=None):
    """Kill the whole process group on timeout, including JIT compiler children."""
    with Path(log).open("a") as stream:
        proc = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                env=env, cwd=cwd, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            raise
    if code:
        raise RuntimeError("process exited {}; see {}".format(code, log))


def overlay_tree(source, dest, selected):
    """Materialize only selected path's ancestors; everything else is a symlink."""
    dest.mkdir()
    for entry in source.iterdir():
        target = dest / entry.name
        if entry.name == selected.parts[0]:
            if len(selected.parts) > 1:
                overlay_tree(entry, target, Path(*selected.parts[1:]))
            # The selected .co is built directly into this empty slot.
        else:
            target.symlink_to(entry, target_is_directory=entry.is_dir())


class AiterEvaluator:
    def __init__(self, ctx):
        self.ctx = ctx
        self.opts, self.config, self.driver = options(ctx)
        if ctx.seed_src:
            source_target(ctx.seed_src, self.config["arch"], self.config["symbol"])

    def evaluate(self, s_path, with_counters=False):
        opts, config = self.opts, self.config
        output_dir = opts.output_dir or self.ctx.out_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="eval-", dir=output_dir))
        result = EvalResult(compiled=False, detail={"work_dir": str(work)})
        evidence = BuildEvidence(s_path, lambda: collect_identity(**identity(self.ctx)))
        try:
            if evidence.data["identity_before"]["status"] != "available":
                raise ValueError("client dependencies are incomplete; inspect build_evidence")
            target, cov = source_target(Path(s_path).read_text(), config["arch"], config["symbol"])
            stage = work / "hsa"
            stage.mkdir()
            overlay_tree(UPSTREAM / "hsa" / config["arch"], stage / config["arch"], Path(config["co"]))
            co = stage / config["arch"] / config["co"]
            obj = work / "candidate.o"
            run_process([toolchain._llvm_tool("clang"), "-x", "assembler", "-target",
                         "amdgcn-amd-amdhsa", "-mcpu=" + target,
                         "-mcode-object-version=" + str(cov), "-c", str(Path(s_path).resolve()),
                         "-o", str(obj)], work / "build.log", opts.timeout)
            run_process([toolchain._llvm_tool("ld.lld"), "-shared", str(obj), "-o", str(co)],
                        work / "build.log", opts.timeout)
            result.compiled = True
            if not evidence.after_build(str(co)):
                raise ValueError("build evidence changed before evaluation")
            request = dict(config, driver=str(self.driver), upstream=str(UPSTREAM),
                           hsa_dir=str(stage), co_path=str(co),
                           co_sha256=evidence.data["artifact_after_build"]["sha256"],
                           seed=opts.seed, warmup=opts.warmup, iters=opts.iters, samples=opts.samples,
                           log_path=str(work / "runner.log"))
            if "dispatch" in config:
                # aiter receives a disposable copy, never the upstream table or
                # the frozen plan. Install its env override before importing it.
                from client.aiter.dispatch import validate_binding
                snapshot = validate_binding(config, opts.manifest, UPSTREAM)
                frozen_copy = work / "dispatch-config.csv"
                shutil.copyfile(snapshot, frozen_copy)
                request["dispatch_snapshot"] = str(frozen_copy)
            (work / "request.json").write_text(json.dumps(request, indent=2) + "\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith("AITER_")}
            for key in ("CK_DIR", "HIP_KITTENS_DIR", "GPU_ARCHS", "PYTHONPATH"):
                env.pop(key, None)
            cache_inputs = {k: v for k, v in evidence.data["identity_before"]["resources"].items()
                            if k.startswith("upstream") or k in ("catalog", "python", "assembler", "linker")}
            cache_key = hashlib.sha256(json.dumps(cache_inputs, sort_keys=True).encode()).hexdigest()[:20]
            cache_dir = Path(output_dir).resolve() / "jit" / config["arch"] / cache_key
            # aiter's cpp_itfs cache is separate from its legacy JIT cache.
            # Both must be writable even when the container UID has no home.
            env.update(AITER_META_DIR=str(UPSTREAM), AITER_JIT_DIR=str(cache_dir),
                       AITER_ROOT_DIR=str(cache_dir / "cpp_itfs"),
                       AITER_ASM_DIR=str(stage), AITER_LOG_LEVEL="INFO", AITER_AOT_IMPORT="0",
                       AITER_TRITON_ONLY="0", GPU_ARCHS=config["arch"], PYTHONDONTWRITEBYTECODE="1")
            run_process([opts.python, "-B", str(HERE / "runner.py"), str(work / "request.json"),
                         str(work / "result.json")], work / "runner.log", opts.timeout, env, str(work))
            report = json.loads((work / "result.json").read_text())
            result.detail["runner"] = report
            if report.get("error"):
                raise ValueError(report["error"])
            if "dispatch" in config:
                checked = report.get("dispatch_check", {})
                if (checked.get("correct") is not True or
                        checked.get("workload_id") != config["dispatch"]["workload_id"] or
                        checked.get("cu_num") != config["dispatch"]["cu_num"]):
                    raise ValueError("runner did not verify the frozen workload's normal dispatch")
            # A basic full-output failure stops the runner before op_test.
            # Preserve its explicit false verdict rather than masking it as
            # missing secondary validation. Successful cases still require it.
            if (report.get("correct") is True and config.get("validation_hook") and
                    report.get("op_test", {}).get("correct") is not True):
                raise ValueError("runner did not report the required driver validation")
            if (report.get("schema_version") != 1 or report.get("co_sha256") != request["co_sha256"] or
                    report.get("arch") != config["arch"] or report.get("symbol") != config["symbol"] or
                    report.get("loader_observed") is not True):
                raise ValueError("runner did not confirm expected candidate loader record")
            if report.get("correct") is False:
                result.correct = False
            elif report.get("correct") is True:
                time_us, flops = report.get("time_us"), report.get("flops")
                if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (time_us, flops)):
                    raise ValueError("runner returned invalid timing/FLOP count")
                result.correct, result.time_us = True, time_us
                result.tflops = flops / time_us / 1e6
            else:
                raise ValueError("runner returned no numerical verdict")
        except Exception as exc:
            result.detail["error"] = str(exc)
        finally:
            data = evidence.finish()
            result.detail["build_evidence"] = data
            if data["status"] != "consistent":
                result.correct = result.time_us = result.tflops = None
                result.detail["evidence_error"] = "source/artifact/declared inputs changed or build incomplete"
            if with_counters:
                result.detail["counter_error"] = "aiter client does not implement hardware counters yet"
            if "runner" in result.detail:
                try:
                    result.detail["validation"] = result_evidence(config, result.detail["runner"], data)
                except (ValueError, KeyError, TypeError) as exc:
                    result.detail["validation_error"] = str(exc)
                    result.correct = result.time_us = result.tflops = None
            # Preserve the client verdict after build/identity checks, so the
            # UI never mistakes a raw runner success for an accepted evaluation.
            summary = work / "evaluation.json"
            temporary = summary.with_suffix(".json.tmp")
            try:
                temporary.write_text(json.dumps(asdict(result), indent=2, allow_nan=False) + "\n")
                temporary.replace(summary)
            except (OSError, ValueError, TypeError) as exc:
                result.detail["evaluation_summary_error"] = str(exc)
        return result


def make_evaluator(ctx):
    return AiterEvaluator(ctx)
