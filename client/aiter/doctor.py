#!/usr/bin/env python3
"""Check the selected container/environment; imports torch but does not run kernels or JIT."""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def inspect_environment(profile, expected_pci=None):
    report = {"schema_version": 1, "python": sys.version, "executable": sys.executable,
              "modules": {}, "errors": [], "tools": {}}
    errors = report["errors"]
    upstream = HERE / "upstream"
    for path in ("aiter/__init__.py", "hsa/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co"):
        if not (upstream / path).is_file():
            errors.append("missing submodule file: " + path + "; run bash tools/init_aiter.sh")
    try:
        revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        report["aiter_commit"] = revision
        if revision != profile["aiter_commit"]:
            errors.append("aiter commit differs from reviewed environment profile; review compatibility first")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append("cannot read aiter git revision: " + str(exc))
    modules = {}
    for name in profile["required_modules"]:
        try:
            modules[name] = importlib.import_module(name)
            report["modules"][name] = str(getattr(modules[name], "__version__", "imported"))
        except Exception as exc:
            errors.append("{}: {}".format(name, exc))
    if "triton" in modules and "packaging" in modules:
        from packaging.version import Version
        if Version(modules["triton"].__version__.split("+")[0]) < Version(profile["triton_min"]):
            errors.append("reviewed aiter requires triton >= " + profile["triton_min"])
    llvm = Path(os.environ.get("ROCM_LLVM_BIN", "/opt/rocm/llvm/bin"))
    for name in ("clang", "ld.lld", "llvm-readelf", "llvm-objdump"):
        path = llvm / name
        report["tools"][name] = str(path)
        if not path.is_file():
            errors.append("missing LLVM tool: " + str(path))
    if not shutil.which("hipcc"):
        errors.append("hipcc is absent from PATH")
    torch = modules.get("torch")
    if torch is not None:
        report["hip"] = torch.version.hip
        try:
            # aiter imports Dynamo even for an assembly-only operator. Import
            # it here to catch UID/cache problems without importing/JITing aiter.
            importlib.import_module("torch._dynamo")
        except Exception as exc:
            errors.append("torch._dynamo import/cache setup: " + str(exc))
        try:
            count = torch.cuda.device_count()
            report["visible_devices"] = count
            if not torch.version.hip or count != 1:
                raise ValueError("require ROCm PyTorch with exactly one visible GPU; found {}".format(count))
            props = torch.cuda.get_device_properties(0)
            arch = props.gcnArchName.split(":")[0]
            pci = "{:04x}:{:02x}:{:02x}.0".format(props.pci_domain_id, props.pci_bus_id, props.pci_device_id)
            report["device"] = {"name": props.name, "arch": arch, "pci": pci, "uuid": str(props.uuid)}
            if arch != profile["arch"]:
                errors.append("selected GPU architecture differs from profile")
            if expected_pci and pci.lower() != expected_pci.lower():
                errors.append("selected GPU PCI mismatch: expected {}, observed {}".format(expected_pci, pci))
        except Exception as exc:
            errors.append(str(exc))
    report["visibility"] = {k: os.environ.get(k) for k in
                            ("ROCR_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "GPU_DEVICE_ORDINAL")}
    report["ok"] = not errors
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default=str(HERE / "env/gfx942.json"))
    ap.add_argument("--expected-pci")
    args = ap.parse_args(argv)
    try:
        report = inspect_environment(json.loads(Path(args.profile).read_text()), args.expected_pci)
    except Exception as exc:
        report = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
