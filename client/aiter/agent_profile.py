"""Filesystem-only aiter guidance and per-adapter validation requirements."""
from pathlib import Path

from client.aiter.common import HERE, options, source_target


def validation_contract(config, driver):
    if config.get("validation_hook") is not True:
        raise ValueError("aiter tuning requires op_test: select a dispatch-plan manifest or the reviewed optest_manifest.json")
    if config["arch"] != "gfx942":
        raise ValueError("aiter agent validation is not implemented for " + config["arch"])
    if Path(driver).resolve().parent != (HERE / "hsa" / config["arch"]).resolve():
        raise ValueError("aiter tuning requires a reviewed driver under its architecture directory")
    name = Path(driver).name
    family = config["inputs"].get("family")
    if name == "optest_driver.py" or (name == "dispatch_driver.py" and family == "blockscale"):
        distributions = ["constant/constant", "uniform/auto"]
    elif name in ("gemm_driver.py", "dispatch_driver.py") and family in ("i8", "bf16"):
        distributions = ["signed_random/" + ("per_token" if family == "i8" else "none")]
    elif name == "moe_stage1_driver.py":
        distributions = ["signed_random_routed/per_token"]
    elif name == "mla_stage1_driver.py":
        distributions = ["signed_random_channel_mean/unit_tensor"]
    else:
        raise ValueError("aiter adapter has no declared validation contract: " + name)
    checks = ["full_output", "loader_identity", "build_identity", "op_test"]
    if "dispatch" in config:
        checks.append("dispatch_matches_workload")
    return {"metrics": {key: {"unit": "us", "direction": "lower"}
                        for key in ["hip_graph"] + ["op_test:" + x for x in distributions]},
            "primary_metric": "hip_graph", "required_checks": checks,
            "recommendation_scope": "workload", "associated_workloads": "required_for_artifact_adoption"}


def agent_profile(ctx):
    parts = Path(ctx.case).parts
    selected_arch = parts[1] if len(parts) == 2 and parts[0] == "hsa" else None
    skills = ["knowledge/skills/aiter-tuning/SKILL.md"]
    if selected_arch == "gfx942":
        skills.append("knowledge/skills/aiter-gfx942-validation/SKILL.md")
    # Planning must work before installing aiter or constructing a workload.
    # A bound tuning run always supplies seed_src and takes the strict path below.
    if not ctx.seed_src and "--manifest" not in ctx.params and not any(x.startswith("--manifest=") for x in ctx.params):
        return {"arch": selected_arch, "skills": skills, "validation": None, "requires_workload": True,
                "workload": None, "instructions": [
                    "Planning only: prepare the selected architecture and generate/select a workload manifest using the aiter skill.",
                    "Request guidance again with --manifest before tuning. No validation requirements or workload have been bound yet."]}
    opts, config, driver = options(ctx)
    if ctx.seed_src:
        source_target(ctx.seed_src, config["arch"], config["symbol"])
    return {"arch": config["arch"],
            "skills": skills,
            "validation": validation_contract(config, driver),
            "publication": {"mode": "git_commit_push", "output_dir": "client/aiter/co_out", "readme": "README.md"},
            "workload": {"manifest": opts.manifest, "co": config["co"], "symbol": config["symbol"],
                         "inputs": config["inputs"], "source": "dispatch_csv" if "dispatch" in config else "explicit_manifest",
                         "dispatch": config.get("dispatch")},
            "instructions": ["Use the frozen aiter workload; CSV row parameters are not tuning variables.",
                             "A single-run recommendation is workload-scoped. Use compare.py and dispatch.py assess for associated workloads before claiming artifact adoption."]}


def _zero(value):
    return type(value) in (int, float) and value == 0


def _op_check_passed(check):
    # An explicit failure must never be overridden by another successful field.
    return (("passed" in check or "error_ratio" in check) and
            ("passed" not in check or check["passed"] is True) and
            ("error_ratio" not in check or _zero(check["error_ratio"])))


def result_evidence(config, report, build):
    """Normalize aiter evidence. Missing distributions remain missing, never inferred."""
    metrics = {"hip_graph": report.get("time_us")}
    op = report.get("op_test", {})
    if not isinstance(op, dict):
        raise ValueError("op_test evidence must be an object")
    rows = op.get("rows", [])
    checks = report.get("checks", [])
    op_checks = op.get("checks", [])
    if any(not isinstance(items, list) or any(not isinstance(x, dict) for x in items)
           for items in (rows, checks, op_checks)):
        raise ValueError("validation rows and checks must be lists of objects")
    for row in rows:
        name = "op_test:{}/{}".format(row.get("data_init"), row.get("scale_init"))
        if name in metrics:
            raise ValueError("duplicate op_test distribution")
        metrics[name] = row.get("asm us")
    expected_cases = {"seed+0", "seed+1", "after_graph_replay"}
    dispatch = report.get("dispatch_check", {})
    binding = config.get("dispatch", {})
    return {"metrics": metrics, "checks": {
        "full_output": (report.get("correct") is True and len(checks) == 3 and
                        {x.get("case") for x in checks} == expected_cases and
                        all(x.get("passed") is True for x in checks)),
        "loader_identity": (report.get("loader_observed") is True and report.get("arch") == config["arch"] and
                            report.get("symbol") == config["symbol"] and bool(report.get("co_sha256")) and
                            report.get("co_sha256") == build.get("artifact_after_build", {}).get("sha256")),
        "build_identity": build.get("status") == "consistent",
        "op_test": (op.get("correct") is True and op.get("symbol") == config["symbol"] and bool(rows) and
                    all(_zero(x.get("asm err")) for x in rows) and bool(op_checks) and
                    all(_op_check_passed(x) for x in op_checks)),
        "dispatch_matches_workload": (bool(binding) and dispatch.get("correct") is True and
                                      dispatch.get("workload_id") == binding.get("workload_id") and
                                      dispatch.get("cu_num") == binding.get("cu_num") and
                                      dispatch.get("snapshot_sha256") == binding.get("snapshot_sha256") and
                                      dispatch.get("entrypoint") == binding.get("entrypoint"))}}
