"""Tuning-client loader (client/README.md): spec resolution, per-client
tune_out, the bundled poc_kl client and the CLI bridges that require it."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import client as cl
from harness.evaluator import GpuTestcaseEvaluator

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEMM = os.path.join(REPO, "client", "poc_kl", "fp8_blockscale_gemm")
SEED = os.path.join(GEMM, "shader", "fp8gemm_blockscase_32mx1_32nx4.s")


class TestResolve(unittest.TestCase):
    def test_poc_kl_case(self):
        c = cl.resolve("poc_kl/fp8_blockscale_gemm")
        self.assertEqual((c.name, c.case), ("poc_kl", "fp8_blockscale_gemm"))
        self.assertEqual(c.case_dir, GEMM)
        self.assertEqual(c.out_dir, os.path.join(REPO, "client", "poc_kl", "tune_out"))

    def test_spec_forms(self):
        for spec in ("client/poc_kl/fp8_blockscale_gemm", GEMM, "poc_kl/fp8_blockscale_gemm/"):
            self.assertEqual(cl.resolve(spec).spec, "poc_kl/fp8_blockscale_gemm")

    def test_errors(self):
        for spec in ("nope", "../tools", "", "poc_kl/fp8_blockscale_gemm/../../.."):
            with self.assertRaises(ValueError):
                cl.resolve(spec)

    def test_list(self):
        self.assertIn("poc_kl", cl.list_clients())

    def test_nearest_client_py_wins(self):
        with tempfile.TemporaryDirectory() as root:
            for d in ("proj/a", "proj/b"):
                os.makedirs(os.path.join(root, d))
            with open(os.path.join(root, "proj", "client.py"), "w") as f:
                f.write("def make_evaluator(ctx):\n    return ('proj', ctx.case)\n")
            with open(os.path.join(root, "proj", "b", "client.py"), "w") as f:
                f.write("def make_evaluator(ctx):\n    return ('b', ctx.case, ctx.params)\n")
            with mock.patch.object(cl, "CLIENT_ROOT", root):
                a = cl.resolve("proj/a")
                b = cl.resolve("proj/b")
                self.assertEqual((a.name, a.case), ("proj", "a"))
                self.assertEqual(a.make_evaluator(), ("proj", "a"))
                self.assertEqual((b.name, b.case), ("proj/b", ""))
                self.assertEqual(b.make_evaluator(params=["x=1"]), ("b", "", ["x=1"]))
                self.assertEqual(b.out_dir, os.path.join(root, "proj", "b", "tune_out"))
                self.assertEqual(cl.list_clients(), ["proj", "proj/b"])

    def test_missing_make_evaluator(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "bad"))
            with open(os.path.join(root, "bad", "client.py"), "w") as f:
                f.write("X = 1\n")
            with mock.patch.object(cl, "CLIENT_ROOT", root):
                with self.assertRaises(ValueError):
                    cl.resolve("bad")


class TestPocKl(unittest.TestCase):
    def test_gemm_evaluator(self):
        c = cl.resolve("poc_kl/fp8_blockscale_gemm")
        ev = c.make_evaluator(seed_src=open(SEED).read(), params=["m=256", "k=512"],
                              loop=7, kernel="kern")
        self.assertIsInstance(ev, GpuTestcaseEvaluator)
        self.assertEqual(ev.exe_path, os.path.join(GEMM, "gemm.exe"))
        self.assertEqual(ev.co_path, os.path.join(GEMM, "gemm.co"))
        self.assertEqual(ev.exe_params, ["m=256", "k=512"])
        self.assertEqual((ev.total_loop, ev.kernel_name), (7, "kern"))
        self.assertIsNotNone(ev.target)
        self.assertIn("gemm.exe", c.describe(params=["m=256"]))

    def test_client_root_is_not_a_case(self):
        with self.assertRaises(ValueError):
            cl.resolve("poc_kl").make_evaluator()



class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable] + list(args), cwd=REPO,
                              capture_output=True, text=True)

    def test_resolve_cli(self):
        r = self._run("-m", "client", "resolve", "poc_kl/fp8_blockscale_gemm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["out_dir"],
                         os.path.join(REPO, "client", "poc_kl", "tune_out"))
        self.assertEqual(self._run("-m", "client", "resolve", "nope").returncode, 2)

    def test_agent_session_eval_needs_client(self):
        r = self._run("tools/agent_session.py", "eval", SEED, "--layout", "{}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--client", r.stderr)

    def test_agent_session_propose_needs_no_client(self):
        r = self._run("tools/agent_session.py", "propose", SEED, "--layout", "{}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["legal"])

    def test_summarize_default_out_next_to_results(self):
        with tempfile.TemporaryDirectory() as d:
            ts = os.path.join(d, "tune_out", "transcripts")
            os.makedirs(ts)
            res = os.path.join(ts, "tune-x.results.jsonl")
            with open(res, "w") as f:
                f.write(json.dumps({"correct": True, "tflops": 1.0, "baseline": 1.0}) + "\n")
            r = self._run("tools/tune_summarize.py", "--results", res)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(os.path.join(
                d, "tune_out", "tune_result", "tune-x.summary.json")))


if __name__ == "__main__":
    unittest.main()
