"""CLI bridge so an LLM agent can DRIVE the engine over a real kernel.

This exposes the AgentSession decision surface (agent/session.py) as two
sub-commands an external model (or a Cursor agent) calls turn-by-turn:

  observe   dump the read-only facts map (per-slot layout, kinds, legal windows,
            latency edges, recognised prefetch loads, voted direction, knowledge
            prior) as JSON -- this is what the LLM READS. Add ``--compact`` to
            trim a big anchor-less DAG to a per-node summary (iid/kind/pos/window/
            movable/bumps_counter) and spill the full dag to a sidecar .jsonl
            (path echoed as ``dag_full_path``) so it does not flood context.

  eval      take a proposed per-slot layout (JSON {slot: [iid,...]}) and run the
            gated build -> recompute -> Verifier -> real-HW measure path, print
            the verdict (correct / tflops / accepted) as JSON -- the LLM's ACTION.

  propose   non-committing legality check of one/more layouts; prints placed /
            skipped(+SkipReason) so the LLM can iterate before paying for a run.

  suggest   (anchor-less regions) ask the ENGINE for 2-3 legal seed reorders via
            the weighted list scheduler, each with its est_cycles + baseline, so
            the LLM picks/micro-tunes a candidate instead of building a full order
            from scratch. ``--n N`` sets how many presets to try (default 3).
            ``--phase K`` limits it to phase K of a mixed region (``observe``
            lists ``phases``: anchored WMMA stretches vs anchor-less stretches
            such as the softmax between two GEMMs). Each anchor-less phase also
            carries ``migration``: its instructions that may enter slots of
            the neighbouring GEMM phases (``to_prev``/``to_next`` with slots)
            and the GEMM fillers that may move into it (``from_prev``/
            ``from_next``); apply one with an ordinary ``propose``/``eval``
            slot layout, e.g. ``{"12": [1967]}``.

All sub-commands take an optional ``--region SEL`` to choose WHICH code region
to observe/tune: "loop" (default, the core loop = the loop with the most
MFMA/WMMA), "prologue" (pre-loop), "epilogue" (post-loop), "inter" (between two
loops), "body" (a loop-less kernel), "outlined" (code after the program end:
cold tails / specialised copies), an indexed form like "loop#1" for the 2nd
loop in program order, or "loop@<label>" for the loop headed by <label>. ``observe`` always
lists every detected region (index/kind/line span/instr count) under
``"regions"`` and echoes the selected one under ``"region"``.

The project under test is chosen with ``--client SPEC`` (a path below client/,
e.g. "poc_kl/fp8_blockscale_gemm"; see client/README.md). The client decides how
a candidate is built, checked and timed; the engine only sees ``EvalResult``.
Runtime outputs (experiments log, archived candidates, dag sidecars) go to that
client's ``tune_out/``. ``observe --no-direction`` / ``propose`` / ``suggest``
need no client.

Client params (m/n/k for a GEMM exe, qhead/ctx_len/... for other kernels) are
NOT engine flags. Pass them AFTER a ``--`` sentinel and they are forwarded
VERBATIM to the client; the engine never interprets or defaults them.

Usage:
  python3.8 tools/agent_session.py observe <seed.s> --client poc_kl/fp8_blockscale_gemm \
            [--loop 20] [--no-direction] [--kernel NAME] [--region loop] -- m=2560 n=2560 k=256
  python3.8 tools/agent_session.py propose <seed.s> --layout '{"0":[12,13],"2":[14]}' \
            [--region epilogue]
  python3.8 tools/agent_session.py eval    <seed.s> --client poc_kl/fp8_blockscale_gemm \
            [--loop 20] [--region prologue] [--results-path P] -- m=2560 n=2560 k=256

``--results-path P`` (eval only): append the verdict as one row to P (jsonl) and
P's .md sibling. This is the AUTHORITATIVE per-eval record; the SDK driver no
longer scrapes verdicts from the event stream.

``observe``/``propose`` need no GPU (direction is skipped/handled gracefully).
``eval`` needs a client whose machine can run it. iids printed by ``observe`` are stable
(source line numbers) -- feed them straight back into ``--layout``.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client as _clients
from agent.session import AgentSession
from agent import knowledge as kn

def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def _client(argv, needed_for):
    """The ``--client`` of this command (or None when absent and not needed).
    Read curated knowledge from knowledge/engine; all runtime outputs go to the
    client's tune_out (kn.DEFAULT_OUT_STORE when there is no client)."""
    spec = _arg(argv, "--client", None)
    if spec is None:
        if needed_for:
            raise SystemExit("agent_session {}: needs --client SPEC (known: {})".format(
                needed_for, ", ".join(_clients.list_clients()) or "none"))
        return None
    try:
        return _clients.resolve(spec)
    except ValueError as exc:
        raise SystemExit("agent_session: {}".format(exc))


def _out_store(cl):
    return cl.out_dir if cl is not None else kn.DEFAULT_OUT_STORE


def _make_evaluator(cl, loop, kernel, exe_params, seed_src=""):
    return cl.make_evaluator(seed_src=seed_src, params=exe_params, loop=loop,
                             kernel=kernel)


class _NullEval:
    """Stand-in so observe/propose work without a GPU."""
    def evaluate(self, s_path, with_counters=False):
        raise RuntimeError("no GPU evaluator (observe/propose do not need one)")


# Compact NodeView fields kept inline in --compact mode; the heavy fields
# (preds/succs/waits_on) go to a sidecar .jsonl so a big anchor-less DAG
# (hundreds of nodes) does not blow up the agent's context window
# (proj/brainstorm/large_dag_finetune.md direction 8).
_COMPACT_NODE_FIELDS = ("iid", "kind", "pos", "legal_window", "movable",
                        "bumps_counter")


def _compact_observation(d, region, kernel, out_store):
    """Trim the anchor-less ``dag`` to a compact per-node view and spill the FULL
    dag to ``<out_store>/<kernel>_<region>_dag.jsonl`` (one node per line). Adds
    ``dag_full_path`` so the agent can read the full nodes on demand. No-op when
    there is no dag (anchored region)."""
    dag = d.get("dag")
    if not dag:
        return d
    reg = str(region).replace("#", "_").replace("/", "_")
    stem = os.path.splitext(kernel or "kernel")[0]
    os.makedirs(out_store, exist_ok=True)
    full_path = os.path.join(out_store, "%s_%s_dag.jsonl" % (stem, reg))
    with open(full_path, "w") as f:
        for n in dag:
            f.write(json.dumps(n) + "\n")
    d["dag"] = [{k: n.get(k) for k in _COMPACT_NODE_FIELDS} for n in dag]
    d["dag_full_path"] = full_path
    return d


def _append_result(jsonl_path, region, layout_obj, res, shader=None):
    """Authoritative per-eval result row, written by the engine itself (NOT by
    scraping the LLM event stream). Appends one row to ``<path>.jsonl`` and a
    matching markdown row to the sibling ``<path>.md`` (creating its header if
    absent). The round number is the count of existing jsonl rows + 1, so each
    sequential eval gets a stable index regardless of how the agent ran."""
    rnd = 0
    if os.path.exists(jsonl_path):
        with open(jsonl_path) as f:
            rnd = sum(1 for _ in f)
    rnd += 1
    tf, base = res.tflops, res.baseline_tflops
    impr = (tf - base) / base if (tf is not None and base) else None
    row = {"round": rnd, "ts": int(time.time() * 1000), "region": region,
           "layout": layout_obj, "correct": res.correct, "tflops": tf,
           "baseline_tflops": base, "improvement": impr,
           "accepted": res.accepted, "note": res.note,
           "est_cycles": res.est_cycles, "shader": shader}
    row.update({"schema_version": 2, "stage": res.stage,
                "verdict": res.verdict, "evidence": res.evidence,
                "baseline_kind": "normalized"})
    row["artifact_sha256"] = (res.evidence.get("candidate", {})
                              .get("artifact", {}).get("sha256"))
    d = os.path.dirname(jsonl_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    md_path = (jsonl_path[:-6] if jsonl_path.endswith(".jsonl") else jsonl_path) + ".md"
    write_header = not os.path.exists(md_path)
    pct = "?" if impr is None else "{:.2f}%".format(impr * 100)
    with open(md_path, "a") as f:
        if write_header:
            f.write("| round | region | stage | verdict | layout | correct | tflops | normalized baseline | "
                    "improvement | accepted | note |\n"
                    "|---|---|---|---|---|---|---|---|---|---|---|\n")
        f.write("| {} | {} | {} | {} | `{}` | {} | {} | {} | {} | {} | {} |\n".format(
            rnd, region, res.stage, res.verdict, json.dumps(layout_obj), row["correct"],
            tf if tf is not None else "?", base if base is not None else "?",
            pct, row["accepted"], row["note"]))


def main(argv):
    # Everything AFTER a `--` sentinel is forwarded VERBATIM to the client. The
    # engine never parses or defaults its params (m/n/k, qhead/ctx_len, ...).
    # Engine flags are parsed only from before it.
    if "--" in argv:
        sep = argv.index("--")
        exe_params = argv[sep + 1:]
        argv = argv[:sep]
    else:
        exe_params = []

    if len(argv) < 2 or argv[0] not in ("observe", "propose", "eval", "suggest"):
        print(__doc__)
        return 2
    cmd, seed_path = argv[0], argv[1]
    with open(seed_path, encoding="utf-8", newline="") as f:
        seed = f.read()

    loop = int(_arg(argv, "--loop", 20))
    kernel = _arg(argv, "--kernel", None)
    with_direction = cmd == "observe" and "--no-direction" not in argv
    cl = _client(argv, needed_for=cmd if cmd == "eval" or with_direction else None)
    out_store = _out_store(cl)
    region = _arg(argv, "--region", "loop")
    from isa.registry import arch_of_source
    arch = arch_of_source(seed)
    context = {"kernel": _arg(argv, "--ctx-kernel", os.path.basename(seed_path)),
               "arch": arch,
               "loop_kind": "mfma_dense"}
    context["evaluation_contract"] = {
        "client": cl.spec if cl is not None else None,
        "params": list(exe_params), "loop": loop, "kernel": kernel, "arch": arch}

    if cmd == "observe":
        evaluator = _make_evaluator(cl, loop, kernel, exe_params, seed) \
            if with_direction else _NullEval()
        sess = AgentSession(seed, evaluator, context=context, region=region,
                            out_store=out_store)
        obs = sess.observe(with_direction=with_direction)
        d = obs.to_dict()
        if "--compact" in argv:
            d = _compact_observation(d, region, context["kernel"], out_store)
        print(json.dumps(d, indent=2))
        return 0

    if cmd == "suggest":
        sess = AgentSession(seed, _NullEval(), context=context, region=region)
        n = int(_arg(argv, "--n", 3))
        phase = _arg(argv, "--phase", None)
        print(json.dumps(sess.suggest_orders(
            n=n, phase=None if phase is None else int(phase)), indent=2))
        return 0

    # --order '[iid, ...]' is the anchor-less linear-order intent (M9); when
    # present it takes the order path instead of the MFMA-gap --layout path.
    order_arg = _arg(argv, "--order", None)
    order = json.loads(order_arg) if order_arg is not None else None
    layout = json.loads(_arg(argv, "--layout", "{}"))
    layout = {int(s): list(v) for s, v in layout.items()}

    if cmd == "propose":
        sess = AgentSession(seed, _NullEval(), context=context, region=region)
        if order is not None:
            print(json.dumps(sess.propose_orders([order])[0], indent=2))
            return 0
        out = sess.propose([layout])[0]
        print(json.dumps({"legal": out.legal, "placed": out.placed,
                          "skipped": out.skipped}, indent=2))
        return 0

    # eval
    sess = AgentSession(seed, _make_evaluator(cl, loop, kernel, exe_params, seed),
                        context=context, region=region, out_store=out_store)
    res = (sess.commit_and_eval_order(order) if order is not None
           else sess.commit_and_eval(layout))
    print(json.dumps({"correct": res.correct, "tflops": res.tflops,
                      "baseline_tflops": res.baseline_tflops,
                      "accepted": res.accepted, "note": res.note,
                      "est_cycles": res.est_cycles,
                      "baseline_est_cycles": res.baseline_est_cycles,
                      "stage": res.stage, "verdict": res.verdict,
                      "baseline_kind": "normalized", "evidence": res.evidence}, indent=2))
    # Authoritative result logging: write one row per eval right here, so the
    # record never depends on parsing the LLM/tool event stream downstream.
    results_path = _arg(argv, "--results-path", None)
    if results_path:
        layout_obj = {"order": order} if order is not None else layout
        _append_result(results_path, region, layout_obj, res,
                       shader=getattr(sess, "last_archive", None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
