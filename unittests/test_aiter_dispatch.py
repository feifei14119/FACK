"""Dispatch planning, immutable workload contracts and public-API observation.

CPU only: no aiter import, JIT, assembler or GPU.
"""
import ast
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

from client.aiter import client as adapter, common, dispatch as d, runner

SYMBOL = "_ZN5aiter41I8gemm_bf16_perTokenI8_BpreShuffle_32x128E"
CO = "i8gemm/I8gemm_bf16_perTokenI8_BpreShuffle_32x128.co"
ROW = dict(gfx="gfx942", cu_num="80", M="192", N="1280", K="1024", q_dtype_w="torch.int8",
           libtype="asm", splitK="1", kernelName=SYMBOL, kernelId="1", us="6.79", errRatio="0.0")
BLOCK_SYMBOL = "_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E"
BLOCK_CO = "fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co"
BLOCK_ROW = dict(gfx="gfx942", cu_num="80", M="192", N="1280", K="1024",
                 libtype="asm", splitK="1", kernelName=BLOCK_SYMBOL, errRatio="0.0")


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def tree(tmp_path):
    upstream = tmp_path / "upstream"
    write_csv(upstream / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv", [ROW])
    write_csv(upstream / "hsa/gfx942/i8gemm/kernels.csv", [
        dict(knl_name=SYMBOL, co_name=Path(CO).name, bpreshuffle="1", splitK="1")])
    (upstream / "hsa/gfx942" / CO).write_bytes(b"original code object")
    for name in d.RESOLVER_FILES:
        path = upstream / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# pinned resolver fixture\n")
    return upstream


def scan(tree, **kwargs):
    return d.build_plan(tree, "gfx942", 80, ["a8w8"], environ={}, **kwargs)


def export(tree, tmp_path):
    plan, snapshots = scan(tree)
    out = tmp_path / "out"
    with patch.object(d, "REPO", tmp_path):
        d.export_plan(plan, snapshots, out, tree)
    manifest = out / plan["tasks"][0]["manifest"]
    return plan, manifest, json.loads(manifest.read_text())


def test_multishape_identity_and_arch_cu_filter_without_mutation(tree):
    source = tree / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv"
    write_csv(source, [ROW, dict(ROW, N="1536"), dict(ROW, cu_num="304"), dict(ROW, gfx="gfx950")])
    before = source.read_bytes()
    plan, snapshots = scan(tree)
    refs = plan["references"]
    assert len(refs) == 2
    assert len(set(r["workload_id"] for r in refs)) == 2
    assert len(plan["co_to_workloads"][CO]) == 2
    assert all(r["status"] == "ready_for_validation" for r in refs)
    assert "304" not in snapshots["a8w8"]
    assert source.read_bytes() == before
    assert "aiter" not in __import__("sys").modules


def test_conflict_blocks_family_instead_of_selecting_fastest(tree):
    model = tree / "aiter/configs/model_configs/model_a8w8_bpreshuffle_tuned_gemm.csv"
    write_csv(model, [dict(ROW, us="1.0", splitK="4")])
    before = model.read_bytes()
    plan, _ = scan(tree)
    assert plan["families"]["a8w8"]["conflicting_keys"] == 1
    assert {r["status"] for r in plan["references"]} == {"config_conflict"}
    assert model.read_bytes() == before
    # An explicitly chosen table replaces, rather than adds to, defaults.
    base = tree / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv"
    plan, _ = scan(tree, overrides={"a8w8": str(base)})
    assert len(plan["references"]) == 1
    assert plan["references"][0]["status"] == "ready_for_validation"


def test_environment_override_and_unknown_legacy_arch(tree):
    path = tree / "legacy.csv"
    rows = [{k: v for k, v in row.items() if k != "gfx"} for row in [ROW, dict(ROW, cu_num="81")]]
    write_csv(path, rows)
    plan, _ = d.build_plan(tree, "gfx942", 80, ["a8w8"], environ={d.FAMILIES["a8w8"][1]: str(path)})
    assert len(plan["references"]) == 1
    assert plan["families"]["a8w8"]["source_mode"] == "environment_override"
    assert plan["families"]["a8w8"]["excluded"]["unknown_legacy_gfx"] == 1


@pytest.mark.parametrize("updates,status", [
    ({"libtype": "hipblaslt"}, "other_backend"),
    ({"libtype": "flydsl"}, "other_backend"),
    ({"kernelName": "unknown"}, "unmapped"),
    ({"splitK": "8"}, "unsupported_adapter"),
    ({"N": "128"}, "unsupported_adapter"),
    ({"errRatio": "0.1825"}, "unsupported_adapter"),
    ({"errRatio": "nan"}, "unsupported_adapter"),
    ({"q_dtype_w": "torch.float8_e4m3fnuz"}, "unsupported_adapter"),
])
def test_backend_and_unsupported_contracts_are_visible(tree, updates, status):
    write_csv(tree / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv", [dict(ROW, **updates)])
    plan, _ = scan(tree)
    assert plan["references"][0]["status"] == status
    if status == "other_backend":
        assert plan["co_to_workloads"] == {}


def test_missing_ambiguous_and_escaping_catalogs(tree):
    original = tree / "hsa/gfx942/i8gemm/kernels.csv"
    other = original.with_name("alias.csv")
    other.write_bytes(original.read_bytes())
    assert scan(tree)[0]["references"][0]["status"] == "ambiguous_catalog"
    other.unlink()
    (tree / "hsa/gfx942" / CO).unlink()
    assert scan(tree)[0]["references"][0]["status"] == "missing_co"
    write_csv(original, [dict(knl_name=SYMBOL, co_name="../../outside.co")])
    with pytest.raises(ValueError, match="relative path"):
        scan(tree)


def test_export_load_shape_freeze_and_snapshot_identity(tree, tmp_path):
    plan, manifest, data = export(tree, tmp_path)
    with patch.object(common, "UPSTREAM", tree):
        assert common.load_manifest(manifest, "gfx942")[0] == data
        ctx = SimpleNamespace(case="hsa/gfx942", loop=2, kernel=None,
                              params=["--manifest", str(manifest), "--m", "193"])
        with pytest.raises(ValueError, match="cannot override"):
            common.options(ctx)
        ctx.params[-1] = "192"
        assert common.options(ctx)[1]["inputs"]["m"] == 192
    assert "--alpha" in plan["tasks"][0]["commands"]["compare"]
    assert "dispatch-" + plan["tasks"][0]["task_id"] in plan["tasks"][0]["commands"]["tune_init"]
    (manifest.parent / data["dispatch"]["snapshot"]).write_text("tampered\n")
    with pytest.raises(ValueError, match="snapshot changed"):
        d.validate_binding(data, manifest, tree)


@pytest.mark.parametrize("field,value", [("symbol", "other"), ("inputs", {"m": 999}),
                                         ("atol", 999), ("validation_hook", False)])
def test_manifest_drift_rejected(tree, tmp_path, field, value):
    _, manifest, data = export(tree, tmp_path)
    data[field] = value
    with pytest.raises(ValueError):
        d.validate_binding(data, manifest, tree)


def test_resolver_original_and_path_drift_rejected(tree, tmp_path):
    _, manifest, data = export(tree, tmp_path)
    code = tree / d.RESOLVER_FILES[0]
    old = code.read_bytes()
    code.write_bytes(b"changed resolver")
    with pytest.raises(ValueError, match="resolver changed"):
        d.validate_binding(data, manifest, tree)
    code.write_bytes(old)
    changed = copy.deepcopy(data)
    changed["dispatch"]["snapshot"] = "../outside.csv"
    changed["dispatch"]["binding_id"] = d.binding_id(changed["dispatch"])
    with pytest.raises(ValueError, match="relative path"):
        d.validate_binding(changed, manifest, tree)
    (tree / "hsa/gfx942" / CO).write_bytes(b"changed co")
    with pytest.raises(ValueError, match="original .co changed"):
        d.validate_binding(data, manifest, tree)


def test_runtime_env_and_cu_guard(tree, tmp_path):
    _, manifest, data = export(tree, tmp_path)
    req = dict(data, dispatch_snapshot=str(manifest.parent / data["dispatch"]["snapshot"]))
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="CU count"):
            runner.configure_dispatch(req, SimpleNamespace(multi_processor_count=304))
        assert d.FAMILIES["a8w8"][1] not in os.environ
        runner.configure_dispatch(req, SimpleNamespace(multi_processor_count=80))
        assert os.environ[d.FAMILIES["a8w8"][1]] == req["dispatch_snapshot"]


def load_driver():
    spec = importlib.util.spec_from_file_location("dispatch_driver_test", common.HERE / "hsa/gfx942/dispatch_driver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("selected,split_k,passes", [(SYMBOL, 1, True), ("other", 1, False), (SYMBOL, 8, False)])
def test_normal_entrypoint_observer_does_not_force_selection(selected, split_k, passes):
    driver = load_driver()
    calls = []
    out = SimpleNamespace(fill_=lambda value: None)
    def low(*args):
        calls.append(args)
        return out
    module = SimpleNamespace(gemm_a8w8_asm=low)
    def normal(a, b, sa, sb, bias, dtype):
        return module.gemm_a8w8_asm(a, b, sa, sb, out, selected, bias, splitK=split_k)
    module.gemm_a8w8_ASM = normal
    inputs = {"family": "i8", "splitK": 1, "bpreshuffle": True}
    binding = {"symbol": SYMBOL, "inputs": inputs}
    extra = {key: object() for key in ("a", "packed", "sa", "sb", "bias")}
    args = (module, inputs, extra, binding, SimpleNamespace(bfloat16="bf16"))
    if passes:
        result, observed = driver.normal_call(*args)
        assert result is out and observed[0]["symbol"] == SYMBOL
        assert calls[0][-1] == 1
    else:
        with pytest.raises(ValueError, match="different kernel"):
            driver.normal_call(*args)
        assert calls == []  # mismatching selection rejected before launch
    assert module.gemm_a8w8_asm is low


def test_moe_retains_full_stage_contract_and_mla_requires_workload(tree):
    row = dict(cu_num="80", token="4", model_dim="2304", inter_dim="1536", expert="8", topk="2",
               act_type="ActivationType.Gelu", dtype="torch.bfloat16", q_dtype_a="fp8", q_dtype_w="fp8",
               q_type="QuantType.per_Token", use_g1u1="1", doweight_stage1="1", run_1stage="0", ksplit="0",
               kernelName1=SYMBOL, kernelName2="moe_ck_second_stage", _tag="")
    write_csv(tree / "aiter/configs/tuned_fmoe.csv", [row])
    write_csv(tree / "hsa/gfx942/mla/mla_asm.csv", [dict(knl_name="mla_stage1", co_name="mla.co", Gqa="128")])
    plan, _ = d.build_plan(tree, "gfx942", 80, ["moe"], environ={})
    assert len(plan["references"]) == 2
    assert {r["stage"] for r in plan["references"]} == {"kernelName1", "kernelName2"}
    assert plan["references"][0]["row"] == row
    assert all(r["status"] != "ready_for_validation" for r in plan["references"])
    mla = next(r for r in plan["unreferenced_co"] if r["co"] == "mla/mla.co")
    assert "batch/KV" in mla["reason"]


def comparison_fixture(path, task, root, candidate_us=9.0, candidate_hash="c" * 64):
    report = {"status": "completed", "records": [], "device": {"arch": "gfx942", "cu": 80},
              "contract": {"client_identity": {"environment": {}, "resources": {
                  "manifest": {"sha256": d.sha(root / task["manifest"])}}}},
              "assemblies": {"reference": {"sha256": "b" * 64}, "candidate": {"sha256": candidate_hash}},
              "policy": {"method": "paired_sign_v1", "confirm_pairs": 6, "final_pairs": 6,
                         "min_gain": 0.01, "alpha": 0.05, "max_confirmations": 1}}
    for trial in range(6):
        for side, us in (("reference", 10.0), ("candidate", candidate_us)):
            result = {"compiled": True, "correct": True, "time_us": us,
                      "detail": {"build_evidence": {"status": "consistent"}, "runner": {
                          "loader_observed": True, "dispatch_check": {"correct": True, "workload_id": task["task_id"]},
                          "op_test": {"correct": True, "rows": [{"asm err": 0, "asm us": us,
                                       "data_init": "signed_random", "scale_init": "per_token"}]}}}}
            report["records"].append({"trial": trial, "side": side, "result": result,
                "times_us": {"hip_graph": us, "op_test:signed_random/per_token": us}})
    path.write_text(json.dumps(report))
    return path


def test_cross_shape_coverage_cannot_hide_missing_or_regressed_workload(tree, tmp_path):
    write_csv(tree / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv", [ROW, dict(ROW, N="1536")])
    plan, manifest, _ = export(tree, tmp_path)
    first, second = plan["tasks"]
    root = manifest.parent
    p1 = comparison_fixture(tmp_path / "first.json", first, root)
    p2 = comparison_fixture(tmp_path / "second.json", second, root)
    check = lambda paths: d.assess_coverage(root / "plan.json", CO, paths, 0.01)
    assert check([p1])["counts"] == {"pass": 1, "pending": 1}
    assert check([p1])["status"] == "not_accepted"
    assert check([p1, p2])["status"] == "all_referenced_workloads_pass"
    comparison_fixture(p2, second, root, candidate_us=11.0)
    assert check([p1, p2])["counts"] == {"pass": 1, "regression": 1}
    comparison_fixture(p2, second, root, candidate_hash="d" * 64)
    with pytest.raises(ValueError, match="same frozen assemblies"):
        check([p1, p2])
    with pytest.raises(ValueError, match="duplicate"):
        check([p1, p1])


def test_unsupported_reference_prevents_global_co_acceptance(tree, tmp_path):
    write_csv(tree / "aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv", [ROW, dict(ROW, N="128", splitK="8")])
    plan, manifest, _ = export(tree, tmp_path)
    report = comparison_fixture(tmp_path / "result.json", plan["tasks"][0], manifest.parent)
    result = d.assess_coverage(manifest.parent / "plan.json", CO, [report], 0.01)
    assert result["status"] == "not_accepted"
    assert result["counts"] == {"pass": 1, "unsupported": 1}


def test_bf16_contract_is_not_coerced_to_adapter_defaults():
    row = dict(M="192", N="128", K="1024", splitK="1", dtype="torch.bfloat16", outdtype="torch.bfloat16",
               bias="False", scaleAB="False", bpreshuffle="True", kernelName="bf16gemm_fp32bf16_test")
    match = {"attributes": {"tn": "1", "bPreshuffle": "1"}}
    assert d.adapter_inputs("bf16", row, match)["bpreshuffle"] is True
    for updates in ({"outdtype": "torch.float32"}, {"bias": "True"}, {"scaleAB": "True"}, {"splitK": "4"}):
        with pytest.raises(ValueError):
            d.adapter_inputs("bf16", dict(row, **updates), match)


@pytest.mark.parametrize("mode", ["pass", "missing_check", "wrong_cu"])
def test_evaluator_copies_snapshot_and_requires_dispatch_evidence(tree, tmp_path, mode):
    _, manifest, data = export(tree, tmp_path)
    source = tmp_path / "seed.s"
    source.write_text('.amdgcn_target "amdgcn-amd-amdhsa--gfx942:xnack-"\n'
                      '.amdhsa_code_object_version 5\n.amdhsa_kernel ' + SYMBOL + '\n.end_amdhsa_kernel\n')
    ev = adapter.AiterEvaluator.__new__(adapter.AiterEvaluator)
    ev.ctx = SimpleNamespace(out_dir=str(tmp_path / "eval"))
    ev.opts = SimpleNamespace(timeout=10, seed=123, warmup=1, iters=2, samples=2, python="python3",
                              output_dir=None, manifest=str(manifest))
    ev.config = data
    ev.driver = common.HERE / "hsa/gfx942/dispatch_driver.py"
    frozen = manifest.parent / data["dispatch"]["snapshot"]
    frozen_bytes = frozen.read_bytes()

    def process(argv, log, timeout, env=None, cwd=None):
        if "request.json" in str(argv):
            request = json.loads(Path(argv[-2]).read_text())
            snapshot = Path(request["dispatch_snapshot"])
            assert snapshot != frozen and snapshot.read_bytes() == frozen_bytes
            assert tmp_path / "eval" in snapshot.parents
            assert "AITER_CONFIG_GEMM_A8W8_BPRESHUFFLE" not in env  # runner installs the declared copy
            report = {"schema_version": 1, "arch": "gfx942", "symbol": SYMBOL,
                      "co_sha256": request["co_sha256"], "loader_observed": True, "correct": True,
                      "op_test": {"correct": True}, "time_us": 2.0, "flops": 100.0}
            if mode != "missing_check":
                report["dispatch_check"] = {"correct": True, "workload_id": data["dispatch"]["workload_id"],
                                            "cu_num": 304 if mode == "wrong_cu" else 80}
            Path(argv[-1]).write_text(json.dumps(report))
        else:
            Path(argv[-1]).write_bytes(b"assembled")

    with patch.object(adapter, "UPSTREAM", tree), \
            patch.object(adapter, "identity", return_value={"resources": {"manifest": manifest, "seed": source}}), \
            patch.object(adapter.toolchain, "_llvm_tool", side_effect=lambda name: name), \
            patch.object(adapter, "run_process", side_effect=process), \
            patch.dict(os.environ, {"AITER_CONFIG_GEMM_A8W8_BPRESHUFFLE": "/do/not/use.csv"}):
        result = ev.evaluate(str(source))
    assert result.compiled
    if mode == "pass":
        assert result.correct is True and result.time_us == 2.0
    else:
        assert result.correct is None and result.time_us is None
        assert "normal dispatch" in result.detail["error"]
    assert frozen.read_bytes() == frozen_bytes


@pytest.fixture
def blockscale_tree(tree):
    write_csv(tree / "aiter/configs/a8w8_blockscale_bpreshuffle_tuned_gemm.csv", [BLOCK_ROW])
    write_csv(tree / "hsa/gfx942/fp8gemm_blockscale/kernels.csv", [
        dict(knl_name=BLOCK_SYMBOL, co_name=Path(BLOCK_CO).name, tile_m="32", tile_n="128",
             bpreshuffle="1", splitK="1")])
    (tree / "hsa/gfx942" / BLOCK_CO).write_bytes(b"blockscale original")
    for name in d.BLOCKSCALE_UPSTREAM_FILES:
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# pinned blockscale validation fixture\n")
    return tree


def blockscale_export(tree, tmp_path):
    plan, snapshots = d.build_plan(tree, "gfx942", 80, ["blockscale_preshuffle"], environ={})
    out = tmp_path / "blockscale-out"
    with patch.object(d, "REPO", tmp_path):
        d.export_plan(plan, snapshots, out, tree)
    manifest = out / plan["tasks"][0]["manifest"]
    return plan, manifest, json.loads(manifest.read_text())


def test_blockscale_plan_freezes_full_input_and_validation_contract(blockscale_tree, tmp_path):
    tree = blockscale_tree
    config = tree / "aiter/configs/a8w8_blockscale_bpreshuffle_tuned_gemm.csv"
    write_csv(config, [BLOCK_ROW, dict(BLOCK_ROW, M="193"), dict(BLOCK_ROW, M="64", splitK="8")])
    before = config.read_bytes()
    plan, manifest, data = blockscale_export(tree, tmp_path)
    assert config.read_bytes() == before
    assert len(plan["tasks"]) == 2 and len(plan["co_to_workloads"][BLOCK_CO]) == 3
    assert plan["counts"] == {"ready_for_validation": 2, "unsupported_adapter": 1}
    assert data["inputs"] == dict(m=192, n=1280, k=1024, family="blockscale", splitK=1,
        bpreshuffle=True, dtype="torch.float8_e4m3fnuz", outdtype="torch.bfloat16", bias=None,
        quantization="blockscale", scale_dtype="torch.float32", a_scale_block=[1, 128],
        b_scale_block=[128, 128], a_scale_shape=[192, 8], b_scale_shape=[10, 8],
        a_scale_layout="transpose_contiguous_view", b_scale_layout="row_major",
        weight_layout=[16, 16], a_row_padding=0)
    assert data["dispatch"]["entrypoint"] == "aiter.ops.gemm_op_a8w8.gemm_a8w8_blockscale_bpreshuffle"
    assert set(data["dispatch"]["adapter_sha256"]) == set(d.BLOCKSCALE_ADAPTER_FILES)
    assert set(data["dispatch"]["validation_sha256"]) == set(d.BLOCKSCALE_UPSTREAM_FILES)
    assert set(data["upstream_resources"]) == set(d.RESOLVER_FILES + d.BLOCKSCALE_UPSTREAM_FILES)
    assert (manifest.parent / data["resources"]["blockscale_driver"]).resolve() == common.HERE / "hsa/gfx942/driver.py"
    assert (manifest.parent / data["resources"]["blockscale_optest"]).resolve() == common.HERE / "hsa/gfx942/optest_driver.py"
    with patch.object(common, "UPSTREAM", tree):
        assert common.load_manifest(manifest, "gfx942")[0] == data
    req = dict(data, dispatch_snapshot=str(manifest.parent / data["dispatch"]["snapshot"]))
    with patch.dict(os.environ, {}, clear=True):
        runner.configure_dispatch(req, SimpleNamespace(multi_processor_count=80))
        assert os.environ[d.FAMILIES["blockscale_preshuffle"][1]] == req["dispatch_snapshot"]
        assert d.FAMILIES["a8w8"][1] not in os.environ
    assert "aiter" not in __import__("sys").modules


@pytest.mark.parametrize("row_update,attrs_update", [
    ({"splitK": "2"}, {}), ({"N": "129"}, {}), ({"K": "129"}, {}),
    ({"errRatio": "nan"}, {}), ({"errRatio": "0.01"}, {}),
    ({"kernelName": SYMBOL}, {}), ({}, {"bpreshuffle": "0"}),
    ({}, {"tile_n": "256"}), ({}, {"tile_m": "112"}), ({}, {"splitK": "0"}),
])
def test_blockscale_rejects_unreviewed_contracts(row_update, attrs_update):
    attrs = dict(tile_m="32", tile_n="128", bpreshuffle="1", splitK="1")
    attrs.update(attrs_update)
    with pytest.raises(ValueError):
        d.adapter_inputs("blockscale_preshuffle", dict(BLOCK_ROW, **row_update), {"attributes": attrs})


def test_blockscale_supported_symbols_match_existing_optest():
    from client.aiter.hsa.gfx942 import optest_driver
    symbols = set()
    for tile in (32, 48, 64, 80, 96, 128):
        symbol = "_ZN5aiter{}fp8gemm_bf16_blockscale_BpreShuffle_{}x128E".format(43 if tile == 128 else 42, tile)
        attrs = dict(tile_m=str(tile), tile_n="128", bpreshuffle="1", splitK="1")
        assert d.adapter_inputs("blockscale_preshuffle", dict(BLOCK_ROW, kernelName=symbol), {"attributes": attrs})["family"] == "blockscale"
        symbols.add(symbol)
    assert symbols == optest_driver.SYMBOLS


@pytest.mark.parametrize("changed", ["adapter", "upstream", "missing_hash", "inputs"])
def test_blockscale_fingerprint_and_declared_layout_drift_fail_closed(blockscale_tree, tmp_path, changed):
    tree = blockscale_tree
    _, manifest, data = blockscale_export(tree, tmp_path)
    if changed == "upstream":
        (tree / d.BLOCKSCALE_UPSTREAM_FILES[0]).write_text("# changed test\n")
    elif changed == "missing_hash":
        del data["dispatch"]["adapter_sha256"][d.BLOCKSCALE_ADAPTER_FILES[0]]
        data["dispatch"]["binding_id"] = d.binding_id(data["dispatch"])
    elif changed == "inputs":
        data["inputs"]["a_scale_layout"] = "row_major"
        data["dispatch"]["inputs"] = data["inputs"]
        data["dispatch"]["binding_id"] = d.binding_id(data["dispatch"])
    original_sha = d.sha
    def changed_sha(path):
        if changed == "adapter" and Path(path) == common.HERE / "hsa/gfx942/driver.py":
            return "0" * 64
        return original_sha(path)
    with patch.object(d, "sha", side_effect=changed_sha), pytest.raises(ValueError, match="blockscale"):
        d.validate_binding(data, manifest, tree)


@pytest.mark.parametrize("selected,split_k,backend,failure", [
    (BLOCK_SYMBOL, 1, "asm", None), ("other", 1, "asm", "different kernel"),
    (BLOCK_SYMBOL, 8, "asm", "different kernel"),
    (BLOCK_SYMBOL, 1, "ck", "exactly one"),
    (BLOCK_SYMBOL, 1, "asm", "launch failed"),
])
def test_blockscale_actual_public_api_observer_preserves_selection_and_zero_bias(selected, split_k, backend, failure):
    # Execute the actual upstream public function and ASM wrapper with CPU
    # doubles at the config/tensor/launch boundaries. No aiter import or JIT.
    source = ast.parse((common.UPSTREAM / "aiter/ops/gemm_op_a8w8.py").read_text())
    names = {"gemm_a8w8_blockscale_bpreshuffle", "gemm_a8w8_blockscale_bpreshuffle_asm"}
    definitions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(definitions) == 2
    for node in definitions:
        node.decorator_list = []
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = compile(ast.fix_missing_locations(ast.Module(body=[future] + definitions, type_ignores=[])), "upstream-public-api.py", "exec")
    module = ModuleType("blockscale_public_api_cpu")
    fills, launches, configurations, zero_bias_calls = [], [], [], []
    out = SimpleNamespace(fill_=lambda value: fills.append(value))
    torch = SimpleNamespace(empty=lambda *a, **kw: out, bfloat16="bf16")
    extra = {key: SimpleNamespace(shape=shape, dtype="fp32", device="cuda") for key, shape in
             (("a", (192, 1024)), ("packed", (1280, 1024)), ("packed_sa", (192, 8)), ("sb", (10, 8)))}
    extra["sa"] = object()  # Raw scales must never be passed to the ASM/public API.
    extra["zero_bias"] = object()  # Timed run's buffer must not replace normal API allocation.
    zero_bias = object()
    def config(*args):
        configurations.append(args)
        return {"libtype": backend, "kernelName": selected, "splitK": split_k}
    def launch(*args):
        launches.append(args)
        if failure == "launch failed":
            raise RuntimeError("launch failed")
    def get_zero_bias(b):
        zero_bias_calls.append(b)
        return zero_bias
    module.__dict__.update(torch=torch, dtypes=SimpleNamespace(bf16="bf16", fp16="fp16", fp8_e8m0="e8m0"),
        get_gfx=lambda: "gfx942", _hip_blockscale_supported=lambda: True,
        get_CKGEMM_config=config, get_zero_bias_buf=get_zero_bias,
        AITER_CONFIGS=SimpleNamespace(AITER_CONFIG_GEMM_A8W8_BLOCKSCALE_BPRESHUFFLE_FILE="frozen.csv"),
        _gemm_a8w8_blockscale_bpreshuffle_asm=launch,
        gemm_a8w8_blockscale_bpreshuffle_ck=lambda *a, **kw: out)
    exec(code, module.__dict__)
    original = module.gemm_a8w8_blockscale_bpreshuffle_asm
    driver = load_driver()
    inputs = {"family": "blockscale", "splitK": 1, "bpreshuffle": True}
    binding = {"symbol": BLOCK_SYMBOL, "inputs": inputs}
    if failure:
        with pytest.raises((ValueError, RuntimeError), match=failure):
            driver.normal_call(module, inputs, extra, binding, torch)
    else:
        result, observed = driver.normal_call(module, inputs, extra, binding, torch)
        assert result is out and observed == [{"symbol": BLOCK_SYMBOL, "splitK": 1, "bpreshuffle": True}]
    assert configurations == [(192, 1280, 1024, "frozen.csv")]
    assert module.gemm_a8w8_blockscale_bpreshuffle_asm is original
    if failure in (None, "launch failed"):
        assert len(fills) == 1
        assert zero_bias_calls == [extra["packed"]]
        assert launches == [(extra["a"], extra["packed"], out, extra["packed_sa"], extra["sb"],
                             None, 1, BLOCK_SYMBOL, 1, zero_bias)]
    else:
        assert not launches and not zero_bias_calls and not fills


def test_blockscale_dispatch_reuses_existing_full_optest_adapter():
    driver = load_driver()
    inputs = {"family": "blockscale", "m": 192, "n": 1280, "k": 1024}
    selected = driver.adapter(inputs)
    assert selected.SYMBOL == BLOCK_SYMBOL and selected.prepare is selected._base.prepare
    case, report = object(), {"correct": True, "checks": ["ck", "ck strided x_scale", "asm", "triton"]}
    with patch.object(driver, "adapter", return_value=selected), \
            patch.object(selected, "prepare", return_value=case) as prepare, \
            patch.object(selected, "validate", return_value=report) as validate:
        assert driver.prepare(inputs, BLOCK_SYMBOL, 987) is case
        assert driver.validate(inputs, BLOCK_SYMBOL, 987) is report
        prepare.assert_called_once_with(inputs, BLOCK_SYMBOL, 987)
        validate.assert_called_once_with(inputs, BLOCK_SYMBOL, 987)
