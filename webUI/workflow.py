"""Explicit UI actions for the frozen aiter workload workflow (argv only)."""
import math
import os
from pathlib import Path
import re
import shutil
import sys

from webUI.workloads import local_record_path, resolve_task

ACTIONS = {"dispatch_plan", "dispatch_prepare", "dispatch_validate", "dispatch_init",
           "dispatch_evaluate", "dispatch_compare", "dispatch_assess", "run_step"}


def positive(value, default, integer=True):
    try:
        n = int(value if value not in (None, "") else default) if integer else float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        raise ValueError("请输入有效的数字")
    if not math.isfinite(n) or n <= 0:
        raise ValueError("参数必须为正数")
    if integer and float(value if value not in (None, "") else default) != n:
        raise ValueError("参数必须为整数")
    return str(n)


def file_path(value, repo, suffix):
    path = local_record_path(value or "", repo)
    if not path.is_file() or path.suffix != suffix:
        raise ValueError("请选择仓库内已有的 {} 文件".format(suffix))
    return str(path)


def command(action, p, repo):
    repo = Path(repo).resolve()
    python = shutil.which("python3.8") or sys.executable
    env = {}
    if p.get("gpu"):
        gpu = str(p["gpu"]).strip()
        if not re.fullmatch(r"(?:\d+|GPU-[A-Za-z0-9-]+)", gpu):
            raise ValueError("GPU 请选择单卡可见序号或 UUID")
        env["HIP_VISIBLE_DEVICES"] = gpu
    def gpu_required():
        if not env and not any(os.environ.get(k) for k in ("HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES")):
            raise ValueError("请填写单卡 GPU 序号/UUID，或在已限制可见 GPU 的环境中启动 Web UI")
    if action == "dispatch_plan":
        out = local_record_path(p.get("out") or "", repo)
        out.resolve().relative_to(repo / "client/aiter/tune_out")
        if out.exists():
            raise ValueError("计划输出目录必须是新目录")
        argv = [python, "client/aiter/dispatch.py", "plan", "--cu", positive(p.get("cu"), None), "--out", str(out)]
        from client.aiter.dispatch import FAMILIES
        family = p.get("family")
        if family:
            if family not in FAMILIES:
                raise ValueError("未知 family")
            argv += ["--family", family]
        if p.get("config"):
            if not family:
                raise ValueError("指定 CSV 时请选择一个 family")
            paths = [file_path(s.strip(), repo, ".csv") for s in p["config"].splitlines() if s.strip()]
            argv += ["--config", family + "=" + os.pathsep.join(paths)]
        return "生成 CSV workload 计划（CPU）", argv, str(repo), {}
    if action == "run_step":
        run = local_record_path(p.get("run") or "", repo)
        run.resolve().relative_to(repo / "client/aiter/tune_out")
        if not (run / "manifest.json").is_file():
            raise ValueError("调优 run 不存在")
        step = p.get("step", "status")
        if step not in {"status", "observe", "suggest", "prepare", "eval", "confirm", "final"}:
            raise ValueError("非法调优步骤")
        argv = [python, "tools/tune_run.py", step, str(run)]
        if step in {"eval", "confirm"}:
            candidate = (p.get("candidate_id") or "original").strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", candidate):
                raise ValueError("非法候选 ID")
            argv.append(candidate)
        if step == "prepare":
            if not p.get("observation") or not p.get("base_sha256"):
                raise ValueError("准备候选需要 observation 和 base SHA256")
            argv += ["--observation", p["observation"], "--base-sha256", p["base_sha256"],
                     "--spec-file", file_path(p.get("spec_file"), repo, ".json")]
        if step in {"eval", "confirm", "final"}:
            gpu_required()
        return "调优步骤 · " + step, argv, str(repo), env
    config, manifest, seed = resolve_task(repo, p.get("plan", ""), p.get("task_id"))
    params = ["--manifest", str(manifest), "--python", p.get("python") or "python3",
              "--warmup", positive(p.get("warmup"), 20), "--iters", positive(p.get("iters"), 100),
              "--samples", positive(p.get("samples"), 7)]
    if action == "dispatch_prepare":
        argv = [python, "client/aiter/prepare.py", "gfx942", "--manifest", str(manifest), "--out", str(seed)]
        label = "导出原始 seed"
    elif action == "dispatch_init":
        file_path(str(seed), repo, ".s")
        run_id = (p.get("run_id") or "dispatch-" + p["task_id"]).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id) or run_id in (".", ".."):
            raise ValueError("非法 run ID")
        argv = [python, "tools/tune_run.py", "init", str(seed), "--run-id", run_id,
                "--eval-calls", positive(p.get("eval_calls"), 48)]
        if p.get("policy"):
            argv += ["--comparison-policy", file_path(p["policy"], repo, ".json")]
        if p.get("search_policy"):
            argv += ["--search-policy", file_path(p["search_policy"], repo, ".json")]
        argv += ["--client", "aiter/hsa/gfx942", "--"] + params
        label = "创建逐 workload 调优任务"
    elif action in {"dispatch_validate", "dispatch_evaluate"}:
        gpu_required()
        candidate = str(seed) if action == "dispatch_validate" else p.get("candidate")
        argv = [python, "tools/eval_candidate.py", file_path(candidate, repo, ".s"), "--client", "aiter/hsa/gfx942", "--"] + params
        label = "原始派发与 op_test 验证" if action == "dispatch_validate" else "候选 op_test 验证"
    elif action == "dispatch_compare":
        gpu_required()
        argv = [python, "client/aiter/compare.py", file_path(str(seed), repo, ".s"),
                file_path(p.get("candidate"), repo, ".s"), "--client", "aiter/hsa/gfx942",
                "--pairs", positive(p.get("pairs"), 6), "--min-gain", positive(p.get("min_gain"), 0.01, False),
                "--alpha", positive(p.get("alpha"), 0.05, False), "--"] + params
        label = "固定候选配对比较"
    elif action == "dispatch_assess":
        paths = [file_path(s.strip(), repo, ".json") for s in (p.get("comparisons") or "").splitlines() if s.strip()]
        argv = [python, "client/aiter/dispatch.py", "assess", str(local_record_path(p["plan"], repo)),
                "--co", config["co"], "--max-regression", positive(p.get("max_regression"), 0.01, False)]
        for path in paths:
            argv += ["--comparison", path]
        label = "同一 .co 跨尺寸覆盖汇总"
    else:
        raise ValueError("未知 workload 操作")
    return label + " · " + p["task_id"], argv, str(repo), env
