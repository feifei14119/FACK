"""Optional REAL-HARDWARE validation step for gold-mined layout skills (Layer 3).

Skill SUMMARISATION (tools/mine_corpus.py) is always static + GPU-free, so you
can mine candidate skills for many architectures on ONE box. This tool is the
SEPARATE, opt-in step that takes those candidate constraints, derives candidate
gap layouts for a runnable target kernel, and validates them on REAL hardware
(commit_and_eval -> measured TFLOPS, gated + logged), optionally promoting
corroborated skills to ``trusted`` via induce_skills.

It is gated by a SWITCH so it only runs where it makes sense (the matching GPU
+ a runnable client). ``--no-validate`` makes it a dry, CPU-only plan (derive
+ propose-legality) so the same command is safe to run anywhere.

  python3.8 tools/validate_skills.py --seed K.s --client poc_kl/fp8_blockscale_gemm \
      [--store knowledge/engine] [--region loop] [--loop-kind mfma_dense] [--arch gfx942] \
      [--max-candidates 4] [--promote] [--no-validate] [--out DIR] -- m=256 n=256 k=512

``--out`` defaults to the client's tune_out. The core ``validate_skill_layouts``
is evaluator-INJECTABLE, so it is unit-tested without a GPU; only the CLI asks
the client for a real evaluator (lazily).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn
from agent.session import AgentSession


def validate_skill_layouts(seed_src: str, evaluator, *,
                           store: str = kn.DEFAULT_STORE,
                           out_store: Optional[str] = None,
                           context: Optional[Dict] = None,
                           region: str = "loop", max_candidates: int = 4,
                           validate: bool = True, promote: bool = False) -> Dict:
    """Drive AgentSession.learn_layouts for one seed kernel.

    ``validate=False`` => CPU-only plan (no evaluator call); ``validate=True`` =>
    commit_and_eval each legal candidate on the injected evaluator. Returns the
    learn_layouts summary dict."""
    sess = AgentSession(seed_src, evaluator, store=store, out_store=out_store,
                        context=context or {}, region=region)
    return sess.learn_layouts(validate=validate, max_candidates=max_candidates,
                              promote=promote)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _arg(argv: List[str], flag: str, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


class _NullEval:
    """Stand-in so the dry (--no-validate) path needs no GPU."""
    def evaluate(self, s_path, with_counters=False):
        raise RuntimeError("no GPU evaluator (use real --validate on a GPU box)")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # everything after `--` is forwarded VERBATIM to the program under test
    exe_params: List[str] = []
    if "--" in argv:
        sep = argv.index("--")
        exe_params = argv[sep + 1:]
        argv = argv[:sep]

    seed_path = _arg(argv, "--seed")
    if not seed_path:
        sys.stderr.write("usage: validate_skills.py --seed K.s "
                         "[--client SPEC] [--no-validate] ...\n")
        return 2
    do_validate = "--no-validate" not in argv
    store = _arg(argv, "--store", kn.DEFAULT_STORE)
    cl = None
    if _arg(argv, "--client"):
        import client as _clients
        try:
            cl = _clients.resolve(_arg(argv, "--client"))
        except ValueError as exc:
            sys.stderr.write("[validate] {}\n".format(exc))
            return 2
    out_store = _arg(argv, "--out", cl.out_dir if cl else kn.DEFAULT_OUT_STORE)
    region = _arg(argv, "--region", "loop")
    max_candidates = int(_arg(argv, "--max-candidates", "4"))
    promote = "--promote" in argv
    context: Dict = {}
    if _arg(argv, "--arch"):
        context["arch"] = _arg(argv, "--arch")
    if _arg(argv, "--loop-kind"):
        context["loop_kind"] = _arg(argv, "--loop-kind")

    with open(seed_path) as fh:
        seed_src = fh.read()

    if do_validate:
        if cl is None:
            sys.stderr.write("[validate] --validate needs --client SPEC "
                             "(a client runnable on this GPU, see client/README.md)\n")
            return 2
        evaluator = cl.make_evaluator(seed_src=seed_src, params=exe_params,
                                      loop=int(_arg(argv, "--loop", "20")),
                                      kernel=_arg(argv, "--kernel"))
    else:
        evaluator = _NullEval()

    summary = validate_skill_layouts(
        seed_src, evaluator, store=store, out_store=out_store, context=context,
        region=region, max_candidates=max_candidates, validate=do_validate,
        promote=promote)

    print("[validate] mode=%s candidates=%d legal=%d" % (
        "HW" if do_validate else "dry(CPU)", summary["n_candidates"],
        summary["n_legal"]))
    if do_validate:
        best = summary.get("best")
        print("[validate] accepted_best=%s" % (
            json.dumps(best) if best else "none"))
        if promote:
            print("[validate] promoted=%s" % summary.get("promoted", []))
    return 0



if __name__ == "__main__":
    sys.exit(main())
