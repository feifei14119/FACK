#!/usr/bin/env python3
"""Compare two fixed assemblies through the aiter client; no tuning or candidate selection.

Example (from the repository root):
  python3 client/aiter/compare.py base.s candidate.s --client aiter/hsa/gfx942 \
    --pairs 6 --min-gain 0.01 --alpha 0.05 -- \
    --manifest client/aiter/hsa/gfx942/optest_manifest.json --python /path/to/python
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import client as clients
from harness.comparison import assess_pairs, pair_order, validate_policy
from tools.tune_run import client_contract, evaluation_lock
from harness.validation import evidence as validation_evidence


def metrics(result, validation=None):
    if validation:
        values, _ = validation_evidence(asdict(result), validation)
        return values
    if result.compiled is not True or result.correct is not True:
        raise ValueError("candidate did not compile and pass correctness: " + str(result.detail.get("error")))
    runner = result.detail.get("runner", {})
    if runner.get("loader_observed") is not True:
        raise ValueError("candidate loader path was not verified")
    times = {"hip_graph": result.time_us}
    if "op_test" in runner:
        test = runner["op_test"]
        if test.get("correct") is not True or not test.get("rows"):
            raise ValueError("op_test validation did not pass")
        for row in test["rows"]:
            key = "op_test:{}/{}".format(row["data_init"], row["scale_init"])
            if key in times or row.get("asm err") != 0:
                raise ValueError("duplicate/incorrect op_test distribution")
            times[key] = row["asm us"]
    if any(type(t) not in (int, float) or not math.isfinite(t) or t <= 0 for t in times.values()):
        raise ValueError("invalid GPU timing")
    return times


def summarize(records, policy):
    paired = []
    for trial in range(policy["final_pairs"]):
        sides = {r["side"]: r for r in records if r["trial"] == trial}
        if len(sides) != 2:
            raise ValueError("incomplete pair")
        paired.append(sides)
    names = set(paired[0]["reference"]["times_us"])
    if any(set(pair[side]["times_us"]) != names for pair in paired for side in pair):
        raise ValueError("timing methods/distributions changed across paired evaluations")
    results = {}
    for name in sorted(names):
        scores = [{side: 1 / pair[side]["times_us"][name] for side in pair} for pair in paired]
        results[name] = assess_pairs(scores, policy, "final")
        for side in ("reference", "candidate"):
            times = [pair[side]["times_us"][name] for pair in paired]
            results[name][side + "_median_us"] = statistics.median(times)
            results[name][side + "_range_us"] = [min(times), max(times)]
    return results


def compare(args, params):
    policy = validate_policy({"method": "paired_sign_v1", "confirm_pairs": args.pairs,
                              "final_pairs": args.pairs, "min_gain": args.min_gain,
                              "alpha": args.alpha, "max_confirmations": 1})
    cl = clients.resolve(args.client)
    sources = {"reference": Path(args.baseline).read_bytes(), "candidate": Path(args.candidate).read_bytes()}
    seed = sources["reference"].decode("utf-8")
    contract = client_contract(cl, params, args.loop, None, seed)
    if contract["client_identity"].get("status") != "available":
        raise ValueError("client dependencies are incomplete; prepare the environment first")
    parent = Path(cl.out_dir) / "comparisons"
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="paired-", dir=parent))
    snapshots = {}
    for side, data in sources.items():
        snapshots[side] = work / (side + ".s")
        snapshots[side].write_bytes(data)
    report = {"schema_version": 1, "status": "running", "client": cl.spec, "params": params,
              "policy": policy, "contract": contract, "records": [],
              "assemblies": {side: {"path": str(snapshots[side]), "sha256": hashlib.sha256(data).hexdigest()}
                             for side, data in sources.items()},
              "scope": "fixed candidates; separate timing methods; host loader evidence, not GPU dispatch attestation"}
    path = work / "comparison.json"
    def save():
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temp.replace(path)
    save()
    print("report: " + str(path), flush=True)
    device = None
    try:
        with evaluation_lock():
            for trial in range(args.pairs):
                for side in pair_order(trial):
                    if client_contract(cl, params, args.loop, None, seed) != contract:
                        raise ValueError("client resources/environment changed between paired evaluations")
                    evaluator = cl.make_evaluator(seed_src=seed, params=params, loop=args.loop)
                    result = evaluator.evaluate(str(snapshots[side]))
                    record = {"trial": trial, "side": side, "result": asdict(result)}
                    report["records"].append(record)
                    save()  # preserve failed numerical results too
                    record["times_us"] = metrics(result, contract.get("agent_profile", {}).get("validation"))
                    observed = {k: result.detail["runner"].get(k) for k in
                                ("device", "arch", "torch_version", "hip_version")}
                    if device is not None and observed != device:
                        raise ValueError("device or runtime changed during comparison")
                    device = observed
                    if client_contract(cl, params, args.loop, None, seed) != contract:
                        raise ValueError("client resources/environment changed during evaluation")
                    save()
                    print(json.dumps({"trial": trial, "side": side, "times_us": record["times_us"]}), flush=True)
        report.update(status="completed", results=summarize(report["records"], policy), device=device)
    except BaseException as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        save()
    # No automatic adoption: different timing methods can disagree.
    print(json.dumps({"report": str(path), "results": report["results"]}, indent=2))
    return path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    params = []
    if "--" in argv:
        split = argv.index("--")
        argv, params = argv[:split], argv[split + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline")
    ap.add_argument("candidate")
    ap.add_argument("--client", required=True, choices=["aiter/hsa/gfx942"])
    ap.add_argument("--pairs", type=int, required=True, help="even, fixed independent pair count")
    ap.add_argument("--min-gain", type=float, required=True)
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--loop", type=int, default=100)
    args = ap.parse_args(argv)
    try:
        if args.loop < 1:
            raise ValueError("loop must be positive")
        compare(args, params)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
