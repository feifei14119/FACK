"""Explicit BF16 / per-token INT8 GEMM adapters for the pinned gfx942 catalogs.

Validation uses the named upstream benchmark wrappers only, not the complete
multi-backend test_gemm suite. Graph timing remains the selected operator run.
"""
import ast
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

UPSTREAM = Path(__file__).resolve().parents[2] / 'upstream'
TESTS = {
    'bf16': ('op_tests/test_gemm_a16w16.py', '3677e1d60a7c08e50c82d5bbfc1a1de08ef0d2fef99650dfa65aa7dbdbb6489a', 'run_bf16gemm_asm'),
    'i8': ('op_tests/test_gemm_a8w8.py', 'ae1226beb297b8d4de63fbcbf0baa72bf924e145f13425ddc3714dfd0cd2d653', 'run_gemm_asm'),
}


def benchmark_definitions(family):
    relative, expected, name = TESTS[family]
    path = UPSTREAM / relative
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError('upstream benchmark changed; review adapter before executing')
    tree = ast.parse(source, filename=str(path))
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in (name, 'run_torch')]
    if len(body) != 2:
        raise ValueError('missing reviewed benchmark functions')
    return compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec')


def prepare(inputs, symbol, seed):
    import torch
    from aiter.ops.shuffle import shuffle_weight
    from aiter.ops.gemm_op_a16w16 import gemm_a16w16_asm
    from aiter.ops.gemm_op_a8w8 import gemm_a8w8_asm
    family = inputs['family']
    m, n, k = (inputs[x] for x in ('m', 'n', 'k'))
    if family not in TESTS or any(type(v) is not int or v <= 0 for v in (m, n, k)):
        raise ValueError('invalid GEMM input')
    if n % (256 if family == 'i8' else 64) or k % 128:
        raise ValueError('GEMM requires aligned N and K')
    gen = torch.Generator(device='cuda').manual_seed(seed)
    bias = None
    if family == 'bf16':
        if 'bf16gemm_fp32bf16_' not in symbol:
            raise ValueError('BF16 symbol mismatch')
        a = (torch.randn((m, k), generator=gen, device='cuda') * 0.25).bfloat16()
        b = (torch.randn((n, k), generator=gen, device='cuda') * 0.25).bfloat16()
        reference = (a.float() @ b.float().T).bfloat16()
        packed = shuffle_weight(b, layout=(16, 16)) if inputs['bpreshuffle'] else b
        out = torch.empty((m, n), device='cuda', dtype=torch.bfloat16)
        def run():
            return gemm_a16w16_asm(a, packed, out, bias=None, splitK=1, kernelName=symbol,
                                  bpreshuffle=inputs['bpreshuffle'])
        extra = {'a': a, 'b': b, 'packed': packed}
    else:
        if 'I8gemm_bf16_perTokenI8_BpreShuffle_' not in symbol or not inputs['bpreshuffle']:
            raise ValueError('INT8 symbol/layout mismatch')
        a = torch.randint(-16, 17, (m, k), generator=gen, device='cuda', dtype=torch.int8)
        # Match the upstream ASM test's 128-byte row padding. The allocation
        # remains owned by this view throughout graph replay and profiling.
        padded = torch.zeros((m, k + 128), device='cuda', dtype=torch.int8)
        padded[:, :k] = a
        a = padded[:, :k]
        b = torch.randint(-16, 17, (n, k), generator=gen, device='cuda', dtype=torch.int8)
        sa = 0.02 + 0.03 * torch.rand((m, 1), generator=gen, device='cuda')
        sb = 0.02 + 0.03 * torch.rand((n, 1), generator=gen, device='cuda')
        # Integer products and sum fit exactly in FP32 at these bounds.
        # This catalog unconditionally loads ptr_bias as FP32; a null optional
        # API bias is not legal for these code objects. Exercise a real bias.
        bias = 0.02 * torch.randn((1, n), generator=gen, device='cuda')
        reference = ((a.float() @ b.float().T) * sa * sb.T + bias).bfloat16()
        packed = shuffle_weight(b, layout=(16, 16))
        out = torch.empty((m, n), device='cuda', dtype=torch.bfloat16)
        def run():
            return gemm_a8w8_asm(a, packed, sa, sb, out, kernelName=symbol, bias=bias, bpreshuffle=True, splitK=1)
        extra = {'a': a, 'b': b, 'packed': packed, 'sa': sa, 'sb': sb, 'bias': bias}
    return {'run':run, 'outputs':[out], 'reference':[reference], 'flops':2*m*n*k, '_inputs':extra}


def validate(inputs, symbol, seed):
    import torch
    import torch.nn.functional as F
    import aiter
    from aiter.test_common import perftest
    family = inputs['family']
    case = prepare(inputs, symbol, seed + 100003)
    extra = case['_inputs']
    calls = []
    if family == 'bf16':
        def selected(a, b, out, bias=None, splitK=None, kernelName=None, bpreshuffle=False):
            calls.append(symbol)
            return aiter.gemm_a16w16_asm(a, b, out, bias=None, splitK=1, kernelName=symbol,
                                       bpreshuffle=inputs['bpreshuffle'])
        selected_api = SimpleNamespace(gemm_a16w16_asm=selected)
    else:
        def selected(a, b, sa, sb, bias=None):
            calls.append(symbol)
            out = torch.empty((a.shape[0], b.shape[0]), device=a.device, dtype=torch.bfloat16)
            return aiter.gemm_a8w8_asm(a, b, sa, sb, out, kernelName=symbol, bias=bias, bpreshuffle=True, splitK=1)
        selected_api = SimpleNamespace(gemm_a8w8_ASM=selected)
    ns = {'torch':torch, 'F':F, 'aiter':selected_api, 'dtypes':aiter.dtypes,
          'perftest':perftest, 'TEST_NUM_ITERS':100}
    exec(benchmark_definitions(family), ns)
    if family == 'bf16':
        reference, ref_us = ns['run_torch'](extra['a'], extra['b'], otype=torch.bfloat16)
        output, asm_us = ns['run_bf16gemm_asm'](extra['a'], extra['packed'], case['outputs'][0],
                                              splitK=1, kernelName=symbol, bpreshuffle=inputs['bpreshuffle'])
    else:
        reference, ref_us = ns['run_torch'](extra['a'], extra['b'], extra['sa'], extra['sb'], bias=extra['bias'], dtype=torch.bfloat16)
        output, asm_us = ns['run_gemm_asm'](extra['a'], extra['packed'], extra['sa'], extra['sb'], bias=extra['bias'], dtype=torch.bfloat16)
    if not calls or any(not math.isfinite(float(t)) or t <= 0 for t in (ref_us, asm_us)):
        raise ValueError('upstream wrapper failed to exercise/timestamp selected symbol')
    checks = []
    for ref in (reference, case['reference'][0]):
        finite = bool(torch.isfinite(output).all().item() and torch.isfinite(ref).all().item())
        passed = finite and torch.allclose(output.float(), ref.float(), atol=0.05, rtol=0.02)
        checks.append({'passed':bool(passed), 'max_abs_error':float((output.float()-ref.float()).abs().max().item()) if finite else None})
        if not passed:
            raise ValueError('upstream wrapper full-output comparison failed: ' + str(checks))
    rel, sha, wrapper = TESTS[family]
    return {'correct':True, 'test':rel, 'test_sha256':sha, 'functions':[wrapper, 'run_torch'],
            'scope':'reviewed single-target upstream benchmark wrappers; not the full test_gemm suite',
            'symbol':symbol, 'splitK':1, 'bpreshuffle':inputs['bpreshuffle'], 'asm_calls':len(calls),
            'bias':'fp32 per-output-channel' if family=='i8' else None, 'a_row_padding':128 if family=='i8' else 0,
            'checks':checks, 'rows':[{'data_init':'signed_random','scale_init':'per_token' if family=='i8' else 'none',
                                   'asm us':float(asm_us),'torch us':float(ref_us),'asm err':0}],
            'timing':'upstream perftest profiler with rotating inputs'}
