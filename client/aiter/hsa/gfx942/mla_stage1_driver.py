"""Pinned gfx942 nonpersistent MLA decode stage1 via a unique dispatch tuple.

The upstream low-level ABI has no symbol argument. A reviewed unique catalog
match binds the symbol and the evaluator separately requires its loader path.
Only useful stage1 output is exposed; unused split-LSE/output scratch is not a
returned value for this split=1 adapter. No high-level MLA suite is claimed.
"""
import ast
import copy
import csv
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import subprocess

UPSTREAM=Path(__file__).resolve().parents[2]/'upstream'
TEST_SHA256='e11878a43c039839c86760b690fd8fb4b89ee9fd465bb5f0c646c4d3b69760b6'
FIELDS=('qType','kvType','Gqa','ps','qSeqLen','prefill','causal','lse')
STAGE1_REVISION = '2abf8aaa44f9d81c88d6153024b21e6931c7f906'
STAGE1_SOURCES = {
    'csrc/py_itfs_cu/asm_mla.cu': '25ca8ce94684f9652c3afdcefc917b52b495d534cf6ad1296418d61fd5e9daaf',
    'aiter/ops/attention.py': '34c28453a371972a6d378cd876a0662702ac87e2ed2c425dfec16ad764729677',
    'aiter/jit/core.py': '91255bfdc97876be9305943fa42c6129cd5673437e9b7c1b093a6ba29a08e813',
    'aiter/jit/optCompilerConfig.json': 'c9690c1371d19659c1145725ec7fc9894e84c32a2522aef2bccc3d776248d29a',
    'aiter/jit/utils/torch_guard.py': '037c74413847fae1a4ad7cf087c583c5786ff82b08250799a67e68b31f04e32c',
    'hsa/codegen.py': '3b87889093896f79511e91d181fb4905a7c6ad3bdea184aa5e529b3c9ee6a120',
    'csrc/include/aiter_ctypes_error.h': 'b8f2a9e49730525b93ad2829f6294aac2c4e9a523abc403257f5cb0c0d699ff8',
}
STAGE1_METADATA = {
    'hsa/gfx1250/mla/mla_asm.csv': 'eb9435307ce842470ae09cde4259c3b498cfbbd5ca1ce04d0c46b9f632968412',
    'hsa/gfx1250/mla_dsl/mla_dsl.csv': '2ba253bd337c566eda3d1ca21395e84f1549e0be62bb220db13952a26fd4d89e',
    'hsa/gfx942/mla/mla_asm.csv': '827f805442143024bdb166662d62304308b50b569f3630fb141ad3338d7c72af',
    'hsa/gfx950/mla/mla_asm.csv': 'e72f763b7f0916ddfde34e3c4487dda2f214b36350f39cf7ad35258b73737d42',
}
METADATA_ROOT = Path(__file__).with_name('mla_codegen_metadata')
_STAGE1_CALL = None
_STAGE1_EVIDENCE = None


def stage1_metadata(directory):
    """Restore real same-revision schema inputs outside the sparse submodule.

    The unchanged codegen unions columns from all architectures, then filters
    emitted rows using AITER_GPU_ARCHS. No other-architecture code is loaded.
    """
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != STAGE1_REVISION:
        raise ValueError('reviewed MLA metadata revision changed')
    contents = {'hsa/codegen.py': (UPSTREAM/'hsa/codegen.py').read_bytes()}
    if hashlib.sha256(contents['hsa/codegen.py']).hexdigest() != STAGE1_SOURCES['hsa/codegen.py']:
        raise ValueError('reviewed MLA codegen changed')
    for name, expected in STAGE1_METADATA.items():
        # These raw files were exported with git show at STAGE1_REVISION.
        # A shared sparse clone's alternates may be outside the container;
        # runtime never repairs its object database or invents missing fields.
        data = (METADATA_ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('reviewed MLA metadata changed: '+name)
        if (UPSTREAM/name).is_file() and (UPSTREAM/name).read_bytes() != data:
            raise ValueError('MLA metadata checkout differs from pinned object: '+name)
        contents[name] = data
    for name, data in contents.items():
        target = Path(directory)/name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('staged MLA metadata changed: '+name)
        else:
            with target.open('xb') as stream:
                stream.write(data)
    return contents


def stage1_build_recipe(core):
    for name, expected in STAGE1_SOURCES.items():
        if hashlib.sha256((UPSTREAM/name).read_bytes()).hexdigest() != expected:
            raise ValueError('reviewed MLA binding source changed: '+name)
    if core.get_gfx() != 'gfx942' or os.environ.get('AITER_GPU_ARCHS') != 'gfx942':
        raise ValueError('MLA binding requires gfx942-only code generation')
    digest = hashlib.sha256(json.dumps(dict(STAGE1_METADATA, codegen=STAGE1_SOURCES['hsa/codegen.py']), sort_keys=True).encode()).hexdigest()
    metadata = Path(core.get_user_jit_dir())/('fack-mla-metadata-'+digest[:20])
    stage1_metadata(metadata)
    args = copy.deepcopy(core.get_args_of_build('module_mla_asm'))
    if args['srcs'] != [str(UPSTREAM/'csrc/py_itfs_cu/asm_mla.cu')]:
        raise ValueError('unexpected upstream MLA source recipe')
    original = [str(UPSTREAM/'hsa/codegen.py')+' -m '+module+' --output_dir {}' for module in ('mla','mla_dsl')]
    if args['blob_gen_cmd'] != original:
        raise ValueError('unexpected upstream MLA metadata recipe')
    args['blob_gen_cmd'] = [command.replace(str(UPSTREAM/'hsa/codegen.py'), str(metadata/'hsa/codegen.py')) for command in original]
    keys = ('srcs','flags_extra_cc','flags_extra_hip','blob_gen_cmd','extra_include',
            'extra_ldflags','verbose','is_python_module','is_standalone',
            'torch_exclude','third_party','flags_extra_hip_per_source')
    recipe = {key:args[key] for key in keys}
    evidence = {'upstream_commit':STAGE1_REVISION, 'source_sha256':dict(STAGE1_SOURCES),
                'metadata_sha256':dict(STAGE1_METADATA), 'metadata_directory':str(metadata),
                'build_recipe':recipe, 'emitted_architectures':['gfx942'],
                'entrypoint':'mla_decode_stage1_asm_fwd', 'ffi':'pinned upstream compile_ops ctypes',
                'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    name = 'module_fack_mla_stage1_gfx942_'+hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()[:20]
    return name, recipe, evidence


def stage1_declaration(namespace, name):
    path = UPSTREAM/'aiter/ops/attention.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != STAGE1_SOURCES['aiter/ops/attention.py']:
        raise ValueError('reviewed MLA declaration changed')
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node,ast.FunctionDef) and node.name=='mla_decode_stage1_asm_fwd']
    if len(nodes)!=1:
        raise ValueError('MLA declaration is not unique')
    node=nodes[0]
    if (len(node.body)!=1 or not isinstance(node.body[0],ast.Expr)
            or not isinstance(node.body[0].value,ast.Constant) or node.body[0].value.value is not Ellipsis):
        raise ValueError('MLA declaration has an unexpected implementation')
    node.decorator_list=[]
    node.name=name
    scope=dict(namespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),scope)
    return scope[name]


def stage1_binding():
    global _STAGE1_CALL, _STAGE1_EVIDENCE
    if _STAGE1_CALL is not None:
        return _STAGE1_CALL
    from aiter.jit import core
    from aiter.ops import attention
    name, recipe, evidence = stage1_build_recipe(core)
    library = Path(core.get_user_jit_dir())/(name+core.JIT_LIB_EXT)
    receipt=library.with_suffix('.binding.json')
    if not library.exists():
        core.build_module(name,**recipe)
        receipt.write_text(json.dumps(dict(evidence,module=name,library=str(library),
            library_sha256=hashlib.sha256(library.read_bytes()).hexdigest()),indent=2)+'\n')
    record=json.loads(receipt.read_text())
    if (record['library_sha256']!=hashlib.sha256(library.read_bytes()).hexdigest()
            or any(record[key]!=value for key,value in evidence.items())):
        raise ValueError('MLA binding library or recipe changed')
    function=stage1_declaration(vars(attention),name+'_call')
    _STAGE1_CALL=core.compile_ops(name,fc_name='mla_decode_stage1_asm_fwd',ffi_type='ctypes')(function)
    _STAGE1_EVIDENCE=dict(record,signature=str(inspect.signature(function)))
    print('[FACK] MLA stage1 binding '+json.dumps(_STAGE1_EVIDENCE,sort_keys=True),flush=True)
    return _STAGE1_CALL
# Native split=1 output formats, reviewed against the pinned gfx942 objects.
# The legacy QH8/QH16 BF16 kernels always store FP32. Newer variants pack
# BF16 in their split=1 branch, independently of the input dtype.
# KernelArgs.s_kv_split is at 0x90; QH128 and QH16/qseq8 load it into
# s67 and use s_cmp_le_u32 s67, 1 before the BF16 packing/stores to ptr_R
# (kernarg 0x00). The legacy FP32 epilogues have no such conversion branch.
SPLIT1_OUTPUT_FORMAT={
    'mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co':'bf16',
    'mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co':'fp32',
    'mla_a16w16_qh16_m16x4_n16x1_coex0_mask1.co':'bf16',
    'mla_a16w16_qh16_m32x4_n16x1_coex0_mask1.co':'bf16',
    'mla_a8w8_qh16_qseqlen1_gqaratio16.co':'bf16',
    'mla_a8w8_qh16_qseqlen2_gqaratio16.co':'bf16',
    'mla_a8w8_qh64_qseqlen4_gqaratio16.co':'bf16',
    'mla_a8w8_qh128_m32x4_n16x2_msk1.co':'bf16',
    'mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co':'fp32',
    'mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co':'bf16',
}
SPLIT1_NULL_OUTPUT_POINTER={
    'MLA_A16W16_1TG_4W_32mx1_16nx1_Coex0_Msk1_QH16.co',
    'MLA_A16W16_1TG_4W_64mx1_16nx1_Coex0_Msk1_QH16.co',
}


def split1_output_format(row):
    name=row['co_name']
    if name in SPLIT1_NULL_OUTPUT_POINTER:
        # These objects load ptr_RP at kernarg 0xf0 for BF16 stores. The
        # pinned nonpersistent C++ wrapper sets that pointer to nullptr.
        raise ValueError('MLA split=1 native output uses ptr_RP, which the pinned nonpersistent wrapper leaves null')
    if name not in SPLIT1_OUTPUT_FORMAT:
        raise ValueError('MLA split=1 native output ABI has not been reviewed')
    return SPLIT1_OUTPUT_FORMAT[name]


def selected_row(inputs,symbol):
    catalog=UPSTREAM/'hsa/gfx942/mla/mla_asm.csv'
    rows=list(csv.DictReader(catalog.open()))
    selected=[r for r in rows if all(str(inputs['dispatch'][k])==r[k] for k in FIELDS)]
    if len(selected)!=1 or selected[0]['knl_name']!=symbol:
        raise ValueError('MLA dispatch tuple does not uniquely bind the selected symbol')
    row=selected[0]
    if row['ps']!='0' or row['prefill']!='0' or row['lse']!='0' or row['qType']!=row['kvType'] or row['qType'] not in ('bf16','fp8'):
        raise ValueError('only reviewed nonpersistent same-dtype decode paths are supported')
    heads,qseq=int(row['Gqa']),inputs['qseq']
    effective_qseq=0 if heads in (32,128) or (heads==64 and qseq>1) else qseq
    if effective_qseq!=int(row['qSeqLen']) or (heads==64 and qseq==1):
        raise ValueError('actual shape does not reach the reviewed C++ dispatch branch')
    split1_output_format(row)
    return row


def native_page_size(inputs):
    # The reviewed gfx942 native loops force log2(page_size) to zero and
    # consume one KV token per page index. Require an explicit contract so
    # old page16 workload certificates cannot silently follow this repair.
    if type(inputs.get('page_size')) is not int or inputs['page_size'] != 1:
        raise ValueError('gfx942 MLA adapter requires explicit inputs.page_size=1; rebind the workload contract')
    return 1


def native_kv_tail_padding(inputs, row):
    required = 32 if row['co_name'] == 'mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co' else 0
    declared = inputs.get('kv_tail_padding_bytes')
    if type(declared) is not int or declared != required:
        raise ValueError('gfx942 MLA adapter requires explicit inputs.kv_tail_padding_bytes={}'.format(required))
    return required


def padded_kv_storage(kv, padding_bytes):
    """Keep the logical tensor contiguous while owning an initialized tail."""
    import torch
    logical_bytes = kv.numel() * kv.element_size()
    if padding_bytes:
        if padding_bytes % kv.element_size():
            raise ValueError('KV padding is not an integral element count')
        storage = torch.empty(kv.numel() + padding_bytes // kv.element_size(),
                              dtype=kv.dtype, device=kv.device)
        storage[:kv.numel()].copy_(kv.reshape(-1))
        storage[kv.numel():].zero_()
        kv = storage[:kv.numel()].view(kv.shape)
    receipt = {'logical_shape': list(kv.shape), 'logical_bytes': logical_bytes,
               'byte_strides': [s * kv.element_size() for s in kv.stride()],
               'storage_bytes': kv.untyped_storage().nbytes(),
               'storage_offset_bytes': kv.storage_offset() * kv.element_size(),
               'padding_bytes': padding_bytes, 'padding_initialization': 'zero' if padding_bytes else None,
               'data_ptr': hex(kv.data_ptr()), 'storage_data_ptr': hex(kv.untyped_storage().data_ptr())}
    if receipt['storage_offset_bytes'] != 0 or receipt['storage_bytes'] != logical_bytes + padding_bytes:
        raise ValueError('unexpected KV storage extent')
    return kv, receipt


def prepare(inputs,symbol,seed):
    import torch
    import aiter
    row=selected_row(inputs,symbol)
    page=native_page_size(inputs)
    padding=native_kv_tail_padding(inputs,row)
    stage1_call=stage1_binding()
    batch,length=inputs['m'],inputs['n']
    heads,qseq=int(row['Gqa']),inputs['qseq']
    dimension=576;value_dimension=512
    if inputs['k']!=dimension or length%page or length<qseq or batch<1:
        raise ValueError('unsupported MLA shape')
    dtype=torch.bfloat16 if row['qType']=='bf16' else aiter.dtypes.fp8
    generator=torch.Generator(device='cuda').manual_seed(seed)
    q=torch.randn((batch*qseq,heads,dimension),generator=generator,device='cuda').to(dtype)
    kv=torch.randn((batch,length,dimension),generator=generator,device='cuda')
    # Nonzero signed channel means prevent an all-zero output from hiding under
    # absolute tolerance when attention averages many random values.
    offsets=torch.where(torch.arange(value_dimension,device='cuda')%2==0,0.5,-0.5)
    kv[:,:,:value_dimension]+=offsets
    kv=kv.to(dtype)
    kv,storage_receipt=padded_kv_storage(kv,padding)
    print('[FACK] MLA KV storage '+json.dumps(storage_receipt,sort_keys=True),flush=True)
    kv_buffer=kv.reshape(batch*length//page,page,1,dimension)
    qo=torch.arange(0,(batch+1)*qseq,qseq,device='cuda',dtype=torch.int32)
    pages_per_sequence=length//page
    kvptr=torch.arange(0,(batch+1)*pages_per_sequence,pages_per_sequence,device='cuda',dtype=torch.int32)
    indices=torch.arange(batch*pages_per_sequence,device='cuda',dtype=torch.int32)
    tails=torch.full((batch,),page,device='cuda',dtype=torch.int32)
    splitptr=torch.arange(batch+1,device='cuda',dtype=torch.int32)
    out_dtype=torch.bfloat16 if split1_output_format(row)=='bf16' else torch.float32
    out=torch.empty((batch*qseq,heads,value_dimension),device='cuda',dtype=out_dtype)
    split_data=out.view(batch*qseq,1,heads,value_dimension)
    scratch_lse=torch.empty((batch*qseq,1,heads,1),device='cuda',dtype=torch.float32)
    scratch_output=torch.empty_like(out,dtype=torch.bfloat16)
    scale=dimension**-0.5
    qscale=torch.ones(1,device='cuda',dtype=torch.float32) if dtype==aiter.dtypes.fp8 else None
    kvscale=torch.ones(1,device='cuda',dtype=torch.float32) if dtype==aiter.dtypes.fp8 else None
    qf=q.float().reshape(batch,qseq*heads,dimension)
    kvf=kv.float()
    logits=torch.bmm(qf,kvf.transpose(1,2))*scale
    logits=logits.reshape(batch,qseq,heads,length)
    mask=torch.arange(length,device='cuda')[None,:] > (length-qseq+torch.arange(qseq,device='cuda')[:,None])
    logits.masked_fill_(mask[None,:,None,:],-float('inf'))
    probability=logits.reshape(batch,qseq*heads,length).softmax(-1)
    reference=torch.bmm(probability,kvf[:,:,:value_dimension]).reshape_as(out).to(out_dtype)
    def run():
        stage1_call(q,kv_buffer,qo,kvptr,indices,tails,splitptr,None,None,None,
            qseq,page,1,scale,split_data,scratch_lse,scratch_output,None,qscale,kvscale,None,1,0,None,0,True)
        return out
    return {'run':run,'outputs':[out],'reference':[reference],
            'flops':2*batch*qseq*heads*length*(dimension+value_dimension),
            '_raw':(q,kv,qo,scale),'_dispatch':row,'_kv_storage':storage_receipt}


def validate(inputs,symbol,seed):
    import torch
    from aiter.test_common import run_perftest
    path=UPSTREAM/'op_tests/test_mla.py'
    source=path.read_bytes()
    if hashlib.sha256(source).hexdigest()!=TEST_SHA256:
        raise ValueError('reviewed upstream MLA reference changed')
    tree=ast.parse(source,filename=str(path))
    body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('ref_masked_attention','torch_mla_extend')]
    if len(body)!=2:raise ValueError('MLA reference definitions absent')
    ns={'torch':torch};exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),ns)
    case=prepare(inputs,symbol,seed+100003)
    q,kv,qo,scale=case['_raw']
    batch,length=inputs['m'],inputs['n']
    indptr=torch.arange(0,(batch+1)*length,length,device='cuda',dtype=torch.int32)
    token_indices=torch.arange(batch*length,device='cuda',dtype=torch.int32)
    with torch.device('cuda'):
        # The upstream reference builds a -inf causal bias in query.dtype.
        # Decode the already-quantized values to FP32 so FP8's lack of infinity
        # cannot turn its mask into NaNs; the mathematical inputs stay exact.
        reference,_=ns['torch_mla_extend'](q.float(),kv.float().reshape(batch*length,1,576),qo,indptr,token_indices,
                                         scale,512,64,case['outputs'][0].dtype,is_causal=True)
    output,us=run_perftest(case['run'],num_iters=101,num_warmup=2)
    if not math.isfinite(float(us)) or us<=0:raise ValueError('invalid MLA stage1 profiler time')
    checks=[]
    for ref in (reference,case['reference'][0]):
        finite=bool(torch.isfinite(output).all().item() and torch.isfinite(ref).all().item())
        passed=finite and torch.allclose(output.float(),ref.float(),atol=0.005,rtol=0.02)
        checks.append({'passed':bool(passed),'max_abs_error':float((output.float()-ref.float()).abs().max().item()) if finite else None})
        if not passed:raise ValueError('MLA full-output validation failed: '+str(checks))
    return {'correct':True,'test':'op_tests/test_mla.py','test_sha256':TEST_SHA256,
            'stage1_binding':dict(_STAGE1_EVIDENCE),
            'kv_storage':case['_kv_storage'],
            'functions':['torch_mla_extend','ref_masked_attention','mla_decode_stage1_asm_fwd'],
            'scope':'gfx942 low-level stage1, unique fixed dispatch tuple, split=1; no high-level/full MLA suite',
            'symbol':symbol,'dispatch':case['_dispatch'],'checks':checks,
            'rows':[{'data_init':'signed_random_channel_mean','scale_init':'unit_tensor','asm us':float(us),'asm err':0}],
            'timing':'upstream run_perftest profiler'}
