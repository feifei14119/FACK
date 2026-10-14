.text
.global cold_kernel
.p2align 8
.type cold_kernel,@function

cold_kernel:
  v_mfma_f32_16x16x16_bf16 v[44:47], a[96:97], a[64:65], v[44:47]
  v_mfma_f32_16x16x16_bf16 v[44:47], a[98:99], a[66:67], v[44:47]
  v_mfma_f32_16x16x16_bf16 v[44:47], a[100:101], a[68:69], v[44:47]
  v_mfma_f32_16x16x16_bf16 v[44:47], a[102:103], a[70:71], v[44:47]
  v_mfma_f32_16x16x16_bf16 v[44:47], a[104:105], a[72:73], v[44:47]
  ds_read_b128 a[0:3], v31
  ds_read_b128 a[4:7], v32
  ds_read_b128 a[8:11], v33
  ds_read_b128 a[12:15], v34
  s_endpgm
