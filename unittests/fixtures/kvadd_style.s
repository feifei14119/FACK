.amdhsa_code_object_version 6

.text
.protected vadd_kernel
.globl vadd_kernel
.p2align 8
.type vadd_kernel,@function

// kernarg layout
.set s_karg, 0
.set s_width, 2
.set s_height, 3
.set v_tid_x, 0
.set v_a, 2
.set v_b, 3
.set v_c, 4

vadd_kernel:
	s_load_b64 s[s_karg:s_karg+1], s[0:1], 0x18    // load base ptr
	s_waitcnt lgkmcnt(0)
	v_and_b32_e32 v[v_tid_x], 0x3ff, v0
	v_cmp_gt_i32_e32 vcc_lo, s[s_width], v[v_tid_x]
	s_and_saveexec_b32 s[s_height], vcc_lo
	s_cbranch_execz .label_exit
	global_load_b32 v[v_a], v[2:3], off
	global_load_b32 v[v_b], v[2:3], off
	s_waitcnt vmcnt(0)
	v_add_f32_e32 v[v_c], v[v_a], v[v_b]
	global_store_b32 v[2:3], v[v_c], off

.label_exit:
	s_endpgm
