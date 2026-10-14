"""CPU-only checks of identity declarations and real subprocess build plumbing."""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import client
from harness import toolchain
from harness.evaluator import CompileOnlyEvaluator, GpuTestcaseEvaluator
from harness.evidence import collect_identity, file_identity, unavailable_identity
from harness.measurement import measure_screen


SOURCE = '.amdgcn_target "amdgcn-amd-amdhsa--gfx942"\ns_endpgm\n'


def test_file_identity_tracks_bytes_paths_and_missing(tmp_path):
    source = tmp_path / "external.py"
    assert file_identity(source)["status"] == "missing"
    assert file_identity(None)["status"] == "unresolved"
    assert file_identity(tmp_path)["status"] == "not_regular"
    source.write_text("one")
    first = file_identity(source)
    stamp = source.stat()
    source.write_text("two")
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert file_identity(source)["sha256"] != first["sha256"]
    assert file_identity(source)["sha256"] == hashlib.sha256(b"two").hexdigest()
    link = tmp_path / "link"
    link.symlink_to(source)
    assert file_identity(link)["resolved_path"] == str(source)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert file_identity(fifo)["status"] == "not_regular"


def test_identity_is_explicit_and_never_records_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "must-not-be-stored")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    monkeypatch.delenv("HSA_USE_SVM", raising=False)
    result = collect_identity({"optional": tmp_path / "absent"},
                              ["OMP_NUM_THREADS", "HSA_USE_SVM"])
    assert result["status"] == "partial"
    assert result["environment"]["HSA_USE_SVM"] == {"status": "missing"}
    assert result["environment"]["OMP_NUM_THREADS"]["value"] == "2"
    assert "API_TOKEN" not in json.dumps(result)
    assert "must-not-be-stored" not in json.dumps(result)
    with pytest.raises(ValueError, match="allowlist"):
        collect_identity({}, ["API_TOKEN"])


def test_repeated_search_path_entries_do_not_change_identity(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/app/aiter:")
    once = collect_identity({}, ["PYTHONPATH"])
    monkeypatch.setenv("PYTHONPATH", "/app/aiter:/app/aiter:")
    assert collect_identity({}, ["PYTHONPATH"]) == once
    assert once["environment"]["PYTHONPATH"]["value"] == "/app/aiter:"
    monkeypatch.setenv("PYTHONPATH", "/app/aiter")
    assert collect_identity({}, ["PYTHONPATH"]) != once
    monkeypatch.setenv("PYTHONPATH", "/other:/app/aiter:")
    assert collect_identity({}, ["PYTHONPATH"]) != once
    monkeypatch.setenv("HSA_XNACK", "a:a")
    assert collect_identity({}, ["HSA_XNACK"])["environment"]["HSA_XNACK"]["value"] == "a:a"


def test_legacy_client_identity_is_optional(tmp_path):
    module = SimpleNamespace(make_evaluator=lambda ctx: (ctx.case, ctx.params))
    cl = client.Client("old/case", "old", "case", str(tmp_path), str(tmp_path), module)
    assert cl.identity() == unavailable_identity()
    assert cl.make_evaluator(params=["x=1"]) == ("case", ["x=1"])
    resource = tmp_path / "test.py"
    resource.write_text("test-version-1")
    module.identity = lambda ctx: {"resources": {"test": resource}}
    first = cl.identity()
    resource.write_text("test-version-2")
    assert cl.identity() != first
    module.identity = lambda ctx: {"credentials": "not-allowed"}
    with pytest.raises(ValueError, match="must declare"):
        cl.identity()




@pytest.fixture
def cpu_case(tmp_path, monkeypatch):
    """Exercise gfx942 build plumbing with a harmless clang++ stand-in."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    compiler = ("#!" + sys.executable + "\n"
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "output = pathlib.Path(args[args.index('-o') + 1])\n"
                "source = next(pathlib.Path(a) for a in args if a.endswith('.s'))\n"
                "output.write_bytes(b'fake-stage:' + source.read_bytes())\n")
    path = tools_dir / "clang++"
    path.write_text(compiler)
    path.chmod(0o755)
    assemble = toolchain.assemble_codeobject

    def assemble_with_fake_compiler(s_path, out_path, gfx_target=None):
        return assemble(s_path, out_path, gfx_target, clangpp=str(path))

    monkeypatch.setattr(toolchain, "assemble_codeobject", assemble_with_fake_compiler)
    exe = tmp_path / "gemm.exe"
    exe.write_text("#!" + sys.executable + "\nimport sys\n"
                   "print('#TEST PASSED' if 'dump_result=1' in sys.argv else 'time: 0.01 gflops: 1000')\n")
    exe.chmod(0o755)
    source = tmp_path / "candidate.s"
    source.write_text(SOURCE)
    evaluator = GpuTestcaseEvaluator(str(tmp_path))
    return source, evaluator


def test_every_call_builds_fresh_and_records_exact_source_artifact(cpu_case):
    source, evaluator = cpu_case
    artifact = Path(evaluator.co_path)
    artifact.write_bytes(b"old-stale-object")
    first = evaluator.evaluate(str(source))
    assert first.compiled and first.correct is True and first.tflops == 1
    evidence = first.detail["build_evidence"]
    assert evidence["status"] == "consistent"
    assert evidence["loaded_code_object"] == "unverified"
    assert evidence["source_before"]["sha256"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert evidence["artifact_after_build"] == evidence["artifact_after_evaluation"]
    assert evidence["artifact_after_build"]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert evidence["build"]["strategy"] == "fresh_output_atomic_replace"
    first_stage = evidence["build"]["staged_artifact"]["path"]
    assert not Path(first_stage).exists()
    second = evaluator.evaluate(str(source))
    assert second.detail["build_evidence"]["build"]["staged_artifact"]["path"] != first_stage
    assert second.detail["build_evidence"]["artifact_after_build"] == evidence["artifact_after_build"]
    assert not list(source.parent.glob(".testft-build-*"))


def test_noop_toolchain_cannot_reuse_old_artifact(cpu_case, monkeypatch):
    source, evaluator = cpu_case
    artifact = Path(evaluator.co_path)
    artifact.write_bytes(b"stale")
    monkeypatch.setattr(toolchain, "assemble_codeobject", lambda *a: str(artifact))
    monkeypatch.setattr(evaluator, "check_correctness", lambda p: pytest.fail("must not launch stale object"))
    result = evaluator.evaluate(str(source))
    assert result.compiled is False
    assert result.detail["build_evidence"]["status"] == "invalid"
    assert artifact.read_bytes() == b"stale"
    assert not list(source.parent.glob(".testft-build-*"))


def test_source_changes_during_build_stop_before_client_launch(cpu_case, monkeypatch):
    source, evaluator = cpu_case
    assemble = toolchain.assemble_codeobject

    def mutate(*args):
        output = assemble(*args)
        source.write_text(SOURCE + "; changed\n")
        return output

    monkeypatch.setattr(toolchain, "assemble_codeobject", mutate)
    monkeypatch.setattr(evaluator, "check_correctness", lambda p: pytest.fail("changed source must stop"))
    result = evaluator.evaluate(str(source))
    assert result.compiled is True and result.correct is None and result.tflops is None
    assert result.detail["build_evidence"]["checks"]["source_stable_during_build"] is False


@pytest.mark.parametrize("changed", ["artifact", "source", "resource", "environment"])
def test_evaluation_drift_retains_raw_report_but_invalidates_sample(cpu_case, monkeypatch, changed):
    source, evaluator = cpu_case
    resource = source.parent / "test-helper.py"
    resource.write_text("version1")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    evaluator.identity_provider = lambda: collect_identity({"helper": resource}, ["OMP_NUM_THREADS"])

    def measure(path):
        if changed == "artifact":
            Path(evaluator.co_path).write_bytes(b"replaced")
        elif changed == "source":
            source.write_text(SOURCE + "; rewritten\n")
        elif changed == "resource":
            resource.write_text("version2")
        else:
            monkeypatch.setenv("OMP_NUM_THREADS", "3")
        return 0.01, 1000

    monkeypatch.setattr(evaluator, "measure_perf", measure)
    batch = measure_screen(evaluator, str(source), 2)
    assert batch.status == "measurement_invalid"
    assert len(batch.samples) == 1
    result = batch.samples[0]["result"]
    assert result["correct"] is None and result["tflops"] is None
    assert result["detail"]["reported_result"] == {"correct": True, "time_us": 10, "tflops": 1}
    assert result["detail"]["build_evidence"]["status"] == "invalid"


def test_numerical_failure_keeps_evidence_and_stops_perf(cpu_case, monkeypatch):
    source, evaluator = cpu_case
    monkeypatch.setattr(evaluator, "check_correctness", lambda path: False)
    monkeypatch.setattr(evaluator, "measure_perf", lambda path: pytest.fail("failed check must stop perf"))
    result = evaluator.evaluate(str(source))
    assert result.correct is False
    assert result.detail["build_evidence"]["status"] == "consistent"


def test_missing_declared_resource_is_explicit_but_not_a_numerical_failure(cpu_case):
    source, evaluator = cpu_case
    evaluator.identity_provider = lambda: collect_identity({"optional": source.parent / "missing"})
    result = evaluator.evaluate(str(source))
    assert result.correct is True
    evidence = result.detail["build_evidence"]
    assert evidence["identity_before"]["status"] == "partial"
    assert evidence["status"] == "consistent"


def test_runtime_exception_preserves_build_evidence(cpu_case, monkeypatch):
    source, evaluator = cpu_case

    def fail(path):
        raise RuntimeError("fake executable failed")

    monkeypatch.setattr(evaluator, "measure_perf", fail)
    result = evaluator.evaluate(str(source))
    assert result.compiled is True and result.tflops is None
    assert result.detail["error"] == "fake executable failed"
    assert result.detail["build_evidence"]["artifact_after_build"]["status"] == "present"


def test_compile_only_keeps_identity_without_claiming_gpu_execution(tmp_path):
    source = tmp_path / "source.s"
    source.write_text(SOURCE)
    artifact = tmp_path / "source.o"

    def assemble(path):
        artifact.write_bytes(b"fake-object")
        return str(artifact)

    result = CompileOnlyEvaluator(SimpleNamespace(assemble=assemble)).evaluate(str(source))
    assert result.compiled is True and result.correct is None
    assert result.detail["build_evidence"]["loaded_code_object"] == "unverified"
