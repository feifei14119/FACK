// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_96x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E
	.protected _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E
	.p2align 8
	.type _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E,@function
_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E:
	s_and_b32 s1, s1, 0xffff  // 002300
	s_load_dwordx2 s[16:17], s[0:1], 0x0  // 002308
	s_load_dwordx2 s[4:5], s[0:1], 0x10  // 002310
	s_load_dwordx2 s[8:9], s[0:1], 0x20  // 002318
	s_load_dwordx2 s[20:21], s[0:1], 0x30  // 002320
	s_load_dwordx2 s[24:25], s[0:1], 0x40  // 002328
	s_load_dwordx2 s[28:29], s[0:1], 0x50  // 002330
	s_load_dword s32, s[0:1], 0x60  // 002338
	s_load_dword s33, s[0:1], 0x70  // 002340
	s_load_dword s34, s[0:1], 0x80  // 002348
	s_load_dword s35, s[0:1], 0x90  // 002350
	s_load_dword s36, s[0:1], 0xa0  // 002358
	s_load_dword s37, s[0:1], 0xb0  // 002360
	s_load_dword s38, s[0:1], 0xc0  // 002368
	s_load_dword s39, s[0:1], 0xd0  // 002370
	s_load_dword s40, s[0:1], 0xe0  // 002378
	s_load_dword s41, s[0:1], 0xf0  // 002380
	v_lshrrev_b32_e32 v1, 10, v0  // 002388
	v_lshrrev_b32_e32 v2, 10, v1  // 00238c
	v_and_b32_e32 v2, 0x3ff, v2  // 002390
	v_and_b32_e32 v1, 0x3ff, v1  // 002398
	v_and_b32_e32 v0, 0x3ff, v0  // 0023a0
	v_lshrrev_b32_e32 v3, 6, v0  // 0023a8
	v_and_b32_e32 v0, 63, v0  // 0023ac
	s_mov_b32 s44, s2  // 0023b0
	s_mov_b32 s45, s3  // 0023b4
	s_waitcnt lgkmcnt(0)  // 0023b8
	v_readfirstlane_b32 s47, v3  // 0023bc
	s_mov_b32 s6, 0x80000000  // 0023c0
	s_mov_b32 s10, 0x80000000  // 0023c8
	s_mov_b32 s22, 0x80000000  // 0023d0
	s_mov_b32 s26, 0x80000000  // 0023d8
	s_mov_b32 s30, 0x80000000  // 0023e0
	s_mov_b32 s7, 0x20000  // 0023e8
	s_mov_b32 s11, 0x20000  // 0023f0
	s_mov_b32 s23, 0x20000  // 0023f8
	s_mov_b32 s27, 0x20000  // 002400
	s_mov_b32 s31, 0x20000  // 002408
	s_and_b32 s5, s5, 0xffff  // 002410
	s_and_b32 s9, s9, 0xffff  // 002418
	s_and_b32 s21, s21, 0xffff  // 002420
	s_and_b32 s25, s25, 0xffff  // 002428
	s_and_b32 s29, s29, 0xffff  // 002430
	s_or_b32 s5, s5, 0x40000  // 002438
	s_or_b32 s9, s9, 0x40000  // 002440
	s_or_b32 s21, s21, 0x40000  // 002448
	s_or_b32 s25, s25, 0x40000  // 002450
	s_or_b32 s29, s29, 0x40000  // 002458
	s_mov_b32 s61, s44  // 002460
	s_mov_b32 s62, s38  // 002464
	v_cvt_f32_u32_e32 v4, s62  // 002468
	s_sub_i32 s50, 0, s62  // 00246c
	v_rcp_iflag_f32_e32 v4, v4  // 002470
	s_nop 0  // 002474
	v_mul_f32_e32 v4, 0x4f7ffffe, v4  // 002478
	v_cvt_u32_f32_e32 v4, v4  // 002480
	v_mul_lo_u32 v5, s50, v4  // 002484
	v_mul_hi_u32 v5, v4, v5  // 00248c
	v_add_u32_e32 v4, v4, v5  // 002494
	v_mul_hi_u32 v4, s61, v4  // 002498
	v_mul_lo_u32 v5, v4, s62  // 0024a0
	v_sub_u32_e32 v7, s61, v5  // 0024a8
	v_add_u32_e32 v6, 1, v4  // 0024ac
	v_cmp_le_u32_e32 vcc, s62, v7  // 0024b0
	v_subrev_u32_e32 v5, s62, v7  // 0024b4
	s_nop 0  // 0024b8
	v_cndmask_b32_e32 v4, v4, v6, vcc  // 0024bc
	v_cndmask_b32_e32 v7, v7, v5, vcc  // 0024c0
	v_add_u32_e32 v5, 1, v4  // 0024c4
	v_cmp_le_u32_e32 vcc, s62, v7  // 0024c8
	s_nop 1  // 0024cc
	v_cndmask_b32_e32 v7, v4, v5, vcc  // 0024d0
	s_nop 3  // 0024d4
	v_readfirstlane_b32 s63, v7  // 0024d8
	s_nop 3  // 0024dc
	s_mov_b32 s44, s63  // 0024e0
	s_mul_i32 s50, s44, s38  // 0024e4
	s_sub_u32 s75, s61, s50  // 0024e8
	s_mov_b32 s61, s34  // 0024ec
	s_mov_b32 s62, s38  // 0024f0
	v_cvt_f32_u32_e32 v4, s62  // 0024f4
	s_sub_i32 s50, 0, s62  // 0024f8
	v_rcp_iflag_f32_e32 v4, v4  // 0024fc
	s_nop 0  // 002500
	v_mul_f32_e32 v4, 0x4f7ffffe, v4  // 002504
	v_cvt_u32_f32_e32 v4, v4  // 00250c
	v_mul_lo_u32 v5, s50, v4  // 002510
	v_mul_hi_u32 v5, v4, v5  // 002518
	v_add_u32_e32 v4, v4, v5  // 002520
	v_mul_hi_u32 v4, s61, v4  // 002524
	v_mul_lo_u32 v5, v4, s62  // 00252c
	v_sub_u32_e32 v7, s61, v5  // 002534
	v_add_u32_e32 v6, 1, v4  // 002538
	v_cmp_le_u32_e32 vcc, s62, v7  // 00253c
	v_subrev_u32_e32 v5, s62, v7  // 002540
	s_nop 0  // 002544
	v_cndmask_b32_e32 v4, v4, v6, vcc  // 002548
	v_cndmask_b32_e32 v7, v7, v5, vcc  // 00254c
	v_add_u32_e32 v5, 1, v4  // 002550
	v_cmp_le_u32_e32 vcc, s62, v7  // 002554
	s_nop 1  // 002558
	v_cndmask_b32_e32 v7, v4, v5, vcc  // 00255c
	s_nop 3  // 002560
	v_readfirstlane_b32 s63, v7  // 002564
	s_nop 3  // 002568
	s_add_u32 s63, 0x7f, s63  // 00256c
	s_lshr_b32 s63, s63, 7  // 002574
	s_lshl_b32 s76, s63, 7  // 002578
	s_mul_i32 s51, s76, s75  // 00257c
	s_sub_i32 s50, s34, s51  // 002580
	s_cmp_lt_i32 s50, s76  // 002584
	s_cselect_b32 s34, s50, s76  // 002588
	s_mul_i32 s50, s45, 0x60  // 00258c
	s_mul_i32 s51, s50, s37  // 002594
	s_mul_hi_u32 s52, s50, s37  // 002598
	s_add_u32 s16, s16, s51  // 00259c
	s_addc_u32 s17, s17, s52  // 0025a0
	s_mul_i32 s50, s44, 0x80  // 0025a4
	s_mul_i32 s51, s50, 2  // 0025ac
	s_mul_hi_u32 s52, s50, 2  // 0025b0
	s_add_u32 s16, s16, s51  // 0025b4
	s_addc_u32 s17, s17, s52  // 0025b8
	s_mov_b32 s80, s16  // 0025bc
	s_mov_b32 s81, s17  // 0025c0
	s_mul_i32 s50, s45, 0x60  // 0025c4
	s_sub_i32 s51, s32, s50  // 0025cc
	s_cmp_lt_u32 s51, 0x60  // 0025d0
	s_cselect_b32 s50, s51, 0x60  // 0025d8
	s_mul_i32 s51, s50, s37  // 0025e0
	s_mov_b32 s18, s51  // 0025e4
	s_mov_b32 s82, 0x80000000  // 0025e8
	s_mov_b32 s19, 0x20000  // 0025f0
	s_and_b32 s17, s17, 0xffff  // 0025f8
	s_and_b32 s81, s81, 0xffff  // 002600
	s_or_b32 s17, s17, 0x40000  // 002608
	s_mov_b32 s48, 0x7060302  // 002610
	v_mov_b32_e32 v9, 0xffff0000  // 002618
	v_mov_b32_e32 v10, 0x7fff0000  // 002620
	v_mov_b32_e32 v11, 0x7fff  // 002628
	s_mul_i32 s50, 0x80, s44  // 002630
	s_mul_hi_u32 s51, 4, s50  // 002638
	s_add_u32 s29, s29, s51  // 00263c
	s_mul_i32 s51, 4, s50  // 002640
	s_add_u32 s28, s28, s51  // 002644
	s_addc_u32 s29, s29, 0  // 002648
	s_sub_i32 s51, s33, s50  // 00264c
	s_cmp_lt_u32 s51, 0x80  // 002650
	s_cselect_b32 s50, s51, 0x80  // 002658
	s_mul_i32 s51, 4, s50  // 002660
	s_mov_b32 s30, s51  // 002664
	s_mov_b32 s31, 0x20000  // 002668
	v_lshrrev_b32_e32 v4, 4, v0  // 002670
	v_lshlrev_b32_e32 v4, 4, v4  // 002674
	s_mul_i32 s52, s47, 0x80  // 002678
	v_add_u32_e64 v4, v4, s52  // 002680
	v_add_u32_e64 v5, v4, 64  // 002688
	buffer_load_dwordx4 v[12:15], v4, s[28:31], 0 offen  // 002690
	buffer_load_dwordx4 v[16:19], v5, s[28:31], 0 offen  // 002698
	s_mul_i32 s50, 0x60, s45  // 0026a0
	s_mul_hi_u32 s52, 4, s50  // 0026a8
	s_mul_i32 s51, 4, s50  // 0026ac
	s_add_u32 s20, s20, s51  // 0026b0
	s_addc_u32 s21, s21, s52  // 0026b4
	s_sub_i32 s51, s32, s50  // 0026b8
	s_cmp_lt_u32 s51, 0x60  // 0026bc
	s_cselect_b32 s50, s51, 0x60  // 0026c4
	s_lshl_b32 s51, s50, 2  // 0026cc
	s_mov_b32 s22, s51  // 0026d0
	s_mov_b32 s23, 0x20000  // 0026d4
	s_lshr_b32 s50, s76, 7  // 0026dc
	s_mul_i32 s50, s50, s75  // 0026e0
	s_mul_i32 s51, s50, s32  // 0026e4
	s_mul_hi_u32 s52, s50, s32  // 0026e8
	s_lshr_b32 s50, s51, 30  // 0026ec
	s_lshl_b32 s51, s51, 2  // 0026f0
	s_lshl_b32 s52, s52, 2  // 0026f4
	s_add_u32 s52, s52, s50  // 0026f8
	s_add_u32 s20, s20, s51  // 0026fc
	s_addc_u32 s21, s21, s52  // 002700
	v_and_b32_e64 v187, v0, 15  // 002704
	v_lshlrev_b32_e32 v187, 2, v187  // 00270c
	s_mov_b32 s50, 64  // 002710
	v_add_u32_e64 v188, v187, s50  // 002714
	s_mov_b32 s50, 0x80  // 00271c
	v_add_u32_e64 v189, v187, s50  // 002724
	s_mov_b32 s50, 0xc0  // 00272c
	v_add_u32_e64 v190, v187, s50  // 002734
	s_mov_b32 s50, 0x100  // 00273c
	v_add_u32_e64 v191, v187, s50  // 002744
	s_mov_b32 s50, 0x140  // 00274c
	v_add_u32_e64 v192, v187, s50  // 002754
	s_mul_i32 s51, s41, s44  // 00275c
	s_mul_hi_u32 s52, 4, s51  // 002760
	s_add_u32 s25, s25, s52  // 002764
	s_mul_i32 s52, 4, s51  // 002768
	s_add_u32 s24, s24, s52  // 00276c
	s_addc_u32 s25, s25, 0  // 002770
	s_lshr_b32 s50, s76, 7  // 002774
	s_mul_i32 s50, s50, s75  // 002778
	s_lshl_b32 s50, s50, 2  // 00277c
	s_add_u32 s24, s24, s50  // 002780
	s_addc_u32 s25, s25, 0  // 002784
	s_sub_u32 s26, s26, s50  // 002788
	v_mov_b32_e32 v199, 0  // 00278c
	v_lshrrev_b32_e32 v4, 5, v0  // 002790
	v_lshlrev_b32_e32 v4, 2, v4  // 002794
	v_mul_i32_i24_e32 v4, s35, v4  // 002798
	v_and_b32_e32 v38, 31, v0  // 00279c
	v_lshlrev_b32_e32 v38, 2, v38  // 0027a0
	s_mul_i32 s50, 0x60, s45  // 0027a4
	s_sub_i32 s51, s32, s50  // 0027ac
	s_cmp_lt_u32 s51, 0x60  // 0027b0
	s_cselect_b32 s51, s51, 0x60  // 0027b8
	s_mul_i32 s52, s35, s50  // 0027c0
	s_mul_hi_u32 s50, s35, s50  // 0027c4
	s_add_u32 s4, s4, s52  // 0027c8
	s_addc_u32 s5, s5, s50  // 0027cc
	s_mul_i32 s50, s35, s51  // 0027d0
	s_mov_b32 s6, s50  // 0027d4
	s_mov_b32 s7, 0x20000  // 0027d8
	s_mul_i32 s51, s76, s75  // 0027e0
	s_add_u32 s4, s51, s4  // 0027e4
	s_addc_u32 s5, 0, s5  // 0027e8
	s_sub_u32 s6, s6, s51  // 0027ec
	s_mul_i32 s50, s35, s47  // 0027f0
	v_add3_u32 v38, v4, v38, s50  // 0027f4
	s_lshl_b32 s50, s35, 3  // 0027fc
	v_add_u32_e32 v39, s50, v38  // 002800
	v_add_u32_e32 v40, s50, v39  // 002804
	v_add_u32_e32 v41, s50, v40  // 002808
	v_add_u32_e32 v42, s50, v41  // 00280c
	v_add_u32_e32 v43, s50, v42  // 002810
	v_add_u32_e32 v44, s50, v43  // 002814
	v_add_u32_e32 v45, s50, v44  // 002818
	v_add_u32_e32 v46, s50, v45  // 00281c
	v_add_u32_e32 v47, s50, v46  // 002820
	v_add_u32_e32 v48, s50, v47  // 002824
	v_add_u32_e32 v49, s50, v48  // 002828
	s_mov_b32 s54, 0x80  // 00282c
	s_mul_i32 s56, s32, 4  // 002834
	s_mov_b32 s57, 4  // 002838
	s_mov_b32 s50, 0x60  // 00283c
	s_lshr_b32 s50, s50, 2  // 002844
	s_mul_i32 s50, s50, 32  // 002848
	s_mov_b32 s51, 8  // 00284c
	s_add_u32 s50, s50, s51  // 002850
	v_lshrrev_b32_e32 v4, 4, v0  // 002854
	v_and_b32_e32 v5, 15, v0  // 002858
	v_and_b32_e32 v6, 3, v5  // 00285c
	v_lshrrev_b32_e32 v7, 2, v5  // 002860
	v_lshlrev_b32_e32 v4, 2, v4  // 002864
	v_mul_lo_u32 v6, v6, s50  // 002868
	v_lshlrev_b32_e32 v7, 5, v7  // 002870
	v_add_u32_e32 v4, v4, v6  // 002874
	v_add_u32_e32 v4, v4, v7  // 002878
	v_lshlrev_b32_e32 v50, 2, v4  // 00287c
	s_mul_i32 s50, 0xc20, s47  // 002880
	s_add_u32 s58, 0, s50  // 002888
	s_add_u32 s59, 0x3080, s58  // 00288c
	s_add_u32 s60, 0x3080, s59  // 002894
	s_mov_b32 s55, 0x800  // 00289c
	s_mul_i32 s49, 0x80, s44  // 0028a4
	s_sub_i32 s51, s33, s49  // 0028ac
	s_cmp_lt_u32 s51, 0x80  // 0028b0
	s_cselect_b32 s50, s51, 0x80  // 0028b8
	s_mul_i32 s51, s36, s49  // 0028c0
	s_mul_hi_u32 s52, s36, s49  // 0028c4
	s_add_u32 s8, s8, s51  // 0028c8
	s_addc_u32 s9, s9, s52  // 0028cc
	s_mul_i32 s51, s36, s50  // 0028d0
	s_mov_b32 s10, s51  // 0028d4
	s_mov_b32 s11, 0x20000  // 0028d8
	s_lshr_b32 s51, s76, 7  // 0028e0
	s_mul_i32 s50, s55, s75  // 0028e4
	s_mul_i32 s50, s51, s50  // 0028e8
	s_add_u32 s8, s50, s8  // 0028ec
	s_addc_u32 s9, 0, s9  // 0028f0
	s_sub_u32 s10, s10, s50  // 0028f4
	s_lshl_b32 s50, s47, 5  // 0028f8
	s_mul_i32 s50, s36, s50  // 0028fc
	v_lshlrev_b32_e32 v34, 4, v0  // 002900
	v_add_u32_e32 v34, s50, v34  // 002904
	s_mov_b32 s50, 0x400  // 002908
	v_add_u32_e64 v35, v34, s50  // 002910
	s_mul_i32 s50, s36, 16  // 002918
	v_add_u32_e64 v36, v34, s50  // 00291c
	v_add_u32_e64 v37, v35, s50  // 002924
	s_add_u32 m0, 0, s58  // 00292c
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002930
	s_add_u32 m0, 0x100, s58  // 002938
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002940
	s_add_u32 m0, 0x200, s58  // 002948
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002950
	s_add_u32 m0, 0x300, s58  // 002958
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002960
	s_add_u32 m0, 0x400, s58  // 002968
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002970
	s_add_u32 m0, 0x500, s58  // 002978
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002980
	s_add_u32 m0, 0x600, s58  // 002988
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002990
	s_add_u32 m0, 0x700, s58  // 002998
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0029a0
	s_add_u32 m0, 0x800, s58  // 0029a8
	buffer_load_dword v46, s[4:7], 0 offen lds  // 0029b0
	s_add_u32 m0, 0x900, s58  // 0029b8
	buffer_load_dword v47, s[4:7], 0 offen lds  // 0029c0
	s_add_u32 m0, 0xa00, s58  // 0029c8
	buffer_load_dword v48, s[4:7], 0 offen lds  // 0029d0
	s_add_u32 m0, 0xb00, s58  // 0029d8
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0029e0
	s_mov_b32 s53, 0  // 0029e8
	s_add_u32 s50, 0x80, s53  // 0029ec
	s_cmp_lt_u32 s50, s34  // 0029f4
	s_cselect_b32 s54, s54, 0  // 0029f8
	s_add_u32 s4, s54, s4  // 0029fc
	s_addc_u32 s5, 0, s5  // 002a00
	s_sub_u32 s6, s6, s54  // 002a04
	buffer_load_dword v148, v187, s[20:23], 0 offen  // 002a08
	buffer_load_dword v149, v188, s[20:23], 0 offen  // 002a10
	buffer_load_dword v150, v189, s[20:23], 0 offen  // 002a18
	buffer_load_dword v151, v190, s[20:23], 0 offen  // 002a20
	buffer_load_dword v152, v191, s[20:23], 0 offen  // 002a28
	buffer_load_dword v153, v192, s[20:23], 0 offen  // 002a30
	s_add_u32 s50, 0x80, s53  // 002a38
	s_cmp_lt_u32 s50, s34  // 002a40
	s_cselect_b32 s56, s56, 0  // 002a44
	s_add_u32 s20, s56, s20  // 002a48
	s_addc_u32 s21, 0, s21  // 002a4c
	v_mov_b32_e32 v100, 0  // 002a50
	v_mov_b32_e32 v101, 0  // 002a54
	v_mov_b32_e32 v102, 0  // 002a58
	v_mov_b32_e32 v103, 0  // 002a5c
	v_mov_b32_e32 v104, 0  // 002a60
	v_mov_b32_e32 v105, 0  // 002a64
	v_mov_b32_e32 v106, 0  // 002a68
	v_mov_b32_e32 v107, 0  // 002a6c
	buffer_load_dwordx4 a[0:3], v34, s[8:11], 0 offen  // 002a70
	buffer_load_dwordx4 a[4:7], v35, s[8:11], 0 offen  // 002a78
	buffer_load_dwordx4 a[8:11], v36, s[8:11], 0 offen  // 002a80
	buffer_load_dwordx4 a[12:15], v37, s[8:11], 0 offen  // 002a88
	s_mov_b32 s53, 0  // 002a90
	s_add_u32 s50, 0x80, s53  // 002a94
	s_cmp_lt_u32 s50, s34  // 002a9c
	s_cselect_b32 s55, s55, 0  // 002aa0
	s_add_u32 s8, s55, s8  // 002aa4
	s_addc_u32 s9, 0, s9  // 002aa8
	s_sub_u32 s10, s10, s55  // 002aac
	buffer_load_dword v184, v199, s[24:27], 0 offen  // 002ab0
	s_add_u32 s50, 0x80, s53  // 002ab8
	s_cmp_lt_u32 s50, s34  // 002ac0
	s_cselect_b32 s57, s57, 0  // 002ac4
	s_add_u32 s24, s57, s24  // 002ac8
	s_addc_u32 s25, 0, s25  // 002acc
	s_sub_u32 s26, s26, s57  // 002ad0
	s_add_u32 m0, 0, s59  // 002ad4
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002ad8
	s_add_u32 m0, 0x100, s59  // 002ae0
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002ae8
	s_add_u32 m0, 0x200, s59  // 002af0
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002af8
	s_add_u32 m0, 0x300, s59  // 002b00
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002b08
	s_add_u32 m0, 0x400, s59  // 002b10
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002b18
	s_add_u32 m0, 0x500, s59  // 002b20
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002b28
	s_add_u32 m0, 0x600, s59  // 002b30
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002b38
	s_add_u32 m0, 0x700, s59  // 002b40
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002b48
	s_add_u32 m0, 0x800, s59  // 002b50
	buffer_load_dword v46, s[4:7], 0 offen lds  // 002b58
	s_add_u32 m0, 0x900, s59  // 002b60
	buffer_load_dword v47, s[4:7], 0 offen lds  // 002b68
	s_add_u32 m0, 0xa00, s59  // 002b70
	buffer_load_dword v48, s[4:7], 0 offen lds  // 002b78
	s_add_u32 m0, 0xb00, s59  // 002b80
	buffer_load_dword v49, s[4:7], 0 offen lds  // 002b88
	s_mov_b32 s53, 0x80  // 002b90
	s_add_u32 s50, 0x80, s53  // 002b98
	s_cmp_lt_u32 s50, s34  // 002ba0
	s_cselect_b32 s54, s54, 0  // 002ba4
	s_add_u32 s4, s54, s4  // 002ba8
	s_addc_u32 s5, 0, s5  // 002bac
	s_sub_u32 s6, s6, s54  // 002bb0
	buffer_load_dword v154, v187, s[20:23], 0 offen  // 002bb4
	buffer_load_dword v155, v188, s[20:23], 0 offen  // 002bbc
	buffer_load_dword v156, v189, s[20:23], 0 offen  // 002bc4
	buffer_load_dword v157, v190, s[20:23], 0 offen  // 002bcc
	buffer_load_dword v158, v191, s[20:23], 0 offen  // 002bd4
	buffer_load_dword v159, v192, s[20:23], 0 offen  // 002bdc
	s_add_u32 s50, 0x80, s53  // 002be4
	s_cmp_lt_u32 s50, s34  // 002bec
	s_cselect_b32 s56, s56, 0  // 002bf0
	s_add_u32 s20, s56, s20  // 002bf4
	s_addc_u32 s21, 0, s21  // 002bf8
	v_mov_b32_e32 v108, 0  // 002bfc
	v_mov_b32_e32 v109, 0  // 002c00
	v_mov_b32_e32 v110, 0  // 002c04
	v_mov_b32_e32 v111, 0  // 002c08
	v_mov_b32_e32 v112, 0  // 002c0c
	v_mov_b32_e32 v113, 0  // 002c10
	v_mov_b32_e32 v114, 0  // 002c14
	v_mov_b32_e32 v115, 0  // 002c18
	buffer_load_dwordx4 a[16:19], v34, s[8:11], 0 offen  // 002c1c
	buffer_load_dwordx4 a[20:23], v35, s[8:11], 0 offen  // 002c24
	buffer_load_dwordx4 a[24:27], v36, s[8:11], 0 offen  // 002c2c
	buffer_load_dwordx4 a[28:31], v37, s[8:11], 0 offen  // 002c34
	s_mov_b32 s53, 0x80  // 002c3c
	s_add_u32 s50, 0x80, s53  // 002c44
	s_cmp_lt_u32 s50, s34  // 002c4c
	s_cselect_b32 s55, s55, 0  // 002c50
	s_add_u32 s8, s55, s8  // 002c54
	s_addc_u32 s9, 0, s9  // 002c58
	s_sub_u32 s10, s10, s55  // 002c5c
	buffer_load_dword v185, v199, s[24:27], 0 offen  // 002c60
	s_add_u32 s50, 0x80, s53  // 002c68
	s_cmp_lt_u32 s50, s34  // 002c70
	s_cselect_b32 s57, s57, 0  // 002c74
	s_add_u32 s24, s57, s24  // 002c78
	s_addc_u32 s25, 0, s25  // 002c7c
	s_sub_u32 s26, s26, s57  // 002c80
	s_add_u32 m0, 0, s60  // 002c84
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002c88
	s_add_u32 m0, 0x100, s60  // 002c90
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002c98
	s_add_u32 m0, 0x200, s60  // 002ca0
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002ca8
	s_add_u32 m0, 0x300, s60  // 002cb0
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002cb8
	s_add_u32 m0, 0x400, s60  // 002cc0
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002cc8
	s_add_u32 m0, 0x500, s60  // 002cd0
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002cd8
	s_add_u32 m0, 0x600, s60  // 002ce0
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002ce8
	s_add_u32 m0, 0x700, s60  // 002cf0
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002cf8
	s_add_u32 m0, 0x800, s60  // 002d00
	buffer_load_dword v46, s[4:7], 0 offen lds  // 002d08
	s_add_u32 m0, 0x900, s60  // 002d10
	buffer_load_dword v47, s[4:7], 0 offen lds  // 002d18
	s_add_u32 m0, 0xa00, s60  // 002d20
	buffer_load_dword v48, s[4:7], 0 offen lds  // 002d28
	s_add_u32 m0, 0xb00, s60  // 002d30
	buffer_load_dword v49, s[4:7], 0 offen lds  // 002d38
	s_mov_b32 s53, 0x100  // 002d40
	s_add_u32 s50, 0x80, s53  // 002d48
	s_cmp_lt_u32 s50, s34  // 002d50
	s_cselect_b32 s54, s54, 0  // 002d54
	s_add_u32 s4, s54, s4  // 002d58
	s_addc_u32 s5, 0, s5  // 002d5c
	s_sub_u32 s6, s6, s54  // 002d60
	buffer_load_dword v160, v187, s[20:23], 0 offen  // 002d64
	buffer_load_dword v161, v188, s[20:23], 0 offen  // 002d6c
	buffer_load_dword v162, v189, s[20:23], 0 offen  // 002d74
	buffer_load_dword v163, v190, s[20:23], 0 offen  // 002d7c
	buffer_load_dword v164, v191, s[20:23], 0 offen  // 002d84
	buffer_load_dword v165, v192, s[20:23], 0 offen  // 002d8c
	s_add_u32 s50, 0x80, s53  // 002d94
	s_cmp_lt_u32 s50, s34  // 002d9c
	s_cselect_b32 s56, s56, 0  // 002da0
	s_add_u32 s20, s56, s20  // 002da4
	s_addc_u32 s21, 0, s21  // 002da8
	v_mov_b32_e32 v116, 0  // 002dac
	v_mov_b32_e32 v117, 0  // 002db0
	v_mov_b32_e32 v118, 0  // 002db4
	v_mov_b32_e32 v119, 0  // 002db8
	v_mov_b32_e32 v120, 0  // 002dbc
	v_mov_b32_e32 v121, 0  // 002dc0
	v_mov_b32_e32 v122, 0  // 002dc4
	v_mov_b32_e32 v123, 0  // 002dc8
	v_mov_b32_e32 v124, 0  // 002dcc
	v_mov_b32_e32 v125, 0  // 002dd0
	v_mov_b32_e32 v126, 0  // 002dd4
	v_mov_b32_e32 v127, 0  // 002dd8
	v_mov_b32_e32 v128, 0  // 002ddc
	v_mov_b32_e32 v129, 0  // 002de0
	v_mov_b32_e32 v130, 0  // 002de4
	v_mov_b32_e32 v131, 0  // 002de8
	v_mov_b32_e32 v132, 0  // 002dec
	v_mov_b32_e32 v133, 0  // 002df0
	v_mov_b32_e32 v134, 0  // 002df4
	v_mov_b32_e32 v135, 0  // 002df8
	v_mov_b32_e32 v136, 0  // 002dfc
	v_mov_b32_e32 v137, 0  // 002e00
	v_mov_b32_e32 v138, 0  // 002e04
	v_mov_b32_e32 v139, 0  // 002e08
	v_mov_b32_e32 v140, 0  // 002e0c
	v_mov_b32_e32 v141, 0  // 002e10
	v_mov_b32_e32 v142, 0  // 002e14
	v_mov_b32_e32 v143, 0  // 002e18
	v_mov_b32_e32 v144, 0  // 002e1c
	v_mov_b32_e32 v145, 0  // 002e20
	v_mov_b32_e32 v146, 0  // 002e24
	v_mov_b32_e32 v147, 0  // 002e28
	s_mov_b32 s43, s34  // 002e2c
	s_mov_b32 s42, 0  // 002e30
	s_waitcnt vmcnt(46)  // 002e34
	s_barrier  // 002e38
	ds_read_b128 a[48:51], v50  // 002e3c
	ds_read_b128 a[52:55], v50 offset:64  // 002e44
	ds_read_b128 a[56:59], v50 offset:512  // 002e4c
	ds_read_b128 a[60:63], v50 offset:576  // 002e54
	ds_read_b128 a[64:67], v50 offset:1024  // 002e5c
	ds_read_b128 a[68:71], v50 offset:1088  // 002e64
	ds_read_b128 a[72:75], v50 offset:1536  // 002e6c
	ds_read_b128 a[76:79], v50 offset:1600  // 002e74
	ds_read_b128 a[80:83], v50 offset:2048  // 002e7c
	ds_read_b128 a[84:87], v50 offset:2112  // 002e84
	ds_read_b128 a[88:91], v50 offset:2560  // 002e8c
	ds_read_b128 a[92:95], v50 offset:2624  // 002e94
	s_mov_b32 s50, 0  // 002e9c
	s_mov_b32 s51, 1.0  // 002ea0
	s_cmp_eq_u32 s50, s75  // 002ea4
	s_cselect_b32 s50, s51, 0  // 002ea8
	v_mul_f32_e64 v12, v12, s50  // 002eac
	v_mul_f32_e64 v13, v13, s50  // 002eb4
	v_mul_f32_e64 v14, v14, s50  // 002ebc
	v_mul_f32_e64 v15, v15, s50  // 002ec4
	v_mul_f32_e64 v16, v16, s50  // 002ecc
	v_mul_f32_e64 v17, v17, s50  // 002ed4
	v_mul_f32_e64 v18, v18, s50  // 002edc
	v_mul_f32_e64 v19, v19, s50  // 002ee4
	v_and_b32_e64 v20, v0, 15  // 002eec
	v_mul_lo_u32 v20, v20, s37  // 002ef4
	v_lshrrev_b32_e32 v4, 4, v0  // 002efc
	v_mul_i32_i24_e32 v4, 8, v4  // 002f00
	v_add_u32_e32 v20, v4, v20  // 002f04
	s_mul_i32 s50, 32, s47  // 002f08
	s_mul_i32 s50, 2, s50  // 002f0c
	v_add_u32_e32 v20, s50, v20  // 002f10
	s_mul_i32 s50, 16, s37  // 002f14
	v_add_u32_e32 v21, s50, v20  // 002f18
	v_add_u32_e32 v22, s50, v21  // 002f1c
	v_add_u32_e32 v23, s50, v22  // 002f20
	v_add_u32_e32 v24, s50, v23  // 002f24
	v_add_u32_e32 v25, s50, v24  // 002f28
	s_mul_i32 s50, s47, s37  // 002f2c
	v_lshlrev_b32_e32 v5, 2, v0  // 002f30
	v_add_u32_e32 v26, s50, v5  // 002f34
	s_mul_i32 s50, s45, 0x60  // 002f38
	s_add_i32 s77, s50, s47  // 002f40
	s_cmp_lt_i32 s42, s43  // 002f44
	s_cbranch_scc0 L_49a8  // 002f48
L_2f4c:
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 002f50
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[0:1], a[48:49], 0  // 002f54
	s_add_u32 m0, 0, s58  // 002f5c
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002f60
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[2:3], a[50:51], v[52:55]  // 002f68
	ds_read_b128 a[96:99], v50 offset:12416  // 002f70
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[4:5], a[52:53], v[52:55]  // 002f78
	s_add_u32 m0, 0x100, s58  // 002f80
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002f88
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[6:7], a[54:55], v[52:55]  // 002f90
	ds_read_b128 a[100:103], v50 offset:12480  // 002f98
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v184, v148  // 002fa0
	v_mov_b32_e32 v5, v4  // 002fa4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[8:9], a[48:49], 0  // 002fa8
	buffer_load_dwordx4 a[32:35], v34, s[8:11], 0 offen  // 002fb0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[10:11], a[50:51], v[56:59]  // 002fb8
	buffer_load_dword v148, v187, s[20:23], 0 offen  // 002fc0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[12:13], a[52:53], v[56:59]  // 002fc8
	buffer_load_dwordx4 a[36:39], v35, s[8:11], 0 offen  // 002fd0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[14:15], a[54:55], v[56:59]  // 002fd8
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 002fe0
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 002fe8
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 002ff0
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 002ff8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[56:57], 0  // 003000
	s_add_u32 m0, 0x200, s58  // 003008
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003010
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[58:59], v[60:63]  // 003018
	ds_read_b128 a[104:107], v50 offset:12928  // 003020
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[60:61], v[60:63]  // 003028
	s_add_u32 m0, 0x300, s58  // 003030
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003038
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[62:63], v[60:63]  // 003040
	ds_read_b128 a[108:111], v50 offset:12992  // 003048
	v_mul_f32_e32 v4, v184, v149  // 003050
	v_mov_b32_e32 v5, v4  // 003054
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[56:57], 0  // 003058
	buffer_load_dwordx4 a[40:43], v36, s[8:11], 0 offen  // 003060
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[58:59], v[64:67]  // 003068
	buffer_load_dword v149, v188, s[20:23], 0 offen  // 003070
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[60:61], v[64:67]  // 003078
	buffer_load_dwordx4 a[44:47], v37, s[8:11], 0 offen  // 003080
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[62:63], v[64:67]  // 003088
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 003090
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 003098
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 0030a0
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 0030a8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[64:65], 0  // 0030b0
	s_add_u32 m0, 0x400, s58  // 0030b8
	buffer_load_dword v42, s[4:7], 0 offen lds  // 0030c0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[66:67], v[68:71]  // 0030c8
	ds_read_b128 a[112:115], v50 offset:13440  // 0030d0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[68:69], v[68:71]  // 0030d8
	s_add_u32 m0, 0x500, s58  // 0030e0
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0030e8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[70:71], v[68:71]  // 0030f0
	ds_read_b128 a[116:119], v50 offset:13504  // 0030f8
	v_mul_f32_e32 v4, v184, v150  // 003100
	v_mov_b32_e32 v5, v4  // 003104
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[64:65], 0  // 003108
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[66:67], v[72:75]  // 003110
	buffer_load_dword v150, v189, s[20:23], 0 offen  // 003118
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[68:69], v[72:75]  // 003120
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[70:71], v[72:75]  // 003128
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 003130
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 003138
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 003140
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 003148
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[0:1], a[72:73], 0  // 003150
	s_add_u32 m0, 0x600, s58  // 003158
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003160
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[2:3], a[74:75], v[76:79]  // 003168
	ds_read_b128 a[120:123], v50 offset:13952  // 003170
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[4:5], a[76:77], v[76:79]  // 003178
	s_add_u32 m0, 0x700, s58  // 003180
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003188
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[6:7], a[78:79], v[76:79]  // 003190
	ds_read_b128 a[124:127], v50 offset:14016  // 003198
	v_mul_f32_e32 v4, v184, v151  // 0031a0
	v_mov_b32_e32 v5, v4  // 0031a4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[8:9], a[72:73], 0  // 0031a8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[10:11], a[74:75], v[80:83]  // 0031b0
	buffer_load_dword v151, v190, s[20:23], 0 offen  // 0031b8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[12:13], a[76:77], v[80:83]  // 0031c0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[14:15], a[78:79], v[80:83]  // 0031c8
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 0031d0
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 0031d8
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 0031e0
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 0031e8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[0:1], a[80:81], 0  // 0031f0
	s_add_u32 m0, 0x800, s58  // 0031f8
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003200
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[2:3], a[82:83], v[84:87]  // 003208
	ds_read_b128 a[128:131], v50 offset:14464  // 003210
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[4:5], a[84:85], v[84:87]  // 003218
	s_add_u32 m0, 0x900, s58  // 003220
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003228
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[6:7], a[86:87], v[84:87]  // 003230
	ds_read_b128 a[132:135], v50 offset:14528  // 003238
	v_mul_f32_e32 v4, v184, v152  // 003240
	v_mov_b32_e32 v5, v4  // 003244
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[8:9], a[80:81], 0  // 003248
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[10:11], a[82:83], v[88:91]  // 003250
	buffer_load_dword v152, v191, s[20:23], 0 offen  // 003258
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[12:13], a[84:85], v[88:91]  // 003260
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[14:15], a[86:87], v[88:91]  // 003268
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 003270
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 003278
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 003280
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 003288
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[0:1], a[88:89], 0  // 003290
	s_add_u32 m0, 0xa00, s58  // 003298
	buffer_load_dword v48, s[4:7], 0 offen lds  // 0032a0
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[2:3], a[90:91], v[92:95]  // 0032a8
	ds_read_b128 a[136:139], v50 offset:14976  // 0032b0
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[4:5], a[92:93], v[92:95]  // 0032b8
	s_add_u32 m0, 0xb00, s58  // 0032c0
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0032c8
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[6:7], a[94:95], v[92:95]  // 0032d0
	s_add_u32 s50, 0x200, s42  // 003300
	s_cmp_lt_u32 s50, s43  // 003308
	s_cselect_b32 s54, s54, 0  // 00330c
	ds_read_b128 a[140:143], v50 offset:15040  // 0032d8
	v_mul_f32_e32 v4, v184, v153  // 0032e0
	v_mov_b32_e32 v5, v4  // 0032e4
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[8:9], a[88:89], 0  // 0032e8
	s_add_u32 s50, 0x180, s42  // 003310
	s_cmp_lt_u32 s50, s43  // 003318
	s_cselect_b32 s55, s55, 0  // 00331c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[10:11], a[90:91], v[96:99]  // 0032f0
	buffer_load_dword v153, v192, s[20:23], 0 offen  // 0032f8
	s_add_u32 s50, 0x200, s42  // 003320
	s_cmp_lt_u32 s50, s43  // 003328
	s_cselect_b32 s56, s56, 0  // 00332c
	s_add_u32 s50, 0x180, s42  // 003330
	s_cmp_lt_u32 s50, s43  // 003338
	s_cselect_b32 s57, s57, 0  // 00333c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[12:13], a[92:93], v[96:99]  // 003340
	s_add_u32 s4, s54, s4  // 003358
	s_addc_u32 s5, 0, s5  // 00335c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[14:15], a[94:95], v[96:99]  // 003348
	buffer_load_dword v186, v199, s[24:27], 0 offen  // 003350
	s_sub_u32 s6, s6, s54  // 003360
	s_add_u32 s8, s55, s8  // 003364
	s_addc_u32 s9, 0, s9  // 003368
	s_sub_u32 s10, s10, s55  // 00336c
	s_add_u32 s20, s56, s20  // 003370
	s_addc_u32 s21, 0, s21  // 003374
	s_add_u32 s24, s57, s24  // 003378
	s_addc_u32 s25, 0, s25  // 00337c
	s_sub_u32 s26, s26, s57  // 003380
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 003384
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 00338c
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 003394
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 00339c
	s_addk_i32 s42, 0x80  // 0033a4
	s_cmp_lt_i32 s42, s43  // 0033a8
	s_cbranch_scc0 L_49a8  // 0033ac
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 0033b4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[16:17], a[96:97], 0  // 0033b8
	s_add_u32 m0, 0, s59  // 0033c0
	buffer_load_dword v38, s[4:7], 0 offen lds  // 0033c4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[18:19], a[98:99], v[52:55]  // 0033cc
	ds_read_b128 a[48:51], v50 offset:24832  // 0033d4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[20:21], a[100:101], v[52:55]  // 0033dc
	s_add_u32 m0, 0x100, s59  // 0033e4
	buffer_load_dword v39, s[4:7], 0 offen lds  // 0033ec
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[22:23], a[102:103], v[52:55]  // 0033f4
	ds_read_b128 a[52:55], v50 offset:24896  // 0033fc
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v185, v154  // 003404
	v_mov_b32_e32 v5, v4  // 003408
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[24:25], a[96:97], 0  // 00340c
	buffer_load_dwordx4 a[0:3], v34, s[8:11], 0 offen  // 003414
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[26:27], a[98:99], v[56:59]  // 00341c
	buffer_load_dword v154, v187, s[20:23], 0 offen  // 003424
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[28:29], a[100:101], v[56:59]  // 00342c
	buffer_load_dwordx4 a[4:7], v35, s[8:11], 0 offen  // 003434
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[30:31], a[102:103], v[56:59]  // 00343c
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 003444
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 00344c
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 003454
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 00345c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[104:105], 0  // 003464
	s_add_u32 m0, 0x200, s59  // 00346c
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003474
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[106:107], v[60:63]  // 00347c
	ds_read_b128 a[56:59], v50 offset:25344  // 003484
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[108:109], v[60:63]  // 00348c
	s_add_u32 m0, 0x300, s59  // 003494
	buffer_load_dword v41, s[4:7], 0 offen lds  // 00349c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[110:111], v[60:63]  // 0034a4
	ds_read_b128 a[60:63], v50 offset:25408  // 0034ac
	v_mul_f32_e32 v4, v185, v155  // 0034b4
	v_mov_b32_e32 v5, v4  // 0034b8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[104:105], 0  // 0034bc
	buffer_load_dwordx4 a[8:11], v36, s[8:11], 0 offen  // 0034c4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[106:107], v[64:67]  // 0034cc
	buffer_load_dword v155, v188, s[20:23], 0 offen  // 0034d4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[108:109], v[64:67]  // 0034dc
	buffer_load_dwordx4 a[12:15], v37, s[8:11], 0 offen  // 0034e4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[110:111], v[64:67]  // 0034ec
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 0034f4
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 0034fc
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 003504
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 00350c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[112:113], 0  // 003514
	s_add_u32 m0, 0x400, s59  // 00351c
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003524
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[114:115], v[68:71]  // 00352c
	ds_read_b128 a[64:67], v50 offset:25856  // 003534
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[116:117], v[68:71]  // 00353c
	s_add_u32 m0, 0x500, s59  // 003544
	buffer_load_dword v43, s[4:7], 0 offen lds  // 00354c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[118:119], v[68:71]  // 003554
	ds_read_b128 a[68:71], v50 offset:25920  // 00355c
	v_mul_f32_e32 v4, v185, v156  // 003564
	v_mov_b32_e32 v5, v4  // 003568
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[112:113], 0  // 00356c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[114:115], v[72:75]  // 003574
	buffer_load_dword v156, v189, s[20:23], 0 offen  // 00357c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[116:117], v[72:75]  // 003584
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[118:119], v[72:75]  // 00358c
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 003594
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 00359c
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 0035a4
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 0035ac
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[16:17], a[120:121], 0  // 0035b4
	s_add_u32 m0, 0x600, s59  // 0035bc
	buffer_load_dword v44, s[4:7], 0 offen lds  // 0035c4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[18:19], a[122:123], v[76:79]  // 0035cc
	ds_read_b128 a[72:75], v50 offset:26368  // 0035d4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[20:21], a[124:125], v[76:79]  // 0035dc
	s_add_u32 m0, 0x700, s59  // 0035e4
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0035ec
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[22:23], a[126:127], v[76:79]  // 0035f4
	ds_read_b128 a[76:79], v50 offset:26432  // 0035fc
	v_mul_f32_e32 v4, v185, v157  // 003604
	v_mov_b32_e32 v5, v4  // 003608
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[24:25], a[120:121], 0  // 00360c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[26:27], a[122:123], v[80:83]  // 003614
	buffer_load_dword v157, v190, s[20:23], 0 offen  // 00361c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[28:29], a[124:125], v[80:83]  // 003624
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[30:31], a[126:127], v[80:83]  // 00362c
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 003634
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 00363c
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 003644
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 00364c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[16:17], a[128:129], 0  // 003654
	s_add_u32 m0, 0x800, s59  // 00365c
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003664
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[18:19], a[130:131], v[84:87]  // 00366c
	ds_read_b128 a[80:83], v50 offset:26880  // 003674
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[20:21], a[132:133], v[84:87]  // 00367c
	s_add_u32 m0, 0x900, s59  // 003684
	buffer_load_dword v47, s[4:7], 0 offen lds  // 00368c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[22:23], a[134:135], v[84:87]  // 003694
	ds_read_b128 a[84:87], v50 offset:26944  // 00369c
	v_mul_f32_e32 v4, v185, v158  // 0036a4
	v_mov_b32_e32 v5, v4  // 0036a8
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[24:25], a[128:129], 0  // 0036ac
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[26:27], a[130:131], v[88:91]  // 0036b4
	buffer_load_dword v158, v191, s[20:23], 0 offen  // 0036bc
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[28:29], a[132:133], v[88:91]  // 0036c4
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[30:31], a[134:135], v[88:91]  // 0036cc
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 0036d4
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 0036dc
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 0036e4
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 0036ec
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[16:17], a[136:137], 0  // 0036f4
	s_add_u32 m0, 0xa00, s59  // 0036fc
	buffer_load_dword v48, s[4:7], 0 offen lds  // 003704
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[18:19], a[138:139], v[92:95]  // 00370c
	ds_read_b128 a[88:91], v50 offset:27392  // 003714
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[20:21], a[140:141], v[92:95]  // 00371c
	s_add_u32 m0, 0xb00, s59  // 003724
	buffer_load_dword v49, s[4:7], 0 offen lds  // 00372c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[22:23], a[142:143], v[92:95]  // 003734
	s_add_u32 s50, 0x200, s42  // 003764
	s_cmp_lt_u32 s50, s43  // 00376c
	s_cselect_b32 s54, s54, 0  // 003770
	ds_read_b128 a[92:95], v50 offset:27456  // 00373c
	v_mul_f32_e32 v4, v185, v159  // 003744
	v_mov_b32_e32 v5, v4  // 003748
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[24:25], a[136:137], 0  // 00374c
	s_add_u32 s50, 0x180, s42  // 003774
	s_cmp_lt_u32 s50, s43  // 00377c
	s_cselect_b32 s55, s55, 0  // 003780
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[26:27], a[138:139], v[96:99]  // 003754
	buffer_load_dword v159, v192, s[20:23], 0 offen  // 00375c
	s_add_u32 s50, 0x200, s42  // 003784
	s_cmp_lt_u32 s50, s43  // 00378c
	s_cselect_b32 s56, s56, 0  // 003790
	s_add_u32 s50, 0x180, s42  // 003794
	s_cmp_lt_u32 s50, s43  // 00379c
	s_cselect_b32 s57, s57, 0  // 0037a0
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[28:29], a[140:141], v[96:99]  // 0037a4
	s_add_u32 s4, s54, s4  // 0037bc
	s_addc_u32 s5, 0, s5  // 0037c0
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[30:31], a[142:143], v[96:99]  // 0037ac
	buffer_load_dword v184, v199, s[24:27], 0 offen  // 0037b4
	s_sub_u32 s6, s6, s54  // 0037c4
	s_add_u32 s8, s55, s8  // 0037c8
	s_addc_u32 s9, 0, s9  // 0037cc
	s_sub_u32 s10, s10, s55  // 0037d0
	s_add_u32 s20, s56, s20  // 0037d4
	s_addc_u32 s21, 0, s21  // 0037d8
	s_add_u32 s24, s57, s24  // 0037dc
	s_addc_u32 s25, 0, s25  // 0037e0
	s_sub_u32 s26, s26, s57  // 0037e4
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 0037e8
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 0037f0
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 0037f8
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 003800
	s_addk_i32 s42, 0x80  // 003808
	s_cmp_lt_i32 s42, s43  // 00380c
	s_cbranch_scc0 L_49a8  // 003810
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 003818
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[32:33], a[48:49], 0  // 00381c
	s_add_u32 m0, 0, s60  // 003824
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003828
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[34:35], a[50:51], v[52:55]  // 003830
	ds_read_b128 a[96:99], v50  // 003838
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[36:37], a[52:53], v[52:55]  // 003840
	s_add_u32 m0, 0x100, s60  // 003848
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003850
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[38:39], a[54:55], v[52:55]  // 003858
	ds_read_b128 a[100:103], v50 offset:64  // 003860
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v186, v160  // 003868
	v_mov_b32_e32 v5, v4  // 00386c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[40:41], a[48:49], 0  // 003870
	buffer_load_dwordx4 a[16:19], v34, s[8:11], 0 offen  // 003878
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[42:43], a[50:51], v[56:59]  // 003880
	buffer_load_dword v160, v187, s[20:23], 0 offen  // 003888
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[44:45], a[52:53], v[56:59]  // 003890
	buffer_load_dwordx4 a[20:23], v35, s[8:11], 0 offen  // 003898
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[46:47], a[54:55], v[56:59]  // 0038a0
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 0038a8
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 0038b0
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 0038b8
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 0038c0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[56:57], 0  // 0038c8
	s_add_u32 m0, 0x200, s60  // 0038d0
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0038d8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[58:59], v[60:63]  // 0038e0
	ds_read_b128 a[104:107], v50 offset:512  // 0038e8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[60:61], v[60:63]  // 0038f0
	s_add_u32 m0, 0x300, s60  // 0038f8
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003900
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[62:63], v[60:63]  // 003908
	ds_read_b128 a[108:111], v50 offset:576  // 003910
	v_mul_f32_e32 v4, v186, v161  // 003918
	v_mov_b32_e32 v5, v4  // 00391c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[56:57], 0  // 003920
	buffer_load_dwordx4 a[24:27], v36, s[8:11], 0 offen  // 003928
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[58:59], v[64:67]  // 003930
	buffer_load_dword v161, v188, s[20:23], 0 offen  // 003938
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[60:61], v[64:67]  // 003940
	buffer_load_dwordx4 a[28:31], v37, s[8:11], 0 offen  // 003948
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[62:63], v[64:67]  // 003950
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 003958
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 003960
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 003968
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 003970
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[64:65], 0  // 003978
	s_add_u32 m0, 0x400, s60  // 003980
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003988
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[66:67], v[68:71]  // 003990
	ds_read_b128 a[112:115], v50 offset:1024  // 003998
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[68:69], v[68:71]  // 0039a0
	s_add_u32 m0, 0x500, s60  // 0039a8
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0039b0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[70:71], v[68:71]  // 0039b8
	ds_read_b128 a[116:119], v50 offset:1088  // 0039c0
	v_mul_f32_e32 v4, v186, v162  // 0039c8
	v_mov_b32_e32 v5, v4  // 0039cc
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[64:65], 0  // 0039d0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[66:67], v[72:75]  // 0039d8
	buffer_load_dword v162, v189, s[20:23], 0 offen  // 0039e0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[68:69], v[72:75]  // 0039e8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[70:71], v[72:75]  // 0039f0
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 0039f8
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 003a00
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 003a08
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 003a10
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[32:33], a[72:73], 0  // 003a18
	s_add_u32 m0, 0x600, s60  // 003a20
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003a28
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[34:35], a[74:75], v[76:79]  // 003a30
	ds_read_b128 a[120:123], v50 offset:1536  // 003a38
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[36:37], a[76:77], v[76:79]  // 003a40
	s_add_u32 m0, 0x700, s60  // 003a48
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003a50
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[38:39], a[78:79], v[76:79]  // 003a58
	ds_read_b128 a[124:127], v50 offset:1600  // 003a60
	v_mul_f32_e32 v4, v186, v163  // 003a68
	v_mov_b32_e32 v5, v4  // 003a6c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[40:41], a[72:73], 0  // 003a70
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[42:43], a[74:75], v[80:83]  // 003a78
	buffer_load_dword v163, v190, s[20:23], 0 offen  // 003a80
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[44:45], a[76:77], v[80:83]  // 003a88
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[46:47], a[78:79], v[80:83]  // 003a90
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 003a98
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 003aa0
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 003aa8
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 003ab0
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[32:33], a[80:81], 0  // 003ab8
	s_add_u32 m0, 0x800, s60  // 003ac0
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003ac8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[34:35], a[82:83], v[84:87]  // 003ad0
	ds_read_b128 a[128:131], v50 offset:2048  // 003ad8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[36:37], a[84:85], v[84:87]  // 003ae0
	s_add_u32 m0, 0x900, s60  // 003ae8
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003af0
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[38:39], a[86:87], v[84:87]  // 003af8
	ds_read_b128 a[132:135], v50 offset:2112  // 003b00
	v_mul_f32_e32 v4, v186, v164  // 003b08
	v_mov_b32_e32 v5, v4  // 003b0c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[40:41], a[80:81], 0  // 003b10
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[42:43], a[82:83], v[88:91]  // 003b18
	buffer_load_dword v164, v191, s[20:23], 0 offen  // 003b20
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[44:45], a[84:85], v[88:91]  // 003b28
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[46:47], a[86:87], v[88:91]  // 003b30
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 003b38
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 003b40
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 003b48
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 003b50
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[32:33], a[88:89], 0  // 003b58
	s_add_u32 m0, 0xa00, s60  // 003b60
	buffer_load_dword v48, s[4:7], 0 offen lds  // 003b68
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[34:35], a[90:91], v[92:95]  // 003b70
	ds_read_b128 a[136:139], v50 offset:2560  // 003b78
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[36:37], a[92:93], v[92:95]  // 003b80
	s_add_u32 m0, 0xb00, s60  // 003b88
	buffer_load_dword v49, s[4:7], 0 offen lds  // 003b90
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[38:39], a[94:95], v[92:95]  // 003b98
	s_add_u32 s50, 0x200, s42  // 003bc8
	s_cmp_lt_u32 s50, s43  // 003bd0
	s_cselect_b32 s54, s54, 0  // 003bd4
	ds_read_b128 a[140:143], v50 offset:2624  // 003ba0
	v_mul_f32_e32 v4, v186, v165  // 003ba8
	v_mov_b32_e32 v5, v4  // 003bac
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[40:41], a[88:89], 0  // 003bb0
	s_add_u32 s50, 0x180, s42  // 003bd8
	s_cmp_lt_u32 s50, s43  // 003be0
	s_cselect_b32 s55, s55, 0  // 003be4
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[42:43], a[90:91], v[96:99]  // 003bb8
	buffer_load_dword v165, v192, s[20:23], 0 offen  // 003bc0
	s_add_u32 s50, 0x200, s42  // 003be8
	s_cmp_lt_u32 s50, s43  // 003bf0
	s_cselect_b32 s56, s56, 0  // 003bf4
	s_add_u32 s50, 0x180, s42  // 003bf8
	s_cmp_lt_u32 s50, s43  // 003c00
	s_cselect_b32 s57, s57, 0  // 003c04
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[44:45], a[92:93], v[96:99]  // 003c08
	s_add_u32 s4, s54, s4  // 003c20
	s_addc_u32 s5, 0, s5  // 003c24
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[46:47], a[94:95], v[96:99]  // 003c10
	buffer_load_dword v185, v199, s[24:27], 0 offen  // 003c18
	s_sub_u32 s6, s6, s54  // 003c28
	s_add_u32 s8, s55, s8  // 003c2c
	s_addc_u32 s9, 0, s9  // 003c30
	s_sub_u32 s10, s10, s55  // 003c34
	s_add_u32 s20, s56, s20  // 003c38
	s_addc_u32 s21, 0, s21  // 003c3c
	s_add_u32 s24, s57, s24  // 003c40
	s_addc_u32 s25, 0, s25  // 003c44
	s_sub_u32 s26, s26, s57  // 003c48
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 003c4c
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 003c54
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 003c5c
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 003c64
	s_addk_i32 s42, 0x80  // 003c6c
	s_cmp_lt_i32 s42, s43  // 003c70
	s_cbranch_scc0 L_49a8  // 003c74
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 003c7c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[0:1], a[96:97], 0  // 003c80
	s_add_u32 m0, 0, s58  // 003c88
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003c8c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[2:3], a[98:99], v[52:55]  // 003c94
	ds_read_b128 a[48:51], v50 offset:12416  // 003c9c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[4:5], a[100:101], v[52:55]  // 003ca4
	s_add_u32 m0, 0x100, s58  // 003cac
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003cb4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[6:7], a[102:103], v[52:55]  // 003cbc
	ds_read_b128 a[52:55], v50 offset:12480  // 003cc4
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v184, v148  // 003ccc
	v_mov_b32_e32 v5, v4  // 003cd0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[8:9], a[96:97], 0  // 003cd4
	buffer_load_dwordx4 a[32:35], v34, s[8:11], 0 offen  // 003cdc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[10:11], a[98:99], v[56:59]  // 003ce4
	buffer_load_dword v148, v187, s[20:23], 0 offen  // 003cec
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[12:13], a[100:101], v[56:59]  // 003cf4
	buffer_load_dwordx4 a[36:39], v35, s[8:11], 0 offen  // 003cfc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[14:15], a[102:103], v[56:59]  // 003d04
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 003d0c
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 003d14
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 003d1c
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 003d24
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[104:105], 0  // 003d2c
	s_add_u32 m0, 0x200, s58  // 003d34
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003d3c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[106:107], v[60:63]  // 003d44
	ds_read_b128 a[56:59], v50 offset:12928  // 003d4c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[108:109], v[60:63]  // 003d54
	s_add_u32 m0, 0x300, s58  // 003d5c
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003d64
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[110:111], v[60:63]  // 003d6c
	ds_read_b128 a[60:63], v50 offset:12992  // 003d74
	v_mul_f32_e32 v4, v184, v149  // 003d7c
	v_mov_b32_e32 v5, v4  // 003d80
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[104:105], 0  // 003d84
	buffer_load_dwordx4 a[40:43], v36, s[8:11], 0 offen  // 003d8c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[106:107], v[64:67]  // 003d94
	buffer_load_dword v149, v188, s[20:23], 0 offen  // 003d9c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[108:109], v[64:67]  // 003da4
	buffer_load_dwordx4 a[44:47], v37, s[8:11], 0 offen  // 003dac
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[110:111], v[64:67]  // 003db4
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 003dbc
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 003dc4
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 003dcc
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 003dd4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[112:113], 0  // 003ddc
	s_add_u32 m0, 0x400, s58  // 003de4
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003dec
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[114:115], v[68:71]  // 003df4
	ds_read_b128 a[64:67], v50 offset:13440  // 003dfc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[116:117], v[68:71]  // 003e04
	s_add_u32 m0, 0x500, s58  // 003e0c
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003e14
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[118:119], v[68:71]  // 003e1c
	ds_read_b128 a[68:71], v50 offset:13504  // 003e24
	v_mul_f32_e32 v4, v184, v150  // 003e2c
	v_mov_b32_e32 v5, v4  // 003e30
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[112:113], 0  // 003e34
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[114:115], v[72:75]  // 003e3c
	buffer_load_dword v150, v189, s[20:23], 0 offen  // 003e44
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[116:117], v[72:75]  // 003e4c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[118:119], v[72:75]  // 003e54
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 003e5c
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 003e64
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 003e6c
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 003e74
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[0:1], a[120:121], 0  // 003e7c
	s_add_u32 m0, 0x600, s58  // 003e84
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003e8c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[2:3], a[122:123], v[76:79]  // 003e94
	ds_read_b128 a[72:75], v50 offset:13952  // 003e9c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[4:5], a[124:125], v[76:79]  // 003ea4
	s_add_u32 m0, 0x700, s58  // 003eac
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003eb4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[6:7], a[126:127], v[76:79]  // 003ebc
	ds_read_b128 a[76:79], v50 offset:14016  // 003ec4
	v_mul_f32_e32 v4, v184, v151  // 003ecc
	v_mov_b32_e32 v5, v4  // 003ed0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[8:9], a[120:121], 0  // 003ed4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[10:11], a[122:123], v[80:83]  // 003edc
	buffer_load_dword v151, v190, s[20:23], 0 offen  // 003ee4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[12:13], a[124:125], v[80:83]  // 003eec
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[14:15], a[126:127], v[80:83]  // 003ef4
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 003efc
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 003f04
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 003f0c
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 003f14
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[0:1], a[128:129], 0  // 003f1c
	s_add_u32 m0, 0x800, s58  // 003f24
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003f2c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[2:3], a[130:131], v[84:87]  // 003f34
	ds_read_b128 a[80:83], v50 offset:14464  // 003f3c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[4:5], a[132:133], v[84:87]  // 003f44
	s_add_u32 m0, 0x900, s58  // 003f4c
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003f54
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[6:7], a[134:135], v[84:87]  // 003f5c
	ds_read_b128 a[84:87], v50 offset:14528  // 003f64
	v_mul_f32_e32 v4, v184, v152  // 003f6c
	v_mov_b32_e32 v5, v4  // 003f70
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[8:9], a[128:129], 0  // 003f74
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[10:11], a[130:131], v[88:91]  // 003f7c
	buffer_load_dword v152, v191, s[20:23], 0 offen  // 003f84
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[12:13], a[132:133], v[88:91]  // 003f8c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[14:15], a[134:135], v[88:91]  // 003f94
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 003f9c
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 003fa4
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 003fac
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 003fb4
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[0:1], a[136:137], 0  // 003fbc
	s_add_u32 m0, 0xa00, s58  // 003fc4
	buffer_load_dword v48, s[4:7], 0 offen lds  // 003fcc
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[2:3], a[138:139], v[92:95]  // 003fd4
	ds_read_b128 a[88:91], v50 offset:14976  // 003fdc
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[4:5], a[140:141], v[92:95]  // 003fe4
	s_add_u32 m0, 0xb00, s58  // 003fec
	buffer_load_dword v49, s[4:7], 0 offen lds  // 003ff4
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[6:7], a[142:143], v[92:95]  // 003ffc
	s_add_u32 s50, 0x200, s42  // 00402c
	s_cmp_lt_u32 s50, s43  // 004034
	s_cselect_b32 s54, s54, 0  // 004038
	ds_read_b128 a[92:95], v50 offset:15040  // 004004
	v_mul_f32_e32 v4, v184, v153  // 00400c
	v_mov_b32_e32 v5, v4  // 004010
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[8:9], a[136:137], 0  // 004014
	s_add_u32 s50, 0x180, s42  // 00403c
	s_cmp_lt_u32 s50, s43  // 004044
	s_cselect_b32 s55, s55, 0  // 004048
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[10:11], a[138:139], v[96:99]  // 00401c
	buffer_load_dword v153, v192, s[20:23], 0 offen  // 004024
	s_add_u32 s50, 0x200, s42  // 00404c
	s_cmp_lt_u32 s50, s43  // 004054
	s_cselect_b32 s56, s56, 0  // 004058
	s_add_u32 s50, 0x180, s42  // 00405c
	s_cmp_lt_u32 s50, s43  // 004064
	s_cselect_b32 s57, s57, 0  // 004068
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[12:13], a[140:141], v[96:99]  // 00406c
	s_add_u32 s4, s54, s4  // 004084
	s_addc_u32 s5, 0, s5  // 004088
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[14:15], a[142:143], v[96:99]  // 004074
	buffer_load_dword v186, v199, s[24:27], 0 offen  // 00407c
	s_sub_u32 s6, s6, s54  // 00408c
	s_add_u32 s8, s55, s8  // 004090
	s_addc_u32 s9, 0, s9  // 004094
	s_sub_u32 s10, s10, s55  // 004098
	s_add_u32 s20, s56, s20  // 00409c
	s_addc_u32 s21, 0, s21  // 0040a0
	s_add_u32 s24, s57, s24  // 0040a4
	s_addc_u32 s25, 0, s25  // 0040a8
	s_sub_u32 s26, s26, s57  // 0040ac
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 0040b0
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 0040b8
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 0040c0
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 0040c8
	s_addk_i32 s42, 0x80  // 0040d0
	s_cmp_lt_i32 s42, s43  // 0040d4
	s_cbranch_scc0 L_49a8  // 0040d8
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 0040e0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[16:17], a[48:49], 0  // 0040e4
	s_add_u32 m0, 0, s59  // 0040ec
	buffer_load_dword v38, s[4:7], 0 offen lds  // 0040f0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[18:19], a[50:51], v[52:55]  // 0040f8
	ds_read_b128 a[96:99], v50 offset:24832  // 004100
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[20:21], a[52:53], v[52:55]  // 004108
	s_add_u32 m0, 0x100, s59  // 004110
	buffer_load_dword v39, s[4:7], 0 offen lds  // 004118
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[22:23], a[54:55], v[52:55]  // 004120
	ds_read_b128 a[100:103], v50 offset:24896  // 004128
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v185, v154  // 004130
	v_mov_b32_e32 v5, v4  // 004134
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[24:25], a[48:49], 0  // 004138
	buffer_load_dwordx4 a[0:3], v34, s[8:11], 0 offen  // 004140
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[26:27], a[50:51], v[56:59]  // 004148
	buffer_load_dword v154, v187, s[20:23], 0 offen  // 004150
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[28:29], a[52:53], v[56:59]  // 004158
	buffer_load_dwordx4 a[4:7], v35, s[8:11], 0 offen  // 004160
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[30:31], a[54:55], v[56:59]  // 004168
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 004170
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 004178
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 004180
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 004188
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[56:57], 0  // 004190
	s_add_u32 m0, 0x200, s59  // 004198
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0041a0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[58:59], v[60:63]  // 0041a8
	ds_read_b128 a[104:107], v50 offset:25344  // 0041b0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[60:61], v[60:63]  // 0041b8
	s_add_u32 m0, 0x300, s59  // 0041c0
	buffer_load_dword v41, s[4:7], 0 offen lds  // 0041c8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[62:63], v[60:63]  // 0041d0
	ds_read_b128 a[108:111], v50 offset:25408  // 0041d8
	v_mul_f32_e32 v4, v185, v155  // 0041e0
	v_mov_b32_e32 v5, v4  // 0041e4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[56:57], 0  // 0041e8
	buffer_load_dwordx4 a[8:11], v36, s[8:11], 0 offen  // 0041f0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[58:59], v[64:67]  // 0041f8
	buffer_load_dword v155, v188, s[20:23], 0 offen  // 004200
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[60:61], v[64:67]  // 004208
	buffer_load_dwordx4 a[12:15], v37, s[8:11], 0 offen  // 004210
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[62:63], v[64:67]  // 004218
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 004220
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 004228
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 004230
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 004238
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[64:65], 0  // 004240
	s_add_u32 m0, 0x400, s59  // 004248
	buffer_load_dword v42, s[4:7], 0 offen lds  // 004250
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[66:67], v[68:71]  // 004258
	ds_read_b128 a[112:115], v50 offset:25856  // 004260
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[68:69], v[68:71]  // 004268
	s_add_u32 m0, 0x500, s59  // 004270
	buffer_load_dword v43, s[4:7], 0 offen lds  // 004278
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[70:71], v[68:71]  // 004280
	ds_read_b128 a[116:119], v50 offset:25920  // 004288
	v_mul_f32_e32 v4, v185, v156  // 004290
	v_mov_b32_e32 v5, v4  // 004294
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[64:65], 0  // 004298
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[66:67], v[72:75]  // 0042a0
	buffer_load_dword v156, v189, s[20:23], 0 offen  // 0042a8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[68:69], v[72:75]  // 0042b0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[70:71], v[72:75]  // 0042b8
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 0042c0
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 0042c8
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 0042d0
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 0042d8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[16:17], a[72:73], 0  // 0042e0
	s_add_u32 m0, 0x600, s59  // 0042e8
	buffer_load_dword v44, s[4:7], 0 offen lds  // 0042f0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[18:19], a[74:75], v[76:79]  // 0042f8
	ds_read_b128 a[120:123], v50 offset:26368  // 004300
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[20:21], a[76:77], v[76:79]  // 004308
	s_add_u32 m0, 0x700, s59  // 004310
	buffer_load_dword v45, s[4:7], 0 offen lds  // 004318
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[22:23], a[78:79], v[76:79]  // 004320
	ds_read_b128 a[124:127], v50 offset:26432  // 004328
	v_mul_f32_e32 v4, v185, v157  // 004330
	v_mov_b32_e32 v5, v4  // 004334
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[24:25], a[72:73], 0  // 004338
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[26:27], a[74:75], v[80:83]  // 004340
	buffer_load_dword v157, v190, s[20:23], 0 offen  // 004348
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[28:29], a[76:77], v[80:83]  // 004350
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[30:31], a[78:79], v[80:83]  // 004358
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 004360
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 004368
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 004370
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 004378
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[16:17], a[80:81], 0  // 004380
	s_add_u32 m0, 0x800, s59  // 004388
	buffer_load_dword v46, s[4:7], 0 offen lds  // 004390
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[18:19], a[82:83], v[84:87]  // 004398
	ds_read_b128 a[128:131], v50 offset:26880  // 0043a0
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[20:21], a[84:85], v[84:87]  // 0043a8
	s_add_u32 m0, 0x900, s59  // 0043b0
	buffer_load_dword v47, s[4:7], 0 offen lds  // 0043b8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[22:23], a[86:87], v[84:87]  // 0043c0
	ds_read_b128 a[132:135], v50 offset:26944  // 0043c8
	v_mul_f32_e32 v4, v185, v158  // 0043d0
	v_mov_b32_e32 v5, v4  // 0043d4
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[24:25], a[80:81], 0  // 0043d8
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[26:27], a[82:83], v[88:91]  // 0043e0
	buffer_load_dword v158, v191, s[20:23], 0 offen  // 0043e8
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[28:29], a[84:85], v[88:91]  // 0043f0
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[30:31], a[86:87], v[88:91]  // 0043f8
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 004400
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 004408
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 004410
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 004418
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[16:17], a[88:89], 0  // 004420
	s_add_u32 m0, 0xa00, s59  // 004428
	buffer_load_dword v48, s[4:7], 0 offen lds  // 004430
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[18:19], a[90:91], v[92:95]  // 004438
	ds_read_b128 a[136:139], v50 offset:27392  // 004440
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[20:21], a[92:93], v[92:95]  // 004448
	s_add_u32 m0, 0xb00, s59  // 004450
	buffer_load_dword v49, s[4:7], 0 offen lds  // 004458
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[22:23], a[94:95], v[92:95]  // 004460
	s_add_u32 s50, 0x200, s42  // 004490
	s_cmp_lt_u32 s50, s43  // 004498
	s_cselect_b32 s54, s54, 0  // 00449c
	ds_read_b128 a[140:143], v50 offset:27456  // 004468
	v_mul_f32_e32 v4, v185, v159  // 004470
	v_mov_b32_e32 v5, v4  // 004474
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[24:25], a[88:89], 0  // 004478
	s_add_u32 s50, 0x180, s42  // 0044a0
	s_cmp_lt_u32 s50, s43  // 0044a8
	s_cselect_b32 s55, s55, 0  // 0044ac
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[26:27], a[90:91], v[96:99]  // 004480
	buffer_load_dword v159, v192, s[20:23], 0 offen  // 004488
	s_add_u32 s50, 0x200, s42  // 0044b0
	s_cmp_lt_u32 s50, s43  // 0044b8
	s_cselect_b32 s56, s56, 0  // 0044bc
	s_add_u32 s50, 0x180, s42  // 0044c0
	s_cmp_lt_u32 s50, s43  // 0044c8
	s_cselect_b32 s57, s57, 0  // 0044cc
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[28:29], a[92:93], v[96:99]  // 0044d0
	s_add_u32 s4, s54, s4  // 0044e8
	s_addc_u32 s5, 0, s5  // 0044ec
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[30:31], a[94:95], v[96:99]  // 0044d8
	buffer_load_dword v184, v199, s[24:27], 0 offen  // 0044e0
	s_sub_u32 s6, s6, s54  // 0044f0
	s_add_u32 s8, s55, s8  // 0044f4
	s_addc_u32 s9, 0, s9  // 0044f8
	s_sub_u32 s10, s10, s55  // 0044fc
	s_add_u32 s20, s56, s20  // 004500
	s_addc_u32 s21, 0, s21  // 004504
	s_add_u32 s24, s57, s24  // 004508
	s_addc_u32 s25, 0, s25  // 00450c
	s_sub_u32 s26, s26, s57  // 004510
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 004514
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 00451c
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 004524
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 00452c
	s_addk_i32 s42, 0x80  // 004534
	s_cmp_lt_i32 s42, s43  // 004538
	s_cbranch_scc0 L_49a8  // 00453c
	s_waitcnt vmcnt(25) & lgkmcnt(0)
	s_barrier  // 004544
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[32:33], a[96:97], 0  // 004548
	s_add_u32 m0, 0, s60  // 004550
	buffer_load_dword v38, s[4:7], 0 offen lds  // 004554
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[34:35], a[98:99], v[52:55]  // 00455c
	ds_read_b128 a[48:51], v50  // 004564
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[36:37], a[100:101], v[52:55]  // 00456c
	s_add_u32 m0, 0x100, s60  // 004574
	buffer_load_dword v39, s[4:7], 0 offen lds  // 00457c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[38:39], a[102:103], v[52:55]  // 004584
	ds_read_b128 a[52:55], v50 offset:64  // 00458c
	s_waitcnt vmcnt(25)
	v_mul_f32_e32 v4, v186, v160  // 004594
	v_mov_b32_e32 v5, v4  // 004598
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[40:41], a[96:97], 0  // 00459c
	buffer_load_dwordx4 a[16:19], v34, s[8:11], 0 offen  // 0045a4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[42:43], a[98:99], v[56:59]  // 0045ac
	buffer_load_dword v160, v187, s[20:23], 0 offen  // 0045b4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[44:45], a[100:101], v[56:59]  // 0045bc
	buffer_load_dwordx4 a[20:23], v35, s[8:11], 0 offen  // 0045c4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[46:47], a[102:103], v[56:59]  // 0045cc
	s_nop 0
	v_pk_fma_f32 v[100:101], v[4:5], v[52:53], v[100:101]  // 0045d4
	v_pk_fma_f32 v[102:103], v[4:5], v[54:55], v[102:103]  // 0045dc
	v_pk_fma_f32 v[104:105], v[4:5], v[56:57], v[104:105]  // 0045e4
	v_pk_fma_f32 v[106:107], v[4:5], v[58:59], v[106:107]  // 0045ec
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[104:105], 0  // 0045f4
	s_add_u32 m0, 0x200, s60  // 0045fc
	buffer_load_dword v40, s[4:7], 0 offen lds  // 004604
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[106:107], v[60:63]  // 00460c
	ds_read_b128 a[56:59], v50 offset:512  // 004614
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[108:109], v[60:63]  // 00461c
	s_add_u32 m0, 0x300, s60  // 004624
	buffer_load_dword v41, s[4:7], 0 offen lds  // 00462c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[110:111], v[60:63]  // 004634
	ds_read_b128 a[60:63], v50 offset:576  // 00463c
	v_mul_f32_e32 v4, v186, v161  // 004644
	v_mov_b32_e32 v5, v4  // 004648
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[104:105], 0  // 00464c
	buffer_load_dwordx4 a[24:27], v36, s[8:11], 0 offen  // 004654
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[106:107], v[64:67]  // 00465c
	buffer_load_dword v161, v188, s[20:23], 0 offen  // 004664
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[108:109], v[64:67]  // 00466c
	buffer_load_dwordx4 a[28:31], v37, s[8:11], 0 offen  // 004674
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[110:111], v[64:67]  // 00467c
	s_nop 0
	v_pk_fma_f32 v[108:109], v[4:5], v[60:61], v[108:109]  // 004684
	v_pk_fma_f32 v[110:111], v[4:5], v[62:63], v[110:111]  // 00468c
	v_pk_fma_f32 v[112:113], v[4:5], v[64:65], v[112:113]  // 004694
	v_pk_fma_f32 v[114:115], v[4:5], v[66:67], v[114:115]  // 00469c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[112:113], 0  // 0046a4
	s_add_u32 m0, 0x400, s60  // 0046ac
	buffer_load_dword v42, s[4:7], 0 offen lds  // 0046b4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[114:115], v[68:71]  // 0046bc
	ds_read_b128 a[64:67], v50 offset:1024  // 0046c4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[116:117], v[68:71]  // 0046cc
	s_add_u32 m0, 0x500, s60  // 0046d4
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0046dc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[118:119], v[68:71]  // 0046e4
	ds_read_b128 a[68:71], v50 offset:1088  // 0046ec
	v_mul_f32_e32 v4, v186, v162  // 0046f4
	v_mov_b32_e32 v5, v4  // 0046f8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[112:113], 0  // 0046fc
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[114:115], v[72:75]  // 004704
	buffer_load_dword v162, v189, s[20:23], 0 offen  // 00470c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[116:117], v[72:75]  // 004714
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[118:119], v[72:75]  // 00471c
	s_nop 0
	v_pk_fma_f32 v[116:117], v[4:5], v[68:69], v[116:117]  // 004724
	v_pk_fma_f32 v[118:119], v[4:5], v[70:71], v[118:119]  // 00472c
	v_pk_fma_f32 v[120:121], v[4:5], v[72:73], v[120:121]  // 004734
	v_pk_fma_f32 v[122:123], v[4:5], v[74:75], v[122:123]  // 00473c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[32:33], a[120:121], 0  // 004744
	s_add_u32 m0, 0x600, s60  // 00474c
	buffer_load_dword v44, s[4:7], 0 offen lds  // 004754
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[34:35], a[122:123], v[76:79]  // 00475c
	ds_read_b128 a[72:75], v50 offset:1536  // 004764
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[36:37], a[124:125], v[76:79]  // 00476c
	s_add_u32 m0, 0x700, s60  // 004774
	buffer_load_dword v45, s[4:7], 0 offen lds  // 00477c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[38:39], a[126:127], v[76:79]  // 004784
	ds_read_b128 a[76:79], v50 offset:1600  // 00478c
	v_mul_f32_e32 v4, v186, v163  // 004794
	v_mov_b32_e32 v5, v4  // 004798
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[40:41], a[120:121], 0  // 00479c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[42:43], a[122:123], v[80:83]  // 0047a4
	buffer_load_dword v163, v190, s[20:23], 0 offen  // 0047ac
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[44:45], a[124:125], v[80:83]  // 0047b4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[46:47], a[126:127], v[80:83]  // 0047bc
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[76:77], v[124:125]  // 0047c4
	v_pk_fma_f32 v[126:127], v[4:5], v[78:79], v[126:127]  // 0047cc
	v_pk_fma_f32 v[128:129], v[4:5], v[80:81], v[128:129]  // 0047d4
	v_pk_fma_f32 v[130:131], v[4:5], v[82:83], v[130:131]  // 0047dc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[32:33], a[128:129], 0  // 0047e4
	s_add_u32 m0, 0x800, s60  // 0047ec
	buffer_load_dword v46, s[4:7], 0 offen lds  // 0047f4
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[34:35], a[130:131], v[84:87]  // 0047fc
	ds_read_b128 a[80:83], v50 offset:2048  // 004804
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[36:37], a[132:133], v[84:87]  // 00480c
	s_add_u32 m0, 0x900, s60  // 004814
	buffer_load_dword v47, s[4:7], 0 offen lds  // 00481c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[38:39], a[134:135], v[84:87]  // 004824
	ds_read_b128 a[84:87], v50 offset:2112  // 00482c
	v_mul_f32_e32 v4, v186, v164  // 004834
	v_mov_b32_e32 v5, v4  // 004838
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[40:41], a[128:129], 0  // 00483c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[42:43], a[130:131], v[88:91]  // 004844
	buffer_load_dword v164, v191, s[20:23], 0 offen  // 00484c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[44:45], a[132:133], v[88:91]  // 004854
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[46:47], a[134:135], v[88:91]  // 00485c
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[84:85], v[132:133]  // 004864
	v_pk_fma_f32 v[134:135], v[4:5], v[86:87], v[134:135]  // 00486c
	v_pk_fma_f32 v[136:137], v[4:5], v[88:89], v[136:137]  // 004874
	v_pk_fma_f32 v[138:139], v[4:5], v[90:91], v[138:139]  // 00487c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[32:33], a[136:137], 0  // 004884
	s_add_u32 m0, 0xa00, s60  // 00488c
	buffer_load_dword v48, s[4:7], 0 offen lds  // 004894
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[34:35], a[138:139], v[92:95]  // 00489c
	ds_read_b128 a[88:91], v50 offset:2560  // 0048a4
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[36:37], a[140:141], v[92:95]  // 0048ac
	s_add_u32 m0, 0xb00, s60  // 0048b4
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0048bc
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[38:39], a[142:143], v[92:95]  // 0048c4
	s_add_u32 s50, 0x200, s42  // 0048f4
	s_cmp_lt_u32 s50, s43  // 0048fc
	s_cselect_b32 s54, s54, 0  // 004900
	ds_read_b128 a[92:95], v50 offset:2624  // 0048cc
	v_mul_f32_e32 v4, v186, v165  // 0048d4
	v_mov_b32_e32 v5, v4  // 0048d8
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[40:41], a[136:137], 0  // 0048dc
	s_add_u32 s50, 0x180, s42  // 004904
	s_cmp_lt_u32 s50, s43  // 00490c
	s_cselect_b32 s55, s55, 0  // 004910
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[42:43], a[138:139], v[96:99]  // 0048e4
	buffer_load_dword v165, v192, s[20:23], 0 offen  // 0048ec
	s_add_u32 s50, 0x200, s42  // 004914
	s_cmp_lt_u32 s50, s43  // 00491c
	s_cselect_b32 s56, s56, 0  // 004920
	s_add_u32 s50, 0x180, s42  // 004924
	s_cmp_lt_u32 s50, s43  // 00492c
	s_cselect_b32 s57, s57, 0  // 004930
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[44:45], a[140:141], v[96:99]  // 004934
	s_add_u32 s4, s54, s4  // 00494c
	s_addc_u32 s5, 0, s5  // 004950
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[46:47], a[142:143], v[96:99]  // 00493c
	buffer_load_dword v185, v199, s[24:27], 0 offen  // 004944
	s_sub_u32 s6, s6, s54  // 004954
	s_add_u32 s8, s55, s8  // 004958
	s_addc_u32 s9, 0, s9  // 00495c
	s_sub_u32 s10, s10, s55  // 004960
	s_add_u32 s20, s56, s20  // 004964
	s_addc_u32 s21, 0, s21  // 004968
	s_add_u32 s24, s57, s24  // 00496c
	s_addc_u32 s25, 0, s25  // 004970
	s_sub_u32 s26, s26, s57  // 004974
	v_pk_fma_f32 v[140:141], v[4:5], v[92:93], v[140:141]  // 004978
	v_pk_fma_f32 v[142:143], v[4:5], v[94:95], v[142:143]  // 004980
	v_pk_fma_f32 v[144:145], v[4:5], v[96:97], v[144:145]  // 004988
	v_pk_fma_f32 v[146:147], v[4:5], v[98:99], v[146:147]  // 004990
	s_addk_i32 s42, 0x80  // 004998
	s_cmp_lt_i32 s42, s43  // 00499c
	s_cbranch_scc0 L_49a8  // 0049a0
	s_branch L_2f4c  // 0049a4
L_49a8:
	s_cmp_eq_u32 s38, 1  // 0049a8
	s_cbranch_scc1 L_4f88  // 0049ac
	v_add_f32_e32 v100, v100, v12  // 0049b0
	v_add_f32_e32 v101, v101, v13  // 0049b4
	v_perm_b32 v52, v101, v100, s48  // 0049b8
	v_add_f32_e32 v102, v102, v14  // 0049c0
	v_add_f32_e32 v103, v103, v15  // 0049c4
	v_perm_b32 v53, v103, v102, s48  // 0049c8
	v_add_f32_e32 v104, v104, v16  // 0049d0
	v_add_f32_e32 v105, v105, v17  // 0049d4
	v_perm_b32 v54, v105, v104, s48  // 0049d8
	v_add_f32_e32 v106, v106, v18  // 0049e0
	v_add_f32_e32 v107, v107, v19  // 0049e4
	v_perm_b32 v55, v107, v106, s48  // 0049e8
	v_add_f32_e32 v108, v108, v12  // 0049f0
	v_add_f32_e32 v109, v109, v13  // 0049f4
	v_perm_b32 v56, v109, v108, s48  // 0049f8
	v_add_f32_e32 v110, v110, v14  // 004a00
	v_add_f32_e32 v111, v111, v15  // 004a04
	v_perm_b32 v57, v111, v110, s48  // 004a08
	v_add_f32_e32 v112, v112, v16  // 004a10
	v_add_f32_e32 v113, v113, v17  // 004a14
	v_perm_b32 v58, v113, v112, s48  // 004a18
	v_add_f32_e32 v114, v114, v18  // 004a20
	v_add_f32_e32 v115, v115, v19  // 004a24
	v_perm_b32 v59, v115, v114, s48  // 004a28
	v_add_f32_e32 v116, v116, v12  // 004a30
	v_add_f32_e32 v117, v117, v13  // 004a34
	v_perm_b32 v60, v117, v116, s48  // 004a38
	v_add_f32_e32 v118, v118, v14  // 004a40
	v_add_f32_e32 v119, v119, v15  // 004a44
	v_perm_b32 v61, v119, v118, s48  // 004a48
	v_add_f32_e32 v120, v120, v16  // 004a50
	v_add_f32_e32 v121, v121, v17  // 004a54
	v_perm_b32 v62, v121, v120, s48  // 004a58
	v_add_f32_e32 v122, v122, v18  // 004a60
	v_add_f32_e32 v123, v123, v19  // 004a64
	v_perm_b32 v63, v123, v122, s48  // 004a68
	v_add_f32_e32 v124, v124, v12  // 004a70
	v_add_f32_e32 v125, v125, v13  // 004a74
	v_perm_b32 v64, v125, v124, s48  // 004a78
	v_add_f32_e32 v126, v126, v14  // 004a80
	v_add_f32_e32 v127, v127, v15  // 004a84
	v_perm_b32 v65, v127, v126, s48  // 004a88
	v_add_f32_e32 v128, v128, v16  // 004a90
	v_add_f32_e32 v129, v129, v17  // 004a94
	v_perm_b32 v66, v129, v128, s48  // 004a98
	v_add_f32_e32 v130, v130, v18  // 004aa0
	v_add_f32_e32 v131, v131, v19  // 004aa4
	v_perm_b32 v67, v131, v130, s48  // 004aa8
	v_add_f32_e32 v132, v132, v12  // 004ab0
	v_add_f32_e32 v133, v133, v13  // 004ab4
	v_perm_b32 v68, v133, v132, s48  // 004ab8
	v_add_f32_e32 v134, v134, v14  // 004ac0
	v_add_f32_e32 v135, v135, v15  // 004ac4
	v_perm_b32 v69, v135, v134, s48  // 004ac8
	v_add_f32_e32 v136, v136, v16  // 004ad0
	v_add_f32_e32 v137, v137, v17  // 004ad4
	v_perm_b32 v70, v137, v136, s48  // 004ad8
	v_add_f32_e32 v138, v138, v18  // 004ae0
	v_add_f32_e32 v139, v139, v19  // 004ae4
	v_perm_b32 v71, v139, v138, s48  // 004ae8
	v_add_f32_e32 v140, v140, v12  // 004af0
	v_add_f32_e32 v141, v141, v13  // 004af4
	v_perm_b32 v72, v141, v140, s48  // 004af8
	v_add_f32_e32 v142, v142, v14  // 004b00
	v_add_f32_e32 v143, v143, v15  // 004b04
	v_perm_b32 v73, v143, v142, s48  // 004b08
	v_add_f32_e32 v144, v144, v16  // 004b10
	v_add_f32_e32 v145, v145, v17  // 004b14
	v_perm_b32 v74, v145, v144, s48  // 004b18
	v_add_f32_e32 v146, v146, v18  // 004b20
	v_add_f32_e32 v147, v147, v19  // 004b24
	v_perm_b32 v75, v147, v146, s48  // 004b28
	v_lshrrev_b32_e32 v4, 4, v0  // 004b30
	v_mul_u32_u24_e32 v50, 34, v4  // 004b34
	v_and_b32_e32 v4, 15, v0  // 004b38
	v_mul_lo_u32 v5, 2, v4  // 004b3c
	v_add_u32_e32 v50, v5, v50  // 004b44
	s_mul_i32 s50, s47, 0x110  // 004b48
	v_add_u32_e32 v50, s50, v50  // 004b50
	v_lshlrev_b32_e32 v50, 2, v50  // 004b54
	v_lshrrev_b32_e32 v4, 1, v0  // 004b58
	v_mul_u32_u24_e32 v38, 34, v4  // 004b5c
	v_and_b32_e32 v5, 1, v0  // 004b60
	v_add_u32_e32 v38, v5, v38  // 004b64
	s_mul_i32 s50, s47, 2  // 004b68
	v_add_u32_e32 v38, s50, v38  // 004b6c
	v_lshlrev_b32_e32 v38, 2, v38  // 004b70
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 004b74
	s_barrier  // 004b78
	ds_write_b64 v50, v[52:53]  // 004b7c
	ds_write_b64 v50, v[54:55] offset:544  // 004b84
	ds_write_b64 v50, v[56:57] offset:4352  // 004b8c
	ds_write_b64 v50, v[58:59] offset:4896  // 004b94
	ds_write_b64 v50, v[60:61] offset:8704  // 004b9c
	ds_write_b64 v50, v[62:63] offset:9248  // 004ba4
	ds_write_b64 v50, v[64:65] offset:13056  // 004bac
	ds_write_b64 v50, v[66:67] offset:13600  // 004bb4
	ds_write_b64 v50, v[68:69] offset:17408  // 004bbc
	ds_write_b64 v50, v[70:71] offset:17952  // 004bc4
	ds_write_b64 v50, v[72:73] offset:21760  // 004bcc
	ds_write_b64 v50, v[74:75] offset:22304  // 004bd4
	s_waitcnt lgkmcnt(0)  // 004bdc
	s_barrier  // 004be0
	ds_read_b32 v52, v38  // 004be4
	ds_read_b32 v53, v38 offset:32  // 004bec
	ds_read_b32 v54, v38 offset:64  // 004bf4
	ds_read_b32 v55, v38 offset:96  // 004bfc
	ds_read_b32 v56, v38 offset:4352  // 004c04
	ds_read_b32 v57, v38 offset:4384  // 004c0c
	ds_read_b32 v58, v38 offset:4416  // 004c14
	ds_read_b32 v59, v38 offset:4448  // 004c1c
	ds_read_b32 v60, v38 offset:8704  // 004c24
	ds_read_b32 v61, v38 offset:8736  // 004c2c
	ds_read_b32 v62, v38 offset:8768  // 004c34
	ds_read_b32 v63, v38 offset:8800  // 004c3c
	ds_read_b32 v64, v38 offset:13056  // 004c44
	ds_read_b32 v65, v38 offset:13088  // 004c4c
	ds_read_b32 v66, v38 offset:13120  // 004c54
	ds_read_b32 v67, v38 offset:13152  // 004c5c
	ds_read_b32 v68, v38 offset:17408  // 004c64
	ds_read_b32 v69, v38 offset:17440  // 004c6c
	ds_read_b32 v70, v38 offset:17472  // 004c74
	ds_read_b32 v71, v38 offset:17504  // 004c7c
	ds_read_b32 v72, v38 offset:21760  // 004c84
	ds_read_b32 v73, v38 offset:21792  // 004c8c
	ds_read_b32 v74, v38 offset:21824  // 004c94
	ds_read_b32 v75, v38 offset:21856  // 004c9c
	s_waitcnt lgkmcnt(0)  // 004ca4
	s_barrier  // 004ca8
	s_mul_i32 s50, s37, 4  // 004cac
	s_mul_i32 s51, s37, 8  // 004cb0
	s_mul_i32 s52, s37, 16  // 004cb4
	v_mov_b32_e32 v4, v26  // 004cb8
	v_mov_b32_e32 v5, 0  // 004cbc
	v_mov_b32_e32 v7, 0  // 004cc0
	v_mov_b32_e32 v9, 0  // 004cc4
	v_mov_b32_e32 v11, 0  // 004cc8
	v_mov_b32_e32 v6, v4  // 004ccc
	v_add_u32_e64 v10, v4, s51  // 004cd0
	s_cmp_ge_u32 s77, s32  // 004cd8
	s_cbranch_scc1 L_5168  // 004cdc
	global_atomic_pk_add_bf16 v6, v52, s[80:81]  // 004ce0
	v_add_u32_e64 v8, v6, s50  // 004ce8
	s_add_i32 s77, s77, 4  // 004cf0
	s_cmp_ge_u32 s77, s32  // 004cf4
	s_cbranch_scc1 L_5168  // 004cf8
	global_atomic_pk_add_bf16 v8, v53, s[80:81]  // 004cfc
	s_add_i32 s77, s77, 4  // 004d04
	s_cmp_ge_u32 s77, s32  // 004d08
	s_cbranch_scc1 L_5168  // 004d0c
	global_atomic_pk_add_bf16 v10, v54, s[80:81]  // 004d10
	v_add_u32_e64 v12, v10, s50  // 004d18
	s_add_i32 s77, s77, 4  // 004d20
	s_cmp_ge_u32 s77, s32  // 004d24
	s_cbranch_scc1 L_5168  // 004d28
	global_atomic_pk_add_bf16 v12, v55, s[80:81]  // 004d2c
	s_add_i32 s77, s77, 4  // 004d34
	v_add_u32_e64 v4, v4, s52  // 004d38
	v_mov_b32_e32 v6, v4  // 004d40
	v_add_u32_e64 v10, v4, s51  // 004d44
	s_cmp_ge_u32 s77, s32  // 004d4c
	s_cbranch_scc1 L_5168  // 004d50
	global_atomic_pk_add_bf16 v6, v56, s[80:81]  // 004d54
	v_add_u32_e64 v8, v6, s50  // 004d5c
	s_add_i32 s77, s77, 4  // 004d64
	s_cmp_ge_u32 s77, s32  // 004d68
	s_cbranch_scc1 L_5168  // 004d6c
	global_atomic_pk_add_bf16 v8, v57, s[80:81]  // 004d70
	s_add_i32 s77, s77, 4  // 004d78
	s_cmp_ge_u32 s77, s32  // 004d7c
	s_cbranch_scc1 L_5168  // 004d80
	global_atomic_pk_add_bf16 v10, v58, s[80:81]  // 004d84
	v_add_u32_e64 v12, v10, s50  // 004d8c
	s_add_i32 s77, s77, 4  // 004d94
	s_cmp_ge_u32 s77, s32  // 004d98
	s_cbranch_scc1 L_5168  // 004d9c
	global_atomic_pk_add_bf16 v12, v59, s[80:81]  // 004da0
	s_add_i32 s77, s77, 4  // 004da8
	v_add_u32_e64 v4, v4, s52  // 004dac
	v_mov_b32_e32 v6, v4  // 004db4
	v_add_u32_e64 v10, v4, s51  // 004db8
	s_cmp_ge_u32 s77, s32  // 004dc0
	s_cbranch_scc1 L_5168  // 004dc4
	global_atomic_pk_add_bf16 v6, v60, s[80:81]  // 004dc8
	v_add_u32_e64 v8, v6, s50  // 004dd0
	s_add_i32 s77, s77, 4  // 004dd8
	s_cmp_ge_u32 s77, s32  // 004ddc
	s_cbranch_scc1 L_5168  // 004de0
	global_atomic_pk_add_bf16 v8, v61, s[80:81]  // 004de4
	s_add_i32 s77, s77, 4  // 004dec
	s_cmp_ge_u32 s77, s32  // 004df0
	s_cbranch_scc1 L_5168  // 004df4
	global_atomic_pk_add_bf16 v10, v62, s[80:81]  // 004df8
	v_add_u32_e64 v12, v10, s50  // 004e00
	s_add_i32 s77, s77, 4  // 004e08
	s_cmp_ge_u32 s77, s32  // 004e0c
	s_cbranch_scc1 L_5168  // 004e10
	global_atomic_pk_add_bf16 v12, v63, s[80:81]  // 004e14
	s_add_i32 s77, s77, 4  // 004e1c
	v_add_u32_e64 v4, v4, s52  // 004e20
	v_mov_b32_e32 v6, v4  // 004e28
	v_add_u32_e64 v10, v4, s51  // 004e2c
	s_cmp_ge_u32 s77, s32  // 004e34
	s_cbranch_scc1 L_5168  // 004e38
	global_atomic_pk_add_bf16 v6, v64, s[80:81]  // 004e3c
	v_add_u32_e64 v8, v6, s50  // 004e44
	s_add_i32 s77, s77, 4  // 004e4c
	s_cmp_ge_u32 s77, s32  // 004e50
	s_cbranch_scc1 L_5168  // 004e54
	global_atomic_pk_add_bf16 v8, v65, s[80:81]  // 004e58
	s_add_i32 s77, s77, 4  // 004e60
	s_cmp_ge_u32 s77, s32  // 004e64
	s_cbranch_scc1 L_5168  // 004e68
	global_atomic_pk_add_bf16 v10, v66, s[80:81]  // 004e6c
	v_add_u32_e64 v12, v10, s50  // 004e74
	s_add_i32 s77, s77, 4  // 004e7c
	s_cmp_ge_u32 s77, s32  // 004e80
	s_cbranch_scc1 L_5168  // 004e84
	global_atomic_pk_add_bf16 v12, v67, s[80:81]  // 004e88
	s_add_i32 s77, s77, 4  // 004e90
	v_add_u32_e64 v4, v4, s52  // 004e94
	v_mov_b32_e32 v6, v4  // 004e9c
	v_add_u32_e64 v10, v4, s51  // 004ea0
	s_cmp_ge_u32 s77, s32  // 004ea8
	s_cbranch_scc1 L_5168  // 004eac
	global_atomic_pk_add_bf16 v6, v68, s[80:81]  // 004eb0
	v_add_u32_e64 v8, v6, s50  // 004eb8
	s_add_i32 s77, s77, 4  // 004ec0
	s_cmp_ge_u32 s77, s32  // 004ec4
	s_cbranch_scc1 L_5168  // 004ec8
	global_atomic_pk_add_bf16 v8, v69, s[80:81]  // 004ecc
	s_add_i32 s77, s77, 4  // 004ed4
	s_cmp_ge_u32 s77, s32  // 004ed8
	s_cbranch_scc1 L_5168  // 004edc
	global_atomic_pk_add_bf16 v10, v70, s[80:81]  // 004ee0
	v_add_u32_e64 v12, v10, s50  // 004ee8
	s_add_i32 s77, s77, 4  // 004ef0
	s_cmp_ge_u32 s77, s32  // 004ef4
	s_cbranch_scc1 L_5168  // 004ef8
	global_atomic_pk_add_bf16 v12, v71, s[80:81]  // 004efc
	s_add_i32 s77, s77, 4  // 004f04
	v_add_u32_e64 v4, v4, s52  // 004f08
	v_mov_b32_e32 v6, v4  // 004f10
	v_add_u32_e64 v10, v4, s51  // 004f14
	s_cmp_ge_u32 s77, s32  // 004f1c
	s_cbranch_scc1 L_5168  // 004f20
	global_atomic_pk_add_bf16 v6, v72, s[80:81]  // 004f24
	v_add_u32_e64 v8, v6, s50  // 004f2c
	s_add_i32 s77, s77, 4  // 004f34
	s_cmp_ge_u32 s77, s32  // 004f38
	s_cbranch_scc1 L_5168  // 004f3c
	global_atomic_pk_add_bf16 v8, v73, s[80:81]  // 004f40
	s_add_i32 s77, s77, 4  // 004f48
	s_cmp_ge_u32 s77, s32  // 004f4c
	s_cbranch_scc1 L_5168  // 004f50
	global_atomic_pk_add_bf16 v10, v74, s[80:81]  // 004f54
	v_add_u32_e64 v12, v10, s50  // 004f5c
	s_add_i32 s77, s77, 4  // 004f64
	s_cmp_ge_u32 s77, s32  // 004f68
	s_cbranch_scc1 L_5168  // 004f6c
	global_atomic_pk_add_bf16 v12, v75, s[80:81]  // 004f70
	s_add_i32 s77, s77, 4  // 004f78
	v_add_u32_e64 v4, v4, s52  // 004f7c
	s_branch L_5168  // 004f84
L_4f88:
	v_add_f32_e32 v100, v100, v12  // 004f88
	v_add_f32_e32 v101, v101, v13  // 004f8c
	v_perm_b32 v52, v101, v100, s48  // 004f90
	v_add_f32_e32 v102, v102, v14  // 004f98
	v_add_f32_e32 v103, v103, v15  // 004f9c
	v_perm_b32 v53, v103, v102, s48  // 004fa0
	buffer_store_dwordx2 v[52:53], v20, s[16:19], 0 offen  // 004fa8
	v_add_f32_e32 v104, v104, v16  // 004fb0
	v_add_f32_e32 v105, v105, v17  // 004fb4
	v_perm_b32 v54, v105, v104, s48  // 004fb8
	v_add_f32_e32 v106, v106, v18  // 004fc0
	v_add_f32_e32 v107, v107, v19  // 004fc4
	v_perm_b32 v55, v107, v106, s48  // 004fc8
	buffer_store_dwordx2 v[54:55], v20, s[16:19], 0 offen offset:32  // 004fd0
	v_add_f32_e32 v108, v108, v12  // 004fd8
	v_add_f32_e32 v109, v109, v13  // 004fdc
	v_perm_b32 v56, v109, v108, s48  // 004fe0
	v_add_f32_e32 v110, v110, v14  // 004fe8
	v_add_f32_e32 v111, v111, v15  // 004fec
	v_perm_b32 v57, v111, v110, s48  // 004ff0
	buffer_store_dwordx2 v[56:57], v21, s[16:19], 0 offen  // 004ff8
	v_add_f32_e32 v112, v112, v16  // 005000
	v_add_f32_e32 v113, v113, v17  // 005004
	v_perm_b32 v58, v113, v112, s48  // 005008
	v_add_f32_e32 v114, v114, v18  // 005010
	v_add_f32_e32 v115, v115, v19  // 005014
	v_perm_b32 v59, v115, v114, s48  // 005018
	buffer_store_dwordx2 v[58:59], v21, s[16:19], 0 offen offset:32  // 005020
	v_add_f32_e32 v116, v116, v12  // 005028
	v_add_f32_e32 v117, v117, v13  // 00502c
	v_perm_b32 v60, v117, v116, s48  // 005030
	v_add_f32_e32 v118, v118, v14  // 005038
	v_add_f32_e32 v119, v119, v15  // 00503c
	v_perm_b32 v61, v119, v118, s48  // 005040
	buffer_store_dwordx2 v[60:61], v22, s[16:19], 0 offen  // 005048
	v_add_f32_e32 v120, v120, v16  // 005050
	v_add_f32_e32 v121, v121, v17  // 005054
	v_perm_b32 v62, v121, v120, s48  // 005058
	v_add_f32_e32 v122, v122, v18  // 005060
	v_add_f32_e32 v123, v123, v19  // 005064
	v_perm_b32 v63, v123, v122, s48  // 005068
	buffer_store_dwordx2 v[62:63], v22, s[16:19], 0 offen offset:32  // 005070
	v_add_f32_e32 v124, v124, v12  // 005078
	v_add_f32_e32 v125, v125, v13  // 00507c
	v_perm_b32 v64, v125, v124, s48  // 005080
	v_add_f32_e32 v126, v126, v14  // 005088
	v_add_f32_e32 v127, v127, v15  // 00508c
	v_perm_b32 v65, v127, v126, s48  // 005090
	buffer_store_dwordx2 v[64:65], v23, s[16:19], 0 offen  // 005098
	v_add_f32_e32 v128, v128, v16  // 0050a0
	v_add_f32_e32 v129, v129, v17  // 0050a4
	v_perm_b32 v66, v129, v128, s48  // 0050a8
	v_add_f32_e32 v130, v130, v18  // 0050b0
	v_add_f32_e32 v131, v131, v19  // 0050b4
	v_perm_b32 v67, v131, v130, s48  // 0050b8
	buffer_store_dwordx2 v[66:67], v23, s[16:19], 0 offen offset:32  // 0050c0
	v_add_f32_e32 v132, v132, v12  // 0050c8
	v_add_f32_e32 v133, v133, v13  // 0050cc
	v_perm_b32 v68, v133, v132, s48  // 0050d0
	v_add_f32_e32 v134, v134, v14  // 0050d8
	v_add_f32_e32 v135, v135, v15  // 0050dc
	v_perm_b32 v69, v135, v134, s48  // 0050e0
	buffer_store_dwordx2 v[68:69], v24, s[16:19], 0 offen  // 0050e8
	v_add_f32_e32 v136, v136, v16  // 0050f0
	v_add_f32_e32 v137, v137, v17  // 0050f4
	v_perm_b32 v70, v137, v136, s48  // 0050f8
	v_add_f32_e32 v138, v138, v18  // 005100
	v_add_f32_e32 v139, v139, v19  // 005104
	v_perm_b32 v71, v139, v138, s48  // 005108
	buffer_store_dwordx2 v[70:71], v24, s[16:19], 0 offen offset:32  // 005110
	v_add_f32_e32 v140, v140, v12  // 005118
	v_add_f32_e32 v141, v141, v13  // 00511c
	v_perm_b32 v72, v141, v140, s48  // 005120
	v_add_f32_e32 v142, v142, v14  // 005128
	v_add_f32_e32 v143, v143, v15  // 00512c
	v_perm_b32 v73, v143, v142, s48  // 005130
	buffer_store_dwordx2 v[72:73], v25, s[16:19], 0 offen  // 005138
	v_add_f32_e32 v144, v144, v16  // 005140
	v_add_f32_e32 v145, v145, v17  // 005144
	v_perm_b32 v74, v145, v144, s48  // 005148
	v_add_f32_e32 v146, v146, v18  // 005150
	v_add_f32_e32 v147, v147, v19  // 005154
	v_perm_b32 v75, v147, v146, s48  // 005158
	buffer_store_dwordx2 v[74:75], v25, s[16:19], 0 offen offset:32  // 005160
L_5168:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 005168
	s_endpgm  // 00516c
.Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E:
	.size _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E, .Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E-_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E
	.amdhsa_group_segment_fixed_size 65536
	.amdhsa_private_segment_fixed_size 0
	.amdhsa_kernarg_size 0
	.amdhsa_accum_offset 256
	.amdhsa_tg_split 0
	.amdhsa_next_free_vgpr 512
	.amdhsa_reserve_vcc 0
	.amdhsa_reserve_xnack_mask 1
	.amdhsa_next_free_sgpr 98
	.amdhsa_float_round_mode_32 0
	.amdhsa_float_round_mode_16_64 0
	.amdhsa_float_denorm_mode_32 0
	.amdhsa_float_denorm_mode_16_64 3
	.amdhsa_dx10_clamp 0
	.amdhsa_ieee_mode 0
	.amdhsa_fp16_overflow 0
	.amdhsa_enable_private_segment 0
	.amdhsa_system_sgpr_workgroup_id_x 1
	.amdhsa_system_sgpr_workgroup_id_y 1
	.amdhsa_system_sgpr_workgroup_id_z 1
	.amdhsa_system_sgpr_workgroup_info 0
	.amdhsa_system_vgpr_workitem_id 0
	.amdhsa_exception_fp_ieee_invalid_op 0
	.amdhsa_exception_fp_denorm_src 0
	.amdhsa_exception_fp_ieee_div_zero 0
	.amdhsa_exception_fp_ieee_overflow 0
	.amdhsa_exception_fp_ieee_underflow 0
	.amdhsa_exception_fp_ieee_inexact 0
	.amdhsa_exception_int_div_zero 0
	.amdhsa_user_sgpr_dispatch_ptr 0
	.amdhsa_user_sgpr_queue_ptr 0
	.amdhsa_user_sgpr_kernarg_segment_ptr 1
	.amdhsa_user_sgpr_dispatch_id 0
	.amdhsa_user_sgpr_private_segment_size 0
	.amdhsa_uses_dynamic_stack 0
.end_amdhsa_kernel

	.amdgpu_metadata
---
amdhsa.kernels:
  - .args:
      - .actual_access:  read_write
        .address_space:  global
        .name:           C
        .offset:         0
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         8
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .actual_access:  read_only
        .address_space:  global
        .name:           A
        .offset:         16
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         24
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .actual_access:  read_only
        .address_space:  global
        .name:           B
        .offset:         32
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         40
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .actual_access:  read_only
        .address_space:  global
        .name:           SA
        .offset:         48
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         56
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .actual_access:  read_only
        .address_space:  global
        .name:           SB
        .offset:         64
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         72
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .actual_access:  read_only
        .address_space:  global
        .name:           BIAS
        .offset:         80
        .size:           8
        .value_kind:     global_buffer
      - .name:           pad
        .offset:         88
        .size:           8
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           M
        .offset:         96
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         100
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         104
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         108
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           Ndim
        .offset:         112
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         116
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         120
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         124
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           K
        .offset:         128
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         132
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         136
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         140
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           PA
        .offset:         144
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         148
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         152
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         156
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           PB
        .offset:         160
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         164
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         168
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         172
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           PC
        .offset:         176
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         180
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         184
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         188
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           KS
        .offset:         192
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         196
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         200
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         204
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           scale_m
        .offset:         208
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         212
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         216
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         220
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           scale_n
        .offset:         224
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         228
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         232
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         236
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           scale_k
        .offset:         240
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         244
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         248
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
      - .name:           pad
        .offset:         252
        .size:           4
        .value_kind:     by_value
        .value_type:     fp32
    .group_segment_fixed_size: 65536
    .kernarg_segment_align: 4
    .kernarg_segment_size: 256
    .max_flat_workgroup_size: 256
    .name:           _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_96x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
