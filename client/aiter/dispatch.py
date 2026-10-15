#!/usr/bin/env python3
"""CPU-only dispatch CSV indexing and exact-workload manifest export.

Never import aiter here: its config merger may rewrite its input files. Export
an explicit, architecture/CU-scoped config override and verify normal dispatch
on the target before accepting measurements. No heuristic/padded-M expansion.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from client.aiter.common import HERE, UPSTREAM, inside

FAMILIES = {
    "bf16": ("bf16_tuned_gemm", "AITER_CONFIG_GEMM_BF16",
             "M N K bias dtype outdtype scaleAB bpreshuffle"),
    "a8w8": ("a8w8_bpreshuffle_tuned_gemm", "AITER_CONFIG_GEMM_A8W8_BPRESHUFFLE",
             "M N K q_dtype_w"),
    "blockscale": ("a8w8_blockscale_tuned_gemm", "AITER_CONFIG_GEMM_A8W8_BLOCKSCALE", "M N K"),
    "blockscale_preshuffle": ("a8w8_blockscale_bpreshuffle_tuned_gemm",
                             "AITER_CONFIG_GEMM_A8W8_BLOCKSCALE_BPRESHUFFLE", "M N K"),
    "moe": ("tuned_fmoe", "AITER_CONFIG_FMOE",
            "token model_dim inter_dim expert topk act_type dtype q_dtype_a q_dtype_w q_type use_g1u1 doweight_stage1"),
}
ENTRYPOINTS = {"bf16": "aiter.tuned_gemm.gemm_a16w16", "a8w8": "aiter.gemm_a8w8_ASM",
              "blockscale_preshuffle": "aiter.ops.gemm_op_a8w8.gemm_a8w8_blockscale_bpreshuffle"}
RESOLVER_FILES = ["aiter/jit/core.py", "aiter/jit/utils/chip_info.py",
                  "aiter/tuned_gemm.py", "aiter/ops/gemm_op_a8w8.py"]
BLOCKSCALE_ADAPTER_FILES = ["dispatch.py", "hsa/gfx942/dispatch_driver.py",
                          "hsa/gfx942/gemm_driver.py", "hsa/gfx942/driver.py",
                          "hsa/gfx942/optest_driver.py"]
BLOCKSCALE_UPSTREAM_FILES = [
    "op_tests/test_gemm_a8w8_blockscale.py", "aiter/test_common.py",
    "aiter/benchmark_data_init.py", "aiter/benchmark_reporting.py",
    "aiter/utility/dtypes.py", "aiter/utility/fp4_utils.py", "aiter/ops/shuffle.py",
    "aiter/ops/triton/gemm/basic/gemm_a8w8_blockscale.py",
    "csrc/py_itfs_cu/asm_a8w8_blockscale_bpreshuffle.cu",
    "csrc/ck_gemm_a8w8_blockscale_bpreshuffle/gemm_a8w8_blockscale_bpreshuffle.cu",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_csv(path):
    # Catalogs may start with comments. Keep physical line numbers for review.
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines(keepends=True)
    kept = [(i, line) for i, line in enumerate(lines, 1) if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(line for _, line in kept)
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("malformed CSV: {}".format(path))
        rows.append((kept[reader.line_num - 1][0], {k.strip(): v.strip() for k, v in row.items()}))
    return [k.strip() for k in (reader.fieldnames or [])], rows


def int_value(value):
    number = float(value)
    if not math.isfinite(number) or number != int(number):
        raise ValueError("expected integer: {}".format(value))
    return int(number)


def boolean(value):
    if str(value).lower() in ("true", "1", "1.0"):
        return True
    if str(value).lower() in ("false", "0", "0.0"):
        return False
    raise ValueError("expected boolean: {}".format(value))


def canonical_key(row, keys):
    numeric = set("cu_num M N K token model_dim inter_dim expert topk use_g1u1 doweight_stage1".split())
    booleans = {"bias", "scaleAB", "bpreshuffle"}
    return tuple(int_value(row[k]) if k in numeric else boolean(row[k]) if k in booleans else row[k]
                 for k in keys)


def discover(upstream, family, overrides, environ):
    stem, env, _ = FAMILIES[family]
    explicit = (overrides.get(family) or environ.get(env) or "").strip()
    if explicit:
        paths = [Path(p).resolve() for p in explicit.split(os.pathsep)]
        mode = "explicit_override" if family in overrides else "environment_override"
    else:
        base = upstream / "aiter/configs"
        paths = [base / (stem + ".csv")] + sorted(
            p for p in (base / "model_configs").glob("*" + stem + "*.csv") if "untuned" not in p.name)
        mode = "default_and_model_configs"
    if not paths or any(not p.is_file() for p in paths):
        raise ValueError("missing config source for {}: {}".format(family, paths))
    return paths, mode


def catalog_index(upstream, arch):
    base = upstream / "hsa" / arch
    index = defaultdict(list)
    sources = {}
    for path in sorted(base.rglob("*.csv")):
        fields, rows = read_csv(path)
        if not {"knl_name", "co_name"} <= set(fields):
            continue
        sources[str(path.relative_to(upstream))] = sha(path)
        for line, row in rows:
            co = inside(base, str(path.parent.relative_to(base) / row["co_name"]))
            if co.suffix != ".co":
                raise ValueError("invalid catalog .co path")
            index[row["knl_name"]].append({"co": str(co.relative_to(base)),
                "catalog": str(path.relative_to(base)), "line": line,
                "attributes": row, "exists": co.is_file()})
    return dict(index), sources


def adapter_inputs(family, row, match):
    """Accept only contracts implemented by the reviewed drivers, without repairs."""
    if family not in ENTRYPOINTS:
        raise ValueError("no reviewed dispatch/op_test adapter for this family")
    if int_value(row.get("splitK", "-1")) != 1:
        raise ValueError("adapter supports splitK=1 only; preserve CSV splitK")
    for field in ("errRatio", "err_ratio"):
        if row.get(field) and float(row[field]) != 0:
            raise ValueError("CSV reports nonzero/nonfinite error; original needs investigation")
    shape = {k.lower(): int_value(row[k]) for k in ("M", "N", "K")}
    if min(shape.values()) <= 0 or shape["k"] % 128:
        raise ValueError("adapter requires positive MNK and K divisible by 128")
    attrs = match["attributes"]
    if family == "blockscale_preshuffle":
        tile_m = int_value(attrs.get("tile_m", "-1"))
        expected = "_ZN5aiter{}fp8gemm_bf16_blockscale_BpreShuffle_{}x128E".format(
            43 if tile_m == 128 else 42, tile_m)
        if (tile_m not in (32, 48, 64, 80, 96, 128) or
                int_value(attrs.get("tile_n", "-1")) != 128 or
                row["kernelName"] != expected or int_value(attrs.get("splitK", "-1")) != 1 or
                not boolean(attrs.get("bpreshuffle", "0"))):
            raise ValueError("blockscale adapter requires a reviewed preshuffled x128 splitK=1 catalog symbol")
        if shape["n"] % 128:
            raise ValueError("blockscale adapter requires N divisible by 128")
        return dict(shape, family="blockscale", bpreshuffle=True, splitK=1,
                    dtype="torch.float8_e4m3fnuz", outdtype="torch.bfloat16", bias=None,
                    quantization="blockscale", scale_dtype="torch.float32",
                    a_scale_block=[1, 128], b_scale_block=[128, 128],
                    a_scale_shape=[shape["m"], shape["k"] // 128],
                    b_scale_shape=[shape["n"] // 128, shape["k"] // 128],
                    a_scale_layout="transpose_contiguous_view", b_scale_layout="row_major",
                    weight_layout=[16, 16], a_row_padding=0)
    if family == "a8w8":
        if row["q_dtype_w"] != "torch.int8" or not row["kernelName"].startswith("_ZN5aiter") or "I8gemm_bf16_perTokenI8_BpreShuffle_" not in row["kernelName"]:
            raise ValueError("adapter is per-token INT8 ASM; FP8 uses another entrypoint")
        if shape["n"] % 256 or not boolean(attrs.get("bpreshuffle", "0")):
            raise ValueError("INT8 adapter requires N divisible by 256 and preshuffled weights")
        return dict(shape, family="i8", bpreshuffle=True, splitK=1,
                    dtype="torch.int8", outdtype="torch.bfloat16", quantization="per_token",
                    scale_dtype="torch.float32", bias="fp32_per_output_channel",
                    weight_layout=[16, 16], a_row_padding=128)
    if row["dtype"] != "torch.bfloat16" or row["outdtype"] != "torch.bfloat16" or boolean(row["bias"]) or boolean(row["scaleAB"]):
        raise ValueError("BF16 adapter requires BF16 output, no bias and no scaleAB")
    if shape["n"] % 64 or "bf16gemm_fp32bf16_" not in row["kernelName"] or not boolean(attrs.get("tn", "0")):
        raise ValueError("BF16 adapter requires TN and N divisible by 64")
    shuffled = boolean(row["bpreshuffle"])
    if boolean(attrs.get("bPreshuffle", "0")) != shuffled:
        raise ValueError("CSV and catalog weight layouts disagree")
    return dict(shape, family="bf16", bpreshuffle=shuffled, splitK=1,
                dtype="torch.bfloat16", outdtype="torch.bfloat16", bias=None, scaleAB=False,
                weight_layout=[16, 16] if shuffled else None, a_row_padding=0)


def build_plan(upstream, arch, cu, families, overrides=None, environ=None):
    upstream = Path(upstream).resolve()
    if arch != "gfx942" or cu <= 0:
        raise ValueError("this planner requires gfx942 and a positive measured CU count")
    index, catalog_sources = catalog_index(upstream, arch)
    plan = {"schema_version": 1, "arch": arch, "cu_num": cu,
            "scope": "exact CSV workloads; scoped config overrides; runtime dispatch pending; not global optima",
            "families": {}, "references": [], "co_to_workloads": {}, "tasks": [],
            "catalog_sources": catalog_sources}
    snapshots = {}
    originals = {}
    for family in families:
        paths, mode = discover(upstream, family, overrides or {}, os.environ if environ is None else environ)
        sources, raw, columns = [], [], []
        for path in paths:
            digest = sha(path)
            originals[path] = digest
            source = {"path": str(path.relative_to(upstream)) if upstream in path.parents else str(path), "sha256": digest}
            sources.append(source)
            fields, rows = read_csv(path)
            columns.extend(k for k in fields if k not in columns)
            raw.extend({"source": source, "line": line, "row": row} for line, row in rows)
        # Legacy gfx backfill is pinned to chip_info.py's known CU mapping.
        if "gfx" not in columns:
            columns.insert(0, "gfx")
        selected, excluded = [], Counter()
        for item in raw:
            row = dict(item["row"])
            try:
                row_cu = int_value(row["cu_num"])
            except (KeyError, ValueError):
                excluded["invalid_cu"] += 1
                continue
            row_gfx = row.get("gfx") if "gfx" in row else {80: "gfx942", 304: "gfx942", 256: "gfx950"}.get(row_cu)
            if not row_gfx:
                excluded["unknown_legacy_gfx"] += 1
                continue
            if row_cu != cu or row_gfx != arch:
                excluded["other_arch_or_cu"] += 1
                continue
            row = {k: row.get(k, "0") for k in columns}
            row["gfx"], row["cu_num"] = row_gfx, str(row_cu)
            # _tag participates in MoE fallback; retain its original value.
            selected.append(dict(item, effective_row=row))
        keys = ["gfx", "cu_num"] + FAMILIES[family][2].split()
        groups, malformed = defaultdict(list), []
        for item in selected:
            try:
                if any(k not in item["row"] for k in keys if k != "gfx"):
                    raise ValueError("missing dispatch key")
                key = canonical_key(item["effective_row"], keys)
                if family == "moe":
                    key += (item["effective_row"].get("_tag", ""),)
                groups[key].append(item)
            except (ValueError, KeyError):
                malformed.append(item)
        # Even byte-identical duplicates are rejected upstream. Never pick a
        # fastest row silently or mutate the user's original files.
        conflicts = [items for items in groups.values() if len(items) > 1]
        family_blocked = bool(conflicts or malformed)
        meta = {"source_mode": mode, "sources": sources, "rows": len(selected),
                "excluded": dict(excluded), "conflicting_keys": len(conflicts),
                "malformed_keys": len(malformed), "config_status": "blocked" if family_blocked else "ready"}
        plan["families"][family] = meta
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(item["effective_row"] for item in selected)
        snapshots[family] = buf.getvalue()
        snapshot_sha = hashlib.sha256(buf.getvalue().encode()).hexdigest()
        for item in selected:
            row = item["effective_row"]
            for field in (["kernelName1", "kernelName2"] if family == "moe" else ["kernelName"]):
                symbol = row.get(field, "")
                backend = row.get("libtype", "")
                # A stale kernelName on a CK/FlyDSL/etc row is not an HSA
                # dispatch reference even if the symbol exists in a catalog.
                matches = index.get(symbol, []) if not backend or backend.lower() == "asm" else []
                ref = {"family": family, "source": item["source"], "line": item["line"],
                       "row": item["row"], "effective_row": row, "stage": field,
                       "symbol": symbol, "backend": backend or ("hsa_reference" if matches else "unresolved"),
                       "matches": matches, "runtime_status": "not_checked"}
                if backend and backend.lower() != "asm":
                    ref.update(status="other_backend", reason="CSV selects " + backend)
                elif not matches:
                    ref.update(status="unmapped", reason="no gfx942 catalog match; may use CK/Triton/FlyDSL or heuristics")
                elif len(matches) != 1:
                    ref.update(status="ambiguous_catalog", reason="symbol is not unique across catalogs")
                elif not matches[0]["exists"]:
                    ref.update(status="missing_co", reason="catalog .co is absent")
                elif family_blocked:
                    ref.update(status="config_conflict", reason="selected family has duplicate or incomplete dispatch keys")
                else:
                    try:
                        inputs = adapter_inputs(family, row, matches[0])
                        ref.update(status="ready_for_validation", inputs=inputs,
                                   entrypoint=ENTRYPOINTS[family], reason="exact workload; target validation required")
                    except (ValueError, KeyError) as exc:
                        ref.update(status="unsupported_adapter", reason=str(exc))
                ref["workload_id"] = object_id({"family": family, "row": row, "stage": field,
                    "sources": sources, "snapshot": snapshot_sha, "inputs": ref.get("inputs"),
                    "entrypoint": ref.get("entrypoint")})[:24]
                plan["references"].append(ref)
    # Inverse index retains every association, including unsupported cases.
    inverse = defaultdict(list)
    for ref in plan["references"]:
        for match in ref["matches"]:
            inverse[match["co"]].append(ref["workload_id"])
    plan["co_to_workloads"] = dict(sorted(inverse.items()))
    inventory = defaultdict(list)
    for matches in index.values():
        for match in matches:
            inventory[match["co"]].append(match)
    plan["unreferenced_co"] = [{"co": co, "catalog_entries": matches,
        "reason": "needs explicit batch/KV/routing workload and runtime heuristic validation" if co.startswith("mla/")
                  else "no reference in selected config families/arch/CU; does not prove unused"}
        for co, matches in sorted(inventory.items()) if co not in inverse]
    plan["counts"] = dict(Counter(r["status"] for r in plan["references"]))
    if any(sha(p) != digest for p, digest in originals.items()):
        raise ValueError("config sources changed while indexing")
    return plan, snapshots


def binding_id(binding):
    return object_id({k: v for k, v in binding.items() if k != "binding_id"})


def validate_binding(data, manifest, upstream=UPSTREAM):
    """Fail closed on shape/config/entrypoint drift; callable without torch."""
    binding = data["dispatch"]
    family = binding["family"]
    if binding.get("binding_id") != binding_id(binding):
        raise ValueError("dispatch binding changed; regenerate the plan")
    if family not in ENTRYPOINTS or binding["entrypoint"] != ENTRYPOINTS[family]:
        raise ValueError("unreviewed dispatch entrypoint")
    if any(data[k] != binding[k] for k in ("arch", "co", "symbol", "inputs")):
        raise ValueError("manifest differs from frozen dispatch workload")
    if not data.get("validation_hook"):
        raise ValueError("dispatch manifests require op_test validation")
    if data["atol"] != 0.05 or data["rtol"] != 0.02:
        raise ValueError("dispatch adapter tolerances changed")
    expected_driver = HERE / "hsa/gfx942/dispatch_driver.py"
    if (Path(manifest).parent / data["driver"]).resolve() != expected_driver.resolve():
        raise ValueError("dispatch manifest requires the reviewed dispatch driver")
    snapshot = inside(Path(manifest).resolve().parent, binding["snapshot"])
    if sha(snapshot) != binding["snapshot_sha256"]:
        raise ValueError("dispatch snapshot changed")
    _, rows = read_csv(snapshot)
    if sum(row == binding["row"] for _, row in rows) != 1:
        raise ValueError("dispatch row is not unique in snapshot")
    if sha(inside(Path(upstream) / "hsa" / data["arch"], data["co"])) != binding["original_co_sha256"]:
        raise ValueError("original .co changed since dispatch export")
    if data["catalog"] != binding["catalog"] or sha(inside(Path(upstream) / "hsa" / data["arch"], data["catalog"])) != binding["catalog_sha256"]:
        raise ValueError("HSA catalog changed since dispatch export")
    for relative, digest in binding["resolver_sha256"].items():
        if sha(inside(Path(upstream), relative)) != digest:
            raise ValueError("upstream resolver changed; review and regenerate dispatch plan")
    if family == "blockscale_preshuffle":
        _, catalog_rows = read_csv(inside(Path(upstream) / "hsa" / data["arch"], data["catalog"]))
        matches = [row for _, row in catalog_rows if row.get("knl_name") == data["symbol"] and
                   row.get("co_name") == Path(data["co"]).name]
        if len(matches) != 1 or adapter_inputs(family, binding["row"], {"attributes": matches[0]}) != data["inputs"]:
            raise ValueError("blockscale inputs differ from the reviewed CSV adapter contract")
        for key, root, required in (("adapter_sha256", HERE, BLOCKSCALE_ADAPTER_FILES),
                                    ("validation_sha256", Path(upstream), BLOCKSCALE_UPSTREAM_FILES)):
            hashes = binding.get(key, {})
            if set(hashes) != set(required) or any(sha(inside(root, name)) != hashes[name] for name in required):
                raise ValueError("blockscale adapter/validation source changed; review and regenerate dispatch plan")
    return snapshot


def export_plan(plan, snapshots, out, upstream=UPSTREAM):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("choose a new output directory; plans are frozen")
    out.mkdir(parents=True)
    for family, content in snapshots.items():
        (out / (family + ".csv")).write_text(content)
    resolver_hashes = {name: sha(Path(upstream) / name) for name in RESOLVER_FILES}
    for ref in plan["references"]:
        if ref["status"] != "ready_for_validation":
            continue
        match = ref["matches"][0]
        task_id = ref["workload_id"]
        binding = {"version": 1, "family": ref["family"], "entrypoint": ref["entrypoint"],
                   "arch": plan["arch"], "cu_num": plan["cu_num"], "co": match["co"],
                   "symbol": ref["symbol"], "inputs": ref["inputs"], "row": ref["effective_row"],
                   "workload_id": task_id, "snapshot": ref["family"] + ".csv",
                   "snapshot_sha256": sha(out / (ref["family"] + ".csv")),
                   "resolver_sha256": resolver_hashes,
                   "sources": plan["families"][ref["family"]]["sources"],
                   "reference": {"source": ref["source"], "line": ref["line"], "stage": ref["stage"]},
                   "catalog": match["catalog"],
                   "catalog_sha256": sha(Path(upstream) / "hsa" / plan["arch"] / match["catalog"]),
                   "original_co_sha256": sha(Path(upstream) / "hsa" / plan["arch"] / match["co"]),
                   "scope": "exact-row dispatch using frozen arch/CU config override"}
        if ref["family"] == "blockscale_preshuffle":
            binding["adapter_sha256"] = {name: sha(HERE / name) for name in BLOCKSCALE_ADAPTER_FILES}
            binding["validation_sha256"] = {name: sha(Path(upstream) / name) for name in BLOCKSCALE_UPSTREAM_FILES}
        binding["binding_id"] = binding_id(binding)
        manifest = {"schema_version": 1, "arch": plan["arch"], "co": match["co"],
                    "symbol": ref["symbol"], "catalog": match["catalog"],
                    "driver": os.path.relpath(HERE / "hsa/gfx942/dispatch_driver.py", out),
                    "inputs": ref["inputs"], "atol": 0.05, "rtol": 0.02, "validation_hook": True,
                    "dispatch": binding, "resources": {
                        "dispatch_snapshot": binding["snapshot"],
                        "dispatch_code": os.path.relpath(HERE / "dispatch.py", out),
                        "gemm_driver": os.path.relpath(HERE / "hsa/gfx942/gemm_driver.py", out)},
                    "upstream_resources": RESOLVER_FILES + [
                        "op_tests/test_gemm_a16w16.py", "op_tests/test_gemm_a8w8.py",
                        "csrc/py_itfs_cu/asm_gemm_a8w8.cu", "csrc/py_itfs_cu/asm_gemm_a16w16.cu"]}
        if ref["family"] == "blockscale_preshuffle":
            manifest["resources"].update(
                blockscale_driver=os.path.relpath(HERE / "hsa/gfx942/driver.py", out),
                blockscale_optest=os.path.relpath(HERE / "hsa/gfx942/optest_driver.py", out))
            manifest["upstream_resources"] = RESOLVER_FILES + BLOCKSCALE_UPSTREAM_FILES
        # Paths must remain valid when copying the repository to another host.
        path = out / (task_id + ".json")
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        rel = str(path.relative_to(REPO))
        seed = str((out / (task_id + ".s")).relative_to(REPO))
        params = ["--client", "aiter/hsa/gfx942", "--", "--manifest", rel]
        plan["tasks"].append({"task_id": task_id, "co": match["co"], "manifest": path.name,
            "inputs": ref["inputs"], "status": "pending_original_validation", "commands": {
                "prepare": ["python3", "client/aiter/prepare.py", "gfx942", "--manifest", rel, "--out", seed],
                "validate": ["python3", "tools/eval_candidate.py", seed] + params,
                "tune_init": ["python3", "tools/tune_run.py", "init", seed,
                              "--run-id", "dispatch-" + task_id] + params,
                "compare": ["python3", "client/aiter/compare.py", seed, "CANDIDATE.s",
                            "--pairs", "6", "--min-gain", "0.01", "--alpha", "0.05"] + params}})
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def assess_coverage(plan_path, co, comparisons, max_regression):
    """Summarize one frozen candidate over all CSV references of one .co.

    Use lower paired bounds for non-regression; missing/unsupported shapes can
    never disappear behind a favorable average or one completed .co record.
    """
    from types import SimpleNamespace
    from client.aiter.compare import metrics, summarize
    if not math.isfinite(max_regression) or not 0 <= max_regression < 1:
        raise ValueError("--max-regression must be in [0, 1)")
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    ids = set(plan["co_to_workloads"].get(co, []))
    if not ids:
        raise ValueError(".co has no references in this plan")
    refs = {r["workload_id"]: r for r in plan["references"] if r["workload_id"] in ids}
    tasks = {t["task_id"]: t for t in plan["tasks"] if t["co"] == co}
    completed, hashes, devices = {}, set(), set()
    for path in comparisons:
        report = json.loads(Path(path).read_text())
        if report.get("status") != "completed" or not report.get("records"):
            raise ValueError("comparison is incomplete: {}".format(path))
        task_ids = set()
        for record in report["records"]:
            result = record["result"]
            detail = result["detail"]
            checked = detail["runner"].get("dispatch_check", {})
            if (result.get("correct") is not True or checked.get("correct") is not True or
                    detail.get("build_evidence", {}).get("status") != "consistent" or
                    detail["runner"].get("op_test", {}).get("correct") is not True):
                raise ValueError("comparison lacks correctness/dispatch/op_test evidence")
            if metrics(SimpleNamespace(**result)) != record["times_us"]:
                raise ValueError("paired timing differs from runner evidence")
            task_ids.add(checked["workload_id"])
        if len(task_ids) != 1:
            raise ValueError("comparison mixed workload identities")
        task_id = task_ids.pop()
        if task_id not in tasks or task_id in completed:
            raise ValueError("comparison is duplicate or outside this .co/plan")
        identity = report["contract"]["client_identity"]["resources"]
        if identity["manifest"]["sha256"] != sha(plan_path.parent / tasks[task_id]["manifest"]):
            raise ValueError("comparison used a different manifest")
        hashes.add(tuple(report["assemblies"][side]["sha256"] for side in ("reference", "candidate")))
        devices.add(object_id({"device": report["device"],
                               "environment": report["contract"]["client_identity"]["environment"]}))
        # Recompute statistics from paired observations, not a hand-picked us.
        results = summarize(report["records"], report["policy"])
        if "hip_graph" not in results or not any(k.startswith("op_test:") for k in results):
            raise ValueError("comparison must include HIP graph and op_test timing")
        lower = [v["lower_ratio_bound"] for v in results.values()]
        medians = [v["median_ratio"] for v in results.values()]
        bound = 1 / (1 + max_regression)
        status = "pass" if all(v is not None and v >= bound for v in lower) else (
            "regression" if any(v is not None and v < bound for v in medians) else "inconclusive")
        completed[task_id] = {"status": status, "comparison": str(path), "results": results}
    if len(hashes) > 1 or len(devices) > 1:
        raise ValueError("cross-shape comparisons must use the same frozen assemblies and device")
    workloads = []
    for task_id, ref in refs.items():
        row = {"task_id": task_id, "row": ref["row"], "source_status": ref["status"]}
        row.update(completed.get(task_id, {"status": "pending" if task_id in tasks else "unsupported",
                                           "reason": ref["reason"]}))
        workloads.append(row)
    accepted = bool(workloads) and all(r["status"] == "pass" for r in workloads)
    return {"schema_version": 1, "co": co, "max_regression": max_regression,
            "status": "all_referenced_workloads_pass" if accepted else "not_accepted",
            "scope": "only this plan's exact CSV references; no padded-M/heuristic/general workload guarantee; per-workload bounds",
            "assemblies": list(next(iter(hashes))) if hashes else None,
            "counts": dict(Counter(r["status"] for r in workloads)), "workloads": workloads}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    scan = sub.add_parser("plan", help="read-only index + frozen configs/manifests; no GPU")
    scan.add_argument("--arch", default="gfx942", choices=["gfx942"])
    scan.add_argument("--cu", required=True, type=int, help="measured device CU count")
    scan.add_argument("--family", action="append", choices=list(FAMILIES))
    scan.add_argument("--config", action="append", default=[], metavar="FAMILY=PATH[:PATH]",
                      help="explicit sources replace default/model/env sources for this family")
    scan.add_argument("--out", required=True)
    lookup = sub.add_parser("lookup", help="inverse .co -> all exact workload references")
    lookup.add_argument("plan")
    lookup.add_argument("--co", required=True, help="exact relative HSA path")
    assess = sub.add_parser("assess", help="cross-shape comparison coverage for one frozen candidate")
    assess.add_argument("plan")
    assess.add_argument("--co", required=True)
    assess.add_argument("--comparison", action="append", default=[])
    assess.add_argument("--max-regression", type=float, required=True,
                        help="predeclared allowed fractional latency increase per workload/method")
    args = ap.parse_args()
    if args.action == "assess":
        print(json.dumps(assess_coverage(args.plan, args.co, args.comparison, args.max_regression), indent=2))
        return
    if args.action == "lookup":
        plan = json.loads(Path(args.plan).read_text())
        ids = set(plan["co_to_workloads"].get(args.co, []))
        print(json.dumps({"co": args.co, "references": [r for r in plan["references"] if r["workload_id"] in ids],
                          "unreferenced": [r for r in plan["unreferenced_co"] if r["co"] == args.co]}, indent=2))
        return
    overrides = {}
    for item in args.config:
        family, sep, value = item.partition("=")
        if not sep or family not in FAMILIES or family in overrides or not value:
            ap.error("--config requires unique FAMILY=PATH[:PATH]")
        overrides[family] = value
    families = args.family or list(FAMILIES)
    if len(set(families)) != len(families) or set(overrides) - set(families):
        ap.error("duplicate family or override outside selected families")
    out = Path(args.out).resolve()
    if (HERE / "tune_out").resolve() not in out.parents:
        ap.error("--out must be a new directory under client/aiter/tune_out")
    plan, snapshots = build_plan(UPSTREAM, args.arch, args.cu, families, overrides)
    export_plan(plan, snapshots, out)
    print(json.dumps({"plan": str(out / "plan.json"), "counts": plan["counts"],
                      "tasks": len(plan["tasks"]), "referenced_co": len(plan["co_to_workloads"])}, indent=2))


if __name__ == "__main__":
    main()
