

#ifndef GEMM_HPP
#define GEMM_HPP

#include <list>
#include <string>
#include <vector>
#include <math.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "./common/common_mi300_fp8.h"
#include "./common/fmoe.hpp"

#define BEXP16(x) ((x & 0x7c00) >> 10)
#define MAN16(x)  (x & 0x3ff)
#define SIGN16(x) ((x >> 15) & 1)
#define BEXP32(x) ((x & 0x7f800000) >> 23)
#define MAN32(x)  (x & 0x7fffff)
#define SIGN32(x) (x >> 31)
#define BEXP64(x) ((x & 0x7ff0000000000000ULL) >> 52)
#define MAN64(x)  (x & 0xfffffffffffffULL)
#define SIGN64(x) (x >> 63)
#define FP16(s,e,m) ((s<<15) | (e<<10) | (m&0x3ff))
#define FP32(s,e,m) ((s<<31) | (e<<23) | (m&0x7fffff))
#define FP64(s,e,m) ((s<<63) | (e<<52) | (m&0xfffffffffffffULL))
#define DEBUG 0


//add some function for GEMM with scale/bias 
static void initF32_scale(float *buffer, int length,  int usesin) {
    for (int i = 0; i < length; i++) {
         buffer[i] = (float)gaussrand(); //random float value
    }
}

static void initFP32_bias(float *buffer, int length) {
    for (int i = 0; i < length; i++) {
        buffer[i] = (float)gaussrand();
    }
}

static void initFP8MatrixInRowMajor(uint8* buffer, int m, int n){

    float f_tmp = 1.0f;
    for (int iii = 0; iii < m; ++iii)
    {
        for (int jjj = 0; jjj < n; ++jjj)
        {
            f_tmp = (float)gaussrand();   //[-3,3]
            #ifdef FMHA_MI300
            buffer[iii * n + jjj] = f32_to_f8(FloatMapToInt(f_tmp), FP8_FMT, true /*f8_bias = true*/, false, 0);
            #else
            buffer[iii * n + jjj] = f32_to_fp8(FloatMapToInt(f_tmp), 127, FP8_FMT, true /*f8_bias = true*/, true, false, 0);
            #endif
        }
    }
}

//tiling for sw shuffle 32x16
static void tiling_32x32x16_i8_dw4_sw(uint8 *out, uint8 *in, unsigned int MN, unsigned int K) {

    int block_index = 0;
    int block_size = 32 * 16;
    int idx_x, idx_y;  //block idx. x is k dim, y is mn dim
    int pos_x, pos_y;  //pos in block. x is k dim, y is mn dim
    int pos_index = 0;
    int addr = 0;
    for (int i = 0; i < MN; i++) {
        for (int j = 0; j < K; j++) {
            idx_x = j / 16;
            idx_y = i / 32;
            block_index = (K / 16) * idx_y + idx_x; //block idx

            pos_x = j % 16;
            pos_y = i % 32;
            pos_index = 16 * pos_y + pos_x;

            addr = block_index * block_size + pos_index;
            out[addr] = in[i * K + j];
        }
    }
}

//tiling for sw shuffle 16x32
static void tiling_16x16x32_i8_dw4_sw(cl_char *out, cl_char *in, unsigned int MN, unsigned int K) {

    int block_index = 0;
    int block_size = 16 * 16;
    int idx_x, idx_y;  //block idx. x is k dim, y is mn dim
    int pos_x, pos_y;  //pos in block. x is k dim, y is mn dim
    int pos_index = 0;
    int addr = 0;
    for (int mn = 0; mn < MN; mn++) {
        for (int k = 0; k < K; k++) {
            idx_x = k  / 16;
            idx_y = mn / 16;
            block_index = (K / 16) * idx_y + idx_x; //block idx

            pos_x = k  % 16;
            pos_y = mn % 16;
            pos_index = 16 * pos_y + pos_x;

            addr = block_index * block_size + pos_index;
            out[addr] = in[mn * K + k];
        }
    }
    return;

}

bool GEMM_FP8_BLOCKSCALE_BIAS_dbg(unsigned short* dst, float* output_f32, 
                        uint8* matrix_a, uint8* matrix_b, float* scale_a, float* scale_b, float* bias,
                        unsigned int m, unsigned int n, unsigned int k, unsigned int block_shape_m, unsigned int block_shape_n, unsigned int block_shape_k, bool ksplit, bool b_tiling) {
    printf("FP8 Block Scale GEMM calc start, the matrix M=%d N=%d K=%d\n", m, n, k);
    printf("Block scale dimensions: block_shape_m=%d, block_shape_n=%d, block_shape_k=%d\n", block_shape_m, block_shape_n, block_shape_k);
    
    // 打印一些调试信息
    printf("Sample FP8 values: matrix_a[0]=0x%02x, matrix_b[0]=0x%02x\n", 
           (uint8)matrix_a[0], (uint8)matrix_b[0]);
    printf("Sample scale values: scale_a[0]=%.3f, scale_b[0]=%.3f\n", 
           scale_a[0], scale_b[0]);

    // 计算block大小
    int block_m = (m + block_shape_m - 1) / block_shape_m;
    int block_n = (n + block_shape_n - 1) / block_shape_n;
    int block_k = (k + block_shape_k - 1) / block_shape_k;
    
    printf("Block sizes: block_m=%d, block_n=%d, block_k=%d\n", block_m, block_n, block_k);

    // 执行FP8 block scale GEMM计算
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float acc_f32 = 0.0f;         
            int block_i = i / block_shape_m;  // 当前行属于哪个block
            int block_j = j / block_shape_n;  // 当前列属于哪个block
        
            for (int t = 0; t < k; t++) {
                int block_t = t / block_shape_k;  // 当前K维度属于哪个block
            
                uint8 a_fp8 = matrix_a[i * k + t];
                uint8 b_fp8 = matrix_b[j * k + t];
                
                float a_f32 = IntMapToFloat(f8_to_f32(a_fp8, FP8_FMT, true));
                float b_f32 = IntMapToFloat(f8_to_f32(b_fp8, FP8_FMT, true));
                if (isnan(a_f32) || isnan(b_f32)) {
                    printf("Warning: NaN detected at [%d,%d,%d], a_fp8=0x%02x, b_fp8=0x%02x\n", 
                           i, j, t, (uint8)a_fp8, (uint8)b_fp8);
                    a_f32 = 0.0f; 
                    b_f32 = 0.0f;
                }

                float scale_a_val = scale_a[block_i * block_k + block_t];
                float scale_b_val = scale_b[block_j * block_k + block_t];
                
                float product = a_f32 * scale_a_val * b_f32 * scale_b_val;
                acc_f32 += product;
            }
          
            output_f32[i * n + j] = acc_f32;
            
            float f32_bias =  bias[j];
            float result_with_bias = acc_f32 + f32_bias;
            
            dst[i * n + j] = (unsigned short)FP32toBFP16(FloatMapToInt(result_with_bias));
        }
    }

    printf("FP8 Block Scale GEMM calculation completed\n");
    return true;
}


//Return 1 means succeed
template<typename T> uint32 check_result_eps(T *result, T *golden, int Mdim, int Ndim, int pad, int c_col_major, double eps) 
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
            double delta = 0.0;
            if(c_col_major)
            {
                delta = fabs((result[i * strideC + j] - golden[j * Ndim + i])/ golden[j * Ndim + i]);
            }
            else
            {
                delta = fabs((result[j * strideC + i] - golden[j * Ndim + i])/ golden[j * Ndim + i]);
            }
            //if ((c_col_major ? result[i * strideC + j] : result[j * strideC + i]) != golden[j * Ndim + i]) {
              if(delta > eps)
              {
                SameResult = 0;

                uint32 *aaa, *bbb;
                aaa = (uint32 *)&(c_col_major ? result[i * strideC + j] : result[j * strideC + i]);
                bbb = (uint32 *)&golden[j * Ndim + i];
                if (DEBUG) {
                printf("#######  diff index is [y = %d, x = %d]\n", j, i);
                printf("#######  gpu results      = %f   \n", (c_col_major ? result[i * strideC + j] : result[j * strideC + i]));
                printf("#######  golden           = %f   \n", golden[j * Ndim + i]);
                if (sizeof(T) == 4) {
                    printf("#######  gpu results hex  = %08x    \n", aaa[0]);
                    printf("#######  golden      hex  = %08x    \n", bbb[0]);
                } else if (sizeof(T) == 8) {
                        printf("#######  gpu results hex  = %08x %08x    \n", aaa[1], aaa[0]);
                        printf("#######  golden      hex  = %08x %08x    \n", bbb[1], bbb[0]);
                    }
                }

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

#include <cstdio>
#include <cstdint>
#include <cmath>
#include <type_traits>

// -----------------------------------------------------------------------------
// CVT function: Parses 2-byte BF16 data (stored in hexadecimal) into a decimal floating-point number
// Input: bf16_data - Pointer to BF16 data (2 bytes, uint16_t ensures unsigned access)
// Output: Corresponding decimal floating-point value of the BF16
// -----------------------------------------------------------------------------
float bf16_to_float(const uint16_t* bf16_data) {
    if (bf16_data == nullptr) {
        printf("Error: bf16_data is null pointer!\n");
        return NAN; 
    }
    const uint16_t bf16 = *bf16_data;
    const uint8_t S = (bf16 >> 15) & 0x01;      
    const uint8_t E = (bf16 >> 7) & 0xFF;       
    const uint8_t M = bf16 & 0x7F;               

    float value = 0.0f;
    if (E == 0) {
        value = (S ? -1.0f : 1.0f) * (static_cast<float>(M) / 128.0f) * powf(2.0f, -126.0f);
    } else if (E == 0xFF) {
        if (M == 0) {
            value = (S ? -INFINITY : INFINITY); 
        } else {
            value = NAN; 
        }
    } else {
        // （E≠0 and ≠255）：value = (-1)^S * (1 + M/2^7) * 2^(E-127)
        const float mantissa = 1.0f + (static_cast<float>(M) / 128.0f); 
        const float exponent = powf(2.0f, static_cast<float>(E) - 127.0f); 
        value = (S ? -1.0f : 1.0f) * mantissa * exponent;
    }

    return value;
}

template<>
uint32 check_result_eps<uint16_t>(uint16_t* result_bf16, uint16_t* golden_bf16, 
                                 int Mdim, int Ndim, int pad, int c_col_major, double eps) {

    const double rtol = 1e-2; 
    const double atol = 1e-2; 
    const double tol_err_ratio = 0.05;  
    
    uint32 SameResult = 1;
    const uint32 strideC = (c_col_major == 1) ? (Mdim + pad) : (Ndim + pad);
    int total_count = Mdim * Ndim;  
    int mismatch_count = 0;       

    printf("\n\n>>>>>>>>>>>>> \033[1m\033[;34m  CHECKING RESULTS (BF16 Type)  \033[0m  >>>>>>>>>>>>>>>>>>>>>>>\n");
    printf("Error tolerance: rtol=%.4f, atol=%.4f, max allowed mismatch ratio=%.2f%%\n",
           rtol, atol, tol_err_ratio * 100);

    for (int j = 0; j < Mdim; j++) { 
        for (int i = 0; i < Ndim; i++) { 
   
            const size_t result_idx = (c_col_major) ? 
                (i * strideC + j) : (j * strideC + i);   
            const size_t golden_idx = j * Ndim + i;

  
            const float result_val = bf16_to_float(&result_bf16[result_idx]);
            const float golden_val = bf16_to_float(&golden_bf16[golden_idx]);

            // |a - b| <= atol + rtol * |b|
            bool is_close = false;
            if (std::isnan(result_val) && std::isnan(golden_val)) {
                is_close = true;  
            } else if (std::isinf(result_val) && std::isinf(golden_val)) {
                is_close = (result_val > 0) == (golden_val > 0);  
            } else {
                const double abs_diff = fabs(static_cast<double>(result_val - golden_val));
                const double tolerance = atol + rtol * fabs(static_cast<double>(golden_val));
                is_close = (abs_diff <= tolerance);
            }

            if (!is_close) {
                mismatch_count++;
                printf("\n#######  Mismatch at [y=%d, x=%d]  #######\n", j, i);
                printf("         Result BF16 (Hex):  0x%04x\n", result_bf16[result_idx]);
                printf("         Result Value:       %.6f\n", result_val);
                printf("         Golden BF16 (Hex):  0x%04x\n", golden_bf16[golden_idx]);
                printf("         Golden Value:       %.6f\n", golden_val);
                if (!std::isnan(result_val) && !std::isnan(golden_val) &&
                    !std::isinf(result_val) && !std::isinf(golden_val)) {
                    const double abs_diff = fabs(static_cast<double>(result_val - golden_val));
                    const double tolerance = atol + rtol * fabs(static_cast<double>(golden_val));
                    printf("         Abs Diff:           %.6f (Tolerance: %.6f)\n", abs_diff, tolerance);
                }
            }
        }
    }
    
    const double mismatch_ratio = static_cast<double>(mismatch_count) / total_count;
    SameResult = (mismatch_ratio <= tol_err_ratio) ? 1 : 0;

    if (SameResult) {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;32m #TEST PASSED (BF16) \033[0m                      <<<<<<<<<<<<<<<<<<<<\n");
        printf("                  Total elements: %d, Mismatches: %d, Ratio: %.2f%% (<= %.2f%%)\n\n",
               total_count, mismatch_count, mismatch_ratio * 100, tol_err_ratio * 100);
    } else {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;35m #TEST FAILED (BF16) \033[0m!!!!!!!!!! !!!!!!!!!! <<<<<<<<<<<<<<<<<<<<\n");
        printf("                  Total elements: %d, Mismatches: %d, Ratio: %.2f%% (> %.2f%%)\n\n",
               total_count, mismatch_count, mismatch_ratio * 100, tol_err_ratio * 100);
    }

    return SameResult;
}



#if 0
template<typename T>
static uint32 check_result_ulp(T *result, T *golden, int Mdim, int Ndim, int pad, int c_col_major, int ulp_margin) 
{
    uint32 SameResult = 1;
    uint32 strideC;
    void *cpuOut, *gpuOut; 

    printf("\n\n>>>>>>>>>>>>> \033[1m\033[;34m  CHECKING RESULTS (ULP-BASED)  \033[0m  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n");

    if(c_col_major == 1) {
        strideC = Mdim + pad;
    }
    else {
      strideC = Ndim + pad;
    }

    for(int j = 0; j < Mdim; j++) {
        for(int i = 0; i < Ndim; i++) {
            
            int delta = 0;
            
            if (sizeof(T) == 1)
            {
                cpuOut = (uint8 *)&(golden[j * Ndim + i]);
                gpuOut = c_col_major? (uint8 *)&(result[i * strideC + j]) : (uint8 *)&(result[j * strideC + i]);

                delta = abs(*((uint8 *)gpuOut) - *((uint8 *)cpuOut));
            }
            else if (sizeof(T) == 2)
            {
                cpuOut = (uint16 *)&(golden[j * Ndim + i]);
                gpuOut = c_col_major? (uint16 *)&(result[i * strideC + j]) : (uint16 *)&(result[j * strideC + i]);

                delta = abs(*((uint16 *)gpuOut) - *((uint16 *)cpuOut));
            }
            else if (sizeof(T) == 4)
            {
                cpuOut = (uint32 *)&(golden[j * Ndim + i]);
                gpuOut = c_col_major? (uint32 *)&(result[i * strideC + j]) : (uint32 *)&(result[j * strideC + i]);

                delta = labs(*((uint32 *)gpuOut) - *((uint32 *)cpuOut));
            }
            else
            {
                cpuOut = (uint64 *)&(golden[j * Ndim + i]);
                gpuOut = c_col_major? (uint64 *)&(result[i * strideC + j]) : (uint64 *)&(result[j * strideC + i]);

                delta = llabs(*((uint64 *)gpuOut) - *((uint64 *)cpuOut));
            }

            //if ((c_col_major ? result[i * strideC + j] : result[j * strideC + i]) != golden[j * Ndim + i]) {
              if(delta > ulp_margin)
              {
                SameResult = 0;

                printf("#######  diff index is [y = %d, x = %d]\n", j, i);
 
                if (sizeof(T) == 1) {
                    printf("#######  gpu results hex  = %02x    \n", *((uint8 *)gpuOut));
                    printf("#######  golden      hex  = %02x    \n", *((uint8 *)cpuOut));
                }
                else if (sizeof(T) == 2) {
                    printf("#######  gpu results hex  = %04x    \n", *((uint16 *)gpuOut));
                    printf("#######  golden      hex  = %04x    \n", *((uint16 *)cpuOut));
                }
                else if (sizeof(T) == 4) {
                    printf("#######  gpu results hex  = %08x    \n", *((uint32 *)gpuOut));
                    printf("#######  golden      hex  = %08x    \n", *((uint32 *)cpuOut));
                } else if (sizeof(T) == 8) {

                    uint32 *aaa, *bbb;
                    aaa = (uint32 *)gpuOut;
                    bbb = (uint32 *)cpuOut;

                    printf("#######  gpu results hex  = %08x %08x    \n", aaa[1], aaa[0]);
                    printf("#######  golden      hex  = %08x %08x    \n", bbb[1], bbb[0]);
                }

                goto PRINT_RESULT;
            }
        }
    }

PRINT_RESULT:
    if (SameResult) {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;32m #TEST PASSED WITH ULP TOLERANCE OF %d\033[0m                      <<<<<<<<<<<<<<<<<<<<\n\n", ulp_margin);
    }
    else {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;35m #TEST FAILED WITH ULP TOLERANCE OF %d\033[0m!!!!!!!!!! !!!!!!!!!! <<<<<<<<<<<<<<<<<<<<\n\n", ulp_margin);
    }
    return SameResult;
}
#endif

#endif