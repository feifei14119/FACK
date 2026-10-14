"""Build candidate .s files from the real shader for HW validation.

The testcase shader is ALREADY optimized, so it is itself the seed and the
performance baseline: the optimization ladder runs directly on it, no
even-distribution. Two separate things (see reorder/optlevel.py):

  * the OPTIMIZATION LADDER (``level <N>``): recompute waitcnt at OptLevel N
    (L0 drain-all barrier .. L1 band look-ahead) on the current (already-
    optimized) kernel. Does NOT reorder.
  * EVEN-DISTRIBUTION (``even_distribute``): bootstrap a *completely unoptimized*
    kernel (ops clustered by type) into a usable seed by spreading the memory
    ops into the MFMA stream, then recompute. NOT an optimization level, and NOT
    appropriate for an already-optimized kernel like this shader (kept here only
    to exercise the path / for cold kernels).

Per-instruction reorder (``level 2``+, ``level 4`` also moves VALU/SALU) is
tunable for HW experimentation:
  --reorder-kind vmem_load|ds_read|valu|salu   (default: L2/L3 vmem_load;
                                                L4 = vmem_load+valu+salu)
  --reorder-dir  hoist|sink                     (default hoist)

Usage:
  python3.8 tools/make_candidate.py level <N> <out.s> [--reorder-kind K --reorder-dir D]
  python3.8 tools/make_candidate.py cfg               <out.s> [--opt N]  # whole-kernel multi-region recompute
  python3.8 tools/make_candidate.py recompute_only    <out.s> [--opt N]
  python3.8 tools/make_candidate.py even_distribute    <out.s> [--opt N]  # cold-kernel bootstrap
  python3.8 tools/make_candidate.py reorder_recompute  <out.s> [--opt N]  # alias of even_distribute
  python3.8 tools/make_candidate.py reorder_only       <out.s>            # even-distribute, keep hand waits
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parser, regions, emitter, waitcnt, optlevel
from reorder.editor import RegionEditor
from reorder.passes import PassPipeline
from reorder.verifier import Verifier
from reorder.model import Kind
from isa.gfx942.target import Gfx942Target

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADER = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")

EVEN_DIST_MODES = ("even_distribute", "reorder_recompute", "reorder_only")


def load():
    with open(SHADER) as f:
        src = f.read()
    prog = parser.parse(src)
    return src, prog, Gfx942Target.from_program(prog)


def _parse_opt(argv, default=None):
    if "--opt" in argv:
        return int(argv[argv.index("--opt") + 1])
    return default


def _arg(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main():
    mode = sys.argv[1]

    pol = None
    if mode == "level":
        pol = optlevel.policy(int(sys.argv[2]))
        opt_level = pol.level
        out = sys.argv[3]
    else:
        out = sys.argv[2]
        opt_level = _parse_opt(sys.argv, default=None)

    do_even_dist = mode in EVEN_DIST_MODES
    treat_fence = mode == "reorder_only"     # distribute but keep hand waits as fences
    do_recompute = mode in ("level", "recompute_only", "even_distribute", "reorder_recompute")
    do_nop = mode in ("even_distribute", "reorder_recompute") or (pol and pol.reorder)
    # L2: per-instruction reorder on the seed; L4 also moves VALU/SALU.
    do_reorder = bool(pol and pol.reorder)
    reorder_alu = bool(pol and pol.reorder_alu)
    KMAP = {"vmem_load": Kind.VMEM_LOAD, "ds_read": Kind.DS_READ,
            "valu": Kind.VALU, "salu": Kind.SALU}
    rdir_earliest = _arg(sys.argv, "--reorder-dir", "hoist") == "hoist"
    if "--reorder-kind" in sys.argv:
        kinds = [KMAP[_arg(sys.argv, "--reorder-kind", "vmem_load")]]
    elif reorder_alu:
        kinds = [Kind.VMEM_LOAD, Kind.VALU, Kind.SALU]   # L4 default set
    else:
        kinds = [Kind.VMEM_LOAD]                          # L2/L3 default

    src, prog, t = load()
    ref = parser.parse(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]

    # SCHEDULED/AGGRESSIVE: slide ops to their legal-window extreme on the seed.
    # Legal windows already encode RAW/WAR/WAW (incl. a v/s dest feeding a later
    # load's address), so v/s moves can never cross their consumers.
    if do_reorder:
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
        for kind in kinds:
            d = ed.compact_kind(kind, earliest=rdir_earliest)
            sys.stderr.write("reorder {}\n".format(d.note))
        ed.materialize()

    # EVEN-DISTRIBUTION: only to bootstrap a completely-unoptimized (clustered)
    # kernel into a seed. NOT an optimization level; on this already-optimized
    # shader it just scrambles the schedule (kept to exercise the path).
    if do_even_dist:
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=treat_fence)
        n_gaps = len(ed.anchors(Kind.MFMA))
        diff = ed.distribute_evenly(Kind.DS_READ, 0, max(0, n_gaps - 1))
        ed.materialize()
        sys.stderr.write("even_distribute(ds_read): skipped={}\n".format(
            len(getattr(diff, "skipped", []) or [])))

    # OPTIMIZATION LADDER: recompute waitcnt at the chosen OptLevel.
    if mode == "cfg":
        # whole-kernel multi-region recompute (prologue+loop+epilogue) with the
        # cross-region boundary counter contract (reorder.waitcnt.recompute_cfg).
        waitcnt.recompute_cfg(prog, t, opt_level=opt_level)
        from isa.gfx942.passes import ForcedNopPass
        ForcedNopPass().run(prog, t)
    elif do_recompute and not treat_fence:
        waitcnt.recompute(prog, t, region=loop, opt_level=opt_level)  # loop-aware auto
        if do_nop:
            from isa.gfx942.passes import ForcedNopPass
            ForcedNopPass().run(prog, t)
    sys.stderr.write("opt_level={}\n".format(
        "fence(keep hand waits)" if treat_fence
        else (opt_level if opt_level is not None else "default({})".format(int(optlevel.DEFAULT)))))

    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    sys.stderr.write("verify ok={} violations={}\n".format(res.ok, res.violations[:3]))

    text = emitter.emit(prog)
    with open(out, "w") as f:
        f.write(text)
    sys.stderr.write("wrote {} ({} bytes)\n".format(out, len(text)))


if __name__ == "__main__":
    main()
