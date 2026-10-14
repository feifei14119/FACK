#ifndef COMMON_MI300_FP4_H
#define COMMON_MI300_FP4_H

#include "common.h"
#include "common_mi300_f16.h"
#ifdef USE_OPENBLAS
#include <cblas.h>
#endif

#define BEXP_FP4(x) ((x & 0x6) >> 1)
#define MANT_FP4(x) (x & 0x1)
#define SIGN_FP4(x) ((x >> 3) & 1)
#define FP4(s,e,m) ((s << 3) | (e << 1) | (m&0x1))
#define FP4_BS_SIZE 32

static int32 round_fp32_f4_significand_rne(bool &is_significand_ovf, uint32 trail_sig_fp32)
{
    is_significand_ovf = false;
    // trail_sig_fp32 is of the form 1.31
    uint32 trail_significand = (trail_sig_fp32 >>  8) & 0x7fffff;
    uint32 ulp_half_ulp      = (trail_sig_fp32 >>  7) & 0x3;    // 1.31 >> 7 = 1.24
    uint32 or_remain         = (trail_sig_fp32 >>  0) & 0x7f;
    switch(ulp_half_ulp) {
        case 0:
        case 2:
            break;
        case 1:
            if(or_remain) {
                trail_significand += 1;
            }
            break;
        case 3:
            trail_significand += 1;
            break;
        default:
            break;
    }
    is_significand_ovf = (((trail_significand >> 23) & 0x1) == 0x1);
    return (trail_significand & 0x7fffff);   // trail_significand is of the form .23
}

static uint32 fp4_to_f32(uint4_t in, uint32 scale_exp_f32)
{
    uint32 sign_fp4 = SIGN_FP4(in.val);
    uint32 trailing_significand_fp4
                    = MANT_FP4(in.val);
    int32  unbiased_exp_fp4 = BEXP_FP4(in.val) - 1;
    bool   is_fp4_pre_scale_zero = ((in.val & 0x7) == 0x0);
    bool   is_fp4_pre_scale_dnrm = (SIGN_FP4(in.val) == 0) && (MANT_FP4(in.val) != 0);

    // normalize subnormal number
    if (is_fp4_pre_scale_dnrm) {
        trailing_significand_fp4 = 0;
        unbiased_exp_fp4 = -1;
    }
    // at this point, leading significand bit is always 1 for non-zero input

    // apply scale
    unbiased_exp_fp4 += (scale_exp_f32 - 127);

    // at this point the exponent range is the output exponent range

    uint32 f32 = 0;

    if (scale_exp_f32 == 0xff) {
        f32 = (sign_fp4 << 31) | 0x7fc00000 | (trailing_significand_fp4 << 22);
    } else if (scale_exp_f32 == 0x7f) {
        // Scale is 1.0; Direct conversion
        switch(in.val & 0x7) {
            case 0: f32 = 0x00000000; break;    // +-0.0
            case 1: f32 = 0x3f000000; break;    // +-0.5
            case 2: f32 = 0x3f800000; break;    // +-1.0
            case 3: f32 = 0x3fc00000; break;    // +-1.5
            case 4: f32 = 0x40000000; break;    // +-2.0
            case 5: f32 = 0x40400000; break;    // +-3.0
            case 6: f32 = 0x40800000; break;    // +-4.0
            case 7: f32 = 0x40c00000; break;    // +-6.0
            default: f32 = 0; break;
        }
        f32 |= (sign_fp4 << 31);
    } else if (is_fp4_pre_scale_zero) {
        f32 = (sign_fp4 << 31) | 0x0;
    } else {
        if (unbiased_exp_fp4 < -149) {
            // scaled number is less than f32 min subnorm; output 0
            f32 = ((sign_fp4 << 31) | 0x0);
        } else if (unbiased_exp_fp4 < -126) {
            // scaled number is in f32 subnorm range,
            //  adjust mantissa such that unbiased_exp_fp4 is -126 and apply rne
            int32  exp_shift      = -126 - unbiased_exp_fp4;
            int32  unbiased_exp_f32
                                  = unbiased_exp_fp4 + exp_shift;
            assert(unbiased_exp_f32 == -126);
            uint32 trail_sig_fp32 = (1 << 31) | (trailing_significand_fp4 << 30);
            trail_sig_fp32      >>= exp_shift;
            bool   is_sig_ovf     = false;
            trail_sig_fp32        = round_fp32_f4_significand_rne(is_sig_ovf, trail_sig_fp32);
            f32 = (sign_fp4 << 31) | ((is_sig_ovf ? 0x01 : 0x00) << 23) | (trail_sig_fp32 & 0x7fffff);
        } else if (unbiased_exp_fp4 < +128) {
            // scaled number is in f32 normal range
            //  apply rne
            uint32  biased_exp_f32
                                  = unbiased_exp_fp4 + 127;
            uint32 trail_sig_fp32 = (1 << 31) | (trailing_significand_fp4 << 30);
            bool   is_sig_ovf     = false;
            trail_sig_fp32        = round_fp32_f4_significand_rne(is_sig_ovf, trail_sig_fp32);
            biased_exp_f32       += (is_sig_ovf ? 1 : 0);
            if (biased_exp_f32 == +255) {
                f32 = (sign_fp4 << 31) | 0x7f800000;
            } else {
                f32 = (sign_fp4 << 31) | ((biased_exp_f32 & 0xff) << 23) | (trail_sig_fp32 & 0x7fffff);
            }
        } else {
            // scaled number is greater than f32 max normL output +/- inf
            f32 = (sign_fp4 << 31) | 0x7f800000;
        }
    }

    return f32;
}

static uint32 round_f4_significand_rne(bool &is_significand_ovf, uint32 trail_sig_f4)
{
    is_significand_ovf = false;
    // trail_sig_f4 is of the form 1.31
    uint32 trail_significand
            = (trail_sig_f4 >> 30) & 0x1;
    uint32 ulp_half_ulp      = (trail_sig_f4 >> 29) & 0x3;    // 1.31 >> (31-1-1)
    uint32 or_remain         = (trail_sig_f4 >> 0) & ((1 << 29)-1);
    switch(ulp_half_ulp) {
        case 0:
        case 2:
            break;
        case 1:
            if(or_remain) {
                trail_significand += 1;
            }
            break;
        case 3:
            trail_significand += 1;
            break;
        default:
            break;
    }
    is_significand_ovf = (((trail_significand >> 1) & 0x1) == 0x1);
    // trail_significand is of the form .1
    return (trail_significand & 0x1);
}

static uint4_t f32_to_fp4(uint32 in, uint32 scale_exp_f32, bool stochastic_round, uint32 in1)
{
    uint32  sign_f32                 = SIGN32(in);
    uint32  trailing_significand_f32 = MAN32(in);
    int32   exp_f32                  = BEXP32(in);
    int32   unbiased_exp_f32         = exp_f32 - 127;
    bool    is_f32_pre_scale_inf     = (exp_f32 == 0xff)
                                        && (trailing_significand_f32 == 0);
    bool    is_f32_pre_scale_nan     = (exp_f32 == 0xff)
                                        && (trailing_significand_f32 != 0);
    bool    is_f32_pre_scale_zero    = ((in & 0x7fffffff) == 0);
    bool    is_f32_pre_scale_denorm  = (exp_f32 == 0x00)
                                        && (trailing_significand_f32 != 0);
    // stochastic rounding
    // copied from existing f8_math.cpp
    if (stochastic_round) {
        trailing_significand_f32 += ((in1 & 0xfffff000) >> 12);
    }

    // normalize subnormal number
    if (is_f32_pre_scale_denorm) {
        unbiased_exp_f32 = -126;
        for (uint32 mB = 22; mB >= 0; mB--) {
            if ((trailing_significand_f32 >> mB) != 0) {
                trailing_significand_f32 
                                 = (trailing_significand_f32 << (23 - mB)) & 0x7fffff;
                unbiased_exp_f32 = unbiased_exp_f32 - (23 - mB);
                break;
            }
        }
    }
    // at this point, leading significand bit is always 1 for non-zero input

    // apply scale
    unbiased_exp_f32 -= (scale_exp_f32 - 127);

    // at this point the exponent is the output exponent range

    uint4_t fp4 = {0};

    if (is_f32_pre_scale_inf || is_f32_pre_scale_nan || (scale_exp_f32 == 0xff)) {
        fp4.val = (sign_f32 << 3) | 0x7;
    } else if (is_f32_pre_scale_zero) {
        fp4.val = (sign_f32 << 3) | 0x0;
    } else {
        int32   min_subnorm_uexp_f4 = -1;
        int32   max_subnorm_uexp_f4 =  0;
        int32   max_norm_uexp_f4    = +2;
        uint32  mantissa_bits_f4    =  1;
        uint32  exponent_bits_f4    =  2;
        if (unbiased_exp_f32 < min_subnorm_uexp_f4) {
            // scaled number is less than f4 min subnorm; output 0
            fp4.val = (sign_f32 << 3) | 0x0;
            // even less than 0.5; actual hardware for >0.25 return sign<<3|1; not all 0
            if (unbiased_exp_f32 == -2 && trailing_significand_f32 > 0) {
                //>0.25 <0.5
                fp4.val = (sign_f32 << 3) | 0x1;
            }
        } else if (unbiased_exp_f32 < max_subnorm_uexp_f4) {
            // scaled number is in f4 subnorm range,
            //  adjust mantissa such that unbiased_exp_f32 is 
            //  max_subnorm_uexp_f4 and apply rne
            int32 exp_shift     = max_subnorm_uexp_f4 - unbiased_exp_f32;
            int32 unbiased_exp_f4
                                = unbiased_exp_f32 + exp_shift;
            assert(unbiased_exp_f4 == max_subnorm_uexp_f4);
            uint32 trail_sig_f4 = (1 << 31) | (trailing_significand_f32 << 8);
            trail_sig_f4      >>= exp_shift;
            bool   is_sig_ovf   = false;
            trail_sig_f4        = round_f4_significand_rne(is_sig_ovf, trail_sig_f4);
            fp4.val = (sign_f32 << 3)
                        | ((uint8_t)((is_sig_ovf ? 0x01 : 0x00) << mantissa_bits_f4))
                        | (trail_sig_f4 & ((1 << mantissa_bits_f4) - 1));
        } else if (unbiased_exp_f32 <= max_norm_uexp_f4) {
            // scaled number is in f4 normal range
            //  apply rne
            uint32 biased_exp_f4
                                = unbiased_exp_f32 + 1;
            uint32 trail_sig_f4 = (1 << 31) | (trailing_significand_f32 << 8);
            bool   is_sig_ovf   = false;
            trail_sig_f4        = round_f4_significand_rne(is_sig_ovf, trail_sig_f4);
            biased_exp_f4      += (is_sig_ovf ? 1 : 0);
            if (biased_exp_f4 == (uint32)(max_norm_uexp_f4 + 1 + 1)) {
                fp4.val = (sign_f32 << 3) | 0x7;
            } else {
                fp4.val = (sign_f32 << 3)
                            | ((biased_exp_f4 & ((1 << exponent_bits_f4)-1)) << mantissa_bits_f4)
                            | (trail_sig_f4 & ((1 << mantissa_bits_f4)-1));
            }
        } else {
            // scaled number is greater than f4 max normal output
            //  clamp to f4 flt_max
            fp4.val = (sign_f32 << 3) | 0x7;
        }
    }

    return fp4;
}

static void initFp4ScaleMatrixInRowMajor(cl_char* buffer, int m, int n, uint8_t init_pattern, short exp_value=2, uint8_t scale_exp_bias=127)
{
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            short temp_var;

            switch (init_pattern)
            {
            case 1:                                             // 1: Fixed exponent value in the range [-127,127]
                temp_var = exp_value;
                break;
            case 2:                                             // 2: Randomize exponent values in range [-exp_value, exp_value]
                if (exp_value == 0) {
                    temp_var = 0;
                } else {
                    temp_var = (rand()%(2*exp_value)) - exp_value;
                }
                break;
            default:                                            // 0: zero exp value
                temp_var = 0;           // default scale: 0
                break;
            }

            buffer[i * n + j] = (cl_char)((temp_var+scale_exp_bias)&0xFF);
        }
    }
}

//buffer is row major, m, n is size of uint4
static void initFp4MatrixInRowMajor(cl_char* buffer, int m, int n, int init_pattern) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            int offset = i*n + j;
            float temp_var;
            switch (init_pattern)
            {
                case 1:
                    temp_var = cos(offset);
                    break;
                case 2:
                    temp_var = sin(offset);
                    break;
                case 3:
                    temp_var = cos(offset) + sin(offset);
                    break;
                case 10:
                    temp_var = 0.25;
                    break;
                default:
                    temp_var = 0;
                    break;
            }
            uint4_t value = f32_to_fp4(FloatMapToInt(temp_var), 127, false, 0);
            setFp4(buffer, value, m, n, i, j, 1);
        }
    }
}

//rowin is row major without padding; columnout is column major with padding
static void padFp4RowToColumn(cl_char *columnout, cl_char *rowin, int m, int n, int pad) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            uint4_t value = getFp4(rowin, m, n, i, j, 1);
            setFp4(columnout, value, m+pad, n, i, j, 0);
        }
    }
}

//rowin is row major without padding; rowout is row major with padding
static void padFp4RowToRow(cl_char *rowout, cl_char *rowin, int m, int n, int pad) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            uint4_t value = getFp4(rowin, m, n, i, j, 1);
            setFp4(rowout, value, m, n+pad, i, j, 1);
        }
    }
}

//columnin is column major with padding; rowout is row major without padding
static void unpadFp4ColumnToRow(cl_char *rowout, cl_char *columnin, int m, int n, int pad) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            uint4_t value = getFp4(columnin, m+pad, n, i, j, 0);
            setFp4(rowout, value, m, n, i, j, 1);
        }
    }
}

//rowin is row major with padding; rowout is row major without padding
static void unpadFp4RowToRow(cl_char *rowout, cl_char *rowin, int m, int n, int pad) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            uint4_t value = getFp4(rowin, m, n+pad, i, j, 1);
            setFp4(rowout, value, m, n, i, j, 1);
        }
    }
}

static void printFp4Matrix(cl_char* buffer, int m, int n, int rowmajor) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float value = IntMapToFloat(fp4_to_f32(getFp4(buffer, m, n, i, j, rowmajor), 127));
            printf("%f ", value);
        }
        printf("\n");
    }
}

static void dumpFp4MatrixInHex(cl_char *data, const char *fileName, int m, int n, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            uint value = getFp4(data, m, n, i, j, rowmajor).val;
            fprintf(file, "%01x ", value);
        }
        fprintf(file, "\n");
    }

    fclose(file);
}

static void dumpFp4MatrixInFloat(cl_char *data, const char *fileName, int m, int n, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float value = IntMapToFloat(fp4_to_f32(getFp4(data, m, n, i, j, rowmajor), 127));
            fprintf(file, "%10.8f ", value);
        }
        fprintf(file, "\n");
    }

    fclose(file);
}

/*
//matrix all row major, a: mxk, b: kxn, c:mxn
static void matrix_mul_Fp4_nopad(cl_char *a, cl_char *b, cl_int *c, int m, int n, int k) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            for (int p = 0; p < k; p++) {
                uint value_a = getFp4(a, m, k, i, p, 1);
                uint value_b = getFp4(b, k, n, p, j, 1);
                c[i*n+j] += value_a * value_b;
            }
        }
    }
}*/

static uint32 check_fp4_result(cl_char *result, cl_char *golden, int Mdim, int Ndim, int pad, int c_col_major) 
{
    uint32 SameResult = 1;
    uint32 strideC;

    printf("\n\n>>>>>>>>>>>>> \033[1m\033[;34m  CHECKING RESULTS  \033[0m  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n");

    if(c_col_major == 1) {
        strideC = Mdim + pad;
    }
    else {
        strideC = Ndim + pad;
    }

    for(int j = 0; j < Mdim; j++) {
        for(int i = 0; i < Ndim; i++) {
            uint4_t rlt, gld;
            if (c_col_major) {
                rlt = getFp4(result, strideC, Ndim, j, i, 0);
            } else {
                rlt = getFp4(result, Mdim, strideC, j, i, 1);
            }
            gld = getFp4(golden, Mdim, Ndim, j, i, 1);

            if (rlt.val != gld.val) {
                SameResult = 0;

                printf("#######  diff index is [y = %d, x = %d]\n", j, i);
                //printf("#######  gpu results      = %f   \n", (c_col_major ? result[i * strideC + j] : result[j * strideC + i]));
                //printf("#######  golden           = %f   \n", golden[j * Ndim + i]);
                
                printf("#######  gpu results hex  = %08x    \n", rlt.val);
                printf("#######  golden      hex  = %08x    \n", gld.val);
                

                goto PRINT_RESULT;
            }
        }
    }

PRINT_RESULT:
    if (SameResult) {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;32m #TEST PASSED \033[0m                      <<<<<<<<<<<<<<<<<<<<\n\n");
    }
    else {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;35m #TEST FAILED \033[0m!!!!!!!!!! !!!!!!!!!! <<<<<<<<<<<<<<<<<<<<\n\n");
    }
    return SameResult;
}


static void printFp32Matrix(cl_float* data, int m, int n, int rowmajor) {
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            cl_float *valueP;
            if (rowmajor == 1) {
                valueP = data + (i * n + j);
            } else {
                valueP = data + (j * m + i);
            }

            printf("%f ", *valueP);
        }
        printf("\n");
    }
}

static void dumpFp32MatrixInHex(cl_int *data, const char *fileName, int m, int n, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            cl_int *valueP;
            if (rowmajor == 1) {
                valueP = data + (i * n + j);
            } else {
                valueP = data + (j * m + i);
            }

            fprintf(file, "%08x ", *valueP);
        }
        fprintf(file, "\n");
    }

    fclose(file);
}

static void dumpFp32MatrixInFloat(cl_float *data, const char *fileName, int m, int n, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            cl_float *valueP;
            if (rowmajor == 1) {
                valueP = data + (i * n + j);
            } else {
                valueP = data + (j * m + i);
            }

            fprintf(file, "%10.8f ", *valueP);
        }
        fprintf(file, "\n");
    }

    fclose(file);
}

static void Dot32FloatScale(float srcA[], float srcB[], float srcC, float & dest, float scaleA, float scaleB, bool debug=false)
{
    double result = 0.0f;
    for (int i = 0; i < 32; i++) {
        result += (double)srcA[i] * (double)srcB[i];
        if (debug)
            printf("+%08x*%08x ", *((uint32*)(&srcA[i])), *((uint32*)(&srcB[i])));
    }
    result *= (double)scaleA;
    result *= (double)scaleB;
    result += (double)srcC;
    if (debug) {
        printf(" *=%08x *=%08x +=%08x", *((uint32*)(&scaleA)),*((uint32*)(&scaleB)),*((uint32*)(&srcC)));
    }
    dest = (float)result;
    if (debug) {
        printf("\n   result=%08x\n",*((uint32*)(&dest)));
    }
}

//matrix all row major, a: mxk, b: kxn, c:mxn
static void matrix_mul_Fp4Fp4_nopad(cl_char *a, cl_char *b, cl_float *c, bool add_c, int m, int n, int k, bool afp8, bool needalphabeta, float alpha,
                                            bool f4_dst = false,
                                            uint32 scale_exp_f32 = 127, uint32 f8_src_fmt = FP8_FMT, bool f8_bias = false,
                                            int f8_dst_fmt = FP8_FMT, bool f8_bias_dst = false, bool clamp = false, bool stochastic_round = false, uint32 in1 = 0) {
    int8 scale_exp_a = 0;
    int8 scale_exp_b = 0;
    float scaleA = (float)pow(2, scale_exp_a);
    float scaleB = (float)pow(2, scale_exp_b);
    #define DOT_SIZE_FP4FP4 32
    float srcAf32[DOT_SIZE_FP4FP4];
    float srcBf32[DOT_SIZE_FP4FP4];

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float srcCf32 = 0;
            float srcDf32 = 0;
            if (add_c) {
                srcCf32 = c[i*n+j];
            }
            bool debug = false;
            if (i == 0 && j == 0)
                debug = false;

            for (int p = 0; p < k; p+=DOT_SIZE_FP4FP4) {
                for (int dot = 0; dot < DOT_SIZE_FP4FP4; dot++) {
                    srcAf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(a, m, k, i, p+dot, 1, debug), scale_exp_f32));
                    srcBf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(b, k, n, p+dot, j, 1, debug), scale_exp_f32));
                }
                Dot32FloatScale(srcAf32, srcBf32, p == 0 ? srcCf32 : srcDf32, srcDf32, scaleA, scaleB, debug);
            }
            if (needalphabeta) {
                srcDf32 = srcDf32 * alpha;
            }

            cl_char *fp4_dst = (cl_char*) c;
            if (f4_dst) {
                setFp4(fp4_dst, f32_to_fp4(FloatMapToInt(srcDf32), 127, false, 0),m,n,i,j,1);
            } else {
                c[i*n+j] = srcDf32;
            }
        }
    }
}

//matrix all row major, a: mxk, b: kxn, c:mxn;
//scale_a row major; scale_b col major, both fast-changing is K
#ifndef USE_OPENBLAS    
static void matrix_mul_Fp4Fp4_nopad_scale_std(cl_char *a, cl_char *b, cl_float *c, uint8 *scale_a, uint8 *scale_b, bool inp_scale_en, bool add_c, int m, int n, int k, bool afp8, bool needalphabeta, float alpha,
                                            bool f4_dst = false, DATA_TYPE outtype = TYPE_NUM,
                                            uint32 scale_exp_f32 = 127, uint32 f8_src_fmt = FP8_FMT, bool f8_bias = false,
                                            int f8_dst_fmt = FP8_FMT, bool f8_bias_dst = false, bool clamp = false, bool stochastic_round = false, uint32 in1 = 0) {
    int8 scale_exp_a = 0;
    int8 scale_exp_b = 0;
    float scaleA = (float)pow(2, scale_exp_a);
    float scaleB = (float)pow(2, scale_exp_b);
    #define DOT_SIZE_FP4FP4 32
    float srcAf32[DOT_SIZE_FP4FP4];
    float srcBf32[DOT_SIZE_FP4FP4];
    unsigned short *p1 = (unsigned short*) c;

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float srcCf32 = 0;
            float srcDf32 = 0;
            if (add_c) {
                srcCf32 = c[i*n+j];
            }
            bool debug = false;
            if (i == 0 && j == 0)
                debug = false;

            for (int p = 0; p < k; p+=DOT_SIZE_FP4FP4) {
                if (inp_scale_en) {
                    //get real scale value
                    uint8 as = scale_a[i*k/FP4_BS_SIZE+p/FP4_BS_SIZE];
                    uint8 bs = scale_b[j*k/FP4_BS_SIZE+p/FP4_BS_SIZE];
                    scaleA = (float)pow(2, as-127);
                    scaleB = (float)pow(2, bs-127);
                }
                for (int dot = 0; dot < DOT_SIZE_FP4FP4; dot++) {
                    srcAf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(a, m, k, i, p+dot, 1, debug), scale_exp_f32));
                    srcBf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(b, k, n, p+dot, j, 1, debug), scale_exp_f32));
                }
                Dot32FloatScale(srcAf32, srcBf32, p == 0 ? srcCf32 : srcDf32, srcDf32, scaleA, scaleB, debug);
            }
            if (needalphabeta) {
                srcDf32 = srcDf32 * alpha;
            }

            cl_char *fp4_dst = (cl_char*) c;
            if (f4_dst) {
                setFp4(fp4_dst, f32_to_fp4(FloatMapToInt(srcDf32), 127, false, 0),m,n,i,j,1);
            }  else {
                if (outtype == FP32) {
                    c[i*n+j] = srcDf32;
                } else if (outtype == BF16) {
                    p1[i*n+j] = (unsigned short)FP32toBFP16(FloatMapToInt(srcDf32));
                } else {
                    assert(0);
                }
            }
        }
    }
}

#else
//using openblas to accelerate matmul
//matrix all row major, a: mxk, b: kxn, c:mxn;
//scale_a row major; scale_b col major, both fast-changing is K
static void matrix_mul_Fp4Fp4_nopad_scale_std(cl_char *a, cl_char *b, cl_float *c, uint8 *scale_a, uint8 *scale_b, bool inp_scale_en, bool add_c, int m, int n, int k, bool afp8, bool needalphabeta, float alpha,
                                            bool f4_dst = false, DATA_TYPE outtype = TYPE_NUM,
                                            uint32 scale_exp_f32 = 127, uint32 f8_src_fmt = FP8_FMT, bool f8_bias = false,
                                            int f8_dst_fmt = FP8_FMT, bool f8_bias_dst = false, bool clamp = false, bool stochastic_round = false, uint32 in1 = 0) {
    assert(add_c == false && f4_dst == false);                                                
    std::vector<float> a_fp32(m * k), b_fp32(n * k), c_fp32(m * n, 0);
    
    #pragma omp parallel for    
    for (int i = 0; i < m; i++) {
        for (int p = 0; p < k; p+=DOT_SIZE_FP4FP4) {
            float scaleA = 1.0f;
            if (inp_scale_en) {
                //get real scale value
                uint8 as = scale_a[i*k/FP4_BS_SIZE+p/FP4_BS_SIZE];
                scaleA = (float)pow(2, as-127);
            }
            for (int dot = 0; dot < DOT_SIZE_FP4FP4; dot++) {
                a_fp32[i * k + p + dot] = IntMapToFloat(fp4_to_f32(getFp4(a, m, k, i, p + dot, 1, false), scale_exp_f32)) * scaleA;
            }
        }
    }
    #pragma omp parallel for    
    for (int i=0; i < n; i++) {
        for (int p = 0; p < k; p+=DOT_SIZE_FP4FP4) {
            float scaleB = 1.0f;
            if (inp_scale_en) {
                //get real scale value
                uint8 bs = scale_b[i*k/FP4_BS_SIZE+p/FP4_BS_SIZE];
                scaleB = (float)pow(2, bs-127);
            }
            for (int dot = 0; dot < DOT_SIZE_FP4FP4; dot++) {
                b_fp32[(p + dot) * n + i] = IntMapToFloat(fp4_to_f32(getFp4(b, k, n, p + dot, i, 1, false), scale_exp_f32)) * scaleB;
            }
        }
    }
    
    cblas_sgemm(CblasRowMajor,
                CblasNoTrans,   // A, row major
                CblasNoTrans,   // B, row major
                m, n, k,
                needalphabeta? alpha: 1,
                a_fp32.data(),
                k,              // A leading dimension
                b_fp32.data(),
                n,
                0,
                c_fp32.data(),
                n);
                
    #pragma omp parallel for
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            if (outtype == FP32) {
                c[i*n+j] = c_fp32[i*n+j];
            } else if (outtype == BF16) {
                unsigned short bf16_val = (unsigned short)FP32toBFP16(FloatMapToInt(c_fp32[i*n+j]));
                unsigned short * c_u16 = (unsigned short*) c;
                c_u16[i * n + j] = bf16_val;
            }
        }
    }
}
#endif


static void matrix_mul_Fp4Fp4_nopad_scale_stochrnd(cl_char *a, cl_char *b, cl_float *c, cl_char *scale_a, cl_char *scale_b, bool inp_scale_en,
                                            bool add_c, int m, int n, int k, bool afp8, bool needalphabeta, float alpha,
                                            bool f4_dst = false, uint32 scale_exp_f32 = 127, bool stochastic_round = false, uint32 in1 = 0, 
                                            uint32 f8_src_fmt = FP8_FMT, bool f8_bias = false,
                                            int f8_dst_fmt = FP8_FMT, bool f8_bias_dst = false, bool clamp = false) {
    int8 scale_exp_a = 0;
    int8 scale_exp_b = 0;
    float scaleA = (float)pow(2, scale_exp_a);
    float scaleB = (float)pow(2, scale_exp_b);
    #define DOT_SIZE_FP4FP4 32
    float srcAf32[DOT_SIZE_FP4FP4];
    float srcBf32[DOT_SIZE_FP4FP4];

    printf("Enter: matrix_mul_Fp4Fp4_nopad_stochrnd\n");
    printf("Enter: seed for stochastic rounding = 0x%08x\n", in1);

    // When stochastic rounding is enabled in output conversion from F32 to F4

    int mtile = 256;
    int ntile = 256;
    int mSU = 128;
    int nSU = 128;
    int mCvtblkSize = 64;       // each conversion instruction processes M64xN32 output block
    int nCvtblkSize = 32;
    int ThreadSeed[64];

    for (int i = 0; i < m; i+=mtile)
    {
        for (int j = 0; j < n; j+=ntile)
        {
            for (int mSUIdx = 0; mSUIdx < mtile; mSUIdx+=mSU)
            {
                for (int nSUIdx = 0; nSUIdx < ntile; nSUIdx+=nSU)
                {
                    for (int mCvtblkIdx = 0; mCvtblkIdx < mSU; mCvtblkIdx+=mCvtblkSize)
                    {
                        for (int nCvtblkIdx = 0; nCvtblkIdx < nSU; nCvtblkIdx+=nCvtblkSize)
                        {
                            for(int thIdx=0; thIdx<64; thIdx++)
                                ThreadSeed[thIdx] = in1+thIdx;
                            for (int nCvtsubblkIdx = 0; nCvtsubblkIdx < nCvtblkSize; nCvtsubblkIdx+=16)
                            {                                    
                                for (int mOutIdx = 0; mOutIdx < mCvtblkSize; mOutIdx+=1)
                                {
                                    for (int nOutIdx = 0; nOutIdx < 16; nOutIdx+=1)
                                    {
                                        float srcCf32 = 0;
                                        float srcDf32 = 0;
                                        int threadIdx = (((mOutIdx&0xF)>>2)<<4)+(nOutIdx&0xF);
                                        int tmp_seed = ThreadSeed[threadIdx];
                                        int outRowIdx = i+mSUIdx+mCvtblkIdx+mOutIdx;
                                        int outColIdx = j+nSUIdx+nCvtblkIdx+nCvtsubblkIdx+nOutIdx;

                                        if(mOutIdx&1)
                                            tmp_seed = prngB32(tmp_seed);

                                        if (add_c) {
                                            srcCf32 = c[outRowIdx*n+outColIdx];
                                        }
                                        bool debug = false;
                                        if (i == 0 && j == 0)
                                            debug = false;

                                        for (int p = 0; p < k; p+=DOT_SIZE_FP4FP4) {
                                            for (int dot = 0; dot < DOT_SIZE_FP4FP4; dot++) {
                                                srcAf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(a, m, k, outRowIdx, p+dot, 1, debug), scale_exp_f32));
                                                srcBf32[dot] = IntMapToFloat(fp4_to_f32(getFp4(b, k, n, p+dot, outColIdx, 1, debug), scale_exp_f32));
                                            }

                                            int ScaleA_Idx = outRowIdx*(k/DOT_SIZE_FP4FP4)+(p/DOT_SIZE_FP4FP4);
                                            int ScaleB_Idx = ((p/DOT_SIZE_FP4FP4)*n) + outColIdx;
                                            short iScaleA = inp_scale_en? ((scale_a[ScaleA_Idx]&0xFF)-127): 0;      // Unbiased
                                            short iScaleB = inp_scale_en? ((scale_b[ScaleB_Idx]&0xFF)-127): 0;      // Unbiased
                                            scaleA = (float)pow(2, iScaleA);
                                            scaleB = (float)pow(2, iScaleB);

                                            Dot32FloatScale(srcAf32, srcBf32, p == 0 ? srcCf32 : srcDf32, srcDf32, scaleA, scaleB, debug);
                                        }
                                        if (needalphabeta) {
                                            srcDf32 = srcDf32 * alpha;
                                        }

                                        cl_char *fp4_dst = (cl_char*) c;
                                        if (f4_dst) {
                                            setFp4(fp4_dst, f32_to_fp4(FloatMapToInt(srcDf32), 127, stochastic_round, tmp_seed),m,n,outRowIdx,outColIdx,1);
                                        } else {
                                            c[outRowIdx*n+outColIdx] = srcDf32;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
#endif