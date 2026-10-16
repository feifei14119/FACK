// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_80x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E
	.protected _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E
	.p2align 8
	.type _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E,@function
_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E:
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
	s_mul_i32 s50, s45, 0x50  // 00258c
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
	s_mul_i32 s50, s45, 0x50  // 0025c4
	s_sub_i32 s51, s32, s50  // 0025cc
	s_cmp_lt_u32 s51, 0x50  // 0025d0
	s_cselect_b32 s50, s51, 0x50  // 0025d8
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
	s_mul_i32 s50, 0x50, s45  // 0026a0
	s_mul_hi_u32 s52, 4, s50  // 0026a8
	s_mul_i32 s51, 4, s50  // 0026ac
	s_add_u32 s20, s20, s51  // 0026b0
	s_addc_u32 s21, s21, s52  // 0026b4
	s_sub_i32 s51, s32, s50  // 0026b8
	s_cmp_lt_u32 s51, 0x50  // 0026bc
	s_cselect_b32 s50, s51, 0x50  // 0026c4
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
	v_and_b32_e64 v161, v0, 15  // 002704
	v_lshlrev_b32_e32 v161, 2, v161  // 00270c
	s_mov_b32 s50, 64  // 002710
	v_add_u32_e64 v162, v161, s50  // 002714
	s_mov_b32 s50, 0x80  // 00271c
	v_add_u32_e64 v163, v161, s50  // 002724
	s_mov_b32 s50, 0xc0  // 00272c
	v_add_u32_e64 v164, v161, s50  // 002734
	s_mov_b32 s50, 0x100  // 00273c
	v_add_u32_e64 v165, v161, s50  // 002744
	s_mul_i32 s51, s41, s44  // 00274c
	s_mul_hi_u32 s52, 4, s51  // 002750
	s_add_u32 s25, s25, s52  // 002754
	s_mul_i32 s52, 4, s51  // 002758
	s_add_u32 s24, s24, s52  // 00275c
	s_addc_u32 s25, s25, 0  // 002760
	s_lshr_b32 s50, s76, 7  // 002764
	s_mul_i32 s50, s50, s75  // 002768
	s_lshl_b32 s50, s50, 2  // 00276c
	s_add_u32 s24, s24, s50  // 002770
	s_addc_u32 s25, s25, 0  // 002774
	s_sub_u32 s26, s26, s50  // 002778
	v_mov_b32_e32 v171, 0  // 00277c
	v_lshrrev_b32_e32 v4, 5, v0  // 002780
	v_lshlrev_b32_e32 v4, 2, v4  // 002784
	v_mul_i32_i24_e32 v4, s35, v4  // 002788
	v_and_b32_e32 v36, 31, v0  // 00278c
	v_lshlrev_b32_e32 v36, 2, v36  // 002790
	s_mul_i32 s50, 0x50, s45  // 002794
	s_sub_i32 s51, s32, s50  // 00279c
	s_cmp_lt_u32 s51, 0x50  // 0027a0
	s_cselect_b32 s51, s51, 0x50  // 0027a8
	s_mul_i32 s52, s35, s50  // 0027b0
	s_mul_hi_u32 s50, s35, s50  // 0027b4
	s_add_u32 s4, s4, s52  // 0027b8
	s_addc_u32 s5, s5, s50  // 0027bc
	s_mul_i32 s50, s35, s51  // 0027c0
	s_mov_b32 s6, s50  // 0027c4
	s_mov_b32 s7, 0x20000  // 0027c8
	s_mul_i32 s51, s76, s75  // 0027d0
	s_add_u32 s4, s51, s4  // 0027d4
	s_addc_u32 s5, 0, s5  // 0027d8
	s_sub_u32 s6, s6, s51  // 0027dc
	s_mul_i32 s50, s35, s47  // 0027e0
	v_add3_u32 v36, v4, v36, s50  // 0027e4
	s_lshl_b32 s50, s35, 3  // 0027ec
	v_add_u32_e32 v37, s50, v36  // 0027f0
	v_add_u32_e32 v38, s50, v37  // 0027f4
	v_add_u32_e32 v39, s50, v38  // 0027f8
	v_add_u32_e32 v40, s50, v39  // 0027fc
	v_add_u32_e32 v41, s50, v40  // 002800
	v_add_u32_e32 v42, s50, v41  // 002804
	v_add_u32_e32 v43, s50, v42  // 002808
	v_add_u32_e32 v44, s50, v43  // 00280c
	v_add_u32_e32 v45, s50, v44  // 002810
	s_mov_b32 s54, 0x80  // 002814
	s_mul_i32 s56, s32, 4  // 00281c
	s_mov_b32 s57, 4  // 002820
	s_mov_b32 s50, 0x50  // 002824
	s_lshr_b32 s50, s50, 2  // 00282c
	s_mul_i32 s50, s50, 32  // 002830
	s_mov_b32 s51, 8  // 002834
	s_add_u32 s50, s50, s51  // 002838
	v_lshrrev_b32_e32 v4, 4, v0  // 00283c
	v_and_b32_e32 v5, 15, v0  // 002840
	v_and_b32_e32 v6, 3, v5  // 002844
	v_lshrrev_b32_e32 v7, 2, v5  // 002848
	v_lshlrev_b32_e32 v4, 2, v4  // 00284c
	v_mul_lo_u32 v6, v6, s50  // 002850
	v_lshlrev_b32_e32 v7, 5, v7  // 002858
	v_add_u32_e32 v4, v4, v6  // 00285c
	v_add_u32_e32 v4, v4, v7  // 002860
	v_lshlrev_b32_e32 v46, 2, v4  // 002864
	s_mul_i32 s50, 0xa20, s47  // 002868
	s_add_u32 s58, 0, s50  // 002870
	s_add_u32 s59, 0x2880, s58  // 002874
	s_add_u32 s60, 0x2880, s59  // 00287c
	s_mov_b32 s55, 0x800  // 002884
	s_mul_i32 s49, 0x80, s44  // 00288c
	s_sub_i32 s51, s33, s49  // 002894
	s_cmp_lt_u32 s51, 0x80  // 002898
	s_cselect_b32 s50, s51, 0x80  // 0028a0
	s_mul_i32 s51, s36, s49  // 0028a8
	s_mul_hi_u32 s52, s36, s49  // 0028ac
	s_add_u32 s8, s8, s51  // 0028b0
	s_addc_u32 s9, s9, s52  // 0028b4
	s_mul_i32 s51, s36, s50  // 0028b8
	s_mov_b32 s10, s51  // 0028bc
	s_mov_b32 s11, 0x20000  // 0028c0
	s_lshr_b32 s51, s76, 7  // 0028c8
	s_mul_i32 s50, s55, s75  // 0028cc
	s_mul_i32 s50, s51, s50  // 0028d0
	s_add_u32 s8, s50, s8  // 0028d4
	s_addc_u32 s9, 0, s9  // 0028d8
	s_sub_u32 s10, s10, s50  // 0028dc
	s_lshl_b32 s50, s47, 5  // 0028e0
	s_mul_i32 s50, s36, s50  // 0028e4
	v_lshlrev_b32_e32 v32, 4, v0  // 0028e8
	v_add_u32_e32 v32, s50, v32  // 0028ec
	s_mov_b32 s50, 0x400  // 0028f0
	v_add_u32_e64 v33, v32, s50  // 0028f8
	s_mul_i32 s50, s36, 16  // 002900
	v_add_u32_e64 v34, v32, s50  // 002904
	v_add_u32_e64 v35, v33, s50  // 00290c
	s_add_u32 m0, 0, s58  // 002914
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002918
	s_add_u32 m0, 0x100, s58  // 002920
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002928
	s_add_u32 m0, 0x200, s58  // 002930
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002938
	s_add_u32 m0, 0x300, s58  // 002940
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002948
	s_add_u32 m0, 0x400, s58  // 002950
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002958
	s_add_u32 m0, 0x500, s58  // 002960
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002968
	s_add_u32 m0, 0x600, s58  // 002970
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002978
	s_add_u32 m0, 0x700, s58  // 002980
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002988
	s_add_u32 m0, 0x800, s58  // 002990
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002998
	s_add_u32 m0, 0x900, s58  // 0029a0
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0029a8
	s_mov_b32 s53, 0  // 0029b0
	s_add_u32 s50, 0x80, s53  // 0029b4
	s_cmp_lt_u32 s50, s34  // 0029bc
	s_cselect_b32 s54, s54, 0  // 0029c0
	s_add_u32 s4, s54, s4  // 0029c4
	s_addc_u32 s5, 0, s5  // 0029c8
	s_sub_u32 s6, s6, s54  // 0029cc
	buffer_load_dword v128, v161, s[20:23], 0 offen  // 0029d0
	buffer_load_dword v129, v162, s[20:23], 0 offen  // 0029d8
	buffer_load_dword v130, v163, s[20:23], 0 offen  // 0029e0
	buffer_load_dword v131, v164, s[20:23], 0 offen  // 0029e8
	buffer_load_dword v132, v165, s[20:23], 0 offen  // 0029f0
	s_add_u32 s50, 0x80, s53  // 0029f8
	s_cmp_lt_u32 s50, s34  // 002a00
	s_cselect_b32 s56, s56, 0  // 002a04
	s_add_u32 s20, s56, s20  // 002a08
	s_addc_u32 s21, 0, s21  // 002a0c
	v_mov_b32_e32 v88, 0  // 002a10
	v_mov_b32_e32 v89, 0  // 002a14
	v_mov_b32_e32 v90, 0  // 002a18
	v_mov_b32_e32 v91, 0  // 002a1c
	v_mov_b32_e32 v92, 0  // 002a20
	v_mov_b32_e32 v93, 0  // 002a24
	v_mov_b32_e32 v94, 0  // 002a28
	v_mov_b32_e32 v95, 0  // 002a2c
	buffer_load_dwordx4 a[0:3], v32, s[8:11], 0 offen  // 002a30
	buffer_load_dwordx4 a[4:7], v33, s[8:11], 0 offen  // 002a38
	buffer_load_dwordx4 a[8:11], v34, s[8:11], 0 offen  // 002a40
	buffer_load_dwordx4 a[12:15], v35, s[8:11], 0 offen  // 002a48
	s_mov_b32 s53, 0  // 002a50
	s_add_u32 s50, 0x80, s53  // 002a54
	s_cmp_lt_u32 s50, s34  // 002a5c
	s_cselect_b32 s55, s55, 0  // 002a60
	s_add_u32 s8, s55, s8  // 002a64
	s_addc_u32 s9, 0, s9  // 002a68
	s_sub_u32 s10, s10, s55  // 002a6c
	buffer_load_dword v158, v171, s[24:27], 0 offen  // 002a70
	s_add_u32 s50, 0x80, s53  // 002a78
	s_cmp_lt_u32 s50, s34  // 002a80
	s_cselect_b32 s57, s57, 0  // 002a84
	s_add_u32 s24, s57, s24  // 002a88
	s_addc_u32 s25, 0, s25  // 002a8c
	s_sub_u32 s26, s26, s57  // 002a90
	s_add_u32 m0, 0, s59  // 002a94
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002a98
	s_add_u32 m0, 0x100, s59  // 002aa0
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002aa8
	s_add_u32 m0, 0x200, s59  // 002ab0
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002ab8
	s_add_u32 m0, 0x300, s59  // 002ac0
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002ac8
	s_add_u32 m0, 0x400, s59  // 002ad0
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002ad8
	s_add_u32 m0, 0x500, s59  // 002ae0
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002ae8
	s_add_u32 m0, 0x600, s59  // 002af0
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002af8
	s_add_u32 m0, 0x700, s59  // 002b00
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002b08
	s_add_u32 m0, 0x800, s59  // 002b10
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002b18
	s_add_u32 m0, 0x900, s59  // 002b20
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002b28
	s_mov_b32 s53, 0x80  // 002b30
	s_add_u32 s50, 0x80, s53  // 002b38
	s_cmp_lt_u32 s50, s34  // 002b40
	s_cselect_b32 s54, s54, 0  // 002b44
	s_add_u32 s4, s54, s4  // 002b48
	s_addc_u32 s5, 0, s5  // 002b4c
	s_sub_u32 s6, s6, s54  // 002b50
	buffer_load_dword v133, v161, s[20:23], 0 offen  // 002b54
	buffer_load_dword v134, v162, s[20:23], 0 offen  // 002b5c
	buffer_load_dword v135, v163, s[20:23], 0 offen  // 002b64
	buffer_load_dword v136, v164, s[20:23], 0 offen  // 002b6c
	buffer_load_dword v137, v165, s[20:23], 0 offen  // 002b74
	s_add_u32 s50, 0x80, s53  // 002b7c
	s_cmp_lt_u32 s50, s34  // 002b84
	s_cselect_b32 s56, s56, 0  // 002b88
	s_add_u32 s20, s56, s20  // 002b8c
	s_addc_u32 s21, 0, s21  // 002b90
	v_mov_b32_e32 v96, 0  // 002b94
	v_mov_b32_e32 v97, 0  // 002b98
	v_mov_b32_e32 v98, 0  // 002b9c
	v_mov_b32_e32 v99, 0  // 002ba0
	v_mov_b32_e32 v100, 0  // 002ba4
	v_mov_b32_e32 v101, 0  // 002ba8
	v_mov_b32_e32 v102, 0  // 002bac
	v_mov_b32_e32 v103, 0  // 002bb0
	buffer_load_dwordx4 a[16:19], v32, s[8:11], 0 offen  // 002bb4
	buffer_load_dwordx4 a[20:23], v33, s[8:11], 0 offen  // 002bbc
	buffer_load_dwordx4 a[24:27], v34, s[8:11], 0 offen  // 002bc4
	buffer_load_dwordx4 a[28:31], v35, s[8:11], 0 offen  // 002bcc
	s_mov_b32 s53, 0x80  // 002bd4
	s_add_u32 s50, 0x80, s53  // 002bdc
	s_cmp_lt_u32 s50, s34  // 002be4
	s_cselect_b32 s55, s55, 0  // 002be8
	s_add_u32 s8, s55, s8  // 002bec
	s_addc_u32 s9, 0, s9  // 002bf0
	s_sub_u32 s10, s10, s55  // 002bf4
	buffer_load_dword v159, v171, s[24:27], 0 offen  // 002bf8
	s_add_u32 s50, 0x80, s53  // 002c00
	s_cmp_lt_u32 s50, s34  // 002c08
	s_cselect_b32 s57, s57, 0  // 002c0c
	s_add_u32 s24, s57, s24  // 002c10
	s_addc_u32 s25, 0, s25  // 002c14
	s_sub_u32 s26, s26, s57  // 002c18
	s_add_u32 m0, 0, s60  // 002c1c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002c20
	s_add_u32 m0, 0x100, s60  // 002c28
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002c30
	s_add_u32 m0, 0x200, s60  // 002c38
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002c40
	s_add_u32 m0, 0x300, s60  // 002c48
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002c50
	s_add_u32 m0, 0x400, s60  // 002c58
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002c60
	s_add_u32 m0, 0x500, s60  // 002c68
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002c70
	s_add_u32 m0, 0x600, s60  // 002c78
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002c80
	s_add_u32 m0, 0x700, s60  // 002c88
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002c90
	s_add_u32 m0, 0x800, s60  // 002c98
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002ca0
	s_add_u32 m0, 0x900, s60  // 002ca8
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002cb0
	s_mov_b32 s53, 0x100  // 002cb8
	s_add_u32 s50, 0x80, s53  // 002cc0
	s_cmp_lt_u32 s50, s34  // 002cc8
	s_cselect_b32 s54, s54, 0  // 002ccc
	s_add_u32 s4, s54, s4  // 002cd0
	s_addc_u32 s5, 0, s5  // 002cd4
	s_sub_u32 s6, s6, s54  // 002cd8
	buffer_load_dword v138, v161, s[20:23], 0 offen  // 002cdc
	buffer_load_dword v139, v162, s[20:23], 0 offen  // 002ce4
	buffer_load_dword v140, v163, s[20:23], 0 offen  // 002cec
	buffer_load_dword v141, v164, s[20:23], 0 offen  // 002cf4
	buffer_load_dword v142, v165, s[20:23], 0 offen  // 002cfc
	s_add_u32 s50, 0x80, s53  // 002d04
	s_cmp_lt_u32 s50, s34  // 002d0c
	s_cselect_b32 s56, s56, 0  // 002d10
	s_add_u32 s20, s56, s20  // 002d14
	s_addc_u32 s21, 0, s21  // 002d18
	v_mov_b32_e32 v104, 0  // 002d1c
	v_mov_b32_e32 v105, 0  // 002d20
	v_mov_b32_e32 v106, 0  // 002d24
	v_mov_b32_e32 v107, 0  // 002d28
	v_mov_b32_e32 v108, 0  // 002d2c
	v_mov_b32_e32 v109, 0  // 002d30
	v_mov_b32_e32 v110, 0  // 002d34
	v_mov_b32_e32 v111, 0  // 002d38
	v_mov_b32_e32 v112, 0  // 002d3c
	v_mov_b32_e32 v113, 0  // 002d40
	v_mov_b32_e32 v114, 0  // 002d44
	v_mov_b32_e32 v115, 0  // 002d48
	v_mov_b32_e32 v116, 0  // 002d4c
	v_mov_b32_e32 v117, 0  // 002d50
	v_mov_b32_e32 v118, 0  // 002d54
	v_mov_b32_e32 v119, 0  // 002d58
	v_mov_b32_e32 v120, 0  // 002d5c
	v_mov_b32_e32 v121, 0  // 002d60
	v_mov_b32_e32 v122, 0  // 002d64
	v_mov_b32_e32 v123, 0  // 002d68
	v_mov_b32_e32 v124, 0  // 002d6c
	v_mov_b32_e32 v125, 0  // 002d70
	v_mov_b32_e32 v126, 0  // 002d74
	v_mov_b32_e32 v127, 0  // 002d78
	s_mov_b32 s43, s34  // 002d7c
	s_mov_b32 s42, 0  // 002d80
	s_waitcnt vmcnt(40)  // 002d84
	s_barrier  // 002d88
	ds_read_b128 a[48:51], v46  // 002d8c
	ds_read_b128 a[52:55], v46 offset:64  // 002d94
	ds_read_b128 a[56:59], v46 offset:512  // 002d9c
	ds_read_b128 a[60:63], v46 offset:576  // 002da4
	ds_read_b128 a[64:67], v46 offset:1024  // 002dac
	ds_read_b128 a[68:71], v46 offset:1088  // 002db4
	ds_read_b128 a[72:75], v46 offset:1536  // 002dbc
	ds_read_b128 a[76:79], v46 offset:1600  // 002dc4
	ds_read_b128 a[80:83], v46 offset:2048  // 002dcc
	ds_read_b128 a[84:87], v46 offset:2112  // 002dd4
	s_mov_b32 s50, 0  // 002ddc
	s_mov_b32 s51, 1.0  // 002de0
	s_cmp_eq_u32 s50, s75  // 002de4
	s_cselect_b32 s50, s51, 0  // 002de8
	v_mul_f32_e64 v12, v12, s50  // 002dec
	v_mul_f32_e64 v13, v13, s50  // 002df4
	v_mul_f32_e64 v14, v14, s50  // 002dfc
	v_mul_f32_e64 v15, v15, s50  // 002e04
	v_mul_f32_e64 v16, v16, s50  // 002e0c
	v_mul_f32_e64 v17, v17, s50  // 002e14
	v_mul_f32_e64 v18, v18, s50  // 002e1c
	v_mul_f32_e64 v19, v19, s50  // 002e24
	v_and_b32_e64 v20, v0, 15  // 002e2c
	v_mul_lo_u32 v20, v20, s37  // 002e34
	v_lshrrev_b32_e32 v4, 4, v0  // 002e3c
	v_mul_i32_i24_e32 v4, 8, v4  // 002e40
	v_add_u32_e32 v20, v4, v20  // 002e44
	s_mul_i32 s50, 32, s47  // 002e48
	s_mul_i32 s50, 2, s50  // 002e4c
	v_add_u32_e32 v20, s50, v20  // 002e50
	s_mul_i32 s50, 16, s37  // 002e54
	v_add_u32_e32 v21, s50, v20  // 002e58
	v_add_u32_e32 v22, s50, v21  // 002e5c
	v_add_u32_e32 v23, s50, v22  // 002e60
	v_add_u32_e32 v24, s50, v23  // 002e64
	s_mul_i32 s50, s47, s37  // 002e68
	v_lshlrev_b32_e32 v5, 2, v0  // 002e6c
	v_add_u32_e32 v25, s50, v5  // 002e70
	s_mul_i32 s50, s45, 0x50  // 002e74
	s_add_i32 s77, s50, s47  // 002e7c
	s_cmp_lt_i32 s42, s43  // 002e80
	s_cbranch_scc0 L_4524  // 002e84
L_2e88:
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 002e8c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[0:1], a[48:49], 0  // 002e90
	s_add_u32 m0, 0, s58  // 002e98
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002e9c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[2:3], a[50:51], v[48:51]  // 002ea4
	ds_read_b128 a[88:91], v46 offset:10368  // 002eac
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[4:5], a[52:53], v[48:51]  // 002eb4
	s_add_u32 m0, 0x100, s58  // 002ebc
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002ec4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[6:7], a[54:55], v[48:51]  // 002ecc
	ds_read_b128 a[92:95], v46 offset:10432  // 002ed4
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v158, v128  // 002edc
	v_mov_b32_e32 v5, v4  // 002ee0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[8:9], a[48:49], 0  // 002ee4
	buffer_load_dwordx4 a[32:35], v32, s[8:11], 0 offen  // 002eec
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[10:11], a[50:51], v[52:55]  // 002ef4
	buffer_load_dword v128, v161, s[20:23], 0 offen  // 002efc
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[12:13], a[52:53], v[52:55]  // 002f04
	buffer_load_dwordx4 a[36:39], v33, s[8:11], 0 offen  // 002f0c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[14:15], a[54:55], v[52:55]  // 002f14
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 002f1c
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 002f24
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 002f2c
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 002f34
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[0:1], a[56:57], 0  // 002f3c
	s_add_u32 m0, 0x200, s58  // 002f44
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002f4c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[2:3], a[58:59], v[56:59]  // 002f54
	ds_read_b128 a[96:99], v46 offset:10880  // 002f5c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[4:5], a[60:61], v[56:59]  // 002f64
	s_add_u32 m0, 0x300, s58  // 002f6c
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002f74
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[6:7], a[62:63], v[56:59]  // 002f7c
	ds_read_b128 a[100:103], v46 offset:10944  // 002f84
	v_mul_f32_e32 v4, v158, v129  // 002f8c
	v_mov_b32_e32 v5, v4  // 002f90
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[8:9], a[56:57], 0  // 002f94
	buffer_load_dwordx4 a[40:43], v34, s[8:11], 0 offen  // 002f9c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[10:11], a[58:59], v[60:63]  // 002fa4
	buffer_load_dword v129, v162, s[20:23], 0 offen  // 002fac
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[12:13], a[60:61], v[60:63]  // 002fb4
	buffer_load_dwordx4 a[44:47], v35, s[8:11], 0 offen  // 002fbc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[14:15], a[62:63], v[60:63]  // 002fc4
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 002fcc
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 002fd4
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 002fdc
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 002fe4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[0:1], a[64:65], 0  // 002fec
	s_add_u32 m0, 0x400, s58  // 002ff4
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002ffc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[2:3], a[66:67], v[64:67]  // 003004
	ds_read_b128 a[104:107], v46 offset:11392  // 00300c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[4:5], a[68:69], v[64:67]  // 003014
	s_add_u32 m0, 0x500, s58  // 00301c
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003024
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[6:7], a[70:71], v[64:67]  // 00302c
	ds_read_b128 a[108:111], v46 offset:11456  // 003034
	v_mul_f32_e32 v4, v158, v130  // 00303c
	v_mov_b32_e32 v5, v4  // 003040
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[8:9], a[64:65], 0  // 003044
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[10:11], a[66:67], v[68:71]  // 00304c
	buffer_load_dword v130, v163, s[20:23], 0 offen  // 003054
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[12:13], a[68:69], v[68:71]  // 00305c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[14:15], a[70:71], v[68:71]  // 003064
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 00306c
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 003074
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 00307c
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 003084
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[0:1], a[72:73], 0  // 00308c
	s_add_u32 m0, 0x600, s58  // 003094
	buffer_load_dword v42, s[4:7], 0 offen lds  // 00309c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[2:3], a[74:75], v[72:75]  // 0030a4
	ds_read_b128 a[112:115], v46 offset:11904  // 0030ac
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[4:5], a[76:77], v[72:75]  // 0030b4
	s_add_u32 m0, 0x700, s58  // 0030bc
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0030c4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[6:7], a[78:79], v[72:75]  // 0030cc
	ds_read_b128 a[116:119], v46 offset:11968  // 0030d4
	v_mul_f32_e32 v4, v158, v131  // 0030dc
	v_mov_b32_e32 v5, v4  // 0030e0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[8:9], a[72:73], 0  // 0030e4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[10:11], a[74:75], v[76:79]  // 0030ec
	buffer_load_dword v131, v164, s[20:23], 0 offen  // 0030f4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[12:13], a[76:77], v[76:79]  // 0030fc
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[14:15], a[78:79], v[76:79]  // 003104
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 00310c
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 003114
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 00311c
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 003124
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[0:1], a[80:81], 0  // 00312c
	s_add_u32 m0, 0x800, s58  // 003134
	buffer_load_dword v44, s[4:7], 0 offen lds  // 00313c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[2:3], a[82:83], v[80:83]  // 003144
	ds_read_b128 a[120:123], v46 offset:12416  // 00314c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[4:5], a[84:85], v[80:83]  // 003154
	s_add_u32 m0, 0x900, s58  // 00315c
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003164
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[6:7], a[86:87], v[80:83]  // 00316c
	s_add_u32 s50, 0x200, s42  // 00319c
	s_cmp_lt_u32 s50, s43  // 0031a4
	s_cselect_b32 s54, s54, 0  // 0031a8
	ds_read_b128 a[124:127], v46 offset:12480  // 003174
	v_mul_f32_e32 v4, v158, v132  // 00317c
	v_mov_b32_e32 v5, v4  // 003180
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[8:9], a[80:81], 0  // 003184
	s_add_u32 s50, 0x180, s42  // 0031ac
	s_cmp_lt_u32 s50, s43  // 0031b4
	s_cselect_b32 s55, s55, 0  // 0031b8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[10:11], a[82:83], v[84:87]  // 00318c
	buffer_load_dword v132, v165, s[20:23], 0 offen  // 003194
	s_add_u32 s50, 0x200, s42  // 0031bc
	s_cmp_lt_u32 s50, s43  // 0031c4
	s_cselect_b32 s56, s56, 0  // 0031c8
	s_add_u32 s50, 0x180, s42  // 0031cc
	s_cmp_lt_u32 s50, s43  // 0031d4
	s_cselect_b32 s57, s57, 0  // 0031d8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[12:13], a[84:85], v[84:87]  // 0031dc
	s_add_u32 s4, s54, s4  // 0031f4
	s_addc_u32 s5, 0, s5  // 0031f8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[14:15], a[86:87], v[84:87]  // 0031e4
	buffer_load_dword v160, v171, s[24:27], 0 offen  // 0031ec
	s_sub_u32 s6, s6, s54  // 0031fc
	s_add_u32 s8, s55, s8  // 003200
	s_addc_u32 s9, 0, s9  // 003204
	s_sub_u32 s10, s10, s55  // 003208
	s_add_u32 s20, s56, s20  // 00320c
	s_addc_u32 s21, 0, s21  // 003210
	s_add_u32 s24, s57, s24  // 003214
	s_addc_u32 s25, 0, s25  // 003218
	s_sub_u32 s26, s26, s57  // 00321c
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 003220
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 003228
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 003230
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 003238
	s_addk_i32 s42, 0x80  // 003240
	s_cmp_lt_i32 s42, s43  // 003244
	s_cbranch_scc0 L_4524  // 003248
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 003250
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[16:17], a[88:89], 0  // 003254
	s_add_u32 m0, 0, s59  // 00325c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003260
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[18:19], a[90:91], v[48:51]  // 003268
	ds_read_b128 a[48:51], v46 offset:20736  // 003270
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[20:21], a[92:93], v[48:51]  // 003278
	s_add_u32 m0, 0x100, s59  // 003280
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003288
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[22:23], a[94:95], v[48:51]  // 003290
	ds_read_b128 a[52:55], v46 offset:20800  // 003298
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v159, v133  // 0032a0
	v_mov_b32_e32 v5, v4  // 0032a4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[24:25], a[88:89], 0  // 0032a8
	buffer_load_dwordx4 a[0:3], v32, s[8:11], 0 offen  // 0032b0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[26:27], a[90:91], v[52:55]  // 0032b8
	buffer_load_dword v133, v161, s[20:23], 0 offen  // 0032c0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[28:29], a[92:93], v[52:55]  // 0032c8
	buffer_load_dwordx4 a[4:7], v33, s[8:11], 0 offen  // 0032d0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[30:31], a[94:95], v[52:55]  // 0032d8
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 0032e0
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 0032e8
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 0032f0
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 0032f8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[16:17], a[96:97], 0  // 003300
	s_add_u32 m0, 0x200, s59  // 003308
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003310
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[18:19], a[98:99], v[56:59]  // 003318
	ds_read_b128 a[56:59], v46 offset:21248  // 003320
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[20:21], a[100:101], v[56:59]  // 003328
	s_add_u32 m0, 0x300, s59  // 003330
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003338
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[22:23], a[102:103], v[56:59]  // 003340
	ds_read_b128 a[60:63], v46 offset:21312  // 003348
	v_mul_f32_e32 v4, v159, v134  // 003350
	v_mov_b32_e32 v5, v4  // 003354
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[24:25], a[96:97], 0  // 003358
	buffer_load_dwordx4 a[8:11], v34, s[8:11], 0 offen  // 003360
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[26:27], a[98:99], v[60:63]  // 003368
	buffer_load_dword v134, v162, s[20:23], 0 offen  // 003370
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[28:29], a[100:101], v[60:63]  // 003378
	buffer_load_dwordx4 a[12:15], v35, s[8:11], 0 offen  // 003380
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[30:31], a[102:103], v[60:63]  // 003388
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 003390
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 003398
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 0033a0
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 0033a8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[16:17], a[104:105], 0  // 0033b0
	s_add_u32 m0, 0x400, s59  // 0033b8
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0033c0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[18:19], a[106:107], v[64:67]  // 0033c8
	ds_read_b128 a[64:67], v46 offset:21760  // 0033d0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[20:21], a[108:109], v[64:67]  // 0033d8
	s_add_u32 m0, 0x500, s59  // 0033e0
	buffer_load_dword v41, s[4:7], 0 offen lds  // 0033e8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[22:23], a[110:111], v[64:67]  // 0033f0
	ds_read_b128 a[68:71], v46 offset:21824  // 0033f8
	v_mul_f32_e32 v4, v159, v135  // 003400
	v_mov_b32_e32 v5, v4  // 003404
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[24:25], a[104:105], 0  // 003408
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[26:27], a[106:107], v[68:71]  // 003410
	buffer_load_dword v135, v163, s[20:23], 0 offen  // 003418
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[28:29], a[108:109], v[68:71]  // 003420
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[30:31], a[110:111], v[68:71]  // 003428
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 003430
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 003438
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 003440
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 003448
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[16:17], a[112:113], 0  // 003450
	s_add_u32 m0, 0x600, s59  // 003458
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003460
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[18:19], a[114:115], v[72:75]  // 003468
	ds_read_b128 a[72:75], v46 offset:22272  // 003470
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[20:21], a[116:117], v[72:75]  // 003478
	s_add_u32 m0, 0x700, s59  // 003480
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003488
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[22:23], a[118:119], v[72:75]  // 003490
	ds_read_b128 a[76:79], v46 offset:22336  // 003498
	v_mul_f32_e32 v4, v159, v136  // 0034a0
	v_mov_b32_e32 v5, v4  // 0034a4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[24:25], a[112:113], 0  // 0034a8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[26:27], a[114:115], v[76:79]  // 0034b0
	buffer_load_dword v136, v164, s[20:23], 0 offen  // 0034b8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[28:29], a[116:117], v[76:79]  // 0034c0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[30:31], a[118:119], v[76:79]  // 0034c8
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 0034d0
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 0034d8
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 0034e0
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 0034e8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[16:17], a[120:121], 0  // 0034f0
	s_add_u32 m0, 0x800, s59  // 0034f8
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003500
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[18:19], a[122:123], v[80:83]  // 003508
	ds_read_b128 a[80:83], v46 offset:22784  // 003510
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[20:21], a[124:125], v[80:83]  // 003518
	s_add_u32 m0, 0x900, s59  // 003520
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003528
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[22:23], a[126:127], v[80:83]  // 003530
	s_add_u32 s50, 0x200, s42  // 003560
	s_cmp_lt_u32 s50, s43  // 003568
	s_cselect_b32 s54, s54, 0  // 00356c
	ds_read_b128 a[84:87], v46 offset:22848  // 003538
	v_mul_f32_e32 v4, v159, v137  // 003540
	v_mov_b32_e32 v5, v4  // 003544
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[24:25], a[120:121], 0  // 003548
	s_add_u32 s50, 0x180, s42  // 003570
	s_cmp_lt_u32 s50, s43  // 003578
	s_cselect_b32 s55, s55, 0  // 00357c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[26:27], a[122:123], v[84:87]  // 003550
	buffer_load_dword v137, v165, s[20:23], 0 offen  // 003558
	s_add_u32 s50, 0x200, s42  // 003580
	s_cmp_lt_u32 s50, s43  // 003588
	s_cselect_b32 s56, s56, 0  // 00358c
	s_add_u32 s50, 0x180, s42  // 003590
	s_cmp_lt_u32 s50, s43  // 003598
	s_cselect_b32 s57, s57, 0  // 00359c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[28:29], a[124:125], v[84:87]  // 0035a0
	s_add_u32 s4, s54, s4  // 0035b8
	s_addc_u32 s5, 0, s5  // 0035bc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[30:31], a[126:127], v[84:87]  // 0035a8
	buffer_load_dword v158, v171, s[24:27], 0 offen  // 0035b0
	s_sub_u32 s6, s6, s54  // 0035c0
	s_add_u32 s8, s55, s8  // 0035c4
	s_addc_u32 s9, 0, s9  // 0035c8
	s_sub_u32 s10, s10, s55  // 0035cc
	s_add_u32 s20, s56, s20  // 0035d0
	s_addc_u32 s21, 0, s21  // 0035d4
	s_add_u32 s24, s57, s24  // 0035d8
	s_addc_u32 s25, 0, s25  // 0035dc
	s_sub_u32 s26, s26, s57  // 0035e0
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 0035e4
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 0035ec
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 0035f4
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 0035fc
	s_addk_i32 s42, 0x80  // 003604
	s_cmp_lt_i32 s42, s43  // 003608
	s_cbranch_scc0 L_4524  // 00360c
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 003614
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[32:33], a[48:49], 0  // 003618
	s_add_u32 m0, 0, s60  // 003620
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003624
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[34:35], a[50:51], v[48:51]  // 00362c
	ds_read_b128 a[88:91], v46  // 003634
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[36:37], a[52:53], v[48:51]  // 00363c
	s_add_u32 m0, 0x100, s60  // 003644
	buffer_load_dword v37, s[4:7], 0 offen lds  // 00364c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[38:39], a[54:55], v[48:51]  // 003654
	ds_read_b128 a[92:95], v46 offset:64  // 00365c
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v160, v138  // 003664
	v_mov_b32_e32 v5, v4  // 003668
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[40:41], a[48:49], 0  // 00366c
	buffer_load_dwordx4 a[16:19], v32, s[8:11], 0 offen  // 003674
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[42:43], a[50:51], v[52:55]  // 00367c
	buffer_load_dword v138, v161, s[20:23], 0 offen  // 003684
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[44:45], a[52:53], v[52:55]  // 00368c
	buffer_load_dwordx4 a[20:23], v33, s[8:11], 0 offen  // 003694
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[46:47], a[54:55], v[52:55]  // 00369c
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 0036a4
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 0036ac
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 0036b4
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 0036bc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[32:33], a[56:57], 0  // 0036c4
	s_add_u32 m0, 0x200, s60  // 0036cc
	buffer_load_dword v38, s[4:7], 0 offen lds  // 0036d4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[34:35], a[58:59], v[56:59]  // 0036dc
	ds_read_b128 a[96:99], v46 offset:512  // 0036e4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[36:37], a[60:61], v[56:59]  // 0036ec
	s_add_u32 m0, 0x300, s60  // 0036f4
	buffer_load_dword v39, s[4:7], 0 offen lds  // 0036fc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[38:39], a[62:63], v[56:59]  // 003704
	ds_read_b128 a[100:103], v46 offset:576  // 00370c
	v_mul_f32_e32 v4, v160, v139  // 003714
	v_mov_b32_e32 v5, v4  // 003718
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[40:41], a[56:57], 0  // 00371c
	buffer_load_dwordx4 a[24:27], v34, s[8:11], 0 offen  // 003724
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[42:43], a[58:59], v[60:63]  // 00372c
	buffer_load_dword v139, v162, s[20:23], 0 offen  // 003734
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[44:45], a[60:61], v[60:63]  // 00373c
	buffer_load_dwordx4 a[28:31], v35, s[8:11], 0 offen  // 003744
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[46:47], a[62:63], v[60:63]  // 00374c
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 003754
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 00375c
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 003764
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 00376c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[32:33], a[64:65], 0  // 003774
	s_add_u32 m0, 0x400, s60  // 00377c
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003784
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[34:35], a[66:67], v[64:67]  // 00378c
	ds_read_b128 a[104:107], v46 offset:1024  // 003794
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[36:37], a[68:69], v[64:67]  // 00379c
	s_add_u32 m0, 0x500, s60  // 0037a4
	buffer_load_dword v41, s[4:7], 0 offen lds  // 0037ac
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[38:39], a[70:71], v[64:67]  // 0037b4
	ds_read_b128 a[108:111], v46 offset:1088  // 0037bc
	v_mul_f32_e32 v4, v160, v140  // 0037c4
	v_mov_b32_e32 v5, v4  // 0037c8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[40:41], a[64:65], 0  // 0037cc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[42:43], a[66:67], v[68:71]  // 0037d4
	buffer_load_dword v140, v163, s[20:23], 0 offen  // 0037dc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[44:45], a[68:69], v[68:71]  // 0037e4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[46:47], a[70:71], v[68:71]  // 0037ec
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 0037f4
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 0037fc
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 003804
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 00380c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[32:33], a[72:73], 0  // 003814
	s_add_u32 m0, 0x600, s60  // 00381c
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003824
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[34:35], a[74:75], v[72:75]  // 00382c
	ds_read_b128 a[112:115], v46 offset:1536  // 003834
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[36:37], a[76:77], v[72:75]  // 00383c
	s_add_u32 m0, 0x700, s60  // 003844
	buffer_load_dword v43, s[4:7], 0 offen lds  // 00384c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[38:39], a[78:79], v[72:75]  // 003854
	ds_read_b128 a[116:119], v46 offset:1600  // 00385c
	v_mul_f32_e32 v4, v160, v141  // 003864
	v_mov_b32_e32 v5, v4  // 003868
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[40:41], a[72:73], 0  // 00386c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[42:43], a[74:75], v[76:79]  // 003874
	buffer_load_dword v141, v164, s[20:23], 0 offen  // 00387c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[44:45], a[76:77], v[76:79]  // 003884
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[46:47], a[78:79], v[76:79]  // 00388c
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 003894
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 00389c
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 0038a4
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 0038ac
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[32:33], a[80:81], 0  // 0038b4
	s_add_u32 m0, 0x800, s60  // 0038bc
	buffer_load_dword v44, s[4:7], 0 offen lds  // 0038c4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[34:35], a[82:83], v[80:83]  // 0038cc
	ds_read_b128 a[120:123], v46 offset:2048  // 0038d4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[36:37], a[84:85], v[80:83]  // 0038dc
	s_add_u32 m0, 0x900, s60  // 0038e4
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0038ec
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[38:39], a[86:87], v[80:83]  // 0038f4
	s_add_u32 s50, 0x200, s42  // 003924
	s_cmp_lt_u32 s50, s43  // 00392c
	s_cselect_b32 s54, s54, 0  // 003930
	ds_read_b128 a[124:127], v46 offset:2112  // 0038fc
	v_mul_f32_e32 v4, v160, v142  // 003904
	v_mov_b32_e32 v5, v4  // 003908
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[40:41], a[80:81], 0  // 00390c
	s_add_u32 s50, 0x180, s42  // 003934
	s_cmp_lt_u32 s50, s43  // 00393c
	s_cselect_b32 s55, s55, 0  // 003940
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[42:43], a[82:83], v[84:87]  // 003914
	buffer_load_dword v142, v165, s[20:23], 0 offen  // 00391c
	s_add_u32 s50, 0x200, s42  // 003944
	s_cmp_lt_u32 s50, s43  // 00394c
	s_cselect_b32 s56, s56, 0  // 003950
	s_add_u32 s50, 0x180, s42  // 003954
	s_cmp_lt_u32 s50, s43  // 00395c
	s_cselect_b32 s57, s57, 0  // 003960
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[44:45], a[84:85], v[84:87]  // 003964
	s_add_u32 s4, s54, s4  // 00397c
	s_addc_u32 s5, 0, s5  // 003980
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[46:47], a[86:87], v[84:87]  // 00396c
	buffer_load_dword v159, v171, s[24:27], 0 offen  // 003974
	s_sub_u32 s6, s6, s54  // 003984
	s_add_u32 s8, s55, s8  // 003988
	s_addc_u32 s9, 0, s9  // 00398c
	s_sub_u32 s10, s10, s55  // 003990
	s_add_u32 s20, s56, s20  // 003994
	s_addc_u32 s21, 0, s21  // 003998
	s_add_u32 s24, s57, s24  // 00399c
	s_addc_u32 s25, 0, s25  // 0039a0
	s_sub_u32 s26, s26, s57  // 0039a4
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 0039a8
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 0039b0
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 0039b8
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 0039c0
	s_addk_i32 s42, 0x80  // 0039c8
	s_cmp_lt_i32 s42, s43  // 0039cc
	s_cbranch_scc0 L_4524  // 0039d0
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 0039d8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[0:1], a[88:89], 0  // 0039dc
	s_add_u32 m0, 0, s58  // 0039e4
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0039e8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[2:3], a[90:91], v[48:51]  // 0039f0
	ds_read_b128 a[48:51], v46 offset:10368  // 0039f8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[4:5], a[92:93], v[48:51]  // 003a00
	s_add_u32 m0, 0x100, s58  // 003a08
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003a10
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[6:7], a[94:95], v[48:51]  // 003a18
	ds_read_b128 a[52:55], v46 offset:10432  // 003a20
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v158, v128  // 003a28
	v_mov_b32_e32 v5, v4  // 003a2c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[8:9], a[88:89], 0  // 003a30
	buffer_load_dwordx4 a[32:35], v32, s[8:11], 0 offen  // 003a38
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[10:11], a[90:91], v[52:55]  // 003a40
	buffer_load_dword v128, v161, s[20:23], 0 offen  // 003a48
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[12:13], a[92:93], v[52:55]  // 003a50
	buffer_load_dwordx4 a[36:39], v33, s[8:11], 0 offen  // 003a58
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[14:15], a[94:95], v[52:55]  // 003a60
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 003a68
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 003a70
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 003a78
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 003a80
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[0:1], a[96:97], 0  // 003a88
	s_add_u32 m0, 0x200, s58  // 003a90
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003a98
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[2:3], a[98:99], v[56:59]  // 003aa0
	ds_read_b128 a[56:59], v46 offset:10880  // 003aa8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[4:5], a[100:101], v[56:59]  // 003ab0
	s_add_u32 m0, 0x300, s58  // 003ab8
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003ac0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[6:7], a[102:103], v[56:59]  // 003ac8
	ds_read_b128 a[60:63], v46 offset:10944  // 003ad0
	v_mul_f32_e32 v4, v158, v129  // 003ad8
	v_mov_b32_e32 v5, v4  // 003adc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[8:9], a[96:97], 0  // 003ae0
	buffer_load_dwordx4 a[40:43], v34, s[8:11], 0 offen  // 003ae8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[10:11], a[98:99], v[60:63]  // 003af0
	buffer_load_dword v129, v162, s[20:23], 0 offen  // 003af8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[12:13], a[100:101], v[60:63]  // 003b00
	buffer_load_dwordx4 a[44:47], v35, s[8:11], 0 offen  // 003b08
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[14:15], a[102:103], v[60:63]  // 003b10
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 003b18
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 003b20
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 003b28
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 003b30
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[0:1], a[104:105], 0  // 003b38
	s_add_u32 m0, 0x400, s58  // 003b40
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003b48
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[2:3], a[106:107], v[64:67]  // 003b50
	ds_read_b128 a[64:67], v46 offset:11392  // 003b58
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[4:5], a[108:109], v[64:67]  // 003b60
	s_add_u32 m0, 0x500, s58  // 003b68
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003b70
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[6:7], a[110:111], v[64:67]  // 003b78
	ds_read_b128 a[68:71], v46 offset:11456  // 003b80
	v_mul_f32_e32 v4, v158, v130  // 003b88
	v_mov_b32_e32 v5, v4  // 003b8c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[8:9], a[104:105], 0  // 003b90
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[10:11], a[106:107], v[68:71]  // 003b98
	buffer_load_dword v130, v163, s[20:23], 0 offen  // 003ba0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[12:13], a[108:109], v[68:71]  // 003ba8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[14:15], a[110:111], v[68:71]  // 003bb0
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 003bb8
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 003bc0
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 003bc8
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 003bd0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[0:1], a[112:113], 0  // 003bd8
	s_add_u32 m0, 0x600, s58  // 003be0
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003be8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[2:3], a[114:115], v[72:75]  // 003bf0
	ds_read_b128 a[72:75], v46 offset:11904  // 003bf8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[4:5], a[116:117], v[72:75]  // 003c00
	s_add_u32 m0, 0x700, s58  // 003c08
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003c10
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[6:7], a[118:119], v[72:75]  // 003c18
	ds_read_b128 a[76:79], v46 offset:11968  // 003c20
	v_mul_f32_e32 v4, v158, v131  // 003c28
	v_mov_b32_e32 v5, v4  // 003c2c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[8:9], a[112:113], 0  // 003c30
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[10:11], a[114:115], v[76:79]  // 003c38
	buffer_load_dword v131, v164, s[20:23], 0 offen  // 003c40
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[12:13], a[116:117], v[76:79]  // 003c48
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[14:15], a[118:119], v[76:79]  // 003c50
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 003c58
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 003c60
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 003c68
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 003c70
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[0:1], a[120:121], 0  // 003c78
	s_add_u32 m0, 0x800, s58  // 003c80
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003c88
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[2:3], a[122:123], v[80:83]  // 003c90
	ds_read_b128 a[80:83], v46 offset:12416  // 003c98
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[4:5], a[124:125], v[80:83]  // 003ca0
	s_add_u32 m0, 0x900, s58  // 003ca8
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003cb0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[6:7], a[126:127], v[80:83]  // 003cb8
	s_add_u32 s50, 0x200, s42  // 003ce8
	s_cmp_lt_u32 s50, s43  // 003cf0
	s_cselect_b32 s54, s54, 0  // 003cf4
	ds_read_b128 a[84:87], v46 offset:12480  // 003cc0
	v_mul_f32_e32 v4, v158, v132  // 003cc8
	v_mov_b32_e32 v5, v4  // 003ccc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[8:9], a[120:121], 0  // 003cd0
	s_add_u32 s50, 0x180, s42  // 003cf8
	s_cmp_lt_u32 s50, s43  // 003d00
	s_cselect_b32 s55, s55, 0  // 003d04
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[10:11], a[122:123], v[84:87]  // 003cd8
	buffer_load_dword v132, v165, s[20:23], 0 offen  // 003ce0
	s_add_u32 s50, 0x200, s42  // 003d08
	s_cmp_lt_u32 s50, s43  // 003d10
	s_cselect_b32 s56, s56, 0  // 003d14
	s_add_u32 s50, 0x180, s42  // 003d18
	s_cmp_lt_u32 s50, s43  // 003d20
	s_cselect_b32 s57, s57, 0  // 003d24
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[12:13], a[124:125], v[84:87]  // 003d28
	s_add_u32 s4, s54, s4  // 003d40
	s_addc_u32 s5, 0, s5  // 003d44
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[14:15], a[126:127], v[84:87]  // 003d30
	buffer_load_dword v160, v171, s[24:27], 0 offen  // 003d38
	s_sub_u32 s6, s6, s54  // 003d48
	s_add_u32 s8, s55, s8  // 003d4c
	s_addc_u32 s9, 0, s9  // 003d50
	s_sub_u32 s10, s10, s55  // 003d54
	s_add_u32 s20, s56, s20  // 003d58
	s_addc_u32 s21, 0, s21  // 003d5c
	s_add_u32 s24, s57, s24  // 003d60
	s_addc_u32 s25, 0, s25  // 003d64
	s_sub_u32 s26, s26, s57  // 003d68
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 003d6c
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 003d74
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 003d7c
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 003d84
	s_addk_i32 s42, 0x80  // 003d8c
	s_cmp_lt_i32 s42, s43  // 003d90
	s_cbranch_scc0 L_4524  // 003d94
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 003d9c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[16:17], a[48:49], 0  // 003da0
	s_add_u32 m0, 0, s59  // 003da8
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003dac
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[18:19], a[50:51], v[48:51]  // 003db4
	ds_read_b128 a[88:91], v46 offset:20736  // 003dbc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[20:21], a[52:53], v[48:51]  // 003dc4
	s_add_u32 m0, 0x100, s59  // 003dcc
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003dd4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[22:23], a[54:55], v[48:51]  // 003ddc
	ds_read_b128 a[92:95], v46 offset:20800  // 003de4
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v159, v133  // 003dec
	v_mov_b32_e32 v5, v4  // 003df0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[24:25], a[48:49], 0  // 003df4
	buffer_load_dwordx4 a[0:3], v32, s[8:11], 0 offen  // 003dfc
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[26:27], a[50:51], v[52:55]  // 003e04
	buffer_load_dword v133, v161, s[20:23], 0 offen  // 003e0c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[28:29], a[52:53], v[52:55]  // 003e14
	buffer_load_dwordx4 a[4:7], v33, s[8:11], 0 offen  // 003e1c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[30:31], a[54:55], v[52:55]  // 003e24
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 003e2c
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 003e34
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 003e3c
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 003e44
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[16:17], a[56:57], 0  // 003e4c
	s_add_u32 m0, 0x200, s59  // 003e54
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003e5c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[18:19], a[58:59], v[56:59]  // 003e64
	ds_read_b128 a[96:99], v46 offset:21248  // 003e6c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[20:21], a[60:61], v[56:59]  // 003e74
	s_add_u32 m0, 0x300, s59  // 003e7c
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003e84
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[22:23], a[62:63], v[56:59]  // 003e8c
	ds_read_b128 a[100:103], v46 offset:21312  // 003e94
	v_mul_f32_e32 v4, v159, v134  // 003e9c
	v_mov_b32_e32 v5, v4  // 003ea0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[24:25], a[56:57], 0  // 003ea4
	buffer_load_dwordx4 a[8:11], v34, s[8:11], 0 offen  // 003eac
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[26:27], a[58:59], v[60:63]  // 003eb4
	buffer_load_dword v134, v162, s[20:23], 0 offen  // 003ebc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[28:29], a[60:61], v[60:63]  // 003ec4
	buffer_load_dwordx4 a[12:15], v35, s[8:11], 0 offen  // 003ecc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[30:31], a[62:63], v[60:63]  // 003ed4
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 003edc
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 003ee4
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 003eec
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 003ef4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[16:17], a[64:65], 0  // 003efc
	s_add_u32 m0, 0x400, s59  // 003f04
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003f0c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[18:19], a[66:67], v[64:67]  // 003f14
	ds_read_b128 a[104:107], v46 offset:21760  // 003f1c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[20:21], a[68:69], v[64:67]  // 003f24
	s_add_u32 m0, 0x500, s59  // 003f2c
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003f34
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[22:23], a[70:71], v[64:67]  // 003f3c
	ds_read_b128 a[108:111], v46 offset:21824  // 003f44
	v_mul_f32_e32 v4, v159, v135  // 003f4c
	v_mov_b32_e32 v5, v4  // 003f50
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[24:25], a[64:65], 0  // 003f54
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[26:27], a[66:67], v[68:71]  // 003f5c
	buffer_load_dword v135, v163, s[20:23], 0 offen  // 003f64
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[28:29], a[68:69], v[68:71]  // 003f6c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[30:31], a[70:71], v[68:71]  // 003f74
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 003f7c
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 003f84
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 003f8c
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 003f94
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[16:17], a[72:73], 0  // 003f9c
	s_add_u32 m0, 0x600, s59  // 003fa4
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003fac
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[18:19], a[74:75], v[72:75]  // 003fb4
	ds_read_b128 a[112:115], v46 offset:22272  // 003fbc
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[20:21], a[76:77], v[72:75]  // 003fc4
	s_add_u32 m0, 0x700, s59  // 003fcc
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003fd4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[22:23], a[78:79], v[72:75]  // 003fdc
	ds_read_b128 a[116:119], v46 offset:22336  // 003fe4
	v_mul_f32_e32 v4, v159, v136  // 003fec
	v_mov_b32_e32 v5, v4  // 003ff0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[24:25], a[72:73], 0  // 003ff4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[26:27], a[74:75], v[76:79]  // 003ffc
	buffer_load_dword v136, v164, s[20:23], 0 offen  // 004004
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[28:29], a[76:77], v[76:79]  // 00400c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[30:31], a[78:79], v[76:79]  // 004014
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 00401c
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 004024
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 00402c
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 004034
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[16:17], a[80:81], 0  // 00403c
	s_add_u32 m0, 0x800, s59  // 004044
	buffer_load_dword v44, s[4:7], 0 offen lds  // 00404c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[18:19], a[82:83], v[80:83]  // 004054
	ds_read_b128 a[120:123], v46 offset:22784  // 00405c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[20:21], a[84:85], v[80:83]  // 004064
	s_add_u32 m0, 0x900, s59  // 00406c
	buffer_load_dword v45, s[4:7], 0 offen lds  // 004074
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[22:23], a[86:87], v[80:83]  // 00407c
	s_add_u32 s50, 0x200, s42  // 0040ac
	s_cmp_lt_u32 s50, s43  // 0040b4
	s_cselect_b32 s54, s54, 0  // 0040b8
	ds_read_b128 a[124:127], v46 offset:22848  // 004084
	v_mul_f32_e32 v4, v159, v137  // 00408c
	v_mov_b32_e32 v5, v4  // 004090
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[24:25], a[80:81], 0  // 004094
	s_add_u32 s50, 0x180, s42  // 0040bc
	s_cmp_lt_u32 s50, s43  // 0040c4
	s_cselect_b32 s55, s55, 0  // 0040c8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[26:27], a[82:83], v[84:87]  // 00409c
	buffer_load_dword v137, v165, s[20:23], 0 offen  // 0040a4
	s_add_u32 s50, 0x200, s42  // 0040cc
	s_cmp_lt_u32 s50, s43  // 0040d4
	s_cselect_b32 s56, s56, 0  // 0040d8
	s_add_u32 s50, 0x180, s42  // 0040dc
	s_cmp_lt_u32 s50, s43  // 0040e4
	s_cselect_b32 s57, s57, 0  // 0040e8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[28:29], a[84:85], v[84:87]  // 0040ec
	s_add_u32 s4, s54, s4  // 004104
	s_addc_u32 s5, 0, s5  // 004108
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[30:31], a[86:87], v[84:87]  // 0040f4
	buffer_load_dword v158, v171, s[24:27], 0 offen  // 0040fc
	s_sub_u32 s6, s6, s54  // 00410c
	s_add_u32 s8, s55, s8  // 004110
	s_addc_u32 s9, 0, s9  // 004114
	s_sub_u32 s10, s10, s55  // 004118
	s_add_u32 s20, s56, s20  // 00411c
	s_addc_u32 s21, 0, s21  // 004120
	s_add_u32 s24, s57, s24  // 004124
	s_addc_u32 s25, 0, s25  // 004128
	s_sub_u32 s26, s26, s57  // 00412c
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 004130
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 004138
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 004140
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 004148
	s_addk_i32 s42, 0x80  // 004150
	s_cmp_lt_i32 s42, s43  // 004154
	s_cbranch_scc0 L_4524  // 004158
	s_waitcnt vmcnt(22) & lgkmcnt(0)
	s_barrier  // 004160
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[32:33], a[88:89], 0  // 004164
	s_add_u32 m0, 0, s60  // 00416c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 004170
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[34:35], a[90:91], v[48:51]  // 004178
	ds_read_b128 a[48:51], v46  // 004180
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[36:37], a[92:93], v[48:51]  // 004188
	s_add_u32 m0, 0x100, s60  // 004190
	buffer_load_dword v37, s[4:7], 0 offen lds  // 004198
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[38:39], a[94:95], v[48:51]  // 0041a0
	ds_read_b128 a[52:55], v46 offset:64  // 0041a8
	s_waitcnt vmcnt(22)
	v_mul_f32_e32 v4, v160, v138  // 0041b0
	v_mov_b32_e32 v5, v4  // 0041b4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[40:41], a[88:89], 0  // 0041b8
	buffer_load_dwordx4 a[16:19], v32, s[8:11], 0 offen  // 0041c0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[42:43], a[90:91], v[52:55]  // 0041c8
	buffer_load_dword v138, v161, s[20:23], 0 offen  // 0041d0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[44:45], a[92:93], v[52:55]  // 0041d8
	buffer_load_dwordx4 a[20:23], v33, s[8:11], 0 offen  // 0041e0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[46:47], a[94:95], v[52:55]  // 0041e8
	s_nop 0
	v_pk_fma_f32 v[88:89], v[4:5], v[48:49], v[88:89]  // 0041f0
	v_pk_fma_f32 v[90:91], v[4:5], v[50:51], v[90:91]  // 0041f8
	v_pk_fma_f32 v[92:93], v[4:5], v[52:53], v[92:93]  // 004200
	v_pk_fma_f32 v[94:95], v[4:5], v[54:55], v[94:95]  // 004208
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[32:33], a[96:97], 0  // 004210
	s_add_u32 m0, 0x200, s60  // 004218
	buffer_load_dword v38, s[4:7], 0 offen lds  // 004220
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[34:35], a[98:99], v[56:59]  // 004228
	ds_read_b128 a[56:59], v46 offset:512  // 004230
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[36:37], a[100:101], v[56:59]  // 004238
	s_add_u32 m0, 0x300, s60  // 004240
	buffer_load_dword v39, s[4:7], 0 offen lds  // 004248
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[38:39], a[102:103], v[56:59]  // 004250
	ds_read_b128 a[60:63], v46 offset:576  // 004258
	v_mul_f32_e32 v4, v160, v139  // 004260
	v_mov_b32_e32 v5, v4  // 004264
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[40:41], a[96:97], 0  // 004268
	buffer_load_dwordx4 a[24:27], v34, s[8:11], 0 offen  // 004270
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[42:43], a[98:99], v[60:63]  // 004278
	buffer_load_dword v139, v162, s[20:23], 0 offen  // 004280
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[44:45], a[100:101], v[60:63]  // 004288
	buffer_load_dwordx4 a[28:31], v35, s[8:11], 0 offen  // 004290
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[46:47], a[102:103], v[60:63]  // 004298
	s_nop 0
	v_pk_fma_f32 v[96:97], v[4:5], v[56:57], v[96:97]  // 0042a0
	v_pk_fma_f32 v[98:99], v[4:5], v[58:59], v[98:99]  // 0042a8
	v_pk_fma_f32 v[100:101], v[4:5], v[60:61], v[100:101]  // 0042b0
	v_pk_fma_f32 v[102:103], v[4:5], v[62:63], v[102:103]  // 0042b8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[32:33], a[104:105], 0  // 0042c0
	s_add_u32 m0, 0x400, s60  // 0042c8
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0042d0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[34:35], a[106:107], v[64:67]  // 0042d8
	ds_read_b128 a[64:67], v46 offset:1024  // 0042e0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[36:37], a[108:109], v[64:67]  // 0042e8
	s_add_u32 m0, 0x500, s60  // 0042f0
	buffer_load_dword v41, s[4:7], 0 offen lds  // 0042f8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[38:39], a[110:111], v[64:67]  // 004300
	ds_read_b128 a[68:71], v46 offset:1088  // 004308
	v_mul_f32_e32 v4, v160, v140  // 004310
	v_mov_b32_e32 v5, v4  // 004314
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[40:41], a[104:105], 0  // 004318
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[42:43], a[106:107], v[68:71]  // 004320
	buffer_load_dword v140, v163, s[20:23], 0 offen  // 004328
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[44:45], a[108:109], v[68:71]  // 004330
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[46:47], a[110:111], v[68:71]  // 004338
	s_nop 0
	v_pk_fma_f32 v[104:105], v[4:5], v[64:65], v[104:105]  // 004340
	v_pk_fma_f32 v[106:107], v[4:5], v[66:67], v[106:107]  // 004348
	v_pk_fma_f32 v[108:109], v[4:5], v[68:69], v[108:109]  // 004350
	v_pk_fma_f32 v[110:111], v[4:5], v[70:71], v[110:111]  // 004358
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[32:33], a[112:113], 0  // 004360
	s_add_u32 m0, 0x600, s60  // 004368
	buffer_load_dword v42, s[4:7], 0 offen lds  // 004370
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[34:35], a[114:115], v[72:75]  // 004378
	ds_read_b128 a[72:75], v46 offset:1536  // 004380
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[36:37], a[116:117], v[72:75]  // 004388
	s_add_u32 m0, 0x700, s60  // 004390
	buffer_load_dword v43, s[4:7], 0 offen lds  // 004398
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[38:39], a[118:119], v[72:75]  // 0043a0
	ds_read_b128 a[76:79], v46 offset:1600  // 0043a8
	v_mul_f32_e32 v4, v160, v141  // 0043b0
	v_mov_b32_e32 v5, v4  // 0043b4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[40:41], a[112:113], 0  // 0043b8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[42:43], a[114:115], v[76:79]  // 0043c0
	buffer_load_dword v141, v164, s[20:23], 0 offen  // 0043c8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[44:45], a[116:117], v[76:79]  // 0043d0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[46:47], a[118:119], v[76:79]  // 0043d8
	s_nop 0
	v_pk_fma_f32 v[112:113], v[4:5], v[72:73], v[112:113]  // 0043e0
	v_pk_fma_f32 v[114:115], v[4:5], v[74:75], v[114:115]  // 0043e8
	v_pk_fma_f32 v[116:117], v[4:5], v[76:77], v[116:117]  // 0043f0
	v_pk_fma_f32 v[118:119], v[4:5], v[78:79], v[118:119]  // 0043f8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[32:33], a[120:121], 0  // 004400
	s_add_u32 m0, 0x800, s60  // 004408
	buffer_load_dword v44, s[4:7], 0 offen lds  // 004410
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[34:35], a[122:123], v[80:83]  // 004418
	ds_read_b128 a[80:83], v46 offset:2048  // 004420
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[36:37], a[124:125], v[80:83]  // 004428
	s_add_u32 m0, 0x900, s60  // 004430
	buffer_load_dword v45, s[4:7], 0 offen lds  // 004438
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[38:39], a[126:127], v[80:83]  // 004440
	s_add_u32 s50, 0x200, s42  // 004470
	s_cmp_lt_u32 s50, s43  // 004478
	s_cselect_b32 s54, s54, 0  // 00447c
	ds_read_b128 a[84:87], v46 offset:2112  // 004448
	v_mul_f32_e32 v4, v160, v142  // 004450
	v_mov_b32_e32 v5, v4  // 004454
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[40:41], a[120:121], 0  // 004458
	s_add_u32 s50, 0x180, s42  // 004480
	s_cmp_lt_u32 s50, s43  // 004488
	s_cselect_b32 s55, s55, 0  // 00448c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[42:43], a[122:123], v[84:87]  // 004460
	buffer_load_dword v142, v165, s[20:23], 0 offen  // 004468
	s_add_u32 s50, 0x200, s42  // 004490
	s_cmp_lt_u32 s50, s43  // 004498
	s_cselect_b32 s56, s56, 0  // 00449c
	s_add_u32 s50, 0x180, s42  // 0044a0
	s_cmp_lt_u32 s50, s43  // 0044a8
	s_cselect_b32 s57, s57, 0  // 0044ac
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[44:45], a[124:125], v[84:87]  // 0044b0
	s_add_u32 s4, s54, s4  // 0044c8
	s_addc_u32 s5, 0, s5  // 0044cc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[46:47], a[126:127], v[84:87]  // 0044b8
	buffer_load_dword v159, v171, s[24:27], 0 offen  // 0044c0
	s_sub_u32 s6, s6, s54  // 0044d0
	s_add_u32 s8, s55, s8  // 0044d4
	s_addc_u32 s9, 0, s9  // 0044d8
	s_sub_u32 s10, s10, s55  // 0044dc
	s_add_u32 s20, s56, s20  // 0044e0
	s_addc_u32 s21, 0, s21  // 0044e4
	s_add_u32 s24, s57, s24  // 0044e8
	s_addc_u32 s25, 0, s25  // 0044ec
	s_sub_u32 s26, s26, s57  // 0044f0
	v_pk_fma_f32 v[120:121], v[4:5], v[80:81], v[120:121]  // 0044f4
	v_pk_fma_f32 v[122:123], v[4:5], v[82:83], v[122:123]  // 0044fc
	v_pk_fma_f32 v[124:125], v[4:5], v[84:85], v[124:125]  // 004504
	v_pk_fma_f32 v[126:127], v[4:5], v[86:87], v[126:127]  // 00450c
	s_addk_i32 s42, 0x80  // 004514
	s_cmp_lt_i32 s42, s43  // 004518
	s_cbranch_scc0 L_4524  // 00451c
	s_branch L_2e88  // 004520
L_4524:
	s_cmp_eq_u32 s38, 1  // 004524
	s_cbranch_scc1 L_4a20  // 004528
	v_add_f32_e32 v88, v88, v12  // 00452c
	v_add_f32_e32 v89, v89, v13  // 004530
	v_perm_b32 v48, v89, v88, s48  // 004534
	v_add_f32_e32 v90, v90, v14  // 00453c
	v_add_f32_e32 v91, v91, v15  // 004540
	v_perm_b32 v49, v91, v90, s48  // 004544
	v_add_f32_e32 v92, v92, v16  // 00454c
	v_add_f32_e32 v93, v93, v17  // 004550
	v_perm_b32 v50, v93, v92, s48  // 004554
	v_add_f32_e32 v94, v94, v18  // 00455c
	v_add_f32_e32 v95, v95, v19  // 004560
	v_perm_b32 v51, v95, v94, s48  // 004564
	v_add_f32_e32 v96, v96, v12  // 00456c
	v_add_f32_e32 v97, v97, v13  // 004570
	v_perm_b32 v52, v97, v96, s48  // 004574
	v_add_f32_e32 v98, v98, v14  // 00457c
	v_add_f32_e32 v99, v99, v15  // 004580
	v_perm_b32 v53, v99, v98, s48  // 004584
	v_add_f32_e32 v100, v100, v16  // 00458c
	v_add_f32_e32 v101, v101, v17  // 004590
	v_perm_b32 v54, v101, v100, s48  // 004594
	v_add_f32_e32 v102, v102, v18  // 00459c
	v_add_f32_e32 v103, v103, v19  // 0045a0
	v_perm_b32 v55, v103, v102, s48  // 0045a4
	v_add_f32_e32 v104, v104, v12  // 0045ac
	v_add_f32_e32 v105, v105, v13  // 0045b0
	v_perm_b32 v56, v105, v104, s48  // 0045b4
	v_add_f32_e32 v106, v106, v14  // 0045bc
	v_add_f32_e32 v107, v107, v15  // 0045c0
	v_perm_b32 v57, v107, v106, s48  // 0045c4
	v_add_f32_e32 v108, v108, v16  // 0045cc
	v_add_f32_e32 v109, v109, v17  // 0045d0
	v_perm_b32 v58, v109, v108, s48  // 0045d4
	v_add_f32_e32 v110, v110, v18  // 0045dc
	v_add_f32_e32 v111, v111, v19  // 0045e0
	v_perm_b32 v59, v111, v110, s48  // 0045e4
	v_add_f32_e32 v112, v112, v12  // 0045ec
	v_add_f32_e32 v113, v113, v13  // 0045f0
	v_perm_b32 v60, v113, v112, s48  // 0045f4
	v_add_f32_e32 v114, v114, v14  // 0045fc
	v_add_f32_e32 v115, v115, v15  // 004600
	v_perm_b32 v61, v115, v114, s48  // 004604
	v_add_f32_e32 v116, v116, v16  // 00460c
	v_add_f32_e32 v117, v117, v17  // 004610
	v_perm_b32 v62, v117, v116, s48  // 004614
	v_add_f32_e32 v118, v118, v18  // 00461c
	v_add_f32_e32 v119, v119, v19  // 004620
	v_perm_b32 v63, v119, v118, s48  // 004624
	v_add_f32_e32 v120, v120, v12  // 00462c
	v_add_f32_e32 v121, v121, v13  // 004630
	v_perm_b32 v64, v121, v120, s48  // 004634
	v_add_f32_e32 v122, v122, v14  // 00463c
	v_add_f32_e32 v123, v123, v15  // 004640
	v_perm_b32 v65, v123, v122, s48  // 004644
	v_add_f32_e32 v124, v124, v16  // 00464c
	v_add_f32_e32 v125, v125, v17  // 004650
	v_perm_b32 v66, v125, v124, s48  // 004654
	v_add_f32_e32 v126, v126, v18  // 00465c
	v_add_f32_e32 v127, v127, v19  // 004660
	v_perm_b32 v67, v127, v126, s48  // 004664
	v_lshrrev_b32_e32 v4, 4, v0  // 00466c
	v_mul_u32_u24_e32 v46, 34, v4  // 004670
	v_and_b32_e32 v4, 15, v0  // 004674
	v_mul_lo_u32 v5, 2, v4  // 004678
	v_add_u32_e32 v46, v5, v46  // 004680
	s_mul_i32 s50, s47, 0x110  // 004684
	v_add_u32_e32 v46, s50, v46  // 00468c
	v_lshlrev_b32_e32 v46, 2, v46  // 004690
	v_lshrrev_b32_e32 v4, 1, v0  // 004694
	v_mul_u32_u24_e32 v36, 34, v4  // 004698
	v_and_b32_e32 v5, 1, v0  // 00469c
	v_add_u32_e32 v36, v5, v36  // 0046a0
	s_mul_i32 s50, s47, 2  // 0046a4
	v_add_u32_e32 v36, s50, v36  // 0046a8
	v_lshlrev_b32_e32 v36, 2, v36  // 0046ac
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 0046b0
	s_barrier  // 0046b4
	ds_write_b64 v46, v[48:49]  // 0046b8
	ds_write_b64 v46, v[50:51] offset:544  // 0046c0
	ds_write_b64 v46, v[52:53] offset:4352  // 0046c8
	ds_write_b64 v46, v[54:55] offset:4896  // 0046d0
	ds_write_b64 v46, v[56:57] offset:8704  // 0046d8
	ds_write_b64 v46, v[58:59] offset:9248  // 0046e0
	ds_write_b64 v46, v[60:61] offset:13056  // 0046e8
	ds_write_b64 v46, v[62:63] offset:13600  // 0046f0
	ds_write_b64 v46, v[64:65] offset:17408  // 0046f8
	ds_write_b64 v46, v[66:67] offset:17952  // 004700
	s_waitcnt lgkmcnt(0)  // 004708
	s_barrier  // 00470c
	ds_read_b32 v48, v36  // 004710
	ds_read_b32 v49, v36 offset:32  // 004718
	ds_read_b32 v50, v36 offset:64  // 004720
	ds_read_b32 v51, v36 offset:96  // 004728
	ds_read_b32 v52, v36 offset:4352  // 004730
	ds_read_b32 v53, v36 offset:4384  // 004738
	ds_read_b32 v54, v36 offset:4416  // 004740
	ds_read_b32 v55, v36 offset:4448  // 004748
	ds_read_b32 v56, v36 offset:8704  // 004750
	ds_read_b32 v57, v36 offset:8736  // 004758
	ds_read_b32 v58, v36 offset:8768  // 004760
	ds_read_b32 v59, v36 offset:8800  // 004768
	ds_read_b32 v60, v36 offset:13056  // 004770
	ds_read_b32 v61, v36 offset:13088  // 004778
	ds_read_b32 v62, v36 offset:13120  // 004780
	ds_read_b32 v63, v36 offset:13152  // 004788
	ds_read_b32 v64, v36 offset:17408  // 004790
	ds_read_b32 v65, v36 offset:17440  // 004798
	ds_read_b32 v66, v36 offset:17472  // 0047a0
	ds_read_b32 v67, v36 offset:17504  // 0047a8
	s_waitcnt lgkmcnt(0)  // 0047b0
	s_barrier  // 0047b4
	s_mul_i32 s50, s37, 4  // 0047b8
	s_mul_i32 s51, s37, 8  // 0047bc
	s_mul_i32 s52, s37, 16  // 0047c0
	v_mov_b32_e32 v4, v25  // 0047c4
	v_mov_b32_e32 v5, 0  // 0047c8
	v_mov_b32_e32 v7, 0  // 0047cc
	v_mov_b32_e32 v9, 0  // 0047d0
	v_mov_b32_e32 v11, 0  // 0047d4
	v_mov_b32_e32 v6, v4  // 0047d8
	v_add_u32_e64 v10, v4, s51  // 0047dc
	s_cmp_ge_u32 s77, s32  // 0047e4
	s_cbranch_scc1 L_4bb0  // 0047e8
	global_atomic_pk_add_bf16 v6, v48, s[80:81]  // 0047ec
	v_add_u32_e64 v8, v6, s50  // 0047f4
	s_add_i32 s77, s77, 4  // 0047fc
	s_cmp_ge_u32 s77, s32  // 004800
	s_cbranch_scc1 L_4bb0  // 004804
	global_atomic_pk_add_bf16 v8, v49, s[80:81]  // 004808
	s_add_i32 s77, s77, 4  // 004810
	s_cmp_ge_u32 s77, s32  // 004814
	s_cbranch_scc1 L_4bb0  // 004818
	global_atomic_pk_add_bf16 v10, v50, s[80:81]  // 00481c
	v_add_u32_e64 v12, v10, s50  // 004824
	s_add_i32 s77, s77, 4  // 00482c
	s_cmp_ge_u32 s77, s32  // 004830
	s_cbranch_scc1 L_4bb0  // 004834
	global_atomic_pk_add_bf16 v12, v51, s[80:81]  // 004838
	s_add_i32 s77, s77, 4  // 004840
	v_add_u32_e64 v4, v4, s52  // 004844
	v_mov_b32_e32 v6, v4  // 00484c
	v_add_u32_e64 v10, v4, s51  // 004850
	s_cmp_ge_u32 s77, s32  // 004858
	s_cbranch_scc1 L_4bb0  // 00485c
	global_atomic_pk_add_bf16 v6, v52, s[80:81]  // 004860
	v_add_u32_e64 v8, v6, s50  // 004868
	s_add_i32 s77, s77, 4  // 004870
	s_cmp_ge_u32 s77, s32  // 004874
	s_cbranch_scc1 L_4bb0  // 004878
	global_atomic_pk_add_bf16 v8, v53, s[80:81]  // 00487c
	s_add_i32 s77, s77, 4  // 004884
	s_cmp_ge_u32 s77, s32  // 004888
	s_cbranch_scc1 L_4bb0  // 00488c
	global_atomic_pk_add_bf16 v10, v54, s[80:81]  // 004890
	v_add_u32_e64 v12, v10, s50  // 004898
	s_add_i32 s77, s77, 4  // 0048a0
	s_cmp_ge_u32 s77, s32  // 0048a4
	s_cbranch_scc1 L_4bb0  // 0048a8
	global_atomic_pk_add_bf16 v12, v55, s[80:81]  // 0048ac
	s_add_i32 s77, s77, 4  // 0048b4
	v_add_u32_e64 v4, v4, s52  // 0048b8
	v_mov_b32_e32 v6, v4  // 0048c0
	v_add_u32_e64 v10, v4, s51  // 0048c4
	s_cmp_ge_u32 s77, s32  // 0048cc
	s_cbranch_scc1 L_4bb0  // 0048d0
	global_atomic_pk_add_bf16 v6, v56, s[80:81]  // 0048d4
	v_add_u32_e64 v8, v6, s50  // 0048dc
	s_add_i32 s77, s77, 4  // 0048e4
	s_cmp_ge_u32 s77, s32  // 0048e8
	s_cbranch_scc1 L_4bb0  // 0048ec
	global_atomic_pk_add_bf16 v8, v57, s[80:81]  // 0048f0
	s_add_i32 s77, s77, 4  // 0048f8
	s_cmp_ge_u32 s77, s32  // 0048fc
	s_cbranch_scc1 L_4bb0  // 004900
	global_atomic_pk_add_bf16 v10, v58, s[80:81]  // 004904
	v_add_u32_e64 v12, v10, s50  // 00490c
	s_add_i32 s77, s77, 4  // 004914
	s_cmp_ge_u32 s77, s32  // 004918
	s_cbranch_scc1 L_4bb0  // 00491c
	global_atomic_pk_add_bf16 v12, v59, s[80:81]  // 004920
	s_add_i32 s77, s77, 4  // 004928
	v_add_u32_e64 v4, v4, s52  // 00492c
	v_mov_b32_e32 v6, v4  // 004934
	v_add_u32_e64 v10, v4, s51  // 004938
	s_cmp_ge_u32 s77, s32  // 004940
	s_cbranch_scc1 L_4bb0  // 004944
	global_atomic_pk_add_bf16 v6, v60, s[80:81]  // 004948
	v_add_u32_e64 v8, v6, s50  // 004950
	s_add_i32 s77, s77, 4  // 004958
	s_cmp_ge_u32 s77, s32  // 00495c
	s_cbranch_scc1 L_4bb0  // 004960
	global_atomic_pk_add_bf16 v8, v61, s[80:81]  // 004964
	s_add_i32 s77, s77, 4  // 00496c
	s_cmp_ge_u32 s77, s32  // 004970
	s_cbranch_scc1 L_4bb0  // 004974
	global_atomic_pk_add_bf16 v10, v62, s[80:81]  // 004978
	v_add_u32_e64 v12, v10, s50  // 004980
	s_add_i32 s77, s77, 4  // 004988
	s_cmp_ge_u32 s77, s32  // 00498c
	s_cbranch_scc1 L_4bb0  // 004990
	global_atomic_pk_add_bf16 v12, v63, s[80:81]  // 004994
	s_add_i32 s77, s77, 4  // 00499c
	v_add_u32_e64 v4, v4, s52  // 0049a0
	v_mov_b32_e32 v6, v4  // 0049a8
	v_add_u32_e64 v10, v4, s51  // 0049ac
	s_cmp_ge_u32 s77, s32  // 0049b4
	s_cbranch_scc1 L_4bb0  // 0049b8
	global_atomic_pk_add_bf16 v6, v64, s[80:81]  // 0049bc
	v_add_u32_e64 v8, v6, s50  // 0049c4
	s_add_i32 s77, s77, 4  // 0049cc
	s_cmp_ge_u32 s77, s32  // 0049d0
	s_cbranch_scc1 L_4bb0  // 0049d4
	global_atomic_pk_add_bf16 v8, v65, s[80:81]  // 0049d8
	s_add_i32 s77, s77, 4  // 0049e0
	s_cmp_ge_u32 s77, s32  // 0049e4
	s_cbranch_scc1 L_4bb0  // 0049e8
	global_atomic_pk_add_bf16 v10, v66, s[80:81]  // 0049ec
	v_add_u32_e64 v12, v10, s50  // 0049f4
	s_add_i32 s77, s77, 4  // 0049fc
	s_cmp_ge_u32 s77, s32  // 004a00
	s_cbranch_scc1 L_4bb0  // 004a04
	global_atomic_pk_add_bf16 v12, v67, s[80:81]  // 004a08
	s_add_i32 s77, s77, 4  // 004a10
	v_add_u32_e64 v4, v4, s52  // 004a14
	s_branch L_4bb0  // 004a1c
L_4a20:
	v_add_f32_e32 v88, v88, v12  // 004a20
	v_add_f32_e32 v89, v89, v13  // 004a24
	v_perm_b32 v48, v89, v88, s48  // 004a28
	v_add_f32_e32 v90, v90, v14  // 004a30
	v_add_f32_e32 v91, v91, v15  // 004a34
	v_perm_b32 v49, v91, v90, s48  // 004a38
	buffer_store_dwordx2 v[48:49], v20, s[16:19], 0 offen  // 004a40
	v_add_f32_e32 v92, v92, v16  // 004a48
	v_add_f32_e32 v93, v93, v17  // 004a4c
	v_perm_b32 v50, v93, v92, s48  // 004a50
	v_add_f32_e32 v94, v94, v18  // 004a58
	v_add_f32_e32 v95, v95, v19  // 004a5c
	v_perm_b32 v51, v95, v94, s48  // 004a60
	buffer_store_dwordx2 v[50:51], v20, s[16:19], 0 offen offset:32  // 004a68
	v_add_f32_e32 v96, v96, v12  // 004a70
	v_add_f32_e32 v97, v97, v13  // 004a74
	v_perm_b32 v52, v97, v96, s48  // 004a78
	v_add_f32_e32 v98, v98, v14  // 004a80
	v_add_f32_e32 v99, v99, v15  // 004a84
	v_perm_b32 v53, v99, v98, s48  // 004a88
	buffer_store_dwordx2 v[52:53], v21, s[16:19], 0 offen  // 004a90
	v_add_f32_e32 v100, v100, v16  // 004a98
	v_add_f32_e32 v101, v101, v17  // 004a9c
	v_perm_b32 v54, v101, v100, s48  // 004aa0
	v_add_f32_e32 v102, v102, v18  // 004aa8
	v_add_f32_e32 v103, v103, v19  // 004aac
	v_perm_b32 v55, v103, v102, s48  // 004ab0
	buffer_store_dwordx2 v[54:55], v21, s[16:19], 0 offen offset:32  // 004ab8
	v_add_f32_e32 v104, v104, v12  // 004ac0
	v_add_f32_e32 v105, v105, v13  // 004ac4
	v_perm_b32 v56, v105, v104, s48  // 004ac8
	v_add_f32_e32 v106, v106, v14  // 004ad0
	v_add_f32_e32 v107, v107, v15  // 004ad4
	v_perm_b32 v57, v107, v106, s48  // 004ad8
	buffer_store_dwordx2 v[56:57], v22, s[16:19], 0 offen  // 004ae0
	v_add_f32_e32 v108, v108, v16  // 004ae8
	v_add_f32_e32 v109, v109, v17  // 004aec
	v_perm_b32 v58, v109, v108, s48  // 004af0
	v_add_f32_e32 v110, v110, v18  // 004af8
	v_add_f32_e32 v111, v111, v19  // 004afc
	v_perm_b32 v59, v111, v110, s48  // 004b00
	buffer_store_dwordx2 v[58:59], v22, s[16:19], 0 offen offset:32  // 004b08
	v_add_f32_e32 v112, v112, v12  // 004b10
	v_add_f32_e32 v113, v113, v13  // 004b14
	v_perm_b32 v60, v113, v112, s48  // 004b18
	v_add_f32_e32 v114, v114, v14  // 004b20
	v_add_f32_e32 v115, v115, v15  // 004b24
	v_perm_b32 v61, v115, v114, s48  // 004b28
	buffer_store_dwordx2 v[60:61], v23, s[16:19], 0 offen  // 004b30
	v_add_f32_e32 v116, v116, v16  // 004b38
	v_add_f32_e32 v117, v117, v17  // 004b3c
	v_perm_b32 v62, v117, v116, s48  // 004b40
	v_add_f32_e32 v118, v118, v18  // 004b48
	v_add_f32_e32 v119, v119, v19  // 004b4c
	v_perm_b32 v63, v119, v118, s48  // 004b50
	buffer_store_dwordx2 v[62:63], v23, s[16:19], 0 offen offset:32  // 004b58
	v_add_f32_e32 v120, v120, v12  // 004b60
	v_add_f32_e32 v121, v121, v13  // 004b64
	v_perm_b32 v64, v121, v120, s48  // 004b68
	v_add_f32_e32 v122, v122, v14  // 004b70
	v_add_f32_e32 v123, v123, v15  // 004b74
	v_perm_b32 v65, v123, v122, s48  // 004b78
	buffer_store_dwordx2 v[64:65], v24, s[16:19], 0 offen  // 004b80
	v_add_f32_e32 v124, v124, v16  // 004b88
	v_add_f32_e32 v125, v125, v17  // 004b8c
	v_perm_b32 v66, v125, v124, s48  // 004b90
	v_add_f32_e32 v126, v126, v18  // 004b98
	v_add_f32_e32 v127, v127, v19  // 004b9c
	v_perm_b32 v67, v127, v126, s48  // 004ba0
	buffer_store_dwordx2 v[66:67], v24, s[16:19], 0 offen offset:32  // 004ba8
L_4bb0:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 004bb0
	s_endpgm  // 004bb4
.Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E:
	.size _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E, .Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E-_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E
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
    .name:           _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_80x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
