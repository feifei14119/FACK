.text
.global _ZN5testft12gemm_styleE
.p2align 8
.type _ZN5testft12gemm_styleE,@function

_ZN5testft12gemm_styleE:
  s_load_dword s25, s[0:1], 0xe0
  s_waitcnt lgkmcnt(0)
  s_cmp_eq_u32 s53, 0
  s_cbranch_scc0 label_005F
  s_branch label_00B0

label_005F:
  v_lshrrev_b32_e32 v1, 10, v0
  s_add_u32 s31, s26, 63

label_0338:
  buffer_load_dword v32, s[8:11], 0 offen lds
  s_add_u32 m0, 0x100, s51
  s_waitcnt vmcnt(40)
  s_barrier
  ds_read_b128 a[0:3], v31
  s_waitcnt vmcnt(20) lgkmcnt(0)
  v_mfma_f32_16x16x16_bf16 v[44:47], a[96:97], a[0:1], v[44:47]
  s_nop 0
  v_mfma_f32_16x16x16_bf16 v[44:47], a[98:99], a[2:3], v[44:47]
  s_cmp_gt_u32 s32, s31
  s_cbranch_scc0 label_0338

label_00B0:
  ds_write_b128 v31, v[44:47]
  s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)
  s_endpgm

.rodata
.p2align 6
.amdhsa_kernel _ZN5testft12gemm_styleE
    .amdhsa_group_segment_fixed_size 65536
    .amdhsa_next_free_vgpr 512
    .amdhsa_next_free_sgpr 64
    .amdhsa_accum_offset 256
.end_amdhsa_kernel

.amdgpu_metadata
---
amdhsa.kernels:
  - .name: _ZN5testft12gemm_styleE
    .symbol: _ZN5testft12gemm_styleE.kd
    .vgpr_count: 512
    .sgpr_count: 64
    .wavefront_size: 64
...
.end_amdgpu_metadata
