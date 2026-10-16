"""Locate the exact aiter code object measured by a successful final; CPU only."""
import hashlib
from pathlib import Path, PurePosixPath
import re

from client.aiter.agent_profile import result_evidence
from harness.validation import evidence


def publication_candidate(report):
    profile = report["manifest"]["evaluation_contract"]["agent_profile"]
    workload, validation = profile["workload"], profile["validation"]
    arch, co = profile["arch"], workload["co"]
    relative = PurePosixPath(co)
    if (not re.fullmatch(r"gfx[0-9a-f]+", arch) or relative.is_absolute() or
            ".." in relative.parts or "\\" in co or relative.as_posix() != co or relative.suffix != ".co"):
        raise ValueError("invalid original aiter code-object path")
    if not validation or "hip_graph" not in validation["metrics"] or not any(
            name.startswith("op_test:") for name in validation["metrics"]):
        raise ValueError("aiter publication requires the frozen complete validation contract")
    final = report["comparisons"][report["final_result"]["comparison_id"]]
    config = dict(workload, arch=arch)
    hashes, paths = {"reference": set(), "candidate": set()}, []
    for pair in final["pairs"]:
        for side in ("reference", "candidate"):
            batch = report["batches"][pair["batches"][side]]
            sample = report["attempts"][batch["attempt_ids"][0]]["result"]
            detail = sample["detail"]
            build, runner = detail["build_evidence"], detail["runner"]
            normalized = result_evidence(config, runner, build)
            if normalized != detail.get("validation"):
                raise ValueError("aiter validation does not reproduce from runner/build evidence")
            evidence(sample, validation)
            expected_source = final[side + "_sha256"]
            source = build.get("source_before", {})
            artifact = build.get("artifact_after_build", {})
            if (source.get("status") != "present" or source.get("sha256") != expected_source or
                    any(build.get(key) != source for key in ("source_after_build", "source_after_evaluation")) or
                    artifact.get("status") != "present" or artifact != build.get("artifact_after_evaluation") or
                    not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", ""))):
                raise ValueError("final source/code-object identity is incomplete or changed")
            hashes[side].add(artifact["sha256"])
            if side == "candidate":
                paths.append(artifact["path"])
    if any(len(values) != 1 for values in hashes.values()):
        raise ValueError("final samples did not measure one stable code object on each side")
    if hashes["candidate"] == hashes["reference"]:
        return None  # Normalization can change assembly text without changing code.
    expected = next(iter(hashes["candidate"]))
    for filename in dict.fromkeys(paths):
        path = Path(filename)
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("measured final code object changed: " + filename)
        if not raw.startswith(b"\x7fELF"):
            raise ValueError("measured code object is not ELF")
        inputs = workload["inputs"]
        display = ({k: inputs[k] for k in ("m", "n", "k", "splitK", "dtype", "outdtype") if k in inputs}
                   if all(k in inputs for k in ("m", "n", "k")) else inputs)
        return {"relative_path": arch + "/" + co, "code_object": raw,
                "co_sha256": expected, "original_co_sha256": next(iter(hashes["reference"])),
                "display_inputs": display}
    raise ValueError("measured final code object is missing; publication never rebuilds it")
