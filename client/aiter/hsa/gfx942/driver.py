"""One explicitly selected FP8 blockscale GEMM, B preshuffled, splitK=1."""


def prepare(inputs, symbol, seed):
    import torch
    from aiter import dtypes
    from aiter.ops.shuffle import shuffle_weight
    from aiter.ops.gemm_op_a8w8 import gemm_a8w8_blockscale_bpreshuffle_asm

    m, n, k = (inputs[x] for x in ("m", "n", "k"))
    if any(type(v) is not int or v <= 0 for v in (m, n, k)) or n % 128 or k % 128:
        raise ValueError("gfx942 blockscale requires positive M, N%128=K%128=0")
    gen = torch.Generator(device="cuda").manual_seed(seed)
    a = torch.randn((m, k), generator=gen, device="cuda").to(dtypes.fp8)
    b = torch.randn((n, k), generator=gen, device="cuda").to(dtypes.fp8)
    sa = 0.5 + torch.rand((m, k // 128), generator=gen, device="cuda")
    sb = 0.5 + torch.rand((n // 128, k // 128), generator=gen, device="cuda")
    # Reference uses the original, unshuffled tensors and ordinary FP32 GEMM.
    reference = ((a.float() * sa.repeat_interleave(128, dim=1)) @
                 (b.float() * sb.repeat_interleave(128, dim=0).repeat_interleave(128, dim=1)).T).bfloat16()
    packed_b = shuffle_weight(b, layout=(16, 16))
    packed_sa = sa.T.contiguous().view_as(sa)
    out = torch.empty((m, n), dtype=torch.bfloat16, device="cuda")
    zero_bias = torch.zeros((1, n), dtype=torch.float32, device="cuda")

    def run():
        gemm_a8w8_blockscale_bpreshuffle_asm(
            a, packed_b, out, packed_sa, sb, splitK=1, kernelName=symbol,
            bpreshuffle=True, zero_bias_buf=zero_bias)

    return {"run": run, "outputs": [out], "reference": [reference], "flops": 2 * m * n * k}
