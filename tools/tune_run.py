"""Persistent tuning runs; see proj/steps/geak-P0c-paired-validation.md.

`eval`, `profile`, `confirm` and `final` may construct an evaluator; other commands are CPU-only.
Client arguments are supplied verbatim after `--` at init and frozen thereafter.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import fcntl
import json
from pathlib import Path
import re
import sys
import uuid

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import client as clients
from agent.run import RunController, RunError
from harness.evidence import unavailable_identity
from harness.measurement import file_sha256

# Cooperating run-mode commands in this checkout serialize all client work.
# Legacy commands, other checkouts and unrelated GPU processes do not use it.
EVAL_LOCK = REPO / "study_case/study_out/run-eval.lock"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RunError("arguments", message)


def parser():
    ap = Parser(description=__doc__)
    commands = ap.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="archive input and freeze a run; no client evaluation")
    init.add_argument("seed")
    init.add_argument("--client", required=True)
    init.add_argument("--run-id", default=None)
    init.add_argument("--eval-calls", type=int, default=24)
    init.add_argument("--proposal-limit", type=int, default=64)
    init.add_argument("--perf-repeats", type=int, default=3)
    init.add_argument("--final-reserve", type=int, default=0)
    init.add_argument("--wall-seconds", type=float, default=None)
    init.add_argument("--region", default="loop")
    init.add_argument("--loop", type=int, default=20)
    init.add_argument("--kernel", default=None)
    init.add_argument("--no-protect-prefetch", action="store_true")
    init.add_argument("--search-policy", help="JSON with explicit navigation limits and optional profile allowance")
    init.add_argument("--comparison-policy", help="JSON file with an explicit fixed paired-comparison policy")
    for name in ("status", "observe", "prepare", "eval", "confirm", "final", "select-parent", "resume",
                 "ledger", "annotate", "suggest", "profile", "replay", "combine", "history", "warm-start"):
        sub = commands.add_parser(name)
        sub.add_argument("run")
        if name in ("observe", "suggest"):
            sub.add_argument("--region", default=None)
            if name == "suggest":
                sub.add_argument("--n", type=int, default=6)
        elif name == "prepare":
            sub.add_argument("--observation", required=True)
            sub.add_argument("--base-sha256", required=True)
            sub.add_argument("--spec-file", required=True)
            sub.add_argument("--hypothesis-file")
        elif name == "annotate":
            sub.add_argument("--file", required=True)
        elif name in ("history", "warm-start"):
            sub.add_argument("history_run")
            sub.add_argument("--candidate", default=None)
        elif name in ("eval", "confirm", "select-parent", "profile", "replay", "combine"):
            sub.add_argument("candidate")
            if name == "eval":
                sub.add_argument("--repeat", action="store_true")
    return ap


def client_contract(cl, params, loop, kernel, seed_src=""):
    """Record known client identity, not an unverified GPU/toolchain identity."""
    path = str(Path(cl.module.__file__).resolve())
    identity = (cl.identity(seed_src=seed_src, params=params, loop=loop, kernel=kernel)
                if callable(getattr(cl, "identity", None)) else unavailable_identity())
    contract = {"client": cl.spec, "client_file": path, "client_sha256": file_sha256(path),
                "client_identity": identity, "params": list(params), "loop": loop, "kernel": kernel}
    if callable(getattr(cl, "agent_profile", None)):
        contract["agent_profile"] = cl.agent_profile(seed_src=seed_src, params=params, loop=loop, kernel=kernel)
        if contract["agent_profile"].get("client_profile_status") == "workload_unbound":
            raise ValueError("client requires a bound workload and validation contract before run initialization")
    return contract


@contextmanager
def evaluation_lock():
    EVAL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOCK.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RunError("evaluation_busy", "another run-mode client evaluation is active") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def dispatch(args, params):
    if args.command == "init":
        run_id = args.run_id or uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run_id):
            raise RunError("arguments", "run-id must be 1-96 filename-safe characters, starting with a letter or digit")
        if args.loop < 1:
            raise RunError("arguments", "loop must be positive")
        cl = clients.resolve(args.client)
        source = Path(args.seed).read_bytes().decode("utf-8")
        contract = client_contract(cl, params, args.loop, args.kernel, source)
        comparison = (json.loads(Path(args.comparison_policy).read_text(encoding="utf-8"))
                      if args.comparison_policy else None)
        run = RunController.create(
            Path(cl.out_dir) / "runs" / run_id, source, contract,
            eval_call_limit=args.eval_calls, proposal_limit=args.proposal_limit,
            perf_repeats=args.perf_repeats, final_eval_reserve=args.final_reserve,
            wall_time_limit=args.wall_seconds, region=args.region,
            protect_prefetch=not args.no_protect_prefetch, comparison_policy=comparison,
            search_policy=json.loads(Path(args.search_policy).read_text(encoding="utf-8")) if args.search_policy else None)
        return {"run_dir": str(run.directory), "manifest": run.status()["manifest"]}

    run = RunController(args.run)
    if args.command == "status":
        return run.status()
    if args.command == "observe":
        return run.observe(args.region)
    if args.command == "suggest":
        return run.suggest(args.region, n=args.n)
    if args.command in ("replay", "combine"):
        return run.replay(args.candidate)
    if args.command == "history":
        return run.history(args.history_run, args.candidate)
    if args.command == "warm-start":
        return run.warm_start(args.history_run, args.candidate)
    if args.command == "prepare":
        spec = json.loads(Path(args.spec_file).read_text(encoding="utf-8"))
        hypothesis = json.loads(Path(args.hypothesis_file).read_text(encoding="utf-8")) if args.hypothesis_file else None
        return run.prepare(args.observation, args.base_sha256, spec, hypothesis=hypothesis)
    if args.command == "ledger":
        return run.ledger()
    if args.command == "annotate":
        value = json.loads(Path(args.file).read_text(encoding="utf-8"))
        return run.annotate(value["text"], value["evidence_refs"])
    if args.command == "select-parent":
        return run.select_parent(args.candidate)
    if args.command == "resume":
        return run.resume()

    frozen = run.status()["manifest"]["evaluation_contract"]
    source = run.source("original")
    cl = clients.resolve(frozen["client"])
    actual = client_contract(cl, frozen["params"], frozen["loop"], frozen["kernel"], source)
    if actual != frozen:
        raise RunError("contract_mismatch", "client implementation or evaluation contract changed; start a new run")

    # Construct lazily: cached/rejected requests must not initialize the client
    # or spend GPU work. Construction failures belong to the charged attempt.
    class LazyEvaluator:
        evaluator = None

        def validate_contract(self):
            if client_contract(cl, frozen["params"], frozen["loop"], frozen["kernel"], source) != frozen:
                raise RunError("contract_mismatch", "declared client resources changed during this run")

        def evaluate(self, path, with_counters=False):
            # Paired stages also use a fresh client object on every side/call.
            # The client still has to rebuild/load the requested candidate;
            # a fresh object cannot prove absence of external build caches.
            if self.evaluator is None or args.command in ("confirm", "final"):
                self.evaluator = cl.make_evaluator(
                    seed_src=source, params=frozen["params"],
                    loop=frozen["loop"], kernel=frozen["kernel"])
            return self.evaluator.evaluate(path, with_counters=with_counters)

    with evaluation_lock():
        if args.command == "profile":
            return run.profile(args.candidate, LazyEvaluator(), evaluation_contract=actual)
        if args.command == "confirm":
            return run.confirm(args.candidate, LazyEvaluator(), evaluation_contract=actual)
        if args.command == "final":
            return run.finalize(LazyEvaluator(), evaluation_contract=actual)
        return run.evaluate(args.candidate, LazyEvaluator(), repeat=args.repeat,
                            evaluation_contract=actual)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    params = []
    try:
        if "--" in argv:
            split = argv.index("--")
            argv, params = argv[:split], argv[split + 1:]
            if argv[:1] != ["init"]:
                raise RunError("arguments", "client params are frozen at init; only init accepts --")
        args = parser().parse_args(argv)
        # Keep stdout one machine-readable JSON object even if a client prints.
        with redirect_stdout(sys.stderr):
            result = dispatch(args, params)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (RunError, OSError, ValueError, KeyError, TypeError) as exc:
        code = exc.code if isinstance(exc, RunError) else "invalid_request"
        print(json.dumps({"error": {"code": code, "message": str(exc)}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
