#!/usr/bin/env python3
"""Create an isolated aiter container with a verified GPU mapping. Run on the target host."""
import argparse
import json
import os
import pwd
from pathlib import Path
import re
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTAINER_REPO = "/workspace/FACK"
LABEL = "org.fack.aiter-validation"
MASKS = ("ROCR_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "GPU_DEVICE_ORDINAL")


def command(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, text=True, **kwargs).stdout.strip()


def parse_inventory(data):
    devices = []
    for key, row in data.items():
        match = re.fullmatch(r"card(\d+)", key)
        if not match:
            continue
        pci, unique = row.get("PCI Bus", ""), row.get("Unique ID", "")
        if not re.fullmatch(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]", pci):
            raise ValueError("invalid PCI identity in rocm-smi output")
        if not re.fullmatch(r"0x[0-9a-fA-F]{1,16}", unique) or int(unique, 16) == 0:
            raise ValueError("missing GPU unique ID; cannot verify selection")
        devices.append({"index": int(match[1]), "pci": pci.lower(),
                        "uuid": "GPU-{:016x}".format(int(unique, 16)),
                        "arch": row.get("GFX Version"), "name": row.get("Card Series")})
    if not devices or len({d["uuid"] for d in devices}) != len(devices):
        raise ValueError("empty or ambiguous GPU inventory")
    return sorted(devices, key=lambda d: d["index"])


def select_gpu(devices, selector, arch):
    eligible = [d for d in devices if d["arch"] == arch]
    if selector == "second-last":
        if len(eligible) < 2:
            raise ValueError("second-last requires at least two {} devices".format(arch))
        return eligible[-2]
    matches = [d for d in eligible if selector.lower() in
               (str(d["index"]), d["pci"].lower(), d["uuid"].lower())]
    if len(matches) != 1:
        raise ValueError("GPU selection must identify one {} device".format(arch))
    return matches[0]


def build_start_command(repo, image_id, name, device, work, max_jobs, groups):
    if "," in str(repo) or "\n" in str(repo):
        raise ValueError("Docker --mount path must not contain a comma or newline")
    relative = work.relative_to(repo).as_posix()
    cache = CONTAINER_REPO + "/" + relative + "/cache"
    argv = ["docker", "run", "-d", "--name", name, "--label", LABEL + "=1",
            "--label", "org.fack.repo=" + str(repo), "--device=/dev/kfd", "--device=/dev/dri",
            "--security-opt", "seccomp=unconfined", "--shm-size=8g", "--init",
            "--user", "{}:{}".format(os.getuid(), os.getgid()),
            "--mount", "type=bind,src={},dst={}".format(repo, CONTAINER_REPO),
            "--workdir", CONTAINER_REPO, "--entrypoint", "/bin/bash"]
    for group in sorted(set(groups)):
        argv.extend(["--group-add", str(group)])
    env = {"ROCR_VISIBLE_DEVICES": device["uuid"], "HIP_VISIBLE_DEVICES": "0",
           "CUDA_VISIBLE_DEVICES": "0", "GPU_DEVICE_ORDINAL": "0", "GPU_ARCHS": device["arch"],
           "MAX_JOBS": str(max_jobs), "XDG_CACHE_HOME": cache,
           "TRITON_CACHE_DIR": cache + "/triton", "TORCH_EXTENSIONS_DIR": cache + "/torch",
           "TORCHINDUCTOR_CACHE_DIR": cache + "/inductor",
           "USER": pwd.getpwuid(os.getuid()).pw_name, "LOGNAME": pwd.getpwuid(os.getuid()).pw_name,
           "PYTHONPYCACHEPREFIX": cache + "/pycache", "PYTHONPATH": ""}
    for key, value in env.items():
        argv.extend(["--env", key + "=" + value])
    return argv + [image_id, "-c", "exec sleep infinity"]


def start(args):
    inherited = {k: os.environ[k] for k in MASKS if k in os.environ}
    if inherited:
        raise ValueError("host visibility restrictions are already set ({}); resolve their device scope explicitly before using physical GPU selection".format(", ".join(inherited)))
    profile = json.loads((HERE / "env/gfx942.json").read_text())
    devices = parse_inventory(json.loads(command(["rocm-smi", "--showbus", "--showuniqueid", "--showproductname", "--json"])))
    device = select_gpu(devices, args.gpu, profile["arch"])
    image_ref = args.image or profile["image"]
    # Resolve once; run the immutable local image ID even if the input was a tag.
    info = json.loads(command(["docker", "image", "inspect", image_ref]))[0]
    image_env = dict(e.split("=", 1) for e in info.get("Config", {}).get("Env", []) if "=" in e)
    # A restricted base image is not a reliable device inventory source.
    restrictions = {k: v for k, v in image_env.items() if k in MASKS and v not in ("", "all")}
    if restrictions:
        raise ValueError("base image has baked-in visibility restrictions: {}".format(", ".join(restrictions)))
    name = args.name or "fack-aiter-" + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
        raise ValueError("invalid container name")
    work = HERE / "tune_out" / "environments" / name
    work.mkdir(parents=True, exist_ok=False)
    (work / "cache").mkdir()
    groups = [p.stat().st_gid for p in [Path("/dev/kfd")] + list(Path("/dev/dri").glob("renderD*"))]
    argv = build_start_command(REPO, info["Id"], name, device, work, args.max_jobs, groups)
    report = {"schema_version": 1, "container": name, "host_repo": str(REPO),
              "container_repo": CONTAINER_REPO, "device": device, "inventory": devices,
              "image_ref": image_ref, "image_id": info["Id"], "repo_digests": info.get("RepoDigests", []),
              "python": args.python or profile["python"], "command": argv, "status": "starting"}
    def save():
        (work / "environment.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    created = False
    try:
        report["container_id"] = command(argv)
        created = True
        check = subprocess.run(["docker", "exec", name, report["python"], "client/aiter/doctor.py",
                                "--expected-pci", device["pci"]], capture_output=True, text=True)
        (work / "doctor.stdout").write_text(check.stdout)
        (work / "doctor.stderr").write_text(check.stderr)
        report["doctor"] = json.loads(check.stdout)
        if check.returncode or report["doctor"].get("ok") is not True:
            raise ValueError("container preflight failed; inspect " + str(work / "doctor.stdout"))
        report["status"] = "ready"
    except BaseException as exc:
        report.update(status="failed", error=str(exc))
        if created:
            subprocess.run(["docker", "stop", name], capture_output=True)
        raise
    finally:
        save()
    return {"container": name, "device": device, "record": str(work / "environment.json"), "status": "ready"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("inventory", help="read the host GPU inventory; no container or GPU kernels")
    add = sub.add_parser("start", help="create a new container and check dependencies/device mapping")
    add.add_argument("--gpu", required=True, help="physical rocm-smi index, PCI, GPU UUID, or second-last")
    add.add_argument("--image", help="existing local image reference; default is the reviewed digest")
    add.add_argument("--name")
    add.add_argument("--python", help="Python inside the image; default comes from the reviewed profile")
    add.add_argument("--max-jobs", type=int, default=8)
    stop = sub.add_parser("stop", help="stop only a container created by this tool for this checkout")
    stop.add_argument("name")
    args = ap.parse_args(argv)
    try:
        if args.action == "inventory":
            result = parse_inventory(json.loads(command(["rocm-smi", "--showbus", "--showuniqueid", "--showproductname", "--json"])))
        elif args.action == "start":
            if args.max_jobs < 1:
                raise ValueError("max-jobs must be positive")
            result = start(args)
        else:
            info = json.loads(command(["docker", "inspect", args.name]))[0]
            labels = info.get("Config", {}).get("Labels", {})
            if labels.get(LABEL) != "1" or labels.get("org.fack.repo") != str(REPO):
                raise ValueError("container was not created by this tool for this checkout")
            result = {"stopped": command(["docker", "stop", args.name])}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print(json.dumps({"error": detail}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
