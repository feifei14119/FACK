#ifndef COMMON_HELPER
#define COMMON_HELPER
/*
Defines various initializers, dumpers, checkers
*/
#include "common_mi300_f16.h"
#include <stdio.h>
#include <string.h>

#include <cstring>

//NOTE: FMHA_MI300 has big impact to f32<->f8 convertion in golden computation
//if FMHA_MI300 is defined, all f32<->f8 go into MI300 specification
//if FMHA_MI300 is not defined, all f8->f32 go into MI350 specification; f32->f8 goes into MI300 specification only when FP8 bias==true; FLOAT8E4M3FNUZ
//cpp file should define or undefine this macro before including header file
#ifdef FMHA_MI300
#include "common_mi300_fp8.h"
#else //MI350
#include "common_mi350_fp8.h"
#endif
#include "common_mi350_fp4.h"

const float  c1         = -0.071354f; //-2.0*0.035677f
const float  c2         = -1.59577f;  //-2.0*0.797885f
const uint32 c1Hex      = 0xbd92220c;
const uint32 c2Hex      = 0xbfcc4231;

#ifdef FMHA_MI300
static uint32 dot_num[TYPE_NUM] = {4, 4, 8, 1, 1, 1, 1, 1, 1};
#else
static uint32 dot_num[TYPE_NUM] = {8, 8, 16, 1, 1, 1, 1, 1, 1};
#endif

#define INIT_PATN_E8M0 18
inline int ceil_div(int a, int b) { return (a + b - 1) / b; }    
static void dump_float_in_value(cl_float* buffer, FILE *file, uint32 m, uint32 n) {
    for (int b = 0; b < m; b++) {
        for (int k = 0; k < n; k++) {
            fprintf(file, "%10.8f ", *(buffer + b*n+k));
        }
        fprintf(file, "\n");
    }
}

template<typename TT>
static void matrix_pad_zero(TT *buffer, uint32 M, uint32 N, uint32 posM, uint32 posN) {
    if (posM > M || posN > N) {
        printf("Invalid input M:%d, N:%d, posM:%d, posN:%d\n", M, N, posM, posN);
        assert(0);
    }
    for (uint32 m=posM; m < M; m++) {
        for (uint32 n=posN; n < N; n++) {
            *(buffer+m*N+n) = 0;
        }
    }
}

//N is fast changing dimension
//cropback from 0,0 to posM, posN
template<typename TT>
static void matrix_crop_back(TT *buffer, uint32 M, uint32 N, uint32 posM, uint32 posN, TT *out) {
    if (posM > M || posN > N) {
        printf("Invalid input M:%d, N:%d, posM:%d, posN:%d\n", M, N, posM, posN);
        assert(0);
    }
    for (uint32 m=0; m < posM; m++) {
        for (uint32 n=0; n < posN; n++) {
            *(out+m*posN+n) = *(buffer+m*N+n);
        }
    }
}

//buffer M*N, N is fast changing
template<typename TT>
static void matrix_reduce(TT* buffer, uint32 M, uint32 N, bool reduceInM, uint32 reduceSize) {
    if (reduceInM || reduceSize == 0) {
        //if reduce in M, actually need do nothing, just use less buffer
        return;
    }
    uint32 newN = N - reduceSize;
    //only reduce in fast chaning need this work
    TT* newBuffer = new TT[M*newN];

    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < newN; n++) {
            *(newBuffer+m*newN+n) = *(buffer+m*N+n);
        }
    }
    memcpy(buffer, newBuffer, M*newN*sizeof(TT));

    delete []newBuffer;
}

//e^(old_max-new_max) * old_o
void fmha_recompute_o(cl_float *o, cl_float *p_max_delta, int m, int n)
{
    for(int i = 0; i < m; i++)
    {
        //float e_max_delta = fmha_exp(p_max_delta[i], 1, 0);
        float e_max_delta = (float)pow(2.0, p_max_delta[i]);

        for(int j = 0; j < n; j++)
        {
            o[i * n + j] *= e_max_delta;
        }
    }
}

// `update_max_writeback` (default false): when true, write the cross-pass
// t_max back into l_max[0] at the end. The historical (default) behavior leaves
// l_max[0] containing only pass-0's max, with no other passes' maxes.
void fmha_combine_multi_pass(cl_float * l_o[], cl_float * l_sum[], cl_float * l_max[], cl_float s, int pass, int m, int n,
                             bool update_max_writeback = false)
{
    float s2E = s * f_log2E;

    if (pass == 1)
        return;

    cl_float *t_max = new cl_float[m];

    for(int i = 0; i < m; i++)
    {
        t_max[i] = *(l_max[0] + i);
        for(int pi = 1; pi < pass; pi++)
        {
             t_max[i] = (t_max[i] > *(l_max[pi] + i)) ? t_max[i] : *(l_max[pi] + i);
        }
    }

    for(int pi = 0; pi < pass; pi++)
    {
        for(int i = 0; i < m; i++)
        {
            float e_max_delta = (*(l_max[pi] + i) - t_max[i]);
            
            e_max_delta = e_max_delta * s2E;
            e_max_delta = (float)pow(2.0, e_max_delta);

            (*(l_sum[pi] + i)) *= e_max_delta;
            for(int j = 0; j < n; j++)
                 (*(l_o[pi] + i * n + j)) *= e_max_delta;
        }
    }

    for(int i = 0; i < m; i++)
    {
        t_max[i] = *(l_max[0] + i);
        for(int pi = 1; pi < pass; pi++)
        {
             (*(l_sum[0] + i)) += (*(l_sum[pi] + i));

              for(int j = 0; j < n; j++)
                 (*(l_o[0] + i * n + j)) += (*(l_o[pi] + i * n + j));
        }       
    }

    if (update_max_writeback)
    {
        for(int i = 0; i < m; i++)
        {
            float t = *(l_max[0] + i);
            for(int pi = 1; pi < pass; pi++)
            {
                if (*(l_max[pi] + i) > t) t = *(l_max[pi] + i);
            }
            *(l_max[0] + i) = t;
        }
    }

    delete [] t_max;
}


//////transpose function////////////////
//output fast change dim is in_other_dim////
template<typename TT>
static void fmha_matrix_transpose(TT *out, TT *in, int in_fast_change_dim, int in_other_dim, int other_dim_pad=0)
{
    TT *p = NULL;

    if(out == in)
        p = new TT[in_fast_change_dim * in_other_dim];
    else
        p = out;

    for(int i = 0; i < in_fast_change_dim; i++)
    {
        for(int j = 0; j < in_other_dim; j++)
        {
            p[i * in_other_dim + j] = (j >= in_other_dim - other_dim_pad) ? 0 : in[j * in_fast_change_dim + i];
        }
    }

    if(out == in)
    {
        memcpy(out, p, sizeof(TT)*in_fast_change_dim * in_other_dim);
        delete[] p;
    }
} 

//in  M*N        row-major, N is fast-changing
//out posM*posN  col-major, posM is fast-changing
template<typename TT>
static void matrix_crop_and_transpose(TT *in, TT *out, uint32 M, uint32 N, uint32 posM, uint32 posN) {
    TT *tmp = new TT[posM*posN];
    matrix_crop_back(in, M, N, posM, posN, tmp);
    fmha_matrix_transpose(out, tmp, posN, posM);
}

//////in is in_fast_change_dim*in_other_dim////////////////
//////out is in_fast_change_dim*(in_other_dim*group_in_n)
//////in short k*n -> k*(n*group_in_n)
template<typename TT>
static void fmha_matrix_broadcast(TT *out, TT *in, int in_fast_change_dim, int in_other_dim, int group_in_n)
{
    for(int i = 0; i < in_other_dim; i++)
    {
        for(int j = 0; j < group_in_n; j++)
        {
            memcpy(out+(i*group_in_n+j)*in_fast_change_dim, in+i*in_fast_change_dim, sizeof(TT)*in_fast_change_dim);
        }
    }
}

//in  M*N row-major, N is fast-changing
//out M*N col-major, M is fast-changing
template<typename TT>
static void moe_transpose(TT *out, TT *in, uint32 eprt, uint32 M, uint32 N) {
    uint32 offset = M*N;
    for(uint32 exprtIdx = 0; exprtIdx < eprt; exprtIdx++) {
        fmha_matrix_transpose(out+exprtIdx*offset, in+exprtIdx*offset, N, M);
    }
}

//in  M*N               row-major, N is fast-changing
//out (M*group_size)*N  row-major, N is fast-changing
template<typename TT>
static void moe_broadcast(TT *out, TT *in, uint32 eprt, uint32 M, uint32 N, int group_size) {
    uint32 offset_in = M*N;
    uint32 offset_out = M*N*group_size;
    for(uint32 exprtIdx = 0; exprtIdx < eprt; exprtIdx++) {
        fmha_matrix_broadcast(out+exprtIdx*offset_out, in+exprtIdx*offset_in, N, M, group_size);
    }
}

template<typename TT>
static void fmha_dumpMatrixInHex(TT *buffer,  FILE *file, int m, int n, DATA_TYPE in_type, int transpose = 0)
{
    fmha_dumpMatrixSplitKInHex(buffer, file, m, n, 0, n, in_type, transpose);
}

template<typename TT>
static void fmha_dumpMatrixSplitKInHex(TT *buffer,  FILE *file, int m, int n, int k_start, int k_len, DATA_TYPE in_type, int transpose = 0)
{
    if(transpose == 0)
    {
        for(int i = 0; i < m ; i++)
        {
            fprintf(file, "R[%04d]: ", i);
            for(int j = k_start; j < k_start+k_len; j++)
            {
                TT value;
                int offset = i*n+j;
                if (in_type == FP4) {
                    offset/=2;
                }
                value = buffer[offset];
                
                if((in_type == FP16) || (in_type == BF16))
                   fprintf(file, "0x%04x ", (*((uint32*)&value) & 0xffff));
                else if (in_type == FP8 || in_type == INT8) //FP8 INT8
                   fprintf(file, "0x%02x ", (*((uint32*)&value) & 0xff));
                else if (in_type == FP32 || in_type == INT32 || in_type == INT4) //FP32 INT32
                   fprintf(file, "0x%08x ", (*((uint32*)&value) & 0xffffffff));
                else if (in_type == FP4) {
                   uint4_t value4 = getFp4(value, (i*n+j)%2);
                   fprintf(file, "%01x ", value4.val);
                }
            }
            fprintf(file, "\n");
        }
    }
    else
    {
        for(int j = k_start; j < k_start+k_len; j++)
        {
            fprintf(file, "R[%04d]: ", j);
            for(int i = 0; i < m ; i++)
            {
                TT value;
                int offset = i*n+j;
                if (in_type == FP4) {
                    offset/=2;
                }
                value = buffer[offset];
                
                if((in_type == FP16) || (in_type == BF16))
                   fprintf(file, "0x%04x ", (*((uint32*)&value) & 0xffff));
                else if (in_type == FP8 || in_type == INT8) //FP8 INT8
                   fprintf(file, "0x%02x ", (*((uint32*)&value) & 0xff));
                else if (in_type == FP32 || in_type == INT32 || in_type == INT4) //FP32 INT32
                   fprintf(file, "0x%08x ", (*((uint32*)&value) & 0xffffffff));
                else if (in_type == FP4) {
                   uint4_t value4 = getFp4(value, (i*n+j)%2);
                   fprintf(file, "%01x ", value4.val);
                }
            }
            fprintf(file, "\n");
        }
    }
}

template<typename TT>
static void fmha_dump_batch_inHex(TT *buffer, const char *fileName, int batch, int head_num, int m, int n, DATA_TYPE in_type, int transpose = 0)
{
    FILE *file = fopen(fileName, "w+t");

    for(int b = 0; b < batch; b++)
    {
        for(int h = 0; h < head_num; h++)
        {
            fprintf(file, "++++Batch[%04d]---head[%04d]++++: \n", b, h);
            int offset = b*head_num*m*n+h*m*n;
            if (in_type == FP4) {
                offset/=2;
            }
            fmha_dumpMatrixInHex(buffer+offset, file, m, n, in_type, transpose);
        }
    }

    fclose(file);
}

// Merge a single sink logit into existing row-wise softmax stats.
// `row_data` (m x n, row-major, fast-changing n) is rescaled in-place by
// `row_scale = exp((old_max - new_max) * s)` whenever sink becomes the new max.
// Reusable for both P rows (n=kv_seq_len) and O numerators (n=dim_v).
//
// `sink` is in the PRE-SCALE raw domain (same domain as raw Q*K^T, BEFORE
// multiplying by s=1/sqrt(qk_head_dim)). To map AITER / FlashInfer / GPT-OSS
// post-scale logits into this convention: sink_raw = sink_post * sqrt(qk_head_dim).
// Math (matches MI350 SP3 mla_sink_merge / sim common_fmha::fmha_merge_sink_rowwise):
//   new_max   = max(old_max, sink)
//   row_scale = exp((old_max - new_max) * s)   // ==1 when sink <= old_max
//   sink_term = exp((sink    - new_max) * s)   // ==1 when sink == new_max
//   row_data *= row_scale
//   p_sum     = p_sum * row_scale + sink_term
//   p_max     = new_max
inline void fmha_merge_sink_rowwise(cl_float *row_data, cl_float s, int m, int n,
                                    cl_float *p_max, cl_float *p_sum, float sink,
                                    int dbg = 0, FILE *f_trace = NULL,
                                    const char *label = "sink_merge")
{
    float s2E = s * f_log2E;

    if (dbg && f_trace)
    {
        fprintf(f_trace, "++++%s++++BEFORE++++sink: 0x%08x\n", label, (*((uint32 *)&sink)));
        fprintf(f_trace, "++++%s++++BEFORE++++ROW_DATA: \n", label);
        fmha_dumpMatrixInHex(row_data, f_trace, m, n, FP32, 0);
        fprintf(f_trace, "++++%s++++BEFORE++++MAX: \n", label);
        fmha_dumpMatrixInHex(p_max, f_trace, 1, m, FP32, 0);
        fprintf(f_trace, "++++%s++++BEFORE++++SUM: \n", label);
        fmha_dumpMatrixInHex(p_sum, f_trace, 1, m, FP32, 0);
    }

    for (int i = 0; i < m; i++)
    {
        float old_max   = p_max[i];
        float new_max   = (old_max > sink) ? old_max : sink;
        float row_scale = (float)pow(2.0, (old_max - new_max) * s2E);
        float sink_term = (float)pow(2.0, (sink    - new_max) * s2E);

        if (row_scale != 1.0f)
        {
            for (int j = 0; j < n; j++)
                row_data[i * n + j] *= row_scale;
        }

        p_sum[i] = p_sum[i] * row_scale + sink_term;
        p_max[i] = new_max;
    }

    if (dbg && f_trace)
    {
        fprintf(f_trace, "++++%s++++AFTER++++sink: 0x%08x\n", label, (*((uint32 *)&sink)));
        fprintf(f_trace, "++++%s++++AFTER++++ROW_DATA: \n", label);
        fmha_dumpMatrixInHex(row_data, f_trace, m, n, FP32, 0);
        fprintf(f_trace, "++++%s++++AFTER++++MAX: \n", label);
        fmha_dumpMatrixInHex(p_max, f_trace, 1, m, FP32, 0);
        fprintf(f_trace, "++++%s++++AFTER++++SUM: \n", label);
        fmha_dumpMatrixInHex(p_sum, f_trace, 1, m, FP32, 0);
    }
}

template<typename TT>
static void fmha_batch_init(TT *buffer, int batch, int head_num, int seq_len, int head_dim, DATA_TYPE in_type, int init_pattern = 0, int fp_format = FP8_FMT, bool f8_bias = false, unsigned int kv128 = 0, bool is_scale=false)
{
    for(int b = 0; b < batch; b++)
    {
        for(int h = 0; h < head_num; h++)
        {
            for(int s = 0; s < seq_len; s++)
            {
                int flag_kv128 = 0;     //to indicate the save action in kv128 mode
                float temp_var_kv128;   //to save the 1st value in the kv128 mode
                unsigned int mask;
                if(kv128)               //in kv128 mode
                {
                    mask = (1 << (kv128 + 4)) - 1; //blk size is 16 as default
                    if ((s & mask) == 0)           //find the 1st value  
                        flag_kv128 = 1;
                    else
                        flag_kv128 = 0;
                }

                for(int d = 0; d < head_dim; d++)
                {
                    int offset = b * head_num * seq_len * head_dim  + h * seq_len * head_dim + s * head_dim + d;
 
                    float temp_var;
                    switch (init_pattern)
                    {
                        case 0:
                            temp_var = (float)gaussrand();
                            break;
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
                        case 11:
                            temp_var = 0.01*d;
                            break;
                        case 12:
                            temp_var = 0.01*s;
                            break;
                        default:
                            temp_var = 0;
                            break;
                    }

                    temp_var = std::abs(temp_var);
                    
                    if(kv128)
                    {
                        if (flag_kv128)
                            temp_var_kv128 = temp_var;  //save 1st value
                        temp_var = temp_var_kv128;      //set the value by 1st value 
                    }

                    switch(in_type)
                    {
                        case FP16:
                             buffer[offset] = (uint16)FP32toFP16(FloatMapToInt(temp_var));
                             //buffer[offset] = __float2half_rn(temp_var);
                             break;
                        case BF16:
                             buffer[offset] = (uint16)FP32toBFP16(FloatMapToInt(temp_var));
                             //buffer[offset] = __float2half_rn(temp_var);
                             break;
                        case FP8:
                             #ifdef FMHA_MI300
                             buffer[offset] = f32_to_f8(FloatMapToInt(temp_var), fp_format, f8_bias, false, 0);
                             #else
                             buffer[offset] = f32_to_fp8(FloatMapToInt(temp_var), 127, fp_format, f8_bias, true, false, 0);
                             #endif
                             break;
                        case FP32:
                             buffer[offset] = temp_var;
                             break;
                        case INT8: {
                             int8 value8 = (int8)(FloatMapToInt(temp_var)&0xff);
                             buffer[offset] = value8;
                             if (init_pattern >= INIT_PATN_E8M0) {
                                //init for FP4 e8m0 scale
                                //  pattern == INIT_PATN_E8M0 (18): random exp in [-3,+2] + 127
                                //  pattern >  INIT_PATN_E8M0      : force exp = 127 (e8m0 = 1.0)
                                // Mirrors mi400/common/common_fmha.h::fmha_batch_init.
                                int exp;
                                if (init_pattern == INIT_PATN_E8M0) {
                                    int range = 3;
                                    if (range == 0) {
                                        exp = 0;
                                    } else {
                                        exp = (rand()%(2*range)) - range;
                                    }
                                    exp += 127;
                                } else {
                                    exp = 127;
                                }
                                buffer[offset] = exp&0xFF;
                             }
                             break;
                        }
                        case INT4:
                             buffer[offset] = (uint32)(FloatMapToInt(temp_var));
                             break;
                        case FP4: {
                             uint4_t value4 = f32_to_fp4(FloatMapToInt(temp_var), 127, false, 0);
                             cl_char* ptr = (cl_char*)buffer;
                             setFp4(ptr+offset/2, value4, offset%2);
                             break;
                        }
                        default:
                             break;
                    }
                }//head_dim
            }//seq_len
        }//head_num
    }//batch
}

////////////////////////////////////////////////////////////////////////////
//  a[M][K]   b[K][N]   c[M][N]
//  c_matrix=a_matrix*b_matrix  
//  a b c is always row major
//  a fast changing is K; b fast changing is N
//  pointer type of c does not matter, it is converted to target type inside
//  if out_type is not specified, out_type will be changed inside according to in_type
////////////////////////////////////////////////////////////////////////////  
template<typename TT>
void fmha_matrix_mul(TT *a, TT *b, cl_float *c, int m, int n, int k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, DATA_LAYOUT klc=LAYOUT_NONE)
{
    matrix_multiple(a, b, c, m, n, k, 0, in_type, out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, klc);
}

////////////////////////////////////////////////////////////////////////////
//  a[M][K]   b[K][N]   c[M][N]
//  c_matrix=a_matrix*b_matrix  
//  a c is always row major
//  b is col major
//  a fast changing is K; b fast changing is K
//  pointer type of c does not matter, it is converted to target type inside
//  if out_type is not specified, out_type will be changed inside according to in_type
////////////////////////////////////////////////////////////////////////////  
template<typename TT>
void matrix_mul_fast_in_K(TT *a, TT *b, cl_float *c, int m, int n, int k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, DATA_LAYOUT klc=LAYOUT_NONE, int mixed_gemm = 0)
{
    matrix_multiple(a, b, c, m, n, k, 1, in_type, out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, klc, mixed_gemm);
}

template<typename TT>
void matrix_multiple(TT *a, TT *b, cl_float *c, int m, int n, int k, int fast_in_k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, DATA_LAYOUT klc=LAYOUT_NONE, int mixed_gemm = 0)
{
    matrix_multiple_splitK(a, b, c, m, n, k, fast_in_k, in_type, out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, 0, k, klc, mixed_gemm);
}

////////////////////////////////////////////////////////////////////////////
//  a[M][K]   b[K][N]   c[M][N]
//  c_matrix=a_matrix*b_matrix  
//  a c is always row major
//  if fast_in_k==1, b is col major, fast changing is K
//  if fast_in_k==0, b is row major, fast changing is N
//  a fast changing is K;
//  pointer type of c does not matter, it is converted to target type inside
//  if out_type is not specified, out_type will be changed inside according to in_type
////////////////////////////////////////////////////////////////////////////  
template<typename TT>
void matrix_multiple_splitK(TT *a, TT *b, cl_float *c, int m, int n, int k, int fast_in_k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, int k_start, int k_length, DATA_LAYOUT klc=LAYOUT_NONE, int mixed_gemm = 0)
{
    TT *pAbuffer = (TT *)a;
    TT *pBbuffer = (TT *)b;
    unsigned short *p1 = (unsigned short *)c;
    unsigned short *p2 = (unsigned short *)c;
    unsigned char  *p3 = (unsigned char *)c;
    int32          *p4 = (int32*)c;

#ifdef FMHA_MI300
    int off[32] = {0, 0, 0, 0, 4, 4, 4, 4, 8 ,8 ,8 ,8, 12, 12, 12, 12,
                 -12, -12, -12, -12, -8, -8, -8,- 8, -4, -4, -4, -4, 0, 0, 0, 0};
#endif

    if (out_type == TYPE_NUM) {
        out_type = FP32;
        if (in_type == INT8 || in_type == INT32) {
            out_type = INT32;
        }
        if (in_type == FP16 || in_type == BF16 || in_type == FP8) {
            out_type = FP32;
        }
    }

    if (k%(dot_num[in_type]) != 0) {
        //printf("dot_num[in_type:%d]:%d not divisible by k:%d!!!!!!!!!\n", in_type, dot_num[in_type], k);
    }

    for (int iii = 0; iii < m; ++iii)
    {
        for (int jjj = 0; jjj < n; ++jjj)
        {
            float f32_c = add_c ? c[iii * n + jjj] : 0;
            int32 int32_c = add_c ? p4[iii * n + jjj] : 0;
            for (int kkk = k_start; kkk < k_start+k_length; kkk = kkk + dot_num[in_type])
            {
               double result = 0.0f;
               int32 result_int32 = 0;
               int inner_k = (int)dot_num[in_type];
               if (kkk+((int)dot_num[in_type]) > k) {
                   inner_k = k-kkk;
               }
               for (int i = 0; i < inner_k; i++) 
               {
                   float f32_a = 0, f32_b = 0;
                   int32 int32_a = 0, int32_b = 0;
                   int i_off = i;
                   if(klc == LAYOUT_32X32)
                   {
                        #ifndef FMHA_MI300
                        if (in_type == FP16 || in_type == BF16) {
                          //swap 4-7 adding with 8-11 adding
                          //  0+4+8+12
                          //->0+8+4+12
                          if ((i >= 4) && ((kkk/8)%2 == 0))
                              i_off = i + 4;
                          else if ((i < 4) && ((kkk/8)%2 == 1))
                              i_off = i - 4;
                        } else if (in_type == FP8) {
                           //  0+4+8 +12+16+20+24+28
                           //->0+8+16+24+ 4+12+20+28
                           int real_idx = kkk + i;
                           int idx16_in32 = (real_idx%32)/16;
                           if (idx16_in32 == 0)
                               i_off = (i >> 2)*4 + i;
                           else
                               i_off = i - (3 - (i >> 2))*4;
                        }
                        #endif
                   } else if (klc == LAYOUT_16X16) {
                       if (in_type == FP16 || in_type == BF16) {
                           //  0+4 +8+12+16+20+24+28
                           #ifdef FMHA_MI300
                           //0+8+16+24+ 4+12+20+28
                           int real_idx = kkk + i;
                           i_off = i+off[real_idx%32];
                           #else
                           //->0+16+4+20+8 +24+12+28
                           int real_idx = kkk + i;
                           int step_in32 = (real_idx/8)%4;
                           int sub_off = step_in32*4;
                           int add_off = (3-step_in32)*4;
                           if ((real_idx/4)%2 == 0) {
                               i_off = i - sub_off;
                           } else {
                               i_off = i + add_off;
                           }
                           #endif
                       } 
                       #ifndef FMHA_MI300
                           else if (in_type == FP8) {
                           //  0+ 8+16+24+32+40+48+56
                           //->0+16+8 +24+32+48+40+56
                           int real_idx = kkk + i;
                           int step_in32 = (real_idx/8)%4;
                           if (step_in32 == 1) {
                               i_off = i + 8;
                           } else if (step_in32 == 2) {
                               i_off = i - 8;
                           }
                           
                       }
                       #endif
                   }
                   int a_idx = iii * k + kkk + i_off;
                   int b_idx = (kkk + i_off) * n + jjj; //N is fast changing
                   if (fast_in_k) {
                       b_idx = jjj * k + kkk + i_off; //K is fast changing
                   }
                   if(in_type == FP16)
                   {
                      f32_a = IntMapToFloat(FP16toFP32((uint32)pAbuffer[a_idx]));
                      f32_b = IntMapToFloat(FP16toFP32((uint32)pBbuffer[b_idx]));
                   }
                   else if(in_type == BF16)
                   {
                      f32_a = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[a_idx]));
                      f32_b = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[b_idx]));
                   }
                   else if (in_type == FP8)
                   {
                   #ifdef FMHA_MI300
                      if (mixed_gemm == 1) {
                      //in mixed gemm, buffer A is BF16, buffer B is T
                          cl_half *mix_Abuffer = (cl_half*) pAbuffer;
                          f32_a = IntMapToFloat(BFP16toFP32((uint32)mix_Abuffer[a_idx]));
                          f32_b = IntMapToFloat(f8_to_f32(pBbuffer[b_idx], fp_format_src1, f8_bias_src1));
                      }
                      else {
                          f32_a = IntMapToFloat(f8_to_f32(pAbuffer[a_idx], fp_format_src0, f8_bias_src0));
                          f32_b = IntMapToFloat(f8_to_f32(pBbuffer[b_idx], fp_format_src1, f8_bias_src1));
                      }
                   #else
                      if (mixed_gemm == 1) {
                      //in mixed gemm, buffer A is BF16, buffer B is T
                          cl_half *mix_Abuffer = (cl_half*) pAbuffer;
                          f32_a = IntMapToFloat(BFP16toFP32((uint32)mix_Abuffer[a_idx]));
                          f32_b = IntMapToFloat(f8_to_f32(pBbuffer[b_idx], fp_format_src1, f8_bias_src1));
                      }
                      else {
                          f32_a = IntMapToFloat(fp8_to_f32(pAbuffer[a_idx], 127, fp_format_src0, f8_bias_src0));
                          f32_b = IntMapToFloat(fp8_to_f32(pBbuffer[b_idx], 127, fp_format_src1, f8_bias_src1));
                      }
                   #endif
                   }
                   else if (in_type == INT8 || in_type == INT32)
                   {
                      int32_a = (int32)pAbuffer[a_idx];
                      int32_b = (int32)pBbuffer[b_idx];
                   } else if (in_type == FP32) {
                      f32_a = pAbuffer[a_idx];
                      f32_b = pBbuffer[b_idx];
                   } else {
                      printf("NOT SUPPORTED input data type:%d!!!!!!!!\n", in_type);
                   }
                   if (in_type != INT8 && in_type != INT32) {
                      result += (double)f32_a * (double)f32_b;
                   } else {
                      result_int32 += int32_a*int32_b;
                   }
               }
               if (in_type != INT8 && in_type != INT32) {
                   result += (double)f32_c;
                   f32_c = (float)result;
               } else {
                   result_int32 += int32_c;
                   int32_c = result_int32;
               }
            }
          
            switch(out_type)
            {
                case FP16:
                     p1[iii * n + jjj] = (unsigned short)FP32toFP16(FloatMapToInt(f32_c));
                     break;
                case BF16:
                     p2[iii * n + jjj] = (unsigned short)FP32toBFP16(FloatMapToInt(f32_c));
                     break;
                case FP8:
                     #ifdef FMHA_MI300
                     p3[iii * n + jjj] = f32_to_f8(FloatMapToInt(f32_c), fp_format_des, f8_bias_des, false, 0);
                     #else
                     p3[iii * n + jjj] = f32_to_fp8(FloatMapToInt(f32_c), 127, fp_format_des, f8_bias_des, true, false, 0);
                     #endif
                     break;
                case FP32:
                     c[iii * n + jjj]  = f32_c;
                     break;
                case INT32:
                     p4[iii * n + jjj] = int32_c;
                     break;
                default:
                     printf("NOT SUPPORTED output data type %d!!!!!!!!!\n", out_type);
                     break;
            }
        } // loop n
    }//loop m
}

////////////////////////////////////////////////////////////////////////////
//  a[M][K]   b[K][N]   c[M][N]
//  a_scale[M][K/gk] b_scale[K/gk][N]
//  c_matrix=a_matrix*b_matrix*a_scale*b_scale NOTE:block scale
//  a c a_scale is always row major
//  b b_scale is col major
//  a a_scale fast changing is K; b b_scale fast changing is K
//  pointer type of c does not matter, it is converted to target type inside
//  if out_type is not specified, out_type will be changed inside according to in_type
////////////////////////////////////////////////////////////////////////////  
template<typename TT, typename TScale>
void matrix_mul_block_scale_fast_in_K(TT *a, TT *b, cl_float *c, TScale *scale_a, TScale *scale_b, int m, int n, int k, int group_in_k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, DATA_LAYOUT klc=LAYOUT_NONE)
{
    matrix_multiple_block_scale(a, b, c, scale_a, scale_b, m, n, k, group_in_k, 1, in_type, out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, klc);
}

template<typename TT, typename TScale>
void matrix_multiple_block_scale(TT *a, TT *b, cl_float *c, TScale *scale_a, TScale *scale_b, int m, int n, int k, int group_in_k, int fast_in_k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, DATA_LAYOUT klc=LAYOUT_NONE)
{
    matrix_multiple_block_scale_splitK(a, b, c, scale_a, scale_b, m, n, k, group_in_k, fast_in_k, in_type, out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, 0, k, klc);
}

////////////////////////////////////////////////////////////////////////////
//  a[M][K]   b[K][N]   c[M][N]
//  a_scale[M][K/gk] b_scale[K/gk][N]
//  c_matrix=a_matrix*b_matrix*a_scale*b_scale NOTE:block scale
//  a c a_scale is always row major
//  if fast_in_k==1, b b_scale is col major, fast changing is K
//  if fast_in_k==0, b b_scale is row major, fast changing is N
//  a fast changing is K;
//  pointer type of c does not matter, it is converted to target type inside
//  if out_type is not specified, out_type will be changed inside according to in_type
////////////////////////////////////////////////////////////////////////////  
template<typename TT, typename TScale>
void matrix_multiple_block_scale_splitK(TT *a, TT *b, cl_float *c, TScale *scale_a, TScale *scale_b, int m, int n, int k, int group_in_k, int fast_in_k, DATA_TYPE in_type, DATA_TYPE out_type, int add_c, int fp_format_src0, bool f8_bias_src0, int fp_format_src1, bool f8_bias_src1, int fp_format_des, bool f8_bias_des, int k_start, int k_length, DATA_LAYOUT klc=LAYOUT_NONE)
{
    TT *pAbuffer = (TT *)a;
    TT *pBbuffer = (TT *)b;
    unsigned short *p1 = (unsigned short *)c;
    unsigned short *p2 = (unsigned short *)c;
    unsigned char  *p3 = (unsigned char *)c;
    int32          *p4 = (int32*)c;

#ifdef FMHA_MI300
    int off[32] = {0, 0, 0, 0, 4, 4, 4, 4, 8 ,8 ,8 ,8, 12, 12, 12, 12,
                 -12, -12, -12, -12, -8, -8, -8,- 8, -4, -4, -4, -4, 0, 0, 0, 0};
#endif

    if (out_type == TYPE_NUM) {
        out_type = FP32;
        if (in_type == INT8 || in_type == INT32) {
            out_type = INT32;
        }
        if (in_type == FP16 || in_type == BF16 || in_type == FP8) {
            out_type = FP32;
        }
    }

    if (k%(dot_num[in_type]) != 0) {
        printf("dot_num[in_type:%d]:%d not divisible by k:%d!!!!!!!!!\n", in_type, dot_num[in_type], k);
    }
    if (group_in_k%(dot_num[in_type]) != 0) {
        printf("dot_num[in_type:%d]:%d not divisible by group_in_k:%d!!!!!!!!!\n", in_type, dot_num[in_type], group_in_k);
        assert(0);
    }
    if (k%group_in_k != 0) {
        printf("group_in_k:%d not divisible by k:%d!!!!!!!!!\n", group_in_k, k);
        assert(0);
    }

    for (int iii = 0; iii < m; ++iii)
    {
        for (int jjj = 0; jjj < n; ++jjj)
        {
            float f32_c = add_c ? c[iii * n + jjj] : 0;
            int32 int32_c = add_c ? p4[iii * n + jjj] : 0;
            for (int sk = k_start; sk < k_start+k_length; sk += group_in_k) {
                int scaleidx = sk/group_in_k;
                TScale sa;
                if (scale_a != NULL) {
                    sa = *(scale_a + iii*(k/group_in_k) + scaleidx);
                }
                TScale sb;
                if (scale_b != NULL) {
                    sb = *(scale_b + scaleidx*n + jjj);
                    if (fast_in_k) {
                        sb = *(scale_b + jjj*(k/group_in_k) + scaleidx);
                    }
                }

                double result = 0.0f;
                int32 result_int32 = 0;
                for (int kkk = 0; kkk < group_in_k; kkk = kkk + dot_num[in_type])
                {
                   int inner_k = (int)dot_num[in_type];
                   if (sk+kkk+((int)dot_num[in_type]) > k) {
                       inner_k = k-sk-kkk;
                   }
                   for (int i = 0; i < inner_k; i++) 
                   {
                       float f32_a = 0, f32_b = 0;
                       int32 int32_a = 0, int32_b = 0;
                       int i_off = i;
                       if(klc == LAYOUT_32X32)
                       {
                            if (in_type == FP16 || in_type == BF16) {
                              //swap 4-7 adding with 8-11 adding
                              //  0+4+8+12
                              //->0+8+4+12
                              if ((i >= 4) && ((kkk/8)%2 == 0))
                                  i_off = i + 4;
                              else if ((i < 4) && ((kkk/8)%2 == 1))
                                  i_off = i - 4;
                            } else if (in_type == FP8) {
                               //  0+4+8 +12+16+20+24+28
                               //->0+8+16+24+ 4+12+20+28
                               int real_idx = kkk + i;
                               int idx16_in32 = (real_idx%32)/16;
                               if (idx16_in32 == 0)
                                   i_off = (i >> 2)*4 + i;
                               else
                                   i_off = i - (3 - (i >> 2))*4;
                            }
                       } else if (klc == LAYOUT_16X16) {
                           if (in_type == FP16 || in_type == BF16) {
                               //  0+4 +8+12+16+20+24+28
                               #ifdef FMHA_MI300
                               //0+8+16+24+ 4+12+20+28
                               int real_idx = kkk + i;
                               i_off = i+off[real_idx%32];
                               #else
                               //->0+16+4+20+8 +24+12+28
                               int real_idx = kkk + i;
                               int step_in32 = (real_idx/8)%4;
                               int sub_off = step_in32*4;
                               int add_off = (3-step_in32)*4;
                               if ((real_idx/4)%2 == 0) {
                                   i_off = i - sub_off;
                               } else {
                                   i_off = i + add_off;
                               }
                               #endif
                           } 
                           #ifndef FMHA_MI300
                               else if (in_type == FP8) {
                               //  0+ 8+16+24+32+40+48+56
                               //->0+16+8 +24+32+48+40+56
                               int real_idx = kkk + i;
                               int step_in32 = (real_idx/8)%4;
                               if (step_in32 == 1) {
                                   i_off = i + 8;
                               } else if (step_in32 == 2) {
                                   i_off = i - 8;
                               }
                               
                           }
                           #endif
                       }
                       int a_idx = iii * k + kkk + sk + i_off;
                       int b_idx = (kkk + sk + i_off) * n + jjj; //N is fast changing
                       if (fast_in_k) {
                           b_idx = jjj * k + kkk + sk + i_off; //K is fast changing
                       }
                       if(in_type == FP16)
                       {
                          f32_a = IntMapToFloat(FP16toFP32((uint32)pAbuffer[a_idx]));
                          f32_b = IntMapToFloat(FP16toFP32((uint32)pBbuffer[b_idx]));
                       }
                       else if(in_type == BF16)
                       {
                          f32_a = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[a_idx]));
                          f32_b = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[b_idx]));
                       }
                       else if (in_type == FP8)
                       {
                       #ifdef FMHA_MI300
                          f32_a = IntMapToFloat(f8_to_f32(pAbuffer[a_idx], fp_format_src0, f8_bias_src0));
                          f32_b = IntMapToFloat(f8_to_f32(pBbuffer[b_idx], fp_format_src1, f8_bias_src1));
                       #else
                          f32_a = IntMapToFloat(fp8_to_f32(pAbuffer[a_idx], 127, fp_format_src0, f8_bias_src0));
                          f32_b = IntMapToFloat(fp8_to_f32(pBbuffer[b_idx], 127, fp_format_src1, f8_bias_src1));
                       #endif
                       }
                       else if (in_type == INT8 || in_type == INT32)
                       {
                          int32_a = (int32)pAbuffer[a_idx];
                          int32_b = (int32)pBbuffer[b_idx];
                       } else if (in_type == FP32) {
                          f32_a = pAbuffer[a_idx];
                          f32_b = pBbuffer[b_idx];
                       } else if (in_type == FP4) {
                            uint4_t f4_a = getFp4(pAbuffer[a_idx/2], a_idx % 2);
                            uint4_t f4_b = getFp4(pBbuffer[b_idx/2], b_idx % 2);
                            f32_a = IntMapToFloat(fp4_to_f32(f4_a, 127));
                            f32_b = IntMapToFloat(fp4_to_f32(f4_b, 127));
                       } else {
                          printf("NOT SUPPORTED input data type:%d!!!!!!!!\n", in_type);
                       }
                       if (in_type != INT8 && in_type != INT32) {
                          result += (double)f32_a * (double)f32_b;
                       } else {
                          result_int32 += int32_a*int32_b;
                       }
                   }
                }
                if (in_type == FP4 || in_type == FP8) {
                    //scale in E8M0
                    if (scale_a != NULL) {
                        float scaleA = (float)pow(2, sa-127);
                        result *= (double) scaleA;
                    }
                    if (scale_b != NULL) {
                        float scaleB = (float)pow(2, sb-127);
                        result *= (double) scaleB;
                    }
                } else if (in_type != INT8 && in_type != INT32) {
                    result *= sa;
                    result *= sb;
                } else {
                    float fresult = V_CVT_F32_I32(result_int32);
                    fresult *= sa;
                    fresult *= sb;
                    result_int32 = V_CVT_I32_F32(fresult);
                }
                if (in_type != INT8 && in_type != INT32) {
                    result += (double)f32_c;
                    f32_c = (float)result;
                } else {
                   result_int32 += int32_c;
                   int32_c = result_int32;
                }
            }
          
            switch(out_type)
            {
                case FP16:
                     p1[iii * n + jjj] = (unsigned short)FP32toFP16(FloatMapToInt(f32_c));
                     break;
                case BF16:
                     p2[iii * n + jjj] = (unsigned short)FP32toBFP16(FloatMapToInt(f32_c));
                     break;
                case FP8:
                     #ifdef FMHA_MI300
                     p3[iii * n + jjj] = f32_to_f8(FloatMapToInt(f32_c), fp_format_des, f8_bias_des, false, 0);
                     #else
                     p3[iii * n + jjj] = f32_to_fp8(FloatMapToInt(f32_c), 127, fp_format_des, f8_bias_des, true, false, 0);
                     #endif
                     break;
                case FP32:
                     c[iii * n + jjj]  = f32_c;
                     break;
                case INT32:
                     p4[iii * n + jjj] = int32_c;
                     break;
                default:
                     printf("NOT SUPPORTED output data type %d!!!!!!!!!\n", out_type);
                     break;
            }
        } // loop n
    }//loop m
}

void fmha_o_div_by_sum(cl_float *o, cl_float *p_sum, int m, int n)
{
    for(int i = 0; i < m; i++)
    {
        float sum = (p_sum[i] == 0.0) ? 1.0 : (float)(1.0 / (double)p_sum[i]);
        for(int j = 0; j < n; j++)
        {
            o[i * n + j] *= sum;
        }
    }
}

//in is M*N row-major, fast-changing is N;
//out is blockM*blockN row-major, fast-changing is blockN
//crop a block size of blockM*blockN, top-left coordinate is idxM, idxN
template<typename TT>
static void matrix_crop_block(TT *in, TT *out, uint32 M, uint32 N, uint32 idxM, uint32 idxN, uint32 blockM, uint32 blockN) {
    for (uint32 blockM_idx = 0; blockM_idx < blockM; blockM_idx++) {
        for (uint32 blockN_idx = 0; blockN_idx < blockN; blockN_idx++) {
            out[blockM_idx*blockN + blockN_idx] = in[(idxM+blockM_idx)*N + idxN + blockN_idx];
        }
    }
    return;
}

//to is M*N row-major, fast-changing is N;
//from is blockM*blockN row-major, fast-changing is blockN
//crop a block size of blockM*blockN, top-left coordinate is idxM, idxN
template<typename TT>
static void matrix_fill_block(TT *from, TT *to, uint32 M, uint32 N, uint32 idxM, uint32 idxN, uint32 blockM, uint32 blockN) {
    for (uint32 blockM_idx = 0; blockM_idx < blockM; blockM_idx++) {
        for (uint32 blockN_idx = 0; blockN_idx < blockN; blockN_idx++) {
            to[(idxM+blockM_idx)*N + idxN + blockN_idx] = from[blockM_idx*blockN + blockN_idx] ;
        }
    }
    return;
}

//softmax functions//////
void fmha_softmax_dev(cl_float *a, cl_float s, int m, int n, int start, cl_float *p_max = NULL, cl_float *p_max_delta = NULL, cl_float *p_sum = NULL, DATA_LAYOUT klc = LAYOUT_NONE, DATA_TYPE type = FP16, int max_fix=1)
{
    float s2E = s * f_log2E;
    int   sum_step = n;
    float min_f32 = 0;

    *((uint32 *)&min_f32) = 0xff7fffff;

    if (s2E > 1.0) {
        min_f32 /= s2E;
    }

    for(int i = 0; i < m; i++)
    {
        float em  = 0.0;
        float sum = 0.0;
        float klc_tmp_sum0 = 0.0;
        float klc_tmp_sum1 = 0.0;
        float klc_tmp_sum2 = 0.0;
        float klc_tmp_sum3 = 0.0;
        float klc_tmp_sum01 = 0.0;
        float klc_tmp_sum11 = 0.0;
        float klc_tmp_sum21 = 0.0;
        float klc_tmp_sum31 = 0.0;

        if(start)
            em  = (max_fix == 0) ? a[i * n + 0] : ((a[i * n + 0] > min_f32) ? a[i * n + 0] : min_f32);
        else
            em  = p_max[i];

        for(int j = 0; j < n; j++)
        {
            em = (em > a[i * n + j]) ? em : a[i * n + j];
        }

        if(!start)
        {
            //save max_delta
            p_max_delta[i] = p_max[i] - em;
            p_max_delta[i] = p_max_delta[i] * s2E;

            //e^(old_max-new_max) * old_sum
            sum = p_sum[i] * (float)pow(2.0, p_max_delta[i]);
            //save max
            p_max[i] = em;
        }
        else if(p_max != NULL)
           p_max[i] = em;

        for(int j = 0; j < n; j++)
        {
            float max_slog2E = em * s2E;

            a[i * n + j] = (float)pow(2.0, (a[i * n + j] *s2E - max_slog2E));

            if (klc == LAYOUT_32X32)
            {
                if (type == FP8)
                {
                    if(j%8 < 4)
                    {
                        if(j%2 == 0)
                           klc_tmp_sum0+=a[i * n + j];
                        else
                           klc_tmp_sum1+=a[i * n + j];
                    }
                    else
                    {
                        if(j%2 == 0)
                           klc_tmp_sum2+=a[i * n + j];
                        else
                           klc_tmp_sum3+=a[i * n + j];
                    }
                    
                    if (j%sum_step == (sum_step-1))
                    {
                        klc_tmp_sum0 += klc_tmp_sum1;
                        klc_tmp_sum2 += klc_tmp_sum3;
                        klc_tmp_sum0 += klc_tmp_sum2;
                    
                        sum += klc_tmp_sum0;
                        klc_tmp_sum0 = 0.0;
                        klc_tmp_sum1 = 0.0;
                        klc_tmp_sum2 = 0.0;
                        klc_tmp_sum3 = 0.0;
                    }
                }
                else
                {
                    if(j%8 < 4)
                        klc_tmp_sum0+=a[i * n + j];
                    else
                        klc_tmp_sum1+=a[i * n + j];
                    
                    if (j%sum_step == (sum_step-1))
                    {
                        klc_tmp_sum0 += klc_tmp_sum1;
                        sum += klc_tmp_sum0;
                        klc_tmp_sum0 = 0.0;
                        klc_tmp_sum1 = 0.0;
                    }
                }
            } else if (klc == LAYOUT_16X16) {
                if (type == FP8) {
                    int step = j%16;
                    if(step < 4) {
                        if (step%2 == 0)
                            klc_tmp_sum0+=a[i * n + j];
                        else
                            klc_tmp_sum01+=a[i * n + j];
                    }
                    else if (step >= 4 && step < 8) {
                        if (step%2 == 0)
                            klc_tmp_sum1+=a[i * n + j];
                        else
                            klc_tmp_sum11+=a[i * n + j];
                    }
                    else if (step >= 8 && step < 12) {
                        if (step%2 == 0)
                            klc_tmp_sum2+=a[i * n + j];
                        else
                            klc_tmp_sum21+=a[i * n + j];
                    }
                    else if (step >= 12 && step < 16) {
                        if (step%2 == 0)
                            klc_tmp_sum3+=a[i * n + j];
                        else
                            klc_tmp_sum31+=a[i * n + j];
                    }

                    if (j%sum_step == (sum_step-1))
                    {
                        klc_tmp_sum0 += klc_tmp_sum01;
                        klc_tmp_sum1 += klc_tmp_sum11;
                        klc_tmp_sum2 += klc_tmp_sum21;
                        klc_tmp_sum3 += klc_tmp_sum31;
                        
                        klc_tmp_sum0 += klc_tmp_sum2;
                        klc_tmp_sum1 += klc_tmp_sum3;
                        klc_tmp_sum0 += klc_tmp_sum1;
                        sum += klc_tmp_sum0;
                        klc_tmp_sum0 = 0.0;
                        klc_tmp_sum1 = 0.0;
                        klc_tmp_sum2 = 0.0;
                        klc_tmp_sum3 = 0.0;
                        klc_tmp_sum01 = 0.0;
                        klc_tmp_sum11 = 0.0;
                        klc_tmp_sum21 = 0.0;
                        klc_tmp_sum31 = 0.0;
                    }
                } else {
                    int step = j%16;
                    if(step < 4)
                        klc_tmp_sum0+=a[i * n + j];
                    else if (step >= 4 && step < 8)
                        klc_tmp_sum1+=a[i * n + j];
                    else if (step >= 8 && step < 12)
                        klc_tmp_sum2+=a[i * n + j];
                    else if (step >= 12 && step < 16)
                        klc_tmp_sum3+=a[i * n + j];

                    if (j%sum_step == (sum_step-1))
                    {
                        klc_tmp_sum0 += klc_tmp_sum2;
                        klc_tmp_sum1 += klc_tmp_sum3;
                        klc_tmp_sum0 += klc_tmp_sum1;
                        sum += klc_tmp_sum0;
                        klc_tmp_sum0 = 0.0;
                        klc_tmp_sum1 = 0.0;
                        klc_tmp_sum2 = 0.0;
                        klc_tmp_sum3 = 0.0;
                    }
                }
            }
            else
                sum = sum + a[i * n + j];
        }

        p_sum[i] = sum;
    }
}

static float Gelu(float x) {
    float u   = x * (c1 * x * x + c2);
    float emu = pow (2.0, u * f_log2E);
    float y   = x / (1.0f + emu);
    return y;
}

static float Silu(float x) {
//silu(x) = x/(1+ e^(-x))
    float u   = (float) -x;
    float emu = pow (2.0, u * f_log2E);
    float y   = x / (1.0f + emu);
    return y;
}

//in's dimension is M*N
//quant's dimension is 1*N
//fast changing dimension is N
//out = in * quant;
static void smooth_quant(float *in, float *quant, uint32 M, uint32 N, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * quant[n];
        }
    }
}

static void smooth_quant_per_block(float *in, float *quant, uint32 M, uint32 N, uint32 blk_size, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * quant[n / blk_size];
        }
    }
}

//in's dimension is M*N
//scale's dimension is M*1
//fast changing dimension is N
//out = in * quant;
//actually copied from common_pa.h, which is developed later than moe, so just copy back, don't want bother change common_pa.h again
static void moe_dequant_onCol(float *in, float *scale, uint32 M, uint32 N, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * scale[m];
        }
    }
}

//in's dimension is M*N
//dequant_vec_out's dimension is M*1
//dbg_max_out's dimension is M*2, first column is abs(max), second column is max
//fast changing dimension is N
//first generate dequant_vec_out 
//out = in / dequant_vec_out;
//NOTE, the computation sequence here matters, may impact bit-match with kernel
static void quant(float *in, float *dequant_vec_out, uint32 M, uint32 N, float qnt_deno, float *out = NULL, float *dbg_max_out = NULL) {
    if (out == NULL) {
        out = in;
    }

    float *scaleOriginQuant = new float[M];
    //find largest absolute value in each row and put it into dequant_vec
    float rowMax;
    for (uint32 m = 0; m < M; m++) {
        rowMax = 1e-6;
        dequant_vec_out[m]  = rowMax/qnt_deno;
        scaleOriginQuant[m] = qnt_deno/rowMax;
        if (dbg_max_out != NULL) {
            dbg_max_out[m*2]    = rowMax;
            dbg_max_out[m*2+1]  = rowMax;
        }

        for (uint32 n = 0; n < N; n++) {
            float absValue = abs(in[m*N+n]);
            if (absValue > rowMax) {
                rowMax = absValue;
                dequant_vec_out[m]  = rowMax/qnt_deno;
                scaleOriginQuant[m] = qnt_deno/rowMax;
                if (dbg_max_out != NULL) {
                    dbg_max_out[m*2]    = rowMax;
                    dbg_max_out[m*2+1]  = in[m*N+n];
                }
            }
        }
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = in[m*N+n] * scaleOriginQuant[m];
        }
    }

    delete []scaleOriginQuant;
}

//same name is dsv3, 1D block quant
//in's dimension is M*N
//dequant_vec_out's dimension is M*(N/block_size)
//dbg_max_out's dimension is M*(2*N/block_size), first column is abs(max), second column is max
//fast changing dimension is N
//first generate dequant_vec_out
//out = in / dequant_vec_out;
//NOTE, the computation sequence here matters, may impact bit-match with kernel
static void act_quant(float *in, float *dequant_vec_out, uint32 M, uint32 N, uint32 block_size, float qnt_deno, float *out = NULL, float *dbg_max_out = NULL) {
    if (N % block_size != 0) {
        printf("block_size:%d not divisible by N:%d\n", block_size, N);
        assert(0);
    }
    if (out == NULL) {
        out = in;
    }
    uint32 scaleN = N/block_size;

    float *scaleOriginQuant = new float[M*scaleN];
    //find largest absolute value in each block and put it into dequant_vec
    float rowMax;
    for (uint32 m = 0; m < M; m++) {
        for (uint32 s = 0; s < scaleN; s++) {
            rowMax = 1e-6;
            *(dequant_vec_out + m*scaleN + s)  = rowMax/qnt_deno;
            *(scaleOriginQuant+ m*scaleN + s)  = qnt_deno/rowMax;
            if (dbg_max_out != NULL) {
                *(dbg_max_out + m*scaleN*2 + 2*s)      = rowMax;
                *(dbg_max_out + m*scaleN*2 + 2*s + 1)  = rowMax;
            }
            for (uint32 n = s*block_size; n < (s+1)*block_size; n++) {
                float absValue = abs(in[m*N+n]);
                if (absValue > rowMax) {
                    rowMax = absValue;
                    *(dequant_vec_out + m*scaleN + s)  = rowMax/qnt_deno;
                    *(scaleOriginQuant+ m*scaleN + s)  = qnt_deno/rowMax;
                    if (dbg_max_out != NULL) {
                        *(dbg_max_out + m*scaleN*2 + 2*s)      = rowMax;
                        *(dbg_max_out + m*scaleN*2 + 2*s + 1)  = rowMax;
                    }
                }
            }
            for (uint32 n = s*block_size; n < (s+1)*block_size; n++) {
                out[m*N+n] = in[m*N+n] * scaleOriginQuant[m*scaleN + s];
            }
        }
    }

    delete []scaleOriginQuant;
}

static uint8 e8m0fnu_from_fp32_value(float in) {
    uint32 f_bits   = FloatMapToInt(in);
    uint8  exponent = BEXP32(f_bits);

    // special case float32 NaN and +-inf to map to e8m0 nan
    if (exponent == 0xff) {
        return exponent;
    }

    // next, we use guard, round, sticky bits and the LSB to implement round to
    // nearest, with ties to even

    // guard bit - bit 23, or 22 zero-indexed
    uint8_t g = (f_bits & 0x400000) > 0;
    // round bit - bit 22, or 21 zero-indexed
    uint8_t r = (f_bits & 0x200000) > 0;
    // sticky bit - bits 21 to 1, or 20 to 0 zero-indexed
    uint8_t s = (f_bits & 0x1FFFFF) > 0;
    // in casting to e8m0, LSB is the implied mantissa bit. It equals to 0 if the
    // original float32 is denormal, and to 1 if the original float32 is normal.
    uint8_t lsb = exponent > 0;

    // implement the RNE logic
    bool round_up = false;
    // if g == 0, round down (no-op)
    if (g == 1) {
        if ((r == 1) || (s == 1)) {
            // round up
            round_up = true;
        } else {
            if (lsb == 1) {
                // round up
                round_up = true;
            }
          // if lsb == 0, round down (no-op)
        }
    }

    if (round_up) {
        // adjust exponent
        // note that if exponent was 255 we would have already returned earlier, so
        // we know we can add one safely without running out of bounds
        exponent++;
    }

    return exponent;
}

static float fp32_from_e8m0(uint8 exponent) {
    uint32 ret = exponent << 23;
    if (exponent == 0) {
        ret = 0x00400000;
    } else if (exponent == 0xff) {
        ret = 0x7f800001;
    }
    return IntMapToFloat(ret);
}

//in's dimension is M*N
//dequant_vec_out's dimension is M*(N/block_size)
//dbg_max_out's dimension is M*(2*N/block_size), first column is abs(max), second column is max
//fast changing dimension is N
//first generate dequant_vec_out
//out = in / dequant_vec_out;
//NOTE, the computation sequence here matters, may impact bit-match with kernel
static void mxFPX_quant(float *in, uint8 *dequant_vec_out, uint32 M, uint32 N, uint32 block_size, float qnt_deno, DATA_TYPE type, float *out = NULL, float *dbg_max_out = NULL) {
    if (N % block_size != 0) {
        printf("block_size:%d not divisible by N:%d\n", block_size, N);
        assert(0);
    }
    if (out == NULL) {
        out = in;
    }
    cl_char *fp4out = (cl_char*)out;
    uint32 scaleN = N/block_size;

    float *scaleOriginQuant = new float[M*scaleN];
    //find largest absolute value in each block and put it into dequant_vec
    float rowMax;
    for (uint32 m = 0; m < M; m++) {
        for (uint32 s = 0; s < scaleN; s++) {
            rowMax = 1e-6;
            uint8 e8m0 = e8m0fnu_from_fp32_value(rowMax/qnt_deno);
            float scale = fp32_from_e8m0(e8m0);
            *(dequant_vec_out + m*scaleN + s)  = e8m0;
            *(scaleOriginQuant+ m*scaleN + s)  = 1/scale;
            if (dbg_max_out != NULL) {
                *(dbg_max_out + m*scaleN*2 + 2*s)      = rowMax;
                *(dbg_max_out + m*scaleN*2 + 2*s + 1)  = rowMax;
            }
            for (uint32 n = s*block_size; n < (s+1)*block_size; n++) {
                float absValue = abs(in[m*N+n]);
                if (absValue > rowMax) {
                    rowMax = absValue;
                    e8m0 = e8m0fnu_from_fp32_value(rowMax/qnt_deno);
                    scale = fp32_from_e8m0(e8m0);
                    *(dequant_vec_out + m*scaleN + s)  = e8m0;
                    *(scaleOriginQuant+ m*scaleN + s)  = 1/scale;
                    if (dbg_max_out != NULL) {
                        *(dbg_max_out + m*scaleN*2 + 2*s)      = rowMax;
                        *(dbg_max_out + m*scaleN*2 + 2*s + 1)  = rowMax;
                    }
                }
            }

            //divide by scale; convert later
            for (uint32 n = s*block_size; n < (s+1)*block_size; n++) {
                out[m*N+n] = in[m*N+n] * scaleOriginQuant[m*scaleN + s];
            }
            /*
            //divide by scale by using f32_to_fp4 with e8m0; so, scale and convert all together
            for (uint32 n = s*block_size; n < (s+1)*block_size; n++) {
                uint32 offset = m*N+n;
                if (type == FP4) {
                    setFp4(fp4out+offset/2, f32_to_fp4(FloatMapToInt(in[offset]), e8m0, false, 0), offset%2);
                } else {
                    printf("NONE supported mxFPX_quant type:%d\n", type);
                }
            }*/
        }
    }

    delete []scaleOriginQuant;
}

//in's dimension is M*N
//dequant_matrix's dimension is M*N
//fast changing dimension is N
//out = in * dequant_matrix * weight;
static void dequant(float *in, float *dequant_matrix, uint32 M, uint32 N, float *out = NULL, float weight=1.0f) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * dequant_matrix[m*N + n] * weight;
        }
    }
}

//in's dimension is M*N
//weight's dimension is M*1
//dequant_matrix's dimension is M*N
//fast changing dimension is N
//out = in * dequant_matrix * weight;
static void dequant_with_weight_vec(float *in, float *dequant_matrix, uint32 M, uint32 N, float *weight_vec, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * dequant_matrix[m*N + n] * weight_vec[m];
        }
    }
}

//in's dimension is M*N
//fast changing dimension is N
//out = f32_to_i8(in);
static void matrix_v_cvt_i8_f32(float *in, uint32 M, uint32 N, int8 *out = NULL) {
    if (out == NULL) {
        out = (int8*) in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = (int8)V_CVT_I32_F32(in[m*N+n]);
        }
    }
}

template<typename TT>
static void matrix_v_cvt_to_type(float *in, TT *output, int M, int N, DATA_TYPE out_type, int fp_format_des, bool f8_bias_des) {
//    fmha_cvt_output's inner INT8 target assumes input is INT32; which is not the case here.
    if (out_type == INT8) {
        matrix_v_cvt_i8_f32(in, M, N);
    } else {
        fmha_cvt_output(in, output, M, N, out_type, fp_format_des, f8_bias_des);
    }
}

//in's dimension is M*N
//fast changing dimension is N
//out = i32_to_f32(in);
static void matrix_v_cvt_f32_i32(int32 *in, uint32 M, uint32 N, float *out = NULL) {
    if (out == NULL) {
        out = (float*) in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = V_CVT_F32_I32(in[m*N+n]);
        }
    }
}

//in's dimension is M*N
//fast changing dimension is N
//out = GELU(in);
static void matrix_GELU(float *in, uint32 M, uint32 N, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = Gelu(in[m*N+n]);
        }
    }
}

//in's dimension is M*N
//fast changing dimension is N
//out = Silu(in);
static void matrix_SILU(float *in, uint32 M, uint32 N, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = Silu(in[m*N+n]);
        }
    }
}

//in's dimension is M*N
//fast changing dimension is N
//out = out * weight;
static void matrix_multi_weight(float *in, uint32 M, uint32 N, float weight, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N+n] = in[m*N+n]*weight;
        }
    }
}

//in's dimension is M*N
//weight's dimension is M*1
//fast changing dimension is N
//out = in * weight_vec;
static void matrix_multi_weight_vec(float *in, uint32 M, uint32 N, float* weight_vec, float *out = NULL) {
    if (out == NULL) {
        out = in;
    }
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            out[m*N + n] = in[m*N + n] * weight_vec[m];
        }
    }
}

//fast-changing is N
//c = a * b;
static void matrix_multiple(cl_float *a, cl_float* b, cl_float *c, uint32 M, uint32 N) {
    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            c[m*N + n] = a[m*N + n] * b[m*N + n];
        }
    }
}

//in's dimension is M*N
//fast changing dimension is N
//c = a + b;
//this is to simulate atomic_add in memory; reference tcc.cpp around line:5716
template<typename TT>
static void matrix_accumlate(TT *a, TT* b, cl_float *c, uint32 M, uint32 N, DATA_TYPE in_type, DATA_TYPE out_type) {
    TT *pAbuffer = (TT *)a;
    TT *pBbuffer = (TT *)b;
    unsigned short *p1 = (unsigned short *)c;
    unsigned short *p2 = (unsigned short *)c;
    //unsigned char  *p3 = (unsigned char *)c;
    //int32          *p4 = (int32*)c;

    if (out_type == TYPE_NUM) {
        out_type = in_type;
    }

    for (uint32 m = 0; m < M; m++) {
        for (uint32 n = 0; n < N; n++) {
            float f32_a = 0, f32_b = 0, f32_c = 0;
            if(in_type == FP16) {
                f32_a = IntMapToFloat(FP16toFP32((uint32)pAbuffer[m*N + n]));
                f32_b = IntMapToFloat(FP16toFP32((uint32)pBbuffer[m*N + n]));
            } else if(in_type == BF16) {
                f32_a = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[m*N + n]));
                f32_b = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[m*N + n]));
            } else if (in_type == FP32) {
                f32_a = (float)pAbuffer[m*N + n];
                f32_b = (float)pBbuffer[m*N + n];
            } else {
                printf("NOT SUPPORTED input data type %d!!!!!!!!!\n", in_type);
            }
            f32_c = f32_a + f32_b;
            switch(out_type)
            {
                case FP16:
                     p1[m*N + n] = (unsigned short)FP32toFP16(FloatMapToInt(f32_c));
                     break;
                case BF16:
                     p2[m*N + n] = (unsigned short)FP32toBFP16(FloatMapToInt(f32_c));
                     break;
                case FP32:
                     c[m*N + n]  = f32_c;
                     break;
                default:
                     printf("NOT SUPPORTED output data type %d!!!!!!!!!\n", out_type);
                     break;
            }
        }
    }
}

//Input M*N row-major, N is fast-changing
//majorInN means for the little tile block, its data fast-changing dimension; it's also fast-changing dimension between tiles
//i think tileSizeMajor is how many points to form 4 words, for FP16, it should be 8
//tileSizeMinor is related to XDL instructions, for 16x16 it should be 16, for 32x8 it should be 32
template<typename TT>
void fmha_shuffle_one(TT *buffer, uint32 M, uint32 N, bool majorInN=true, uint32 tileSizeMajor=8, uint32 tileSizeMinor=16) {
    uint32 tilesInM;
    uint32 tilesInN;
    uint32 tileStride = tileSizeMajor*tileSizeMinor;

    if (majorInN) {
        if (M % tileSizeMinor != 0 || N % tileSizeMajor != 0) {
            printf("Not divisible M:%d,tileSizeMinor:%d N:%d,tileSizeMajor:%d\n", M, tileSizeMinor, N, tileSizeMajor);
            assert(0);
        }
        if ((M % tileSizeMinor)%2 != 0) {
            printf("Warning!!!!! If UP is enabled, this size in M cannot be divided into Gate/Up evenly\n!!!!!!!!!!!");
        }
        tilesInM = (M+tileSizeMinor-1)/tileSizeMinor;
        tilesInN = (N+tileSizeMajor-1)/tileSizeMajor;
    } else {
        if (M % tileSizeMajor != 0 || N % tileSizeMinor != 0) {
            printf("Not divisible M:%d,tileSizeMajor:%d N:%d,tileSizeMinor:%d\n", M, tileSizeMajor, N, tileSizeMinor);
            assert(0);
        }
        tilesInM = (M+tileSizeMajor-1)/tileSizeMajor;
        tilesInN = (N+tileSizeMinor-1)/tileSizeMinor;
    }

    TT *shuffle = new TT[M*N];
    TT *tilePtr;
    uint32 originM;
    uint32 originN;
    for (uint32 tileM = 0; tileM < tilesInM; tileM++) {
        for (uint32 tileN = 0; tileN < tilesInN; tileN++) {
            //first find tile's position
            if (majorInN) {
                tilePtr = shuffle+(tileM*tilesInN+tileN)*tileStride;
            } else {
                tilePtr = shuffle+(tileN*tilesInM+tileM)*tileStride;
            }
            //scan each point inside the tile, remap the position back to original buffer

            for(uint32 m=0; m < tileSizeMinor; m++) {
                for(uint32 k=0; k < tileSizeMajor; k++) {
                    if (majorInN) {
                        originM = tileM * tileSizeMinor + m;
                        originN = tileN * tileSizeMajor + k;
                    } else {
                        originM = tileM * tileSizeMajor + k;
                        originN = tileN * tileSizeMinor + m;
                    }
                     //for each point inside tile, no matter majorInN or not, its fast changing is tileSizeMajor
                     //origin buffer is M*N row-major
                    *(tilePtr + m*tileSizeMajor+k) = *(buffer + originM*N+originN);
                }
            }
        }
    }

    memcpy(buffer, shuffle, sizeof(TT)*M*N);
    delete []shuffle;
    return;
}

template<typename TT>
void fmha_batch_cvt(TT *output, cl_float *a, int batch, int head_num, int seq_len, int head_dim, DATA_TYPE type, int fp_format_des = FP8_FMT, bool f8_bias_des = false)
{
    for(int b = 0; b < batch; b++)
    {
        for(int h = 0; h < head_num; h++)
        {
           int p_offs = b*head_num*seq_len*head_dim + h*seq_len*head_dim;
           int o_offs = p_offs;
           if (type==FP4) {
               o_offs /= 2;
           }

           fmha_cvt_output(a+p_offs, output+o_offs, seq_len, head_dim, type, fp_format_des, f8_bias_des);
        }
    }
}

void fmha_bwd_dQ_redc(float *dq, int batch, int head_num, int seq_len, int head_dim, int split)
{
    for(int b = 0; b < batch; b++)
    {
        for(int h = 0; h < head_num; h++)
        {
            for(int s = 0; s < seq_len; s++)
            {
                for(int d = 0; d < head_dim; d++)
                {
                   float sum = 0.0;

                   int o_offs =  b * head_num * seq_len * head_dim  + h * seq_len * head_dim + s * head_dim + d;
                   int i_offs =  b * head_num * seq_len * head_dim * split + h * seq_len * head_dim * split + s * head_dim + d;
                   for(int i = 0; i < split; i++)
                   {
                      sum += dq[i_offs];
                      i_offs += head_dim*seq_len;
                   }
                   
                   dq[o_offs] = sum;
                }
            }
        }
    }
}

template<typename TT>
void fmha_cvt_output(cl_float *a, TT *output, int m, int n, DATA_TYPE type, int fp_format_des, bool f8_bias_des)
{
    unsigned short *p1 = (unsigned short *)output;
    unsigned short *p2 = (unsigned short *)output;
    unsigned char  *p3 = (unsigned char *)output;
    int8           *pint8  = (int8*)output;
    cl_char        *pfp4   = (cl_char*)output;
    int32          *pint32 = (int32*)a;

    for(int i = 0; i < m; i++)
    {
        for(int j = 0; j < n; j++)
        {
            switch(type)
            {
                case FP16:
                     p1[i * n + j]  = (unsigned short)FP32toFP16(FloatMapToInt(a[i * n + j]));
                     break;
                case BF16:
                     p2[i * n + j]  = (unsigned short)FP32toBFP16(FloatMapToInt(a[i * n + j]));
                     break;
                case FP8:
                     #ifdef FMHA_MI300
                     p3[i * n + j]  = f32_to_f8(FloatMapToInt(a[i * n + j]), fp_format_des, f8_bias_des, false, 0);
                     #else
                     p3[i * n + j]  = f32_to_fp8(FloatMapToInt(a[i * n + j]), 127, fp_format_des, f8_bias_des, true, false, 0);
                     #endif
                     break;
                case INT8:
                     pint8[i * n + j] = (int8)pint32[i * n + j];
                case FP4:
                     setFp4(pfp4+(i*n+j)/2, f32_to_fp4(FloatMapToInt(a[i * n + j]), 127, false, 0), (i*n+j)%2);
                default:
                     break;
            }
        }
    }
}

//pointer type of a does not matter, it is converted to target type inside
void moe_v_cvt_f32_bf16(cl_half *in, uint32 M, uint32 N, float* out)
{
    for(uint32 m = 0; m < M; m++) {
        for(uint32 n = 0; n < N; n++) {
            out[m*N + n] = IntMapToFloat(BFP16toFP32((uint32)in[m*N + n]));
        }
    }
}

template<typename TT>
static void matrix_cvt_to_f32(TT *in_buf, uint32 M, uint32 N, DATA_TYPE in_type, float* out_f32, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {
    for(uint32 m = 0; m < M; m++) {
        for(uint32 n = 0; n < N; n++) {
            switch(in_type)
            {
                case FP16:
                    out_f32[m*N + n] = IntMapToFloat(FP16toFP32((uint32)in_buf[m*N + n]));
                    break;
                case BF16:
                    out_f32[m*N + n] = IntMapToFloat(BFP16toFP32((uint32)in_buf[m*N + n]));
                    break;
                case FP8:
                    #ifdef FMHA_MI300
                    out_f32[m*N + n]  = IntMapToFloat(f8_to_f32(in_buf[m*N + n], fp_format_des,f8_bias_des));
                    #else
                    out_f32[m*N + n]  = IntMapToFloat(fp8_to_f32(in_buf[m*N + n], 127, fp_format_des,f8_bias_des));
                    #endif
                     break;
                case INT32:
                    out_f32[m*N + n] = V_CVT_F32_I32((int32)in_buf[m*N+n]);
                    break;
                default:
                    printf("NOT SUPPORTED input data type %d!!!!!!!!!\n", in_type);
                    break;
            }
        }
    }
}

//////////////result check/////////////////
template<typename TT>
static int fmha_sqrt_diff_check(const TT *result, const TT *golden, int n, int in_type, double nrms = 1.5e-6, 
                                int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false) 
{
    int igemm_per_pixel_check = 0;//env_get_int("PER_PIXEL_CHECK", 0);
    int igemm_per_pixel_check_print = 1;//env_get_int("PER_PIXEL_CHECK_PRINT", 1);
    int print_every_pixel = 0;//env_get_int("PRINT_EVERY_PIXEL", 0);
    int print_nrms = 1;//env_get_int("PRINT_NRMS", 0);
    //int igemm_valid_float = 1;//env_get_int("VALID_FLOAT", 1);
    size_t pp_err = 0;

    double square_difference = .0;
    double difference = .0;
    double mag1 = .0;
    double mag2 = .0;
    int error=0;
    for (int i = 0; i < n; ++i) 
    {
        float f32_a, f32_b;

        if (in_type == FP8) 
        {
            #ifdef FMHA_MI300
            f32_a = IntMapToFloat(f8_to_f32(golden[i], fp_format_src1,f8_bias_src1));
            f32_b = IntMapToFloat(f8_to_f32(result[i], fp_format_src0,f8_bias_src0));
            #else
            f32_a = IntMapToFloat(fp8_to_f32(golden[i], 127, fp_format_src1,f8_bias_src1));
            f32_b = IntMapToFloat(fp8_to_f32(result[i], 127, fp_format_src0,f8_bias_src0));
            #endif
        }
        else if(in_type == FP16)
        {
            f32_a = IntMapToFloat(FP16toFP32(golden[i]));
            f32_b = IntMapToFloat(FP16toFP32(result[i]));
        }
        else if(in_type == BF16)
        {
            f32_a = IntMapToFloat(BFP16toFP32(golden[i]));
            f32_b = IntMapToFloat(BFP16toFP32(result[i]));
        } else if (in_type == INT8) {
            f32_a = (float) golden[i];
            f32_b = (float) result[i];
        } else if (in_type == FP32) {
            f32_a = golden[i];
            f32_b = result[i];
        } else if (in_type == FP4) {
            f32_a = IntMapToFloat(fp4_to_f32(getFp4(golden[i/2], i%2), 127));
            f32_b = IntMapToFloat(fp4_to_f32(getFp4(result[i/2], i%2), 127));
        }

        double ri = (double)f32_a;
        double pi = (double)f32_b;
        double d = ri - pi;
        //printf("ri:%lf, pi:%lf, d:%lf, d*d:%lf\n", ri, pi, d, d*d);
        double delta = abs(abs(ri - pi) / ri);
        if (delta > 1e-3 && error < 20) {
            error += 1;
            printf("error at [%d], expected %lf, got %lf, delta: %lf\n", i, ri, pi, delta);
        }
        if(igemm_per_pixel_check)
        {
            double delta = abs(abs(ri - pi) / ri);      // TODO: this is just a reference compare
            if(print_every_pixel)
                printf("[%d] ref:%lf, pred:%lf(0x%08x) [%s]\n", i, ri, pi, *(uint32_t*)(&result[i]), delta > 3e-5? "N":"Y");
            if (delta > 3e-5)
            {
                if(igemm_per_pixel_check_print)
                {
                    if (pp_err < 100)
                        printf("diff at %d, ref:%lf, pred:%lf(0x%08x), d:%lf\n", i, ri,
                            pi, *(uint32_t*)(&result[i]), delta);
                }
                pp_err++;
            }
        }
        difference += (ri == 0) ? 1.0 : abs(abs(ri - pi) / ri);
        square_difference += d * d;
        if(abs(mag1) < abs(ri)) mag1 = ri;
        if(abs(mag2) < abs(pi)) mag2 = pi;
    }
    double mag = std::max({std::fabs(mag1), std::fabs(mag2), std::numeric_limits<double>::min()});
    double computed_nrms = std::sqrt(square_difference) / (std::sqrt(n) * mag);
    if(print_nrms)
        printf("\nd:%lf, square_difference:%lf, nrms:%lf, mag1:%lf, mag2:%lf, expected_nrms is %1f\n",(difference/n), square_difference, computed_nrms,mag1,mag2,nrms);
    return (computed_nrms < nrms)
#ifdef PER_PIXEL_CHECK
           && (pp_err == 0)
#endif
        ;
}

template<typename TT>
static uint32 fmha_check_result(TT *result, TT *golden, int batch, int head_num, int seq_len, int head_dim, DATA_TYPE in_type, int check_mode = 0, double eps = 5e-4, int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false) 
{
    uint32 SameResult = 1;

    printf("\n\n>>>>>>>>>>>>> \033[1m\033[;34m  CHECKING RESULTS  \033[0m  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n");
    if (check_mode == 1) //sqrt diff check
    {
       printf("####### Sqrt-Check ########\n");
       SameResult = fmha_sqrt_diff_check(result, golden, batch*head_num*seq_len*head_dim, in_type, eps, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1);
       goto PRINT_RESULT;
    }

    for(int b = 0; b < batch; b++)
    {
        for(int h = 0; h < head_num; h++)
        {
            for(int s = 0; s < seq_len; s++)
            {
                for(int d = 0; d < head_dim; d++)
                {
                    int offset = b * head_num * seq_len * head_dim  + h * seq_len * head_dim + s * head_dim + d;
                    uint32 *aaa, *bbb;
                    aaa = (uint32 *)&result[offset];
                    bbb = (uint32 *)&golden[offset];

                    if (check_mode == 0) //bitmatch check
                    {
                        if (result[offset] != golden[offset]) 
                        {
                            SameResult = 0;
                                                  
                            printf("#######  diff index is [batch = %d, head_num = %d, seq_index = %d, head_index = %d]\n", b, h, s, d);

                            if((in_type == FP16) || (in_type == BF16))
                            {
                                printf("#######  gpu results hex  = 0x%04x    \n", (*aaa & 0xffff));
                                printf("#######  golden      hex  = 0x%04x    \n", (*bbb & 0xffff));
                            }
                            else if (in_type == FP8 || in_type == INT8)
                            {
                                printf("#######  gpu results hex  = 0x%02x    \n", (*aaa & 0xff));
                                printf("#######  golden      hex  = 0x%02x    \n", (*bbb & 0xff));
                            }
                            else if (in_type == FP32)
                            {
                                printf("#######  gpu results hex  = 0x%08x    \n", (*aaa & 0xffffffff));
                                printf("#######  golden      hex  = 0x%08x    \n", (*bbb & 0xffffffff));
                            }
                          
                            goto PRINT_RESULT;
                        }

                    } 
                    else if (check_mode == 2)
                    {
                        if (result[offset] != golden[offset]) 
                        {
                            uint la,lb;
                            if((in_type == FP16) || (in_type == BF16))
                            {
                                la =  (*aaa & 0xffff);
                                lb =  (*bbb & 0xffff);
                            }
                            else if (in_type == FP8 || in_type == INT8)
                            {
                                la =  (*aaa & 0xff);
                                lb =  (*bbb & 0xff);
                            }
                            else if(in_type == FP32)
                            {
                                la =  (*aaa & 0xffffffff);
                                lb =  (*bbb & 0xffffffff);
                            }
                            if(abs((int)la-(int)lb) > 16)
                            {
                                printf("#######  diff index is [batch = %d, head_num = %d, seq_index = %d, head_index = %d]: diff %d\n", b, h, s, d,abs((int)la-(int)lb));
                                printf("#######  gpu results hex  = 0x%04x    \n", la);
                                printf("#######  golden      hex  = 0x%04x    \n", lb);
                                SameResult = 0;
                               // goto PRINT_RESULT;
                            }
                        }
                    }
                    else
                    {
                        printf("#######  Unsupported check mode %d\n", check_mode);
                        SameResult = 0;
                        goto PRINT_RESULT;
                    }
                }//head_dim loop
            }//seq_len loop
        }//head num loop
    }//batch loop

    PRINT_RESULT:
    if (SameResult) {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;32m #TEST PASSED \033[0m                      <<<<<<<<<<<<<<<<<<<<\n\n");
    }
    else {
        printf("\n<<<<<<<<<<<<<<<   \033[1m\033[;35m #TEST FAILED \033[0m!!!!!!!!!! !!!!!!!!!! <<<<<<<<<<<<<<<<<<<<\n\n");
    }
    return SameResult;
}

static float getQuantDeno(DATA_TYPE in_type, int fp_format_src = FP8_FMT, bool f8_bias_src = false) {
    float quant_deno = QNT_DENO;
    if (in_type == FP8 && fp_format_src == FP8_FMT && f8_bias_src) {
        quant_deno = QNT_DENO_FP8_E4M3_BIAS8;
    } else if (in_type == FP8 && fp_format_src == FP8_FMT && !f8_bias_src) {
        quant_deno = QNT_DENO_FP8_E4M3_BIAS7;
    } else if (in_type == FP8 && fp_format_src == BF8_FMT && f8_bias_src) {
        quant_deno = QNT_DENO_FP8_E5M2_BIAS16;
    } else if (in_type == FP4) {
        quant_deno = QNT_DENO_MXFP4_LARGEST_POWER_OF_TWO;
    }
    return quant_deno;
}

//fast changing dimension is N
//a is M*N row-major, fast-changing is N;
//b is blockM*blockN row-major, fast-changing is blockN
//accumulate block size of blockM*blockN, top-left coordinate is idxM, idxN
//c = a + b;
//this is to simulate atomic_add in memory; reference tcc.cpp around line:5716
template<typename TT>
static void matrix_accumulate_block(TT *a, TT* b, cl_float *c, uint32 M, uint32 N, uint32 idxM, uint32 idxN, uint32 blockM, uint32 blockN, DATA_TYPE in_type, DATA_TYPE out_type) {
    TT *pAbuffer = (TT *)a;
    TT *pBbuffer = (TT *)b;
    unsigned short *p1 = (unsigned short *)c;
    unsigned short *p2 = (unsigned short *)c;
    //unsigned char  *p3 = (unsigned char *)c;
    //int32          *p4 = (int32*)c;

    if (out_type == TYPE_NUM) {
        out_type = in_type;
    }

    for (uint32 blockM_idx = 0; blockM_idx < blockM; blockM_idx++) {
        for (uint32 blockN_idx = 0; blockN_idx < blockN; blockN_idx++) {
            uint32 aIdx = (idxM+blockM_idx)*N + idxN + blockN_idx;
            uint32 bIdx = blockM_idx*blockN + blockN_idx;
            float f32_a = 0, f32_b = 0, f32_c = 0;
            if(in_type == FP16) {
                f32_a = IntMapToFloat(FP16toFP32((uint32)pAbuffer[aIdx]));
                f32_b = IntMapToFloat(FP16toFP32((uint32)pBbuffer[bIdx]));
            } else if(in_type == BF16) {
                f32_a = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[aIdx]));
                f32_b = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[bIdx]));
            } else if (in_type == FP32) {
                f32_a = (float)pAbuffer[aIdx];
                f32_b = (float)pBbuffer[bIdx];
            } else {
                printf("NOT SUPPORTED input data type %d!!!!!!!!!\n", in_type);
            }
            f32_c = f32_a + f32_b;
            switch(out_type)
            {
                case FP16:
                     p1[aIdx] = (unsigned short)FP32toFP16(FloatMapToInt(f32_c));
                     break;
                case BF16:
                     p2[aIdx] = (unsigned short)FP32toBFP16(FloatMapToInt(f32_c));
                     break;
                case FP32:
                     c[aIdx]  = f32_c;
                     break;
                default:
                     printf("NOT SUPPORTED output data type %d!!!!!!!!!\n", out_type);
                     break;
            }
        }
    }
}

float i4_to_f32_gfx9(uint8_t i4)
{
    static std::unordered_map<uint8_t, float> u = {
        {0b1000,    -0.5000f},
        {0b1001,    -0.4375f},
        {0b1010,    -0.3750f},
        {0b1011,    -0.3125f},
        {0b1100,    -0.2500f},
        {0b1101,    -0.1875f},
        {0b1110,    -0.1250f},
        {0b1111,    -0.0625f},
        {0b0   ,    +0.0000f},
        {0b1   ,    +0.0625f},
        {0b10  ,    +0.1250f},
        {0b11  ,    +0.1875f},
        {0b100 ,    +0.2500f},
        {0b101 ,    +0.3125f},
        {0b110 ,    +0.3750f},
        {0b111 ,    +0.4375f}};

    return u[i4];
}

template<typename TT>
static void cvtint4_to_fp8_buffer(TT *fp8_buffer, uint32 *int4_buffer,  uint32 head_num, uint32 seq_len, uint32 head_dim , int fp_format = FP8_FMT, bool f8_bias = false)
{
    assert( head_dim%2 == 0);
    for(uint h = 0; h < head_num; h++)
    {
        for(uint s = 0; s < seq_len; s++)
        {
            for(uint d = 0; d < head_dim; d++)
            {
                int offset_fp8 = h * seq_len * head_dim + s * head_dim + d;
                int offset_int4 = offset_fp8/8;
                int shift = (offset_fp8%8) * 4;
               // float fp32_value = i4_to_f32_gfx9((int4_buffer[offset_int4] >> shift)& 0xf) * 16;
                float fp32_value = i4_to_f32_gfx9((int4_buffer[offset_int4] >> shift)& 0xf);
                fp32_value = fp32_value * 16;
                uint8 fp8_value = f32_to_f8(FloatMapToInt(fp32_value), fp_format, f8_bias, false, 0);
                fp8_buffer[offset_fp8] = fp8_value;                
            }//head_dim
        }//seq_len
    }//head_num
}

static inline uint32_t perm_i4_dword(uint32_t x)
{
    // [e0, e2, e4, e6, e1, e3, e5, e7]
    uint32_t e0 = (x & 0x0000000f) >> 0;
    uint32_t e1 = (x & 0x000000f0) >> 4;
    uint32_t e2 = (x & 0x00000f00) >> 8;
    uint32_t e3 = (x & 0x0000f000) >> 12;
    uint32_t e4 = (x & 0x000f0000) >> 16;
    uint32_t e5 = (x & 0x00f00000) >> 20;
    uint32_t e6 = (x & 0x0f000000) >> 24;
    uint32_t e7 = (x & 0xf0000000) >> 28;

    return e0 | e2 << 4 | e4 << 8 | e6 << 12 | e1 << 16 | e3 << 20  | e5 << 24  | e7 << 28;
}

void permute_buffer(uint32_t * dst_i4_dwords, const uint32_t * src_i4_dwords, int num_dwords) {
    for(int i = 0; i < num_dwords; i++) {
        dst_i4_dwords[i] = perm_i4_dword(src_i4_dwords[i]);
    }
}
#endif
