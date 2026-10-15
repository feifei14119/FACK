"""CPU-only MLA binding checks; no aiter import, compiler, or GPU execution."""
import ast
import copy
import hashlib
import inspect
from types import SimpleNamespace

import pytest

from client.aiter.hsa.gfx942 import mla_stage1_driver as driver


@pytest.mark.parametrize('page',[None,0,16,True])
def test_native_page_contract_rejects_old_or_implicit_paging(page):
    with pytest.raises(ValueError,match='explicit inputs.page_size=1'):
        driver.native_page_size({} if page is None else {'page_size':page})


def test_native_page_contract_covers_every_logical_token():
    page=driver.native_page_size({'page_size':1})
    batch,length,dim=384,1024,576
    assert batch*length//page == 393216
    assert length//page == 1024
    assert page*dim == 576  # FP8 page byte stride, BF16 is twice this.


@pytest.mark.parametrize('declared',[None,0,16,True,64])
def test_qh8_kv_tail_requires_exact_explicit_storage_padding(declared):
    row={'co_name':'mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co'}
    with pytest.raises(ValueError,match='kv_tail_padding_bytes=32'):
        driver.native_kv_tail_padding({} if declared is None else {'kv_tail_padding_bytes':declared},row)
    assert driver.native_kv_tail_padding({'kv_tail_padding_bytes':32},row)==32


def test_qh128_does_not_inherit_qh8_padding():
    row={'co_name':'mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co'}
    assert driver.native_kv_tail_padding({'kv_tail_padding_bytes':0},row)==0
    with pytest.raises(ValueError,match='kv_tail_padding_bytes=0'):
        driver.native_kv_tail_padding({'kv_tail_padding_bytes':32},row)


@pytest.mark.parametrize('dtype_name',['uint8','float8_e4m3fnuz'])
def test_kv_padding_preserves_all_logical_bytes_and_owns_zero_tail(dtype_name):
    torch=pytest.importorskip('torch')
    source=torch.arange(1152,dtype=torch.int32).remainder(256).to(torch.uint8).view(getattr(torch,dtype_name)).reshape(2,1,576)
    state=torch.random.get_rng_state().clone()
    padded,receipt=driver.padded_kv_storage(source,32)
    assert torch.equal(padded.view(torch.uint8),source.view(torch.uint8)) and padded.shape==source.shape
    assert padded.stride()==source.stride() and padded.is_contiguous()
    assert torch.equal(torch.random.get_rng_state(),state)
    assert receipt['storage_bytes']==1184 and receipt['storage_offset_bytes']==0
    whole=torch.empty(0,dtype=torch.uint8).set_(padded.untyped_storage(),0,(1184,),(1,))
    assert not torch.count_nonzero(whole[1152:]).item()
    del source
    assert torch.equal(padded.view(torch.uint8).reshape(-1),torch.arange(1152,dtype=torch.int32).remainder(256).to(torch.uint8))


def test_zero_padding_retains_original_bf16_allocation():
    torch=pytest.importorskip('torch')
    source=torch.zeros((2,1,576),dtype=torch.bfloat16)
    result,receipt=driver.padded_kv_storage(source,0)
    assert result is source and receipt['storage_bytes']==2304


@pytest.fixture
def recipe_context(tmp_path, monkeypatch):
    monkeypatch.setenv('AITER_GPU_ARCHS', 'gfx942')
    args = {'srcs':[str(driver.UPSTREAM/'csrc/py_itfs_cu/asm_mla.cu')],
        'blob_gen_cmd':[str(driver.UPSTREAM/'hsa/codegen.py')+' -m '+m+' --output_dir {}' for m in ('mla','mla_dsl')],
        'flags_extra_cc':['-DORIGINAL_FLAG'], 'flags_extra_hip':[], 'extra_include':[],
        'extra_ldflags':None, 'verbose':False, 'is_python_module':True,
        'is_standalone':False, 'torch_exclude':True, 'third_party':[], 'flags_extra_hip_per_source':{}}
    core = SimpleNamespace(get_gfx=lambda:'gfx942', get_args_of_build=lambda _:args,
                           get_user_jit_dir=lambda:str(tmp_path))
    return args, core


def test_real_pinned_sparse_metadata_restored_outside_upstream(tmp_path):
    contents = driver.stage1_metadata(tmp_path)
    assert set(contents) == set(driver.STAGE1_METADATA) | {'hsa/codegen.py'}
    for name, expected in driver.STAGE1_METADATA.items():
        assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest() == expected
    assert (tmp_path/'hsa/codegen.py').read_bytes() == (driver.UPSTREAM/'hsa/codegen.py').read_bytes()


def test_changed_staged_metadata_is_rejected_without_overwrite(tmp_path):
    driver.stage1_metadata(tmp_path)
    target = tmp_path/'hsa/gfx942/mla/mla_asm.csv'
    target.write_bytes(b'changed target dispatch')
    with pytest.raises(ValueError, match='staged MLA metadata changed'):
        driver.stage1_metadata(tmp_path)
    assert target.read_bytes() == b'changed target dispatch'


def test_missing_packaged_metadata_has_no_runtime_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, 'METADATA_ROOT', tmp_path/'missing-package')
    with pytest.raises(FileNotFoundError):
        driver.stage1_metadata(tmp_path/'stage')


def test_changed_packaged_metadata_is_rejected(tmp_path, monkeypatch):
    package=tmp_path/'package'
    for name in driver.STAGE1_METADATA:
        path=package/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((driver.METADATA_ROOT/name).read_bytes())
    (package/next(iter(driver.STAGE1_METADATA))).write_bytes(b'invented columns')
    monkeypatch.setattr(driver, 'METADATA_ROOT', package)
    with pytest.raises(ValueError,match='metadata changed'):
        driver.stage1_metadata(tmp_path/'stage')


def test_recipe_preserves_whole_cpp_and_all_flags(recipe_context):
    shared, core = recipe_context
    before = copy.deepcopy(shared)
    name, recipe, evidence = driver.stage1_build_recipe(core)
    assert shared == before
    assert recipe['srcs'] == before['srcs']
    assert {k:v for k,v in recipe.items() if k!='blob_gen_cmd'} == {k:v for k,v in before.items() if k!='blob_gen_cmd'}
    assert [x.split(' -m ',1)[1] for x in recipe['blob_gen_cmd']] == ['mla --output_dir {}','mla_dsl --output_dir {}']
    assert evidence['metadata_sha256'] == driver.STAGE1_METADATA
    assert evidence['emitted_architectures'] == ['gfx942']
    assert name.startswith('module_fack_mla_stage1_gfx942_')


def test_recipe_rejects_extra_architecture(recipe_context, monkeypatch):
    _, core = recipe_context
    monkeypatch.setenv('AITER_GPU_ARCHS', 'gfx942;gfx950')
    with pytest.raises(ValueError, match='gfx942-only'):
        driver.stage1_build_recipe(core)


def test_recipe_rejects_changed_cpp_or_codegen_recipe(recipe_context):
    shared, core = recipe_context
    shared['blob_gen_cmd'] = ['unreviewed generator']
    with pytest.raises(ValueError, match='metadata recipe'):
        driver.stage1_build_recipe(core)


def test_original_26_argument_signature_is_preserved_without_importing_aiter():
    class TensorAnnotation:
        def __or__(self, other):
            return ('union', self, other)
    tensor = TensorAnnotation()
    function = driver.stage1_declaration({'torch':SimpleNamespace(Tensor=tensor)}, 'unique_mla_call')
    signature = inspect.signature(function)
    original = next(n for n in ast.parse((driver.UPSTREAM/'aiter/ops/attention.py').read_text()).body
                    if isinstance(n,ast.FunctionDef) and n.name=='mla_decode_stage1_asm_fwd')
    assert len(signature.parameters) == 26
    assert list(signature.parameters) == [a.arg for a in original.args.args]
    assert signature.parameters['Q'].annotation is tensor
    assert signature.parameters['cp_world_size'].default == 1
    assert signature.parameters['cp_rank'].default == 0
    assert signature.parameters['causal'].default is True
    assert signature.parameters['g_kv_indptr'].default is None
    assert function.__name__ == 'unique_mla_call'


def test_changed_pinned_commit_is_rejected(tmp_path, monkeypatch):
    real = driver.subprocess.check_output
    def altered(argv, **kwargs):
        return 'wrong-revision\n' if argv[-2:] == ['rev-parse','HEAD'] else real(argv,**kwargs)
    monkeypatch.setattr(driver.subprocess, 'check_output', altered)
    with pytest.raises(ValueError, match='revision changed'):
        driver.stage1_metadata(tmp_path)
