"""Verify normal aiter dispatch, then reuse the reviewed fixed-symbol GEMM test.

The observer does not inject a kernelName or splitK. A mismatching public-API
selection is rejected before its ASM call. This is host dispatch evidence, not
GPU ATT. Timed runs still measure only the selected ASM operation.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("aiter_dispatch_gemm", Path(__file__).with_name("gemm_driver.py"))
gemm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gemm)


def adapter(inputs):
    if inputs["family"] in ("i8", "bf16"):
        return gemm
    if inputs["family"] == "blockscale":
        # Keep the blockscale adapter out of the INT8/BF16 import path. Its
        # source and base driver are separately frozen by blockscale manifests.
        spec = importlib.util.spec_from_file_location("aiter_dispatch_blockscale", Path(__file__).with_name("optest_driver.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ValueError("unreviewed dispatch input family")


def prepare(inputs, symbol, seed):
    return adapter(inputs).prepare(inputs, symbol, seed)


def validate(inputs, symbol, seed):
    return adapter(inputs).validate(inputs, symbol, seed)


def assert_selection(symbol, split_k, shuffled, binding):
    if (symbol != binding["symbol"] or split_k != binding["inputs"]["splitK"] or
            bool(shuffled) != binding["inputs"]["bpreshuffle"]):
        raise ValueError("normal dispatch selected a different kernel, splitK or layout")
    return {"symbol": symbol, "splitK": int(split_k), "bpreshuffle": bool(shuffled)}


def normal_call(module, inputs, extra, binding, torch):
    """Observe the low-level arguments of an otherwise unchanged public call."""
    observed = []
    if inputs["family"] == "i8":
        name = "gemm_a8w8_asm"
        original = getattr(module, name)

        def tracked(a, b, sa, sb, out, kernelName="", bias=None, bpreshuffle=True, splitK=None):
            observed.append(assert_selection(kernelName, splitK, bpreshuffle, binding))
            out.fill_(float("nan"))
            return original(a, b, sa, sb, out, kernelName, bias, bpreshuffle, splitK)

        def call():
            return module.gemm_a8w8_ASM(extra["a"], extra["packed"], extra["sa"], extra["sb"],
                                        bias=extra["bias"], dtype=torch.bfloat16)
    elif inputs["family"] == "blockscale":
        name = "gemm_a8w8_blockscale_bpreshuffle_asm"
        original = getattr(module, name)

        def tracked(a, b, out, sa, sb, bias=None, splitK=None, kernelName=None,
                    bpreshuffle=True, zero_bias_buf=None):
            observed.append(assert_selection(kernelName, splitK, bpreshuffle, binding))
            if bias is not None:
                raise ValueError("normal blockscale dispatch supplied an unexpected bias")
            out.fill_(float("nan"))
            # Preserve public-API selection and let the original wrapper
            # allocate its zero bias. Do not inject the timed run's buffer.
            return original(a, b, out, sa, sb, bias, splitK, kernelName, bpreshuffle, zero_bias_buf)

        def call():
            return module.gemm_a8w8_blockscale_bpreshuffle(
                extra["a"], extra["packed"], extra["packed_sa"], extra["sb"], dtype=torch.bfloat16)
    elif inputs["family"] == "bf16":
        name = "gemm_a16w16_asm"
        original = getattr(module, name)
        if inputs["bpreshuffle"]:
            extra["packed"].is_shuffled = True

        def tracked(a, b, out, bias=None, splitK=None, kernelName=None, bpreshuffle=False):
            observed.append(assert_selection(kernelName, splitK, bpreshuffle, binding))
            out.fill_(float("nan"))
            return original(a, b, out, bias, splitK, kernelName, bpreshuffle)

        def call():
            return module.gemm_a16w16(extra["a"], extra["packed"], bias=None, otype=torch.bfloat16)
    else:
        raise ValueError("unreviewed dispatch input family")
    setattr(module, name, tracked)
    try:
        output = call()
    finally:
        setattr(module, name, original)
    if len(observed) != 1:
        raise ValueError("normal entrypoint did not make exactly one expected ASM call")
    return output, observed


def check_dispatch(inputs, symbol, seed, binding):
    import importlib
    import torch
    case = prepare(inputs, symbol, seed + 200003)
    module = importlib.import_module("aiter.ops.gemm_op_a8w8" if inputs["family"] in ("i8", "blockscale") else "aiter.tuned_gemm")
    output, calls = normal_call(module, inputs, case["_inputs"], binding, torch)
    torch.cuda.synchronize()
    ref = case["reference"][0]
    if (output.shape != ref.shape or not bool(torch.isfinite(output).all().item()) or
            not torch.allclose(output.float(), ref.float(), atol=0.05, rtol=0.02)):
        raise ValueError("normal-entrypoint full-output comparison failed")
    return {"correct": True, "entrypoint": binding["entrypoint"], "calls": calls,
            "workload_id": binding["workload_id"], "cu_num": binding["cu_num"],
            "snapshot_sha256": binding["snapshot_sha256"],
            "max_abs_error": float((output.float() - ref.float()).abs().max().item()),
            "scope": "normal public API with frozen config override; observed host ASM selection, not GPU ATT"}
