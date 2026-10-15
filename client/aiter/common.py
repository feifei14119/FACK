"""Filesystem-only configuration shared by the client and seed preparation."""
import argparse
import csv
import json
import math
import os
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "upstream"


def inside(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("expected a relative path inside {}: {}".format(root, relative))
    path = root / rel
    if root.resolve() not in path.resolve().parents:
        raise ValueError("path escapes {}: {}".format(root, relative))
    return path


def load_manifest(path, arch):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    required = {"schema_version", "arch", "co", "symbol", "driver", "inputs", "atol", "rtol"}
    if not required <= set(data) or data["schema_version"] != 1 or data["arch"] != arch:
        raise ValueError("manifest schema/architecture mismatch: {}".format(path))
    if not re.fullmatch(r"[A-Za-z_.$][A-Za-z0-9_.$]*", data["symbol"]):
        raise ValueError("invalid kernel symbol")
    co = inside(UPSTREAM / "hsa" / arch, data["co"])
    if co.suffix != ".co" or not co.is_file():
        raise ValueError("missing HSA .co (initialize submodule): {}".format(co))
    driver = (path.parent / data["driver"]).resolve()
    if not driver.is_file() or driver.suffix != ".py":
        raise ValueError("missing Python driver: {}".format(driver))
    if not isinstance(data["inputs"], dict):
        raise ValueError("inputs must be an object")
    if "validation_hook" in data and type(data["validation_hook"]) is not bool:
        raise ValueError("validation_hook must be a boolean")
    for key in ("atol", "rtol"):
        if type(data[key]) not in (int, float) or not math.isfinite(data[key]) or data[key] < 0:
            raise ValueError("{} must be finite and nonnegative".format(key))
    if "catalog" in data:
        catalog = inside(UPSTREAM / "hsa" / arch, data["catalog"])
        with catalog.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        matching = [r for r in rows if r.get("knl_name") == data["symbol"] and
                    r.get("co_name") == co.name]
        if len(matching) != 1 or catalog.parent != co.parent:
            raise ValueError("symbol/.co pair not uniquely present in HSA catalog")
        if any(str(matching[0].get(k)) != str(v) for k, v in data.get("selection", {}).items()):
            raise ValueError("HSA catalog layout differs from manifest selection")
    if "dispatch" in data:
        from client.aiter.dispatch import validate_binding
        validate_binding(data, path, UPSTREAM)
    return data, driver


def options(ctx):
    # Supported cases are real directories: FACK ships only its selected arch.
    parts = Path(ctx.case).parts
    if len(parts) != 2 or parts[0] != "hsa" or not (HERE / ctx.case / "manifest.json").is_file():
        raise ValueError("select an aiter/hsa/<gfx> client listed in client/aiter/README.md")
    ap = argparse.ArgumentParser(prog="aiter client parameters")
    ap.add_argument("--manifest", default=str(HERE / ctx.case / "manifest.json"))
    ap.add_argument("--python", default="python3", help="target-machine Python with ROCm torch and aiter dependencies")
    ap.add_argument("--m", type=int)
    ap.add_argument("--n", type=int)
    ap.add_argument("--k", type=int)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--iters", type=int, default=max(1, ctx.loop))
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--output-dir", help="evaluation artifacts under client/aiter/tune_out")
    opts = ap.parse_args(ctx.params)
    if opts.output_dir:
        opts.output_dir = str(Path(opts.output_dir).resolve())
        root = (HERE / "tune_out").resolve()
        if root not in Path(opts.output_dir).parents and Path(opts.output_dir) != root:
            raise ValueError("--output-dir must be inside client/aiter/tune_out")
    interpreter = shutil.which(opts.python)
    if interpreter:
        # Preserve a venv executable symlink while making it independent of runner cwd.
        opts.python = os.path.abspath(interpreter)
    if (min(opts.iters, opts.samples, opts.warmup) < 1 or
            not math.isfinite(opts.timeout) or opts.timeout <= 0):
        raise ValueError("iterations, samples, warmup and timeout must be positive")
    data, driver = load_manifest(opts.manifest, parts[1])
    data["inputs"] = dict(data["inputs"])
    for key in ("m", "n", "k"):
        value = getattr(opts, key)
        if value is not None:
            if "dispatch" in data and value != data["inputs"].get(key):
                raise ValueError("CSV-bound workload cannot override --{}; generate another task".format(key))
            if value <= 0:
                raise ValueError("shape dimensions must be positive")
            data["inputs"][key] = value
    if ctx.kernel and ctx.kernel != data["symbol"]:
        raise ValueError("--kernel must match manifest symbol")
    opts.manifest = str(Path(opts.manifest).resolve())
    return opts, data, driver


def source_target(source, arch, symbol):
    match = re.search(r'^\s*\.amdgcn_target\s+"amdgcn-amd-amdhsa--([^"\s]+)"', source, re.M)
    cov = re.search(r'^\s*\.amdhsa_code_object_version\s+(\d+)', source, re.M)
    if not match or match[1].split(":")[0] != arch or not cov:
        raise ValueError("seed must declare the matching .amdgcn_target and code-object version")
    if not re.search(r'^\s*\.amdhsa_kernel\s+' + re.escape(symbol) + r'\s*$', source, re.M):
        raise ValueError("seed has no descriptor for manifest symbol")
    return match[1], int(cov[1])
