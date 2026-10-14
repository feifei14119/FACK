#ifndef COMMON_MI300_FP8_H
#define COMMON_MI300_FP8_H
/*
Defines fp8 convert related functions
*/
#include "common.h"
#include <unordered_map>
#define FAST_MODEL

#define BEXP_BF8(x) ((x & 0x7c) >> 2)
#define MAN_BF8(x)  (x & 0x3)
#define BEXP_FP8(x) ((x & 0x78) >> 3)
#define MAN_FP8(x)  (x & 0x7)
#define SIGN8(x)    ((x >> 7) & 1)
#define BF8(s,e,m)  ((s<<7) | (e<<2) | (m&0x3))
#define FP8(s,e,m)  ((s<<7) | (e<<3) | (m&0x7))

#define BEXP16(x) ((x & 0x7c00) >> 10)
#define MAN16(x)  (x & 0x3ff)
#define SIGN16(x) ((x >> 15) & 1)
//#define SIGN32(x) ((x >> 31) & 1)
#define BEXP32(x) ((x & 0x7f800000) >> 23)
#define MAN32(x)  (x & 0x7fffff)
//#define SIGN32(x) (x >> 31)
#define BEXP64(x) ((x & 0x7ff0000000000000ULL) >> 52)
#define MAN64(x)  (x & 0xfffffffffffffULL)
//#define SIGN64(x) (x >> 63)
#define FP16(s,e,m) ((s<<15) | (e<<10) | (m&0x3ff))
#define FP32(s,e,m) ((s<<31) | (e<<23) | (m&0x7fffff))
#define FP64(s,e,m) ((s<<63) | (e<<52) | (m&0xfffffffffffffULL))

#define RND_NEAREST_EVEN 0
#define RND_POS_INF      1
#define RND_NEG_INF      2
#define RND_TO_ZERO      3

uint32 mExceptionFlags = 0;
uint32 mIeeeMode = 1;
uint32 mSpInDenorms = 0;
uint32 mSpOutDenorms = 0;
uint32 mHpRoundMode = 0;
uint32 mSpRoundMode = 0;
uint32 mHpOutDenorms = 1;
uint32 mFp16OverFlowMode = 0;
uint32 mHpInDenorms = 1;

union Float8
{
    struct{
        unsigned long Frac:3;
        unsigned long Exp:4;
        unsigned long Sign:1;
    }fp8;
    struct{
        unsigned long Frac:2;
        unsigned long Exp:5;
        unsigned long Sign:1;
    }bf8;
    cl_char value;
};


uint32 get_f8_bias(uint32 f8_src_fmt, bool f8_bias)
{
    if ((f8_src_fmt == BF8_FMT) && f8_bias) {
        return 16;
    }
    else if ((f8_src_fmt == BF8_FMT) && !f8_bias) {
        return 15;
    }
    else if ((f8_src_fmt == FP8_FMT) && f8_bias) {
        return 8;
    }
    else if ((f8_src_fmt == FP8_FMT) && !f8_bias) {
        return 7;
    }
    else {
        printf("ERROR mathen.cpp: Argument of get_f8_bias(f8_src_fmt = %d, ieee_bias = %d) is not correct!\n", f8_src_fmt, f8_bias);
        assert(false);
        return 0;
    }
}

uint32 get_f8_mant_bits(uint32 f8_src_fmt)
{
    if (f8_src_fmt == BF8_FMT) {
        return 2;
    }
    else if (f8_src_fmt == FP8_FMT) {
        return 3;
    }
    else {
        printf("ERROR mathen.cpp: Argument of get_f8_mant_bits(f8_src_fmt = %d) is not correct!\n", f8_src_fmt);
        assert(false);
        return 0;
    }
}

int32 get_f8_max_exp(uint32 f8_src_fmt)
{
    if (f8_src_fmt == BF8_FMT) {
        return 0x1f;
    }
    else if (f8_src_fmt == FP8_FMT) {
        return 0xf;
    }
    else {
        printf("ERROR mathen.cpp: Argument of get_f8_max_exp(f8_src_fmt = %d) is not correct!\n", f8_src_fmt);
        assert(false);
        return 0;
    }
}

uint32 f8_to_f32(uint8 in, uint32 f8_src_fmt, bool f8_bias)
{
    uint32  mm,ee,ss;
    uint32  m,e,s,b;

    // Get sign, exponent and mantissa of input BF8/FP8 data.
    ss = SIGN8(in);
    ee = (f8_src_fmt == BF8_FMT)? BEXP_BF8(in) : BEXP_FP8(in);
    mm = (f8_src_fmt == BF8_FMT)? MAN_BF8(in)  : MAN_FP8(in);

    // Convert 8 bit float to 32 bit float
    m = mm;
    m <<= (f8_src_fmt == BF8_FMT)? (23-2) : (23-3) ;
    e = ee;
    b = get_f8_bias(f8_src_fmt, f8_bias);
    e += (127-b);
    s = ss;

    if (f8_bias) { // BF8 or FP8 with f8_bias:
                   // +0 Encoding: +0/-0, -0 Encoding: INF/NAN, INF Encoding: Normal, NAN encoding: Normal 
        if(ee == 0) {
            if(m == 0) {
                if (ss == 0) { //+0 encoding -> +0/-0
                    return 0;
                }
                else { //ss == 1: -0 encoding -> NAN
                    //return _pele_fp_nan.u32; //_minus_infinity.u;
                    return 0x7fffffff; //_minus_infinity.u;
                }
            }
            else {      // normalize input denorm
                e++;
#ifdef HECTOR
#pragma max_iterations 23
#endif
                while (!(m >> 23)) {
                    m <<= 1;
                    e--;
                }
                m &= 0x7fffff;
            }
        }
    }
    else { // BF8 or FP8 with non-ieee bias:
           // +0 Encoding: +0; -0 encoding: -0; INF encoding: INF; NAN encoding: NAN
        if((ee == 0x1f && f8_src_fmt == BF8_FMT) || (ee == 0xf && f8_src_fmt == FP8_FMT)) {
            if(mm) {  // NaN
                //return _pele_fp_nan.u32; 
                return 0x7fffffff; //_minus_infinity.u;
            }
            else      // INF
                return (s ? 0xff800000 : 0x7f800000);
        }

        if(ee == 0) {
            if(m == 0)  // zero
                return (s ? 0x80000000 : 0x0);
            else {      // normalize input denorm
                e++;
#ifdef HECTOR
#pragma max_iterations 23
#endif
                while (!(m >> 23)) {
                    m <<= 1;
                    e--;
                }
                m &= 0x7fffff;
            }
        }
    }
    m |= (e << 23);
    m |= (s << 31);
    return m;

}

// Only 1 round mode: round to nearest even
// No exception flags needed.
uint8 round_ieee_8(uint32 mant, uint32 guard, uint32 round, uint32 sticky, uint32 sign, int32 &exp, uint8 f8_fmt)
{
//#ifdef FAST_MODEL
#if 0
    uint32 result = mant;
#else
    assert(mHpRoundMode==RND_NEAREST_EVEN);

    uint32 result = mant;

    // Pre-Round - Catch possible underflow before final round
    uint32 mant_bits = get_f8_mant_bits(f8_fmt);
    uint32 max_mant = (1 << mant_bits) - 1; 
    if (exp==1 && result==max_mant && (guard && round==0)) {
        if (!mHpOutDenorms)
            result = 0;
    }

    // Round
    if (guard && ((mant&1) || round || sticky))
        result++;

    uint32 shift = mant_bits + 1;
    if(result >> shift) {
        result >>= 1;
        exp++;
    }

    // Overflow
/*
    int32 max_exp = get_f8_max_exp(f8_fmt);
    if(exp >= max_exp && (mant || guard || round || sticky)) 
    {
        if(mFp16OverFlowMode){ //Clamp to MAX_BF8
            exp = max_exp - 1;
            result = max_exp >> 1;
        }
        else {
            exp = max_exp;
            result = max_mant + 1;
        }
    }
*/
    // Underflow
    if(exp <= 0 || result==0) {
        exp = 0;
        if (result || guard || round || sticky ) {
            result = 0;
        }
    }

    // Handle denorms
    else if (exp==1 && (result>>mant_bits)==0)
    {
        exp = 0;
        if (!mHpOutDenorms){
            result = 0;
        }
    }
#endif

    return result;
}

uint8 f32_to_f8(uint32 src_a, uint32 f8_src_fmt, bool f8_bias, bool stoch_rnd, uint32 src_b)
{
    uint8 result_uint8;
    bool stick = false;
    uint32 m, b, mbits, mshift, mmask;
    int32  e;
    uint32 ss = SIGN32(src_a);
    uint32 ee = BEXP32(src_a);
    uint32 mm = MAN32(src_a);

    // Stochastic rounding
    if (stoch_rnd) {
        if (f8_src_fmt == BF8_FMT) {
            mm += ((src_b & 0xfffff800) >> 11);
        }
        else { // FP8_FMT
            mm += ((src_b & 0xfffff000) >> 12);
        }
    }

    // Check Special cases
    if(ee == 0xff) {
        if(mm) {  //NaN -> return -0
            return 0x80;      
        }
        else      //inf -> return -0
            return 0x80;
    }

    if(ee==0 && mm==0) //+0/-0 -> return +0
        return 0x0;

    // Normal cases
    b = get_f8_bias(f8_src_fmt, f8_bias);
    e = ee - 127 + b;
    if (ee)
        mm |= 0x800000;

    mbits  = get_f8_mant_bits(f8_src_fmt);
    mshift = 23 - mbits - 2;  // BF8: 1.(2+2); FP8: 1.(3+2) (m + g + r)
    m      = (mm >> mshift); 
    mmask  = (1 << mshift) - 1;
    stick  = (mm & mmask)? true : false;

    // Create denorm output
    int32 max_exp = get_f8_max_exp(f8_src_fmt);
    if (e < 1) {
        int32 shift = 1 - e;
        if (shift > max_exp) shift = max_exp;
        uint32 mask = (1 << shift) - 1;
        stick |= (m & mask)? true : false;
        m >>= shift;
        if (shift > max_exp) m = 0;
        e = 1;
    }
    
    m = round_ieee_8(m>>2, m&2, m&1, stick, ss, e, f8_src_fmt);
    result_uint8 = (f8_src_fmt == BF8_FMT)? BF8(ss, e, m) : FP8(ss, e, m);
    if ((f8_src_fmt == FP8_FMT) && (result_uint8 == 0x80))
       result_uint8 = 0x0;

    return result_uint8;
}

// f8_bias:   true: bias is 16 for BF8, bias is 8 for FP8.
// src_fmt:   Bit 0 ~ bit 2 stand for source format for source 0~2. If set, means BF8, otherwise means FP8.
uint32 dot16_f32_f8(uint64 srca0, uint64 srca1, uint64 srcb0, uint64 srcb1, uint32 srcc, uint8 src_fmt[2], const bool f8_bias) 
{
#ifdef FAST_MODEL
    uint32 result_int = 0;
#else
    //if (mMathenTrace) {
    //    printf("[dot16_f32_f8] srca0 = %llx, srca1 = %llx, srcb0 = %llx, srcb1 = %llx, srcc = %x, mDLInfNanClampEn = %d, src_fmt = {%d, %d}, f8_bias = %d\n",
    //           srca0, srca1, srcb0, srcb1, srcc, mDLInfNanClampEn, src_fmt[0], src_fmt[1], f8_bias);
    //}

    uint8  a_f8[16], b_f8[16];
    uint32 a_f32[16], b_f32[16], p[17], a_even[8], a_odd[8], b_even[8], b_odd[8], p_even[8], p_odd[8];
    uint32 result_int, result_exp;
    uint64 result_man;

    mIeeeMode    = true;
    mSpRoundMode = RND_NEAREST_EVEN;

    // Get 8bit data, put them into uint8 array.
    for (int i = 0; i < 8; i++) {
        a_f8[i]   = (srca0 >> (i*8)) & 0xff;
        b_f8[i]   = (srcb0 >> (i*8)) & 0xff;
        a_f8[i+8] = (srca1 >> (i+8)*8) & 0xff;
        b_f8[i+8] = (srcb1 >> (i+8)*8) & 0xff;
    }
    
    // Convert f8 to f32 for source a/b. Do a*b. Put src_c to p[16]
    for (int i = 0; i < 16; i ++) {
        a_f32[i] = f8_to_f32(a_f8[i], src_fmt[0], f8_bias);
        b_f32[i] = f8_to_f32(b_f8[i], src_fmt[1], f8_bias);
        p[i]     = dot_mul(a_f32[i], b_f32[i]);
    }
    p[16] = quietNan(vspflushdenorm(srcc));
    
    for (int i = 0; i < 16; i = i + 2) {
        a_even[i/2] = a_f32[i];
        a_odd[i/2]  = a_f32[i+1];
        b_even[i/2] = b_f32[i];
        b_odd[i/2]  = b_f32[i+1];
        p_even[i/2] = p[i];
        p_odd[i/2]  = p[i+1];
    }

    if (mMathenTrace) {
        for (int i = 0; i < 16; i ++) {
            printf("[dot16_f32_f8] a_f8[%d] = 0x%x, a_f32[%d] = 0x%x, b_f8[%d] = 0x%x, b_f32[%d] = 0x%x, p[%d] = 0x%x\n", 
                    i, a_f8[i], i, a_f32[i], i, b_f8[i], i, b_f32[i], i, p[i]);
        }

        printf("[dot16_f32_f8] c = 0x%x, flushed to 0x%x\n", srcc, p[16]);
        
        for (int i = 0; i < 8; i ++) {
            printf("a_even[%d] = 0x%x, b_even[%d] = 0x%x, p_even[%d] = 0x%x\n", i, a_even[i], i, b_even[i], i, p_even[i]);
        }
        
        for (int i = 0; i < 8; i ++) {
            printf("a_odd[%d] = 0x%x, b_odd[%d] = 0x%x, p_odd[%d] = 0x%x\n", i, a_odd[i], i, b_odd[i], i, p_odd[i]);
        }
    }

    // Check p[0]~p[16]: if nan/inf, get the nan/inf as result; 
    //                   else accumulate the sum of p[0]~p[16]
    if (rangeCheckN(17, p, result_int)) { // for nan, inf: return false
                                          // for normal, denorm, 0: continue

        bool    s[3];                // signs of accumulated sum.
        uint32  e[4];                // exponents of accumulated sum.
        uint64  m[5];                // mantisa of accumulated sum.
        int     ADDR_TAIL_WIDTH = 0; // total 1(s) + 28(5.23) + x(tail) FIXME: need to change to a variable.

        // Get the accumulated sum of even p[0]~p[15], put the results in {s[0], e[0], m[0]}
        m[0]    = accum_sum_f32(8, a_even, b_even, p_even, &(e[0]), &(s[0]), ADDR_TAIL_WIDTH);  
        if (mMathenTrace) {
            printf("[dot16_f32_f8] s0(sum of 0~7) : exp = 0x%x, mant = 0x%llx, sign = %d\n", e[0], m[0], s[0]);
        }

        // Get the accumulated sum of odd p[0]~p[15], put the results in {s[1], e[1], m[1]}
        m[1]    = accum_sum_f32(8, a_odd, b_odd, p_odd, &(e[1]), &(s[1]), ADDR_TAIL_WIDTH);  
        if (mMathenTrace) {
            printf("[dot16_f32_f8] s1(sum of 8~15): exp = 0x%x, mant = 0x%llx, sign = %d\n", e[1], m[1], s[1]);
        }

        // Align S0 and S1 and add. Say S2. At this stage, the output of the adder is 29bits.  
        m[2]    = align_shift_add(s, e, m, &(s[2]), &(e[2]), ADDR_TAIL_WIDTH); 

        if (mMathenTrace) {
            printf("[dot16_f32_f8] s2(s0 + s1)    : exp = 0x%x, mant = 0x%llx, sign = %d\n", e[2], m[2], s[2]);
        }

        // Get source C: the accumulated input 32bit float value
        s[3] = SIGN32(p[16]);                  // sign of flushed source C
        e[3] = BEXP32(p[16]);                  // exponent of flushed source C
        m[3] = MAN32(p[16]);                   // Mantisa of flushed source C
        m[3] = e[3]? (m[3] | 0x800000) : m[3]; // Normal number need to add 1 to bit 23 of mantissa.
        e[3] = (!e[3] && m[3])? 1 : e[3];      // Denormal number need to change exponent to 1.

        if (mMathenTrace) {
            printf("[dot16_f32_f8] C              : exp = 0x%x, mant = 0x%llx, sign = %d\n", e[3], m[3], s[3]);
        }
        
        // Align the 32bit C value relative to S2, C will be shifted relative to S2.
        m[4]    = align_shift_add(&(s[2]), &(e[2]), &(m[2]), &(s[4]), &(e[4]), ADDR_TAIL_WIDTH); // align C with S2, shift mantisa, add mantisa
        
        if (mMathenTrace) {
            printf("[dot16_f32_f8] result(s2 + c) : exp = 0x%x, mant = 0x%llx, sign = %d\n", e[4], m[4], s[4]);
        }

		// Normalize the output to get the 32bit float number (24bits of mantissa, 1.23).
        // Perform IEEE defined, round to the nearest even (RNE) to get the final float 32 number.
	    result_exp = e[4] + 5;                                            // 17 mantissa added together will make 5 more bits in mantissa; Change 6.23rg to 1.28rg
        result_man = m[4] << (35-ADDR_TAIL_WIDTH);                        // 1.28rg,4'hx,31'h0 --> 64-(24+5+addr_tail_width)
        result_int = normalize_denorms(s[4], result_exp, result_man, 0);  // including normalize and rounding

        if (mMathenTrace) {
            printf("[dot16_f32_f8] result (after normalized and rounded) : exp = 0x%x, mant = 0x%llx, sign = %d, result = 0x%x\n", 
                   result_exp, result_man, s[4], result_int);
        }
    }

    // Do clamp for Nan/Inf result according to clamp mode
    if(mDLInfNanClampEn) {                                            // Clamp Nan/Inf
        int ns = getNumberState(result_int);
        if(ns == NS_NAN) 
            result_int = 0;
        else if(ns == NS_POS_INF)
            result_int = _plus_max_float.u;
        else if(ns == NS_NEG_INF)
            result_int = _minus_max_float.u;
    }

    // Flush the output denorms
    result_int = vspflushdenorm(result_int, FLUSH_OUTPUT);

    if (mMathenTrace) 
        printf("[dot16_f32_f8] result (after clamp) = 0x%x\n", result_int);
#endif
    return result_int;
}


cl_char GetFP8Rand(int fp_format)
{
    union Float8 r;

    if(fp_format == BF8_FMT)
    {
        r.bf8.Sign = rand() & 0x1;
        r.bf8.Frac = rand() % 0x4;
        r.bf8.Exp  = rand() & 0x7c; 
    } 
    else if(fp_format == FP8_FMT)
    {
        r.fp8.Sign = rand() & 0x1;
        r.fp8.Frac = rand() % 0x8;
        r.fp8.Exp  = rand() & 0x78;
    }
    else
    {
        return 0xff;  //represent NaN
    }
    
    return r.value;

}


#endif