"""Read-only, explicitly declared client resources and per-call build evidence.

File hashes describe bytes observed on disk. They do not attest which object a
GPU loaded, nor discover transitive Python/native dependencies or hardware state.
Identity collection never imports external test code or executes a tool.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat


IDENTITY_SCOPE = "declared_files_and_environment_only; hardware_and_loaded_code_unverified"
ENVIRONMENT_ALLOWLIST = frozenset((
    "PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONPATH", "ROCM_PATH",
    "ROCM_LLVM_BIN", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES",
    "CUDA_VISIBLE_DEVICES", "GPU_DEVICE_ORDINAL", "HSA_XNACK", "HSA_USE_SVM",
    "HSA_ENABLE_SDMA", "HIP_FORCE_DEV_KERNARG", "HSA_FORCE_FINE_GRAIN_PCIE",
    "OMP_NUM_THREADS",
))
# Lookup takes the first match, so a repeated entry never changes resolution;
# shells that re-append on every nesting level must not break a frozen identity.
SEARCH_PATH_VARIABLES = frozenset(("PATH", "LD_LIBRARY_PATH", "PYTHONPATH"))


def _environment_value(name):
    value = os.environ[name]
    if name in SEARCH_PATH_VARIABLES:
        value = os.pathsep.join(dict.fromkeys(value.split(os.pathsep)))
    return value


def file_identity(path):
    """Hash one declared regular file; absence/unreadability are explicit data.

    No directory traversal and no special-device reads. Metadata is checked
    around streaming reads to reject a file observed changing during hashing.
    Modification times are intentionally excluded from the stable identity.
    """
    if path is None:
        return {"path": None, "status": "unresolved"}
    path = os.path.abspath(os.fspath(path))
    result = {"path": path, "resolved_path": os.path.realpath(path)}
    fd = None
    try:
        # O_NONBLOCK avoids waiting indefinitely if a file is replaced by a FIFO.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            return dict(result, status="not_regular")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb") as stream:
            fd = None
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        current = os.stat(path)
        keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if (any(getattr(before, k) != getattr(after, k) for k in keys) or
                any(getattr(after, k) != getattr(current, k) for k in keys) or
                result["resolved_path"] != os.path.realpath(path)):
            return dict(result, status="changed_during_read")
        return dict(result, status="present", size=after.st_size, sha256=digest.hexdigest())
    except FileNotFoundError:
        return dict(result, status="missing")
    except OSError as exc:
        # An errno is sufficient and avoids including unrelated exception text.
        return dict(result, status="unreadable", errno=exc.errno)
    finally:
        if fd is not None:
            os.close(fd)


def unavailable_identity():
    return {"schema_version": 1, "status": "unavailable",
            "reason": "client_identity_not_declared", "scope": IDENTITY_SCOPE}


def collect_identity(resources, environment=()):
    """Snapshot a client's explicit file/variable declarations, without commands.

    Environment names outside the public allowlist are rejected before reading
    any values. Clients must not declare credential files as resources.
    """
    if not isinstance(resources, dict) or not all(isinstance(k, str) for k in resources):
        raise ValueError("identity resources must map string names to file paths")
    if not isinstance(environment, (list, tuple)) or not all(isinstance(k, str) for k in environment):
        raise ValueError("identity environment must be a list of allowed variable names")
    if set(environment) - ENVIRONMENT_ALLOWLIST:
        raise ValueError("identity environment contains a variable outside the allowlist")
    files = {name: file_identity(path) for name, path in sorted(resources.items())}
    env = {name: ({"status": "present", "value": _environment_value(name)} if name in os.environ
                  else {"status": "missing"}) for name in sorted(set(environment))}
    return {"schema_version": 1,
            "status": "available" if all(v["status"] == "present" for v in files.values()) else "partial",
            "resources": files, "environment": env, "scope": IDENTITY_SCOPE}


def codeobject_tools(arch):
    """Resolve the same executable paths as toolchain.assemble_codeobject.

    This only resolves/hashes tools; it does not run --version or an assembler.
    """
    default = "/opt/rocm/llvm/bin/clang++"
    return {"assembler": default if os.path.exists(default) else shutil.which("clang++")}


class BuildEvidence:
    """Bounded snapshots around construction and evaluation of one candidate."""

    def __init__(self, source_path, identity_provider=None):
        self.source_path = source_path
        self.artifact_path = None
        self.identity_provider = identity_provider or unavailable_identity
        self.data = {"schema_version": 1, "loaded_code_object": "unverified",
                     "scope": "observed_source_and_build_artifact_bytes; not_gpu_load_attestation",
                     "source_before": file_identity(source_path),
                     "identity_before": self.identity_provider(), "checks": {}}

    def after_build(self, artifact_path=None):
        self.artifact_path = artifact_path
        self.data["source_after_build"] = file_identity(self.source_path)
        self.data["artifact_after_build"] = file_identity(artifact_path)
        self.data["identity_after_build"] = self.identity_provider()
        checks = self.data["checks"]
        checks["source_stable_during_build"] = self._same_file(
            self.data["source_before"], self.data["source_after_build"])
        checks["artifact_present"] = self.data["artifact_after_build"]["status"] == "present"
        checks["identity_stable_during_build"] = self.data["identity_before"] == self.data["identity_after_build"]
        return all(checks.values())

    @staticmethod
    def _same_file(before, after):
        return before.get("status") == "present" and before == after

    def finish(self):
        self.data["source_after_evaluation"] = file_identity(self.source_path)
        self.data["artifact_after_evaluation"] = file_identity(self.artifact_path)
        self.data["identity_after_evaluation"] = self.identity_provider()
        checks = self.data["checks"]
        checks["source_stable_during_evaluation"] = self._same_file(
            self.data["source_before"], self.data["source_after_evaluation"])
        checks["artifact_stable_during_evaluation"] = self._same_file(
            self.data.get("artifact_after_build", {}), self.data["artifact_after_evaluation"])
        checks["identity_stable_during_evaluation"] = self.data["identity_before"] == self.data["identity_after_evaluation"]
        self.data["status"] = "consistent" if all(checks.values()) else "invalid"
        return self.data
