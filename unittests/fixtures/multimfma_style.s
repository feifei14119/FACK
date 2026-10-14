.text
.global _ZN5testft15multimfma_styleE
.p2align 8
.type _ZN5testft15multimfma_styleE,@function

_ZN5testft15multimfma_styleE:
  s_load_dword s25, s[0:1], 0xe0
  s_waitcnt lgkmcnt(0)
  s_cmp_eq_u32 s53, 0
  s_cbranch_scc0 label_loop
  s_branch label_done

label_loop:
  ds_read_b128 a[0:3], v31
  ds_read_b128 a[4:7], v32
  v_mfma_f32_16x16x16_bf16 v[44:47], a[96:97], a[0:1], v[44:47]
  ds_read_b64 a[8:9], v33
  v_mfma_f32_32x32x8_bf16 v[48:63], a[98:99], a[2:3], v[48:63]
  ds_read_b128 a[10:13], v34
  ds_read_b128 a[14:17], v35
  ds_read_b128 a[18:21], v36
  v_mfma_f32_16x16x16_bf16 v[44:47], a[100:101], a[4:5], v[44:47]
  s_cmp_gt_u32 s32, s31
  s_cbranch_scc0 label_loop

label_done:
  ds_write_b128 v31, v[44:47]
  s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
  s_endpgm

.rodata
.p2align 6
.amdhsa_kernel _ZN5testft15multimfma_styleE
    .amdhsa_group_segment_fixed_size 65536
    .amdhsa_next_free_vgpr 512
    .amdhsa_next_free_sgpr 64
    .amdhsa_accum_offset 256
.end_amdhsa_kernel

.amdgpu_metadata
---
amdhsa.kernels:
  - .name: _ZN5testft15multimfma_styleE
    .symbol: _ZN5testft15multimfma_styleE.kd
    .vgpr_count: 512
    .sgpr_count: 64
    .wavefront_size: 64
...
.end_amdgpu_metadata
