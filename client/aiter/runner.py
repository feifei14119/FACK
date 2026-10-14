#!/usr/bin/env python3
"""One fresh target-machine process per candidate. Never imported by the engine."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import traceback


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def loader_observed(request):
    # A host-side loader record, not GPU dispatch attestation.
    text = Path(request["log_path"]).read_text(errors="replace")
    matches = re.findall(r"\[aiter\] LoadKernel: (\S+) hsaco: (.+)", text)
    paths = [path.strip() for symbol, path in matches if symbol == request["symbol"]]
    return bool(paths) and all(Path(path).resolve() == Path(request["co_path"]).resolve() for path in paths)


def validate_driver(driver, request):
    """Run an explicitly requested validation stage once, outside GPU timing."""
    hook = getattr(driver, "validate", None)
    if not callable(hook):
        raise ValueError("manifest requires a driver.validate hook")
    result = hook(dict(request["inputs"]), request["symbol"], request["seed"])
    if not isinstance(result, dict) or result.get("correct") is not True:
        raise ValueError("driver validation did not pass")
    return result


def execute(request, report):
    import torch

    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError("a ROCm PyTorch GPU environment is required")
    torch.cuda.set_device(0)  # select through HIP_VISIBLE_DEVICES/ROCR_VISIBLE_DEVICES
    props = torch.cuda.get_device_properties(0)
    arch = props.gcnArchName.split(":")[0]
    report.update(arch=arch, device=str(props), torch_version=str(torch.__version__),
                  hip_version=torch.version.hip)
    if arch != request["arch"]:
        raise RuntimeError("device {} differs from requested {}".format(arch, request["arch"]))
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.set_grad_enabled(False)

    upstream = Path(request["upstream"]).resolve()
    sys.path.insert(0, str(upstream))
    import aiter
    from aiter.jit import core

    if Path(aiter.__file__).resolve() != upstream / "aiter" / "__init__.py":
        raise RuntimeError("imported a different aiter checkout")
    # core overwrites AITER_ASM_DIR on import. Reset it AND all already-imported
    # copies before preparing inputs or invoking any operator. Keep META stable
    # so the external JIT cache can be reused between fresh processes.
    asm_dir = request["hsa_dir"]
    os.environ["AITER_ASM_DIR"] = asm_dir
    for name, module in list(sys.modules.items()):
        if (name == "aiter" or name.startswith("aiter.")) and hasattr(module, "AITER_ASM_DIR"):
            module.AITER_ASM_DIR = asm_dir
    core.get_asm_dir.cache_clear()
    if Path(core.get_asm_dir()).resolve() != Path(asm_dir) / arch:
        raise RuntimeError("aiter assembly directory redirection failed")

    spec = importlib.util.spec_from_file_location("aiter_tuning_driver", request["driver"])
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    checks = []
    report["checks"] = checks

    def compare(case, label):
        outputs, refs = case["outputs"], case["reference"]
        if (not isinstance(outputs, (list, tuple)) or not isinstance(refs, (list, tuple)) or
                not outputs or len(outputs) != len(refs)):
            raise ValueError("driver must declare every output and independent reference")
        errors = []
        passed = True
        for output, ref in zip(outputs, refs):
            if (not isinstance(output, torch.Tensor) or not isinstance(ref, torch.Tensor) or
                    output.shape != ref.shape or output.numel() == 0 or output.data_ptr() == ref.data_ptr()):
                raise ValueError("invalid/aliased driver output or reference")
            a, b = output.float(), ref.float()
            finite = bool(torch.isfinite(a).all().item() and torch.isfinite(b).all().item())
            passed &= finite and torch.allclose(a, b, atol=request["atol"], rtol=request["rtol"])
            errors.append(float((a - b).abs().max().item()) if finite else None)
        checks.append({"case": label, "passed": bool(passed), "max_abs_error": errors})
        return bool(passed)

    def poison(case):
        for output in case["outputs"]:
            if not output.is_floating_point() or not output.is_cuda:
                raise ValueError("this runner requires floating point GPU outputs")
            output.fill_(float("nan"))

    # Two reproducible signed input sets. Reference is computed before run().
    for offset in range(2):
        case = driver.prepare(dict(request["inputs"]), request["symbol"], request["seed"] + offset)
        poison(case)
        case["run"]()
        torch.cuda.synchronize()
        report["loader_observed"] = loader_observed(request)
        if not report["loader_observed"]:
            raise RuntimeError("expected .co/symbol absent from aiter loader log; no timing accepted")
        if not compare(case, "seed+{}".format(offset)):
            report["correct"] = False
            return
        if offset == 0:
            del case

    flops = case["flops"]
    if type(flops) not in (int, float) or not math.isfinite(flops) or flops <= 0:
        raise ValueError("driver must supply a positive FLOP count per run()")
    if request.get("validation_hook"):
        report["op_test"] = validate_driver(driver, request)
        if not loader_observed(request):
            raise RuntimeError("validation hook loaded an unexpected candidate path")
    # Warm up on a side stream, capture repeated launches, and time graph replay
    # to keep Python/ctypes launch overhead out of short-kernel comparisons.
    stream = torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for _ in range(request["warmup"]):
            case["run"]()
    torch.cuda.current_stream().wait_stream(stream)
    torch.cuda.synchronize()
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph, stream=stream):
        for _ in range(request["iters"]):
            case["run"]()
    graph.replay()
    torch.cuda.synchronize()
    timings = []
    for _ in range(request["samples"]):
        start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record()
        graph.replay()
        end.record()
        end.synchronize()
        timings.append(start.elapsed_time(end) * 1000.0 / request["iters"])
    poison(case)
    graph.replay()
    torch.cuda.synchronize()
    if not compare(case, "after_graph_replay"):
        report["correct"] = False
        return
    report.update(correct=True, time_us=statistics.median(timings), samples_us=timings,
                  flops=flops, timing="HIP graph replay event median per run()",
                  validation="two input seeds plus post-timing full-output comparison")


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    result_path = Path(sys.argv[2])
    report = {"schema_version": 1, "correct": None, "symbol": request["symbol"],
              "co_sha256": digest(request["co_path"]), "loader_observed": False,
              "loader_scope": "host loader path/symbol log only; GPU dispatch unverified"}
    try:
        if report["co_sha256"] != request["co_sha256"]:
            raise RuntimeError("candidate bytes changed before runner start")
        execute(request, report)
        if digest(request["co_path"]) != request["co_sha256"]:
            raise RuntimeError("candidate bytes changed during execution")
    except Exception:
        report["error"] = traceback.format_exc()
        report["correct"] = None
        report.pop("time_us", None)
        report.pop("flops", None)
    result_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
