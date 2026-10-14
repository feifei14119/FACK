"""Single-shape upstream op_test adapter, reviewed for aiter 2abf8aaa44f9.

The AST boundary is version-specific. A changed test file must be reviewed;
never silently execute its CLI or unrelated split-K sweep.
"""
import ast
import hashlib
import importlib.util
import math
from numbers import Real
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parents[1] / "upstream"
TEST_REL = "op_tests/test_gemm_a8w8_blockscale.py"
TEST_SHA256 = "4be1b0fae5f43b786aa077673dccf2bbdcdd9a3036b7cb69f3ed93091eb0a9f3"
SYMBOL = "_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E"

_spec = importlib.util.spec_from_file_location("fack_blockscale_base", HERE / "driver.py")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
prepare = _base.prepare


def definitions(path, expected_sha=TEST_SHA256):
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected_sha:
        raise ValueError("upstream op_test changed; review adapter against the pinned commit before running")
    tree = ast.parse(source, filename=str(path))
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "parser" for t in node.targets):
            break
        body.append(node)
    else:
        raise ValueError("op_test CLI boundary is absent")
    return compile(ast.Module(body=body, type_ignores=[]), str(path), "exec")


def validate_row(row):
    for key in ("asm err", "ck err", "triton err"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value != 0:
            raise ValueError("op_test correctness failed: {}={}".format(key, value))
    for key in ("asm us", "ck us", "triton us"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid op_test time: {}={}".format(key, value))


def validate(inputs, symbol, seed):
    """Explicit once-per-evaluation hook. Any seed is valid; no hidden seed sentinel."""
    if symbol != SYMBOL:
        raise ValueError("this op_test adapter only supports its reviewed blockscale symbol")
    import torch
    import aiter

    path = UPSTREAM / TEST_REL
    namespace = {"__file__": str(path), "__name__": "fack_upstream_optest"}
    exec(definitions(path), namespace)
    original = aiter.gemm_a8w8_blockscale_bpreshuffle_asm
    original_check = namespace["checkAllclose"]
    calls, checks, rows = [], [], []

    def selected(*args, **kwargs):
        kwargs.update(kernelName=symbol, splitK=1, bpreshuffle=True)
        calls.append(symbol)
        return original(*args, **kwargs)

    def checked(a, b, *args, **kwargs):
        if not bool(torch.isfinite(a).all().item() and torch.isfinite(b).all().item()):
            raise ValueError("op_test produced nonfinite output/reference")
        ratio = original_check(a, b, *args, **kwargs)
        checks.append({"label": kwargs.get("msg"), "error_ratio": float(ratio)})
        if ratio != 0:
            raise ValueError("op_test full-output comparison failed: " + str(checks[-1]))
        return ratio

    aiter.gemm_a8w8_blockscale_bpreshuffle_asm = selected
    namespace["checkAllclose"] = checked
    try:
        for data_init, scale_init in (("constant", "constant"), ("uniform", "auto")):
            first_call, first_check = len(calls), len(checks)
            row = namespace["test_gemm"](
                aiter.dtypes.bf16, inputs["m"], inputs["n"], inputs["k"],
                ck_preshuffle=True, data_init=data_init, scale_init=scale_init, seed=seed)
            row = {k: str(v) if k == "dtype" else v for k, v in row.items()}
            validate_row(row)
            labels = {check["label"] for check in checks[first_check:]}
            if len(calls) == first_call or not {"ck", "ck strided x_scale", "asm", "triton"} <= labels:
                raise ValueError("op_test did not exercise all expected comparison paths")
            rows.append(row)
    finally:
        aiter.gemm_a8w8_blockscale_bpreshuffle_asm = original
        namespace["checkAllclose"] = original_check
    return {"correct": True, "test": TEST_REL, "test_sha256": TEST_SHA256, "function": "test_gemm",
            "symbol": symbol, "splitK": 1, "seed": seed, "asm_calls": len(calls),
            "rows": rows, "checks": checks, "timing": "upstream perftest profiler with rotating inputs"}
