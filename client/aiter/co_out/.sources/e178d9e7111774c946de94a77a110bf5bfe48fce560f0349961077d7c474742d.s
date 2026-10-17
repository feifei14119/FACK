// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_32x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E
	.protected _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E
	.p2align 8
	.type _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E,@function
_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E:
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
	s_mul_i32 s50, s45, 32  // 00258c
	s_mul_i32 s51, s50, s37  // 002590
	s_mul_hi_u32 s52, s50, s37  // 002594
	s_add_u32 s16, s16, s51  // 002598
	s_addc_u32 s17, s17, s52  // 00259c
	s_mul_i32 s50, s44, 0x80  // 0025a0
	s_mul_i32 s51, s50, 2  // 0025a8
	s_mul_hi_u32 s52, s50, 2  // 0025ac
	s_add_u32 s16, s16, s51  // 0025b0
	s_addc_u32 s17, s17, s52  // 0025b4
	s_mov_b32 s80, s16  // 0025b8
	s_mov_b32 s81, s17  // 0025bc
	s_mul_i32 s50, s45, 32  // 0025c0
	s_sub_i32 s51, s32, s50  // 0025c4
	s_cmp_lt_u32 s51, 32  // 0025c8
	s_cselect_b32 s50, s51, 32  // 0025cc
	s_mul_i32 s51, s50, s37  // 0025d0
	s_mov_b32 s18, s51  // 0025d4
	s_mov_b32 s82, 0x80000000  // 0025d8
	s_mov_b32 s19, 0x20000  // 0025e0
	s_and_b32 s17, s17, 0xffff  // 0025e8
	s_and_b32 s81, s81, 0xffff  // 0025f0
	s_or_b32 s17, s17, 0x40000  // 0025f8
	s_mov_b32 s48, 0x7060302  // 002600
	v_mov_b32_e32 v9, 0xffff0000  // 002608
	v_mov_b32_e32 v10, 0x7fff0000  // 002610
	v_mov_b32_e32 v11, 0x7fff  // 002618
	s_mul_i32 s50, 0x80, s44  // 002620
	s_mul_hi_u32 s51, 4, s50  // 002628
	s_add_u32 s29, s29, s51  // 00262c
	s_mul_i32 s51, 4, s50  // 002630
	s_add_u32 s28, s28, s51  // 002634
	s_addc_u32 s29, s29, 0  // 002638
	s_sub_i32 s51, s33, s50  // 00263c
	s_cmp_lt_u32 s51, 0x80  // 002640
	s_cselect_b32 s50, s51, 0x80  // 002648
	s_mul_i32 s51, 4, s50  // 002650
	s_mov_b32 s30, s51  // 002654
	s_mov_b32 s31, 0x20000  // 002658
	v_lshrrev_b32_e32 v4, 4, v0  // 002660
	v_lshlrev_b32_e32 v4, 4, v4  // 002664
	s_mul_i32 s52, s47, 0x80  // 002668
	v_add_u32_e64 v4, v4, s52  // 002670
	v_add_u32_e64 v5, v4, 64  // 002678
	buffer_load_dwordx4 v[12:15], v4, s[28:31], 0 offen  // 002680
	buffer_load_dwordx4 v[16:19], v5, s[28:31], 0 offen  // 002688
	s_mul_i32 s50, 32, s45  // 002690
	s_mul_hi_u32 s52, 4, s50  // 002694
	s_mul_i32 s51, 4, s50  // 002698
	s_add_u32 s20, s20, s51  // 00269c
	s_addc_u32 s21, s21, s52  // 0026a0
	s_sub_i32 s51, s32, s50  // 0026a4
	s_cmp_lt_u32 s51, 32  // 0026a8
	s_cselect_b32 s50, s51, 32  // 0026ac
	s_lshl_b32 s51, s50, 2  // 0026b0
	s_mov_b32 s22, s51  // 0026b4
	s_mov_b32 s23, 0x20000  // 0026b8
	s_lshr_b32 s50, s76, 7  // 0026c0
	s_mul_i32 s50, s50, s75  // 0026c4
	s_mul_i32 s51, s50, s32  // 0026c8
	s_mul_hi_u32 s52, s50, s32  // 0026cc
	s_lshr_b32 s50, s51, 30  // 0026d0
	s_lshl_b32 s51, s51, 2  // 0026d4
	s_lshl_b32 s52, s52, 2  // 0026d8
	s_add_u32 s52, s52, s50  // 0026dc
	s_add_u32 s20, s20, s51  // 0026e0
	s_addc_u32 s21, s21, s52  // 0026e4
	v_and_b32_e64 v83, v0, 15  // 0026e8
	v_lshlrev_b32_e32 v83, 2, v83  // 0026f0
	s_mov_b32 s50, 64  // 0026f4
	v_add_u32_e64 v84, v83, s50  // 0026f8
	s_mul_i32 s51, s41, s44  // 002700
	s_mul_hi_u32 s52, 4, s51  // 002704
	s_add_u32 s25, s25, s52  // 002708
	s_mul_i32 s52, 4, s51  // 00270c
	s_add_u32 s24, s24, s52  // 002710
	s_addc_u32 s25, s25, 0  // 002714
	s_lshr_b32 s50, s76, 7  // 002718
	s_mul_i32 s50, s50, s75  // 00271c
	s_lshl_b32 s50, s50, 2  // 002720
	s_add_u32 s24, s24, s50  // 002724
	s_addc_u32 s25, s25, 0  // 002728
	s_sub_u32 s26, s26, s50  // 00272c
	v_mov_b32_e32 v87, 0  // 002730
	v_lshrrev_b32_e32 v4, 5, v0  // 002734
	v_lshlrev_b32_e32 v4, 2, v4  // 002738
	v_mul_i32_i24_e32 v4, s35, v4  // 00273c
	v_and_b32_e32 v30, 31, v0  // 002740
	v_lshlrev_b32_e32 v30, 2, v30  // 002744
	s_mul_i32 s50, 32, s45  // 002748
	s_sub_i32 s51, s32, s50  // 00274c
	s_cmp_lt_u32 s51, 32  // 002750
	s_cselect_b32 s51, s51, 32  // 002754
	s_mul_i32 s52, s35, s50  // 002758
	s_mul_hi_u32 s50, s35, s50  // 00275c
	s_add_u32 s4, s4, s52  // 002760
	s_addc_u32 s5, s5, s50  // 002764
	s_mul_i32 s50, s35, s51  // 002768
	s_mov_b32 s6, s50  // 00276c
	s_mov_b32 s7, 0x20000  // 002770
	s_mul_i32 s51, s76, s75  // 002778
	s_add_u32 s4, s51, s4  // 00277c
	s_addc_u32 s5, 0, s5  // 002780
	s_sub_u32 s6, s6, s51  // 002784
	s_mul_i32 s50, s35, s47  // 002788
	v_add3_u32 v30, v4, v30, s50  // 00278c
	s_lshl_b32 s50, s35, 3  // 002794
	v_add_u32_e32 v31, s50, v30  // 002798
	v_add_u32_e32 v32, s50, v31  // 00279c
	v_add_u32_e32 v33, s50, v32  // 0027a0
	s_mov_b32 s54, 0x80  // 0027a4
	s_mul_i32 s56, s32, 4  // 0027ac
	s_mov_b32 s57, 4  // 0027b0
	s_mov_b32 s50, 32  // 0027b4
	s_lshr_b32 s50, s50, 2  // 0027b8
	s_mul_i32 s50, s50, 32  // 0027bc
	s_mov_b32 s51, 8  // 0027c0
	s_add_u32 s50, s50, s51  // 0027c4
	v_lshrrev_b32_e32 v4, 4, v0  // 0027c8
	v_and_b32_e32 v5, 15, v0  // 0027cc
	v_and_b32_e32 v6, 3, v5  // 0027d0
	v_lshrrev_b32_e32 v7, 2, v5  // 0027d4
	v_lshlrev_b32_e32 v4, 2, v4  // 0027d8
	v_mul_lo_u32 v6, v6, s50  // 0027dc
	v_lshlrev_b32_e32 v7, 5, v7  // 0027e4
	v_add_u32_e32 v4, v4, v6  // 0027e8
	v_add_u32_e32 v4, v4, v7  // 0027ec
	v_lshlrev_b32_e32 v34, 2, v4  // 0027f0
	s_mul_i32 s50, 0x420, s47  // 0027f4
	s_add_u32 s58, 0, s50  // 0027fc
	s_add_u32 s59, 0x1080, s58  // 002800
	s_add_u32 s60, 0x1080, s59  // 002808
	s_mov_b32 s55, 0x800  // 002810
	s_mul_i32 s49, 0x80, s44  // 002818
	s_sub_i32 s51, s33, s49  // 002820
	s_cmp_lt_u32 s51, 0x80  // 002824
	s_cselect_b32 s50, s51, 0x80  // 00282c
	s_mul_i32 s51, s36, s49  // 002834
	s_mul_hi_u32 s52, s36, s49  // 002838
	s_add_u32 s8, s8, s51  // 00283c
	s_addc_u32 s9, s9, s52  // 002840
	s_mul_i32 s51, s36, s50  // 002844
	s_mov_b32 s10, s51  // 002848
	s_mov_b32 s11, 0x20000  // 00284c
	s_lshr_b32 s51, s76, 7  // 002854
	s_mul_i32 s50, s55, s75  // 002858
	s_mul_i32 s50, s51, s50  // 00285c
	s_add_u32 s8, s50, s8  // 002860
	s_addc_u32 s9, 0, s9  // 002864
	s_sub_u32 s10, s10, s50  // 002868
	s_lshl_b32 s50, s47, 5  // 00286c
	s_mul_i32 s50, s36, s50  // 002870
	v_lshlrev_b32_e32 v26, 4, v0  // 002874
	v_add_u32_e32 v26, s50, v26  // 002878
	s_mov_b32 s50, 0x400  // 00287c
	v_add_u32_e64 v27, v26, s50  // 002884
	s_mul_i32 s50, s36, 16  // 00288c
	v_add_u32_e64 v28, v26, s50  // 002890
	v_add_u32_e64 v29, v27, s50  // 002898
	s_add_u32 m0, 0, s58  // 0028a0
	buffer_load_dword v30, s[4:7], 0 offen lds  // 0028a4
	s_add_u32 m0, 0x100, s58  // 0028ac
	buffer_load_dword v31, s[4:7], 0 offen lds  // 0028b4
	s_add_u32 m0, 0x200, s58  // 0028bc
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0028c4
	s_add_u32 m0, 0x300, s58  // 0028cc
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0028d4
	s_mov_b32 s53, 0  // 0028dc
	s_add_u32 s50, 0x80, s53  // 0028e0
	s_cmp_lt_u32 s50, s34  // 0028e8
	s_cselect_b32 s54, s54, 0  // 0028ec
	s_add_u32 s4, s54, s4  // 0028f0
	s_addc_u32 s5, 0, s5  // 0028f4
	s_sub_u32 s6, s6, s54  // 0028f8
	buffer_load_dword v68, v83, s[20:23], 0 offen  // 0028fc
	buffer_load_dword v69, v84, s[20:23], 0 offen  // 002904
	s_add_u32 s50, 0x80, s53  // 00290c
	s_cmp_lt_u32 s50, s34  // 002914
	s_cselect_b32 s56, s56, 0  // 002918
	s_add_u32 s20, s56, s20  // 00291c
	s_addc_u32 s21, 0, s21  // 002920
	v_mov_b32_e32 v52, 0  // 002924
	v_mov_b32_e32 v53, 0  // 002928
	v_mov_b32_e32 v54, 0  // 00292c
	v_mov_b32_e32 v55, 0  // 002930
	v_mov_b32_e32 v56, 0  // 002934
	v_mov_b32_e32 v57, 0  // 002938
	v_mov_b32_e32 v58, 0  // 00293c
	v_mov_b32_e32 v59, 0  // 002940
	buffer_load_dwordx4 a[0:3], v26, s[8:11], 0 offen  // 002944
	buffer_load_dwordx4 a[4:7], v27, s[8:11], 0 offen  // 00294c
	buffer_load_dwordx4 a[8:11], v28, s[8:11], 0 offen  // 002954
	buffer_load_dwordx4 a[12:15], v29, s[8:11], 0 offen  // 00295c
	s_mov_b32 s53, 0  // 002964
	s_add_u32 s50, 0x80, s53  // 002968
	s_cmp_lt_u32 s50, s34  // 002970
	s_cselect_b32 s55, s55, 0  // 002974
	s_add_u32 s8, s55, s8  // 002978
	s_addc_u32 s9, 0, s9  // 00297c
	s_sub_u32 s10, s10, s55  // 002980
	buffer_load_dword v80, v87, s[24:27], 0 offen  // 002984
	s_add_u32 s50, 0x80, s53  // 00298c
	s_cmp_lt_u32 s50, s34  // 002994
	s_cselect_b32 s57, s57, 0  // 002998
	s_add_u32 s24, s57, s24  // 00299c
	s_addc_u32 s25, 0, s25  // 0029a0
	s_sub_u32 s26, s26, s57  // 0029a4
	s_add_u32 m0, 0, s59  // 0029a8
	buffer_load_dword v30, s[4:7], 0 offen lds  // 0029ac
	s_add_u32 m0, 0x100, s59  // 0029b4
	buffer_load_dword v31, s[4:7], 0 offen lds  // 0029bc
	s_add_u32 m0, 0x200, s59  // 0029c4
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0029cc
	s_add_u32 m0, 0x300, s59  // 0029d4
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0029dc
	s_mov_b32 s53, 0x80  // 0029e4
	s_add_u32 s50, 0x80, s53  // 0029ec
	s_cmp_lt_u32 s50, s34  // 0029f4
	s_cselect_b32 s54, s54, 0  // 0029f8
	s_add_u32 s4, s54, s4  // 0029fc
	s_addc_u32 s5, 0, s5  // 002a00
	s_sub_u32 s6, s6, s54  // 002a04
	buffer_load_dword v70, v83, s[20:23], 0 offen  // 002a08
	buffer_load_dword v71, v84, s[20:23], 0 offen  // 002a10
	s_add_u32 s50, 0x80, s53  // 002a18
	s_cmp_lt_u32 s50, s34  // 002a20
	s_cselect_b32 s56, s56, 0  // 002a24
	s_add_u32 s20, s56, s20  // 002a28
	s_addc_u32 s21, 0, s21  // 002a2c
	v_mov_b32_e32 v60, 0  // 002a30
	v_mov_b32_e32 v61, 0  // 002a34
	v_mov_b32_e32 v62, 0  // 002a38
	v_mov_b32_e32 v63, 0  // 002a3c
	v_mov_b32_e32 v64, 0  // 002a40
	v_mov_b32_e32 v65, 0  // 002a44
	v_mov_b32_e32 v66, 0  // 002a48
	v_mov_b32_e32 v67, 0  // 002a4c
	buffer_load_dwordx4 a[16:19], v26, s[8:11], 0 offen  // 002a50
	buffer_load_dwordx4 a[20:23], v27, s[8:11], 0 offen  // 002a58
	buffer_load_dwordx4 a[24:27], v28, s[8:11], 0 offen  // 002a60
	buffer_load_dwordx4 a[28:31], v29, s[8:11], 0 offen  // 002a68
	s_mov_b32 s53, 0x80  // 002a70
	s_add_u32 s50, 0x80, s53  // 002a78
	s_cmp_lt_u32 s50, s34  // 002a80
	s_cselect_b32 s55, s55, 0  // 002a84
	s_add_u32 s8, s55, s8  // 002a88
	s_addc_u32 s9, 0, s9  // 002a8c
	s_sub_u32 s10, s10, s55  // 002a90
	buffer_load_dword v81, v87, s[24:27], 0 offen  // 002a94
	s_add_u32 s50, 0x80, s53  // 002a9c
	s_cmp_lt_u32 s50, s34  // 002aa4
	s_cselect_b32 s57, s57, 0  // 002aa8
	s_add_u32 s24, s57, s24  // 002aac
	s_addc_u32 s25, 0, s25  // 002ab0
	s_sub_u32 s26, s26, s57  // 002ab4
	s_add_u32 m0, 0, s60  // 002ab8
	buffer_load_dword v30, s[4:7], 0 offen lds  // 002abc
	s_add_u32 m0, 0x100, s60  // 002ac4
	buffer_load_dword v31, s[4:7], 0 offen lds  // 002acc
	s_add_u32 m0, 0x200, s60  // 002ad4
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002adc
	s_add_u32 m0, 0x300, s60  // 002ae4
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002aec
	s_mov_b32 s53, 0x100  // 002af4
	s_add_u32 s50, 0x80, s53  // 002afc
	s_cmp_lt_u32 s50, s34  // 002b04
	s_cselect_b32 s54, s54, 0  // 002b08
	s_add_u32 s4, s54, s4  // 002b0c
	s_addc_u32 s5, 0, s5  // 002b10
	s_sub_u32 s6, s6, s54  // 002b14
	buffer_load_dword v72, v83, s[20:23], 0 offen  // 002b18
	buffer_load_dword v73, v84, s[20:23], 0 offen  // 002b20
	s_add_u32 s50, 0x80, s53  // 002b28
	s_cmp_lt_u32 s50, s34  // 002b30
	s_cselect_b32 s56, s56, 0  // 002b34
	s_add_u32 s20, s56, s20  // 002b38
	s_addc_u32 s21, 0, s21  // 002b3c
	s_mov_b32 s43, s34  // 002b40
	s_mov_b32 s42, 0  // 002b44
	s_waitcnt vmcnt(22)  // 002b48
	s_barrier  // 002b4c
	ds_read_b128 a[48:51], v34  // 002b50
	ds_read_b128 a[52:55], v34 offset:64  // 002b58
	ds_read_b128 a[56:59], v34 offset:512  // 002b60
	ds_read_b128 a[60:63], v34 offset:576  // 002b68
	s_mov_b32 s50, 0  // 002b70
	s_mov_b32 s51, 1.0  // 002b74
	s_cmp_eq_u32 s50, s75  // 002b78
	s_cselect_b32 s50, s51, 0  // 002b7c
	v_mul_f32_e64 v12, v12, s50  // 002b80
	v_mul_f32_e64 v13, v13, s50  // 002b88
	v_mul_f32_e64 v14, v14, s50  // 002b90
	v_mul_f32_e64 v15, v15, s50  // 002b98
	v_mul_f32_e64 v16, v16, s50  // 002ba0
	v_mul_f32_e64 v17, v17, s50  // 002ba8
	v_mul_f32_e64 v18, v18, s50  // 002bb0
	v_mul_f32_e64 v19, v19, s50  // 002bb8
	v_and_b32_e64 v20, v0, 15  // 002bc0
	v_mul_lo_u32 v20, v20, s37  // 002bc8
	v_lshrrev_b32_e32 v4, 4, v0  // 002bd0
	v_mul_i32_i24_e32 v4, 8, v4  // 002bd4
	v_add_u32_e32 v20, v4, v20  // 002bd8
	s_mul_i32 s50, 32, s47  // 002bdc
	s_mul_i32 s50, 2, s50  // 002be0
	v_add_u32_e32 v20, s50, v20  // 002be4
	s_mul_i32 s50, 16, s37  // 002be8
	v_add_u32_e32 v21, s50, v20  // 002bec
	s_mul_i32 s50, s47, s37  // 002bf0
	v_lshlrev_b32_e32 v5, 2, v0  // 002bf4
	v_add_u32_e32 v22, s50, v5  // 002bf8
	s_mul_i32 s50, s45, 32  // 002bfc
	s_add_i32 s77, s50, s47  // 002c00
	s_cmp_lt_i32 s42, s43  // 002c04
	s_cbranch_scc0 L_3768  // 002c08
L_2c0c:
	s_waitcnt vmcnt(13) & lgkmcnt(0)
	s_barrier  // 002c10
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[0:1], a[48:49], 0  // 002c14
	s_add_u32 m0, 0, s58  // 002c1c
	buffer_load_dword v30, s[4:7], 0 offen lds  // 002c20
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[2:3], a[50:51], v[36:39]  // 002c28
	ds_read_b128 a[64:67], v34 offset:4224  // 002c30
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[4:5], a[52:53], v[36:39]  // 002c38
	s_add_u32 m0, 0x100, s58  // 002c40
	buffer_load_dword v31, s[4:7], 0 offen lds  // 002c48
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[6:7], a[54:55], v[36:39]  // 002c50
	ds_read_b128 a[68:71], v34 offset:4288  // 002c58
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v80, v68  // 002c60
	v_mov_b32_e32 v5, v4  // 002c64
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[8:9], a[48:49], 0  // 002c68
	buffer_load_dwordx4 a[32:35], v26, s[8:11], 0 offen  // 002c70
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[10:11], a[50:51], v[40:43]  // 002c78
	buffer_load_dword v68, v83, s[20:23], 0 offen  // 002c80
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[12:13], a[52:53], v[40:43]  // 002c88
	buffer_load_dwordx4 a[36:39], v27, s[8:11], 0 offen  // 002c90
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[14:15], a[54:55], v[40:43]  // 002c98
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 002ca0
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 002ca8
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 002cb0
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 002cb8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[0:1], a[56:57], 0  // 002cc0
	s_add_u32 m0, 0x200, s58  // 002cc8
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002cd0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[2:3], a[58:59], v[44:47]  // 002cd8
	ds_read_b128 a[72:75], v34 offset:4736  // 002ce0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[4:5], a[60:61], v[44:47]  // 002ce8
	s_add_u32 m0, 0x300, s58  // 002cf0
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002cf8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[6:7], a[62:63], v[44:47]  // 002d00
	buffer_load_dwordx4 a[40:43], v28, s[8:11], 0 offen  // 002d20
	s_add_u32 s50, 0x200, s42  // 002d38
	s_cmp_lt_u32 s50, s43  // 002d40
	s_cselect_b32 s54, s54, 0  // 002d44
	ds_read_b128 a[76:79], v34 offset:4800  // 002d08
	v_mul_f32_e32 v4, v80, v69  // 002d10
	v_mov_b32_e32 v5, v4  // 002d14
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[8:9], a[56:57], 0  // 002d18
	s_add_u32 s50, 0x180, s42  // 002d48
	s_cmp_lt_u32 s50, s43  // 002d50
	s_cselect_b32 s55, s55, 0  // 002d54
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[10:11], a[58:59], v[48:51]  // 002d28
	buffer_load_dword v69, v84, s[20:23], 0 offen  // 002d30
	s_add_u32 s50, 0x200, s42  // 002d58
	s_cmp_lt_u32 s50, s43  // 002d60
	s_cselect_b32 s56, s56, 0  // 002d64
	s_add_u32 s50, 0x180, s42  // 002d68
	s_cmp_lt_u32 s50, s43  // 002d70
	s_cselect_b32 s57, s57, 0  // 002d74
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[12:13], a[60:61], v[48:51]  // 002d78
	buffer_load_dwordx4 a[44:47], v29, s[8:11], 0 offen  // 002d80
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[14:15], a[62:63], v[48:51]  // 002d88
	buffer_load_dword v82, v87, s[24:27], 0 offen  // 002d90
	s_add_u32 s4, s54, s4  // 002d98
	s_addc_u32 s5, 0, s5  // 002d9c
	s_sub_u32 s6, s6, s54  // 002da0
	s_add_u32 s8, s55, s8  // 002da4
	s_addc_u32 s9, 0, s9  // 002da8
	s_sub_u32 s10, s10, s55  // 002dac
	s_add_u32 s20, s56, s20  // 002db0
	s_addc_u32 s21, 0, s21  // 002db4
	s_add_u32 s24, s57, s24  // 002db8
	s_addc_u32 s25, 0, s25  // 002dbc
	s_sub_u32 s26, s26, s57  // 002dc0
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 002dc4
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 002dcc
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 002dd4
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 002ddc
	s_addk_i32 s42, 0x80  // 002de4
	s_cmp_lt_i32 s42, s43  // 002de8
	s_cbranch_scc0 L_3768  // 002dec
	s_waitcnt vmcnt(13) & lgkmcnt(0)
	s_barrier  // 002df4
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[16:17], a[64:65], 0  // 002df8
	s_add_u32 m0, 0, s59  // 002e00
	buffer_load_dword v30, s[4:7], 0 offen lds  // 002e04
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[18:19], a[66:67], v[36:39]  // 002e0c
	ds_read_b128 a[48:51], v34 offset:8448  // 002e14
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[20:21], a[68:69], v[36:39]  // 002e1c
	s_add_u32 m0, 0x100, s59  // 002e24
	buffer_load_dword v31, s[4:7], 0 offen lds  // 002e2c
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[22:23], a[70:71], v[36:39]  // 002e34
	ds_read_b128 a[52:55], v34 offset:8512  // 002e3c
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v81, v70  // 002e44
	v_mov_b32_e32 v5, v4  // 002e48
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[24:25], a[64:65], 0  // 002e4c
	buffer_load_dwordx4 a[0:3], v26, s[8:11], 0 offen  // 002e54
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[26:27], a[66:67], v[40:43]  // 002e5c
	buffer_load_dword v70, v83, s[20:23], 0 offen  // 002e64
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[28:29], a[68:69], v[40:43]  // 002e6c
	buffer_load_dwordx4 a[4:7], v27, s[8:11], 0 offen  // 002e74
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[30:31], a[70:71], v[40:43]  // 002e7c
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 002e84
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 002e8c
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 002e94
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 002e9c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[16:17], a[72:73], 0  // 002ea4
	s_add_u32 m0, 0x200, s59  // 002eac
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002eb4
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[18:19], a[74:75], v[44:47]  // 002ebc
	ds_read_b128 a[56:59], v34 offset:8960  // 002ec4
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[20:21], a[76:77], v[44:47]  // 002ecc
	s_add_u32 m0, 0x300, s59  // 002ed4
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002edc
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[22:23], a[78:79], v[44:47]  // 002ee4
	buffer_load_dwordx4 a[8:11], v28, s[8:11], 0 offen  // 002f04
	s_add_u32 s50, 0x200, s42  // 002f1c
	s_cmp_lt_u32 s50, s43  // 002f24
	s_cselect_b32 s54, s54, 0  // 002f28
	ds_read_b128 a[60:63], v34 offset:9024  // 002eec
	v_mul_f32_e32 v4, v81, v71  // 002ef4
	v_mov_b32_e32 v5, v4  // 002ef8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[24:25], a[72:73], 0  // 002efc
	s_add_u32 s50, 0x180, s42  // 002f2c
	s_cmp_lt_u32 s50, s43  // 002f34
	s_cselect_b32 s55, s55, 0  // 002f38
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[26:27], a[74:75], v[48:51]  // 002f0c
	buffer_load_dword v71, v84, s[20:23], 0 offen  // 002f14
	s_add_u32 s50, 0x200, s42  // 002f3c
	s_cmp_lt_u32 s50, s43  // 002f44
	s_cselect_b32 s56, s56, 0  // 002f48
	s_add_u32 s50, 0x180, s42  // 002f4c
	s_cmp_lt_u32 s50, s43  // 002f54
	s_cselect_b32 s57, s57, 0  // 002f58
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[28:29], a[76:77], v[48:51]  // 002f5c
	buffer_load_dwordx4 a[12:15], v29, s[8:11], 0 offen  // 002f64
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[30:31], a[78:79], v[48:51]  // 002f6c
	buffer_load_dword v80, v87, s[24:27], 0 offen  // 002f74
	s_add_u32 s4, s54, s4  // 002f7c
	s_addc_u32 s5, 0, s5  // 002f80
	s_sub_u32 s6, s6, s54  // 002f84
	s_add_u32 s8, s55, s8  // 002f88
	s_addc_u32 s9, 0, s9  // 002f8c
	s_sub_u32 s10, s10, s55  // 002f90
	s_add_u32 s20, s56, s20  // 002f94
	s_addc_u32 s21, 0, s21  // 002f98
	s_add_u32 s24, s57, s24  // 002f9c
	s_addc_u32 s25, 0, s25  // 002fa0
	s_sub_u32 s26, s26, s57  // 002fa4
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 002fa8
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 002fb0
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 002fb8
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 002fc0
	s_addk_i32 s42, 0x80  // 002fc8
	s_cmp_lt_i32 s42, s43  // 002fcc
	s_cbranch_scc0 L_3768  // 002fd0
	s_waitcnt vmcnt(15) & lgkmcnt(0)
	s_barrier  // 002fd8
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[32:33], a[48:49], 0  // 002fdc
	s_add_u32 m0, 0, s60  // 002fe4
	buffer_load_dword v30, s[4:7], 0 offen lds  // 002fe8
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[34:35], a[50:51], v[36:39]  // 002ff0
	ds_read_b128 a[64:67], v34  // 002ff8
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[36:37], a[52:53], v[36:39]  // 003000
	s_add_u32 m0, 0x100, s60  // 003008
	buffer_load_dword v31, s[4:7], 0 offen lds  // 003010
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[38:39], a[54:55], v[36:39]  // 003018
	ds_read_b128 a[68:71], v34 offset:64  // 003020
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v82, v72  // 003028
	v_mov_b32_e32 v5, v4  // 00302c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[40:41], a[48:49], 0  // 003030
	buffer_load_dwordx4 a[16:19], v26, s[8:11], 0 offen  // 003038
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[42:43], a[50:51], v[40:43]  // 003040
	buffer_load_dword v72, v83, s[20:23], 0 offen  // 003048
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[44:45], a[52:53], v[40:43]  // 003050
	buffer_load_dwordx4 a[20:23], v27, s[8:11], 0 offen  // 003058
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[46:47], a[54:55], v[40:43]  // 003060
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 003068
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 003070
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 003078
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 003080
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[32:33], a[56:57], 0  // 003088
	s_add_u32 m0, 0x200, s60  // 003090
	buffer_load_dword v32, s[4:7], 0 offen lds  // 003098
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[34:35], a[58:59], v[44:47]  // 0030a0
	ds_read_b128 a[72:75], v34 offset:512  // 0030a8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[36:37], a[60:61], v[44:47]  // 0030b0
	s_add_u32 m0, 0x300, s60  // 0030b8
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0030c0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[38:39], a[62:63], v[44:47]  // 0030c8
	buffer_load_dwordx4 a[24:27], v28, s[8:11], 0 offen  // 0030e8
	s_add_u32 s50, 0x200, s42  // 003100
	s_cmp_lt_u32 s50, s43  // 003108
	s_cselect_b32 s54, s54, 0  // 00310c
	ds_read_b128 a[76:79], v34 offset:576  // 0030d0
	v_mul_f32_e32 v4, v82, v73  // 0030d8
	v_mov_b32_e32 v5, v4  // 0030dc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[40:41], a[56:57], 0  // 0030e0
	s_add_u32 s50, 0x180, s42  // 003110
	s_cmp_lt_u32 s50, s43  // 003118
	s_cselect_b32 s55, s55, 0  // 00311c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[42:43], a[58:59], v[48:51]  // 0030f0
	buffer_load_dword v73, v84, s[20:23], 0 offen  // 0030f8
	s_add_u32 s50, 0x200, s42  // 003120
	s_cmp_lt_u32 s50, s43  // 003128
	s_cselect_b32 s56, s56, 0  // 00312c
	s_add_u32 s50, 0x180, s42  // 003130
	s_cmp_lt_u32 s50, s43  // 003138
	s_cselect_b32 s57, s57, 0  // 00313c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[44:45], a[60:61], v[48:51]  // 003140
	buffer_load_dwordx4 a[28:31], v29, s[8:11], 0 offen  // 003148
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[46:47], a[62:63], v[48:51]  // 003150
	buffer_load_dword v81, v87, s[24:27], 0 offen  // 003158
	s_add_u32 s4, s54, s4  // 003160
	s_addc_u32 s5, 0, s5  // 003164
	s_sub_u32 s6, s6, s54  // 003168
	s_add_u32 s8, s55, s8  // 00316c
	s_addc_u32 s9, 0, s9  // 003170
	s_sub_u32 s10, s10, s55  // 003174
	s_add_u32 s20, s56, s20  // 003178
	s_addc_u32 s21, 0, s21  // 00317c
	s_add_u32 s24, s57, s24  // 003180
	s_addc_u32 s25, 0, s25  // 003184
	s_sub_u32 s26, s26, s57  // 003188
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 00318c
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 003194
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 00319c
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 0031a4
	s_addk_i32 s42, 0x80  // 0031ac
	s_cmp_lt_i32 s42, s43  // 0031b0
	s_cbranch_scc0 L_3768  // 0031b4
	s_waitcnt vmcnt(15) & lgkmcnt(0)
	s_barrier  // 0031bc
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[0:1], a[64:65], 0  // 0031c0
	s_add_u32 m0, 0, s58  // 0031c8
	buffer_load_dword v30, s[4:7], 0 offen lds  // 0031cc
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[2:3], a[66:67], v[36:39]  // 0031d4
	ds_read_b128 a[48:51], v34 offset:4224  // 0031dc
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[4:5], a[68:69], v[36:39]  // 0031e4
	s_add_u32 m0, 0x100, s58  // 0031ec
	buffer_load_dword v31, s[4:7], 0 offen lds  // 0031f4
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[6:7], a[70:71], v[36:39]  // 0031fc
	ds_read_b128 a[52:55], v34 offset:4288  // 003204
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v80, v68  // 00320c
	v_mov_b32_e32 v5, v4  // 003210
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[8:9], a[64:65], 0  // 003214
	buffer_load_dwordx4 a[32:35], v26, s[8:11], 0 offen  // 00321c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[10:11], a[66:67], v[40:43]  // 003224
	buffer_load_dword v68, v83, s[20:23], 0 offen  // 00322c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[12:13], a[68:69], v[40:43]  // 003234
	buffer_load_dwordx4 a[36:39], v27, s[8:11], 0 offen  // 00323c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[14:15], a[70:71], v[40:43]  // 003244
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 00324c
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 003254
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 00325c
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 003264
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[0:1], a[72:73], 0  // 00326c
	s_add_u32 m0, 0x200, s58  // 003274
	buffer_load_dword v32, s[4:7], 0 offen lds  // 00327c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[2:3], a[74:75], v[44:47]  // 003284
	ds_read_b128 a[56:59], v34 offset:4736  // 00328c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[4:5], a[76:77], v[44:47]  // 003294
	s_add_u32 m0, 0x300, s58  // 00329c
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0032a4
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[6:7], a[78:79], v[44:47]  // 0032ac
	buffer_load_dwordx4 a[40:43], v28, s[8:11], 0 offen  // 0032cc
	s_add_u32 s50, 0x200, s42  // 0032e4
	s_cmp_lt_u32 s50, s43  // 0032ec
	s_cselect_b32 s54, s54, 0  // 0032f0
	ds_read_b128 a[60:63], v34 offset:4800  // 0032b4
	v_mul_f32_e32 v4, v80, v69  // 0032bc
	v_mov_b32_e32 v5, v4  // 0032c0
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[8:9], a[72:73], 0  // 0032c4
	s_add_u32 s50, 0x180, s42  // 0032f4
	s_cmp_lt_u32 s50, s43  // 0032fc
	s_cselect_b32 s55, s55, 0  // 003300
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[10:11], a[74:75], v[48:51]  // 0032d4
	buffer_load_dword v69, v84, s[20:23], 0 offen  // 0032dc
	s_add_u32 s50, 0x200, s42  // 003304
	s_cmp_lt_u32 s50, s43  // 00330c
	s_cselect_b32 s56, s56, 0  // 003310
	s_add_u32 s50, 0x180, s42  // 003314
	s_cmp_lt_u32 s50, s43  // 00331c
	s_cselect_b32 s57, s57, 0  // 003320
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[12:13], a[76:77], v[48:51]  // 003324
	buffer_load_dwordx4 a[44:47], v29, s[8:11], 0 offen  // 00332c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[14:15], a[78:79], v[48:51]  // 003334
	buffer_load_dword v82, v87, s[24:27], 0 offen  // 00333c
	s_add_u32 s4, s54, s4  // 003344
	s_addc_u32 s5, 0, s5  // 003348
	s_sub_u32 s6, s6, s54  // 00334c
	s_add_u32 s8, s55, s8  // 003350
	s_addc_u32 s9, 0, s9  // 003354
	s_sub_u32 s10, s10, s55  // 003358
	s_add_u32 s20, s56, s20  // 00335c
	s_addc_u32 s21, 0, s21  // 003360
	s_add_u32 s24, s57, s24  // 003364
	s_addc_u32 s25, 0, s25  // 003368
	s_sub_u32 s26, s26, s57  // 00336c
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 003370
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 003378
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 003380
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 003388
	s_addk_i32 s42, 0x80  // 003390
	s_cmp_lt_i32 s42, s43  // 003394
	s_cbranch_scc0 L_3768  // 003398
	s_waitcnt vmcnt(15) & lgkmcnt(0)
	s_barrier  // 0033a0
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[16:17], a[48:49], 0  // 0033a4
	s_add_u32 m0, 0, s59  // 0033ac
	buffer_load_dword v30, s[4:7], 0 offen lds  // 0033b0
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[18:19], a[50:51], v[36:39]  // 0033b8
	ds_read_b128 a[64:67], v34 offset:8448  // 0033c0
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[20:21], a[52:53], v[36:39]  // 0033c8
	s_add_u32 m0, 0x100, s59  // 0033d0
	buffer_load_dword v31, s[4:7], 0 offen lds  // 0033d8
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[22:23], a[54:55], v[36:39]  // 0033e0
	ds_read_b128 a[68:71], v34 offset:8512  // 0033e8
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v81, v70  // 0033f0
	v_mov_b32_e32 v5, v4  // 0033f4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[24:25], a[48:49], 0  // 0033f8
	buffer_load_dwordx4 a[0:3], v26, s[8:11], 0 offen  // 003400
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[26:27], a[50:51], v[40:43]  // 003408
	buffer_load_dword v70, v83, s[20:23], 0 offen  // 003410
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[28:29], a[52:53], v[40:43]  // 003418
	buffer_load_dwordx4 a[4:7], v27, s[8:11], 0 offen  // 003420
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[30:31], a[54:55], v[40:43]  // 003428
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 003430
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 003438
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 003440
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 003448
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[16:17], a[56:57], 0  // 003450
	s_add_u32 m0, 0x200, s59  // 003458
	buffer_load_dword v32, s[4:7], 0 offen lds  // 003460
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[18:19], a[58:59], v[44:47]  // 003468
	ds_read_b128 a[72:75], v34 offset:8960  // 003470
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[20:21], a[60:61], v[44:47]  // 003478
	s_add_u32 m0, 0x300, s59  // 003480
	buffer_load_dword v33, s[4:7], 0 offen lds  // 003488
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[22:23], a[62:63], v[44:47]  // 003490
	buffer_load_dwordx4 a[8:11], v28, s[8:11], 0 offen  // 0034b0
	s_add_u32 s50, 0x200, s42  // 0034c8
	s_cmp_lt_u32 s50, s43  // 0034d0
	s_cselect_b32 s54, s54, 0  // 0034d4
	ds_read_b128 a[76:79], v34 offset:9024  // 003498
	v_mul_f32_e32 v4, v81, v71  // 0034a0
	v_mov_b32_e32 v5, v4  // 0034a4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[24:25], a[56:57], 0  // 0034a8
	s_add_u32 s50, 0x180, s42  // 0034d8
	s_cmp_lt_u32 s50, s43  // 0034e0
	s_cselect_b32 s55, s55, 0  // 0034e4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[26:27], a[58:59], v[48:51]  // 0034b8
	buffer_load_dword v71, v84, s[20:23], 0 offen  // 0034c0
	s_add_u32 s50, 0x200, s42  // 0034e8
	s_cmp_lt_u32 s50, s43  // 0034f0
	s_cselect_b32 s56, s56, 0  // 0034f4
	s_add_u32 s50, 0x180, s42  // 0034f8
	s_cmp_lt_u32 s50, s43  // 003500
	s_cselect_b32 s57, s57, 0  // 003504
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[28:29], a[60:61], v[48:51]  // 003508
	buffer_load_dwordx4 a[12:15], v29, s[8:11], 0 offen  // 003510
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[30:31], a[62:63], v[48:51]  // 003518
	buffer_load_dword v80, v87, s[24:27], 0 offen  // 003520
	s_add_u32 s4, s54, s4  // 003528
	s_addc_u32 s5, 0, s5  // 00352c
	s_sub_u32 s6, s6, s54  // 003530
	s_add_u32 s8, s55, s8  // 003534
	s_addc_u32 s9, 0, s9  // 003538
	s_sub_u32 s10, s10, s55  // 00353c
	s_add_u32 s20, s56, s20  // 003540
	s_addc_u32 s21, 0, s21  // 003544
	s_add_u32 s24, s57, s24  // 003548
	s_addc_u32 s25, 0, s25  // 00354c
	s_sub_u32 s26, s26, s57  // 003550
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 003554
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 00355c
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 003564
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 00356c
	s_addk_i32 s42, 0x80  // 003574
	s_cmp_lt_i32 s42, s43  // 003578
	s_cbranch_scc0 L_3768  // 00357c
	s_waitcnt vmcnt(15) & lgkmcnt(0)
	s_barrier  // 003584
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[32:33], a[64:65], 0  // 003588
	s_add_u32 m0, 0, s60  // 003590
	buffer_load_dword v30, s[4:7], 0 offen lds  // 003594
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[34:35], a[66:67], v[36:39]  // 00359c
	ds_read_b128 a[48:51], v34  // 0035a4
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[36:37], a[68:69], v[36:39]  // 0035ac
	s_add_u32 m0, 0x100, s60  // 0035b4
	buffer_load_dword v31, s[4:7], 0 offen lds  // 0035bc
	v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[38:39], a[70:71], v[36:39]  // 0035c4
	ds_read_b128 a[52:55], v34 offset:64  // 0035cc
	s_waitcnt vmcnt(13)
	v_mul_f32_e32 v4, v82, v72  // 0035d4
	v_mov_b32_e32 v5, v4  // 0035d8
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[40:41], a[64:65], 0  // 0035dc
	buffer_load_dwordx4 a[16:19], v26, s[8:11], 0 offen  // 0035e4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[42:43], a[66:67], v[40:43]  // 0035ec
	buffer_load_dword v72, v83, s[20:23], 0 offen  // 0035f4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[44:45], a[68:69], v[40:43]  // 0035fc
	buffer_load_dwordx4 a[20:23], v27, s[8:11], 0 offen  // 003604
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[46:47], a[70:71], v[40:43]  // 00360c
	s_nop 0
	v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]  // 003614
	v_pk_fma_f32 v[54:55], v[4:5], v[38:39], v[54:55]  // 00361c
	v_pk_fma_f32 v[56:57], v[4:5], v[40:41], v[56:57]  // 003624
	v_pk_fma_f32 v[58:59], v[4:5], v[42:43], v[58:59]  // 00362c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[32:33], a[72:73], 0  // 003634
	s_add_u32 m0, 0x200, s60  // 00363c
	buffer_load_dword v32, s[4:7], 0 offen lds  // 003644
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[34:35], a[74:75], v[44:47]  // 00364c
	ds_read_b128 a[56:59], v34 offset:512  // 003654
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[36:37], a[76:77], v[44:47]  // 00365c
	s_add_u32 m0, 0x300, s60  // 003664
	buffer_load_dword v33, s[4:7], 0 offen lds  // 00366c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[38:39], a[78:79], v[44:47]  // 003674
	buffer_load_dwordx4 a[24:27], v28, s[8:11], 0 offen  // 003694
	s_add_u32 s50, 0x200, s42  // 0036ac
	s_cmp_lt_u32 s50, s43  // 0036b4
	s_cselect_b32 s54, s54, 0  // 0036b8
	ds_read_b128 a[60:63], v34 offset:576  // 00367c
	v_mul_f32_e32 v4, v82, v73  // 003684
	v_mov_b32_e32 v5, v4  // 003688
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[40:41], a[72:73], 0  // 00368c
	s_add_u32 s50, 0x180, s42  // 0036bc
	s_cmp_lt_u32 s50, s43  // 0036c4
	s_cselect_b32 s55, s55, 0  // 0036c8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[42:43], a[74:75], v[48:51]  // 00369c
	buffer_load_dword v73, v84, s[20:23], 0 offen  // 0036a4
	s_add_u32 s50, 0x200, s42  // 0036cc
	s_cmp_lt_u32 s50, s43  // 0036d4
	s_cselect_b32 s56, s56, 0  // 0036d8
	s_add_u32 s50, 0x180, s42  // 0036dc
	s_cmp_lt_u32 s50, s43  // 0036e4
	s_cselect_b32 s57, s57, 0  // 0036e8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[44:45], a[76:77], v[48:51]  // 0036ec
	buffer_load_dwordx4 a[28:31], v29, s[8:11], 0 offen  // 0036f4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[46:47], a[78:79], v[48:51]  // 0036fc
	buffer_load_dword v81, v87, s[24:27], 0 offen  // 003704
	s_add_u32 s4, s54, s4  // 00370c
	s_addc_u32 s5, 0, s5  // 003710
	s_sub_u32 s6, s6, s54  // 003714
	s_add_u32 s8, s55, s8  // 003718
	s_addc_u32 s9, 0, s9  // 00371c
	s_sub_u32 s10, s10, s55  // 003720
	s_add_u32 s20, s56, s20  // 003724
	s_addc_u32 s21, 0, s21  // 003728
	s_add_u32 s24, s57, s24  // 00372c
	s_addc_u32 s25, 0, s25  // 003730
	s_sub_u32 s26, s26, s57  // 003734
	v_pk_fma_f32 v[60:61], v[4:5], v[44:45], v[60:61]  // 003738
	v_pk_fma_f32 v[62:63], v[4:5], v[46:47], v[62:63]  // 003740
	v_pk_fma_f32 v[64:65], v[4:5], v[48:49], v[64:65]  // 003748
	v_pk_fma_f32 v[66:67], v[4:5], v[50:51], v[66:67]  // 003750
	s_addk_i32 s42, 0x80  // 003758
	s_cmp_lt_i32 s42, s43  // 00375c
	s_cbranch_scc0 L_3768  // 003760
	s_branch L_2c0c  // 003764
L_3768:
	s_cmp_eq_u32 s38, 1  // 003768
	s_cbranch_scc1 L_39b8  // 00376c
	v_add_f32_e32 v52, v52, v12  // 003770
	v_add_f32_e32 v53, v53, v13  // 003774
	v_perm_b32 v36, v53, v52, s48  // 003778
	v_add_f32_e32 v54, v54, v14  // 003780
	v_add_f32_e32 v55, v55, v15  // 003784
	v_perm_b32 v37, v55, v54, s48  // 003788
	v_add_f32_e32 v56, v56, v16  // 003790
	v_add_f32_e32 v57, v57, v17  // 003794
	v_perm_b32 v38, v57, v56, s48  // 003798
	v_add_f32_e32 v58, v58, v18  // 0037a0
	v_add_f32_e32 v59, v59, v19  // 0037a4
	v_perm_b32 v39, v59, v58, s48  // 0037a8
	v_add_f32_e32 v60, v60, v12  // 0037b0
	v_add_f32_e32 v61, v61, v13  // 0037b4
	v_perm_b32 v40, v61, v60, s48  // 0037b8
	v_add_f32_e32 v62, v62, v14  // 0037c0
	v_add_f32_e32 v63, v63, v15  // 0037c4
	v_perm_b32 v41, v63, v62, s48  // 0037c8
	v_add_f32_e32 v64, v64, v16  // 0037d0
	v_add_f32_e32 v65, v65, v17  // 0037d4
	v_perm_b32 v42, v65, v64, s48  // 0037d8
	v_add_f32_e32 v66, v66, v18  // 0037e0
	v_add_f32_e32 v67, v67, v19  // 0037e4
	v_perm_b32 v43, v67, v66, s48  // 0037e8
	v_lshrrev_b32_e32 v4, 4, v0  // 0037f0
	v_mul_u32_u24_e32 v34, 34, v4  // 0037f4
	v_and_b32_e32 v4, 15, v0  // 0037f8
	v_mul_lo_u32 v5, 2, v4  // 0037fc
	v_add_u32_e32 v34, v5, v34  // 003804
	s_mul_i32 s50, s47, 0x110  // 003808
	v_add_u32_e32 v34, s50, v34  // 003810
	v_lshlrev_b32_e32 v34, 2, v34  // 003814
	v_lshrrev_b32_e32 v4, 1, v0  // 003818
	v_mul_u32_u24_e32 v30, 34, v4  // 00381c
	v_and_b32_e32 v5, 1, v0  // 003820
	v_add_u32_e32 v30, v5, v30  // 003824
	s_mul_i32 s50, s47, 2  // 003828
	v_add_u32_e32 v30, s50, v30  // 00382c
	v_lshlrev_b32_e32 v30, 2, v30  // 003830
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 003834
	s_barrier  // 003838
	ds_write_b64 v34, v[36:37]  // 00383c
	ds_write_b64 v34, v[38:39] offset:544  // 003844
	ds_write_b64 v34, v[40:41] offset:4352  // 00384c
	ds_write_b64 v34, v[42:43] offset:4896  // 003854
	s_waitcnt lgkmcnt(0)  // 00385c
	s_barrier  // 003860
	ds_read_b32 v36, v30  // 003864
	ds_read_b32 v37, v30 offset:32  // 00386c
	ds_read_b32 v38, v30 offset:64  // 003874
	ds_read_b32 v39, v30 offset:96  // 00387c
	ds_read_b32 v40, v30 offset:4352  // 003884
	ds_read_b32 v41, v30 offset:4384  // 00388c
	ds_read_b32 v42, v30 offset:4416  // 003894
	ds_read_b32 v43, v30 offset:4448  // 00389c
	s_waitcnt lgkmcnt(0)  // 0038a4
	s_barrier  // 0038a8
	s_mul_i32 s50, s37, 4  // 0038ac
	s_mul_i32 s51, s37, 8  // 0038b0
	s_mul_i32 s52, s37, 16  // 0038b4
	v_mov_b32_e32 v4, v22  // 0038b8
	v_mov_b32_e32 v5, 0  // 0038bc
	v_mov_b32_e32 v7, 0  // 0038c0
	v_mov_b32_e32 v9, 0  // 0038c4
	v_mov_b32_e32 v11, 0  // 0038c8
	v_mov_b32_e32 v6, v4  // 0038cc
	v_add_u32_e64 v10, v4, s51  // 0038d0
	s_cmp_ge_u32 s77, s32  // 0038d8
	s_cbranch_scc1 L_3a58  // 0038dc
	global_atomic_pk_add_bf16 v6, v36, s[80:81]  // 0038e0
	v_add_u32_e64 v8, v6, s50  // 0038e8
	s_add_i32 s77, s77, 4  // 0038f0
	s_cmp_ge_u32 s77, s32  // 0038f4
	s_cbranch_scc1 L_3a58  // 0038f8
	global_atomic_pk_add_bf16 v8, v37, s[80:81]  // 0038fc
	s_add_i32 s77, s77, 4  // 003904
	s_cmp_ge_u32 s77, s32  // 003908
	s_cbranch_scc1 L_3a58  // 00390c
	global_atomic_pk_add_bf16 v10, v38, s[80:81]  // 003910
	v_add_u32_e64 v12, v10, s50  // 003918
	s_add_i32 s77, s77, 4  // 003920
	s_cmp_ge_u32 s77, s32  // 003924
	s_cbranch_scc1 L_3a58  // 003928
	global_atomic_pk_add_bf16 v12, v39, s[80:81]  // 00392c
	s_add_i32 s77, s77, 4  // 003934
	v_add_u32_e64 v4, v4, s52  // 003938
	v_mov_b32_e32 v6, v4  // 003940
	v_add_u32_e64 v10, v4, s51  // 003944
	s_cmp_ge_u32 s77, s32  // 00394c
	s_cbranch_scc1 L_3a58  // 003950
	global_atomic_pk_add_bf16 v6, v40, s[80:81]  // 003954
	v_add_u32_e64 v8, v6, s50  // 00395c
	s_add_i32 s77, s77, 4  // 003964
	s_cmp_ge_u32 s77, s32  // 003968
	s_cbranch_scc1 L_3a58  // 00396c
	global_atomic_pk_add_bf16 v8, v41, s[80:81]  // 003970
	s_add_i32 s77, s77, 4  // 003978
	s_cmp_ge_u32 s77, s32  // 00397c
	s_cbranch_scc1 L_3a58  // 003980
	global_atomic_pk_add_bf16 v10, v42, s[80:81]  // 003984
	v_add_u32_e64 v12, v10, s50  // 00398c
	s_add_i32 s77, s77, 4  // 003994
	s_cmp_ge_u32 s77, s32  // 003998
	s_cbranch_scc1 L_3a58  // 00399c
	global_atomic_pk_add_bf16 v12, v43, s[80:81]  // 0039a0
	s_add_i32 s77, s77, 4  // 0039a8
	v_add_u32_e64 v4, v4, s52  // 0039ac
	s_branch L_3a58  // 0039b4
L_39b8:
	v_add_f32_e32 v52, v52, v12  // 0039b8
	v_add_f32_e32 v53, v53, v13  // 0039bc
	v_perm_b32 v36, v53, v52, s48  // 0039c0
	v_add_f32_e32 v54, v54, v14  // 0039c8
	v_add_f32_e32 v55, v55, v15  // 0039cc
	v_perm_b32 v37, v55, v54, s48  // 0039d0
	buffer_store_dwordx2 v[36:37], v20, s[16:19], 0 offen  // 0039d8
	v_add_f32_e32 v56, v56, v16  // 0039e0
	v_add_f32_e32 v57, v57, v17  // 0039e4
	v_perm_b32 v38, v57, v56, s48  // 0039e8
	v_add_f32_e32 v58, v58, v18  // 0039f0
	v_add_f32_e32 v59, v59, v19  // 0039f4
	v_perm_b32 v39, v59, v58, s48  // 0039f8
	buffer_store_dwordx2 v[38:39], v20, s[16:19], 0 offen offset:32  // 003a00
	v_add_f32_e32 v60, v60, v12  // 003a08
	v_add_f32_e32 v61, v61, v13  // 003a0c
	v_perm_b32 v40, v61, v60, s48  // 003a10
	v_add_f32_e32 v62, v62, v14  // 003a18
	v_add_f32_e32 v63, v63, v15  // 003a1c
	v_perm_b32 v41, v63, v62, s48  // 003a20
	buffer_store_dwordx2 v[40:41], v21, s[16:19], 0 offen  // 003a28
	v_add_f32_e32 v64, v64, v16  // 003a30
	v_add_f32_e32 v65, v65, v17  // 003a34
	v_perm_b32 v42, v65, v64, s48  // 003a38
	v_add_f32_e32 v66, v66, v18  // 003a40
	v_add_f32_e32 v67, v67, v19  // 003a44
	v_perm_b32 v43, v67, v66, s48  // 003a48
	buffer_store_dwordx2 v[42:43], v21, s[16:19], 0 offen offset:32  // 003a50
L_3a58:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 003a58
	s_endpgm  // 003a5c
.Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E:
	.size _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E, .Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E-_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E
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
    .name:           _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_32x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
