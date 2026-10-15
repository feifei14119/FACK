"""Selected gfx942 per-token FP8/INT8 MoE stage1 with independent full outputs.

Times the first-stage gate/up GEMM and activation only. Routing preparation and
quantization are outside timing. Stage2/fused-MoE behavior is not claimed.
"""
import hashlib
import ast
import copy
import inspect
import json
import math
from contextlib import contextmanager
from pathlib import Path

UPSTREAM=Path(__file__).resolve().parents[2]/'upstream'

STAGE1_SOURCES = {
    'csrc/py_itfs_cu/asm_moe_2stage.cu': '4f137d2b0bf1ff55a014019f9f4d47702869f2f2154bda46ced2a67270fc621a',
    'aiter/jit/core.py': '91255bfdc97876be9305943fa42c6129cd5673437e9b7c1b093a6ba29a08e813',
    'aiter/jit/optCompilerConfig.json': 'c9690c1371d19659c1145725ec7fc9894e84c32a2522aef2bccc3d776248d29a',
    'aiter/jit/utils/torch_guard.py': '037c74413847fae1a4ad7cf087c583c5786ff82b08250799a67e68b31f04e32c',
    'aiter/ops/moe_op.py': '84a856614bddcc22cbcffe5ba95554b3546fc7ef42c3b91986a9e658edf12ac4',
    'hsa/codegen.py': '3b87889093896f79511e91d181fb4905a7c6ad3bdea184aa5e529b3c9ee6a120',
    'csrc/include/aiter_ctypes_error.h': 'b8f2a9e49730525b93ad2829f6294aac2c4e9a523abc403257f5cb0c0d699ff8',
}
_STAGE1_CALL = None
_STAGE1_EVIDENCE = None


def stage1_build_recipe(core):
    """Use the pinned JIT interface with only the unchanged stage1 source."""
    for relative, expected in STAGE1_SOURCES.items():
        if hashlib.sha256((UPSTREAM / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('reviewed stage1 binding source changed: ' + relative)
    if core.get_gfx() != 'gfx942':
        raise ValueError('stage1 binding is reviewed only for gfx942')
    args = copy.deepcopy(core.get_args_of_build('module_moe_fmoe_asm'))
    source = str(UPSTREAM / 'csrc/py_itfs_cu/asm_moe_2stage.cu')
    if set(args['srcs']) != {source, str(UPSTREAM / 'csrc/py_itfs_cu/asm_fmoe.cu')}:
        raise ValueError('unexpected upstream MoE source recipe')
    command = str(UPSTREAM / 'hsa/codegen.py') + ' -m fmoe_2stages --output_dir {}'
    if args['blob_gen_cmd'].count(command) != 1 or len(args['blob_gen_cmd']) != 2:
        raise ValueError('unexpected upstream MoE code generation recipe')
    args.update(srcs=[source], blob_gen_cmd=[command], torch_exclude=True)
    keys = ('srcs', 'flags_extra_cc', 'flags_extra_hip', 'blob_gen_cmd', 'extra_include',
            'extra_ldflags', 'verbose', 'is_python_module', 'is_standalone',
            'torch_exclude', 'third_party', 'flags_extra_hip_per_source')
    recipe = {key: args[key] for key in keys}
    evidence = {'source_sha256': dict(STAGE1_SOURCES), 'build_recipe': recipe,
                'entrypoint': 'moe_stage1_g1u1', 'ffi': 'pinned upstream compile_ops ctypes',
                'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    return 'module_fack_moe_stage1_gfx942_' + digest[:20], recipe, evidence


def stage1_binding():
    global _STAGE1_CALL, _STAGE1_EVIDENCE
    if _STAGE1_CALL is not None:
        return _STAGE1_CALL
    import aiter
    from aiter.jit import core
    name, recipe, evidence = stage1_build_recipe(core)
    library = Path(core.get_user_jit_dir()) / (name + core.JIT_LIB_EXT)
    receipt = library.with_suffix('.binding.json')
    if not library.exists():
        core.build_module(name, **recipe)
        record = dict(evidence, module=name, library=str(library),
                      library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())
        receipt.write_text(json.dumps(record, indent=2) + '\n')
    record = json.loads(receipt.read_text())
    if (record['library_sha256'] != hashlib.sha256(library.read_bytes()).hexdigest()
            or any(record[key] != value for key, value in evidence.items())):
        raise ValueError('stage1 binding library or recipe changed')
    from aiter.ops import moe_op
    # The upstream torch guard intentionally hides __wrapped__ and its
    # signature. Reuse only the SHA-bound declaration, not its decorators.
    # A distinct Python op name also prevents reusing the broad module's
    # already-registered torch.ops entry.
    function = stage1_declaration(vars(moe_op), name + '_call')
    _STAGE1_CALL = core.compile_ops(name, fc_name='moe_stage1_g1u1', ffi_type='ctypes')(function)
    _STAGE1_EVIDENCE = dict(record, signature=str(inspect.signature(function)))
    print('[FACK] stage1 binding ' + json.dumps(_STAGE1_EVIDENCE, sort_keys=True), flush=True)
    return _STAGE1_CALL


def stage1_declaration(namespace, name):
    path = UPSTREAM / 'aiter/ops/moe_op.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != STAGE1_SOURCES['aiter/ops/moe_op.py']:
        raise ValueError('reviewed stage1 declaration changed')
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node, ast.FunctionDef) and node.name == 'moe_stage1_g1u1']
    if len(nodes) != 1:
        raise ValueError('stage1 declaration is not unique')
    node = nodes[0]
    if (len(node.body) != 1 or not isinstance(node.body[0], ast.Expr)
            or not isinstance(node.body[0].value, ast.Constant)
            or node.body[0].value.value is not Ellipsis):
        raise ValueError('stage1 declaration has an unexpected implementation')
    node.decorator_list = []
    node.name = name
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    scope = dict(namespace)
    exec(compile(module, str(path), 'exec'), scope)
    return scope[name]


@contextmanager
def validation_binding(aiter, replacement):
    original = aiter.moe_stage1_g1u1
    aiter.moe_stage1_g1u1 = replacement
    try:
        yield
    finally:
        aiter.moe_stage1_g1u1 = original


def prepare(inputs,symbol,seed):
    import torch
    import torch.nn.functional as F
    import aiter
    from aiter.fused_moe_bf16_asm import moe_sorting_ck
    from aiter.ops.shuffle import shuffle_weight
    m,n,k=(inputs[x] for x in ('m','n','k'))
    e,topk=4,2
    family=inputs['family'];block_m=inputs['block_m']
    if family not in ('fp8','i8') or n%128 or k%128 or m<1:
        raise ValueError('unsupported MoE stage1 shape/family')
    expected='pertokenFp8' if family=='fp8' else 'pertokenInt8'
    if expected not in symbol or 'blockscale' in symbol or 'doweight' in symbol:
        raise ValueError('MoE stage1 symbol/quantization mismatch')
    stage1 = stage1_binding()
    gen=torch.Generator(device='cuda').manual_seed(seed)
    dtype=aiter.dtypes.fp8 if family=='fp8' else torch.int8
    if family=='fp8':
        a=(torch.randn((m,k),generator=gen,device='cuda')*0.5).to(dtype)
        w1=(torch.randn((e,2*n,k),generator=gen,device='cuda')*0.5).to(dtype)
    else:
        a=torch.randint(-8,9,(m,k),generator=gen,device='cuda',dtype=dtype)
        w1=torch.randint(-8,9,(e,2*n,k),generator=gen,device='cuda',dtype=dtype)
    scale_base,scale_width=(0.5,0.5) if family=='fp8' else (0.03,0.05)
    sa=scale_base+scale_width*torch.rand((m,1),generator=gen,device='cuda')
    sw=scale_base+scale_width*torch.rand((e,2*n,1),generator=gen,device='cuda')
    topk_ids=((torch.arange(m,device='cuda')[:,None]+torch.arange(topk,device='cuda')[None,:])%e).int()
    topk_weights=0.2+torch.rand((m,topk),generator=gen,device='cuda')
    topk_weights/=topk_weights.sum(dim=1,keepdim=True)
    sorted_ids,sorted_weights,expert_ids,valid_ids,_=moe_sorting_ck(topk_ids,topk_weights,e,k,torch.bfloat16,block_size=block_m)
    w2=torch.zeros((e,k,n),device='cuda',dtype=dtype)
    packed_w1=shuffle_weight(w1,layout=(16,16))
    packed_w2=shuffle_weight(w2,layout=(16,16))
    out=torch.empty((m,topk,n),device='cuda',dtype=torch.bfloat16)
    reference=torch.empty_like(out)
    af=a.float()*sa;wf=w1.float()*sw
    for expert in range(e):
        gate_up=af@wf[expert].T
        gate,up=gate_up.split(n,dim=-1)
        value=(F.silu(gate)*up).bfloat16()
        for route in range(topk):
            mask=topk_ids[:,route]==expert
            reference[mask,route]=value[mask]
    def run():
        stage1(a,packed_w1,packed_w2,sorted_ids,expert_ids,valid_ids,out,n,symbol,block_m,
                            ksplit=0,activation=aiter.ActivationType.Silu.value,quant_type=aiter.QuantType.per_Token.value,
                            a1_scale=sa,w1_scale=sw,sorted_weights=None)
    return {'run':run,'outputs':[out],'reference':[reference],'flops':4*m*topk*n*k,
            '_raw':(a,w1,w2,topk_weights,topk_ids,sa,sw),
            '_args':(a,packed_w1,packed_w2,sorted_ids,expert_ids,valid_ids,out,topk,block_m)}


def validate(inputs,symbol,seed):
    for relative,expected in [('aiter/fused_moe.py','4d655d2243dd2bf7c78bd46f16f2cf0407f40683a64c8d6bfdddf6864b29622e'),('op_tests/test_moe_2stage.py','08c96315b33a72c56e332640b5e2a75c1e4ee94e3f6da4be1620d68cda4b90d8')]:
        if hashlib.sha256((UPSTREAM/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError('reviewed upstream MoE validation functions changed')
    import torch
    import aiter
    from aiter.fused_moe import asm_stage1,torch_moe_stage1
    from aiter.test_common import run_perftest
    case=prepare(inputs,symbol,seed+100003)
    a,w1,w2,weights,ids,sa,sw=case['_raw']
    reference=torch_moe_stage1(a,w1,w2,weights,ids,dtype=torch.bfloat16,
        activation=aiter.ActivationType.Silu,quant_type=aiter.QuantType.per_Token,a1_scale=sa,w1_scale=sw,doweight=False)
    with validation_binding(aiter, stage1_binding()):
        output,us=run_perftest(asm_stage1,*case['_args'],kernelName=symbol,ksplit=0,
            activation=aiter.ActivationType.Silu,quant_type=aiter.QuantType.per_Token,a1_scale=sa,w1_scale=sw,sorted_weights=None)
    if not math.isfinite(float(us)) or us<=0:raise ValueError('invalid stage1 profiler time')
    checks=[]
    for ref in (reference,case['reference'][0]):
        finite=bool(torch.isfinite(output).all().item() and torch.isfinite(ref).all().item())
        passed=finite and torch.allclose(output.float(),ref.float(),atol=0.05,rtol=0.02)
        checks.append({'passed':bool(passed),'max_abs_error':float((output.float()-ref.float()).abs().max().item()) if finite else None})
        if not passed:raise ValueError('MoE stage1 full-output validation failed: '+str(checks))
    return {'correct':True,'test':'op_tests/test_moe_2stage.py','functions':['asm_stage1','torch_moe_stage1'],
            'scope':'single stage1 call and reference used by upstream op_test; no full fused-MoE suite or stage2',
            'symbol':symbol,'ksplit':0,'block_m':inputs['block_m'],'topk':2,'experts':4,'checks':checks,
            'stage1_binding':_STAGE1_EVIDENCE,
            'rows':[{'data_init':'signed_random_routed','scale_init':'per_token','asm us':float(us),'asm err':0}],
            'timing':'upstream run_perftest profiler'}
