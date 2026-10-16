// disassembled from fp8gemm_bf16_blockscale_BpreShuffle_128x128.co by co2s.py
// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu=gfx942 -mcode-object-version=6 -c seed.s -o k.o && ld.lld -shared k.o -o k.co

	.amdgcn_target "amdgcn-amd-amdhsa--gfx942"
	.amdhsa_code_object_version 6

	.text
	.globl _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E
	.protected _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E
	.p2align 8
	.type _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E,@function
_ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E:
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
	s_mul_i32 s50, s45, 0x80  // 00258c
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
	s_mul_i32 s50, s45, 0x80  // 0025c4
	s_sub_i32 s51, s32, s50  // 0025cc
	s_cmp_lt_u32 s51, 0x80  // 0025d0
	s_cselect_b32 s50, s51, 0x80  // 0025d8
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
	s_mul_i32 s50, 0x80, s45  // 0026a0
	s_mul_hi_u32 s52, 4, s50  // 0026a8
	s_mul_i32 s51, 4, s50  // 0026ac
	s_add_u32 s20, s20, s51  // 0026b0
	s_addc_u32 s21, s21, s52  // 0026b4
	s_sub_i32 s51, s32, s50  // 0026b8
	s_cmp_lt_u32 s51, 0x80  // 0026bc
	s_cselect_b32 s50, s51, 0x80  // 0026c4
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
	v_and_b32_e64 v239, v0, 15  // 002704
	v_lshlrev_b32_e32 v239, 2, v239  // 00270c
	s_mov_b32 s50, 64  // 002710
	v_add_u32_e64 v240, v239, s50  // 002714
	s_mov_b32 s50, 0x80  // 00271c
	v_add_u32_e64 v241, v239, s50  // 002724
	s_mov_b32 s50, 0xc0  // 00272c
	v_add_u32_e64 v242, v239, s50  // 002734
	s_mov_b32 s50, 0x100  // 00273c
	v_add_u32_e64 v243, v239, s50  // 002744
	s_mov_b32 s50, 0x140  // 00274c
	v_add_u32_e64 v244, v239, s50  // 002754
	s_mov_b32 s50, 0x180  // 00275c
	v_add_u32_e64 v245, v239, s50  // 002764
	s_mov_b32 s50, 0x1c0  // 00276c
	v_add_u32_e64 v246, v239, s50  // 002774
	s_mul_i32 s51, s41, s44  // 00277c
	s_mul_hi_u32 s52, 4, s51  // 002780
	s_add_u32 s25, s25, s52  // 002784
	s_mul_i32 s52, 4, s51  // 002788
	s_add_u32 s24, s24, s52  // 00278c
	s_addc_u32 s25, s25, 0  // 002790
	s_lshr_b32 s50, s76, 7  // 002794
	s_mul_i32 s50, s50, s75  // 002798
	s_lshl_b32 s50, s50, 2  // 00279c
	s_add_u32 s24, s24, s50  // 0027a0
	s_addc_u32 s25, s25, 0  // 0027a4
	s_sub_u32 s26, s26, s50  // 0027a8
	v_mov_b32_e32 v255, 0  // 0027ac
	v_lshrrev_b32_e32 v4, 5, v0  // 0027b0
	v_lshlrev_b32_e32 v4, 2, v4  // 0027b4
	v_mul_i32_i24_e32 v4, s35, v4  // 0027b8
	v_and_b32_e32 v42, 31, v0  // 0027bc
	v_lshlrev_b32_e32 v42, 2, v42  // 0027c0
	s_mul_i32 s50, 0x80, s45  // 0027c4
	s_sub_i32 s51, s32, s50  // 0027cc
	s_cmp_lt_u32 s51, 0x80  // 0027d0
	s_cselect_b32 s51, s51, 0x80  // 0027d8
	s_mul_i32 s52, s35, s50  // 0027e0
	s_mul_hi_u32 s50, s35, s50  // 0027e4
	s_add_u32 s4, s4, s52  // 0027e8
	s_addc_u32 s5, s5, s50  // 0027ec
	s_mul_i32 s50, s35, s51  // 0027f0
	s_mov_b32 s6, s50  // 0027f4
	s_mov_b32 s7, 0x20000  // 0027f8
	s_mul_i32 s51, s76, s75  // 002800
	s_add_u32 s4, s51, s4  // 002804
	s_addc_u32 s5, 0, s5  // 002808
	s_sub_u32 s6, s6, s51  // 00280c
	s_mul_i32 s50, s35, s47  // 002810
	v_add3_u32 v42, v4, v42, s50  // 002814
	s_lshl_b32 s50, s35, 3  // 00281c
	v_add_u32_e32 v43, s50, v42  // 002820
	v_add_u32_e32 v44, s50, v43  // 002824
	v_add_u32_e32 v45, s50, v44  // 002828
	v_add_u32_e32 v46, s50, v45  // 00282c
	v_add_u32_e32 v47, s50, v46  // 002830
	v_add_u32_e32 v48, s50, v47  // 002834
	v_add_u32_e32 v49, s50, v48  // 002838
	v_add_u32_e32 v50, s50, v49  // 00283c
	v_add_u32_e32 v51, s50, v50  // 002840
	v_add_u32_e32 v52, s50, v51  // 002844
	v_add_u32_e32 v53, s50, v52  // 002848
	v_add_u32_e32 v54, s50, v53  // 00284c
	v_add_u32_e32 v55, s50, v54  // 002850
	v_add_u32_e32 v56, s50, v55  // 002854
	v_add_u32_e32 v57, s50, v56  // 002858
	s_mov_b32 s54, 0x80  // 00285c
	s_mul_i32 s56, s32, 4  // 002864
	s_mov_b32 s57, 4  // 002868
	s_mov_b32 s50, 0x80  // 00286c
	s_lshr_b32 s50, s50, 2  // 002874
	s_mul_i32 s50, s50, 32  // 002878
	s_mov_b32 s51, 8  // 00287c
	s_add_u32 s50, s50, s51  // 002880
	v_lshrrev_b32_e32 v4, 4, v0  // 002884
	v_and_b32_e32 v5, 15, v0  // 002888
	v_and_b32_e32 v6, 3, v5  // 00288c
	v_lshrrev_b32_e32 v7, 2, v5  // 002890
	v_lshlrev_b32_e32 v4, 2, v4  // 002894
	v_mul_lo_u32 v6, v6, s50  // 002898
	v_lshlrev_b32_e32 v7, 5, v7  // 0028a0
	v_add_u32_e32 v4, v4, v6  // 0028a4
	v_add_u32_e32 v4, v4, v7  // 0028a8
	v_lshlrev_b32_e32 v58, 2, v4  // 0028ac
	s_mul_i32 s50, 0x1020, s47  // 0028b0
	s_add_u32 s58, 0, s50  // 0028b8
	s_add_u32 s59, 0x4080, s58  // 0028bc
	s_add_u32 s60, 0x4080, s59  // 0028c4
	s_mov_b32 s55, 0x800  // 0028cc
	s_mul_i32 s49, 0x80, s44  // 0028d4
	s_sub_i32 s51, s33, s49  // 0028dc
	s_cmp_lt_u32 s51, 0x80  // 0028e0
	s_cselect_b32 s50, s51, 0x80  // 0028e8
	s_mul_i32 s51, s36, s49  // 0028f0
	s_mul_hi_u32 s52, s36, s49  // 0028f4
	s_add_u32 s8, s8, s51  // 0028f8
	s_addc_u32 s9, s9, s52  // 0028fc
	s_mul_i32 s51, s36, s50  // 002900
	s_mov_b32 s10, s51  // 002904
	s_mov_b32 s11, 0x20000  // 002908
	s_lshr_b32 s51, s76, 7  // 002910
	s_mul_i32 s50, s55, s75  // 002914
	s_mul_i32 s50, s51, s50  // 002918
	s_add_u32 s8, s50, s8  // 00291c
	s_addc_u32 s9, 0, s9  // 002920
	s_sub_u32 s10, s10, s50  // 002924
	s_lshl_b32 s50, s47, 5  // 002928
	s_mul_i32 s50, s36, s50  // 00292c
	v_lshlrev_b32_e32 v38, 4, v0  // 002930
	v_add_u32_e32 v38, s50, v38  // 002934
	s_mov_b32 s50, 0x400  // 002938
	v_add_u32_e64 v39, v38, s50  // 002940
	s_mul_i32 s50, s36, 16  // 002948
	v_add_u32_e64 v40, v38, s50  // 00294c
	v_add_u32_e64 v41, v39, s50  // 002954
	s_add_u32 m0, 0, s58  // 00295c
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002960
	s_add_u32 m0, 0x100, s58  // 002968
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002970
	s_add_u32 m0, 0x200, s58  // 002978
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002980
	s_add_u32 m0, 0x300, s58  // 002988
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002990
	s_add_u32 m0, 0x400, s58  // 002998
	buffer_load_dword v46, s[4:7], 0 offen lds  // 0029a0
	s_add_u32 m0, 0x500, s58  // 0029a8
	buffer_load_dword v47, s[4:7], 0 offen lds  // 0029b0
	s_add_u32 m0, 0x600, s58  // 0029b8
	buffer_load_dword v48, s[4:7], 0 offen lds  // 0029c0
	s_add_u32 m0, 0x700, s58  // 0029c8
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0029d0
	s_add_u32 m0, 0x800, s58  // 0029d8
	buffer_load_dword v50, s[4:7], 0 offen lds  // 0029e0
	s_add_u32 m0, 0x900, s58  // 0029e8
	buffer_load_dword v51, s[4:7], 0 offen lds  // 0029f0
	s_add_u32 m0, 0xa00, s58  // 0029f8
	buffer_load_dword v52, s[4:7], 0 offen lds  // 002a00
	s_add_u32 m0, 0xb00, s58  // 002a08
	buffer_load_dword v53, s[4:7], 0 offen lds  // 002a10
	s_add_u32 m0, 0xc00, s58  // 002a18
	buffer_load_dword v54, s[4:7], 0 offen lds  // 002a20
	s_add_u32 m0, 0xd00, s58  // 002a28
	buffer_load_dword v55, s[4:7], 0 offen lds  // 002a30
	s_add_u32 m0, 0xe00, s58  // 002a38
	buffer_load_dword v56, s[4:7], 0 offen lds  // 002a40
	s_add_u32 m0, 0xf00, s58  // 002a48
	buffer_load_dword v57, s[4:7], 0 offen lds  // 002a50
	s_mov_b32 s53, 0  // 002a58
	s_add_u32 s50, 0x80, s53  // 002a5c
	s_cmp_lt_u32 s50, s34  // 002a64
	s_cselect_b32 s54, s54, 0  // 002a68
	s_add_u32 s4, s54, s4  // 002a6c
	s_addc_u32 s5, 0, s5  // 002a70
	s_sub_u32 s6, s6, s54  // 002a74
	buffer_load_dword v188, v239, s[20:23], 0 offen  // 002a78
	buffer_load_dword v189, v240, s[20:23], 0 offen  // 002a80
	buffer_load_dword v190, v241, s[20:23], 0 offen  // 002a88
	buffer_load_dword v191, v242, s[20:23], 0 offen  // 002a90
	buffer_load_dword v192, v243, s[20:23], 0 offen  // 002a98
	buffer_load_dword v193, v244, s[20:23], 0 offen  // 002aa0
	buffer_load_dword v194, v245, s[20:23], 0 offen  // 002aa8
	buffer_load_dword v195, v246, s[20:23], 0 offen  // 002ab0
	s_add_u32 s50, 0x80, s53  // 002ab8
	s_cmp_lt_u32 s50, s34  // 002ac0
	s_cselect_b32 s56, s56, 0  // 002ac4
	s_add_u32 s20, s56, s20  // 002ac8
	s_addc_u32 s21, 0, s21  // 002acc
	v_mov_b32_e32 v124, 0  // 002ad0
	v_mov_b32_e32 v125, 0  // 002ad4
	v_mov_b32_e32 v126, 0  // 002ad8
	v_mov_b32_e32 v127, 0  // 002adc
	v_mov_b32_e32 v128, 0  // 002ae0
	v_mov_b32_e32 v129, 0  // 002ae4
	v_mov_b32_e32 v130, 0  // 002ae8
	v_mov_b32_e32 v131, 0  // 002aec
	buffer_load_dwordx4 a[0:3], v38, s[8:11], 0 offen  // 002af0
	buffer_load_dwordx4 a[4:7], v39, s[8:11], 0 offen  // 002af8
	buffer_load_dwordx4 a[8:11], v40, s[8:11], 0 offen  // 002b00
	buffer_load_dwordx4 a[12:15], v41, s[8:11], 0 offen  // 002b08
	s_mov_b32 s53, 0  // 002b10
	s_add_u32 s50, 0x80, s53  // 002b14
	s_cmp_lt_u32 s50, s34  // 002b1c
	s_cselect_b32 s55, s55, 0  // 002b20
	s_add_u32 s8, s55, s8  // 002b24
	s_addc_u32 s9, 0, s9  // 002b28
	s_sub_u32 s10, s10, s55  // 002b2c
	buffer_load_dword v236, v255, s[24:27], 0 offen  // 002b30
	s_add_u32 s50, 0x80, s53  // 002b38
	s_cmp_lt_u32 s50, s34  // 002b40
	s_cselect_b32 s57, s57, 0  // 002b44
	s_add_u32 s24, s57, s24  // 002b48
	s_addc_u32 s25, 0, s25  // 002b4c
	s_sub_u32 s26, s26, s57  // 002b50
	s_add_u32 m0, 0, s59  // 002b54
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002b58
	s_add_u32 m0, 0x100, s59  // 002b60
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002b68
	s_add_u32 m0, 0x200, s59  // 002b70
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002b78
	s_add_u32 m0, 0x300, s59  // 002b80
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002b88
	s_add_u32 m0, 0x400, s59  // 002b90
	buffer_load_dword v46, s[4:7], 0 offen lds  // 002b98
	s_add_u32 m0, 0x500, s59  // 002ba0
	buffer_load_dword v47, s[4:7], 0 offen lds  // 002ba8
	s_add_u32 m0, 0x600, s59  // 002bb0
	buffer_load_dword v48, s[4:7], 0 offen lds  // 002bb8
	s_add_u32 m0, 0x700, s59  // 002bc0
	buffer_load_dword v49, s[4:7], 0 offen lds  // 002bc8
	s_add_u32 m0, 0x800, s59  // 002bd0
	buffer_load_dword v50, s[4:7], 0 offen lds  // 002bd8
	s_add_u32 m0, 0x900, s59  // 002be0
	buffer_load_dword v51, s[4:7], 0 offen lds  // 002be8
	s_add_u32 m0, 0xa00, s59  // 002bf0
	buffer_load_dword v52, s[4:7], 0 offen lds  // 002bf8
	s_add_u32 m0, 0xb00, s59  // 002c00
	buffer_load_dword v53, s[4:7], 0 offen lds  // 002c08
	s_add_u32 m0, 0xc00, s59  // 002c10
	buffer_load_dword v54, s[4:7], 0 offen lds  // 002c18
	s_add_u32 m0, 0xd00, s59  // 002c20
	buffer_load_dword v55, s[4:7], 0 offen lds  // 002c28
	s_add_u32 m0, 0xe00, s59  // 002c30
	buffer_load_dword v56, s[4:7], 0 offen lds  // 002c38
	s_add_u32 m0, 0xf00, s59  // 002c40
	buffer_load_dword v57, s[4:7], 0 offen lds  // 002c48
	s_mov_b32 s53, 0x80  // 002c50
	s_add_u32 s50, 0x80, s53  // 002c58
	s_cmp_lt_u32 s50, s34  // 002c60
	s_cselect_b32 s54, s54, 0  // 002c64
	s_add_u32 s4, s54, s4  // 002c68
	s_addc_u32 s5, 0, s5  // 002c6c
	s_sub_u32 s6, s6, s54  // 002c70
	buffer_load_dword v196, v239, s[20:23], 0 offen  // 002c74
	buffer_load_dword v197, v240, s[20:23], 0 offen  // 002c7c
	buffer_load_dword v198, v241, s[20:23], 0 offen  // 002c84
	buffer_load_dword v199, v242, s[20:23], 0 offen  // 002c8c
	buffer_load_dword v200, v243, s[20:23], 0 offen  // 002c94
	buffer_load_dword v201, v244, s[20:23], 0 offen  // 002c9c
	buffer_load_dword v202, v245, s[20:23], 0 offen  // 002ca4
	buffer_load_dword v203, v246, s[20:23], 0 offen  // 002cac
	s_add_u32 s50, 0x80, s53  // 002cb4
	s_cmp_lt_u32 s50, s34  // 002cbc
	s_cselect_b32 s56, s56, 0  // 002cc0
	s_add_u32 s20, s56, s20  // 002cc4
	s_addc_u32 s21, 0, s21  // 002cc8
	v_mov_b32_e32 v132, 0  // 002ccc
	v_mov_b32_e32 v133, 0  // 002cd0
	v_mov_b32_e32 v134, 0  // 002cd4
	v_mov_b32_e32 v135, 0  // 002cd8
	v_mov_b32_e32 v136, 0  // 002cdc
	v_mov_b32_e32 v137, 0  // 002ce0
	v_mov_b32_e32 v138, 0  // 002ce4
	v_mov_b32_e32 v139, 0  // 002ce8
	buffer_load_dwordx4 a[16:19], v38, s[8:11], 0 offen  // 002cec
	buffer_load_dwordx4 a[20:23], v39, s[8:11], 0 offen  // 002cf4
	buffer_load_dwordx4 a[24:27], v40, s[8:11], 0 offen  // 002cfc
	buffer_load_dwordx4 a[28:31], v41, s[8:11], 0 offen  // 002d04
	s_mov_b32 s53, 0x80  // 002d0c
	s_add_u32 s50, 0x80, s53  // 002d14
	s_cmp_lt_u32 s50, s34  // 002d1c
	s_cselect_b32 s55, s55, 0  // 002d20
	s_add_u32 s8, s55, s8  // 002d24
	s_addc_u32 s9, 0, s9  // 002d28
	s_sub_u32 s10, s10, s55  // 002d2c
	buffer_load_dword v237, v255, s[24:27], 0 offen  // 002d30
	s_add_u32 s50, 0x80, s53  // 002d38
	s_cmp_lt_u32 s50, s34  // 002d40
	s_cselect_b32 s57, s57, 0  // 002d44
	s_add_u32 s24, s57, s24  // 002d48
	s_addc_u32 s25, 0, s25  // 002d4c
	s_sub_u32 s26, s26, s57  // 002d50
	s_add_u32 m0, 0, s60  // 002d54
	buffer_load_dword v42, s[4:7], 0 offen lds  // 002d58
	s_add_u32 m0, 0x100, s60  // 002d60
	buffer_load_dword v43, s[4:7], 0 offen lds  // 002d68
	s_add_u32 m0, 0x200, s60  // 002d70
	buffer_load_dword v44, s[4:7], 0 offen lds  // 002d78
	s_add_u32 m0, 0x300, s60  // 002d80
	buffer_load_dword v45, s[4:7], 0 offen lds  // 002d88
	s_add_u32 m0, 0x400, s60  // 002d90
	buffer_load_dword v46, s[4:7], 0 offen lds  // 002d98
	s_add_u32 m0, 0x500, s60  // 002da0
	buffer_load_dword v47, s[4:7], 0 offen lds  // 002da8
	s_add_u32 m0, 0x600, s60  // 002db0
	buffer_load_dword v48, s[4:7], 0 offen lds  // 002db8
	s_add_u32 m0, 0x700, s60  // 002dc0
	buffer_load_dword v49, s[4:7], 0 offen lds  // 002dc8
	s_add_u32 m0, 0x800, s60  // 002dd0
	buffer_load_dword v50, s[4:7], 0 offen lds  // 002dd8
	s_add_u32 m0, 0x900, s60  // 002de0
	buffer_load_dword v51, s[4:7], 0 offen lds  // 002de8
	s_add_u32 m0, 0xa00, s60  // 002df0
	buffer_load_dword v52, s[4:7], 0 offen lds  // 002df8
	s_add_u32 m0, 0xb00, s60  // 002e00
	buffer_load_dword v53, s[4:7], 0 offen lds  // 002e08
	s_add_u32 m0, 0xc00, s60  // 002e10
	buffer_load_dword v54, s[4:7], 0 offen lds  // 002e18
	s_add_u32 m0, 0xd00, s60  // 002e20
	buffer_load_dword v55, s[4:7], 0 offen lds  // 002e28
	s_add_u32 m0, 0xe00, s60  // 002e30
	buffer_load_dword v56, s[4:7], 0 offen lds  // 002e38
	s_add_u32 m0, 0xf00, s60  // 002e40
	buffer_load_dword v57, s[4:7], 0 offen lds  // 002e48
	s_mov_b32 s53, 0x100  // 002e50
	s_add_u32 s50, 0x80, s53  // 002e58
	s_cmp_lt_u32 s50, s34  // 002e60
	s_cselect_b32 s54, s54, 0  // 002e64
	s_add_u32 s4, s54, s4  // 002e68
	s_addc_u32 s5, 0, s5  // 002e6c
	s_sub_u32 s6, s6, s54  // 002e70
	buffer_load_dword v204, v239, s[20:23], 0 offen  // 002e74
	buffer_load_dword v205, v240, s[20:23], 0 offen  // 002e7c
	buffer_load_dword v206, v241, s[20:23], 0 offen  // 002e84
	buffer_load_dword v207, v242, s[20:23], 0 offen  // 002e8c
	buffer_load_dword v208, v243, s[20:23], 0 offen  // 002e94
	buffer_load_dword v209, v244, s[20:23], 0 offen  // 002e9c
	buffer_load_dword v210, v245, s[20:23], 0 offen  // 002ea4
	buffer_load_dword v211, v246, s[20:23], 0 offen  // 002eac
	s_add_u32 s50, 0x80, s53  // 002eb4
	s_cmp_lt_u32 s50, s34  // 002ebc
	s_cselect_b32 s56, s56, 0  // 002ec0
	s_add_u32 s20, s56, s20  // 002ec4
	s_addc_u32 s21, 0, s21  // 002ec8
	v_mov_b32_e32 v140, 0  // 002ecc
	v_mov_b32_e32 v141, 0  // 002ed0
	v_mov_b32_e32 v142, 0  // 002ed4
	v_mov_b32_e32 v143, 0  // 002ed8
	v_mov_b32_e32 v144, 0  // 002edc
	v_mov_b32_e32 v145, 0  // 002ee0
	v_mov_b32_e32 v146, 0  // 002ee4
	v_mov_b32_e32 v147, 0  // 002ee8
	v_mov_b32_e32 v148, 0  // 002eec
	v_mov_b32_e32 v149, 0  // 002ef0
	v_mov_b32_e32 v150, 0  // 002ef4
	v_mov_b32_e32 v151, 0  // 002ef8
	v_mov_b32_e32 v152, 0  // 002efc
	v_mov_b32_e32 v153, 0  // 002f00
	v_mov_b32_e32 v154, 0  // 002f04
	v_mov_b32_e32 v155, 0  // 002f08
	v_mov_b32_e32 v156, 0  // 002f0c
	v_mov_b32_e32 v157, 0  // 002f10
	v_mov_b32_e32 v158, 0  // 002f14
	v_mov_b32_e32 v159, 0  // 002f18
	v_mov_b32_e32 v160, 0  // 002f1c
	v_mov_b32_e32 v161, 0  // 002f20
	v_mov_b32_e32 v162, 0  // 002f24
	v_mov_b32_e32 v163, 0  // 002f28
	v_mov_b32_e32 v164, 0  // 002f2c
	v_mov_b32_e32 v165, 0  // 002f30
	v_mov_b32_e32 v166, 0  // 002f34
	v_mov_b32_e32 v167, 0  // 002f38
	v_mov_b32_e32 v168, 0  // 002f3c
	v_mov_b32_e32 v169, 0  // 002f40
	v_mov_b32_e32 v170, 0  // 002f44
	v_mov_b32_e32 v171, 0  // 002f48
	v_mov_b32_e32 v172, 0  // 002f4c
	v_mov_b32_e32 v173, 0  // 002f50
	v_mov_b32_e32 v174, 0  // 002f54
	v_mov_b32_e32 v175, 0  // 002f58
	v_mov_b32_e32 v176, 0  // 002f5c
	v_mov_b32_e32 v177, 0  // 002f60
	v_mov_b32_e32 v178, 0  // 002f64
	v_mov_b32_e32 v179, 0  // 002f68
	v_mov_b32_e32 v180, 0  // 002f6c
	v_mov_b32_e32 v181, 0  // 002f70
	v_mov_b32_e32 v182, 0  // 002f74
	v_mov_b32_e32 v183, 0  // 002f78
	v_mov_b32_e32 v184, 0  // 002f7c
	v_mov_b32_e32 v185, 0  // 002f80
	v_mov_b32_e32 v186, 0  // 002f84
	v_mov_b32_e32 v187, 0  // 002f88
	s_mov_b32 s43, s34  // 002f8c
	s_mov_b32 s42, 0  // 002f90
	s_waitcnt vmcnt(58)  // 002f94
	s_barrier  // 002f98
	ds_read_b128 a[48:51], v58  // 002f9c
	ds_read_b128 a[52:55], v58 offset:64  // 002fa4
	ds_read_b128 a[56:59], v58 offset:512  // 002fac
	ds_read_b128 a[60:63], v58 offset:576  // 002fb4
	ds_read_b128 a[64:67], v58 offset:1024  // 002fbc
	ds_read_b128 a[68:71], v58 offset:1088  // 002fc4
	ds_read_b128 a[72:75], v58 offset:1536  // 002fcc
	ds_read_b128 a[76:79], v58 offset:1600  // 002fd4
	ds_read_b128 a[80:83], v58 offset:2048  // 002fdc
	ds_read_b128 a[84:87], v58 offset:2112  // 002fe4
	ds_read_b128 a[88:91], v58 offset:2560  // 002fec
	ds_read_b128 a[92:95], v58 offset:2624  // 002ff4
	ds_read_b128 a[96:99], v58 offset:3072  // 002ffc
	ds_read_b128 a[100:103], v58 offset:3136  // 003004
	ds_read_b128 a[104:107], v58 offset:3584  // 00300c
	ds_read_b128 a[108:111], v58 offset:3648  // 003014
	s_mov_b32 s50, 0  // 00301c
	s_mov_b32 s51, 1.0  // 003020
	s_cmp_eq_u32 s50, s75  // 003024
	s_cselect_b32 s50, s51, 0  // 003028
	v_mul_f32_e64 v12, v12, s50  // 00302c
	v_mul_f32_e64 v13, v13, s50  // 003034
	v_mul_f32_e64 v14, v14, s50  // 00303c
	v_mul_f32_e64 v15, v15, s50  // 003044
	v_mul_f32_e64 v16, v16, s50  // 00304c
	v_mul_f32_e64 v17, v17, s50  // 003054
	v_mul_f32_e64 v18, v18, s50  // 00305c
	v_mul_f32_e64 v19, v19, s50  // 003064
	v_and_b32_e64 v20, v0, 15  // 00306c
	v_mul_lo_u32 v20, v20, s37  // 003074
	v_lshrrev_b32_e32 v4, 4, v0  // 00307c
	v_mul_i32_i24_e32 v4, 8, v4  // 003080
	v_add_u32_e32 v20, v4, v20  // 003084
	s_mul_i32 s50, 32, s47  // 003088
	s_mul_i32 s50, 2, s50  // 00308c
	v_add_u32_e32 v20, s50, v20  // 003090
	s_mul_i32 s50, 16, s37  // 003094
	v_add_u32_e32 v21, s50, v20  // 003098
	v_add_u32_e32 v22, s50, v21  // 00309c
	v_add_u32_e32 v23, s50, v22  // 0030a0
	v_add_u32_e32 v24, s50, v23  // 0030a4
	v_add_u32_e32 v25, s50, v24  // 0030a8
	v_add_u32_e32 v26, s50, v25  // 0030ac
	v_add_u32_e32 v27, s50, v26  // 0030b0
	s_mul_i32 s50, s47, s37  // 0030b4
	v_lshlrev_b32_e32 v5, 2, v0  // 0030b8
	v_add_u32_e32 v28, s50, v5  // 0030bc
	s_mul_i32 s50, s45, 0x80  // 0030c0
	s_add_i32 s77, s50, s47  // 0030c8
	s_cmp_lt_i32 s42, s43  // 0030cc
	s_cbranch_scc0 L_52b0  // 0030d0
L_30d4:
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 0030d8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[48:49], 0  // 0030dc
	s_add_u32 m0, 0, s58  // 0030e4
	buffer_load_dword v42, s[4:7], 0 offen lds  // 0030e8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[50:51], v[60:63]  // 0030f0
	ds_read_b128 a[112:115], v58 offset:16512  // 0030f8
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[52:53], v[60:63]  // 003100
	s_add_u32 m0, 0x100, s58  // 003108
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003110
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[54:55], v[60:63]  // 003118
	ds_read_b128 a[116:119], v58 offset:16576  // 003120
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v236, v188  // 003128
	v_mov_b32_e32 v5, v4  // 00312c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[48:49], 0  // 003130
	buffer_load_dwordx4 a[32:35], v38, s[8:11], 0 offen  // 003138
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[50:51], v[64:67]  // 003140
	buffer_load_dword v188, v239, s[20:23], 0 offen  // 003148
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[52:53], v[64:67]  // 003150
	buffer_load_dwordx4 a[36:39], v39, s[8:11], 0 offen  // 003158
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[54:55], v[64:67]  // 003160
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 003168
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 003170
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 003178
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 003180
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[56:57], 0  // 003188
	s_add_u32 m0, 0x200, s58  // 003190
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003198
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[58:59], v[68:71]  // 0031a0
	ds_read_b128 a[120:123], v58 offset:17024  // 0031a8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[60:61], v[68:71]  // 0031b0
	s_add_u32 m0, 0x300, s58  // 0031b8
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0031c0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[62:63], v[68:71]  // 0031c8
	ds_read_b128 a[124:127], v58 offset:17088  // 0031d0
	v_mul_f32_e32 v4, v236, v189  // 0031d8
	v_mov_b32_e32 v5, v4  // 0031dc
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[56:57], 0  // 0031e0
	buffer_load_dwordx4 a[40:43], v40, s[8:11], 0 offen  // 0031e8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[58:59], v[72:75]  // 0031f0
	buffer_load_dword v189, v240, s[20:23], 0 offen  // 0031f8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[60:61], v[72:75]  // 003200
	buffer_load_dwordx4 a[44:47], v41, s[8:11], 0 offen  // 003208
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[62:63], v[72:75]  // 003210
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 003218
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 003220
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 003228
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 003230
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[0:1], a[64:65], 0  // 003238
	s_add_u32 m0, 0x400, s58  // 003240
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003248
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[2:3], a[66:67], v[76:79]  // 003250
	ds_read_b128 a[128:131], v58 offset:17536  // 003258
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[4:5], a[68:69], v[76:79]  // 003260
	s_add_u32 m0, 0x500, s58  // 003268
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003270
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[6:7], a[70:71], v[76:79]  // 003278
	ds_read_b128 a[132:135], v58 offset:17600  // 003280
	v_mul_f32_e32 v4, v236, v190  // 003288
	v_mov_b32_e32 v5, v4  // 00328c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[8:9], a[64:65], 0  // 003290
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[10:11], a[66:67], v[80:83]  // 003298
	buffer_load_dword v190, v241, s[20:23], 0 offen  // 0032a0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[12:13], a[68:69], v[80:83]  // 0032a8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[14:15], a[70:71], v[80:83]  // 0032b0
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 0032b8
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 0032c0
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 0032c8
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 0032d0
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[0:1], a[72:73], 0  // 0032d8
	s_add_u32 m0, 0x600, s58  // 0032e0
	buffer_load_dword v48, s[4:7], 0 offen lds  // 0032e8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[2:3], a[74:75], v[84:87]  // 0032f0
	ds_read_b128 a[136:139], v58 offset:18048  // 0032f8
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[4:5], a[76:77], v[84:87]  // 003300
	s_add_u32 m0, 0x700, s58  // 003308
	buffer_load_dword v49, s[4:7], 0 offen lds  // 003310
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[6:7], a[78:79], v[84:87]  // 003318
	ds_read_b128 a[140:143], v58 offset:18112  // 003320
	v_mul_f32_e32 v4, v236, v191  // 003328
	v_mov_b32_e32 v5, v4  // 00332c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[8:9], a[72:73], 0  // 003330
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[10:11], a[74:75], v[88:91]  // 003338
	buffer_load_dword v191, v242, s[20:23], 0 offen  // 003340
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[12:13], a[76:77], v[88:91]  // 003348
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[14:15], a[78:79], v[88:91]  // 003350
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 003358
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 003360
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 003368
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 003370
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[0:1], a[80:81], 0  // 003378
	s_add_u32 m0, 0x800, s58  // 003380
	buffer_load_dword v50, s[4:7], 0 offen lds  // 003388
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[2:3], a[82:83], v[92:95]  // 003390
	ds_read_b128 a[144:147], v58 offset:18560  // 003398
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[4:5], a[84:85], v[92:95]  // 0033a0
	s_add_u32 m0, 0x900, s58  // 0033a8
	buffer_load_dword v51, s[4:7], 0 offen lds  // 0033b0
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[6:7], a[86:87], v[92:95]  // 0033b8
	ds_read_b128 a[148:151], v58 offset:18624  // 0033c0
	v_mul_f32_e32 v4, v236, v192  // 0033c8
	v_mov_b32_e32 v5, v4  // 0033cc
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[8:9], a[80:81], 0  // 0033d0
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[10:11], a[82:83], v[96:99]  // 0033d8
	buffer_load_dword v192, v243, s[20:23], 0 offen  // 0033e0
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[12:13], a[84:85], v[96:99]  // 0033e8
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[14:15], a[86:87], v[96:99]  // 0033f0
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 0033f8
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 003400
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 003408
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 003410
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[0:1], a[88:89], 0  // 003418
	s_add_u32 m0, 0xa00, s58  // 003420
	buffer_load_dword v52, s[4:7], 0 offen lds  // 003428
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[2:3], a[90:91], v[100:103]  // 003430
	ds_read_b128 a[152:155], v58 offset:19072  // 003438
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[4:5], a[92:93], v[100:103]  // 003440
	s_add_u32 m0, 0xb00, s58  // 003448
	buffer_load_dword v53, s[4:7], 0 offen lds  // 003450
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[6:7], a[94:95], v[100:103]  // 003458
	ds_read_b128 a[156:159], v58 offset:19136  // 003460
	v_mul_f32_e32 v4, v236, v193  // 003468
	v_mov_b32_e32 v5, v4  // 00346c
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[8:9], a[88:89], 0  // 003470
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[10:11], a[90:91], v[104:107]  // 003478
	buffer_load_dword v193, v244, s[20:23], 0 offen  // 003480
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[12:13], a[92:93], v[104:107]  // 003488
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[14:15], a[94:95], v[104:107]  // 003490
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 003498
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 0034a0
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 0034a8
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 0034b0
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[0:1], a[96:97], 0  // 0034b8
	s_add_u32 m0, 0xc00, s58  // 0034c0
	buffer_load_dword v54, s[4:7], 0 offen lds  // 0034c8
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[2:3], a[98:99], v[108:111]  // 0034d0
	ds_read_b128 a[160:163], v58 offset:19584  // 0034d8
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[4:5], a[100:101], v[108:111]  // 0034e0
	s_add_u32 m0, 0xd00, s58  // 0034e8
	buffer_load_dword v55, s[4:7], 0 offen lds  // 0034f0
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[6:7], a[102:103], v[108:111]  // 0034f8
	ds_read_b128 a[164:167], v58 offset:19648  // 003500
	v_mul_f32_e32 v4, v236, v194  // 003508
	v_mov_b32_e32 v5, v4  // 00350c
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[8:9], a[96:97], 0  // 003510
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[10:11], a[98:99], v[112:115]  // 003518
	buffer_load_dword v194, v245, s[20:23], 0 offen  // 003520
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[12:13], a[100:101], v[112:115]  // 003528
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[14:15], a[102:103], v[112:115]  // 003530
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 003538
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 003540
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 003548
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 003550
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[0:1], a[104:105], 0  // 003558
	s_add_u32 m0, 0xe00, s58  // 003560
	buffer_load_dword v56, s[4:7], 0 offen lds  // 003568
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[2:3], a[106:107], v[116:119]  // 003570
	ds_read_b128 a[168:171], v58 offset:20096  // 003578
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[4:5], a[108:109], v[116:119]  // 003580
	s_add_u32 m0, 0xf00, s58  // 003588
	buffer_load_dword v57, s[4:7], 0 offen lds  // 003590
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[6:7], a[110:111], v[116:119]  // 003598
	s_add_u32 s50, 0x200, s42  // 0035c8
	s_cmp_lt_u32 s50, s43  // 0035d0
	s_cselect_b32 s54, s54, 0  // 0035d4
	ds_read_b128 a[172:175], v58 offset:20160  // 0035a0
	v_mul_f32_e32 v4, v236, v195  // 0035a8
	v_mov_b32_e32 v5, v4  // 0035ac
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[8:9], a[104:105], 0  // 0035b0
	s_add_u32 s50, 0x180, s42  // 0035d8
	s_cmp_lt_u32 s50, s43  // 0035e0
	s_cselect_b32 s55, s55, 0  // 0035e4
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[10:11], a[106:107], v[120:123]  // 0035b8
	buffer_load_dword v195, v246, s[20:23], 0 offen  // 0035c0
	s_add_u32 s50, 0x200, s42  // 0035e8
	s_cmp_lt_u32 s50, s43  // 0035f0
	s_cselect_b32 s56, s56, 0  // 0035f4
	s_add_u32 s50, 0x180, s42  // 0035f8
	s_cmp_lt_u32 s50, s43  // 003600
	s_cselect_b32 s57, s57, 0  // 003604
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[12:13], a[108:109], v[120:123]  // 003608
	s_add_u32 s4, s54, s4  // 003620
	s_addc_u32 s5, 0, s5  // 003624
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[14:15], a[110:111], v[120:123]  // 003610
	buffer_load_dword v238, v255, s[24:27], 0 offen  // 003618
	s_sub_u32 s6, s6, s54  // 003628
	s_add_u32 s8, s55, s8  // 00362c
	s_addc_u32 s9, 0, s9  // 003630
	s_sub_u32 s10, s10, s55  // 003634
	s_add_u32 s20, s56, s20  // 003638
	s_addc_u32 s21, 0, s21  // 00363c
	s_add_u32 s24, s57, s24  // 003640
	s_addc_u32 s25, 0, s25  // 003644
	s_sub_u32 s26, s26, s57  // 003648
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 00364c
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 003654
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 00365c
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 003664
	s_addk_i32 s42, 0x80  // 00366c
	s_cmp_lt_i32 s42, s43  // 003670
	s_cbranch_scc0 L_52b0  // 003674
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 00367c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[112:113], 0  // 003680
	s_add_u32 m0, 0, s59  // 003688
	buffer_load_dword v42, s[4:7], 0 offen lds  // 00368c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[114:115], v[60:63]  // 003694
	ds_read_b128 a[48:51], v58 offset:33024  // 00369c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[116:117], v[60:63]  // 0036a4
	s_add_u32 m0, 0x100, s59  // 0036ac
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0036b4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[118:119], v[60:63]  // 0036bc
	ds_read_b128 a[52:55], v58 offset:33088  // 0036c4
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v237, v196  // 0036cc
	v_mov_b32_e32 v5, v4  // 0036d0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[112:113], 0  // 0036d4
	buffer_load_dwordx4 a[0:3], v38, s[8:11], 0 offen  // 0036dc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[114:115], v[64:67]  // 0036e4
	buffer_load_dword v196, v239, s[20:23], 0 offen  // 0036ec
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[116:117], v[64:67]  // 0036f4
	buffer_load_dwordx4 a[4:7], v39, s[8:11], 0 offen  // 0036fc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[118:119], v[64:67]  // 003704
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 00370c
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 003714
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 00371c
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 003724
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[120:121], 0  // 00372c
	s_add_u32 m0, 0x200, s59  // 003734
	buffer_load_dword v44, s[4:7], 0 offen lds  // 00373c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[122:123], v[68:71]  // 003744
	ds_read_b128 a[56:59], v58 offset:33536  // 00374c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[124:125], v[68:71]  // 003754
	s_add_u32 m0, 0x300, s59  // 00375c
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003764
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[126:127], v[68:71]  // 00376c
	ds_read_b128 a[60:63], v58 offset:33600  // 003774
	v_mul_f32_e32 v4, v237, v197  // 00377c
	v_mov_b32_e32 v5, v4  // 003780
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[120:121], 0  // 003784
	buffer_load_dwordx4 a[8:11], v40, s[8:11], 0 offen  // 00378c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[122:123], v[72:75]  // 003794
	buffer_load_dword v197, v240, s[20:23], 0 offen  // 00379c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[124:125], v[72:75]  // 0037a4
	buffer_load_dwordx4 a[12:15], v41, s[8:11], 0 offen  // 0037ac
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[126:127], v[72:75]  // 0037b4
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 0037bc
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 0037c4
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 0037cc
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 0037d4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[16:17], a[128:129], 0  // 0037dc
	s_add_u32 m0, 0x400, s59  // 0037e4
	buffer_load_dword v46, s[4:7], 0 offen lds  // 0037ec
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[18:19], a[130:131], v[76:79]  // 0037f4
	ds_read_b128 a[64:67], v58 offset:34048  // 0037fc
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[20:21], a[132:133], v[76:79]  // 003804
	s_add_u32 m0, 0x500, s59  // 00380c
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003814
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[22:23], a[134:135], v[76:79]  // 00381c
	ds_read_b128 a[68:71], v58 offset:34112  // 003824
	v_mul_f32_e32 v4, v237, v198  // 00382c
	v_mov_b32_e32 v5, v4  // 003830
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[24:25], a[128:129], 0  // 003834
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[26:27], a[130:131], v[80:83]  // 00383c
	buffer_load_dword v198, v241, s[20:23], 0 offen  // 003844
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[28:29], a[132:133], v[80:83]  // 00384c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[30:31], a[134:135], v[80:83]  // 003854
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 00385c
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 003864
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 00386c
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 003874
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[16:17], a[136:137], 0  // 00387c
	s_add_u32 m0, 0x600, s59  // 003884
	buffer_load_dword v48, s[4:7], 0 offen lds  // 00388c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[18:19], a[138:139], v[84:87]  // 003894
	ds_read_b128 a[72:75], v58 offset:34560  // 00389c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[20:21], a[140:141], v[84:87]  // 0038a4
	s_add_u32 m0, 0x700, s59  // 0038ac
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0038b4
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[22:23], a[142:143], v[84:87]  // 0038bc
	ds_read_b128 a[76:79], v58 offset:34624  // 0038c4
	v_mul_f32_e32 v4, v237, v199  // 0038cc
	v_mov_b32_e32 v5, v4  // 0038d0
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[24:25], a[136:137], 0  // 0038d4
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[26:27], a[138:139], v[88:91]  // 0038dc
	buffer_load_dword v199, v242, s[20:23], 0 offen  // 0038e4
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[28:29], a[140:141], v[88:91]  // 0038ec
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[30:31], a[142:143], v[88:91]  // 0038f4
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 0038fc
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 003904
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 00390c
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 003914
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[16:17], a[144:145], 0  // 00391c
	s_add_u32 m0, 0x800, s59  // 003924
	buffer_load_dword v50, s[4:7], 0 offen lds  // 00392c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[18:19], a[146:147], v[92:95]  // 003934
	ds_read_b128 a[80:83], v58 offset:35072  // 00393c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[20:21], a[148:149], v[92:95]  // 003944
	s_add_u32 m0, 0x900, s59  // 00394c
	buffer_load_dword v51, s[4:7], 0 offen lds  // 003954
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[22:23], a[150:151], v[92:95]  // 00395c
	ds_read_b128 a[84:87], v58 offset:35136  // 003964
	v_mul_f32_e32 v4, v237, v200  // 00396c
	v_mov_b32_e32 v5, v4  // 003970
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[24:25], a[144:145], 0  // 003974
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[26:27], a[146:147], v[96:99]  // 00397c
	buffer_load_dword v200, v243, s[20:23], 0 offen  // 003984
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[28:29], a[148:149], v[96:99]  // 00398c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[30:31], a[150:151], v[96:99]  // 003994
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 00399c
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 0039a4
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 0039ac
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 0039b4
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[16:17], a[152:153], 0  // 0039bc
	s_add_u32 m0, 0xa00, s59  // 0039c4
	buffer_load_dword v52, s[4:7], 0 offen lds  // 0039cc
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[18:19], a[154:155], v[100:103]  // 0039d4
	ds_read_b128 a[88:91], v58 offset:35584  // 0039dc
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[20:21], a[156:157], v[100:103]  // 0039e4
	s_add_u32 m0, 0xb00, s59  // 0039ec
	buffer_load_dword v53, s[4:7], 0 offen lds  // 0039f4
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[22:23], a[158:159], v[100:103]  // 0039fc
	ds_read_b128 a[92:95], v58 offset:35648  // 003a04
	v_mul_f32_e32 v4, v237, v201  // 003a0c
	v_mov_b32_e32 v5, v4  // 003a10
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[24:25], a[152:153], 0  // 003a14
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[26:27], a[154:155], v[104:107]  // 003a1c
	buffer_load_dword v201, v244, s[20:23], 0 offen  // 003a24
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[28:29], a[156:157], v[104:107]  // 003a2c
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[30:31], a[158:159], v[104:107]  // 003a34
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 003a3c
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 003a44
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 003a4c
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 003a54
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[16:17], a[160:161], 0  // 003a5c
	s_add_u32 m0, 0xc00, s59  // 003a64
	buffer_load_dword v54, s[4:7], 0 offen lds  // 003a6c
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[18:19], a[162:163], v[108:111]  // 003a74
	ds_read_b128 a[96:99], v58 offset:36096  // 003a7c
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[20:21], a[164:165], v[108:111]  // 003a84
	s_add_u32 m0, 0xd00, s59  // 003a8c
	buffer_load_dword v55, s[4:7], 0 offen lds  // 003a94
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[22:23], a[166:167], v[108:111]  // 003a9c
	ds_read_b128 a[100:103], v58 offset:36160  // 003aa4
	v_mul_f32_e32 v4, v237, v202  // 003aac
	v_mov_b32_e32 v5, v4  // 003ab0
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[24:25], a[160:161], 0  // 003ab4
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[26:27], a[162:163], v[112:115]  // 003abc
	buffer_load_dword v202, v245, s[20:23], 0 offen  // 003ac4
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[28:29], a[164:165], v[112:115]  // 003acc
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[30:31], a[166:167], v[112:115]  // 003ad4
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 003adc
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 003ae4
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 003aec
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 003af4
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[16:17], a[168:169], 0  // 003afc
	s_add_u32 m0, 0xe00, s59  // 003b04
	buffer_load_dword v56, s[4:7], 0 offen lds  // 003b0c
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[18:19], a[170:171], v[116:119]  // 003b14
	ds_read_b128 a[104:107], v58 offset:36608  // 003b1c
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[20:21], a[172:173], v[116:119]  // 003b24
	s_add_u32 m0, 0xf00, s59  // 003b2c
	buffer_load_dword v57, s[4:7], 0 offen lds  // 003b34
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[22:23], a[174:175], v[116:119]  // 003b3c
	s_add_u32 s50, 0x200, s42  // 003b6c
	s_cmp_lt_u32 s50, s43  // 003b74
	s_cselect_b32 s54, s54, 0  // 003b78
	ds_read_b128 a[108:111], v58 offset:36672  // 003b44
	v_mul_f32_e32 v4, v237, v203  // 003b4c
	v_mov_b32_e32 v5, v4  // 003b50
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[24:25], a[168:169], 0  // 003b54
	s_add_u32 s50, 0x180, s42  // 003b7c
	s_cmp_lt_u32 s50, s43  // 003b84
	s_cselect_b32 s55, s55, 0  // 003b88
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[26:27], a[170:171], v[120:123]  // 003b5c
	buffer_load_dword v203, v246, s[20:23], 0 offen  // 003b64
	s_add_u32 s50, 0x200, s42  // 003b8c
	s_cmp_lt_u32 s50, s43  // 003b94
	s_cselect_b32 s56, s56, 0  // 003b98
	s_add_u32 s50, 0x180, s42  // 003b9c
	s_cmp_lt_u32 s50, s43  // 003ba4
	s_cselect_b32 s57, s57, 0  // 003ba8
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[28:29], a[172:173], v[120:123]  // 003bac
	s_add_u32 s4, s54, s4  // 003bc4
	s_addc_u32 s5, 0, s5  // 003bc8
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[30:31], a[174:175], v[120:123]  // 003bb4
	buffer_load_dword v236, v255, s[24:27], 0 offen  // 003bbc
	s_sub_u32 s6, s6, s54  // 003bcc
	s_add_u32 s8, s55, s8  // 003bd0
	s_addc_u32 s9, 0, s9  // 003bd4
	s_sub_u32 s10, s10, s55  // 003bd8
	s_add_u32 s20, s56, s20  // 003bdc
	s_addc_u32 s21, 0, s21  // 003be0
	s_add_u32 s24, s57, s24  // 003be4
	s_addc_u32 s25, 0, s25  // 003be8
	s_sub_u32 s26, s26, s57  // 003bec
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 003bf0
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 003bf8
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 003c00
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 003c08
	s_addk_i32 s42, 0x80  // 003c10
	s_cmp_lt_i32 s42, s43  // 003c14
	s_cbranch_scc0 L_52b0  // 003c18
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 003c20
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[48:49], 0  // 003c24
	s_add_u32 m0, 0, s60  // 003c2c
	buffer_load_dword v42, s[4:7], 0 offen lds  // 003c30
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[50:51], v[60:63]  // 003c38
	ds_read_b128 a[112:115], v58  // 003c40
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[52:53], v[60:63]  // 003c48
	s_add_u32 m0, 0x100, s60  // 003c50
	buffer_load_dword v43, s[4:7], 0 offen lds  // 003c58
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[54:55], v[60:63]  // 003c60
	ds_read_b128 a[116:119], v58 offset:64  // 003c68
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v238, v204  // 003c70
	v_mov_b32_e32 v5, v4  // 003c74
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[48:49], 0  // 003c78
	buffer_load_dwordx4 a[16:19], v38, s[8:11], 0 offen  // 003c80
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[50:51], v[64:67]  // 003c88
	buffer_load_dword v204, v239, s[20:23], 0 offen  // 003c90
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[52:53], v[64:67]  // 003c98
	buffer_load_dwordx4 a[20:23], v39, s[8:11], 0 offen  // 003ca0
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[54:55], v[64:67]  // 003ca8
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 003cb0
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 003cb8
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 003cc0
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 003cc8
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[56:57], 0  // 003cd0
	s_add_u32 m0, 0x200, s60  // 003cd8
	buffer_load_dword v44, s[4:7], 0 offen lds  // 003ce0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[58:59], v[68:71]  // 003ce8
	ds_read_b128 a[120:123], v58 offset:512  // 003cf0
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[60:61], v[68:71]  // 003cf8
	s_add_u32 m0, 0x300, s60  // 003d00
	buffer_load_dword v45, s[4:7], 0 offen lds  // 003d08
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[62:63], v[68:71]  // 003d10
	ds_read_b128 a[124:127], v58 offset:576  // 003d18
	v_mul_f32_e32 v4, v238, v205  // 003d20
	v_mov_b32_e32 v5, v4  // 003d24
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[56:57], 0  // 003d28
	buffer_load_dwordx4 a[24:27], v40, s[8:11], 0 offen  // 003d30
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[58:59], v[72:75]  // 003d38
	buffer_load_dword v205, v240, s[20:23], 0 offen  // 003d40
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[60:61], v[72:75]  // 003d48
	buffer_load_dwordx4 a[28:31], v41, s[8:11], 0 offen  // 003d50
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[62:63], v[72:75]  // 003d58
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 003d60
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 003d68
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 003d70
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 003d78
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[32:33], a[64:65], 0  // 003d80
	s_add_u32 m0, 0x400, s60  // 003d88
	buffer_load_dword v46, s[4:7], 0 offen lds  // 003d90
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[34:35], a[66:67], v[76:79]  // 003d98
	ds_read_b128 a[128:131], v58 offset:1024  // 003da0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[36:37], a[68:69], v[76:79]  // 003da8
	s_add_u32 m0, 0x500, s60  // 003db0
	buffer_load_dword v47, s[4:7], 0 offen lds  // 003db8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[38:39], a[70:71], v[76:79]  // 003dc0
	ds_read_b128 a[132:135], v58 offset:1088  // 003dc8
	v_mul_f32_e32 v4, v238, v206  // 003dd0
	v_mov_b32_e32 v5, v4  // 003dd4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[40:41], a[64:65], 0  // 003dd8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[42:43], a[66:67], v[80:83]  // 003de0
	buffer_load_dword v206, v241, s[20:23], 0 offen  // 003de8
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[44:45], a[68:69], v[80:83]  // 003df0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[46:47], a[70:71], v[80:83]  // 003df8
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 003e00
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 003e08
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 003e10
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 003e18
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[32:33], a[72:73], 0  // 003e20
	s_add_u32 m0, 0x600, s60  // 003e28
	buffer_load_dword v48, s[4:7], 0 offen lds  // 003e30
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[34:35], a[74:75], v[84:87]  // 003e38
	ds_read_b128 a[136:139], v58 offset:1536  // 003e40
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[36:37], a[76:77], v[84:87]  // 003e48
	s_add_u32 m0, 0x700, s60  // 003e50
	buffer_load_dword v49, s[4:7], 0 offen lds  // 003e58
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[38:39], a[78:79], v[84:87]  // 003e60
	ds_read_b128 a[140:143], v58 offset:1600  // 003e68
	v_mul_f32_e32 v4, v238, v207  // 003e70
	v_mov_b32_e32 v5, v4  // 003e74
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[40:41], a[72:73], 0  // 003e78
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[42:43], a[74:75], v[88:91]  // 003e80
	buffer_load_dword v207, v242, s[20:23], 0 offen  // 003e88
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[44:45], a[76:77], v[88:91]  // 003e90
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[46:47], a[78:79], v[88:91]  // 003e98
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 003ea0
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 003ea8
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 003eb0
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 003eb8
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[32:33], a[80:81], 0  // 003ec0
	s_add_u32 m0, 0x800, s60  // 003ec8
	buffer_load_dword v50, s[4:7], 0 offen lds  // 003ed0
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[34:35], a[82:83], v[92:95]  // 003ed8
	ds_read_b128 a[144:147], v58 offset:2048  // 003ee0
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[36:37], a[84:85], v[92:95]  // 003ee8
	s_add_u32 m0, 0x900, s60  // 003ef0
	buffer_load_dword v51, s[4:7], 0 offen lds  // 003ef8
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[38:39], a[86:87], v[92:95]  // 003f00
	ds_read_b128 a[148:151], v58 offset:2112  // 003f08
	v_mul_f32_e32 v4, v238, v208  // 003f10
	v_mov_b32_e32 v5, v4  // 003f14
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[40:41], a[80:81], 0  // 003f18
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[42:43], a[82:83], v[96:99]  // 003f20
	buffer_load_dword v208, v243, s[20:23], 0 offen  // 003f28
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[44:45], a[84:85], v[96:99]  // 003f30
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[46:47], a[86:87], v[96:99]  // 003f38
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 003f40
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 003f48
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 003f50
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 003f58
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[32:33], a[88:89], 0  // 003f60
	s_add_u32 m0, 0xa00, s60  // 003f68
	buffer_load_dword v52, s[4:7], 0 offen lds  // 003f70
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[34:35], a[90:91], v[100:103]  // 003f78
	ds_read_b128 a[152:155], v58 offset:2560  // 003f80
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[36:37], a[92:93], v[100:103]  // 003f88
	s_add_u32 m0, 0xb00, s60  // 003f90
	buffer_load_dword v53, s[4:7], 0 offen lds  // 003f98
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[38:39], a[94:95], v[100:103]  // 003fa0
	ds_read_b128 a[156:159], v58 offset:2624  // 003fa8
	v_mul_f32_e32 v4, v238, v209  // 003fb0
	v_mov_b32_e32 v5, v4  // 003fb4
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[40:41], a[88:89], 0  // 003fb8
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[42:43], a[90:91], v[104:107]  // 003fc0
	buffer_load_dword v209, v244, s[20:23], 0 offen  // 003fc8
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[44:45], a[92:93], v[104:107]  // 003fd0
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[46:47], a[94:95], v[104:107]  // 003fd8
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 003fe0
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 003fe8
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 003ff0
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 003ff8
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[32:33], a[96:97], 0  // 004000
	s_add_u32 m0, 0xc00, s60  // 004008
	buffer_load_dword v54, s[4:7], 0 offen lds  // 004010
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[34:35], a[98:99], v[108:111]  // 004018
	ds_read_b128 a[160:163], v58 offset:3072  // 004020
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[36:37], a[100:101], v[108:111]  // 004028
	s_add_u32 m0, 0xd00, s60  // 004030
	buffer_load_dword v55, s[4:7], 0 offen lds  // 004038
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[38:39], a[102:103], v[108:111]  // 004040
	ds_read_b128 a[164:167], v58 offset:3136  // 004048
	v_mul_f32_e32 v4, v238, v210  // 004050
	v_mov_b32_e32 v5, v4  // 004054
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[40:41], a[96:97], 0  // 004058
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[42:43], a[98:99], v[112:115]  // 004060
	buffer_load_dword v210, v245, s[20:23], 0 offen  // 004068
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[44:45], a[100:101], v[112:115]  // 004070
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[46:47], a[102:103], v[112:115]  // 004078
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 004080
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 004088
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 004090
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 004098
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[32:33], a[104:105], 0  // 0040a0
	s_add_u32 m0, 0xe00, s60  // 0040a8
	buffer_load_dword v56, s[4:7], 0 offen lds  // 0040b0
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[34:35], a[106:107], v[116:119]  // 0040b8
	ds_read_b128 a[168:171], v58 offset:3584  // 0040c0
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[36:37], a[108:109], v[116:119]  // 0040c8
	s_add_u32 m0, 0xf00, s60  // 0040d0
	buffer_load_dword v57, s[4:7], 0 offen lds  // 0040d8
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[38:39], a[110:111], v[116:119]  // 0040e0
	s_add_u32 s50, 0x200, s42  // 004110
	s_cmp_lt_u32 s50, s43  // 004118
	s_cselect_b32 s54, s54, 0  // 00411c
	ds_read_b128 a[172:175], v58 offset:3648  // 0040e8
	v_mul_f32_e32 v4, v238, v211  // 0040f0
	v_mov_b32_e32 v5, v4  // 0040f4
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[40:41], a[104:105], 0  // 0040f8
	s_add_u32 s50, 0x180, s42  // 004120
	s_cmp_lt_u32 s50, s43  // 004128
	s_cselect_b32 s55, s55, 0  // 00412c
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[42:43], a[106:107], v[120:123]  // 004100
	buffer_load_dword v211, v246, s[20:23], 0 offen  // 004108
	s_add_u32 s50, 0x200, s42  // 004130
	s_cmp_lt_u32 s50, s43  // 004138
	s_cselect_b32 s56, s56, 0  // 00413c
	s_add_u32 s50, 0x180, s42  // 004140
	s_cmp_lt_u32 s50, s43  // 004148
	s_cselect_b32 s57, s57, 0  // 00414c
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[44:45], a[108:109], v[120:123]  // 004150
	s_add_u32 s4, s54, s4  // 004168
	s_addc_u32 s5, 0, s5  // 00416c
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[46:47], a[110:111], v[120:123]  // 004158
	buffer_load_dword v237, v255, s[24:27], 0 offen  // 004160
	s_sub_u32 s6, s6, s54  // 004170
	s_add_u32 s8, s55, s8  // 004174
	s_addc_u32 s9, 0, s9  // 004178
	s_sub_u32 s10, s10, s55  // 00417c
	s_add_u32 s20, s56, s20  // 004180
	s_addc_u32 s21, 0, s21  // 004184
	s_add_u32 s24, s57, s24  // 004188
	s_addc_u32 s25, 0, s25  // 00418c
	s_sub_u32 s26, s26, s57  // 004190
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 004194
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 00419c
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 0041a4
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 0041ac
	s_addk_i32 s42, 0x80  // 0041b4
	s_cmp_lt_i32 s42, s43  // 0041b8
	s_cbranch_scc0 L_52b0  // 0041bc
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 0041c4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[0:1], a[112:113], 0  // 0041c8
	s_add_u32 m0, 0, s58  // 0041d0
	buffer_load_dword v42, s[4:7], 0 offen lds  // 0041d4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[2:3], a[114:115], v[60:63]  // 0041dc
	ds_read_b128 a[48:51], v58 offset:16512  // 0041e4
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[4:5], a[116:117], v[60:63]  // 0041ec
	s_add_u32 m0, 0x100, s58  // 0041f4
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0041fc
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[6:7], a[118:119], v[60:63]  // 004204
	ds_read_b128 a[52:55], v58 offset:16576  // 00420c
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v236, v188  // 004214
	v_mov_b32_e32 v5, v4  // 004218
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[8:9], a[112:113], 0  // 00421c
	buffer_load_dwordx4 a[32:35], v38, s[8:11], 0 offen  // 004224
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[10:11], a[114:115], v[64:67]  // 00422c
	buffer_load_dword v188, v239, s[20:23], 0 offen  // 004234
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[12:13], a[116:117], v[64:67]  // 00423c
	buffer_load_dwordx4 a[36:39], v39, s[8:11], 0 offen  // 004244
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[14:15], a[118:119], v[64:67]  // 00424c
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 004254
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 00425c
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 004264
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 00426c
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[0:1], a[120:121], 0  // 004274
	s_add_u32 m0, 0x200, s58  // 00427c
	buffer_load_dword v44, s[4:7], 0 offen lds  // 004284
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[2:3], a[122:123], v[68:71]  // 00428c
	ds_read_b128 a[56:59], v58 offset:17024  // 004294
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[4:5], a[124:125], v[68:71]  // 00429c
	s_add_u32 m0, 0x300, s58  // 0042a4
	buffer_load_dword v45, s[4:7], 0 offen lds  // 0042ac
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[6:7], a[126:127], v[68:71]  // 0042b4
	ds_read_b128 a[60:63], v58 offset:17088  // 0042bc
	v_mul_f32_e32 v4, v236, v189  // 0042c4
	v_mov_b32_e32 v5, v4  // 0042c8
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[8:9], a[120:121], 0  // 0042cc
	buffer_load_dwordx4 a[40:43], v40, s[8:11], 0 offen  // 0042d4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[10:11], a[122:123], v[72:75]  // 0042dc
	buffer_load_dword v189, v240, s[20:23], 0 offen  // 0042e4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[12:13], a[124:125], v[72:75]  // 0042ec
	buffer_load_dwordx4 a[44:47], v41, s[8:11], 0 offen  // 0042f4
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[14:15], a[126:127], v[72:75]  // 0042fc
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 004304
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 00430c
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 004314
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 00431c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[0:1], a[128:129], 0  // 004324
	s_add_u32 m0, 0x400, s58  // 00432c
	buffer_load_dword v46, s[4:7], 0 offen lds  // 004334
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[2:3], a[130:131], v[76:79]  // 00433c
	ds_read_b128 a[64:67], v58 offset:17536  // 004344
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[4:5], a[132:133], v[76:79]  // 00434c
	s_add_u32 m0, 0x500, s58  // 004354
	buffer_load_dword v47, s[4:7], 0 offen lds  // 00435c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[6:7], a[134:135], v[76:79]  // 004364
	ds_read_b128 a[68:71], v58 offset:17600  // 00436c
	v_mul_f32_e32 v4, v236, v190  // 004374
	v_mov_b32_e32 v5, v4  // 004378
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[8:9], a[128:129], 0  // 00437c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[10:11], a[130:131], v[80:83]  // 004384
	buffer_load_dword v190, v241, s[20:23], 0 offen  // 00438c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[12:13], a[132:133], v[80:83]  // 004394
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[14:15], a[134:135], v[80:83]  // 00439c
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 0043a4
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 0043ac
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 0043b4
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 0043bc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[0:1], a[136:137], 0  // 0043c4
	s_add_u32 m0, 0x600, s58  // 0043cc
	buffer_load_dword v48, s[4:7], 0 offen lds  // 0043d4
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[2:3], a[138:139], v[84:87]  // 0043dc
	ds_read_b128 a[72:75], v58 offset:18048  // 0043e4
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[4:5], a[140:141], v[84:87]  // 0043ec
	s_add_u32 m0, 0x700, s58  // 0043f4
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0043fc
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[6:7], a[142:143], v[84:87]  // 004404
	ds_read_b128 a[76:79], v58 offset:18112  // 00440c
	v_mul_f32_e32 v4, v236, v191  // 004414
	v_mov_b32_e32 v5, v4  // 004418
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[8:9], a[136:137], 0  // 00441c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[10:11], a[138:139], v[88:91]  // 004424
	buffer_load_dword v191, v242, s[20:23], 0 offen  // 00442c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[12:13], a[140:141], v[88:91]  // 004434
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[14:15], a[142:143], v[88:91]  // 00443c
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 004444
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 00444c
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 004454
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 00445c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[0:1], a[144:145], 0  // 004464
	s_add_u32 m0, 0x800, s58  // 00446c
	buffer_load_dword v50, s[4:7], 0 offen lds  // 004474
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[2:3], a[146:147], v[92:95]  // 00447c
	ds_read_b128 a[80:83], v58 offset:18560  // 004484
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[4:5], a[148:149], v[92:95]  // 00448c
	s_add_u32 m0, 0x900, s58  // 004494
	buffer_load_dword v51, s[4:7], 0 offen lds  // 00449c
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[6:7], a[150:151], v[92:95]  // 0044a4
	ds_read_b128 a[84:87], v58 offset:18624  // 0044ac
	v_mul_f32_e32 v4, v236, v192  // 0044b4
	v_mov_b32_e32 v5, v4  // 0044b8
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[8:9], a[144:145], 0  // 0044bc
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[10:11], a[146:147], v[96:99]  // 0044c4
	buffer_load_dword v192, v243, s[20:23], 0 offen  // 0044cc
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[12:13], a[148:149], v[96:99]  // 0044d4
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[14:15], a[150:151], v[96:99]  // 0044dc
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 0044e4
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 0044ec
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 0044f4
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 0044fc
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[0:1], a[152:153], 0  // 004504
	s_add_u32 m0, 0xa00, s58  // 00450c
	buffer_load_dword v52, s[4:7], 0 offen lds  // 004514
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[2:3], a[154:155], v[100:103]  // 00451c
	ds_read_b128 a[88:91], v58 offset:19072  // 004524
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[4:5], a[156:157], v[100:103]  // 00452c
	s_add_u32 m0, 0xb00, s58  // 004534
	buffer_load_dword v53, s[4:7], 0 offen lds  // 00453c
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[6:7], a[158:159], v[100:103]  // 004544
	ds_read_b128 a[92:95], v58 offset:19136  // 00454c
	v_mul_f32_e32 v4, v236, v193  // 004554
	v_mov_b32_e32 v5, v4  // 004558
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[8:9], a[152:153], 0  // 00455c
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[10:11], a[154:155], v[104:107]  // 004564
	buffer_load_dword v193, v244, s[20:23], 0 offen  // 00456c
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[12:13], a[156:157], v[104:107]  // 004574
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[14:15], a[158:159], v[104:107]  // 00457c
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 004584
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 00458c
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 004594
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 00459c
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[0:1], a[160:161], 0  // 0045a4
	s_add_u32 m0, 0xc00, s58  // 0045ac
	buffer_load_dword v54, s[4:7], 0 offen lds  // 0045b4
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[2:3], a[162:163], v[108:111]  // 0045bc
	ds_read_b128 a[96:99], v58 offset:19584  // 0045c4
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[4:5], a[164:165], v[108:111]  // 0045cc
	s_add_u32 m0, 0xd00, s58  // 0045d4
	buffer_load_dword v55, s[4:7], 0 offen lds  // 0045dc
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[6:7], a[166:167], v[108:111]  // 0045e4
	ds_read_b128 a[100:103], v58 offset:19648  // 0045ec
	v_mul_f32_e32 v4, v236, v194  // 0045f4
	v_mov_b32_e32 v5, v4  // 0045f8
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[8:9], a[160:161], 0  // 0045fc
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[10:11], a[162:163], v[112:115]  // 004604
	buffer_load_dword v194, v245, s[20:23], 0 offen  // 00460c
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[12:13], a[164:165], v[112:115]  // 004614
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[14:15], a[166:167], v[112:115]  // 00461c
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 004624
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 00462c
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 004634
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 00463c
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[0:1], a[168:169], 0  // 004644
	s_add_u32 m0, 0xe00, s58  // 00464c
	buffer_load_dword v56, s[4:7], 0 offen lds  // 004654
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[2:3], a[170:171], v[116:119]  // 00465c
	ds_read_b128 a[104:107], v58 offset:20096  // 004664
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[4:5], a[172:173], v[116:119]  // 00466c
	s_add_u32 m0, 0xf00, s58  // 004674
	buffer_load_dword v57, s[4:7], 0 offen lds  // 00467c
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[6:7], a[174:175], v[116:119]  // 004684
	s_add_u32 s50, 0x200, s42  // 0046b4
	s_cmp_lt_u32 s50, s43  // 0046bc
	s_cselect_b32 s54, s54, 0  // 0046c0
	ds_read_b128 a[108:111], v58 offset:20160  // 00468c
	v_mul_f32_e32 v4, v236, v195  // 004694
	v_mov_b32_e32 v5, v4  // 004698
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[8:9], a[168:169], 0  // 00469c
	s_add_u32 s50, 0x180, s42  // 0046c4
	s_cmp_lt_u32 s50, s43  // 0046cc
	s_cselect_b32 s55, s55, 0  // 0046d0
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[10:11], a[170:171], v[120:123]  // 0046a4
	buffer_load_dword v195, v246, s[20:23], 0 offen  // 0046ac
	s_add_u32 s50, 0x200, s42  // 0046d4
	s_cmp_lt_u32 s50, s43  // 0046dc
	s_cselect_b32 s56, s56, 0  // 0046e0
	s_add_u32 s50, 0x180, s42  // 0046e4
	s_cmp_lt_u32 s50, s43  // 0046ec
	s_cselect_b32 s57, s57, 0  // 0046f0
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[12:13], a[172:173], v[120:123]  // 0046f4
	s_add_u32 s4, s54, s4  // 00470c
	s_addc_u32 s5, 0, s5  // 004710
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[14:15], a[174:175], v[120:123]  // 0046fc
	buffer_load_dword v238, v255, s[24:27], 0 offen  // 004704
	s_sub_u32 s6, s6, s54  // 004714
	s_add_u32 s8, s55, s8  // 004718
	s_addc_u32 s9, 0, s9  // 00471c
	s_sub_u32 s10, s10, s55  // 004720
	s_add_u32 s20, s56, s20  // 004724
	s_addc_u32 s21, 0, s21  // 004728
	s_add_u32 s24, s57, s24  // 00472c
	s_addc_u32 s25, 0, s25  // 004730
	s_sub_u32 s26, s26, s57  // 004734
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 004738
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 004740
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 004748
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 004750
	s_addk_i32 s42, 0x80  // 004758
	s_cmp_lt_i32 s42, s43  // 00475c
	s_cbranch_scc0 L_52b0  // 004760
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 004768
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[16:17], a[48:49], 0  // 00476c
	s_add_u32 m0, 0, s59  // 004774
	buffer_load_dword v42, s[4:7], 0 offen lds  // 004778
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[18:19], a[50:51], v[60:63]  // 004780
	ds_read_b128 a[112:115], v58 offset:33024  // 004788
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[20:21], a[52:53], v[60:63]  // 004790
	s_add_u32 m0, 0x100, s59  // 004798
	buffer_load_dword v43, s[4:7], 0 offen lds  // 0047a0
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[22:23], a[54:55], v[60:63]  // 0047a8
	ds_read_b128 a[116:119], v58 offset:33088  // 0047b0
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v237, v196  // 0047b8
	v_mov_b32_e32 v5, v4  // 0047bc
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[24:25], a[48:49], 0  // 0047c0
	buffer_load_dwordx4 a[0:3], v38, s[8:11], 0 offen  // 0047c8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[26:27], a[50:51], v[64:67]  // 0047d0
	buffer_load_dword v196, v239, s[20:23], 0 offen  // 0047d8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[28:29], a[52:53], v[64:67]  // 0047e0
	buffer_load_dwordx4 a[4:7], v39, s[8:11], 0 offen  // 0047e8
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[30:31], a[54:55], v[64:67]  // 0047f0
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 0047f8
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 004800
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 004808
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 004810
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[16:17], a[56:57], 0  // 004818
	s_add_u32 m0, 0x200, s59  // 004820
	buffer_load_dword v44, s[4:7], 0 offen lds  // 004828
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[18:19], a[58:59], v[68:71]  // 004830
	ds_read_b128 a[120:123], v58 offset:33536  // 004838
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[20:21], a[60:61], v[68:71]  // 004840
	s_add_u32 m0, 0x300, s59  // 004848
	buffer_load_dword v45, s[4:7], 0 offen lds  // 004850
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[22:23], a[62:63], v[68:71]  // 004858
	ds_read_b128 a[124:127], v58 offset:33600  // 004860
	v_mul_f32_e32 v4, v237, v197  // 004868
	v_mov_b32_e32 v5, v4  // 00486c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[24:25], a[56:57], 0  // 004870
	buffer_load_dwordx4 a[8:11], v40, s[8:11], 0 offen  // 004878
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[26:27], a[58:59], v[72:75]  // 004880
	buffer_load_dword v197, v240, s[20:23], 0 offen  // 004888
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[28:29], a[60:61], v[72:75]  // 004890
	buffer_load_dwordx4 a[12:15], v41, s[8:11], 0 offen  // 004898
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[30:31], a[62:63], v[72:75]  // 0048a0
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 0048a8
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 0048b0
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 0048b8
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 0048c0
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[16:17], a[64:65], 0  // 0048c8
	s_add_u32 m0, 0x400, s59  // 0048d0
	buffer_load_dword v46, s[4:7], 0 offen lds  // 0048d8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[18:19], a[66:67], v[76:79]  // 0048e0
	ds_read_b128 a[128:131], v58 offset:34048  // 0048e8
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[20:21], a[68:69], v[76:79]  // 0048f0
	s_add_u32 m0, 0x500, s59  // 0048f8
	buffer_load_dword v47, s[4:7], 0 offen lds  // 004900
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[22:23], a[70:71], v[76:79]  // 004908
	ds_read_b128 a[132:135], v58 offset:34112  // 004910
	v_mul_f32_e32 v4, v237, v198  // 004918
	v_mov_b32_e32 v5, v4  // 00491c
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[24:25], a[64:65], 0  // 004920
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[26:27], a[66:67], v[80:83]  // 004928
	buffer_load_dword v198, v241, s[20:23], 0 offen  // 004930
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[28:29], a[68:69], v[80:83]  // 004938
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[30:31], a[70:71], v[80:83]  // 004940
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 004948
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 004950
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 004958
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 004960
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[16:17], a[72:73], 0  // 004968
	s_add_u32 m0, 0x600, s59  // 004970
	buffer_load_dword v48, s[4:7], 0 offen lds  // 004978
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[18:19], a[74:75], v[84:87]  // 004980
	ds_read_b128 a[136:139], v58 offset:34560  // 004988
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[20:21], a[76:77], v[84:87]  // 004990
	s_add_u32 m0, 0x700, s59  // 004998
	buffer_load_dword v49, s[4:7], 0 offen lds  // 0049a0
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[22:23], a[78:79], v[84:87]  // 0049a8
	ds_read_b128 a[140:143], v58 offset:34624  // 0049b0
	v_mul_f32_e32 v4, v237, v199  // 0049b8
	v_mov_b32_e32 v5, v4  // 0049bc
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[24:25], a[72:73], 0  // 0049c0
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[26:27], a[74:75], v[88:91]  // 0049c8
	buffer_load_dword v199, v242, s[20:23], 0 offen  // 0049d0
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[28:29], a[76:77], v[88:91]  // 0049d8
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[30:31], a[78:79], v[88:91]  // 0049e0
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 0049e8
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 0049f0
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 0049f8
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 004a00
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[16:17], a[80:81], 0  // 004a08
	s_add_u32 m0, 0x800, s59  // 004a10
	buffer_load_dword v50, s[4:7], 0 offen lds  // 004a18
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[18:19], a[82:83], v[92:95]  // 004a20
	ds_read_b128 a[144:147], v58 offset:35072  // 004a28
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[20:21], a[84:85], v[92:95]  // 004a30
	s_add_u32 m0, 0x900, s59  // 004a38
	buffer_load_dword v51, s[4:7], 0 offen lds  // 004a40
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[22:23], a[86:87], v[92:95]  // 004a48
	ds_read_b128 a[148:151], v58 offset:35136  // 004a50
	v_mul_f32_e32 v4, v237, v200  // 004a58
	v_mov_b32_e32 v5, v4  // 004a5c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[24:25], a[80:81], 0  // 004a60
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[26:27], a[82:83], v[96:99]  // 004a68
	buffer_load_dword v200, v243, s[20:23], 0 offen  // 004a70
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[28:29], a[84:85], v[96:99]  // 004a78
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[30:31], a[86:87], v[96:99]  // 004a80
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 004a88
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 004a90
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 004a98
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 004aa0
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[16:17], a[88:89], 0  // 004aa8
	s_add_u32 m0, 0xa00, s59  // 004ab0
	buffer_load_dword v52, s[4:7], 0 offen lds  // 004ab8
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[18:19], a[90:91], v[100:103]  // 004ac0
	ds_read_b128 a[152:155], v58 offset:35584  // 004ac8
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[20:21], a[92:93], v[100:103]  // 004ad0
	s_add_u32 m0, 0xb00, s59  // 004ad8
	buffer_load_dword v53, s[4:7], 0 offen lds  // 004ae0
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[22:23], a[94:95], v[100:103]  // 004ae8
	ds_read_b128 a[156:159], v58 offset:35648  // 004af0
	v_mul_f32_e32 v4, v237, v201  // 004af8
	v_mov_b32_e32 v5, v4  // 004afc
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[24:25], a[88:89], 0  // 004b00
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[26:27], a[90:91], v[104:107]  // 004b08
	buffer_load_dword v201, v244, s[20:23], 0 offen  // 004b10
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[28:29], a[92:93], v[104:107]  // 004b18
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[30:31], a[94:95], v[104:107]  // 004b20
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 004b28
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 004b30
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 004b38
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 004b40
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[16:17], a[96:97], 0  // 004b48
	s_add_u32 m0, 0xc00, s59  // 004b50
	buffer_load_dword v54, s[4:7], 0 offen lds  // 004b58
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[18:19], a[98:99], v[108:111]  // 004b60
	ds_read_b128 a[160:163], v58 offset:36096  // 004b68
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[20:21], a[100:101], v[108:111]  // 004b70
	s_add_u32 m0, 0xd00, s59  // 004b78
	buffer_load_dword v55, s[4:7], 0 offen lds  // 004b80
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[22:23], a[102:103], v[108:111]  // 004b88
	ds_read_b128 a[164:167], v58 offset:36160  // 004b90
	v_mul_f32_e32 v4, v237, v202  // 004b98
	v_mov_b32_e32 v5, v4  // 004b9c
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[24:25], a[96:97], 0  // 004ba0
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[26:27], a[98:99], v[112:115]  // 004ba8
	buffer_load_dword v202, v245, s[20:23], 0 offen  // 004bb0
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[28:29], a[100:101], v[112:115]  // 004bb8
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[30:31], a[102:103], v[112:115]  // 004bc0
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 004bc8
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 004bd0
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 004bd8
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 004be0
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[16:17], a[104:105], 0  // 004be8
	s_add_u32 m0, 0xe00, s59  // 004bf0
	buffer_load_dword v56, s[4:7], 0 offen lds  // 004bf8
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[18:19], a[106:107], v[116:119]  // 004c00
	ds_read_b128 a[168:171], v58 offset:36608  // 004c08
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[20:21], a[108:109], v[116:119]  // 004c10
	s_add_u32 m0, 0xf00, s59  // 004c18
	buffer_load_dword v57, s[4:7], 0 offen lds  // 004c20
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[22:23], a[110:111], v[116:119]  // 004c28
	s_add_u32 s50, 0x200, s42  // 004c58
	s_cmp_lt_u32 s50, s43  // 004c60
	s_cselect_b32 s54, s54, 0  // 004c64
	ds_read_b128 a[172:175], v58 offset:36672  // 004c30
	v_mul_f32_e32 v4, v237, v203  // 004c38
	v_mov_b32_e32 v5, v4  // 004c3c
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[24:25], a[104:105], 0  // 004c40
	s_add_u32 s50, 0x180, s42  // 004c68
	s_cmp_lt_u32 s50, s43  // 004c70
	s_cselect_b32 s55, s55, 0  // 004c74
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[26:27], a[106:107], v[120:123]  // 004c48
	buffer_load_dword v203, v246, s[20:23], 0 offen  // 004c50
	s_add_u32 s50, 0x200, s42  // 004c78
	s_cmp_lt_u32 s50, s43  // 004c80
	s_cselect_b32 s56, s56, 0  // 004c84
	s_add_u32 s50, 0x180, s42  // 004c88
	s_cmp_lt_u32 s50, s43  // 004c90
	s_cselect_b32 s57, s57, 0  // 004c94
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[28:29], a[108:109], v[120:123]  // 004c98
	s_add_u32 s4, s54, s4  // 004cb0
	s_addc_u32 s5, 0, s5  // 004cb4
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[30:31], a[110:111], v[120:123]  // 004ca0
	buffer_load_dword v236, v255, s[24:27], 0 offen  // 004ca8
	s_sub_u32 s6, s6, s54  // 004cb8
	s_add_u32 s8, s55, s8  // 004cbc
	s_addc_u32 s9, 0, s9  // 004cc0
	s_sub_u32 s10, s10, s55  // 004cc4
	s_add_u32 s20, s56, s20  // 004cc8
	s_addc_u32 s21, 0, s21  // 004ccc
	s_add_u32 s24, s57, s24  // 004cd0
	s_addc_u32 s25, 0, s25  // 004cd4
	s_sub_u32 s26, s26, s57  // 004cd8
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 004cdc
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 004ce4
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 004cec
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 004cf4
	s_addk_i32 s42, 0x80  // 004cfc
	s_cmp_lt_i32 s42, s43  // 004d00
	s_cbranch_scc0 L_52b0  // 004d04
	s_waitcnt vmcnt(31) & lgkmcnt(0)
	s_barrier  // 004d0c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[32:33], a[112:113], 0  // 004d10
	s_add_u32 m0, 0, s60  // 004d18
	buffer_load_dword v42, s[4:7], 0 offen lds  // 004d1c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[34:35], a[114:115], v[60:63]  // 004d24
	ds_read_b128 a[48:51], v58  // 004d2c
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[36:37], a[116:117], v[60:63]  // 004d34
	s_add_u32 m0, 0x100, s60  // 004d3c
	buffer_load_dword v43, s[4:7], 0 offen lds  // 004d44
	v_mfma_f32_16x16x32_fp8_fp8 v[60:63], a[38:39], a[118:119], v[60:63]  // 004d4c
	ds_read_b128 a[52:55], v58 offset:64  // 004d54
	s_waitcnt vmcnt(31)
	v_mul_f32_e32 v4, v238, v204  // 004d5c
	v_mov_b32_e32 v5, v4  // 004d60
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[40:41], a[112:113], 0  // 004d64
	buffer_load_dwordx4 a[16:19], v38, s[8:11], 0 offen  // 004d6c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[42:43], a[114:115], v[64:67]  // 004d74
	buffer_load_dword v204, v239, s[20:23], 0 offen  // 004d7c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[44:45], a[116:117], v[64:67]  // 004d84
	buffer_load_dwordx4 a[20:23], v39, s[8:11], 0 offen  // 004d8c
	v_mfma_f32_16x16x32_fp8_fp8 v[64:67], a[46:47], a[118:119], v[64:67]  // 004d94
	s_nop 0
	v_pk_fma_f32 v[124:125], v[4:5], v[60:61], v[124:125]  // 004d9c
	v_pk_fma_f32 v[126:127], v[4:5], v[62:63], v[126:127]  // 004da4
	v_pk_fma_f32 v[128:129], v[4:5], v[64:65], v[128:129]  // 004dac
	v_pk_fma_f32 v[130:131], v[4:5], v[66:67], v[130:131]  // 004db4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[32:33], a[120:121], 0  // 004dbc
	s_add_u32 m0, 0x200, s60  // 004dc4
	buffer_load_dword v44, s[4:7], 0 offen lds  // 004dcc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[34:35], a[122:123], v[68:71]  // 004dd4
	ds_read_b128 a[56:59], v58 offset:512  // 004ddc
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[36:37], a[124:125], v[68:71]  // 004de4
	s_add_u32 m0, 0x300, s60  // 004dec
	buffer_load_dword v45, s[4:7], 0 offen lds  // 004df4
	v_mfma_f32_16x16x32_fp8_fp8 v[68:71], a[38:39], a[126:127], v[68:71]  // 004dfc
	ds_read_b128 a[60:63], v58 offset:576  // 004e04
	v_mul_f32_e32 v4, v238, v205  // 004e0c
	v_mov_b32_e32 v5, v4  // 004e10
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[40:41], a[120:121], 0  // 004e14
	buffer_load_dwordx4 a[24:27], v40, s[8:11], 0 offen  // 004e1c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[42:43], a[122:123], v[72:75]  // 004e24
	buffer_load_dword v205, v240, s[20:23], 0 offen  // 004e2c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[44:45], a[124:125], v[72:75]  // 004e34
	buffer_load_dwordx4 a[28:31], v41, s[8:11], 0 offen  // 004e3c
	v_mfma_f32_16x16x32_fp8_fp8 v[72:75], a[46:47], a[126:127], v[72:75]  // 004e44
	s_nop 0
	v_pk_fma_f32 v[132:133], v[4:5], v[68:69], v[132:133]  // 004e4c
	v_pk_fma_f32 v[134:135], v[4:5], v[70:71], v[134:135]  // 004e54
	v_pk_fma_f32 v[136:137], v[4:5], v[72:73], v[136:137]  // 004e5c
	v_pk_fma_f32 v[138:139], v[4:5], v[74:75], v[138:139]  // 004e64
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[32:33], a[128:129], 0  // 004e6c
	s_add_u32 m0, 0x400, s60  // 004e74
	buffer_load_dword v46, s[4:7], 0 offen lds  // 004e7c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[34:35], a[130:131], v[76:79]  // 004e84
	ds_read_b128 a[64:67], v58 offset:1024  // 004e8c
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[36:37], a[132:133], v[76:79]  // 004e94
	s_add_u32 m0, 0x500, s60  // 004e9c
	buffer_load_dword v47, s[4:7], 0 offen lds  // 004ea4
	v_mfma_f32_16x16x32_fp8_fp8 v[76:79], a[38:39], a[134:135], v[76:79]  // 004eac
	ds_read_b128 a[68:71], v58 offset:1088  // 004eb4
	v_mul_f32_e32 v4, v238, v206  // 004ebc
	v_mov_b32_e32 v5, v4  // 004ec0
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[40:41], a[128:129], 0  // 004ec4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[42:43], a[130:131], v[80:83]  // 004ecc
	buffer_load_dword v206, v241, s[20:23], 0 offen  // 004ed4
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[44:45], a[132:133], v[80:83]  // 004edc
	v_mfma_f32_16x16x32_fp8_fp8 v[80:83], a[46:47], a[134:135], v[80:83]  // 004ee4
	s_nop 0
	v_pk_fma_f32 v[140:141], v[4:5], v[76:77], v[140:141]  // 004eec
	v_pk_fma_f32 v[142:143], v[4:5], v[78:79], v[142:143]  // 004ef4
	v_pk_fma_f32 v[144:145], v[4:5], v[80:81], v[144:145]  // 004efc
	v_pk_fma_f32 v[146:147], v[4:5], v[82:83], v[146:147]  // 004f04
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[32:33], a[136:137], 0  // 004f0c
	s_add_u32 m0, 0x600, s60  // 004f14
	buffer_load_dword v48, s[4:7], 0 offen lds  // 004f1c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[34:35], a[138:139], v[84:87]  // 004f24
	ds_read_b128 a[72:75], v58 offset:1536  // 004f2c
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[36:37], a[140:141], v[84:87]  // 004f34
	s_add_u32 m0, 0x700, s60  // 004f3c
	buffer_load_dword v49, s[4:7], 0 offen lds  // 004f44
	v_mfma_f32_16x16x32_fp8_fp8 v[84:87], a[38:39], a[142:143], v[84:87]  // 004f4c
	ds_read_b128 a[76:79], v58 offset:1600  // 004f54
	v_mul_f32_e32 v4, v238, v207  // 004f5c
	v_mov_b32_e32 v5, v4  // 004f60
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[40:41], a[136:137], 0  // 004f64
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[42:43], a[138:139], v[88:91]  // 004f6c
	buffer_load_dword v207, v242, s[20:23], 0 offen  // 004f74
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[44:45], a[140:141], v[88:91]  // 004f7c
	v_mfma_f32_16x16x32_fp8_fp8 v[88:91], a[46:47], a[142:143], v[88:91]  // 004f84
	s_nop 0
	v_pk_fma_f32 v[148:149], v[4:5], v[84:85], v[148:149]  // 004f8c
	v_pk_fma_f32 v[150:151], v[4:5], v[86:87], v[150:151]  // 004f94
	v_pk_fma_f32 v[152:153], v[4:5], v[88:89], v[152:153]  // 004f9c
	v_pk_fma_f32 v[154:155], v[4:5], v[90:91], v[154:155]  // 004fa4
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[32:33], a[144:145], 0  // 004fac
	s_add_u32 m0, 0x800, s60  // 004fb4
	buffer_load_dword v50, s[4:7], 0 offen lds  // 004fbc
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[34:35], a[146:147], v[92:95]  // 004fc4
	ds_read_b128 a[80:83], v58 offset:2048  // 004fcc
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[36:37], a[148:149], v[92:95]  // 004fd4
	s_add_u32 m0, 0x900, s60  // 004fdc
	buffer_load_dword v51, s[4:7], 0 offen lds  // 004fe4
	v_mfma_f32_16x16x32_fp8_fp8 v[92:95], a[38:39], a[150:151], v[92:95]  // 004fec
	ds_read_b128 a[84:87], v58 offset:2112  // 004ff4
	v_mul_f32_e32 v4, v238, v208  // 004ffc
	v_mov_b32_e32 v5, v4  // 005000
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[40:41], a[144:145], 0  // 005004
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[42:43], a[146:147], v[96:99]  // 00500c
	buffer_load_dword v208, v243, s[20:23], 0 offen  // 005014
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[44:45], a[148:149], v[96:99]  // 00501c
	v_mfma_f32_16x16x32_fp8_fp8 v[96:99], a[46:47], a[150:151], v[96:99]  // 005024
	s_nop 0
	v_pk_fma_f32 v[156:157], v[4:5], v[92:93], v[156:157]  // 00502c
	v_pk_fma_f32 v[158:159], v[4:5], v[94:95], v[158:159]  // 005034
	v_pk_fma_f32 v[160:161], v[4:5], v[96:97], v[160:161]  // 00503c
	v_pk_fma_f32 v[162:163], v[4:5], v[98:99], v[162:163]  // 005044
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[32:33], a[152:153], 0  // 00504c
	s_add_u32 m0, 0xa00, s60  // 005054
	buffer_load_dword v52, s[4:7], 0 offen lds  // 00505c
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[34:35], a[154:155], v[100:103]  // 005064
	ds_read_b128 a[88:91], v58 offset:2560  // 00506c
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[36:37], a[156:157], v[100:103]  // 005074
	s_add_u32 m0, 0xb00, s60  // 00507c
	buffer_load_dword v53, s[4:7], 0 offen lds  // 005084
	v_mfma_f32_16x16x32_fp8_fp8 v[100:103], a[38:39], a[158:159], v[100:103]  // 00508c
	ds_read_b128 a[92:95], v58 offset:2624  // 005094
	v_mul_f32_e32 v4, v238, v209  // 00509c
	v_mov_b32_e32 v5, v4  // 0050a0
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[40:41], a[152:153], 0  // 0050a4
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[42:43], a[154:155], v[104:107]  // 0050ac
	buffer_load_dword v209, v244, s[20:23], 0 offen  // 0050b4
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[44:45], a[156:157], v[104:107]  // 0050bc
	v_mfma_f32_16x16x32_fp8_fp8 v[104:107], a[46:47], a[158:159], v[104:107]  // 0050c4
	s_nop 0
	v_pk_fma_f32 v[164:165], v[4:5], v[100:101], v[164:165]  // 0050cc
	v_pk_fma_f32 v[166:167], v[4:5], v[102:103], v[166:167]  // 0050d4
	v_pk_fma_f32 v[168:169], v[4:5], v[104:105], v[168:169]  // 0050dc
	v_pk_fma_f32 v[170:171], v[4:5], v[106:107], v[170:171]  // 0050e4
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[32:33], a[160:161], 0  // 0050ec
	s_add_u32 m0, 0xc00, s60  // 0050f4
	buffer_load_dword v54, s[4:7], 0 offen lds  // 0050fc
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[34:35], a[162:163], v[108:111]  // 005104
	ds_read_b128 a[96:99], v58 offset:3072  // 00510c
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[36:37], a[164:165], v[108:111]  // 005114
	s_add_u32 m0, 0xd00, s60  // 00511c
	buffer_load_dword v55, s[4:7], 0 offen lds  // 005124
	v_mfma_f32_16x16x32_fp8_fp8 v[108:111], a[38:39], a[166:167], v[108:111]  // 00512c
	ds_read_b128 a[100:103], v58 offset:3136  // 005134
	v_mul_f32_e32 v4, v238, v210  // 00513c
	v_mov_b32_e32 v5, v4  // 005140
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[40:41], a[160:161], 0  // 005144
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[42:43], a[162:163], v[112:115]  // 00514c
	buffer_load_dword v210, v245, s[20:23], 0 offen  // 005154
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[44:45], a[164:165], v[112:115]  // 00515c
	v_mfma_f32_16x16x32_fp8_fp8 v[112:115], a[46:47], a[166:167], v[112:115]  // 005164
	s_nop 0
	v_pk_fma_f32 v[172:173], v[4:5], v[108:109], v[172:173]  // 00516c
	v_pk_fma_f32 v[174:175], v[4:5], v[110:111], v[174:175]  // 005174
	v_pk_fma_f32 v[176:177], v[4:5], v[112:113], v[176:177]  // 00517c
	v_pk_fma_f32 v[178:179], v[4:5], v[114:115], v[178:179]  // 005184
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[32:33], a[168:169], 0  // 00518c
	s_add_u32 m0, 0xe00, s60  // 005194
	buffer_load_dword v56, s[4:7], 0 offen lds  // 00519c
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[34:35], a[170:171], v[116:119]  // 0051a4
	ds_read_b128 a[104:107], v58 offset:3584  // 0051ac
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[36:37], a[172:173], v[116:119]  // 0051b4
	s_add_u32 m0, 0xf00, s60  // 0051bc
	buffer_load_dword v57, s[4:7], 0 offen lds  // 0051c4
	v_mfma_f32_16x16x32_fp8_fp8 v[116:119], a[38:39], a[174:175], v[116:119]  // 0051cc
	s_add_u32 s50, 0x200, s42  // 0051fc
	s_cmp_lt_u32 s50, s43  // 005204
	s_cselect_b32 s54, s54, 0  // 005208
	ds_read_b128 a[108:111], v58 offset:3648  // 0051d4
	v_mul_f32_e32 v4, v238, v211  // 0051dc
	v_mov_b32_e32 v5, v4  // 0051e0
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[40:41], a[168:169], 0  // 0051e4
	s_add_u32 s50, 0x180, s42  // 00520c
	s_cmp_lt_u32 s50, s43  // 005214
	s_cselect_b32 s55, s55, 0  // 005218
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[42:43], a[170:171], v[120:123]  // 0051ec
	buffer_load_dword v211, v246, s[20:23], 0 offen  // 0051f4
	s_add_u32 s50, 0x200, s42  // 00521c
	s_cmp_lt_u32 s50, s43  // 005224
	s_cselect_b32 s56, s56, 0  // 005228
	s_add_u32 s50, 0x180, s42  // 00522c
	s_cmp_lt_u32 s50, s43  // 005234
	s_cselect_b32 s57, s57, 0  // 005238
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[44:45], a[172:173], v[120:123]  // 00523c
	s_add_u32 s4, s54, s4  // 005254
	s_addc_u32 s5, 0, s5  // 005258
	v_mfma_f32_16x16x32_fp8_fp8 v[120:123], a[46:47], a[174:175], v[120:123]  // 005244
	buffer_load_dword v237, v255, s[24:27], 0 offen  // 00524c
	s_sub_u32 s6, s6, s54  // 00525c
	s_add_u32 s8, s55, s8  // 005260
	s_addc_u32 s9, 0, s9  // 005264
	s_sub_u32 s10, s10, s55  // 005268
	s_add_u32 s20, s56, s20  // 00526c
	s_addc_u32 s21, 0, s21  // 005270
	s_add_u32 s24, s57, s24  // 005274
	s_addc_u32 s25, 0, s25  // 005278
	s_sub_u32 s26, s26, s57  // 00527c
	v_pk_fma_f32 v[180:181], v[4:5], v[116:117], v[180:181]  // 005280
	v_pk_fma_f32 v[182:183], v[4:5], v[118:119], v[182:183]  // 005288
	v_pk_fma_f32 v[184:185], v[4:5], v[120:121], v[184:185]  // 005290
	v_pk_fma_f32 v[186:187], v[4:5], v[122:123], v[186:187]  // 005298
	s_addk_i32 s42, 0x80  // 0052a0
	s_cmp_lt_i32 s42, s43  // 0052a4
	s_cbranch_scc0 L_52b0  // 0052a8
	s_branch L_30d4  // 0052ac
L_52b0:
	s_cmp_eq_u32 s38, 1  // 0052b0
	s_cbranch_scc1 L_5a58  // 0052b4
	v_add_f32_e32 v124, v124, v12  // 0052b8
	v_add_f32_e32 v125, v125, v13  // 0052bc
	v_perm_b32 v60, v125, v124, s48  // 0052c0
	v_add_f32_e32 v126, v126, v14  // 0052c8
	v_add_f32_e32 v127, v127, v15  // 0052cc
	v_perm_b32 v61, v127, v126, s48  // 0052d0
	v_add_f32_e32 v128, v128, v16  // 0052d8
	v_add_f32_e32 v129, v129, v17  // 0052dc
	v_perm_b32 v62, v129, v128, s48  // 0052e0
	v_add_f32_e32 v130, v130, v18  // 0052e8
	v_add_f32_e32 v131, v131, v19  // 0052ec
	v_perm_b32 v63, v131, v130, s48  // 0052f0
	v_add_f32_e32 v132, v132, v12  // 0052f8
	v_add_f32_e32 v133, v133, v13  // 0052fc
	v_perm_b32 v64, v133, v132, s48  // 005300
	v_add_f32_e32 v134, v134, v14  // 005308
	v_add_f32_e32 v135, v135, v15  // 00530c
	v_perm_b32 v65, v135, v134, s48  // 005310
	v_add_f32_e32 v136, v136, v16  // 005318
	v_add_f32_e32 v137, v137, v17  // 00531c
	v_perm_b32 v66, v137, v136, s48  // 005320
	v_add_f32_e32 v138, v138, v18  // 005328
	v_add_f32_e32 v139, v139, v19  // 00532c
	v_perm_b32 v67, v139, v138, s48  // 005330
	v_add_f32_e32 v140, v140, v12  // 005338
	v_add_f32_e32 v141, v141, v13  // 00533c
	v_perm_b32 v68, v141, v140, s48  // 005340
	v_add_f32_e32 v142, v142, v14  // 005348
	v_add_f32_e32 v143, v143, v15  // 00534c
	v_perm_b32 v69, v143, v142, s48  // 005350
	v_add_f32_e32 v144, v144, v16  // 005358
	v_add_f32_e32 v145, v145, v17  // 00535c
	v_perm_b32 v70, v145, v144, s48  // 005360
	v_add_f32_e32 v146, v146, v18  // 005368
	v_add_f32_e32 v147, v147, v19  // 00536c
	v_perm_b32 v71, v147, v146, s48  // 005370
	v_add_f32_e32 v148, v148, v12  // 005378
	v_add_f32_e32 v149, v149, v13  // 00537c
	v_perm_b32 v72, v149, v148, s48  // 005380
	v_add_f32_e32 v150, v150, v14  // 005388
	v_add_f32_e32 v151, v151, v15  // 00538c
	v_perm_b32 v73, v151, v150, s48  // 005390
	v_add_f32_e32 v152, v152, v16  // 005398
	v_add_f32_e32 v153, v153, v17  // 00539c
	v_perm_b32 v74, v153, v152, s48  // 0053a0
	v_add_f32_e32 v154, v154, v18  // 0053a8
	v_add_f32_e32 v155, v155, v19  // 0053ac
	v_perm_b32 v75, v155, v154, s48  // 0053b0
	v_add_f32_e32 v156, v156, v12  // 0053b8
	v_add_f32_e32 v157, v157, v13  // 0053bc
	v_perm_b32 v76, v157, v156, s48  // 0053c0
	v_add_f32_e32 v158, v158, v14  // 0053c8
	v_add_f32_e32 v159, v159, v15  // 0053cc
	v_perm_b32 v77, v159, v158, s48  // 0053d0
	v_add_f32_e32 v160, v160, v16  // 0053d8
	v_add_f32_e32 v161, v161, v17  // 0053dc
	v_perm_b32 v78, v161, v160, s48  // 0053e0
	v_add_f32_e32 v162, v162, v18  // 0053e8
	v_add_f32_e32 v163, v163, v19  // 0053ec
	v_perm_b32 v79, v163, v162, s48  // 0053f0
	v_add_f32_e32 v164, v164, v12  // 0053f8
	v_add_f32_e32 v165, v165, v13  // 0053fc
	v_perm_b32 v80, v165, v164, s48  // 005400
	v_add_f32_e32 v166, v166, v14  // 005408
	v_add_f32_e32 v167, v167, v15  // 00540c
	v_perm_b32 v81, v167, v166, s48  // 005410
	v_add_f32_e32 v168, v168, v16  // 005418
	v_add_f32_e32 v169, v169, v17  // 00541c
	v_perm_b32 v82, v169, v168, s48  // 005420
	v_add_f32_e32 v170, v170, v18  // 005428
	v_add_f32_e32 v171, v171, v19  // 00542c
	v_perm_b32 v83, v171, v170, s48  // 005430
	v_add_f32_e32 v172, v172, v12  // 005438
	v_add_f32_e32 v173, v173, v13  // 00543c
	v_perm_b32 v84, v173, v172, s48  // 005440
	v_add_f32_e32 v174, v174, v14  // 005448
	v_add_f32_e32 v175, v175, v15  // 00544c
	v_perm_b32 v85, v175, v174, s48  // 005450
	v_add_f32_e32 v176, v176, v16  // 005458
	v_add_f32_e32 v177, v177, v17  // 00545c
	v_perm_b32 v86, v177, v176, s48  // 005460
	v_add_f32_e32 v178, v178, v18  // 005468
	v_add_f32_e32 v179, v179, v19  // 00546c
	v_perm_b32 v87, v179, v178, s48  // 005470
	v_add_f32_e32 v180, v180, v12  // 005478
	v_add_f32_e32 v181, v181, v13  // 00547c
	v_perm_b32 v88, v181, v180, s48  // 005480
	v_add_f32_e32 v182, v182, v14  // 005488
	v_add_f32_e32 v183, v183, v15  // 00548c
	v_perm_b32 v89, v183, v182, s48  // 005490
	v_add_f32_e32 v184, v184, v16  // 005498
	v_add_f32_e32 v185, v185, v17  // 00549c
	v_perm_b32 v90, v185, v184, s48  // 0054a0
	v_add_f32_e32 v186, v186, v18  // 0054a8
	v_add_f32_e32 v187, v187, v19  // 0054ac
	v_perm_b32 v91, v187, v186, s48  // 0054b0
	v_lshrrev_b32_e32 v4, 4, v0  // 0054b8
	v_mul_u32_u24_e32 v58, 34, v4  // 0054bc
	v_and_b32_e32 v4, 15, v0  // 0054c0
	v_mul_lo_u32 v5, 2, v4  // 0054c4
	v_add_u32_e32 v58, v5, v58  // 0054cc
	s_mul_i32 s50, s47, 0x110  // 0054d0
	v_add_u32_e32 v58, s50, v58  // 0054d8
	v_lshlrev_b32_e32 v58, 2, v58  // 0054dc
	v_lshrrev_b32_e32 v4, 1, v0  // 0054e0
	v_mul_u32_u24_e32 v42, 34, v4  // 0054e4
	v_and_b32_e32 v5, 1, v0  // 0054e8
	v_add_u32_e32 v42, v5, v42  // 0054ec
	s_mul_i32 s50, s47, 2  // 0054f0
	v_add_u32_e32 v42, s50, v42  // 0054f4
	v_lshlrev_b32_e32 v42, 2, v42  // 0054f8
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 0054fc
	s_barrier  // 005500
	ds_write_b64 v58, v[60:61]  // 005504
	ds_write_b64 v58, v[62:63] offset:544  // 00550c
	ds_write_b64 v58, v[64:65] offset:4352  // 005514
	ds_write_b64 v58, v[66:67] offset:4896  // 00551c
	ds_write_b64 v58, v[68:69] offset:8704  // 005524
	ds_write_b64 v58, v[70:71] offset:9248  // 00552c
	ds_write_b64 v58, v[72:73] offset:13056  // 005534
	ds_write_b64 v58, v[74:75] offset:13600  // 00553c
	ds_write_b64 v58, v[76:77] offset:17408  // 005544
	ds_write_b64 v58, v[78:79] offset:17952  // 00554c
	ds_write_b64 v58, v[80:81] offset:21760  // 005554
	ds_write_b64 v58, v[82:83] offset:22304  // 00555c
	ds_write_b64 v58, v[84:85] offset:26112  // 005564
	ds_write_b64 v58, v[86:87] offset:26656  // 00556c
	ds_write_b64 v58, v[88:89] offset:30464  // 005574
	ds_write_b64 v58, v[90:91] offset:31008  // 00557c
	s_waitcnt lgkmcnt(0)  // 005584
	s_barrier  // 005588
	ds_read_b32 v60, v42  // 00558c
	ds_read_b32 v61, v42 offset:32  // 005594
	ds_read_b32 v62, v42 offset:64  // 00559c
	ds_read_b32 v63, v42 offset:96  // 0055a4
	ds_read_b32 v64, v42 offset:4352  // 0055ac
	ds_read_b32 v65, v42 offset:4384  // 0055b4
	ds_read_b32 v66, v42 offset:4416  // 0055bc
	ds_read_b32 v67, v42 offset:4448  // 0055c4
	ds_read_b32 v68, v42 offset:8704  // 0055cc
	ds_read_b32 v69, v42 offset:8736  // 0055d4
	ds_read_b32 v70, v42 offset:8768  // 0055dc
	ds_read_b32 v71, v42 offset:8800  // 0055e4
	ds_read_b32 v72, v42 offset:13056  // 0055ec
	ds_read_b32 v73, v42 offset:13088  // 0055f4
	ds_read_b32 v74, v42 offset:13120  // 0055fc
	ds_read_b32 v75, v42 offset:13152  // 005604
	ds_read_b32 v76, v42 offset:17408  // 00560c
	ds_read_b32 v77, v42 offset:17440  // 005614
	ds_read_b32 v78, v42 offset:17472  // 00561c
	ds_read_b32 v79, v42 offset:17504  // 005624
	ds_read_b32 v80, v42 offset:21760  // 00562c
	ds_read_b32 v81, v42 offset:21792  // 005634
	ds_read_b32 v82, v42 offset:21824  // 00563c
	ds_read_b32 v83, v42 offset:21856  // 005644
	ds_read_b32 v84, v42 offset:26112  // 00564c
	ds_read_b32 v85, v42 offset:26144  // 005654
	ds_read_b32 v86, v42 offset:26176  // 00565c
	ds_read_b32 v87, v42 offset:26208  // 005664
	ds_read_b32 v88, v42 offset:30464  // 00566c
	ds_read_b32 v89, v42 offset:30496  // 005674
	ds_read_b32 v90, v42 offset:30528  // 00567c
	ds_read_b32 v91, v42 offset:30560  // 005684
	s_waitcnt lgkmcnt(0)  // 00568c
	s_barrier  // 005690
	s_mul_i32 s50, s37, 4  // 005694
	s_mul_i32 s51, s37, 8  // 005698
	s_mul_i32 s52, s37, 16  // 00569c
	v_mov_b32_e32 v4, v28  // 0056a0
	v_mov_b32_e32 v5, 0  // 0056a4
	v_mov_b32_e32 v7, 0  // 0056a8
	v_mov_b32_e32 v9, 0  // 0056ac
	v_mov_b32_e32 v11, 0  // 0056b0
	v_mov_b32_e32 v6, v4  // 0056b4
	v_add_u32_e64 v10, v4, s51  // 0056b8
	s_cmp_ge_u32 s77, s32  // 0056c0
	s_cbranch_scc1 L_5cd8  // 0056c4
	global_atomic_pk_add_bf16 v6, v60, s[80:81]  // 0056c8
	v_add_u32_e64 v8, v6, s50  // 0056d0
	s_add_i32 s77, s77, 4  // 0056d8
	s_cmp_ge_u32 s77, s32  // 0056dc
	s_cbranch_scc1 L_5cd8  // 0056e0
	global_atomic_pk_add_bf16 v8, v61, s[80:81]  // 0056e4
	s_add_i32 s77, s77, 4  // 0056ec
	s_cmp_ge_u32 s77, s32  // 0056f0
	s_cbranch_scc1 L_5cd8  // 0056f4
	global_atomic_pk_add_bf16 v10, v62, s[80:81]  // 0056f8
	v_add_u32_e64 v12, v10, s50  // 005700
	s_add_i32 s77, s77, 4  // 005708
	s_cmp_ge_u32 s77, s32  // 00570c
	s_cbranch_scc1 L_5cd8  // 005710
	global_atomic_pk_add_bf16 v12, v63, s[80:81]  // 005714
	s_add_i32 s77, s77, 4  // 00571c
	v_add_u32_e64 v4, v4, s52  // 005720
	v_mov_b32_e32 v6, v4  // 005728
	v_add_u32_e64 v10, v4, s51  // 00572c
	s_cmp_ge_u32 s77, s32  // 005734
	s_cbranch_scc1 L_5cd8  // 005738
	global_atomic_pk_add_bf16 v6, v64, s[80:81]  // 00573c
	v_add_u32_e64 v8, v6, s50  // 005744
	s_add_i32 s77, s77, 4  // 00574c
	s_cmp_ge_u32 s77, s32  // 005750
	s_cbranch_scc1 L_5cd8  // 005754
	global_atomic_pk_add_bf16 v8, v65, s[80:81]  // 005758
	s_add_i32 s77, s77, 4  // 005760
	s_cmp_ge_u32 s77, s32  // 005764
	s_cbranch_scc1 L_5cd8  // 005768
	global_atomic_pk_add_bf16 v10, v66, s[80:81]  // 00576c
	v_add_u32_e64 v12, v10, s50  // 005774
	s_add_i32 s77, s77, 4  // 00577c
	s_cmp_ge_u32 s77, s32  // 005780
	s_cbranch_scc1 L_5cd8  // 005784
	global_atomic_pk_add_bf16 v12, v67, s[80:81]  // 005788
	s_add_i32 s77, s77, 4  // 005790
	v_add_u32_e64 v4, v4, s52  // 005794
	v_mov_b32_e32 v6, v4  // 00579c
	v_add_u32_e64 v10, v4, s51  // 0057a0
	s_cmp_ge_u32 s77, s32  // 0057a8
	s_cbranch_scc1 L_5cd8  // 0057ac
	global_atomic_pk_add_bf16 v6, v68, s[80:81]  // 0057b0
	v_add_u32_e64 v8, v6, s50  // 0057b8
	s_add_i32 s77, s77, 4  // 0057c0
	s_cmp_ge_u32 s77, s32  // 0057c4
	s_cbranch_scc1 L_5cd8  // 0057c8
	global_atomic_pk_add_bf16 v8, v69, s[80:81]  // 0057cc
	s_add_i32 s77, s77, 4  // 0057d4
	s_cmp_ge_u32 s77, s32  // 0057d8
	s_cbranch_scc1 L_5cd8  // 0057dc
	global_atomic_pk_add_bf16 v10, v70, s[80:81]  // 0057e0
	v_add_u32_e64 v12, v10, s50  // 0057e8
	s_add_i32 s77, s77, 4  // 0057f0
	s_cmp_ge_u32 s77, s32  // 0057f4
	s_cbranch_scc1 L_5cd8  // 0057f8
	global_atomic_pk_add_bf16 v12, v71, s[80:81]  // 0057fc
	s_add_i32 s77, s77, 4  // 005804
	v_add_u32_e64 v4, v4, s52  // 005808
	v_mov_b32_e32 v6, v4  // 005810
	v_add_u32_e64 v10, v4, s51  // 005814
	s_cmp_ge_u32 s77, s32  // 00581c
	s_cbranch_scc1 L_5cd8  // 005820
	global_atomic_pk_add_bf16 v6, v72, s[80:81]  // 005824
	v_add_u32_e64 v8, v6, s50  // 00582c
	s_add_i32 s77, s77, 4  // 005834
	s_cmp_ge_u32 s77, s32  // 005838
	s_cbranch_scc1 L_5cd8  // 00583c
	global_atomic_pk_add_bf16 v8, v73, s[80:81]  // 005840
	s_add_i32 s77, s77, 4  // 005848
	s_cmp_ge_u32 s77, s32  // 00584c
	s_cbranch_scc1 L_5cd8  // 005850
	global_atomic_pk_add_bf16 v10, v74, s[80:81]  // 005854
	v_add_u32_e64 v12, v10, s50  // 00585c
	s_add_i32 s77, s77, 4  // 005864
	s_cmp_ge_u32 s77, s32  // 005868
	s_cbranch_scc1 L_5cd8  // 00586c
	global_atomic_pk_add_bf16 v12, v75, s[80:81]  // 005870
	s_add_i32 s77, s77, 4  // 005878
	v_add_u32_e64 v4, v4, s52  // 00587c
	v_mov_b32_e32 v6, v4  // 005884
	v_add_u32_e64 v10, v4, s51  // 005888
	s_cmp_ge_u32 s77, s32  // 005890
	s_cbranch_scc1 L_5cd8  // 005894
	global_atomic_pk_add_bf16 v6, v76, s[80:81]  // 005898
	v_add_u32_e64 v8, v6, s50  // 0058a0
	s_add_i32 s77, s77, 4  // 0058a8
	s_cmp_ge_u32 s77, s32  // 0058ac
	s_cbranch_scc1 L_5cd8  // 0058b0
	global_atomic_pk_add_bf16 v8, v77, s[80:81]  // 0058b4
	s_add_i32 s77, s77, 4  // 0058bc
	s_cmp_ge_u32 s77, s32  // 0058c0
	s_cbranch_scc1 L_5cd8  // 0058c4
	global_atomic_pk_add_bf16 v10, v78, s[80:81]  // 0058c8
	v_add_u32_e64 v12, v10, s50  // 0058d0
	s_add_i32 s77, s77, 4  // 0058d8
	s_cmp_ge_u32 s77, s32  // 0058dc
	s_cbranch_scc1 L_5cd8  // 0058e0
	global_atomic_pk_add_bf16 v12, v79, s[80:81]  // 0058e4
	s_add_i32 s77, s77, 4  // 0058ec
	v_add_u32_e64 v4, v4, s52  // 0058f0
	v_mov_b32_e32 v6, v4  // 0058f8
	v_add_u32_e64 v10, v4, s51  // 0058fc
	s_cmp_ge_u32 s77, s32  // 005904
	s_cbranch_scc1 L_5cd8  // 005908
	global_atomic_pk_add_bf16 v6, v80, s[80:81]  // 00590c
	v_add_u32_e64 v8, v6, s50  // 005914
	s_add_i32 s77, s77, 4  // 00591c
	s_cmp_ge_u32 s77, s32  // 005920
	s_cbranch_scc1 L_5cd8  // 005924
	global_atomic_pk_add_bf16 v8, v81, s[80:81]  // 005928
	s_add_i32 s77, s77, 4  // 005930
	s_cmp_ge_u32 s77, s32  // 005934
	s_cbranch_scc1 L_5cd8  // 005938
	global_atomic_pk_add_bf16 v10, v82, s[80:81]  // 00593c
	v_add_u32_e64 v12, v10, s50  // 005944
	s_add_i32 s77, s77, 4  // 00594c
	s_cmp_ge_u32 s77, s32  // 005950
	s_cbranch_scc1 L_5cd8  // 005954
	global_atomic_pk_add_bf16 v12, v83, s[80:81]  // 005958
	s_add_i32 s77, s77, 4  // 005960
	v_add_u32_e64 v4, v4, s52  // 005964
	v_mov_b32_e32 v6, v4  // 00596c
	v_add_u32_e64 v10, v4, s51  // 005970
	s_cmp_ge_u32 s77, s32  // 005978
	s_cbranch_scc1 L_5cd8  // 00597c
	global_atomic_pk_add_bf16 v6, v84, s[80:81]  // 005980
	v_add_u32_e64 v8, v6, s50  // 005988
	s_add_i32 s77, s77, 4  // 005990
	s_cmp_ge_u32 s77, s32  // 005994
	s_cbranch_scc1 L_5cd8  // 005998
	global_atomic_pk_add_bf16 v8, v85, s[80:81]  // 00599c
	s_add_i32 s77, s77, 4  // 0059a4
	s_cmp_ge_u32 s77, s32  // 0059a8
	s_cbranch_scc1 L_5cd8  // 0059ac
	global_atomic_pk_add_bf16 v10, v86, s[80:81]  // 0059b0
	v_add_u32_e64 v12, v10, s50  // 0059b8
	s_add_i32 s77, s77, 4  // 0059c0
	s_cmp_ge_u32 s77, s32  // 0059c4
	s_cbranch_scc1 L_5cd8  // 0059c8
	global_atomic_pk_add_bf16 v12, v87, s[80:81]  // 0059cc
	s_add_i32 s77, s77, 4  // 0059d4
	v_add_u32_e64 v4, v4, s52  // 0059d8
	v_mov_b32_e32 v6, v4  // 0059e0
	v_add_u32_e64 v10, v4, s51  // 0059e4
	s_cmp_ge_u32 s77, s32  // 0059ec
	s_cbranch_scc1 L_5cd8  // 0059f0
	global_atomic_pk_add_bf16 v6, v88, s[80:81]  // 0059f4
	v_add_u32_e64 v8, v6, s50  // 0059fc
	s_add_i32 s77, s77, 4  // 005a04
	s_cmp_ge_u32 s77, s32  // 005a08
	s_cbranch_scc1 L_5cd8  // 005a0c
	global_atomic_pk_add_bf16 v8, v89, s[80:81]  // 005a10
	s_add_i32 s77, s77, 4  // 005a18
	s_cmp_ge_u32 s77, s32  // 005a1c
	s_cbranch_scc1 L_5cd8  // 005a20
	global_atomic_pk_add_bf16 v10, v90, s[80:81]  // 005a24
	v_add_u32_e64 v12, v10, s50  // 005a2c
	s_add_i32 s77, s77, 4  // 005a34
	s_cmp_ge_u32 s77, s32  // 005a38
	s_cbranch_scc1 L_5cd8  // 005a3c
	global_atomic_pk_add_bf16 v12, v91, s[80:81]  // 005a40
	s_add_i32 s77, s77, 4  // 005a48
	v_add_u32_e64 v4, v4, s52  // 005a4c
	s_branch L_5cd8  // 005a54
L_5a58:
	v_add_f32_e32 v124, v124, v12  // 005a58
	v_add_f32_e32 v125, v125, v13  // 005a5c
	v_perm_b32 v60, v125, v124, s48  // 005a60
	v_add_f32_e32 v126, v126, v14  // 005a68
	v_add_f32_e32 v127, v127, v15  // 005a6c
	v_perm_b32 v61, v127, v126, s48  // 005a70
	buffer_store_dwordx2 v[60:61], v20, s[16:19], 0 offen  // 005a78
	v_add_f32_e32 v128, v128, v16  // 005a80
	v_add_f32_e32 v129, v129, v17  // 005a84
	v_perm_b32 v62, v129, v128, s48  // 005a88
	v_add_f32_e32 v130, v130, v18  // 005a90
	v_add_f32_e32 v131, v131, v19  // 005a94
	v_perm_b32 v63, v131, v130, s48  // 005a98
	buffer_store_dwordx2 v[62:63], v20, s[16:19], 0 offen offset:32  // 005aa0
	v_add_f32_e32 v132, v132, v12  // 005aa8
	v_add_f32_e32 v133, v133, v13  // 005aac
	v_perm_b32 v64, v133, v132, s48  // 005ab0
	v_add_f32_e32 v134, v134, v14  // 005ab8
	v_add_f32_e32 v135, v135, v15  // 005abc
	v_perm_b32 v65, v135, v134, s48  // 005ac0
	buffer_store_dwordx2 v[64:65], v21, s[16:19], 0 offen  // 005ac8
	v_add_f32_e32 v136, v136, v16  // 005ad0
	v_add_f32_e32 v137, v137, v17  // 005ad4
	v_perm_b32 v66, v137, v136, s48  // 005ad8
	v_add_f32_e32 v138, v138, v18  // 005ae0
	v_add_f32_e32 v139, v139, v19  // 005ae4
	v_perm_b32 v67, v139, v138, s48  // 005ae8
	buffer_store_dwordx2 v[66:67], v21, s[16:19], 0 offen offset:32  // 005af0
	v_add_f32_e32 v140, v140, v12  // 005af8
	v_add_f32_e32 v141, v141, v13  // 005afc
	v_perm_b32 v68, v141, v140, s48  // 005b00
	v_add_f32_e32 v142, v142, v14  // 005b08
	v_add_f32_e32 v143, v143, v15  // 005b0c
	v_perm_b32 v69, v143, v142, s48  // 005b10
	buffer_store_dwordx2 v[68:69], v22, s[16:19], 0 offen  // 005b18
	v_add_f32_e32 v144, v144, v16  // 005b20
	v_add_f32_e32 v145, v145, v17  // 005b24
	v_perm_b32 v70, v145, v144, s48  // 005b28
	v_add_f32_e32 v146, v146, v18  // 005b30
	v_add_f32_e32 v147, v147, v19  // 005b34
	v_perm_b32 v71, v147, v146, s48  // 005b38
	buffer_store_dwordx2 v[70:71], v22, s[16:19], 0 offen offset:32  // 005b40
	v_add_f32_e32 v148, v148, v12  // 005b48
	v_add_f32_e32 v149, v149, v13  // 005b4c
	v_perm_b32 v72, v149, v148, s48  // 005b50
	v_add_f32_e32 v150, v150, v14  // 005b58
	v_add_f32_e32 v151, v151, v15  // 005b5c
	v_perm_b32 v73, v151, v150, s48  // 005b60
	buffer_store_dwordx2 v[72:73], v23, s[16:19], 0 offen  // 005b68
	v_add_f32_e32 v152, v152, v16  // 005b70
	v_add_f32_e32 v153, v153, v17  // 005b74
	v_perm_b32 v74, v153, v152, s48  // 005b78
	v_add_f32_e32 v154, v154, v18  // 005b80
	v_add_f32_e32 v155, v155, v19  // 005b84
	v_perm_b32 v75, v155, v154, s48  // 005b88
	buffer_store_dwordx2 v[74:75], v23, s[16:19], 0 offen offset:32  // 005b90
	v_add_f32_e32 v156, v156, v12  // 005b98
	v_add_f32_e32 v157, v157, v13  // 005b9c
	v_perm_b32 v76, v157, v156, s48  // 005ba0
	v_add_f32_e32 v158, v158, v14  // 005ba8
	v_add_f32_e32 v159, v159, v15  // 005bac
	v_perm_b32 v77, v159, v158, s48  // 005bb0
	buffer_store_dwordx2 v[76:77], v24, s[16:19], 0 offen  // 005bb8
	v_add_f32_e32 v160, v160, v16  // 005bc0
	v_add_f32_e32 v161, v161, v17  // 005bc4
	v_perm_b32 v78, v161, v160, s48  // 005bc8
	v_add_f32_e32 v162, v162, v18  // 005bd0
	v_add_f32_e32 v163, v163, v19  // 005bd4
	v_perm_b32 v79, v163, v162, s48  // 005bd8
	buffer_store_dwordx2 v[78:79], v24, s[16:19], 0 offen offset:32  // 005be0
	v_add_f32_e32 v164, v164, v12  // 005be8
	v_add_f32_e32 v165, v165, v13  // 005bec
	v_perm_b32 v80, v165, v164, s48  // 005bf0
	v_add_f32_e32 v166, v166, v14  // 005bf8
	v_add_f32_e32 v167, v167, v15  // 005bfc
	v_perm_b32 v81, v167, v166, s48  // 005c00
	buffer_store_dwordx2 v[80:81], v25, s[16:19], 0 offen  // 005c08
	v_add_f32_e32 v168, v168, v16  // 005c10
	v_add_f32_e32 v169, v169, v17  // 005c14
	v_perm_b32 v82, v169, v168, s48  // 005c18
	v_add_f32_e32 v170, v170, v18  // 005c20
	v_add_f32_e32 v171, v171, v19  // 005c24
	v_perm_b32 v83, v171, v170, s48  // 005c28
	buffer_store_dwordx2 v[82:83], v25, s[16:19], 0 offen offset:32  // 005c30
	v_add_f32_e32 v172, v172, v12  // 005c38
	v_add_f32_e32 v173, v173, v13  // 005c3c
	v_perm_b32 v84, v173, v172, s48  // 005c40
	v_add_f32_e32 v174, v174, v14  // 005c48
	v_add_f32_e32 v175, v175, v15  // 005c4c
	v_perm_b32 v85, v175, v174, s48  // 005c50
	buffer_store_dwordx2 v[84:85], v26, s[16:19], 0 offen  // 005c58
	v_add_f32_e32 v176, v176, v16  // 005c60
	v_add_f32_e32 v177, v177, v17  // 005c64
	v_perm_b32 v86, v177, v176, s48  // 005c68
	v_add_f32_e32 v178, v178, v18  // 005c70
	v_add_f32_e32 v179, v179, v19  // 005c74
	v_perm_b32 v87, v179, v178, s48  // 005c78
	buffer_store_dwordx2 v[86:87], v26, s[16:19], 0 offen offset:32  // 005c80
	v_add_f32_e32 v180, v180, v12  // 005c88
	v_add_f32_e32 v181, v181, v13  // 005c8c
	v_perm_b32 v88, v181, v180, s48  // 005c90
	v_add_f32_e32 v182, v182, v14  // 005c98
	v_add_f32_e32 v183, v183, v15  // 005c9c
	v_perm_b32 v89, v183, v182, s48  // 005ca0
	buffer_store_dwordx2 v[88:89], v27, s[16:19], 0 offen  // 005ca8
	v_add_f32_e32 v184, v184, v16  // 005cb0
	v_add_f32_e32 v185, v185, v17  // 005cb4
	v_perm_b32 v90, v185, v184, s48  // 005cb8
	v_add_f32_e32 v186, v186, v18  // 005cc0
	v_add_f32_e32 v187, v187, v19  // 005cc4
	v_perm_b32 v91, v187, v186, s48  // 005cc8
	buffer_store_dwordx2 v[90:91], v27, s[16:19], 0 offen offset:32  // 005cd0
L_5cd8:
	s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)  // 005cd8
	s_endpgm  // 005cdc
.Lfunc_end__ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E:
	.size _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E, .Lfunc_end__ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E-_ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E

	.rodata
	.p2align 6
.amdhsa_kernel _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E
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
    .name:           _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E
    .private_segment_fixed_size: 0
    .reqd_workgroup_size:
      - 256
      - 1
      - 1
    .sgpr_count:     98
    .symbol:         _ZN5aiter43fp8gemm_bf16_blockscale_BpreShuffle_128x128E.kd
    .vgpr_count:     512
    .wavefront_size: 64
amdhsa.version:
  - 1
  - 0
...
	.end_amdgpu_metadata
