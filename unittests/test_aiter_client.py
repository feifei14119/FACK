"""CPU protocol regression tests. No aiter/torch import, LLVM or GPU execution."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from client.aiter import client as adapter
from client.aiter import common, runner


SOURCE = '''.amdgcn_target "amdgcn-amd-amdhsa--gfx942:xnack-"
.amdhsa_code_object_version 5
.amdhsa_kernel selected
.end_amdhsa_kernel
'''


class TestAiterProtocol(unittest.TestCase):
    def test_requires_seed_arch_version_and_symbol(self):
        self.assertEqual(common.source_target(SOURCE, "gfx942", "selected"), ("gfx942:xnack-", 5))
        for source, arch, symbol in ((SOURCE, "gfx1100", "selected"),
                                     (SOURCE, "gfx942", "different"),
                                     (SOURCE.replace(".amdhsa_code_object_version 5", ""), "gfx942", "selected")):
            with self.assertRaises(ValueError):
                common.source_target(source, arch, symbol)

    def test_overlay_never_replaces_original(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            (source / "op").mkdir(parents=True)
            (source / "op" / "selected.co").write_bytes(b"original")
            (source / "op" / "other.co").write_bytes(b"other")
            (source / "catalog.csv").write_text("catalog")
            dest = root / "overlay"
            adapter.overlay_tree(source, dest, Path("op/selected.co"))
            selected = dest / "op" / "selected.co"
            self.assertFalse(selected.exists())
            selected.write_bytes(b"candidate")
            self.assertFalse(selected.is_symlink())
            self.assertTrue((dest / "op" / "other.co").is_symlink())
            self.assertEqual((source / "op" / "selected.co").read_bytes(), b"original")

    def test_loader_requires_matching_symbol_and_path(self):
        with tempfile.TemporaryDirectory() as td:
            log, co = Path(td) / "run.log", Path(td) / "candidate.co"
            request = {"log_path": str(log), "co_path": str(co), "symbol": "selected"}
            for text, expected in (("#TEST PASSED", False),
                                   ("[aiter] LoadKernel: other hsaco: " + str(co), False),
                                   ("[aiter] LoadKernel: selected hsaco: /wrong.co", False),
                                   ("[aiter] LoadKernel: selected hsaco: " + str(co), True)):
                log.write_text(text)
                self.assertEqual(runner.loader_observed(request), expected)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for path in ("../outside.co", "/absolute.co"):
                with self.assertRaises(ValueError):
                    common.inside(Path(td), path)

    def test_missing_load_failure_and_artifact_change_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "hsa" / "gfx942").mkdir(parents=True)
            (root / "hsa" / "gfx942" / "selected.co").write_bytes(b"original")
            source = root / "candidate.s"
            source.write_text(SOURCE)
            ctx = SimpleNamespace(out_dir=str(root / "out"))
            ev = adapter.AiterEvaluator.__new__(adapter.AiterEvaluator)
            ev.ctx = ctx
            ev.opts = SimpleNamespace(timeout=10, seed=123, warmup=1, iters=2, samples=2, python="python3", output_dir=None)
            ev.config = {"arch": "gfx942", "symbol": "selected", "co": "selected.co", "inputs": {}}
            ev.driver = root / "driver.py"

            for mode in ("pass", "missing_load", "numerical_fail", "numerical_fail_required_validation",
                         "missing_required_validation", "artifact_change", "crash", "bad_time"):
                ev.config['validation_hook'] = mode in ('numerical_fail_required_validation','missing_required_validation')
                def fake_process(argv, log, timeout, env=None, cwd=None):
                    if "request.json" in str(argv):
                        cache = Path(env["AITER_ROOT_DIR"])
                        self.assertTrue(cache.is_absolute())
                        cache.relative_to(root / "out")
                        self.assertEqual(cache.parent, Path(env["AITER_JIT_DIR"]))
                        request = json.loads(Path(argv[-2]).read_text())
                        if mode == "crash":
                            raise RuntimeError("runner failed")
                        report = dict(schema_version=1, arch="gfx942", symbol="selected",
                                      co_sha256=request["co_sha256"], loader_observed=mode != "missing_load",
                                      correct=not mode.startswith("numerical_fail"), time_us=2.0, flops=100.0)
                        if mode == "bad_time":
                            report["time_us"] = -1
                        Path(argv[-1]).write_text(json.dumps(report))
                        if mode == "artifact_change":
                            Path(request["co_path"]).write_bytes(b"changed")
                    else:
                        Path(argv[-1]).write_bytes(b"built")

                with patch.object(adapter, "UPSTREAM", root), \
                        patch.object(adapter, "identity", return_value={"resources": {"driver": source}}), \
                        patch.object(adapter.toolchain, "_llvm_tool", side_effect=lambda name: name), \
                        patch.object(adapter, "run_process", side_effect=fake_process):
                    result = ev.evaluate(str(source))
                self.assertTrue(result.compiled)
                if mode == "pass":
                    self.assertIs(result.correct, True)
                    self.assertEqual(result.time_us, 2.0)
                else:
                    self.assertIs(result.correct, False if mode.startswith("numerical_fail") else None)
                    self.assertIsNone(result.time_us)
                    self.assertIsNone(result.tflops)


if __name__ == "__main__":
    unittest.main()
