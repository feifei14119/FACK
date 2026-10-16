// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_48x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E
	.protected _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E
	.p2align 8
	.type _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E,@function
_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E:
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
	s_mul_i32 s50, s45, 48  // 00258c
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
	s_mul_i32 s50, s45, 48  // 0025c0
	s_sub_i32 s51, s32, s50  // 0025c4
	s_cmp_lt_u32 s51, 48  // 0025c8
	s_cselect_b32 s50, s51, 48  // 0025cc
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
	s_mul_i32 s50, 48, s45  // 002690
	s_mul_hi_u32 s52, 4, s50  // 002694
	s_mul_i32 s51, 4, s50  // 002698
	s_add_u32 s20, s20, s51  // 00269c
	s_addc_u32 s21, s21, s52  // 0026a0
	s_sub_i32 s51, s32, s50  // 0026a4
	s_cmp_lt_u32 s51, 48  // 0026a8
	s_cselect_b32 s50, s51, 48  // 0026ac
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
	v_and_b32_e64 v109, v0, 15  // 0026e8
	v_lshlrev_b32_e32 v109, 2, v109  // 0026f0
	s_mov_b32 s50, 64  // 0026f4
	v_add_u32_e64 v110, v109, s50  // 0026f8
	s_mov_b32 s50, 0x80  // 002700
	v_add_u32_e64 v111, v109, s50  // 002708
	s_mul_i32 s51, s41, s44  // 002710
	s_mul_hi_u32 s52, 4, s51  // 002714
	s_add_u32 s25, s25, s52  // 002718
	s_mul_i32 s52, 4, s51  // 00271c
	s_add_u32 s24, s24, s52  // 002720
	s_addc_u32 s25, s25, 0  // 002724
	s_lshr_b32 s50, s76, 7  // 002728
	s_mul_i32 s50, s50, s75  // 00272c
	s_lshl_b32 s50, s50, 2  // 002730
	s_add_u32 s24, s24, s50  // 002734
	s_addc_u32 s25, s25, 0  // 002738
	s_sub_u32 s26, s26, s50  // 00273c
	v_mov_b32_e32 v115, 0  // 002740
	v_lshrrev_b32_e32 v4, 5, v0  // 002744
	v_lshlrev_b32_e32 v4, 2, v4  // 002748
	v_mul_i32_i24_e32 v4, s35, v4  // 00274c
	v_and_b32_e32 v32, 31, v0  // 002750
	v_lshlrev_b32_e32 v32, 2, v32  // 002754
	s_mul_i32 s50, 48, s45  // 002758
	s_sub_i32 s51, s32, s50  // 00275c
	s_cmp_lt_u32 s51, 48  // 002760
	s_cselect_b32 s51, s51, 48  // 002764
	s_mul_i32 s52, s35, s50  // 002768
	s_mul_hi_u32 s50, s35, s50  // 00276c
	s_add_u32 s4, s4, s52  // 002770
	s_addc_u32 s5, s5, s50  // 002774
	s_mul_i32 s50, s35, s51  // 002778
	s_mov_b32 s6, s50  // 00277c
	s_mov_b32 s7, 0x20000  // 002780
	s_mul_i32 s51, s76, s75  // 002788
	s_add_u32 s4, s51, s4  // 00278c
	s_addc_u32 s5, 0, s5  // 002790
	s_sub_u32 s6, s6, s51  // 002794
	s_mul_i32 s50, s35, s47  // 002798
	v_add3_u32 v32, v4, v32, s50  // 00279c
	s_lshl_b32 s50, s35, 3  // 0027a4
	v_add_u32_e32 v33, s50, v32  // 0027a8
	v_add_u32_e32 v34, s50, v33  // 0027ac
	v_add_u32_e32 v35, s50, v34  // 0027b0
	v_add_u32_e32 v36, s50, v35  // 0027b4
	v_add_u32_e32 v37, s50, v36  // 0027b8
	s_mov_b32 s54, 0x80  // 0027bc
	s_mul_i32 s56, s32, 4  // 0027c4
	s_mov_b32 s57, 4  // 0027c8
	s_mov_b32 s50, 48  // 0027cc
	s_lshr_b32 s50, s50, 2  // 0027d0
	s_mul_i32 s50, s50, 32  // 0027d4
	s_mov_b32 s51, 8  // 0027d8
	s_add_u32 s50, s50, s51  // 0027dc
	v_lshrrev_b32_e32 v4, 4, v0  // 0027e0
	v_and_b32_e32 v5, 15, v0  // 0027e4
	v_and_b32_e32 v6, 3, v5  // 0027e8
	v_lshrrev_b32_e32 v7, 2, v5  // 0027ec
	v_lshlrev_b32_e32 v4, 2, v4  // 0027f0
	v_mul_lo_u32 v6, v6, s50  // 0027f4
	v_lshlrev_b32_e32 v7, 5, v7  // 0027fc
	v_add_u32_e32 v4, v4, v6  // 002800
	v_add_u32_e32 v4, v4, v7  // 002804
	v_lshlrev_b32_e32 v38, 2, v4  // 002808
	s_mul_i32 s50, 0x620, s47  // 00280c
	s_add_u32 s58, 0, s50  // 002814
	s_add_u32 s59, 0x1880, s58  // 002818
	s_add_u32 s60, 0x1880, s59  // 002820
	s_mov_b32 s55, 0x800  // 002828
	s_mul_i32 s49, 0x80, s44  // 002830
	s_sub_i32 s51, s33, s49  // 002838
	s_cmp_lt_u32 s51, 0x80  // 00283c
	s_cselect_b32 s50, s51, 0x80  // 002844
	s_mul_i32 s51, s36, s49  // 00284c
	s_mul_hi_u32 s52, s36, s49  // 002850
	s_add_u32 s8, s8, s51  // 002854
	s_addc_u32 s9, s9, s52  // 002858
	s_mul_i32 s51, s36, s50  // 00285c
	s_mov_b32 s10, s51  // 002860
	s_mov_b32 s11, 0x20000  // 002864
	s_lshr_b32 s51, s76, 7  // 00286c
	s_mul_i32 s50, s55, s75  // 002870
	s_mul_i32 s50, s51, s50  // 002874
	s_add_u32 s8, s50, s8  // 002878
	s_addc_u32 s9, 0, s9  // 00287c
	s_sub_u32 s10, s10, s50  // 002880
	s_lshl_b32 s50, s47, 5  // 002884
	s_mul_i32 s50, s36, s50  // 002888
	v_lshlrev_b32_e32 v28, 4, v0  // 00288c
	v_add_u32_e32 v28, s50, v28  // 002890
	s_mov_b32 s50, 0x400  // 002894
	v_add_u32_e64 v29, v28, s50  // 00289c
	s_mul_i32 s50, s36, 16  // 0028a4
	v_add_u32_e64 v30, v28, s50  // 0028a8
	v_add_u32_e64 v31, v29, s50  // 0028b0
	s_add_u32 m0, 0, s58  // 0028b8
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0028bc
	s_add_u32 m0, 0x100, s58  // 0028c4
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0028cc
	s_add_u32 m0, 0x200, s58  // 0028d4
	buffer_load_dword v34, s[4:7], 0 offen lds  // 0028dc
	s_add_u32 m0, 0x300, s58  // 0028e4
	buffer_load_dword v35, s[4:7], 0 offen lds  // 0028ec
	s_add_u32 m0, 0x400, s58  // 0028f4
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0028fc
	s_add_u32 m0, 0x500, s58  // 002904
	buffer_load_dword v37, s[4:7], 0 offen lds  // 00290c
	s_mov_b32 s53, 0  // 002914
	s_add_u32 s50, 0x80, s53  // 002918
	s_cmp_lt_u32 s50, s34  // 002920
	s_cselect_b32 s54, s54, 0  // 002924
	s_add_u32 s4, s54, s4  // 002928
	s_addc_u32 s5, 0, s5  // 00292c
	s_sub_u32 s6, s6, s54  // 002930
	buffer_load_dword v88, v109, s[20:23], 0 offen  // 002934
	buffer_load_dword v89, v110, s[20:23], 0 offen  // 00293c
	buffer_load_dword v90, v111, s[20:23], 0 offen  // 002944
	s_add_u32 s50, 0x80, s53  // 00294c
	s_cmp_lt_u32 s50, s34  // 002954
	s_cselect_b32 s56, s56, 0  // 002958
	s_add_u32 s20, s56, s20  // 00295c
	s_addc_u32 s21, 0, s21  // 002960
	v_mov_b32_e32 v64, 0  // 002964
	v_mov_b32_e32 v65, 0  // 002968
	v_mov_b32_e32 v66, 0  // 00296c
	v_mov_b32_e32 v67, 0  // 002970
	v_mov_b32_e32 v68, 0  // 002974
	v_mov_b32_e32 v69, 0  // 002978
	v_mov_b32_e32 v70, 0  // 00297c
	v_mov_b32_e32 v71, 0  // 002980
	buffer_load_dwordx4 a[0:3], v28, s[8:11], 0 offen  // 002984
	buffer_load_dwordx4 a[4:7], v29, s[8:11], 0 offen  // 00298c
	buffer_load_dwordx4 a[8:11], v30, s[8:11], 0 offen  // 002994
	buffer_load_dwordx4 a[12:15], v31, s[8:11], 0 offen  // 00299c
	s_mov_b32 s53, 0  // 0029a4
	s_add_u32 s50, 0x80, s53  // 0029a8
	s_cmp_lt_u32 s50, s34  // 0029b0
	s_cselect_b32 s55, s55, 0  // 0029b4
	s_add_u32 s8, s55, s8  // 0029b8
	s_addc_u32 s9, 0, s9  // 0029bc
	s_sub_u32 s10, s10, s55  // 0029c0
	buffer_load_dword v106, v115, s[24:27], 0 offen  // 0029c4
	s_add_u32 s50, 0x80, s53  // 0029cc
	s_cmp_lt_u32 s50, s34  // 0029d4
	s_cselect_b32 s57, s57, 0  // 0029d8
	s_add_u32 s24, s57, s24  // 0029dc
	s_addc_u32 s25, 0, s25  // 0029e0
	s_sub_u32 s26, s26, s57  // 0029e4
	s_add_u32 m0, 0, s59  // 0029e8
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0029ec
	s_add_u32 m0, 0x100, s59  // 0029f4
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0029fc
	s_add_u32 m0, 0x200, s59  // 002a04
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002a0c
	s_add_u32 m0, 0x300, s59  // 002a14
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002a1c
	s_add_u32 m0, 0x400, s59  // 002a24
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002a2c
	s_add_u32 m0, 0x500, s59  // 002a34
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002a3c
	s_mov_b32 s53, 0x80  // 002a44
	s_add_u32 s50, 0x80, s53  // 002a4c
	s_cmp_lt_u32 s50, s34  // 002a54
	s_cselect_b32 s54, s54, 0  // 002a58
	s_add_u32 s4, s54, s4  // 002a5c
	s_addc_u32 s5, 0, s5  // 002a60
	s_sub_u32 s6, s6, s54  // 002a64
	buffer_load_dword v91, v109, s[20:23], 0 offen  // 002a68
	buffer_load_dword v92, v110, s[20:23], 0 offen  // 002a70
	buffer_load_dword v93, v111, s[20:23], 0 offen  // 002a78
	s_add_u32 s50, 0x80, s53  // 002a80
	s_cmp_lt_u32 s50, s34  // 002a88
	s_cselect_b32 s56, s56, 0  // 002a8c
	s_add_u32 s20, s56, s20  // 002a90
	s_addc_u32 s21, 0, s21  // 002a94
	v_mov_b32_e32 v72, 0  // 002a98
	v_mov_b32_e32 v73, 0  // 002a9c
	v_mov_b32_e32 v74, 0  // 002aa0
	v_mov_b32_e32 v75, 0  // 002aa4
	v_mov_b32_e32 v76, 0  // 002aa8
	v_mov_b32_e32 v77, 0  // 002aac
	v_mov_b32_e32 v78, 0  // 002ab0
	v_mov_b32_e32 v79, 0  // 002ab4
	buffer_load_dwordx4 a[16:19], v28, s[8:11], 0 offen  // 002ab8
	buffer_load_dwordx4 a[20:23], v29, s[8:11], 0 offen  // 002ac0
	buffer_load_dwordx4 a[24:27], v30, s[8:11], 0 offen  // 002ac8
	buffer_load_dwordx4 a[28:31], v31, s[8:11], 0 offen  // 002ad0
	s_mov_b32 s53, 0x80  // 002ad8
	s_add_u32 s50, 0x80, s53  // 002ae0
	s_cmp_lt_u32 s50, s34  // 002ae8
	s_cselect_b32 s55, s55, 0  // 002aec
	s_add_u32 s8, s55, s8  // 002af0
	s_addc_u32 s9, 0, s9  // 002af4
	s_sub_u32 s10, s10, s55  // 002af8
	buffer_load_dword v107, v115, s[24:27], 0 offen  // 002afc
	s_add_u32 s50, 0x80, s53  // 002b04
	s_cmp_lt_u32 s50, s34  // 002b0c
	s_cselect_b32 s57, s57, 0  // 002b10
	s_add_u32 s24, s57, s24  // 002b14
	s_addc_u32 s25, 0, s25  // 002b18
	s_sub_u32 s26, s26, s57  // 002b1c
	s_add_u32 m0, 0, s60  // 002b20
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002b24
	s_add_u32 m0, 0x100, s60  // 002b2c
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002b34
	s_add_u32 m0, 0x200, s60  // 002b3c
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002b44
	s_add_u32 m0, 0x300, s60  // 002b4c
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002b54
	s_add_u32 m0, 0x400, s60  // 002b5c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002b64
	s_add_u32 m0, 0x500, s60  // 002b6c
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002b74
	s_mov_b32 s53, 0x100  // 002b7c
	s_add_u32 s50, 0x80, s53  // 002b84
	s_cmp_lt_u32 s50, s34  // 002b8c
	s_cselect_b32 s54, s54, 0  // 002b90
	s_add_u32 s4, s54, s4  // 002b94
	s_addc_u32 s5, 0, s5  // 002b98
	s_sub_u32 s6, s6, s54  // 002b9c
	buffer_load_dword v94, v109, s[20:23], 0 offen  // 002ba0
	buffer_load_dword v95, v110, s[20:23], 0 offen  // 002ba8
	buffer_load_dword v96, v111, s[20:23], 0 offen  // 002bb0
	s_add_u32 s50, 0x80, s53  // 002bb8
	s_cmp_lt_u32 s50, s34  // 002bc0
	s_cselect_b32 s56, s56, 0  // 002bc4
	s_add_u32 s20, s56, s20  // 002bc8
	s_addc_u32 s21, 0, s21  // 002bcc
	v_mov_b32_e32 v80, 0  // 002bd0
	v_mov_b32_e32 v81, 0  // 002bd4
	v_mov_b32_e32 v82, 0  // 002bd8
	v_mov_b32_e32 v83, 0  // 002bdc
	v_mov_b32_e32 v84, 0  // 002be0
	v_mov_b32_e32 v85, 0  // 002be4
	v_mov_b32_e32 v86, 0  // 002be8
	v_mov_b32_e32 v87, 0  // 002bec
	s_mov_b32 s43, s34  // 002bf0
	s_mov_b32 s42, 0  // 002bf4
	s_waitcnt vmcnt(28)  // 002bf8
	s_barrier  // 002bfc
	ds_read_b128 a[48:51], v38  // 002c00
	ds_read_b128 a[52:55], v38 offset:64  // 002c08
	ds_read_b128 a[56:59], v38 offset:512  // 002c10
	ds_read_b128 a[60:63], v38 offset:576  // 002c18
	ds_read_b128 a[64:67], v38 offset:1024  // 002c20
	ds_read_b128 a[68:71], v38 offset:1088  // 002c28
	s_mov_b32 s50, 0  // 002c30
	s_mov_b32 s51, 1.0  // 002c34
	s_cmp_eq_u32 s50, s75  // 002c38
	s_cselect_b32 s50, s51, 0  // 002c3c
	v_mul_f32_e64 v12, v12, s50  // 002c40
	v_mul_f32_e64 v13, v13, s50  // 002c48
	v_mul_f32_e64 v14, v14, s50  // 002c50
	v_mul_f32_e64 v15, v15, s50  // 002c58
	v_mul_f32_e64 v16, v16, s50  // 002c60
	v_mul_f32_e64 v17, v17, s50  // 002c68
	v_mul_f32_e64 v18, v18, s50  // 002c70
	v_mul_f32_e64 v19, v19, s50  // 002c78
	v_and_b32_e64 v20, v0, 15  // 002c80
	v_mul_lo_u32 v20, v20, s37  // 002c88
	v_lshrrev_b32_e32 v4, 4, v0  // 002c90
	v_mul_i32_i24_e32 v4, 8, v4  // 002c94
	v_add_u32_e32 v20, v4, v20  // 002c98
	s_mul_i32 s50, 32, s47  // 002c9c
	s_mul_i32 s50, 2, s50  // 002ca0
	v_add_u32_e32 v20, s50, v20  // 002ca4
	s_mul_i32 s50, 16, s37  // 002ca8
	v_add_u32_e32 v21, s50, v20  // 002cac
	v_add_u32_e32 v22, s50, v21  // 002cb0
	s_mul_i32 s50, s47, s37  // 002cb4
	v_lshlrev_b32_e32 v5, 2, v0  // 002cb8
	v_add_u32_e32 v23, s50, v5  // 002cbc
	s_mul_i32 s50, s45, 48  // 002cc0
	s_add_i32 s77, s50, s47  // 002cc4
	s_cmp_lt_i32 s42, s43  // 002cc8
	s_cbranch_scc0 L_3bec  // 002ccc
L_2cd0:
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 002cd4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[0:1], a[48:49], 0  // 002cd8
	s_add_u32 m0, 0, s58  // 002ce0
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002ce4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[2:3], a[50:51], v[40:43]  // 002cec
	ds_read_b128 a[72:75], v38 offset:6272  // 002cf4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[4:5], a[52:53], v[40:43]  // 002cfc
	s_add_u32 m0, 0x100, s58  // 002d04
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002d0c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[6:7], a[54:55], v[40:43]  // 002d14
	ds_read_b128 a[76:79], v38 offset:6336  // 002d1c
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v106, v88  // 002d24
	v_mov_b32_e32 v5, v4  // 002d28
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[8:9], a[48:49], 0  // 002d2c
	buffer_load_dwordx4 a[32:35], v28, s[8:11], 0 offen  // 002d34
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[10:11], a[50:51], v[44:47]  // 002d3c
	buffer_load_dword v88, v109, s[20:23], 0 offen  // 002d44
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[12:13], a[52:53], v[44:47]  // 002d4c
	buffer_load_dwordx4 a[36:39], v29, s[8:11], 0 offen  // 002d54
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[14:15], a[54:55], v[44:47]  // 002d5c
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 002d64
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 002d6c
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 002d74
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 002d7c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[0:1], a[56:57], 0  // 002d84
	s_add_u32 m0, 0x200, s58  // 002d8c
	buffer_load_dword v34, s[4:7], 0 offen lds  // 002d94
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[2:3], a[58:59], v[48:51]  // 002d9c
	ds_read_b128 a[80:83], v38 offset:6784  // 002da4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[4:5], a[60:61], v[48:51]  // 002dac
	s_add_u32 m0, 0x300, s58  // 002db4
	buffer_load_dword v35, s[4:7], 0 offen lds  // 002dbc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[6:7], a[62:63], v[48:51]  // 002dc4
	ds_read_b128 a[84:87], v38 offset:6848  // 002dcc
	v_mul_f32_e32 v4, v106, v89  // 002dd4
	v_mov_b32_e32 v5, v4  // 002dd8
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[8:9], a[56:57], 0  // 002ddc
	buffer_load_dwordx4 a[40:43], v30, s[8:11], 0 offen  // 002de4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[10:11], a[58:59], v[52:55]  // 002dec
	buffer_load_dword v89, v110, s[20:23], 0 offen  // 002df4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[12:13], a[60:61], v[52:55]  // 002dfc
	buffer_load_dwordx4 a[44:47], v31, s[8:11], 0 offen  // 002e04
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[14:15], a[62:63], v[52:55]  // 002e0c
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 002e14
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 002e1c
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 002e24
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 002e2c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[0:1], a[64:65], 0  // 002e34
	s_add_u32 m0, 0x400, s58  // 002e3c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 002e44
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[2:3], a[66:67], v[56:59]  // 002e4c
	ds_read_b128 a[88:91], v38 offset:7296  // 002e54
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[4:5], a[68:69], v[56:59]  // 002e5c
	s_add_u32 m0, 0x500, s58  // 002e64
	buffer_load_dword v37, s[4:7], 0 offen lds  // 002e6c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[6:7], a[70:71], v[56:59]  // 002e74
	s_add_u32 s50, 0x200, s42  // 002ea4
	s_cmp_lt_u32 s50, s43  // 002eac
	s_cselect_b32 s54, s54, 0  // 002eb0
	ds_read_b128 a[92:95], v38 offset:7360  // 002e7c
	v_mul_f32_e32 v4, v106, v90  // 002e84
	v_mov_b32_e32 v5, v4  // 002e88
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[8:9], a[64:65], 0  // 002e8c
	s_add_u32 s50, 0x180, s42  // 002eb4
	s_cmp_lt_u32 s50, s43  // 002ebc
	s_cselect_b32 s55, s55, 0  // 002ec0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[10:11], a[66:67], v[60:63]  // 002e94
	buffer_load_dword v90, v111, s[20:23], 0 offen  // 002e9c
	s_add_u32 s50, 0x200, s42  // 002ec4
	s_cmp_lt_u32 s50, s43  // 002ecc
	s_cselect_b32 s56, s56, 0  // 002ed0
	s_add_u32 s50, 0x180, s42  // 002ed4
	s_cmp_lt_u32 s50, s43  // 002edc
	s_cselect_b32 s57, s57, 0  // 002ee0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[12:13], a[68:69], v[60:63]  // 002ee4
	s_add_u32 s4, s54, s4  // 002efc
	s_addc_u32 s5, 0, s5  // 002f00
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[14:15], a[70:71], v[60:63]  // 002eec
	buffer_load_dword v108, v115, s[24:27], 0 offen  // 002ef4
	s_sub_u32 s6, s6, s54  // 002f04
	s_add_u32 s8, s55, s8  // 002f08
	s_addc_u32 s9, 0, s9  // 002f0c
	s_sub_u32 s10, s10, s55  // 002f10
	s_add_u32 s20, s56, s20  // 002f14
	s_addc_u32 s21, 0, s21  // 002f18
	s_add_u32 s24, s57, s24  // 002f1c
	s_addc_u32 s25, 0, s25  // 002f20
	s_sub_u32 s26, s26, s57  // 002f24
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 002f28
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 002f30
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 002f38
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 002f40
	s_addk_i32 s42, 0x80  // 002f48
	s_cmp_lt_i32 s42, s43  // 002f4c
	s_cbranch_scc0 L_3bec  // 002f50
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 002f58
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[16:17], a[72:73], 0  // 002f5c
	s_add_u32 m0, 0, s59  // 002f64
	buffer_load_dword v32, s[4:7], 0 offen lds  // 002f68
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[18:19], a[74:75], v[40:43]  // 002f70
	ds_read_b128 a[48:51], v38 offset:12544  // 002f78
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[20:21], a[76:77], v[40:43]  // 002f80
	s_add_u32 m0, 0x100, s59  // 002f88
	buffer_load_dword v33, s[4:7], 0 offen lds  // 002f90
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[22:23], a[78:79], v[40:43]  // 002f98
	ds_read_b128 a[52:55], v38 offset:12608  // 002fa0
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v107, v91  // 002fa8
	v_mov_b32_e32 v5, v4  // 002fac
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[24:25], a[72:73], 0  // 002fb0
	buffer_load_dwordx4 a[0:3], v28, s[8:11], 0 offen  // 002fb8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[26:27], a[74:75], v[44:47]  // 002fc0
	buffer_load_dword v91, v109, s[20:23], 0 offen  // 002fc8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[28:29], a[76:77], v[44:47]  // 002fd0
	buffer_load_dwordx4 a[4:7], v29, s[8:11], 0 offen  // 002fd8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[30:31], a[78:79], v[44:47]  // 002fe0
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 002fe8
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 002ff0
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 002ff8
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 003000
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[16:17], a[80:81], 0  // 003008
	s_add_u32 m0, 0x200, s59  // 003010
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003018
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[18:19], a[82:83], v[48:51]  // 003020
	ds_read_b128 a[56:59], v38 offset:13056  // 003028
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[20:21], a[84:85], v[48:51]  // 003030
	s_add_u32 m0, 0x300, s59  // 003038
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003040
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[22:23], a[86:87], v[48:51]  // 003048
	ds_read_b128 a[60:63], v38 offset:13120  // 003050
	v_mul_f32_e32 v4, v107, v92  // 003058
	v_mov_b32_e32 v5, v4  // 00305c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[24:25], a[80:81], 0  // 003060
	buffer_load_dwordx4 a[8:11], v30, s[8:11], 0 offen  // 003068
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[26:27], a[82:83], v[52:55]  // 003070
	buffer_load_dword v92, v110, s[20:23], 0 offen  // 003078
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[28:29], a[84:85], v[52:55]  // 003080
	buffer_load_dwordx4 a[12:15], v31, s[8:11], 0 offen  // 003088
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[30:31], a[86:87], v[52:55]  // 003090
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 003098
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 0030a0
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 0030a8
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 0030b0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[16:17], a[88:89], 0  // 0030b8
	s_add_u32 m0, 0x400, s59  // 0030c0
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0030c8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[18:19], a[90:91], v[56:59]  // 0030d0
	ds_read_b128 a[64:67], v38 offset:13568  // 0030d8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[20:21], a[92:93], v[56:59]  // 0030e0
	s_add_u32 m0, 0x500, s59  // 0030e8
	buffer_load_dword v37, s[4:7], 0 offen lds  // 0030f0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[22:23], a[94:95], v[56:59]  // 0030f8
	s_add_u32 s50, 0x200, s42  // 003128
	s_cmp_lt_u32 s50, s43  // 003130
	s_cselect_b32 s54, s54, 0  // 003134
	ds_read_b128 a[68:71], v38 offset:13632  // 003100
	v_mul_f32_e32 v4, v107, v93  // 003108
	v_mov_b32_e32 v5, v4  // 00310c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[24:25], a[88:89], 0  // 003110
	s_add_u32 s50, 0x180, s42  // 003138
	s_cmp_lt_u32 s50, s43  // 003140
	s_cselect_b32 s55, s55, 0  // 003144
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[26:27], a[90:91], v[60:63]  // 003118
	buffer_load_dword v93, v111, s[20:23], 0 offen  // 003120
	s_add_u32 s50, 0x200, s42  // 003148
	s_cmp_lt_u32 s50, s43  // 003150
	s_cselect_b32 s56, s56, 0  // 003154
	s_add_u32 s50, 0x180, s42  // 003158
	s_cmp_lt_u32 s50, s43  // 003160
	s_cselect_b32 s57, s57, 0  // 003164
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[28:29], a[92:93], v[60:63]  // 003168
	s_add_u32 s4, s54, s4  // 003180
	s_addc_u32 s5, 0, s5  // 003184
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[30:31], a[94:95], v[60:63]  // 003170
	buffer_load_dword v106, v115, s[24:27], 0 offen  // 003178
	s_sub_u32 s6, s6, s54  // 003188
	s_add_u32 s8, s55, s8  // 00318c
	s_addc_u32 s9, 0, s9  // 003190
	s_sub_u32 s10, s10, s55  // 003194
	s_add_u32 s20, s56, s20  // 003198
	s_addc_u32 s21, 0, s21  // 00319c
	s_add_u32 s24, s57, s24  // 0031a0
	s_addc_u32 s25, 0, s25  // 0031a4
	s_sub_u32 s26, s26, s57  // 0031a8
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 0031ac
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 0031b4
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 0031bc
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 0031c4
	s_addk_i32 s42, 0x80  // 0031cc
	s_cmp_lt_i32 s42, s43  // 0031d0
	s_cbranch_scc0 L_3bec  // 0031d4
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 0031dc
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[32:33], a[48:49], 0  // 0031e0
	s_add_u32 m0, 0, s60  // 0031e8
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0031ec
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[34:35], a[50:51], v[40:43]  // 0031f4
	ds_read_b128 a[72:75], v38  // 0031fc
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[36:37], a[52:53], v[40:43]  // 003204
	s_add_u32 m0, 0x100, s60  // 00320c
	buffer_load_dword v33, s[4:7], 0 offen lds  // 003214
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[38:39], a[54:55], v[40:43]  // 00321c
	ds_read_b128 a[76:79], v38 offset:64  // 003224
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v108, v94  // 00322c
	v_mov_b32_e32 v5, v4  // 003230
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[40:41], a[48:49], 0  // 003234
	buffer_load_dwordx4 a[16:19], v28, s[8:11], 0 offen  // 00323c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[42:43], a[50:51], v[44:47]  // 003244
	buffer_load_dword v94, v109, s[20:23], 0 offen  // 00324c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[44:45], a[52:53], v[44:47]  // 003254
	buffer_load_dwordx4 a[20:23], v29, s[8:11], 0 offen  // 00325c
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[46:47], a[54:55], v[44:47]  // 003264
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 00326c
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 003274
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 00327c
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 003284
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[32:33], a[56:57], 0  // 00328c
	s_add_u32 m0, 0x200, s60  // 003294
	buffer_load_dword v34, s[4:7], 0 offen lds  // 00329c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[34:35], a[58:59], v[48:51]  // 0032a4
	ds_read_b128 a[80:83], v38 offset:512  // 0032ac
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[36:37], a[60:61], v[48:51]  // 0032b4
	s_add_u32 m0, 0x300, s60  // 0032bc
	buffer_load_dword v35, s[4:7], 0 offen lds  // 0032c4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[38:39], a[62:63], v[48:51]  // 0032cc
	ds_read_b128 a[84:87], v38 offset:576  // 0032d4
	v_mul_f32_e32 v4, v108, v95  // 0032dc
	v_mov_b32_e32 v5, v4  // 0032e0
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[40:41], a[56:57], 0  // 0032e4
	buffer_load_dwordx4 a[24:27], v30, s[8:11], 0 offen  // 0032ec
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[42:43], a[58:59], v[52:55]  // 0032f4
	buffer_load_dword v95, v110, s[20:23], 0 offen  // 0032fc
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[44:45], a[60:61], v[52:55]  // 003304
	buffer_load_dwordx4 a[28:31], v31, s[8:11], 0 offen  // 00330c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[46:47], a[62:63], v[52:55]  // 003314
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 00331c
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 003324
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 00332c
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 003334
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[32:33], a[64:65], 0  // 00333c
	s_add_u32 m0, 0x400, s60  // 003344
	buffer_load_dword v36, s[4:7], 0 offen lds  // 00334c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[34:35], a[66:67], v[56:59]  // 003354
	ds_read_b128 a[88:91], v38 offset:1024  // 00335c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[36:37], a[68:69], v[56:59]  // 003364
	s_add_u32 m0, 0x500, s60  // 00336c
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003374
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[38:39], a[70:71], v[56:59]  // 00337c
	s_add_u32 s50, 0x200, s42  // 0033ac
	s_cmp_lt_u32 s50, s43  // 0033b4
	s_cselect_b32 s54, s54, 0  // 0033b8
	ds_read_b128 a[92:95], v38 offset:1088  // 003384
	v_mul_f32_e32 v4, v108, v96  // 00338c
	v_mov_b32_e32 v5, v4  // 003390
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[40:41], a[64:65], 0  // 003394
	s_add_u32 s50, 0x180, s42  // 0033bc
	s_cmp_lt_u32 s50, s43  // 0033c4
	s_cselect_b32 s55, s55, 0  // 0033c8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[42:43], a[66:67], v[60:63]  // 00339c
	buffer_load_dword v96, v111, s[20:23], 0 offen  // 0033a4
	s_add_u32 s50, 0x200, s42  // 0033cc
	s_cmp_lt_u32 s50, s43  // 0033d4
	s_cselect_b32 s56, s56, 0  // 0033d8
	s_add_u32 s50, 0x180, s42  // 0033dc
	s_cmp_lt_u32 s50, s43  // 0033e4
	s_cselect_b32 s57, s57, 0  // 0033e8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[44:45], a[68:69], v[60:63]  // 0033ec
	s_add_u32 s4, s54, s4  // 003404
	s_addc_u32 s5, 0, s5  // 003408
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[46:47], a[70:71], v[60:63]  // 0033f4
	buffer_load_dword v107, v115, s[24:27], 0 offen  // 0033fc
	s_sub_u32 s6, s6, s54  // 00340c
	s_add_u32 s8, s55, s8  // 003410
	s_addc_u32 s9, 0, s9  // 003414
	s_sub_u32 s10, s10, s55  // 003418
	s_add_u32 s20, s56, s20  // 00341c
	s_addc_u32 s21, 0, s21  // 003420
	s_add_u32 s24, s57, s24  // 003424
	s_addc_u32 s25, 0, s25  // 003428
	s_sub_u32 s26, s26, s57  // 00342c
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 003430
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 003438
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 003440
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 003448
	s_addk_i32 s42, 0x80  // 003450
	s_cmp_lt_i32 s42, s43  // 003454
	s_cbranch_scc0 L_3bec  // 003458
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 003460
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[0:1], a[72:73], 0  // 003464
	s_add_u32 m0, 0, s58  // 00346c
	buffer_load_dword v32, s[4:7], 0 offen lds  // 003470
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[2:3], a[74:75], v[40:43]  // 003478
	ds_read_b128 a[48:51], v38 offset:6272  // 003480
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[4:5], a[76:77], v[40:43]  // 003488
	s_add_u32 m0, 0x100, s58  // 003490
	buffer_load_dword v33, s[4:7], 0 offen lds  // 003498
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[6:7], a[78:79], v[40:43]  // 0034a0
	ds_read_b128 a[52:55], v38 offset:6336  // 0034a8
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v106, v88  // 0034b0
	v_mov_b32_e32 v5, v4  // 0034b4
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[8:9], a[72:73], 0  // 0034b8
	buffer_load_dwordx4 a[32:35], v28, s[8:11], 0 offen  // 0034c0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[10:11], a[74:75], v[44:47]  // 0034c8
	buffer_load_dword v88, v109, s[20:23], 0 offen  // 0034d0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[12:13], a[76:77], v[44:47]  // 0034d8
	buffer_load_dwordx4 a[36:39], v29, s[8:11], 0 offen  // 0034e0
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[14:15], a[78:79], v[44:47]  // 0034e8
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 0034f0
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 0034f8
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 003500
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 003508
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[0:1], a[80:81], 0  // 003510
	s_add_u32 m0, 0x200, s58  // 003518
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003520
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[2:3], a[82:83], v[48:51]  // 003528
	ds_read_b128 a[56:59], v38 offset:6784  // 003530
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[4:5], a[84:85], v[48:51]  // 003538
	s_add_u32 m0, 0x300, s58  // 003540
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003548
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[6:7], a[86:87], v[48:51]  // 003550
	ds_read_b128 a[60:63], v38 offset:6848  // 003558
	v_mul_f32_e32 v4, v106, v89  // 003560
	v_mov_b32_e32 v5, v4  // 003564
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[8:9], a[80:81], 0  // 003568
	buffer_load_dwordx4 a[40:43], v30, s[8:11], 0 offen  // 003570
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[10:11], a[82:83], v[52:55]  // 003578
	buffer_load_dword v89, v110, s[20:23], 0 offen  // 003580
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[12:13], a[84:85], v[52:55]  // 003588
	buffer_load_dwordx4 a[44:47], v31, s[8:11], 0 offen  // 003590
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[14:15], a[86:87], v[52:55]  // 003598
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 0035a0
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 0035a8
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 0035b0
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 0035b8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[0:1], a[88:89], 0  // 0035c0
	s_add_u32 m0, 0x400, s58  // 0035c8
	buffer_load_dword v36, s[4:7], 0 offen lds  // 0035d0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[2:3], a[90:91], v[56:59]  // 0035d8
	ds_read_b128 a[64:67], v38 offset:7296  // 0035e0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[4:5], a[92:93], v[56:59]  // 0035e8
	s_add_u32 m0, 0x500, s58  // 0035f0
	buffer_load_dword v37, s[4:7], 0 offen lds  // 0035f8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[6:7], a[94:95], v[56:59]  // 003600
	s_add_u32 s50, 0x200, s42  // 003630
	s_cmp_lt_u32 s50, s43  // 003638
	s_cselect_b32 s54, s54, 0  // 00363c
	ds_read_b128 a[68:71], v38 offset:7360  // 003608
	v_mul_f32_e32 v4, v106, v90  // 003610
	v_mov_b32_e32 v5, v4  // 003614
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[8:9], a[88:89], 0  // 003618
	s_add_u32 s50, 0x180, s42  // 003640
	s_cmp_lt_u32 s50, s43  // 003648
	s_cselect_b32 s55, s55, 0  // 00364c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[10:11], a[90:91], v[60:63]  // 003620
	buffer_load_dword v90, v111, s[20:23], 0 offen  // 003628
	s_add_u32 s50, 0x200, s42  // 003650
	s_cmp_lt_u32 s50, s43  // 003658
	s_cselect_b32 s56, s56, 0  // 00365c
	s_add_u32 s50, 0x180, s42  // 003660
	s_cmp_lt_u32 s50, s43  // 003668
	s_cselect_b32 s57, s57, 0  // 00366c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[12:13], a[92:93], v[60:63]  // 003670
	s_add_u32 s4, s54, s4  // 003688
	s_addc_u32 s5, 0, s5  // 00368c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[14:15], a[94:95], v[60:63]  // 003678
	buffer_load_dword v108, v115, s[24:27], 0 offen  // 003680
	s_sub_u32 s6, s6, s54  // 003690
	s_add_u32 s8, s55, s8  // 003694
	s_addc_u32 s9, 0, s9  // 003698
	s_sub_u32 s10, s10, s55  // 00369c
	s_add_u32 s20, s56, s20  // 0036a0
	s_addc_u32 s21, 0, s21  // 0036a4
	s_add_u32 s24, s57, s24  // 0036a8
	s_addc_u32 s25, 0, s25  // 0036ac
	s_sub_u32 s26, s26, s57  // 0036b0
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 0036b4
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 0036bc
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 0036c4
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 0036cc
	s_addk_i32 s42, 0x80  // 0036d4
	s_cmp_lt_i32 s42, s43  // 0036d8
	s_cbranch_scc0 L_3bec  // 0036dc
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 0036e4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[16:17], a[48:49], 0  // 0036e8
	s_add_u32 m0, 0, s59  // 0036f0
	buffer_load_dword v32, s[4:7], 0 offen lds  // 0036f4
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[18:19], a[50:51], v[40:43]  // 0036fc
	ds_read_b128 a[72:75], v38 offset:12544  // 003704
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[20:21], a[52:53], v[40:43]  // 00370c
	s_add_u32 m0, 0x100, s59  // 003714
	buffer_load_dword v33, s[4:7], 0 offen lds  // 00371c
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[22:23], a[54:55], v[40:43]  // 003724
	ds_read_b128 a[76:79], v38 offset:12608  // 00372c
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v107, v91  // 003734
	v_mov_b32_e32 v5, v4  // 003738
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[24:25], a[48:49], 0  // 00373c
	buffer_load_dwordx4 a[0:3], v28, s[8:11], 0 offen  // 003744
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[26:27], a[50:51], v[44:47]  // 00374c
	buffer_load_dword v91, v109, s[20:23], 0 offen  // 003754
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[28:29], a[52:53], v[44:47]  // 00375c
	buffer_load_dwordx4 a[4:7], v29, s[8:11], 0 offen  // 003764
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[30:31], a[54:55], v[44:47]  // 00376c
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 003774
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 00377c
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 003784
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 00378c
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[16:17], a[56:57], 0  // 003794
	s_add_u32 m0, 0x200, s59  // 00379c
	buffer_load_dword v34, s[4:7], 0 offen lds  // 0037a4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[18:19], a[58:59], v[48:51]  // 0037ac
	ds_read_b128 a[80:83], v38 offset:13056  // 0037b4
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[20:21], a[60:61], v[48:51]  // 0037bc
	s_add_u32 m0, 0x300, s59  // 0037c4
	buffer_load_dword v35, s[4:7], 0 offen lds  // 0037cc
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[22:23], a[62:63], v[48:51]  // 0037d4
	ds_read_b128 a[84:87], v38 offset:13120  // 0037dc
	v_mul_f32_e32 v4, v107, v92  // 0037e4
	v_mov_b32_e32 v5, v4  // 0037e8
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[24:25], a[56:57], 0  // 0037ec
	buffer_load_dwordx4 a[8:11], v30, s[8:11], 0 offen  // 0037f4
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[26:27], a[58:59], v[52:55]  // 0037fc
	buffer_load_dword v92, v110, s[20:23], 0 offen  // 003804
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[28:29], a[60:61], v[52:55]  // 00380c
	buffer_load_dwordx4 a[12:15], v31, s[8:11], 0 offen  // 003814
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[30:31], a[62:63], v[52:55]  // 00381c
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 003824
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 00382c
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 003834
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 00383c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[16:17], a[64:65], 0  // 003844
	s_add_u32 m0, 0x400, s59  // 00384c
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003854
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[18:19], a[66:67], v[56:59]  // 00385c
	ds_read_b128 a[88:91], v38 offset:13568  // 003864
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[20:21], a[68:69], v[56:59]  // 00386c
	s_add_u32 m0, 0x500, s59  // 003874
	buffer_load_dword v37, s[4:7], 0 offen lds  // 00387c
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[22:23], a[70:71], v[56:59]  // 003884
	s_add_u32 s50, 0x200, s42  // 0038b4
	s_cmp_lt_u32 s50, s43  // 0038bc
	s_cselect_b32 s54, s54, 0  // 0038c0
	ds_read_b128 a[92:95], v38 offset:13632  // 00388c
	v_mul_f32_e32 v4, v107, v93  // 003894
	v_mov_b32_e32 v5, v4  // 003898
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[24:25], a[64:65], 0  // 00389c
	s_add_u32 s50, 0x180, s42  // 0038c4
	s_cmp_lt_u32 s50, s43  // 0038cc
	s_cselect_b32 s55, s55, 0  // 0038d0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[26:27], a[66:67], v[60:63]  // 0038a4
	buffer_load_dword v93, v111, s[20:23], 0 offen  // 0038ac
	s_add_u32 s50, 0x200, s42  // 0038d4
	s_cmp_lt_u32 s50, s43  // 0038dc
	s_cselect_b32 s56, s56, 0  // 0038e0
	s_add_u32 s50, 0x180, s42  // 0038e4
	s_cmp_lt_u32 s50, s43  // 0038ec
	s_cselect_b32 s57, s57, 0  // 0038f0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[28:29], a[68:69], v[60:63]  // 0038f4
	s_add_u32 s4, s54, s4  // 00390c
	s_addc_u32 s5, 0, s5  // 003910
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[30:31], a[70:71], v[60:63]  // 0038fc
	buffer_load_dword v106, v115, s[24:27], 0 offen  // 003904
	s_sub_u32 s6, s6, s54  // 003914
	s_add_u32 s8, s55, s8  // 003918
	s_addc_u32 s9, 0, s9  // 00391c
	s_sub_u32 s10, s10, s55  // 003920
	s_add_u32 s20, s56, s20  // 003924
	s_addc_u32 s21, 0, s21  // 003928
	s_add_u32 s24, s57, s24  // 00392c
	s_addc_u32 s25, 0, s25  // 003930
	s_sub_u32 s26, s26, s57  // 003934
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 003938
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 003940
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 003948
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 003950
	s_addk_i32 s42, 0x80  // 003958
	s_cmp_lt_i32 s42, s43  // 00395c
	s_cbranch_scc0 L_3bec  // 003960
	s_waitcnt vmcnt(16) & lgkmcnt(0)
	s_barrier  // 003968
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[32:33], a[72:73], 0  // 00396c
	s_add_u32 m0, 0, s60  // 003974
	buffer_load_dword v32, s[4:7], 0 offen lds  // 003978
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[34:35], a[74:75], v[40:43]  // 003980
	ds_read_b128 a[48:51], v38  // 003988
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[36:37], a[76:77], v[40:43]  // 003990
	s_add_u32 m0, 0x100, s60  // 003998
	buffer_load_dword v33, s[4:7], 0 offen lds  // 0039a0
	v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[38:39], a[78:79], v[40:43]  // 0039a8
	ds_read_b128 a[52:55], v38 offset:64  // 0039b0
	s_waitcnt vmcnt(16)
	v_mul_f32_e32 v4, v108, v94  // 0039b8
	v_mov_b32_e32 v5, v4  // 0039bc
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[40:41], a[72:73], 0  // 0039c0
	buffer_load_dwordx4 a[16:19], v28, s[8:11], 0 offen  // 0039c8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[42:43], a[74:75], v[44:47]  // 0039d0
	buffer_load_dword v94, v109, s[20:23], 0 offen  // 0039d8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[44:45], a[76:77], v[44:47]  // 0039e0
	buffer_load_dwordx4 a[20:23], v29, s[8:11], 0 offen  // 0039e8
	v_mfma_f32_16x16x32_fp8_fp8 v[44:47], a[46:47], a[78:79], v[44:47]  // 0039f0
	s_nop 0
	v_pk_fma_f32 v[64:65], v[4:5], v[40:41], v[64:65]  // 0039f8
	v_pk_fma_f32 v[66:67], v[4:5], v[42:43], v[66:67]  // 003a00
	v_pk_fma_f32 v[68:69], v[4:5], v[44:45], v[68:69]  // 003a08
	v_pk_fma_f32 v[70:71], v[4:5], v[46:47], v[70:71]  // 003a10
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[32:33], a[80:81], 0  // 003a18
	s_add_u32 m0, 0x200, s60  // 003a20
	buffer_load_dword v34, s[4:7], 0 offen lds  // 003a28
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[34:35], a[82:83], v[48:51]  // 003a30
	ds_read_b128 a[56:59], v38 offset:512  // 003a38
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[36:37], a[84:85], v[48:51]  // 003a40
	s_add_u32 m0, 0x300, s60  // 003a48
	buffer_load_dword v35, s[4:7], 0 offen lds  // 003a50
	v_mfma_f32_16x16x32_fp8_fp8 v[48:51], a[38:39], a[86:87], v[48:51]  // 003a58
	ds_read_b128 a[60:63], v38 offset:576  // 003a60
	v_mul_f32_e32 v4, v108, v95  // 003a68
	v_mov_b32_e32 v5, v4  // 003a6c
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[40:41], a[80:81], 0  // 003a70
	buffer_load_dwordx4 a[24:27], v30, s[8:11], 0 offen  // 003a78
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[42:43], a[82:83], v[52:55]  // 003a80
	buffer_load_dword v95, v110, s[20:23], 0 offen  // 003a88
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[44:45], a[84:85], v[52:55]  // 003a90
	buffer_load_dwordx4 a[28:31], v31, s[8:11], 0 offen  // 003a98
	v_mfma_f32_16x16x32_fp8_fp8 v[52:55], a[46:47], a[86:87], v[52:55]  // 003aa0
	s_nop 0
	v_pk_fma_f32 v[72:73], v[4:5], v[48:49], v[72:73]  // 003aa8
	v_pk_fma_f32 v[74:75], v[4:5], v[50:51], v[74:75]  // 003ab0
	v_pk_fma_f32 v[76:77], v[4:5], v[52:53], v[76:77]  // 003ab8
	v_pk_fma_f32 v[78:79], v[4:5], v[54:55], v[78:79]  // 003ac0
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[32:33], a[88:89], 0  // 003ac8
	s_add_u32 m0, 0x400, s60  // 003ad0
	buffer_load_dword v36, s[4:7], 0 offen lds  // 003ad8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[34:35], a[90:91], v[56:59]  // 003ae0
	ds_read_b128 a[64:67], v38 offset:1024  // 003ae8
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[36:37], a[92:93], v[56:59]  // 003af0
	s_add_u32 m0, 0x500, s60  // 003af8
	buffer_load_dword v37, s[4:7], 0 offen lds  // 003b00
	v_mfma_f32_16x16x32_fp8_fp8 v[56:59], a[38:39], a[94:95], v[56:59]  // 003b08
	s_add_u32 s50, 0x200, s42  // 003b38
	s_cmp_lt_u32 s50, s43  // 003b40
	s_cselect_b32 s54, s54, 0  // 003b44
	ds_read_b128 a[68:71], v38 offset:1088  // 003b10
	v_mul_f32_e32 v4, v108, v96  // 003b18
	v_mov_b32_e32 v5, v4  // 003b1c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[40:41], a[88:89], 0  // 003b20
	s_add_u32 s50, 0x180, s42  // 003b48
	s_cmp_lt_u32 s50, s43  // 003b50
	s_cselect_b32 s55, s55, 0  // 003b54
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[42:43], a[90:91], v[60:63]  // 003b28
	buffer_load_dword v96, v111, s[20:23], 0 offen  // 003b30
	s_add_u32 s50, 0x200, s42  // 003b58
	s_cmp_lt_u32 s50, s43  // 003b60
	s_cselect_b32 s56, s56, 0  // 003b64
	s_add_u32 s50, 0x180, s42  // 003b68
	s_cmp_lt_u32 s50, s43  // 003b70
	s_cselect_b32 s57, s57, 0  // 003b74
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[44:45], a[92:93], v[60:63]  // 003b78
	s_add_u32 s4, s54, s4  // 003b90
	s_addc_u32 s5, 0, s5  // 003b94
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[46:47], a[94:95], v[60:63]  // 003b80
	buffer_load_dword v107, v115, s[24:27], 0 offen  // 003b88
	s_sub_u32 s6, s6, s54  // 003b98
	s_add_u32 s8, s55, s8  // 003b9c
	s_addc_u32 s9, 0, s9  // 003ba0
	s_sub_u32 s10, s10, s55  // 003ba4
	s_add_u32 s20, s56, s20  // 003ba8
	s_addc_u32 s21, 0, s21  // 003bac
	s_add_u32 s24, s57, s24  // 003bb0
	s_addc_u32 s25, 0, s25  // 003bb4
	s_sub_u32 s26, s26, s57  // 003bb8
	v_pk_fma_f32 v[80:81], v[4:5], v[56:57], v[80:81]  // 003bbc
	v_pk_fma_f32 v[82:83], v[4:5], v[58:59], v[82:83]  // 003bc4
	v_pk_fma_f32 v[84:85], v[4:5], v[60:61], v[84:85]  // 003bcc
	v_pk_fma_f32 v[86:87], v[4:5], v[62:63], v[86:87]  // 003bd4
	s_addk_i32 s42, 0x80  // 003bdc
	s_cmp_lt_i32 s42, s43  // 003be0
	s_cbranch_scc0 L_3bec  // 003be4
	s_branch L_2cd0  // 003be8
L_3bec:
	s_cmp_eq_u32 s38, 1  // 003bec
	s_cbranch_scc1 L_3f20  // 003bf0
	v_add_f32_e32 v64, v64, v12  // 003bf4
	v_add_f32_e32 v65, v65, v13  // 003bf8
	v_perm_b32 v40, v65, v64, s48  // 003bfc
	v_add_f32_e32 v66, v66, v14  // 003c04
	v_add_f32_e32 v67, v67, v15  // 003c08
	v_perm_b32 v41, v67, v66, s48  // 003c0c
	v_add_f32_e32 v68, v68, v16  // 003c14
	v_add_f32_e32 v69, v69, v17  // 003c18
	v_perm_b32 v42, v69, v68, s48  // 003c1c
	v_add_f32_e32 v70, v70, v18  // 003c24
	v_add_f32_e32 v71, v71, v19  // 003c28
	v_perm_b32 v43, v71, v70, s48  // 003c2c
	v_add_f32_e32 v72, v72, v12  // 003c34
	v_add_f32_e32 v73, v73, v13  // 003c38
	v_perm_b32 v44, v73, v72, s48  // 003c3c
	v_add_f32_e32 v74, v74, v14  // 003c44
	v_add_f32_e32 v75, v75, v15  // 003c48
	v_perm_b32 v45, v75, v74, s48  // 003c4c
	v_add_f32_e32 v76, v76, v16  // 003c54
	v_add_f32_e32 v77, v77, v17  // 003c58
	v_perm_b32 v46, v77, v76, s48  // 003c5c
	v_add_f32_e32 v78, v78, v18  // 003c64
	v_add_f32_e32 v79, v79, v19  // 003c68
	v_perm_b32 v47, v79, v78, s48  // 003c6c
	v_add_f32_e32 v80, v80, v12  // 003c74
	v_add_f32_e32 v81, v81, v13  // 003c78
	v_perm_b32 v48, v81, v80, s48  // 003c7c
	v_add_f32_e32 v82, v82, v14  // 003c84
	v_add_f32_e32 v83, v83, v15  // 003c88
	v_perm_b32 v49, v83, v82, s48  // 003c8c
	v_add_f32_e32 v84, v84, v16  // 003c94
	v_add_f32_e32 v85, v85, v17  // 003c98
	v_perm_b32 v50, v85, v84, s48  // 003c9c
	v_add_f32_e32 v86, v86, v18  // 003ca4
	v_add_f32_e32 v87, v87, v19  // 003ca8
	v_perm_b32 v51, v87, v86, s48  // 003cac
	v_lshrrev_b32_e32 v4, 4, v0  // 003cb4
	v_mul_u32_u24_e32 v38, 34, v4  // 003cb8
	v_and_b32_e32 v4, 15, v0  // 003cbc
	v_mul_lo_u32 v5, 2, v4  // 003cc0
	v_add_u32_e32 v38, v5, v38  // 003cc8
	s_mul_i32 s50, s47, 0x110  // 003ccc
	v_add_u32_e32 v38, s50, v38  // 003cd4
	v_lshlrev_b32_e32 v38, 2, v38  // 003cd8
	v_lshrrev_b32_e32 v4, 1, v0  // 003cdc
	v_mul_u32_u24_e32 v32, 34, v4  // 003ce0
	v_and_b32_e32 v5, 1, v0  // 003ce4
	v_add_u32_e32 v32, v5, v32  // 003ce8
	s_mul_i32 s50, s47, 2  // 003cec
	v_add_u32_e32 v32, s50, v32  // 003cf0
	v_lshlrev_b32_e32 v32, 2, v32  // 003cf4
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 003cf8
	s_barrier  // 003cfc
	ds_write_b64 v38, v[40:41]  // 003d00
	ds_write_b64 v38, v[42:43] offset:544  // 003d08
	ds_write_b64 v38, v[44:45] offset:4352  // 003d10
	ds_write_b64 v38, v[46:47] offset:4896  // 003d18
	ds_write_b64 v38, v[48:49] offset:8704  // 003d20
	ds_write_b64 v38, v[50:51] offset:9248  // 003d28
	s_waitcnt lgkmcnt(0)  // 003d30
	s_barrier  // 003d34
	ds_read_b32 v40, v32  // 003d38
	ds_read_b32 v41, v32 offset:32  // 003d40
	ds_read_b32 v42, v32 offset:64  // 003d48
	ds_read_b32 v43, v32 offset:96  // 003d50
	ds_read_b32 v44, v32 offset:4352  // 003d58
	ds_read_b32 v45, v32 offset:4384  // 003d60
	ds_read_b32 v46, v32 offset:4416  // 003d68
	ds_read_b32 v47, v32 offset:4448  // 003d70
	ds_read_b32 v48, v32 offset:8704  // 003d78
	ds_read_b32 v49, v32 offset:8736  // 003d80
	ds_read_b32 v50, v32 offset:8768  // 003d88
	ds_read_b32 v51, v32 offset:8800  // 003d90
	s_waitcnt lgkmcnt(0)  // 003d98
	s_barrier  // 003d9c
	s_mul_i32 s50, s37, 4  // 003da0
	s_mul_i32 s51, s37, 8  // 003da4
	s_mul_i32 s52, s37, 16  // 003da8
	v_mov_b32_e32 v4, v23  // 003dac
	v_mov_b32_e32 v5, 0  // 003db0
	v_mov_b32_e32 v7, 0  // 003db4
	v_mov_b32_e32 v9, 0  // 003db8
	v_mov_b32_e32 v11, 0  // 003dbc
	v_mov_b32_e32 v6, v4  // 003dc0
	v_add_u32_e64 v10, v4, s51  // 003dc4
	s_cmp_ge_u32 s77, s32  // 003dcc
	s_cbranch_scc1 L_4010  // 003dd0
	global_atomic_pk_add_bf16 v6, v40, s[80:81]  // 003dd4
	v_add_u32_e64 v8, v6, s50  // 003ddc
	s_add_i32 s77, s77, 4  // 003de4
	s_cmp_ge_u32 s77, s32  // 003de8
	s_cbranch_scc1 L_4010  // 003dec
	global_atomic_pk_add_bf16 v8, v41, s[80:81]  // 003df0
	s_add_i32 s77, s77, 4  // 003df8
	s_cmp_ge_u32 s77, s32  // 003dfc
	s_cbranch_scc1 L_4010  // 003e00
	global_atomic_pk_add_bf16 v10, v42, s[80:81]  // 003e04
	v_add_u32_e64 v12, v10, s50  // 003e0c
	s_add_i32 s77, s77, 4  // 003e14
	s_cmp_ge_u32 s77, s32  // 003e18
	s_cbranch_scc1 L_4010  // 003e1c
	global_atomic_pk_add_bf16 v12, v43, s[80:81]  // 003e20
	s_add_i32 s77, s77, 4  // 003e28
	v_add_u32_e64 v4, v4, s52  // 003e2c
	v_mov_b32_e32 v6, v4  // 003e34
	v_add_u32_e64 v10, v4, s51  // 003e38
	s_cmp_ge_u32 s77, s32  // 003e40
	s_cbranch_scc1 L_4010  // 003e44
	global_atomic_pk_add_bf16 v6, v44, s[80:81]  // 003e48
	v_add_u32_e64 v8, v6, s50  // 003e50
	s_add_i32 s77, s77, 4  // 003e58
	s_cmp_ge_u32 s77, s32  // 003e5c
	s_cbranch_scc1 L_4010  // 003e60
	global_atomic_pk_add_bf16 v8, v45, s[80:81]  // 003e64
	s_add_i32 s77, s77, 4  // 003e6c
	s_cmp_ge_u32 s77, s32  // 003e70
	s_cbranch_scc1 L_4010  // 003e74
	global_atomic_pk_add_bf16 v10, v46, s[80:81]  // 003e78
	v_add_u32_e64 v12, v10, s50  // 003e80
	s_add_i32 s77, s77, 4  // 003e88
	s_cmp_ge_u32 s77, s32  // 003e8c
	s_cbranch_scc1 L_4010  // 003e90
	global_atomic_pk_add_bf16 v12, v47, s[80:81]  // 003e94
	s_add_i32 s77, s77, 4  // 003e9c
	v_add_u32_e64 v4, v4, s52  // 003ea0
	v_mov_b32_e32 v6, v4  // 003ea8
	v_add_u32_e64 v10, v4, s51  // 003eac
	s_cmp_ge_u32 s77, s32  // 003eb4
	s_cbranch_scc1 L_4010  // 003eb8
	global_atomic_pk_add_bf16 v6, v48, s[80:81]  // 003ebc
	v_add_u32_e64 v8, v6, s50  // 003ec4
	s_add_i32 s77, s77, 4  // 003ecc
	s_cmp_ge_u32 s77, s32  // 003ed0
	s_cbranch_scc1 L_4010  // 003ed4
	global_atomic_pk_add_bf16 v8, v49, s[80:81]  // 003ed8
	s_add_i32 s77, s77, 4  // 003ee0
	s_cmp_ge_u32 s77, s32  // 003ee4
	s_cbranch_scc1 L_4010  // 003ee8
	global_atomic_pk_add_bf16 v10, v50, s[80:81]  // 003eec
	v_add_u32_e64 v12, v10, s50  // 003ef4
	s_add_i32 s77, s77, 4  // 003efc
	s_cmp_ge_u32 s77, s32  // 003f00
	s_cbranch_scc1 L_4010  // 003f04
	global_atomic_pk_add_bf16 v12, v51, s[80:81]  // 003f08
	s_add_i32 s77, s77, 4  // 003f10
	v_add_u32_e64 v4, v4, s52  // 003f14
	s_branch L_4010  // 003f1c
L_3f20:
	v_add_f32_e32 v64, v64, v12  // 003f20
	v_add_f32_e32 v65, v65, v13  // 003f24
	v_perm_b32 v40, v65, v64, s48  // 003f28
	v_add_f32_e32 v66, v66, v14  // 003f30
	v_add_f32_e32 v67, v67, v15  // 003f34
	v_perm_b32 v41, v67, v66, s48  // 003f38
	buffer_store_dwordx2 v[40:41], v20, s[16:19], 0 offen  // 003f40
	v_add_f32_e32 v68, v68, v16  // 003f48
	v_add_f32_e32 v69, v69, v17  // 003f4c
	v_perm_b32 v42, v69, v68, s48  // 003f50
	v_add_f32_e32 v70, v70, v18  // 003f58
	v_add_f32_e32 v71, v71, v19  // 003f5c
	v_perm_b32 v43, v71, v70, s48  // 003f60
	buffer_store_dwordx2 v[42:43], v20, s[16:19], 0 offen offset:32  // 003f68
	v_add_f32_e32 v72, v72, v12  // 003f70
	v_add_f32_e32 v73, v73, v13  // 003f74
	v_perm_b32 v44, v73, v72, s48  // 003f78
	v_add_f32_e32 v74, v74, v14  // 003f80
	v_add_f32_e32 v75, v75, v15  // 003f84
	v_perm_b32 v45, v75, v74, s48  // 003f88
	buffer_store_dwordx2 v[44:45], v21, s[16:19], 0 offen  // 003f90
	v_add_f32_e32 v76, v76, v16  // 003f98
	v_add_f32_e32 v77, v77, v17  // 003f9c
	v_perm_b32 v46, v77, v76, s48  // 003fa0
	v_add_f32_e32 v78, v78, v18  // 003fa8
	v_add_f32_e32 v79, v79, v19  // 003fac
	v_perm_b32 v47, v79, v78, s48  // 003fb0
	buffer_store_dwordx2 v[46:47], v21, s[16:19], 0 offen offset:32  // 003fb8
	v_add_f32_e32 v80, v80, v12  // 003fc0
	v_add_f32_e32 v81, v81, v13  // 003fc4
	v_perm_b32 v48, v81, v80, s48  // 003fc8
	v_add_f32_e32 v82, v82, v14  // 003fd0
	v_add_f32_e32 v83, v83, v15  // 003fd4
	v_perm_b32 v49, v83, v82, s48  // 003fd8
	buffer_store_dwordx2 v[48:49], v22, s[16:19], 0 offen  // 003fe0
	v_add_f32_e32 v84, v84, v16  // 003fe8
	v_add_f32_e32 v85, v85, v17  // 003fec
	v_perm_b32 v50, v85, v84, s48  // 003ff0
	v_add_f32_e32 v86, v86, v18  // 003ff8
	v_add_f32_e32 v87, v87, v19  // 003ffc
	v_perm_b32 v51, v87, v86, s48  // 004000
	buffer_store_dwordx2 v[50:51], v22, s[16:19], 0 offen offset:32  // 004008
L_4010:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 004010
	s_endpgm  // 004014
.Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E:
	.size _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E, .Lfunc_end__ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E-_ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E
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
    .name:           _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter42fp8gemm_bf16_blockscale_BpreShuffle_48x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
