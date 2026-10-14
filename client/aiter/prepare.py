#!/usr/bin/env python3
"""On the target machine, turn the manifest's pinned .co into a verified seed.s."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from client.aiter.common import HERE, UPSTREAM, load_manifest, source_target


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arch", choices=sorted(p.name for p in (HERE / "hsa").iterdir() if p.is_dir()))
    ap.add_argument("--manifest", help="custom manifest; paths inside it are relative to its directory")
    ap.add_argument("--out", required=True, help="new .s output path outside upstream/")
    ap.add_argument("--exact", action="store_true", help="require byte-identical .text in round-trip")
    args = ap.parse_args()
    manifest = Path(args.manifest or HERE / "hsa" / args.arch / "manifest.json").resolve()
    config, _ = load_manifest(manifest, args.arch)
    original = UPSTREAM / "hsa" / args.arch / config["co"]
    out = Path(args.out).resolve()
    provenance = out.with_suffix(out.suffix + ".json")
    if UPSTREAM in out.parents or out.suffix != ".s" or out.exists() or provenance.exists():
        ap.error("choose a new .s path outside the upstream submodule")
    converter = REPO / "tools" / args.arch / "co2s.py"
    if not converter.is_file():
        converter = REPO / "tools" / "co2s.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="aiter-seed-") as directory:
        temp = Path(directory) / "seed.s"
        cmd = [sys.executable, str(converter), str(original), "-o", str(temp)]
        if args.exact:
            cmd.append("--exact")
        # No --no-verify escape: a failed round-trip must not publish a seed.
        subprocess.run(cmd, check=True)
        source_target(temp.read_text(), args.arch, config["symbol"])
        if hashlib.sha256(original.read_bytes()).hexdigest() != original_hash:
            raise RuntimeError("original code object changed during preparation")
        with out.open("x") as stream:
            stream.write(temp.read_text())
    revision = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    provenance.write_text(json.dumps({"upstream_commit": revision, "manifest": str(manifest),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "original_co": str(original), "original_sha256": original_hash,
        "seed_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "symbol": config["symbol"], "arch": args.arch, "exact": args.exact}, indent=2) + "\n")
    print("Verified seed: {}".format(out))


if __name__ == "__main__":
    main()
