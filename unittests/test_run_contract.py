"""Declared client identity is frozen and checked around each charged call."""
from pathlib import Path

from harness.evidence import collect_identity
from unittests.test_tuning_run import cli, passed


def test_cli_freezes_declared_resource_and_refuses_changed_resource(cli, tmp_path):
    invoke, seed, cl, fake, _ = cli
    resource = tmp_path / "test-program"
    resource.write_text("version-one")
    cl.identity = lambda **kw: collect_identity({"test": str(resource)})
    initialized = invoke("init", str(seed), "--client", cl.spec)
    frozen = initialized["manifest"]["evaluation_contract"]["client_identity"]
    assert frozen["resources"]["test"]["status"] == "present"
    resource.write_text("version-two")
    result = invoke("eval", initialized["run_dir"], "original", expected=2)
    assert result["error"]["code"] == "contract_mismatch"
    assert not fake.calls


def test_mid_call_resource_change_preserves_raw_result_and_invalidates_batch(cli, tmp_path):
    invoke, seed, cl, _, _ = cli
    resource = tmp_path / "test-program"
    resource.write_text("version-one")
    cl.identity = lambda **kw: collect_identity({"test": str(resource)})
    directory = invoke("init", str(seed), "--client", cl.spec)["run_dir"]
    class ChangesResource:
        def evaluate(self, path, with_counters=False):
            resource.write_text("version-two")
            return passed(123)
    cl.make_evaluator.return_value = ChangesResource()
    batch = invoke("eval", directory, "original")
    assert batch["status"] == "measurement_invalid"
    state = invoke("status", directory)["state"]
    assert state["used"]["eval_calls"] == 1
    assert next(iter(state["attempts"].values()))["result"]["tflops"] == 123
