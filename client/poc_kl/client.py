"""poc_kl gfx942 client, using the classic executable protocol.

The candidate .s is assembled into <case>/<exe stem>.co. Correctness requires
#TEST PASSED; performance is parsed from time/gflops. Parameters after -- are
forwarded to the executable verbatim.
"""
import os

from harness.evaluator import GpuTestcaseEvaluator

EXE_CASES = {
    "fp8_blockscale_gemm": {"exe": "gemm.exe"},
}


def _exe_case(ctx):
    return EXE_CASES.get(ctx.case)


def _unknown(ctx):
    return ValueError("poc_kl has no case {!r} (known: {})".format(
        ctx.case, ", ".join(sorted(EXE_CASES))))


def make_evaluator(ctx):
    case = _exe_case(ctx)
    if not case:
        raise _unknown(ctx)
    evaluator = GpuTestcaseEvaluator(ctx.case_dir, target=ctx.target, total_loop=ctx.loop,
                                    kernel_name=ctx.kernel, exe_params=ctx.params,
                                    exe_name=case["exe"])
    from harness.evidence import collect_identity
    evaluator.identity_provider = lambda: collect_identity(**identity(ctx))
    return evaluator


def identity(ctx):
    """Declare stable build/test inputs without running an external program."""
    from harness.evidence import codeobject_tools
    from isa.registry import arch_of_source
    case = _exe_case(ctx)
    if not case:
        raise _unknown(ctx)
    resources = codeobject_tools(arch_of_source(ctx.seed_src))
    resources["client_implementation"] = __file__
    resources["test_executable"] = os.path.join(ctx.case_dir, case["exe"])
    resources["att_template"] = os.path.join(ctx.case_dir, "input.txt")
    environment = ["PATH", "ROCM_PATH", "ROCM_LLVM_BIN", "LD_LIBRARY_PATH", "LD_PRELOAD",
                   "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES",
                   "GPU_DEVICE_ORDINAL", "HSA_XNACK", "HSA_USE_SVM", "HSA_ENABLE_SDMA",
                   "HIP_FORCE_DEV_KERNARG", "OMP_NUM_THREADS"]
    return {"resources": resources, "environment": environment}


def describe(ctx):
    case = _exe_case(ctx)
    if not case:
        raise _unknown(ctx)
    return "poc_kl/{}: ./{} (exe protocol, params {})".format(
        ctx.case, case["exe"], " ".join(ctx.params) or "none")
