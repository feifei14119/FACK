"""CPU checks for the isolated, pinned MoE stage1 JIT recipe."""
import copy
import hashlib
import inspect
from types import SimpleNamespace

import pytest

from client.aiter.hsa.gfx942 import moe_stage1_driver as driver


@pytest.fixture
def recipe_context(tmp_path, monkeypatch):
    source = tmp_path / 'csrc/py_itfs_cu/asm_moe_2stage.cu'
    source.parent.mkdir(parents=True)
    source.write_text('unchanged stage1 source')
    monkeypatch.setattr(driver, 'UPSTREAM', tmp_path)
    monkeypatch.setattr(driver, 'STAGE1_SOURCES', {
        str(source.relative_to(tmp_path)): hashlib.sha256(source.read_bytes()).hexdigest()})
    args = {
        'srcs': [str(source), str(source.with_name('asm_fmoe.cu'))],
        'blob_gen_cmd': [str(tmp_path / 'hsa/codegen.py') + ' -m fmoe_2stages --output_dir {}',
                         str(tmp_path / 'hsa/codegen.py') + ' -m fmoe --output_dir {}'],
        'flags_extra_cc': ['-DORIGINAL_FLAG'], 'flags_extra_hip': [], 'extra_include': [],
        'extra_ldflags': None, 'verbose': False, 'is_python_module': True,
        'is_standalone': False, 'torch_exclude': True, 'third_party': [],
        'flags_extra_hip_per_source': {},
    }
    return source, args, SimpleNamespace(get_gfx=lambda: 'gfx942', get_args_of_build=lambda _: args)


def test_stage1_recipe_preserves_upstream_configuration_and_compile_flags(recipe_context):
    source, shared, core = recipe_context
    before = copy.deepcopy(shared)
    name, recipe, evidence = driver.stage1_build_recipe(core)
    assert shared == before
    assert recipe['srcs'] == [str(source)]
    assert len(recipe['blob_gen_cmd']) == 1 and '-m fmoe_2stages ' in recipe['blob_gen_cmd'][0]
    assert recipe['flags_extra_cc'] == before['flags_extra_cc']
    assert name.startswith('module_fack_moe_stage1_gfx942_')
    assert evidence['entrypoint'] == 'moe_stage1_g1u1'


def test_stage1_recipe_rejects_modified_wrapper_before_build(recipe_context):
    source, _, core = recipe_context
    source.write_text('changed launch or argument ABI')
    with pytest.raises(ValueError, match='source changed'):
        driver.stage1_build_recipe(core)


def test_stage1_recipe_rejects_unreviewed_source_dependency(recipe_context):
    _, args, core = recipe_context
    args['srcs'].append('/unreviewed/wrapper.cu')
    with pytest.raises(ValueError, match='source recipe'):
        driver.stage1_build_recipe(core)


def test_stage1_recipe_rejects_other_architecture(recipe_context):
    _, _, core = recipe_context
    core.get_gfx = lambda: 'gfx950'
    with pytest.raises(ValueError, match='only for gfx942'):
        driver.stage1_build_recipe(core)


def test_upstream_validation_binding_is_restored_after_failure():
    original, replacement = object(), object()
    module = SimpleNamespace(moe_stage1_g1u1=original)
    with pytest.raises(RuntimeError, match='validation failed'):
        with driver.validation_binding(module, replacement):
            assert module.moe_stage1_g1u1 is replacement
            raise RuntimeError('validation failed')
    assert module.moe_stage1_g1u1 is original


def test_stage1_declaration_keeps_signature_without_executing_decorators(tmp_path, monkeypatch):
    path = tmp_path / 'aiter/ops/moe_op.py'
    path.parent.mkdir(parents=True)
    path.write_text('raise RuntimeError("unrelated module code")\n'
                    '@not_available_decorator\n'
                    'def moe_stage1_g1u1(input: Tensor, ksplit: int = 0) -> None: ...\n')
    monkeypatch.setattr(driver, 'UPSTREAM', tmp_path)
    monkeypatch.setattr(driver, 'STAGE1_SOURCES', {
        'aiter/ops/moe_op.py': hashlib.sha256(path.read_bytes()).hexdigest()})
    tensor = type('Tensor', (), {})
    function = driver.stage1_declaration({'Tensor': tensor}, 'unique_stage1_binding')
    signature = inspect.signature(function)
    assert list(signature.parameters) == ['input', 'ksplit']
    assert signature.parameters['input'].annotation is tensor
    assert signature.parameters['ksplit'].default == 0
    assert function.__name__ == 'unique_stage1_binding'


def test_stage1_declaration_does_not_import_a_changed_body(tmp_path, monkeypatch):
    path = tmp_path / 'aiter/ops/moe_op.py'
    path.parent.mkdir(parents=True)
    path.write_text('def moe_stage1_g1u1():\n    raise RuntimeError("unexpected")\n')
    monkeypatch.setattr(driver, 'UPSTREAM', tmp_path)
    monkeypatch.setattr(driver, 'STAGE1_SOURCES', {
        'aiter/ops/moe_op.py': hashlib.sha256(path.read_bytes()).hexdigest()})
    with pytest.raises(ValueError, match='unexpected implementation'):
        driver.stage1_declaration({}, 'unique_stage1_binding')
