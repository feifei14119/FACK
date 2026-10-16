// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_64x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E
	.protected _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E
	.p2align 8
	.type _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E,@function
_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E:
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
	s_mul_i32 s50, s45, 64  // 00258c
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
	s_mul_i32 s50, s45, 64  // 0025c0
	s_sub_i32 s51, s32, s50  // 0025c4
	s_cmp_lt_u32 s51, 64  // 0025c8
	s_cselect_b32 s50, s51, 64  // 0025cc
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
	s_mul_i32 s50, 64, s45  // 002690
	s_mul_hi_u32 s52, 4, s50  // 002694
	s_mul_i32 s51, 4, s50  // 002698
	s_add_u32 s20, s20, s51  // 00269c
	s_addc_u32 s21, s21, s52  // 0026a0
	s_sub_i32 s51, s32, s50  // 0026a4
	s_cmp_lt_u32 s51, 64  // 0026a8
	s_cselect_b32 s50, s51, 64  // 0026ac
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
	v_and_b32_e64 v135, v0, 15  // 0026e8
	v_lshlrev_b32_e32 v135, 2, v135  // 0026f0
	s_mov_b32 s50, 64  // 0026f4
	v_add_u32_e64 v136, v135, s50  // 0026f8
	s_mov_b32 s50, 0x80  // 002700
	v_add_u32_e64 v137, v135, s50  // 002708
	s_mov_b32 s50, 0xc0  // 002710
	v_add_u32_e64 v138, v135, s50  // 002718
	s_mul_i32 s51, s41, s44  // 002720
	s_mul_hi_u32 s52, 4, s51  // 002724
	s_add_u32 s25, s25, s52  // 002728
	s_mul_i32 s52, 4, s51  // 00272c
	s_add_u32 s24, s24, s52  // 002730
	s_addc_u32 s25, s25, 0  // 002734
	s_lshr_b32 s50, s76, 7  // 002738
	s_mul_i32 s50, s50, s75  // 00273c
	s_lshl_b32 s50, s50, 2  // 002740
	s_add_u32 s24, s24, s50  // 002744
	s_addc_u32 s25, s25, 0  // 002748
	s_sub_u32 s26, s26, s50  // 00274c
	v_mov_b32_e32 v143, 0  // 002750
	v_lshrrev_b32_e32 v4, 5, v0  // 002754
	v_lshlrev_b32_e32 v4, 2, v4  // 002758
	v_mul_i32_i24_e32 v4, s35, v4  // 00275c
	v_and_b32_e32 v34, 31, v0  // 002760
	v_lshlrev_b32_e32 v34, 2, v34  // 002764
	s_mul_i32 s50, 64, s45  // 002768
	s_sub_i32 s51, s32, s50  // 00276c
	s_cmp_lt_u32 s51, 64  // 002770
	s_cselect_b32 s51, s51, 64  // 002774
	s_mul_i32 s52, s35, s50  // 002778
	s_mul_hi_u32 s50, s35, s50  // 00277c
	s_add_u32 s4, s4, s52  // 002780
	s_addc_u32 s5, s5, s50  // 002784
	s_mul_i32 s50, s35, s51  // 002788
	s_mov_b32 s6, s50  // 00278c
	s_mov_b32 s7, 0x20000  // 002790
	s_mul_i32 s51, s76, s75  // 002798
	s_add_u32 s4, s51, s4  // 00279c
	s_addc_u32 s5, 0, s5  // 0027a0
	s_sub_u32 s6, s6, s51  // 0027a4
	s_mul_i32 s50, s35, s47  // 0027a8
	v_add3_u32 v34, v4, v34, s50  // 0027ac
	s_lshl_b32 s50, s35, 3  // 0027b4
	v_add_u32_e32 v35, s50, v34  // 0027b8
	v_add_u32_e32 v36, s50, v35  // 0027bc
	v_add_u32_e32 v37, s50, v36  // 0027c0
	v_add_u32_e32 v38, s50, v37  // 0027c4
	v_add_u32_e32 v39, s50, v38  // 0027c8
	v_add_u32_e32 v40, s50, v39  // 0027cc
	v_add_u32_e32 v41, s50, v40  // 0027d0
	s_mov_b32 s54, 0x80  // 0027d4
	s_mul_i32 s56, s32, 4  // 0027dc
	s_mov_b32 s57, 4  // 0027e0
	s_mov_b32 s50, 64  // 0027e4
	s_lshr_b32 s50, s50, 2  // 0027e8
	s_mul_i32 s50, s50, 32  // 0027ec
	s_mov_b32 s51, 8  // 0027f0
	s_add_u32 s50, s50, s51  // 0027f4
	v_lshrrev_b32_e32 v4, 4, v0  // 0027f8
	v_and_b32_e32 v5, 15, v0  // 0027fc
	v_and_b32_e32 v6, 3, v5  // 002800
	v_lshrrev_b32_e32 v7, 2, v5  // 002804
	v_lshlrev_b32_e32 v4, 2, v4  // 002808
	v_mul_lo_u32 v6, v6, s50  // 00280c
	v_lshlrev_b32_e32 v7, 5, v7  // 002814
	v_add_u32_e32 v4, v4, v6  // 002818
	v_add_u32_e32 v4, v4, v7  // 00281c
	v_lshlrev_b32_e32 v42, 2, v4  // 002820
	s_mul_i32 s50, 0x820, s47  // 002824
	s_add_u32 s58, 0, s50  // 00282c
	s_add_u32 s59, 0x2080, s58  // 002830
	s_add_u32 s60, 0x2080, s59  // 002838
	s_mov_b32 s55, 0x800  // 002840
	s_mul_i32 s49, 0x80, s44  // 002848
	s_sub_i32 s51, s33, s49  // 002850
	s_cmp_lt_u32 s51, 0x80  // 002854
	s_cselect_b32 s50, s51, 0x80  // 00285c
	s_mul_i32 s51, s36, s49  // 002864
	s_mul_hi_u32 s52, s36, s49  // 002868
	s_add_u32 s8, s8, s51  // 00286c
	s_addc_u32 s9, s9, s52  // 002870
	s_mul_i32 s51, s36, s50  // 002874
	s_mov_b32 s10, s51  // 002878
	s_mov_b32 s11, 0x20000  // 00287c
	s_lshr_b32 s51, s76, 7  // 002884
	s_mul_i32 s50, s55, s75  // 002888
	s_mul_i32 s50, s51, s50  // 00288c
	s_add_u32 s8, s50, s8  // 002890
	s_addc_u32 s9, 0, s9  // 002894
	s_sub_u32 s10, s10, s50  // 002898
	s_lshl_b32 s50, s47, 5  // 00289c
	s_mul_i32 s50, s36, s50  // 0028a0
	v_lshlrev_b32_e32 v30, 4, v0  // 0028a4
	v_add_u32_e32 v30, s50, v30  // 0028a8
	s_mov_b32 s50, 0x400  // 0028ac
	v_add_u32_e64 v31, v30, s50  // 0028b4
	s_mul_i32 s50, s36, 16  // 0028bc
	v_add_u32_e64 v32, v30, s50  // 0028c0
	v_add_u32_e64 v33, v31, s50  // 0028c8
	s_add_u32 m0, 0, s58  // 0028d0
	buffer_load_dword v34, s[4:7], 0 offen lds  // 0028d4
	s_add_u32 m0, 0x100, s58  // 0028dc
	buffer_load_dword v35, s[4:7], 0 offen lds  // 0028e4
	s_add_u32 m0, 0x200, s58  // 0028ec
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0028f4
	s_add_u32 m0, 0x300, s58  // 0028fc
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002904
	s_add_u32 m0, 0x400, s58  // 00290c
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002914
	s_add_u32 m0, 0x500, s58  // 00291c
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002924
	s_add_u32 m0, 0x600, s58  // 00292c
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002934
	s_add_u32 m0, 0x700, s58  // 00293c
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002944
	s_mov_b32 s53, 0  // 00294c
	s_add_u32 s50, 0x80, s53  // 002950
	s_cmp_lt_u32 s50, s34  // 002958
	s_cselect_b32 s54, s54, 0  // 00295c
	s_add_u32 s4, s54, s4  // 002960
	s_addc_u32 s5, 0, s5  // 002964
	s_sub_u32 s6, s6, s54  // 002968
	buffer_load_dword v108, v135, s[20:23], 0 offen  // 00296c
	buffer_load_dword v109, v136, s[20:23], 0 offen  // 002974
	buffer_load_dword v110, v137, s[20:23], 0 offen  // 00297c
	buffer_load_dword v111, v138, s[20:23], 0 offen  // 002984
	s_add_u32 s50, 0x80, s53  // 00298c
	s_cmp_lt_u32 s50, s34  // 002994
	s_cselect_b32 s56, s56, 0  // 002998
	s_add_u32 s20, s56, s20  // 00299c
	s_addc_u32 s21, 0, s21  // 0029a0
	v_mov_b32_e32 v76, 0  // 0029a4
	v_mov_b32_e32 v77, 0  // 0029a8
	v_mov_b32_e32 v78, 0  // 0029ac
	v_mov_b32_e32 v79, 0  // 0029b0
	v_mov_b32_e32 v80, 0  // 0029b4
	v_mov_b32_e32 v81, 0  // 0029b8
	v_mov_b32_e32 v82, 0  // 0029bc
	v_mov_b32_e32 v83, 0  // 0029c0
	buffer_load_dwordx4 a[0:3], v30, s[8:11], 0 offen  // 0029c4
	buffer_load_dwordx4 a[4:7], v31, s[8:11], 0 offen  // 0029cc
	buffer_load_dwordx4 a[8:11], v32, s[8:11], 0 offen  // 0029d4
	buffer_load_dwordx4 a[12:15], v33, s[8:11], 0 offen  // 0029dc
	s_mov_b32 s53, 0  // 0029e4
	s_add_u32 s50, 0x80, s53  // 0029e8
	s_cmp_lt_u32 s50, s34  // 0029f0
	s_cselect_b32 s55, s55, 0  // 0029f4
	s_add_u32 s8, s55, s8  // 0029f8
	s_addc_u32 s9, 0, s9  // 0029fc
	s_sub_u32 s10, s10, s55  // 002a00
	buffer_load_dword v132, v143, s[24:27], 0 offen  // 002a04
	s_add_u32 s50, 0x80, s53  // 002a0c
	s_cmp_lt_u32 s50, s34  // 002a14
	s_cselect_b32 s57, s57, 0  // 002a18
	s_add_u32 s24, s57, s24  // 002a1c
	s_addc_u32 s25, 0, s25  // 002a20
	s_sub_u32 s26, s26, s57  // 002a24
	s_add_u32 m0, 0, s59  // 002a28
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002a2c
	s_add_u32 m0, 0x100, s59  // 002a34
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002a3c
	s_add_u32 m0, 0x200, s59  // 002a44
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002a4c
	s_add_u32 m0, 0x300, s59  // 002a54
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002a5c
	s_add_u32 m0, 0x400, s59  // 002a64
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002a6c
	s_add_u32 m0, 0x500, s59  // 002a74
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002a7c
	s_add_u32 m0, 0x600, s59  // 002a84
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002a8c
	s_add_u32 m0, 0x700, s59  // 002a94
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002a9c
	s_mov_b32 s53, 0x80  // 002aa4
	s_add_u32 s50, 0x80, s53  // 002aac
	s_cmp_lt_u32 s50, s34  // 002ab4
	s_cselect_b32 s54, s54, 0  // 002ab8
	s_add_u32 s4, s54, s4  // 002abc
	s_addc_u32 s5, 0, s5  // 002ac0
	s_sub_u32 s6, s6, s54  // 002ac4
	buffer_load_dword v112, v135, s[20:23], 0 offen  // 002ac8
	buffer_load_dword v113, v136, s[20:23], 0 offen  // 002ad0
	buffer_load_dword v114, v137, s[20:23], 0 offen  // 002ad8
	buffer_load_dword v115, v138, s[20:23], 0 offen  // 002ae0
	s_add_u32 s50, 0x80, s53  // 002ae8
	s_cmp_lt_u32 s50, s34  // 002af0
	s_cselect_b32 s56, s56, 0  // 002af4
	s_add_u32 s20, s56, s20  // 002af8
	s_addc_u32 s21, 0, s21  // 002afc
	v_mov_b32_e32 v84, 0  // 002b00
	v_mov_b32_e32 v85, 0  // 002b04
	v_mov_b32_e32 v86, 0  // 002b08
	v_mov_b32_e32 v87, 0  // 002b0c
	v_mov_b32_e32 v88, 0  // 002b10
	v_mov_b32_e32 v89, 0  // 002b14
	v_mov_b32_e32 v90, 0  // 002b18
	v_mov_b32_e32 v91, 0  // 002b1c
	buffer_load_dwordx4 a[16:19], v30, s[8:11], 0 offen  // 002b20
	buffer_load_dwordx4 a[20:23], v31, s[8:11], 0 offen  // 002b28
	buffer_load_dwordx4 a[24:27], v32, s[8:11], 0 offen  // 002b30
	buffer_load_dwordx4 a[28:31], v33, s[8:11], 0 offen  // 002b38
	s_mov_b32 s53, 0x80  // 002b40
	s_add_u32 s50, 0x80, s53  // 002b48
	s_cmp_lt_u32 s50, s34  // 002b50
	s_cselect_b32 s55, s55, 0  // 002b54
	s_add_u32 s8, s55, s8  // 002b58
	s_addc_u32 s9, 0, s9  // 002b5c
	s_sub_u32 s10, s10, s55  // 002b60
	buffer_load_dword v133, v143, s[24:27], 0 offen  // 002b64
	s_add_u32 s50, 0x80, s53  // 002b6c
	s_cmp_lt_u32 s50, s34  // 002b74
	s_cselect_b32 s57, s57, 0  // 002b78
	s_add_u32 s24, s57, s24  // 002b7c
	s_addc_u32 s25, 0, s25  // 002b80
	s_sub_u32 s26, s26, s57  // 002b84
	s_add_u32 m0, 0, s60  // 002b88
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002b8c
	s_add_u32 m0, 0x100, s60  // 002b94
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002b9c
	s_add_u32 m0, 0x200, s60  // 002ba4
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002bac
	s_add_u32 m0, 0x300, s60  // 002bb4
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002bbc
	s_add_u32 m0, 0x400, s60  // 002bc4
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002bcc
	s_add_u32 m0, 0x500, s60  // 002bd4
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002bdc
	s_add_u32 m0, 0x600, s60  // 002be4
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002bec
	s_add_u32 m0, 0x700, s60  // 002bf4
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002bfc
	s_mov_b32 s53, 0x100  // 002c04
	s_add_u32 s50, 0x80, s53  // 002c0c
	s_cmp_lt_u32 s50, s34  // 002c14
	s_cselect_b32 s54, s54, 0  // 002c18
	s_add_u32 s4, s54, s4  // 002c1c
	s_addc_u32 s5, 0, s5  // 002c20
	s_sub_u32 s6, s6, s54  // 002c24
	buffer_load_dword v116, v135, s[20:23], 0 offen  // 002c28
	buffer_load_dword v117, v136, s[20:23], 0 offen  // 002c30
	buffer_load_dword v118, v137, s[20:23], 0 offen  // 002c38
	buffer_load_dword v119, v138, s[20:23], 0 offen  // 002c40
	s_add_u32 s50, 0x80, s53  // 002c48
	s_cmp_lt_u32 s50, s34  // 002c50
	s_cselect_b32 s56, s56, 0  // 002c54
	s_add_u32 s20, s56, s20  // 002c58
	s_addc_u32 s21, 0, s21  // 002c5c
	v_mov_b32_e32 v92, 0  // 002c60
	v_mov_b32_e32 v93, 0  // 002c64
	v_mov_b32_e32 v94, 0  // 002c68
	v_mov_b32_e32 v95, 0  // 002c6c
	v_mov_b32_e32 v96, 0  // 002c70
	v_mov_b32_e32 v97, 0  // 002c74
	v_mov_b32_e32 v98, 0  // 002c78
	v_mov_b32_e32 v99, 0  // 002c7c
	v_mov_b32_e32 v100, 0  // 002c80
	v_mov_b32_e32 v101, 0  // 002c84
	v_mov_b32_e32 v102, 0  // 002c88
	v_mov_b32_e32 v103, 0  // 002c8c
	v_mov_b32_e32 v104, 0  // 002c90
	v_mov_b32_e32 v105, 0  // 002c94
	v_mov_b32_e32 v106, 0  // 002c98
	v_mov_b32_e32 v107, 0  // 002c9c
	s_mov_b32 s43, s34  // 002ca0
	s_mov_b32 s42, 0  // 002ca4
	s_waitcnt vmcnt(34)  // 002ca8
	s_barrier  // 002cac
	ds_read_b128 a[48:51], v42  // 002cb0
	ds_read_b128 a[52:55], v42 offset:64  // 002cb8
	ds_read_b128 a[56:59], v42 offset:512  // 002cc0
	ds_read_b128 a[60:63], v42 offset:576  // 002cc8
	ds_read_b128 a[64:67], v42 offset:1024  // 002cd0
	ds_read_b128 a[68:71], v42 offset:1088  // 002cd8
	ds_read_b128 a[72:75], v42 offset:1536  // 002ce0
	ds_read_b128 a[76:79], v42 offset:1600  // 002ce8
	s_mov_b32 s50, 0  // 002cf0
	s_mov_b32 s51, 1.0  // 002cf4
	s_cmp_eq_u32 s50, s75  // 002cf8
	s_cselect_b32 s50, s51, 0  // 002cfc
	v_mul_f32_e64 v12, v12, s50  // 002d00
	v_mul_f32_e64 v13, v13, s50  // 002d08
	v_mul_f32_e64 v14, v14, s50  // 002d10
	v_mul_f32_e64 v15, v15, s50  // 002d18
	v_mul_f32_e64 v16, v16, s50  // 002d20
	v_mul_f32_e64 v17, v17, s50  // 002d28
	v_mul_f32_e64 v18, v18, s50  // 002d30
	v_mul_f32_e64 v19, v19, s50  // 002d38
	v_and_b32_e64 v20, v0, 15  // 002d40
	v_mul_lo_u32 v20, v20, s37  // 002d48
	v_lshrrev_b32_e32 v4, 4, v0  // 002d50
	v_mul_i32_i24_e32 v4, 8, v4  // 002d54
	v_add_u32_e32 v20, v4, v20  // 002d58
	s_mul_i32 s50, 32, s47  // 002d5c
	s_mul_i32 s50, 2, s50  // 002d60
	v_add_u32_e32 v20, s50, v20  // 002d64
	s_mul_i32 s50, 16, s37  // 002d68
	v_add_u32_e32 v21, s50, v20  // 002d6c
	v_add_u32_e32 v22, s50, v21  // 002d70
	v_add_u32_e32 v23, s50, v22  // 002d74
	s_mul_i32 s50, s47, s37  // 002d78
	v_lshlrev_b32_e32 v5, 2, v0  // 002d7c
	v_add_u32_e32 v24, s50, v5  // 002d80
	s_mul_i32 s50, s45, 64  // 002d84
	s_add_i32 s77, s50, s47  // 002d88
	s_cmp_lt_i32 s42, s43  // 002d8c
	s_cbranch_scc0 L_4070  // 002d90
L_2d94:
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 002d98
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[0:1], a[48:49], 0  // 002d9c
	s_add_u32 m0, 0, s58  // 002da4
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002da8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[2:3], a[50:51], v[44:47]  // 002db0
	ds_read_b128 a[80:83], v42 offset:8320  // 002db8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[4:5], a[52:53], v[44:47]  // 002dc0
	s_add_u32 m0, 0x100, s58  // 002dc8
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002dd0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[6:7], a[54:55], v[44:47]  // 002dd8
	ds_read_b128 a[84:87], v42 offset:8384  // 002de0
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v132, v108  // 002de8
	v_mov_b32_e32 v5, v4  // 002dec
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[8:9], a[48:49], 0  // 002df0
	buffer_load_dwordx4 a[32:35], v30, s[8:11], 0 offen  // 002df8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[10:11], a[50:51], v[48:51]  // 002e00
	buffer_load_dword v108, v135, s[20:23], 0 offen  // 002e08
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[12:13], a[52:53], v[48:51]  // 002e10
	buffer_load_dwordx4 a[36:39], v31, s[8:11], 0 offen  // 002e18
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[14:15], a[54:55], v[48:51]  // 002e20
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 002e28
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 002e30
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 002e38
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 002e40
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[0:1], a[56:57], 0  // 002e48
	s_add_u32 m0, 0x200, s58  // 002e50
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002e58
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[2:3], a[58:59], v[52:55]  // 002e60
	ds_read_b128 a[88:91], v42 offset:8832  // 002e68
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[4:5], a[60:61], v[52:55]  // 002e70
	s_add_u32 m0, 0x300, s58  // 002e78
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002e80
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[6:7], a[62:63], v[52:55]  // 002e88
	ds_read_b128 a[92:95], v42 offset:8896  // 002e90
	v_mul_f32_e32 v4, v132, v109  // 002e98
	v_mov_b32_e32 v5, v4  // 002e9c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[8:9], a[56:57], 0  // 002ea0
	buffer_load_dwordx4 a[40:43], v32, s[8:11], 0 offen  // 002ea8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[10:11], a[58:59], v[56:59]  // 002eb0
	buffer_load_dword v109, v136, s[20:23], 0 offen  // 002eb8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[12:13], a[60:61], v[56:59]  // 002ec0
	buffer_load_dwordx4 a[44:47], v33, s[8:11], 0 offen  // 002ec8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[14:15], a[62:63], v[56:59]  // 002ed0
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 002ed8
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 002ee0
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 002ee8
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 002ef0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[64:65], 0  // 002ef8
	s_add_u32 m0, 0x400, s58  // 002f00
	buffer_load_dword v38, s[4:7], 0 offen lds  // 002f08
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[66:67], v[60:63]  // 002f10
	ds_read_b128 a[96:99], v42 offset:9344  // 002f18
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[68:69], v[60:63]  // 002f20
	s_add_u32 m0, 0x500, s58  // 002f28
	buffer_load_dword v39, s[4:7], 0 offen lds  // 002f30
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[70:71], v[60:63]  // 002f38
	ds_read_b128 a[100:103], v42 offset:9408  // 002f40
	v_mul_f32_e32 v4, v132, v110  // 002f48
	v_mov_b32_e32 v5, v4  // 002f4c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[64:65], 0  // 002f50
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[66:67], v[64:67]  // 002f58
	buffer_load_dword v110, v137, s[20:23], 0 offen  // 002f60
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[68:69], v[64:67]  // 002f68
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[70:71], v[64:67]  // 002f70
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 002f78
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 002f80
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 002f88
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 002f90
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[72:73], 0  // 002f98
	s_add_u32 m0, 0x600, s58  // 002fa0
	buffer_load_dword v40, s[4:7], 0 offen lds  // 002fa8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[74:75], v[68:71]  // 002fb0
	ds_read_b128 a[104:107], v42 offset:9856  // 002fb8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[76:77], v[68:71]  // 002fc0
	s_add_u32 m0, 0x700, s58  // 002fc8
	buffer_load_dword v41, s[4:7], 0 offen lds  // 002fd0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[78:79], v[68:71]  // 002fd8
	s_add_u32 s50, 0x200, s42  // 003008
	s_cmp_lt_u32 s50, s43  // 003010
	s_cselect_b32 s54, s54, 0  // 003014
	ds_read_b128 a[108:111], v42 offset:9920  // 002fe0
	v_mul_f32_e32 v4, v132, v111  // 002fe8
	v_mov_b32_e32 v5, v4  // 002fec
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[72:73], 0  // 002ff0
	s_add_u32 s50, 0x180, s42  // 003018
	s_cmp_lt_u32 s50, s43  // 003020
	s_cselect_b32 s55, s55, 0  // 003024
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[74:75], v[72:75]  // 002ff8
	buffer_load_dword v111, v138, s[20:23], 0 offen  // 003000
	s_add_u32 s50, 0x200, s42  // 003028
	s_cmp_lt_u32 s50, s43  // 003030
	s_cselect_b32 s56, s56, 0  // 003034
	s_add_u32 s50, 0x180, s42  // 003038
	s_cmp_lt_u32 s50, s43  // 003040
	s_cselect_b32 s57, s57, 0  // 003044
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[76:77], v[72:75]  // 003048
	s_add_u32 s4, s54, s4  // 003060
	s_addc_u32 s5, 0, s5  // 003064
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[78:79], v[72:75]  // 003050
	buffer_load_dword v134, v143, s[24:27], 0 offen  // 003058
	s_sub_u32 s6, s6, s54  // 003068
	s_add_u32 s8, s55, s8  // 00306c
	s_addc_u32 s9, 0, s9  // 003070
	s_sub_u32 s10, s10, s55  // 003074
	s_add_u32 s20, s56, s20  // 003078
	s_addc_u32 s21, 0, s21  // 00307c
	s_add_u32 s24, s57, s24  // 003080
	s_addc_u32 s25, 0, s25  // 003084
	s_sub_u32 s26, s26, s57  // 003088
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 00308c
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 003094
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 00309c
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 0030a4
	s_addk_i32 s42, 0x80  // 0030ac
	s_cmp_lt_i32 s42, s43  // 0030b0
	s_cbranch_scc0 L_4070  // 0030b4
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 0030bc
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[16:17], a[80:81], 0  // 0030c0
	s_add_u32 m0, 0, s59  // 0030c8
	buffer_load_dword v34, s[4:7], 0 offen lds  // 0030cc
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[18:19], a[82:83], v[44:47]  // 0030d4
	ds_read_b128 a[48:51], v42 offset:16640  // 0030dc
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[20:21], a[84:85], v[44:47]  // 0030e4
	s_add_u32 m0, 0x100, s59  // 0030ec
	buffer_load_dword v35, s[4:7], 0 offen lds  // 0030f4
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[22:23], a[86:87], v[44:47]  // 0030fc
	ds_read_b128 a[52:55], v42 offset:16704  // 003104
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v133, v112  // 00310c
	v_mov_b32_e32 v5, v4  // 003110
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[24:25], a[80:81], 0  // 003114
	buffer_load_dwordx4 a[0:3], v30, s[8:11], 0 offen  // 00311c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[26:27], a[82:83], v[48:51]  // 003124
	buffer_load_dword v112, v135, s[20:23], 0 offen  // 00312c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[28:29], a[84:85], v[48:51]  // 003134
	buffer_load_dwordx4 a[4:7], v31, s[8:11], 0 offen  // 00313c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[30:31], a[86:87], v[48:51]  // 003144
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 00314c
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 003154
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 00315c
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 003164
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[16:17], a[88:89], 0  // 00316c
	s_add_u32 m0, 0x200, s59  // 003174
	buffer_load_dword v36, s[4:7], 0 offen lds  // 00317c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[18:19], a[90:91], v[52:55]  // 003184
	ds_read_b128 a[56:59], v42 offset:17152  // 00318c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[20:21], a[92:93], v[52:55]  // 003194
	s_add_u32 m0, 0x300, s59  // 00319c
	buffer_load_dword v37, s[4:7], 0 offen lds  // 0031a4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[22:23], a[94:95], v[52:55]  // 0031ac
	ds_read_b128 a[60:63], v42 offset:17216  // 0031b4
	v_mul_f32_e32 v4, v133, v113  // 0031bc
	v_mov_b32_e32 v5, v4  // 0031c0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[24:25], a[88:89], 0  // 0031c4
	buffer_load_dwordx4 a[8:11], v32, s[8:11], 0 offen  // 0031cc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[26:27], a[90:91], v[56:59]  // 0031d4
	buffer_load_dword v113, v136, s[20:23], 0 offen  // 0031dc
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[28:29], a[92:93], v[56:59]  // 0031e4
	buffer_load_dwordx4 a[12:15], v33, s[8:11], 0 offen  // 0031ec
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[30:31], a[94:95], v[56:59]  // 0031f4
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 0031fc
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 003204
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 00320c
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 003214
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[96:97], 0  // 00321c
	s_add_u32 m0, 0x400, s59  // 003224
	buffer_load_dword v38, s[4:7], 0 offen lds  // 00322c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[98:99], v[60:63]  // 003234
	ds_read_b128 a[64:67], v42 offset:17664  // 00323c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[100:101], v[60:63]  // 003244
	s_add_u32 m0, 0x500, s59  // 00324c
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003254
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[102:103], v[60:63]  // 00325c
	ds_read_b128 a[68:71], v42 offset:17728  // 003264
	v_mul_f32_e32 v4, v133, v114  // 00326c
	v_mov_b32_e32 v5, v4  // 003270
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[96:97], 0  // 003274
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[98:99], v[64:67]  // 00327c
	buffer_load_dword v114, v137, s[20:23], 0 offen  // 003284
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[100:101], v[64:67]  // 00328c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[102:103], v[64:67]  // 003294
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 00329c
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 0032a4
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 0032ac
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 0032b4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[104:105], 0  // 0032bc
	s_add_u32 m0, 0x600, s59  // 0032c4
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0032cc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[106:107], v[68:71]  // 0032d4
	ds_read_b128 a[72:75], v42 offset:18176  // 0032dc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[108:109], v[68:71]  // 0032e4
	s_add_u32 m0, 0x700, s59  // 0032ec
	buffer_load_dword v41, s[4:7], 0 offen lds  // 0032f4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[110:111], v[68:71]  // 0032fc
	s_add_u32 s50, 0x200, s42  // 00332c
	s_cmp_lt_u32 s50, s43  // 003334
	s_cselect_b32 s54, s54, 0  // 003338
	ds_read_b128 a[76:79], v42 offset:18240  // 003304
	v_mul_f32_e32 v4, v133, v115  // 00330c
	v_mov_b32_e32 v5, v4  // 003310
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[104:105], 0  // 003314
	s_add_u32 s50, 0x180, s42  // 00333c
	s_cmp_lt_u32 s50, s43  // 003344
	s_cselect_b32 s55, s55, 0  // 003348
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[106:107], v[72:75]  // 00331c
	buffer_load_dword v115, v138, s[20:23], 0 offen  // 003324
	s_add_u32 s50, 0x200, s42  // 00334c
	s_cmp_lt_u32 s50, s43  // 003354
	s_cselect_b32 s56, s56, 0  // 003358
	s_add_u32 s50, 0x180, s42  // 00335c
	s_cmp_lt_u32 s50, s43  // 003364
	s_cselect_b32 s57, s57, 0  // 003368
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[108:109], v[72:75]  // 00336c
	s_add_u32 s4, s54, s4  // 003384
	s_addc_u32 s5, 0, s5  // 003388
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[110:111], v[72:75]  // 003374
	buffer_load_dword v132, v143, s[24:27], 0 offen  // 00337c
	s_sub_u32 s6, s6, s54  // 00338c
	s_add_u32 s8, s55, s8  // 003390
	s_addc_u32 s9, 0, s9  // 003394
	s_sub_u32 s10, s10, s55  // 003398
	s_add_u32 s20, s56, s20  // 00339c
	s_addc_u32 s21, 0, s21  // 0033a0
	s_add_u32 s24, s57, s24  // 0033a4
	s_addc_u32 s25, 0, s25  // 0033a8
	s_sub_u32 s26, s26, s57  // 0033ac
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 0033b0
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 0033b8
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 0033c0
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 0033c8
	s_addk_i32 s42, 0x80  // 0033d0
	s_cmp_lt_i32 s42, s43  // 0033d4
	s_cbranch_scc0 L_4070  // 0033d8
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 0033e0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[32:33], a[48:49], 0  // 0033e4
	s_add_u32 m0, 0, s60  // 0033ec
	buffer_load_dword v34, s[4:7], 0 offen lds  // 0033f0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[34:35], a[50:51], v[44:47]  // 0033f8
	ds_read_b128 a[80:83], v42  // 003400
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[36:37], a[52:53], v[44:47]  // 003408
	s_add_u32 m0, 0x100, s60  // 003410
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003418
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[38:39], a[54:55], v[44:47]  // 003420
	ds_read_b128 a[84:87], v42 offset:64  // 003428
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v134, v116  // 003430
	v_mov_b32_e32 v5, v4  // 003434
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[40:41], a[48:49], 0  // 003438
	buffer_load_dwordx4 a[16:19], v30, s[8:11], 0 offen  // 003440
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[42:43], a[50:51], v[48:51]  // 003448
	buffer_load_dword v116, v135, s[20:23], 0 offen  // 003450
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[44:45], a[52:53], v[48:51]  // 003458
	buffer_load_dwordx4 a[20:23], v31, s[8:11], 0 offen  // 003460
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[46:47], a[54:55], v[48:51]  // 003468
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 003470
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 003478
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 003480
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 003488
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[32:33], a[56:57], 0  // 003490
	s_add_u32 m0, 0x200, s60  // 003498
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0034a0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[34:35], a[58:59], v[52:55]  // 0034a8
	ds_read_b128 a[88:91], v42 offset:512  // 0034b0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[36:37], a[60:61], v[52:55]  // 0034b8
	s_add_u32 m0, 0x300, s60  // 0034c0
	buffer_load_dword v37, s[4:7], 0 offen lds  // 0034c8
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[38:39], a[62:63], v[52:55]  // 0034d0
	ds_read_b128 a[92:95], v42 offset:576  // 0034d8
	v_mul_f32_e32 v4, v134, v117  // 0034e0
	v_mov_b32_e32 v5, v4  // 0034e4
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[40:41], a[56:57], 0  // 0034e8
	buffer_load_dwordx4 a[24:27], v32, s[8:11], 0 offen  // 0034f0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[42:43], a[58:59], v[56:59]  // 0034f8
	buffer_load_dword v117, v136, s[20:23], 0 offen  // 003500
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[44:45], a[60:61], v[56:59]  // 003508
	buffer_load_dwordx4 a[28:31], v33, s[8:11], 0 offen  // 003510
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[46:47], a[62:63], v[56:59]  // 003518
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 003520
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 003528
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 003530
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 003538
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[64:65], 0  // 003540
	s_add_u32 m0, 0x400, s60  // 003548
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003550
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[66:67], v[60:63]  // 003558
	ds_read_b128 a[96:99], v42 offset:1024  // 003560
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[68:69], v[60:63]  // 003568
	s_add_u32 m0, 0x500, s60  // 003570
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003578
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[70:71], v[60:63]  // 003580
	ds_read_b128 a[100:103], v42 offset:1088  // 003588
	v_mul_f32_e32 v4, v134, v118  // 003590
	v_mov_b32_e32 v5, v4  // 003594
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[64:65], 0  // 003598
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[66:67], v[64:67]  // 0035a0
	buffer_load_dword v118, v137, s[20:23], 0 offen  // 0035a8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[68:69], v[64:67]  // 0035b0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[70:71], v[64:67]  // 0035b8
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 0035c0
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 0035c8
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 0035d0
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 0035d8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[72:73], 0  // 0035e0
	s_add_u32 m0, 0x600, s60  // 0035e8
	buffer_load_dword v40, s[4:7], 0 offen lds  // 0035f0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[74:75], v[68:71]  // 0035f8
	ds_read_b128 a[104:107], v42 offset:1536  // 003600
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[76:77], v[68:71]  // 003608
	s_add_u32 m0, 0x700, s60  // 003610
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003618
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[78:79], v[68:71]  // 003620
	s_add_u32 s50, 0x200, s42  // 003650
	s_cmp_lt_u32 s50, s43  // 003658
	s_cselect_b32 s54, s54, 0  // 00365c
	ds_read_b128 a[108:111], v42 offset:1600  // 003628
	v_mul_f32_e32 v4, v134, v119  // 003630
	v_mov_b32_e32 v5, v4  // 003634
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[72:73], 0  // 003638
	s_add_u32 s50, 0x180, s42  // 003660
	s_cmp_lt_u32 s50, s43  // 003668
	s_cselect_b32 s55, s55, 0  // 00366c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[74:75], v[72:75]  // 003640
	buffer_load_dword v119, v138, s[20:23], 0 offen  // 003648
	s_add_u32 s50, 0x200, s42  // 003670
	s_cmp_lt_u32 s50, s43  // 003678
	s_cselect_b32 s56, s56, 0  // 00367c
	s_add_u32 s50, 0x180, s42  // 003680
	s_cmp_lt_u32 s50, s43  // 003688
	s_cselect_b32 s57, s57, 0  // 00368c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[76:77], v[72:75]  // 003690
	s_add_u32 s4, s54, s4  // 0036a8
	s_addc_u32 s5, 0, s5  // 0036ac
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[78:79], v[72:75]  // 003698
	buffer_load_dword v133, v143, s[24:27], 0 offen  // 0036a0
	s_sub_u32 s6, s6, s54  // 0036b0
	s_add_u32 s8, s55, s8  // 0036b4
	s_addc_u32 s9, 0, s9  // 0036b8
	s_sub_u32 s10, s10, s55  // 0036bc
	s_add_u32 s20, s56, s20  // 0036c0
	s_addc_u32 s21, 0, s21  // 0036c4
	s_add_u32 s24, s57, s24  // 0036c8
	s_addc_u32 s25, 0, s25  // 0036cc
	s_sub_u32 s26, s26, s57  // 0036d0
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 0036d4
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 0036dc
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 0036e4
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 0036ec
	s_addk_i32 s42, 0x80  // 0036f4
	s_cmp_lt_i32 s42, s43  // 0036f8
	s_cbranch_scc0 L_4070  // 0036fc
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 003704
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[0:1], a[80:81], 0  // 003708
	s_add_u32 m0, 0, s58  // 003710
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003714
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[2:3], a[82:83], v[44:47]  // 00371c
	ds_read_b128 a[48:51], v42 offset:8320  // 003724
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[4:5], a[84:85], v[44:47]  // 00372c
	s_add_u32 m0, 0x100, s58  // 003734
	buffer_load_dword v35, s[4:7], 0 offen lds  // 00373c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[6:7], a[86:87], v[44:47]  // 003744
	ds_read_b128 a[52:55], v42 offset:8384  // 00374c
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v132, v108  // 003754
	v_mov_b32_e32 v5, v4  // 003758
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[8:9], a[80:81], 0  // 00375c
	buffer_load_dwordx4 a[32:35], v30, s[8:11], 0 offen  // 003764
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[10:11], a[82:83], v[48:51]  // 00376c
	buffer_load_dword v108, v135, s[20:23], 0 offen  // 003774
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[12:13], a[84:85], v[48:51]  // 00377c
	buffer_load_dwordx4 a[36:39], v31, s[8:11], 0 offen  // 003784
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[14:15], a[86:87], v[48:51]  // 00378c
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 003794
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 00379c
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 0037a4
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 0037ac
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[0:1], a[88:89], 0  // 0037b4
	s_add_u32 m0, 0x200, s58  // 0037bc
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0037c4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[2:3], a[90:91], v[52:55]  // 0037cc
	ds_read_b128 a[56:59], v42 offset:8832  // 0037d4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[4:5], a[92:93], v[52:55]  // 0037dc
	s_add_u32 m0, 0x300, s58  // 0037e4
	buffer_load_dword v37, s[4:7], 0 offen lds  // 0037ec
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[6:7], a[94:95], v[52:55]  // 0037f4
	ds_read_b128 a[60:63], v42 offset:8896  // 0037fc
	v_mul_f32_e32 v4, v132, v109  // 003804
	v_mov_b32_e32 v5, v4  // 003808
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[8:9], a[88:89], 0  // 00380c
	buffer_load_dwordx4 a[40:43], v32, s[8:11], 0 offen  // 003814
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[10:11], a[90:91], v[56:59]  // 00381c
	buffer_load_dword v109, v136, s[20:23], 0 offen  // 003824
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[12:13], a[92:93], v[56:59]  // 00382c
	buffer_load_dwordx4 a[44:47], v33, s[8:11], 0 offen  // 003834
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[14:15], a[94:95], v[56:59]  // 00383c
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 003844
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 00384c
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 003854
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 00385c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[96:97], 0  // 003864
	s_add_u32 m0, 0x400, s58  // 00386c
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003874
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[98:99], v[60:63]  // 00387c
	ds_read_b128 a[64:67], v42 offset:9344  // 003884
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[100:101], v[60:63]  // 00388c
	s_add_u32 m0, 0x500, s58  // 003894
	buffer_load_dword v39, s[4:7], 0 offen lds  // 00389c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[102:103], v[60:63]  // 0038a4
	ds_read_b128 a[68:71], v42 offset:9408  // 0038ac
	v_mul_f32_e32 v4, v132, v110  // 0038b4
	v_mov_b32_e32 v5, v4  // 0038b8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[96:97], 0  // 0038bc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[98:99], v[64:67]  // 0038c4
	buffer_load_dword v110, v137, s[20:23], 0 offen  // 0038cc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[100:101], v[64:67]  // 0038d4
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[102:103], v[64:67]  // 0038dc
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 0038e4
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 0038ec
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 0038f4
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 0038fc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[104:105], 0  // 003904
	s_add_u32 m0, 0x600, s58  // 00390c
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003914
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[106:107], v[68:71]  // 00391c
	ds_read_b128 a[72:75], v42 offset:9856  // 003924
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[108:109], v[68:71]  // 00392c
	s_add_u32 m0, 0x700, s58  // 003934
	buffer_load_dword v41, s[4:7], 0 offen lds  // 00393c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[110:111], v[68:71]  // 003944
	s_add_u32 s50, 0x200, s42  // 003974
	s_cmp_lt_u32 s50, s43  // 00397c
	s_cselect_b32 s54, s54, 0  // 003980
	ds_read_b128 a[76:79], v42 offset:9920  // 00394c
	v_mul_f32_e32 v4, v132, v111  // 003954
	v_mov_b32_e32 v5, v4  // 003958
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[104:105], 0  // 00395c
	s_add_u32 s50, 0x180, s42  // 003984
	s_cmp_lt_u32 s50, s43  // 00398c
	s_cselect_b32 s55, s55, 0  // 003990
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[106:107], v[72:75]  // 003964
	buffer_load_dword v111, v138, s[20:23], 0 offen  // 00396c
	s_add_u32 s50, 0x200, s42  // 003994
	s_cmp_lt_u32 s50, s43  // 00399c
	s_cselect_b32 s56, s56, 0  // 0039a0
	s_add_u32 s50, 0x180, s42  // 0039a4
	s_cmp_lt_u32 s50, s43  // 0039ac
	s_cselect_b32 s57, s57, 0  // 0039b0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[108:109], v[72:75]  // 0039b4
	s_add_u32 s4, s54, s4  // 0039cc
	s_addc_u32 s5, 0, s5  // 0039d0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[110:111], v[72:75]  // 0039bc
	buffer_load_dword v134, v143, s[24:27], 0 offen  // 0039c4
	s_sub_u32 s6, s6, s54  // 0039d4
	s_add_u32 s8, s55, s8  // 0039d8
	s_addc_u32 s9, 0, s9  // 0039dc
	s_sub_u32 s10, s10, s55  // 0039e0
	s_add_u32 s20, s56, s20  // 0039e4
	s_addc_u32 s21, 0, s21  // 0039e8
	s_add_u32 s24, s57, s24  // 0039ec
	s_addc_u32 s25, 0, s25  // 0039f0
	s_sub_u32 s26, s26, s57  // 0039f4
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 0039f8
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 003a00
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 003a08
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 003a10
	s_addk_i32 s42, 0x80  // 003a18
	s_cmp_lt_i32 s42, s43  // 003a1c
	s_cbranch_scc0 L_4070  // 003a20
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 003a28
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[16:17], a[48:49], 0  // 003a2c
	s_add_u32 m0, 0, s59  // 003a34
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003a38
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[18:19], a[50:51], v[44:47]  // 003a40
	ds_read_b128 a[80:83], v42 offset:16640  // 003a48
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[20:21], a[52:53], v[44:47]  // 003a50
	s_add_u32 m0, 0x100, s59  // 003a58
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003a60
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[22:23], a[54:55], v[44:47]  // 003a68
	ds_read_b128 a[84:87], v42 offset:16704  // 003a70
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v133, v112  // 003a78
	v_mov_b32_e32 v5, v4  // 003a7c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[24:25], a[48:49], 0  // 003a80
	buffer_load_dwordx4 a[0:3], v30, s[8:11], 0 offen  // 003a88
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[26:27], a[50:51], v[48:51]  // 003a90
	buffer_load_dword v112, v135, s[20:23], 0 offen  // 003a98
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[28:29], a[52:53], v[48:51]  // 003aa0
	buffer_load_dwordx4 a[4:7], v31, s[8:11], 0 offen  // 003aa8
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[30:31], a[54:55], v[48:51]  // 003ab0
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 003ab8
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 003ac0
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 003ac8
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 003ad0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[16:17], a[56:57], 0  // 003ad8
	s_add_u32 m0, 0x200, s59  // 003ae0
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003ae8
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[18:19], a[58:59], v[52:55]  // 003af0
	ds_read_b128 a[88:91], v42 offset:17152  // 003af8
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[20:21], a[60:61], v[52:55]  // 003b00
	s_add_u32 m0, 0x300, s59  // 003b08
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003b10
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[22:23], a[62:63], v[52:55]  // 003b18
	ds_read_b128 a[92:95], v42 offset:17216  // 003b20
	v_mul_f32_e32 v4, v133, v113  // 003b28
	v_mov_b32_e32 v5, v4  // 003b2c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[24:25], a[56:57], 0  // 003b30
	buffer_load_dwordx4 a[8:11], v32, s[8:11], 0 offen  // 003b38
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[26:27], a[58:59], v[56:59]  // 003b40
	buffer_load_dword v113, v136, s[20:23], 0 offen  // 003b48
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[28:29], a[60:61], v[56:59]  // 003b50
	buffer_load_dwordx4 a[12:15], v33, s[8:11], 0 offen  // 003b58
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[30:31], a[62:63], v[56:59]  // 003b60
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 003b68
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 003b70
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 003b78
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 003b80
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[64:65], 0  // 003b88
	s_add_u32 m0, 0x400, s59  // 003b90
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003b98
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[66:67], v[60:63]  // 003ba0
	ds_read_b128 a[96:99], v42 offset:17664  // 003ba8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[68:69], v[60:63]  // 003bb0
	s_add_u32 m0, 0x500, s59  // 003bb8
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003bc0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[70:71], v[60:63]  // 003bc8
	ds_read_b128 a[100:103], v42 offset:17728  // 003bd0
	v_mul_f32_e32 v4, v133, v114  // 003bd8
	v_mov_b32_e32 v5, v4  // 003bdc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[64:65], 0  // 003be0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[66:67], v[64:67]  // 003be8
	buffer_load_dword v114, v137, s[20:23], 0 offen  // 003bf0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[68:69], v[64:67]  // 003bf8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[70:71], v[64:67]  // 003c00
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 003c08
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 003c10
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 003c18
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 003c20
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[72:73], 0  // 003c28
	s_add_u32 m0, 0x600, s59  // 003c30
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003c38
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[74:75], v[68:71]  // 003c40
	ds_read_b128 a[104:107], v42 offset:18176  // 003c48
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[76:77], v[68:71]  // 003c50
	s_add_u32 m0, 0x700, s59  // 003c58
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003c60
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[78:79], v[68:71]  // 003c68
	s_add_u32 s50, 0x200, s42  // 003c98
	s_cmp_lt_u32 s50, s43  // 003ca0
	s_cselect_b32 s54, s54, 0  // 003ca4
	ds_read_b128 a[108:111], v42 offset:18240  // 003c70
	v_mul_f32_e32 v4, v133, v115  // 003c78
	v_mov_b32_e32 v5, v4  // 003c7c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[72:73], 0  // 003c80
	s_add_u32 s50, 0x180, s42  // 003ca8
	s_cmp_lt_u32 s50, s43  // 003cb0
	s_cselect_b32 s55, s55, 0  // 003cb4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[74:75], v[72:75]  // 003c88
	buffer_load_dword v115, v138, s[20:23], 0 offen  // 003c90
	s_add_u32 s50, 0x200, s42  // 003cb8
	s_cmp_lt_u32 s50, s43  // 003cc0
	s_cselect_b32 s56, s56, 0  // 003cc4
	s_add_u32 s50, 0x180, s42  // 003cc8
	s_cmp_lt_u32 s50, s43  // 003cd0
	s_cselect_b32 s57, s57, 0  // 003cd4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[76:77], v[72:75]  // 003cd8
	s_add_u32 s4, s54, s4  // 003cf0
	s_addc_u32 s5, 0, s5  // 003cf4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[78:79], v[72:75]  // 003ce0
	buffer_load_dword v132, v143, s[24:27], 0 offen  // 003ce8
	s_sub_u32 s6, s6, s54  // 003cf8
	s_add_u32 s8, s55, s8  // 003cfc
	s_addc_u32 s9, 0, s9  // 003d00
	s_sub_u32 s10, s10, s55  // 003d04
	s_add_u32 s20, s56, s20  // 003d08
	s_addc_u32 s21, 0, s21  // 003d0c
	s_add_u32 s24, s57, s24  // 003d10
	s_addc_u32 s25, 0, s25  // 003d14
	s_sub_u32 s26, s26, s57  // 003d18
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 003d1c
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 003d24
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 003d2c
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 003d34
	s_addk_i32 s42, 0x80  // 003d3c
	s_cmp_lt_i32 s42, s43  // 003d40
	s_cbranch_scc0 L_4070  // 003d44
	s_waitcnt vmcnt(19) & lgkmcnt(0)
	s_barrier  // 003d4c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[32:33], a[80:81], 0  // 003d50
	s_add_u32 m0, 0, s60  // 003d58
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003d5c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[34:35], a[82:83], v[44:47]  // 003d64
	ds_read_b128 a[48:51], v42  // 003d6c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[36:37], a[84:85], v[44:47]  // 003d74
	s_add_u32 m0, 0x100, s60  // 003d7c
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003d84
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[38:39], a[86:87], v[44:47]  // 003d8c
	ds_read_b128 a[52:55], v42 offset:64  // 003d94
	s_waitcnt vmcnt(19)
	v_mul_f32_e32 v4, v134, v116  // 003d9c
	v_mov_b32_e32 v5, v4  // 003da0
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[40:41], a[80:81], 0  // 003da4
	buffer_load_dwordx4 a[16:19], v30, s[8:11], 0 offen  // 003dac
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[42:43], a[82:83], v[48:51]  // 003db4
	buffer_load_dword v116, v135, s[20:23], 0 offen  // 003dbc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[44:45], a[84:85], v[48:51]  // 003dc4
	buffer_load_dwordx4 a[20:23], v31, s[8:11], 0 offen  // 003dcc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[46:47], a[86:87], v[48:51]  // 003dd4
	s_nop 0
	v_pk_fma_f32 v[76:77], v[4:5], v[44:45], v[76:77]  // 003ddc
	v_pk_fma_f32 v[78:79], v[4:5], v[46:47], v[78:79]  // 003de4
	v_pk_fma_f32 v[80:81], v[4:5], v[48:49], v[80:81]  // 003dec
	v_pk_fma_f32 v[82:83], v[4:5], v[50:51], v[82:83]  // 003df4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[32:33], a[88:89], 0  // 003dfc
	s_add_u32 m0, 0x200, s60  // 003e04
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003e0c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[34:35], a[90:91], v[52:55]  // 003e14
	ds_read_b128 a[56:59], v42 offset:512  // 003e1c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[36:37], a[92:93], v[52:55]  // 003e24
	s_add_u32 m0, 0x300, s60  // 003e2c
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003e34
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[38:39], a[94:95], v[52:55]  // 003e3c
	ds_read_b128 a[60:63], v42 offset:576  // 003e44
	v_mul_f32_e32 v4, v134, v117  // 003e4c
	v_mov_b32_e32 v5, v4  // 003e50
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[40:41], a[88:89], 0  // 003e54
	buffer_load_dwordx4 a[24:27], v32, s[8:11], 0 offen  // 003e5c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[42:43], a[90:91], v[56:59]  // 003e64
	buffer_load_dword v117, v136, s[20:23], 0 offen  // 003e6c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[44:45], a[92:93], v[56:59]  // 003e74
	buffer_load_dwordx4 a[28:31], v33, s[8:11], 0 offen  // 003e7c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[46:47], a[94:95], v[56:59]  // 003e84
	s_nop 0
	v_pk_fma_f32 v[84:85], v[4:5], v[52:53], v[84:85]  // 003e8c
	v_pk_fma_f32 v[86:87], v[4:5], v[54:55], v[86:87]  // 003e94
	v_pk_fma_f32 v[88:89], v[4:5], v[56:57], v[88:89]  // 003e9c
	v_pk_fma_f32 v[90:91], v[4:5], v[58:59], v[90:91]  // 003ea4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[96:97], 0  // 003eac
	s_add_u32 m0, 0x400, s60  // 003eb4
	buffer_load_dword v38, s[4:7], 0 offen lds  // 003ebc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[98:99], v[60:63]  // 003ec4
	ds_read_b128 a[64:67], v42 offset:1024  // 003ecc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[100:101], v[60:63]  // 003ed4
	s_add_u32 m0, 0x500, s60  // 003edc
	buffer_load_dword v39, s[4:7], 0 offen lds  // 003ee4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[102:103], v[60:63]  // 003eec
	ds_read_b128 a[68:71], v42 offset:1088  // 003ef4
	v_mul_f32_e32 v4, v134, v118  // 003efc
	v_mov_b32_e32 v5, v4  // 003f00
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[96:97], 0  // 003f04
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[98:99], v[64:67]  // 003f0c
	buffer_load_dword v118, v137, s[20:23], 0 offen  // 003f14
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[100:101], v[64:67]  // 003f1c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[102:103], v[64:67]  // 003f24
	s_nop 0
	v_pk_fma_f32 v[92:93], v[4:5], v[60:61], v[92:93]  // 003f2c
	v_pk_fma_f32 v[94:95], v[4:5], v[62:63], v[94:95]  // 003f34
	v_pk_fma_f32 v[96:97], v[4:5], v[64:65], v[96:97]  // 003f3c
	v_pk_fma_f32 v[98:99], v[4:5], v[66:67], v[98:99]  // 003f44
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[104:105], 0  // 003f4c
	s_add_u32 m0, 0x600, s60  // 003f54
	buffer_load_dword v40, s[4:7], 0 offen lds  // 003f5c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[106:107], v[68:71]  // 003f64
	ds_read_b128 a[72:75], v42 offset:1536  // 003f6c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[108:109], v[68:71]  // 003f74
	s_add_u32 m0, 0x700, s60  // 003f7c
	buffer_load_dword v41, s[4:7], 0 offen lds  // 003f84
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[110:111], v[68:71]  // 003f8c
	s_add_u32 s50, 0x200, s42  // 003fbc
	s_cmp_lt_u32 s50, s43  // 003fc4
	s_cselect_b32 s54, s54, 0  // 003fc8
	ds_read_b128 a[76:79], v42 offset:1600  // 003f94
	v_mul_f32_e32 v4, v134, v119  // 003f9c
	v_mov_b32_e32 v5, v4  // 003fa0
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[104:105], 0  // 003fa4
	s_add_u32 s50, 0x180, s42  // 003fcc
	s_cmp_lt_u32 s50, s43  // 003fd4
	s_cselect_b32 s55, s55, 0  // 003fd8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[106:107], v[72:75]  // 003fac
	buffer_load_dword v119, v138, s[20:23], 0 offen  // 003fb4
	s_add_u32 s50, 0x200, s42  // 003fdc
	s_cmp_lt_u32 s50, s43  // 003fe4
	s_cselect_b32 s56, s56, 0  // 003fe8
	s_add_u32 s50, 0x180, s42  // 003fec
	s_cmp_lt_u32 s50, s43  // 003ff4
	s_cselect_b32 s57, s57, 0  // 003ff8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[108:109], v[72:75]  // 003ffc
	s_add_u32 s4, s54, s4  // 004014
	s_addc_u32 s5, 0, s5  // 004018
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[110:111], v[72:75]  // 004004
	buffer_load_dword v133, v143, s[24:27], 0 offen  // 00400c
	s_sub_u32 s6, s6, s54  // 00401c
	s_add_u32 s8, s55, s8  // 004020
	s_addc_u32 s9, 0, s9  // 004024
	s_sub_u32 s10, s10, s55  // 004028
	s_add_u32 s20, s56, s20  // 00402c
	s_addc_u32 s21, 0, s21  // 004030
	s_add_u32 s24, s57, s24  // 004034
	s_addc_u32 s25, 0, s25  // 004038
	s_sub_u32 s26, s26, s57  // 00403c
	v_pk_fma_f32 v[100:101], v[4:5], v[68:69], v[100:101]  // 004040
	v_pk_fma_f32 v[102:103], v[4:5], v[70:71], v[102:103]  // 004048
	v_pk_fma_f32 v[104:105], v[4:5], v[72:73], v[104:105]  // 004050
	v_pk_fma_f32 v[106:107], v[4:5], v[74:75], v[106:107]  // 004058
	s_addk_i32 s42, 0x80  // 004060
	s_cmp_lt_i32 s42, s43  // 004064
	s_cbranch_scc0 L_4070  // 004068
	s_branch L_2d94  // 00406c
L_4070:
	s_cmp_eq_u32 s38, 1  // 004070
	s_cbranch_scc1 L_4488  // 004074
	v_add_f32_e32 v76, v76, v12  // 004078
	v_add_f32_e32 v77, v77, v13  // 00407c
	v_perm_b32 v44, v77, v76, s48  // 004080
	v_add_f32_e32 v78, v78, v14  // 004088
	v_add_f32_e32 v79, v79, v15  // 00408c
	v_perm_b32 v45, v79, v78, s48  // 004090
	v_add_f32_e32 v80, v80, v16  // 004098
	v_add_f32_e32 v81, v81, v17  // 00409c
	v_perm_b32 v46, v81, v80, s48  // 0040a0
	v_add_f32_e32 v82, v82, v18  // 0040a8
	v_add_f32_e32 v83, v83, v19  // 0040ac
	v_perm_b32 v47, v83, v82, s48  // 0040b0
	v_add_f32_e32 v84, v84, v12  // 0040b8
	v_add_f32_e32 v85, v85, v13  // 0040bc
	v_perm_b32 v48, v85, v84, s48  // 0040c0
	v_add_f32_e32 v86, v86, v14  // 0040c8
	v_add_f32_e32 v87, v87, v15  // 0040cc
	v_perm_b32 v49, v87, v86, s48  // 0040d0
	v_add_f32_e32 v88, v88, v16  // 0040d8
	v_add_f32_e32 v89, v89, v17  // 0040dc
	v_perm_b32 v50, v89, v88, s48  // 0040e0
	v_add_f32_e32 v90, v90, v18  // 0040e8
	v_add_f32_e32 v91, v91, v19  // 0040ec
	v_perm_b32 v51, v91, v90, s48  // 0040f0
	v_add_f32_e32 v92, v92, v12  // 0040f8
	v_add_f32_e32 v93, v93, v13  // 0040fc
	v_perm_b32 v52, v93, v92, s48  // 004100
	v_add_f32_e32 v94, v94, v14  // 004108
	v_add_f32_e32 v95, v95, v15  // 00410c
	v_perm_b32 v53, v95, v94, s48  // 004110
	v_add_f32_e32 v96, v96, v16  // 004118
	v_add_f32_e32 v97, v97, v17  // 00411c
	v_perm_b32 v54, v97, v96, s48  // 004120
	v_add_f32_e32 v98, v98, v18  // 004128
	v_add_f32_e32 v99, v99, v19  // 00412c
	v_perm_b32 v55, v99, v98, s48  // 004130
	v_add_f32_e32 v100, v100, v12  // 004138
	v_add_f32_e32 v101, v101, v13  // 00413c
	v_perm_b32 v56, v101, v100, s48  // 004140
	v_add_f32_e32 v102, v102, v14  // 004148
	v_add_f32_e32 v103, v103, v15  // 00414c
	v_perm_b32 v57, v103, v102, s48  // 004150
	v_add_f32_e32 v104, v104, v16  // 004158
	v_add_f32_e32 v105, v105, v17  // 00415c
	v_perm_b32 v58, v105, v104, s48  // 004160
	v_add_f32_e32 v106, v106, v18  // 004168
	v_add_f32_e32 v107, v107, v19  // 00416c
	v_perm_b32 v59, v107, v106, s48  // 004170
	v_lshrrev_b32_e32 v4, 4, v0  // 004178
	v_mul_u32_u24_e32 v42, 34, v4  // 00417c
	v_and_b32_e32 v4, 15, v0  // 004180
	v_mul_lo_u32 v5, 2, v4  // 004184
	v_add_u32_e32 v42, v5, v42  // 00418c
	s_mul_i32 s50, s47, 0x110  // 004190
	v_add_u32_e32 v42, s50, v42  // 004198
	v_lshlrev_b32_e32 v42, 2, v42  // 00419c
	v_lshrrev_b32_e32 v4, 1, v0  // 0041a0
	v_mul_u32_u24_e32 v34, 34, v4  // 0041a4
	v_and_b32_e32 v5, 1, v0  // 0041a8
	v_add_u32_e32 v34, v5, v34  // 0041ac
	s_mul_i32 s50, s47, 2  // 0041b0
	v_add_u32_e32 v34, s50, v34  // 0041b4
	v_lshlrev_b32_e32 v34, 2, v34  // 0041b8
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 0041bc
	s_barrier  // 0041c0
	ds_write_b64 v42, v[44:45]  // 0041c4
	ds_write_b64 v42, v[46:47] offset:544  // 0041cc
	ds_write_b64 v42, v[48:49] offset:4352  // 0041d4
	ds_write_b64 v42, v[50:51] offset:4896  // 0041dc
	ds_write_b64 v42, v[52:53] offset:8704  // 0041e4
	ds_write_b64 v42, v[54:55] offset:9248  // 0041ec
	ds_write_b64 v42, v[56:57] offset:13056  // 0041f4
	ds_write_b64 v42, v[58:59] offset:13600  // 0041fc
	s_waitcnt lgkmcnt(0)  // 004204
	s_barrier  // 004208
	ds_read_b32 v44, v34  // 00420c
	ds_read_b32 v45, v34 offset:32  // 004214
	ds_read_b32 v46, v34 offset:64  // 00421c
	ds_read_b32 v47, v34 offset:96  // 004224
	ds_read_b32 v48, v34 offset:4352  // 00422c
	ds_read_b32 v49, v34 offset:4384  // 004234
	ds_read_b32 v50, v34 offset:4416  // 00423c
	ds_read_b32 v51, v34 offset:4448  // 004244
	ds_read_b32 v52, v34 offset:8704  // 00424c
	ds_read_b32 v53, v34 offset:8736  // 004254
	ds_read_b32 v54, v34 offset:8768  // 00425c
	ds_read_b32 v55, v34 offset:8800  // 004264
	ds_read_b32 v56, v34 offset:13056  // 00426c
	ds_read_b32 v57, v34 offset:13088  // 004274
	ds_read_b32 v58, v34 offset:13120  // 00427c
	ds_read_b32 v59, v34 offset:13152  // 004284
	s_waitcnt lgkmcnt(0)  // 00428c
	s_barrier  // 004290
	s_mul_i32 s50, s37, 4  // 004294
	s_mul_i32 s51, s37, 8  // 004298
	s_mul_i32 s52, s37, 16  // 00429c
	v_mov_b32_e32 v4, v24  // 0042a0
	v_mov_b32_e32 v5, 0  // 0042a4
	v_mov_b32_e32 v7, 0  // 0042a8
	v_mov_b32_e32 v9, 0  // 0042ac
	v_mov_b32_e32 v11, 0  // 0042b0
	v_mov_b32_e32 v6, v4  // 0042b4
	v_add_u32_e64 v10, v4, s51  // 0042b8
	s_cmp_ge_u32 s77, s32  // 0042c0
	s_cbranch_scc1 L_45c8  // 0042c4
	global_atomic_pk_add_bf16 v6, v44, s[80:81]  // 0042c8
	v_add_u32_e64 v8, v6, s50  // 0042d0
	s_add_i32 s77, s77, 4  // 0042d8
	s_cmp_ge_u32 s77, s32  // 0042dc
	s_cbranch_scc1 L_45c8  // 0042e0
	global_atomic_pk_add_bf16 v8, v45, s[80:81]  // 0042e4
	s_add_i32 s77, s77, 4  // 0042ec
	s_cmp_ge_u32 s77, s32  // 0042f0
	s_cbranch_scc1 L_45c8  // 0042f4
	global_atomic_pk_add_bf16 v10, v46, s[80:81]  // 0042f8
	v_add_u32_e64 v12, v10, s50  // 004300
	s_add_i32 s77, s77, 4  // 004308
	s_cmp_ge_u32 s77, s32  // 00430c
	s_cbranch_scc1 L_45c8  // 004310
	global_atomic_pk_add_bf16 v12, v47, s[80:81]  // 004314
	s_add_i32 s77, s77, 4  // 00431c
	v_add_u32_e64 v4, v4, s52  // 004320
	v_mov_b32_e32 v6, v4  // 004328
	v_add_u32_e64 v10, v4, s51  // 00432c
	s_cmp_ge_u32 s77, s32  // 004334
	s_cbranch_scc1 L_45c8  // 004338
	global_atomic_pk_add_bf16 v6, v48, s[80:81]  // 00433c
	v_add_u32_e64 v8, v6, s50  // 004344
	s_add_i32 s77, s77, 4  // 00434c
	s_cmp_ge_u32 s77, s32  // 004350
	s_cbranch_scc1 L_45c8  // 004354
	global_atomic_pk_add_bf16 v8, v49, s[80:81]  // 004358
	s_add_i32 s77, s77, 4  // 004360
	s_cmp_ge_u32 s77, s32  // 004364
	s_cbranch_scc1 L_45c8  // 004368
	global_atomic_pk_add_bf16 v10, v50, s[80:81]  // 00436c
	v_add_u32_e64 v12, v10, s50  // 004374
	s_add_i32 s77, s77, 4  // 00437c
	s_cmp_ge_u32 s77, s32  // 004380
	s_cbranch_scc1 L_45c8  // 004384
	global_atomic_pk_add_bf16 v12, v51, s[80:81]  // 004388
	s_add_i32 s77, s77, 4  // 004390
	v_add_u32_e64 v4, v4, s52  // 004394
	v_mov_b32_e32 v6, v4  // 00439c
	v_add_u32_e64 v10, v4, s51  // 0043a0
	s_cmp_ge_u32 s77, s32  // 0043a8
	s_cbranch_scc1 L_45c8  // 0043ac
	global_atomic_pk_add_bf16 v6, v52, s[80:81]  // 0043b0
	v_add_u32_e64 v8, v6, s50  // 0043b8
	s_add_i32 s77, s77, 4  // 0043c0
	s_cmp_ge_u32 s77, s32  // 0043c4
	s_cbranch_scc1 L_45c8  // 0043c8
	global_atomic_pk_add_bf16 v8, v53, s[80:81]  // 0043cc
	s_add_i32 s77, s77, 4  // 0043d4
	s_cmp_ge_u32 s77, s32  // 0043d8
	s_cbranch_scc1 L_45c8  // 0043dc
	global_atomic_pk_add_bf16 v10, v54, s[80:81]  // 0043e0
	v_add_u32_e64 v12, v10, s50  // 0043e8
	s_add_i32 s77, s77, 4  // 0043f0
	s_cmp_ge_u32 s77, s32  // 0043f4
	s_cbranch_scc1 L_45c8  // 0043f8
	global_atomic_pk_add_bf16 v12, v55, s[80:81]  // 0043fc
	s_add_i32 s77, s77, 4  // 004404
	v_add_u32_e64 v4, v4, s52  // 004408
	v_mov_b32_e32 v6, v4  // 004410
	v_add_u32_e64 v10, v4, s51  // 004414
	s_cmp_ge_u32 s77, s32  // 00441c
	s_cbranch_scc1 L_45c8  // 004420
	global_atomic_pk_add_bf16 v6, v56, s[80:81]  // 004424
	v_add_u32_e64 v8, v6, s50  // 00442c
	s_add_i32 s77, s77, 4  // 004434
	s_cmp_ge_u32 s77, s32  // 004438
	s_cbranch_scc1 L_45c8  // 00443c
	global_atomic_pk_add_bf16 v8, v57, s[80:81]  // 004440
	s_add_i32 s77, s77, 4  // 004448
	s_cmp_ge_u32 s77, s32  // 00444c
	s_cbranch_scc1 L_45c8  // 004450
	global_atomic_pk_add_bf16 v10, v58, s[80:81]  // 004454
	v_add_u32_e64 v12, v10, s50  // 00445c
	s_add_i32 s77, s77, 4  // 004464
	s_cmp_ge_u32 s77, s32  // 004468
	s_cbranch_scc1 L_45c8  // 00446c
	global_atomic_pk_add_bf16 v12, v59, s[80:81]  // 004470
	s_add_i32 s77, s77, 4  // 004478
	v_add_u32_e64 v4, v4, s52  // 00447c
	s_branch L_45c8  // 004484
L_4488:
	v_add_f32_e32 v76, v76, v12  // 004488
	v_add_f32_e32 v77, v77, v13  // 00448c
	v_perm_b32 v44, v77, v76, s48  // 004490
	v_add_f32_e32 v78, v78, v14  // 004498
	v_add_f32_e32 v79, v79, v15  // 00449c
	v_perm_b32 v45, v79, v78, s48  // 0044a0
	buffer_store_dwordx2 v[44:45], v20, s[16:19], 0 offen  // 0044a8
	v_add_f32_e32 v80, v80, v16  // 0044b0
	v_add_f32_e32 v81, v81, v17  // 0044b4
	v_perm_b32 v46, v81, v80, s48  // 0044b8
	v_add_f32_e32 v82, v82, v18  // 0044c0
	v_add_f32_e32 v83, v83, v19  // 0044c4
	v_perm_b32 v47, v83, v82, s48  // 0044c8
	buffer_store_dwordx2 v[46:47], v20, s[16:19], 0 offen offset:32  // 0044d0
	v_add_f32_e32 v84, v84, v12  // 0044d8
	v_add_f32_e32 v85, v85, v13  // 0044dc
	v_perm_b32 v48, v85, v84, s48  // 0044e0
	v_add_f32_e32 v86, v86, v14  // 0044e8
	v_add_f32_e32 v87, v87, v15  // 0044ec
	v_perm_b32 v49, v87, v86, s48  // 0044f0
	buffer_store_dwordx2 v[48:49], v21, s[16:19], 0 offen  // 0044f8
	v_add_f32_e32 v88, v88, v16  // 004500
	v_add_f32_e32 v89, v89, v17  // 004504
	v_perm_b32 v50, v89, v88, s48  // 004508
	v_add_f32_e32 v90, v90, v18  // 004510
	v_add_f32_e32 v91, v91, v19  // 004514
	v_perm_b32 v51, v91, v90, s48  // 004518
	buffer_store_dwordx2 v[50:51], v21, s[16:19], 0 offen offset:32  // 004520
	v_add_f32_e32 v92, v92, v12  // 004528
	v_add_f32_e32 v93, v93, v13  // 00452c
	v_perm_b32 v52, v93, v92, s48  // 004530
	v_add_f32_e32 v94, v94, v14  // 004538
	v_add_f32_e32 v95, v95, v15  // 00453c
	v_perm_b32 v53, v95, v94, s48  // 004540
	buffer_store_dwordx2 v[52:53], v22, s[16:19], 0 offen  // 004548
	v_add_f32_e32 v96, v96, v16  // 004550
	v_add_f32_e32 v97, v97, v17  // 004554
	v_perm_b32 v54, v97, v96, s48  // 004558
	v_add_f32_e32 v98, v98, v18  // 004560
	v_add_f32_e32 v99, v99, v19  // 004564
	v_perm_b32 v55, v99, v98, s48  // 004568
	buffer_store_dwordx2 v[54:55], v22, s[16:19], 0 offen offset:32  // 004570
	v_add_f32_e32 v100, v100, v12  // 004578
	v_add_f32_e32 v101, v101, v13  // 00457c
	v_perm_b32 v56, v101, v100, s48  // 004580
	v_add_f32_e32 v102, v102, v14  // 004588
	v_add_f32_e32 v103, v103, v15  // 00458c
	v_perm_b32 v57, v103, v102, s48  // 004590
	buffer_store_dwordx2 v[56:57], v23, s[16:19], 0 offen  // 004598
	v_add_f32_e32 v104, v104, v16  // 0045a0
	v_add_f32_e32 v105, v105, v17  // 0045a4
	v_perm_b32 v58, v105, v104, s48  // 0045a8
	v_add_f32_e32 v106, v106, v18  // 0045b0
	v_add_f32_e32 v107, v107, v19  // 0045b4
	v_perm_b32 v59, v107, v106, s48  // 0045b8
	buffer_store_dwordx2 v[58:59], v23, s[16:19], 0 offen offset:32  // 0045c0
L_45c8:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 0045c8
	s_endpgm  // 0045cc
.Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E:
	.size _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E, .Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E-_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E
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
    .name:           _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_64x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
