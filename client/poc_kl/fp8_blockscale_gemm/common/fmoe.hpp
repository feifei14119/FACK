#ifndef FUSED_MOE_HPP
#define FUSED_MOE_HPP
#include "common_helper.h"
#include <string.h>
#include <stdio.h>

typedef struct TileSize {
    uint32 tileSizeMajor;
    uint32 tileSizeMinor;
    uint32 tileNumOfDWX4;
} TileSize;

//If token's expect choice is combined with topk choice, topkId is embedded into high 8 bits of 32 bits
static uint32 getTokenExpert(uint32 token, bool tWithTopk) {
    if (!tWithTopk) {
        return token;
    } else {
        return token & 0x00ffffff;
    }
}

static void setTokenExpert(uint32 *token, uint32 expId, bool tWithTopk) {
    if (!tWithTopk) {
        *token = expId;
    } else {
        *token = ((*token & 0xff000000) | (expId & 0x00ffffff));
    }
}

static uint32 getTokenTopk(uint32 token, bool tWithTopk) {
    if (!tWithTopk) {
        return 0;
    } else {
        uint32 topkId = ((token & 0xff000000) >> 24);
        return topkId;
    }
}

static void setTokenTopk(uint32 *token, uint32 topkId, bool tWithTopk) {
    if (!tWithTopk) {
        return;
    } else {
        *token = ((*token & 0x00ffffff) | ((topkId & 0x000000ff) << 24));
    }
}

static DATA_TYPE getMOEOutType(DATA_TYPE in_type, uint32 atm_f32) {
    if (atm_f32) {
        return FP32;
    } else {
        switch(in_type) {
            case INT4:
                return BF16;
            case INT8:
                return BF16;
            case BF16:
                return BF16;
            case FP8:
                return BF16;
            case FP16:
                return FP16;
            case FP32:
                return FP32;
            case FP4:
                return BF16;
            default:
                return FP32;
        }
    }
}

static uint32 typeSize(DATA_TYPE in_type) {
    switch(in_type) {
        case INT8:
            return 1;
        case BF16:
            return 2;
        case FP8:
            return 1;
        case FP16:
            return 2;
        case FP32:
            return 4;
        default:
            return 4;
    }
}

static uint32 getMOEOutElemSize(DATA_TYPE in_type, uint32 atm_f32) {
    return typeSize(getMOEOutType(in_type, atm_f32));
}

//M*N row-major, N is fast-changing
//transpose==0, dump out M*N row-major
//transpose==1, dump out N*M col-major
template<typename TT>
static void moe_dump_inHex(TT *buffer,  std::string fileName, uint32 exprt, uint32 M, uint32 N, DATA_TYPE in_type, int transpose = 0, bool u1 = false, const char* info=NULL) {
    if (buffer == NULL) {
        printf("Neglect moe_dump_inHex for NULL input\n");
        return;
    }
    uint32 offset = M*N;
    if (in_type==FP4) {
        offset/=2;
    }
    if (u1) {
        //if u1==1, which means G and U are consequtive, thus although dump out M*N, but offset is M*N*2
        offset *= 2;
    }

    FILE *file = fopen(fileName.c_str(), "w+t");
    if (file == NULL) {
        printf("Failed to open file %s\n", fileName.c_str());
        return;
    }
    for(uint32 exprtIdx = 0; exprtIdx < exprt; exprtIdx++) {
        if (exprt > 1) {
            if (info == NULL) {
                fprintf(file, "++++Expert[%04d]: \n", exprtIdx);
            } else {
                fprintf(file, "++++%s[%04d]: \n", info, exprtIdx);
            }
        }
        fmha_dumpMatrixInHex(buffer+exprtIdx*offset, file, M, N, in_type, transpose);
    }

    fclose(file);
}

static void dump_uint32_in_value(uint32* buffer, FILE *file, uint32 m, uint32 n, bool tWithTopk=false) {
    for (int b = 0; b < m; b++) {
        for (int k = 0; k < n; k++) {
            uint32 value = *(buffer + b*n+k);
            if (!tWithTopk) {
                fprintf(file, "%10d ", value);
            } else {
                fprintf(file, "%6d_%3d ", getTokenExpert(value, tWithTopk), getTokenTopk(value, tWithTopk));
            }
        }
        fprintf(file, "\n");
    }
}

static void moe_dump_topk_inHex(uint32* TKI_buf,  std::string fileName, uint32 batch, uint32 topk) {
    return moe_dump_inHex(TKI_buf, fileName, 1, batch, topk, FP32);
}

static void moe_dump_topk_inValue(uint32* TKI_buf,  std::string fileName, uint32 batch, uint32 topk, bool tWithTopk=false) {
    FILE *file = fopen(fileName.c_str(), "w+t");
    if (file == NULL) {
        printf("Failed to open file %s\n", fileName.c_str());
        return;
    }

    dump_uint32_in_value(TKI_buf, file, batch, topk, tWithTopk);
    fclose(file);
}

static void moe_weight_softmax(cl_float *weight, uint32 batch, uint32 topk) {
    cl_float scaler = 1;
    cl_float *p_sum = (cl_float*)malloc(batch*sizeof(cl_float));
    int      start  = 1;

    fmha_softmax_dev(weight, scaler, batch, topk, start, NULL, NULL, p_sum);
    //divide by sum
    for (uint32 b = 0; b < batch; b++) {
        for (uint32 t = 0; t < topk; t++) {
            *(weight+b*topk+t) = (*(weight+b*topk+t))/(*(p_sum+b));
        }
    }

    free(p_sum);
}

static void moe_dump_weight_inHex(cl_float* weight,  std::string fileName, uint32 batch, uint32 topk) {
    return moe_dump_inHex(weight, fileName, 1, batch, topk, FP32);
}

static void moe_dump_weight_inValue(cl_float* weight,  std::string fileName, uint32 batch, uint32 topk) {
    FILE *file = fopen(fileName.c_str(), "w+t");
    if (file == NULL) {
        printf("Failed to open file %s\n", fileName.c_str());
        return;
    }

    dump_float_in_value(weight, file, batch, topk);
    fclose(file);
}


//Input M*N row-major, N is fast-changing
//majorInN means for the little tile block, its data fast-changing dimension; it's also fast-changing dimension between tiles
//i think tileSizeMajor is how many points to form 4 words, for FP16, it should be 8
//tileSizeMinor is related to XDL instructions, for 16x16 it should be 16, for 32x8 it should be 32
template<typename TT>
static void moe_shuffle_one(TT *buffer, uint32 M, uint32 N, bool majorInN=true, uint32 tileSizeMajor=8, uint32 tileSizeMinor=16) {
    uint32 tilesInM;
    uint32 tilesInN;
    uint32 tileStride = tileSizeMajor*tileSizeMinor;

    if (majorInN) {
        if (M % tileSizeMinor != 0 || N % tileSizeMajor != 0) {
            printf("Not divisible M:%d,tileSizeMinor:%d N:%d,tileSizeMajor:%d\n", M, tileSizeMinor, N, tileSizeMajor);
            assert(0);
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

    TT *shuffle = (TT*) malloc(M*N*sizeof(TT));
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
    free(shuffle);
    return;
}

static void getTileSize(DATA_TYPE type, DATA_LAYOUT layout, TileSize *tileSize) {
    uint32 tileSizeMajor = 8;
    uint32 tileSizeMinor = 16;
    uint32 DWX4 = 16;
    uint32 elemSize = 2;
    uint32 totalSizeDWX4 = 64*4*4;

    if (type == FP16 || type == BF16) {
        elemSize = 2;
    } else if (type == FP8 || type == INT8) {
        elemSize = 1;
    } else if (type == FP32) {
        elemSize = 4;
    } else if (type == INT4) {
        elemSize = 8;
    } else if (type == FP4) {
         //FP4 is represented by uint8
        elemSize = 1;
    } else {
        printf("Unsupported type %d!!!\n", type);
    }
    tileSizeMajor = DWX4/elemSize;

    if (layout == LAYOUT_16X16) {
        tileSizeMinor = 16; 
    } else if (layout == LAYOUT_32x8 || layout == LAYOUT_32X32) {
        tileSizeMinor = 32;
    } else {
        printf("Unsupported layout %d!!!\n", layout);
    }
    tileSize->tileSizeMajor = tileSizeMajor;
    tileSize->tileSizeMinor = tileSizeMinor;
    tileSize->tileNumOfDWX4 = totalSizeDWX4/(tileSizeMajor*tileSizeMinor*elemSize);
}

//Input M*N row-major, N is fast-changing
template<typename TT>
static void moe_shuffle(TT *buffer, uint32 eprt, uint32 M, uint32 N, bool majorInN, DATA_TYPE type, DATA_LAYOUT layout) {
    TileSize tileSize;
    getTileSize(type, layout, &tileSize);

    if (type == FP4) {
        //assert majorInN==true; since majorInN==false is not heavy tested;
        assert(majorInN);
        //FP4 is represented by uint8; N is FP4's real dimension;cut half before shuffle 8bits
        assert(sizeof(TT)==1);
        N/=2;
    }

    for (uint32 i = 0; i < eprt; i++) {
        moe_shuffle_one(buffer+i*M*N, M, N, majorInN, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
    }
    return ;
}

//Input M*N row-major, N is fast-changing
template<typename T>
static void moe_shuffle(T *buffer, uint32 eprt, uint32 M, uint32 N, bool majorInN, uint32 tileSizeMajor, uint32 tileSizeMinor) {
    if (buffer == NULL) {
        printf("Neglect moe_shuffle for NULL input\n");
        return;
    }

    for (uint32 i = 0; i < eprt; i++) {
        moe_shuffle_one(buffer+i*M*N, M, N, majorInN, tileSizeMajor, tileSizeMinor);
    }
    return ;
}

//Input M*N row-major, N is fast-changing
//do interleave shuffle per groupSize along N direction
//For example, if interExp is 6: shuffle 0~127 as 0, 64, 1, 65, ..., 62, 126, 63, 127
template<typename T>
static void moe_shuffle_inter(T *buffer, uint32 eprt, uint32 M, uint32 N, uint32 interExp) {
    uint32 groupSize = (1 << interExp)*2;

    if (buffer == NULL) {
        printf("Neglect moe_shuffle for NULL input\n");
        return;
    }
    
    if (N % groupSize != 0) {
        printf("N(%d) is not divisible by %d for interleave shuffle\n", N, groupSize);
        assert(0);
    }

    uint32 numGroups = N/groupSize;
    uint32 dstInGroup;

    T *shuffle = new T[eprt * M * N];

    for (uint32 i = 0; i < eprt; i++) {
        for (uint32 m = 0; m < M; ++m) {
            for (uint32 g = 0; g < numGroups; ++g) {

                //interleave shuffle in each groupsize
                for (uint32 k = 0; k < groupSize; ++k) {
                    dstInGroup = (k >> 1) + ((k & 1u) << interExp);
                    *(shuffle + i*M*N + m*N + g*groupSize + k) = *(buffer + i*M*N + m*N + g*groupSize + dstInGroup);
                }
            }
        }
    }

    memcpy(buffer, shuffle, sizeof(T)*eprt*M*N);
    delete []shuffle;
    return;
}

//Input M*N row-major, N is fast-changing
template<typename TT>
static void moe_shuffle_e8m0(TT *buffer, uint32 eprt, uint32 M, uint32 N, uint32 tileSizeM=16, uint32 tileSizeK=4) {
    for (uint32 i = 0; i < eprt; i++) {
        scale_shuffle_one(buffer+i*M*N, M, N, tileSizeM, tileSizeK);
    }
    return;
}

template<typename TT>
static void moe_shuffleback_e8m0(TT *buffer, uint32 eprt, uint32 M, uint32 N, TT *out=NULL, uint32 tileSizeM=16, uint32 tileSizeK=4) {
    for (uint32 i = 0; i < eprt; i++) {
        scale_shuffleback_one(buffer+i*M*N, M, N, out, tileSizeM, tileSizeK);
    }
    return;
}

//M*N row-major, N is fast-changing
template<typename TT>
static void moe_init(TT *buffer, uint32 eprt, uint32 M, uint32 N, DATA_TYPE in_type, int init_pattern = 0, int fp_format = FP8_FMT, bool f8_bias = false)
{
    return fmha_batch_init(buffer, 1, eprt, M, N, in_type, init_pattern, fp_format, f8_bias);
}

template<typename T>
static inline T moe_clamp(T v, T lo, T hi)
{
    if (lo > hi) {
        printf("invalid clamp range\n");
        assert(0);
    }

    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

//M*N row-major, N is fast-changing
//Initialize uint4 and put it in int8
static void moe_init_uint4(int8 *buffer, uint32 eprt, uint32 M, uint32 N, int init_pattern = 0)
{
    if (buffer == NULL) {
        printf("Neglect moe_init for NULL input\n");
        return;
    }

    for(int h = 0; h < eprt; h++)
    {
        for(int s = 0; s < M; s++)
        {
            for(int d = 0; d < N; d++)
            {
                int offset = h * M * N + s * N + d;

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

                int value32 = FloatMapToInt(temp_var)&0x0f;
                buffer[offset] = (int8)(value32);

            }//N
        }//M
    }//eprt
}

//M*N row-major, N is fast-changing
//Initialize int8 qscale, qzero 
static void moe_init_lqq(int8 *qscale_buffer, int8*qzero_buffer, uint32 eprt, uint32 M, uint32 N, DATA_TYPE in_type=INT8, int init_pattern = 0, int min_val=-128, int max_val=127)
{
    if (in_type != INT8) {
        printf("moe_init_lqq only support INT8 data_type\n");
        return;
    }

    for(int h = 0; h < eprt; h++)
    {
        for(int s = 0; s < M; s++)
        {
            for(int d = 0; d < N; d++)
            {
                int offset = h * M * N + s * N + d;

                float temp_var0;
                float temp_var1;
                switch (init_pattern)
                {
                    case 0:
                        temp_var0 = (float)gaussrand();
                        temp_var1 = (float)gaussrand();
                        break;
                    case 1:
                        temp_var0 = cos(offset);
                        temp_var1 = temp_var0;
                        break;
                    case 2:
                        temp_var0 = sin(offset);
                        temp_var1 = temp_var0;
                        break;
                    case 3:
                        temp_var0 = cos(offset) + sin(offset);
                        temp_var1 = temp_var0;
                        break;
                    case 10:
                        temp_var0 = 0.25;
                        temp_var1 = temp_var0;
                        break;
                    case 11:
                        temp_var0 = 0.01*d;
                        temp_var1 = temp_var0;
                        break;
                    case 12:
                        temp_var0 = 0.01*s;
                        temp_var1 = temp_var0;
                        break;
                    default:
                        temp_var0 = 0;
                        temp_var1 = temp_var0;
                        break;
                }

                int qzero_range = max_val - min_val + 1;
                int qzero_val = (FloatMapToInt(temp_var0)&0xff) % qzero_range + min_val;
                qzero_buffer[offset] = (int8)(qzero_val);

                int maxI8_lo = qzero_val + 16;
                int range_maxI8 = 119 - maxI8_lo + 1;
                int maxI8_val = (FloatMapToInt(temp_var1)&0xff) % range_maxI8 + maxI8_lo;

                float qscale_val = static_cast<float>(maxI8_val - qzero_val)/static_cast<float>(15);
                qscale_val = std::round(qscale_val);
                qscale_buffer[offset] = (int8)qscale_val;

            }//N
        }//M
    }//eprt
}

//M*N row-major, N is fast-changing
//clamp buffer data into [lo, hi]
static void moe_qzero_plus_128(int8 *in_buffer, uint8_t *out_buffer, uint32 eprt, uint32 M, uint32 N)
{
    if (in_buffer == NULL) {
        printf("Neglect moe_qzero_plus_128 for NULL input\n");
        return;
    }

    for(int h = 0; h < eprt; h++)
    {
        for(int s = 0; s < M; s++)
        {
            for(int d = 0; d < N; d++)
            {
                int offset = h * M * N + s * N + d;

                out_buffer[offset] = static_cast<uint8_t>(in_buffer[offset] + 128);

            }//N
        }//M
    }//eprt
}

//M*N row-major, N is fast-changing
//Initialize Uint4, store in int8
template<typename T>
static void moe_lqq_dequant(int8 *in_buffer, T *out_buffer, int8 *qscale_buf, int8 *qzero_buf, uint32 eprt, uint32 M, uint32 N, uint32 group_in_k_lqq=64)
{
    if (in_buffer == NULL || qscale_buf == NULL || qzero_buf == NULL) {
        printf("Neglect moe_init_uint4 for NULL input\n");
        return;
    }

    if (N % group_in_k_lqq != 0) {
        printf("N should be divisible by group_in_k_lqq\n");
    }

    uint32 numGroups = N/group_in_k_lqq;
    uint32 qscaleOffset, qzeroOffset;
    uint32 bufOffset;

    for(uint32 h = 0; h < eprt; h++)
    {
        for(uint32 s = 0; s < M; s++)
        {
            for(uint32 g = 0; g < numGroups; g++)
            {
                qscaleOffset = h*M*numGroups + s*numGroups + g;
                qzeroOffset = h*M*numGroups + s*numGroups + g;

                for(uint32 k = 0; k < group_in_k_lqq; k++)
                {
                    bufOffset = h*M*numGroups*group_in_k_lqq + s*numGroups*group_in_k_lqq + g*group_in_k_lqq + k;

                    out_buffer[bufOffset] = in_buffer[bufOffset] * qscale_buf[qscaleOffset] + qzero_buf[qzeroOffset];

                }//one group
            }//N
        }//M
    }//eprt
}

//M*N row-major, N is fast-changing
//Initialize Uint4, store in int8
template<typename T>
static void moe_lqq_dequant_xor(int8 *in_buffer, T *out_buffer, int8 *qscale_buf, uint8_t *qzero_buf, uint32 eprt, uint32 M, uint32 N, uint32 group_in_k_lqq=64)
{
    if (in_buffer == NULL || qscale_buf == NULL || qzero_buf == NULL) {
        printf("Neglect moe_init_uint4 for NULL input\n");
        return;
    }

    if (N % group_in_k_lqq != 0) {
        printf("N should be divisible by group_in_k_lqq\n");
    }

    uint32 numGroups = N/group_in_k_lqq;
    uint32 qscaleOffset, qzeroOffset;
    uint32 bufOffset;

    for(uint32 h = 0; h < eprt; h++)
    {
        for(uint32 s = 0; s < M; s++)
        {
            for(uint32 g = 0; g < numGroups; g++)
            {
                qscaleOffset = h*M*numGroups + s*numGroups + g;
                qzeroOffset = h*M*numGroups + s*numGroups + g;

                for(uint32 k = 0; k < group_in_k_lqq; k++)
                {
                    bufOffset = h*M*numGroups*group_in_k_lqq + s*numGroups*group_in_k_lqq + g*group_in_k_lqq + k;

                    out_buffer[bufOffset] = (in_buffer[bufOffset] * qscale_buf[qscaleOffset] + (uint8_t)qzero_buf[qzeroOffset]) ^ 0x80;

                }//one group
            }//N
        }//M
    }//eprt
}

//M*N row-major, N is fast-changing
//in_buffer: M*N int8, out_buffer: M*N/2 int8
//pack each two int4 from in_buffer into one int8 in out_buffer
template<typename T>
static void moe_pack_int4(int8 *in_buffer, T *out_buffer, uint32 eprt, uint32 M, uint32 N, DATA_TYPE in_type=INT8)
{
    if (in_buffer == NULL || out_buffer == NULL) {
        printf("Neglect moe_init for NULL input/output\n");
        return;
    }

    if (in_type != INT8) {
        printf("moe_pack_int4 only support INT8 data_type\n");
        return;
    }

    if(eprt*M*N%2 != 0) {
        printf("The element number of buffer should be even.");
        return;
    }

    uint32 total_elems = eprt * M * N;
    uint32 out_len = total_elems/2;

    for(int out_idx=0; out_idx < out_len; out_idx++) {
        int8 v0 = in_buffer[out_idx*2] & 0x0F;
        int8 v1 = in_buffer[out_idx*2+1] & 0x0F;
        out_buffer[out_idx] = (int8)(v0 | v1 << 4);
    }
}

static void moe_topk_init(uint32* TKI_buf, cl_float* weight, uint32 eprt, uint32 batch, uint32 topk, uint32 even_dist = 1, bool tWithTopk=false, uint32 shared = 0) {
    memset(TKI_buf, 0, batch*topk*sizeof(uint32));

    if (even_dist) {
        eprt -= shared;
        uint32 *idxLeft     = (uint32*) malloc(eprt*sizeof(uint32));
        uint32 *idxLeftTmp  = (uint32*) malloc(eprt*sizeof(uint32));
        uint32 idxLeftRange = eprt;
        for (uint32 c = 0; c < eprt; c++) {
            idxLeft[c] = c;
        }

        uint32 e;
        uint32 j;
        for (uint32 b = 0; b < batch; b++) {
            for (uint32 t = 0; t < topk-shared; t++) {
                if (idxLeftRange == 0) {
                    //reset for another round
                    for (uint32 c = 0; c < eprt; c++) {
                        idxLeft[c] = c;
                    }
                    idxLeftRange = eprt;
                }

                //actually after reset for another round, it is possible to have duplication
                while(1) {
                    bool duplicate = false;
                    e = rand()%idxLeftRange;
                    for (uint32 i = 0; i < t; i++) {
                        if (*(TKI_buf+b*topk+i) == idxLeft[e]) {
                            duplicate = true;
                        }
                    }

                    if (!duplicate) {
                        *(TKI_buf+b*topk+t) = idxLeft[e];
                        break;
                    }
                }

                //remove idx
                j = 0;
                for (uint32 i = 0; i < idxLeftRange; i++) {
                    if (i != e) {
                        idxLeftTmp[j++] = idxLeft[i];
                    }
                }

                idxLeftRange--;
                if (idxLeftRange != 0) {
                    memcpy(idxLeft, idxLeftTmp, idxLeftRange*sizeof(uint32));
                }
            }
        }

        eprt += shared;
        free(idxLeft);
        free(idxLeftTmp);
    } else {
        bool useSimpleRandom = true; //i don't want to delete matrix random code
        if (useSimpleRandom) {
            eprt -= shared;
            for (uint32 token = 0; token < batch; token++) {
                uint32 offset = token*topk;
                *(TKI_buf+offset) = rand()%eprt; //set first without check duplicate

                for (uint32 idx = 1; idx < topk; idx++) {
                    uint32 topkValue;
                    while(1) {
                        topkValue = rand()%eprt;
                        bool duplicate = false;
                        for(uint32 i = 0; i < idx; i++) {
                            if (topkValue == *(TKI_buf+offset+i)) {
                                duplicate = true;
                                break;
                            }
                        }
                        if (!duplicate) {
                            *(TKI_buf+offset+idx) = topkValue;
                            break; //break out of while(1)
                        }
                    }
                }
            }
        }
        eprt += shared;
    }

    if (shared) {
        //set shared experts
        uint32 idx = 0;
        for (uint32 t = topk-shared; t < topk; t++) {
            uint32 sharedId = eprt-shared+idx;
            for (uint32 b = 0; b < batch; b++) {
                *(TKI_buf+b*topk+t) = sharedId;
            }
            idx++;
        }
    }

    if (tWithTopk) {
        for (uint32 b = 0; b < batch; b++) {
            for (uint32 t = 0; t < topk; t++) {
                setTokenTopk(TKI_buf+b*topk+t, t, tWithTopk);
            }
        }
    }
}

static void moe_twe_ptr_dump_inValue(std::string fileName, uint32 *sorted_token_ids_ptr, cl_float *sorted_weight_buf, uint32 *eprt_slices, uint32 eprt, uint32 sub_X, bool tWithTopk=false) {
    FILE *file = fopen(fileName.c_str(), "w+t");
    if (file == NULL) {
        printf("Failed to open file %s\n", fileName.c_str());
        return;
    }

    for (uint32 e = 0; e < eprt; e++) {
        uint32 m = eprt_slices[e];
        uint32 n = sub_X;
        if (m != 0) {
            fprintf(file, "++++Expert[%04d]: \n", e);
            dump_uint32_in_value(sorted_token_ids_ptr, file, m, n, tWithTopk);
            dump_float_in_value(sorted_weight_buf, file, m, n);
            sorted_token_ids_ptr += m*n;
            sorted_weight_buf    += m*n;
        }
    }

    fclose(file);
}

static void moe_twe_ptr_dump_inHex(std::string fileName, uint32 *sorted_token_ids_ptr, cl_float *sorted_weight_buf, uint32 *eprt_slices, uint32 eprt, uint32 sub_X) {
    FILE *file = fopen(fileName.c_str(), "w+t");
    if (file == NULL) {
        printf("Failed to open file %s\n", fileName.c_str());
        return;
    }

    for (uint32 e = 0; e < eprt; e++) {
        uint32 m = eprt_slices[e];
        uint32 n = sub_X;
        if (m != 0) {
            fprintf(file, "++++Expert[%04d]: \n", e);
            fmha_dumpMatrixInHex(sorted_token_ids_ptr, file, m, n, FP32, 0);
            fmha_dumpMatrixInHex(sorted_weight_buf, file, m, n, FP32, 0);
            sorted_token_ids_ptr += m*n;
            sorted_weight_buf    += m*n;
        }
    }

    fclose(file);
}

static void moe_twe_ptr_gen(uint32 *sorted_token_ids_ptr, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids_ptr, uint32 &sub_X_cnt, cl_float *W_buf, uint32 *TKI_buf,
                            uint32 batch, uint32 eprt, uint32 topk, uint32 sub_X, bool tWithTopk=false) {
    uint32 **eprt_tokens            = new uint32*[eprt];
    cl_float **eprt_token_weights   = new cl_float*[eprt];
    uint32 *eprt_slices             = new uint32[eprt]();
    uint32 *eprt_slice_idxs         = new uint32[eprt]();

    //init
    for (uint32 e = 0; e < eprt; e++) {
        eprt_slices[e]          = 1;
        eprt_slice_idxs[e]      = 0;
        eprt_tokens[e]          = new uint32[sub_X]();
        eprt_token_weights[e]   = new cl_float[sub_X];
        for(uint32 x = 0; x < sub_X; x++) {
            eprt_tokens[e][x]           = batch;
            setTokenTopk(&eprt_tokens[e][x], topk, tWithTopk);
            eprt_token_weights[e][x]    = 0;
        }
    }

    //sort
    for (uint32 t = 0; t < batch; t++) {
        for(uint32 k = 0; k < topk; k++) {
            uint32   e  = getTokenExpert(*(TKI_buf + t*topk+k), tWithTopk);
            cl_float w  = *(W_buf + t*topk+k);
            uint32 idx  = eprt_slice_idxs[e];

            //realloc if needed
            if (idx > eprt_slices[e]*sub_X-1) {
                eprt_slices[e]++;
                uint32 newSize          = eprt_slices[e]*sub_X;
                uint32 *eprt_new        = new uint32[newSize]();
                cl_float *eprt_w_new    = new cl_float[newSize];
                for (uint32 idx = (eprt_slices[e]-1)*sub_X; idx < newSize; idx++) {
                    eprt_new[idx]       = batch;
                    setTokenTopk(&eprt_new[idx], topk, tWithTopk);
                    eprt_w_new[idx]     = 0;
                }
                memcpy(eprt_new, eprt_tokens[e], (eprt_slices[e]-1)*sub_X*sizeof(uint32));
                memcpy(eprt_w_new, eprt_token_weights[e], (eprt_slices[e]-1)*sub_X*sizeof(cl_float));
                delete []eprt_tokens[e];
                delete []eprt_token_weights[e];
                eprt_tokens[e]          = eprt_new;
                eprt_token_weights[e]   = eprt_w_new;
            }

            eprt_tokens[e][idx] = t;
            setTokenTopk(&eprt_tokens[e][idx], getTokenTopk(*(TKI_buf + t*topk+k), tWithTopk), tWithTopk);
            eprt_token_weights[e][idx] = w;
            eprt_slice_idxs[e]++;
        }
    }

    //put back
    uint32 *tokens    = sorted_token_ids_ptr;
    cl_float *weights = sorted_weight_buf;
    uint32 *erp_ids   = sorted_expert_ids_ptr;
    for (uint32 e = 0; e < eprt; e++) {
        memcpy(tokens, eprt_tokens[e], sizeof(uint32)*eprt_slices[e]*sub_X);
        tokens += eprt_slices[e]*sub_X;
        memcpy(weights, eprt_token_weights[e], sizeof(cl_float)*eprt_slices[e]*sub_X);
        weights += eprt_slices[e]*sub_X;

        for (uint32 s = 0; s < eprt_slices[e]; s++) {
            erp_ids[s]= e;
            sub_X_cnt++;
        }
        erp_ids += eprt_slices[e];
    }

    //clean up
    for (uint32 e = 0; e < eprt; e++) {
        delete []eprt_tokens[e];
        delete []eprt_token_weights[e];
    }
    delete []eprt_slices;
    delete []eprt_slice_idxs;
    return;
}

static void moe_twe_ptr_reduce(uint32 *sorted_token_ids_ptr, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids_ptr, 
                            uint32 *sorted_token_ids_ptr_rdc, cl_float *sorted_weight_buf_rdc, uint32 *sorted_expert_ids_ptr_rdc,
                            uint32 * expert_slices,
                            uint32 &sub_X_cnt, uint32 batch, uint32 eprt, uint32 sub_X, bool tWithTopk) {
    uint32 sub_X_cnt_rdc = 0;
    for (uint32 e = 0; e < eprt; e++) {
        uint32 m    = expert_slices[e];
        uint32 n    = sub_X;
        uint32 newM = m;
        if (m == 1) {
            uint32 tokenIdx = getTokenExpert(*sorted_token_ids_ptr, tWithTopk);
            if (tokenIdx == batch) {
                newM = 0; //This expert handles nothing
            }
        }
        if (newM != 0) {    //which means this expert has tokens
            memcpy(sorted_token_ids_ptr_rdc,    sorted_token_ids_ptr,   m*n*sizeof(uint32));
            memcpy(sorted_weight_buf_rdc,       sorted_weight_buf,      m*n*sizeof(cl_float));
            memcpy(sorted_expert_ids_ptr_rdc,   sorted_expert_ids_ptr,  m*sizeof(uint32));
            sub_X_cnt_rdc             += newM;
            sorted_token_ids_ptr_rdc  += newM*n;
            sorted_weight_buf_rdc     += newM*n;
            sorted_expert_ids_ptr_rdc += newM;
        }
        expert_slices[e]       = newM;
        sorted_token_ids_ptr  += m*n;
        sorted_weight_buf     += m*n;
        sorted_expert_ids_ptr += m;
    }
    sub_X_cnt = sub_X_cnt_rdc;
}

//Only called when both t_with_topk/x_bf16 enabled and in_type is INT8/FP8
//Input:
//X_buf_b16:    batch*dim
//expt_scale:   eprt*dim
//TKI_buf:      batch*topk
//Output:
//X_buf:        topk*batch*dim
//X_dqn_buf:    topk*batch*1
template<typename TT>
static void moe_X_fromBF16(cl_half *X_buf_bf16, cl_float* expt_scale, uint32 *TKI_buf, TT *X_buf, cl_float *X_dqn_buf, 
        uint32 batch, uint32 dim, uint32 eprt, uint32 topk, DATA_TYPE type=INT8, uint32 dbg_trace=0, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {
    bool tWithTopk = true;

    float *X_f32    = new float[batch*dim];
    float *X_scaled = new float[eprt*batch*dim];
    float *X_dqnt   = new float[eprt*batch];
    TT     *X_8bits  = new TT[eprt*batch*dim];
    float quant_deno = getQuantDeno(type, fp_format_des, f8_bias_des);

    FILE *f_trace = fopen("moe_x_data_gen.hex", "w+t");
    if (f_trace == NULL) {
       printf("Failed to open moe_x_data_gen.hex!!!!!!\n");
       return;
    }
    
    if (dbg_trace) {
        fprintf(f_trace, "type:%d, batch:%d, dim:%d, eprt:%d, topk:%d, sizeof(TT):%lu \n",
                          type,    batch,    dim,    eprt,    topk,    sizeof(TT));
        if (sizeof(TT) != 1) {
            printf("Warning!!!!!! moe_X_fromBF16, sizeof(TT) is not 1!!!!!!!!!!!!\n");
            fprintf(f_trace, "Warning!!!!!! moe_X_fromBF16, sizeof(TT) is not 1!!!!!!!!!!!!\n");
        }
    }

    //prepare data
    moe_v_cvt_f32_bf16(X_buf_bf16,                                              batch,  dim,    X_f32);
    if (dbg_trace) {
        fprintf(f_trace, "X BF16-IN\n");
        fmha_dumpMatrixInHex(X_buf_bf16,                    f_trace,            batch,  dim,    BF16);
        fprintf(f_trace, "X F32-OUT\n");
        fmha_dumpMatrixInHex(X_f32,                         f_trace,            batch,  dim,    FP32);
    }

    for (uint32 e = 0; e < eprt; e++) {
        smooth_quant(X_f32,  expt_scale     + e*dim,                            batch,  dim,    X_scaled+e*batch*dim);
        if (dbg_trace) {
            fprintf(f_trace, "X scale, expert:%d, Scale-IN\n",          e);
            fmha_dumpMatrixInHex(expt_scale + e*dim,        f_trace,            1,      dim,    FP32);
            fprintf(f_trace, "X scale, expert:%d, Scale-OUT\n",         e);
            fmha_dumpMatrixInHex(X_scaled   + e*batch*dim,  f_trace,            batch,  dim,    FP32);
        }
        
        quant(X_scaled                      + e*batch*dim,  X_dqnt + e*batch,   batch,  dim, quant_deno);
        if (dbg_trace) {
            fprintf(f_trace, "X scale, expert:%d, QUANT-OUT\n",         e);
            fmha_dumpMatrixInHex(X_scaled   + e*batch*dim,  f_trace,            batch,  dim,    FP32);
            fprintf(f_trace, "X scale, expert:%d, DEQUANT-VEC-OUT\n",   e);
            fmha_dumpMatrixInHex(X_dqnt     + e*batch,      f_trace,            batch,  1,      FP32);
        }

        if (type == INT8) {
            matrix_v_cvt_i8_f32(X_scaled    + e*batch*dim,                      batch,  dim,   X_8bits+e*batch*dim);
        } else {
            matrix_v_cvt_to_type(X_scaled   + e*batch*dim, X_8bits+e*batch*dim, batch,  dim,     type, fp_format_des, f8_bias_des);
        }
        
        if (dbg_trace) {
            fprintf(f_trace, "X scale, expert:%d, Convert-BITS8-OUT\n",  e);
            fmha_dumpMatrixInHex(X_8bits     + e*batch*dim,  f_trace,            batch,  dim,    type);
        }
    }

    //fill data
    for (uint32 b = 0; b < batch; b ++) {
        for (uint32 tk = 0; tk < topk; tk++) {
            uint32   e      = getTokenExpert(*(TKI_buf+b*topk+tk), tWithTopk);   //real expert idx may reside in low 24bits
            uint32   t_topk = getTokenTopk  (*(TKI_buf+b*topk+tk), tWithTopk);
            assert(tk == t_topk);
            uint32   X_frm_offset = e*batch*dim +b*dim;
            uint32   X_qnt_frm    = e*batch     +b;
            uint32   X_to_offset  = tk*batch*dim+b*dim;
            uint32   X_qnt_to     = tk*batch    +b;

            memcpy(X_buf+X_to_offset,   X_8bits+X_frm_offset,    dim*sizeof(int8));
            memcpy(X_dqn_buf+X_qnt_to,  X_dqnt+X_qnt_frm,        1*  sizeof(float));
        }
    }

    fclose(f_trace);
    delete [] X_f32;
    delete [] X_scaled;
    delete [] X_dqnt;
    delete [] X_8bits;
}

//for UP enabled, GEMM2-input = quant[Silu(dequant(GEMM0)) * (dequant(GEMM1))]; no smooth quant before quant
//standard golden compute token one by one
template<typename TT>
static void moe_ref_std(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    cl_float *X_dqn_buf, cl_float *GU_dqn_buf, cl_float *D_dqn_buf, cl_float *Smooth_qnt_buf, 
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU, 
    DATA_TYPE in_type=BF16, uint32 dbg_trace=0, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = false,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT,
    bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false, bool tkw1 = false) {

    uint32   batch_cpt  = 1;//batch in compute, 1 means compute token one by one
    uint32   X_topk     = 1;
    TT        *X_ptr;        //offset of X
    TT        *G_ptr;        //offset of G
    TT        *U_ptr;        //offset of U
    TT        *D_ptr;        //offset of D
    TT        *GEMM0_T;      //for GEMM2 operation

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;  //float pointer to GEMM0 result
    int32    *GEMM0_int32;  //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;  //float pointer to GEMM1 result
    int32    *GEMM1_int32;  //int32 pointer to GEMM1 result
    cl_float *GEMM2_float;  //float pointer to GEMM2 result
    int32    *GEMM2_int32;  //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;   //half  pointer to GEMM2 result, for 16bits

    cl_float *X_DQNT;       //dequant matrix for GEMM0, size batch*1
    cl_float *GEMM0DQNT;    //dequant matrix for GEMM0, size eprt*batch*hidden_dim
    cl_float *GEMM1DQNT;    //dequant matrix for GEMM1, size eprt*batch*hidden_dim
    cl_float *GEMM2DQNT_ptr;//dequant matrix for GEMM2, size batch_cpt*dim
    cl_float *GEMM2DQNT_vec;//dequant vector for GEMM2, size batch_cpt*1
    cl_float *GEMM0DQNT_ptr;//dequant matrix for GEMM0, size batch_cpt*hidden_dim; it is offset of GEMM0DQNT
    cl_float *GEMM1DQNT_ptr;//dequant matrix for GEMM1, size batch_cpt*hidden_dim; it is offset of GEMM1DQNT
    cl_float *D_DQNT_ptr;   //offset of D_dqn_buf
    cl_float *SMT_QNT_ptr;  //offset of Smooth_qnt_buf
    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    if (tWithTopk) {
        X_topk = topk;
    }

    FILE *f_trace = fopen("moe_data_trace_std.hex", "w+t");
    if (f_trace == NULL) {
       printf("Failed to open moe_data_trace_std.hex!!!!!!\n");
       return;
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk);
        fprintf(f_trace, "fp8_format:%d fp8_bias:%d\n", fp_format_src0, f8_bias_src0);
    }

    //generate dequant matrixs for GEMM0
    //X X_topk*batch*1 G/U eprt*1*hidden_dim
    GEMM0DQNT = new cl_float[X_topk*eprt*batch*hidden_dim];
    GEMM1DQNT = new cl_float[X_topk*eprt*batch*hidden_dim];
    X_DQNT    = new cl_float[batch*1];
    memset(GEMM0DQNT, 0, X_topk*eprt*batch*hidden_dim*sizeof(cl_float));
    memset(GEMM1DQNT, 0, X_topk*eprt*batch*hidden_dim*sizeof(cl_float));
    for(uint32 tk = 0; tk < X_topk; tk++) {
        //init X_DQNT vector for this topk
        for(uint32 b = 0; b < batch; b++) {
            X_DQNT[b] = X_dqn_buf[b+tk*batch];
        }

        fprintf(f_trace, "topk:%d X-DEQUANT-BUF:\n", tk);
        fmha_dumpMatrixInHex(X_DQNT, f_trace, batch, 1, FP32, 0);

        for(uint32 e = 0; e < eprt; e++) {
            fmha_matrix_mul(X_DQNT, (GU_dqn_buf+e*hidden_dim+u1*e*hidden_dim), (GEMM0DQNT+tk*eprt*batch*hidden_dim+e*batch*hidden_dim),   batch, hidden_dim, 1, FP32, FP32, 0, 
                            fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            if (dbg_trace) {
                fprintf(f_trace, "expert:%d, ++++G-DEQUANT-BUF:\n", e);
                fmha_dumpMatrixInHex(GU_dqn_buf+e*hidden_dim+u1*e*hidden_dim,                   f_trace,                            1,     hidden_dim, FP32, 0);
                fprintf(f_trace, "topk:%d  expert:%d, ++++GEMM0-DEQUANT-MATRIX\n", tk, e);
                fmha_dumpMatrixInHex(GEMM0DQNT+tk*eprt*batch*hidden_dim+e*batch*hidden_dim,     f_trace,                            batch, hidden_dim, FP32, 0);
            }
            if (u1) {
                fmha_matrix_mul(X_DQNT, (GU_dqn_buf+hidden_dim+e*hidden_dim+u1*e*hidden_dim), (GEMM1DQNT+tk*eprt*batch*hidden_dim+e*batch*hidden_dim),   batch, hidden_dim, 1, FP32, FP32, 0, 
                                fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                if (dbg_trace) {
                    fprintf(f_trace, "expert:%d, ++++U-DEQUANT-BUF:\n", e);
                    fmha_dumpMatrixInHex(GU_dqn_buf+hidden_dim+e*hidden_dim+u1*e*hidden_dim,        f_trace,                            1,     hidden_dim, FP32, 0);
                    fprintf(f_trace, "topk:%d  expert:%d, ++++GEMM1-DEQUANT-MATRIX\n", tk, e);
                    fmha_dumpMatrixInHex(GEMM1DQNT+tk*eprt*batch*hidden_dim+e*batch*hidden_dim,     f_trace,                            batch, hidden_dim, FP32, 0);
                }
            }
        }
    }

    //alloc temporary compute results
    GEMM2DQNT_vec = new cl_float[batch_cpt*1];          //size batch_cpt*1
    GEMM2DQNT_ptr = new cl_float[batch_cpt*dim];        //size batch_cpt*dim
    GEMM0_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM1_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM2_float   = new cl_float[batch_cpt*dim];        //size batch_cpt*dim
    GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    GEMM1_int32   = (int32*)   GEMM1_float;
    GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);

    for (uint32 b = 0; b < batch; b += batch_cpt) { //use batch_cpt make below code looks general and easy to extract in future
        //each token need to interact with topk experts and combine result into output
        for (uint32 tk = 0; tk < topk; tk++) {
            uint32   e      = getTokenExpert(*(TKI_buf+b*topk+tk), tWithTopk);   //real expert idx may reside in low 24bits
            uint32   t_topk = getTokenTopk  (*(TKI_buf+b*topk+tk), tWithTopk);
            cl_float weight = *(W_buf  +b*topk+tk);
            //offset pointers
            X_ptr           = X_buf                 + b*dim     + t_topk*batch*dim;             //size batch_cpt*dim
            G_ptr           = GU_buf                + e*hidden_dim*dim + u1*e*hidden_dim*dim;   //size hidden_dim*dim
            U_ptr           = G_ptr                 + hidden_dim*dim;                           //size hidden_dim*dim
            D_ptr           = D_buf                 + e*dim*hidden_dim;                         //size dim*hidden_dim
            GEMM0DQNT_ptr   = GEMM0DQNT             + t_topk*eprt*batch*hidden_dim
                                                    + e*batch*hidden_dim + b*hidden_dim;        //size batch_cpt*hidden_dim
            GEMM1DQNT_ptr   = GEMM1DQNT             + t_topk*eprt*batch*hidden_dim
                                                    + e*batch*hidden_dim + b*hidden_dim;        //size batch_cpt*hidden_dim
            D_DQNT_ptr      = D_dqn_buf             + e*dim;                                    //size 1*dim
            SMT_QNT_ptr     = Smooth_qnt_buf        + e*hidden_dim;                             //size 1*hidden_dim
            cpu_O_buf_ptr   = cpu_O_buf             + b*dim;                                    //size batch_cpt*dim
            cpu_O_buf_half  = (cl_half*) cpu_O_buf  + b*dim;                                    //size batch_cpt*dim
            //clean temporay buffers
            memset(GEMM0_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM1_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM2_float,   0, batch_cpt*dim       *sizeof(cl_float));
            memset(GEMM2DQNT_ptr, 0, batch_cpt*dim       *sizeof(cl_float));
            memset(GEMM2DQNT_vec, 0, batch_cpt*1         *sizeof(cl_float));

            //GEMM0=XxGATE INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*hidden_dim
            matrix_mul_fast_in_K(X_ptr, G_ptr, GEMM0_float,                 batch_cpt,      hidden_dim,     dim, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

            if (dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0-OUT\n",                    b, e);
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }
            
            if (in_type == INT8 || in_type == FP8) {
                if (in_type == INT8) {
                    //Convert to F32 before dequant
                    matrix_v_cvt_f32_i32(GEMM0_int32,                       batch_cpt,      hidden_dim);
                }
                //GEMM0 dequant
                dequant(GEMM0_float, GEMM0DQNT_ptr, batch_cpt, 
                        hidden_dim, 
                        tkw1 ? NULL : nullptr,
                        tkw1 ? weight : 1.0f);

                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 DEQUANT-BUF-IN:\n",    b, e);
                    fmha_dumpMatrixInHex(GEMM0DQNT_ptr, f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 DEQUANT-OUT:\n",       b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            } else {
                matrix_SILU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            }
            if (dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 GELU-OUT: \n",         b, e);
                } else {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SILU-OUT: \n",         b, e);
                }
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }

            if (u1) {
                //GEMM1=XxGATE INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*hidden_dim
                matrix_mul_fast_in_K(X_ptr, U_ptr, GEMM1_float,                 batch_cpt,      hidden_dim,     dim, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM1-OUT\n",                    b, e);
                    fmha_dumpMatrixInHex(GEMM1_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }

                if (in_type == INT8 || in_type == FP8) {
                    if (in_type == INT8) {
                        //Convert to F32 before dequant
                        matrix_v_cvt_f32_i32(GEMM1_int32,                       batch_cpt,      hidden_dim);
                    }
                    //GEMM1 dequant
                    dequant(GEMM1_float, GEMM1DQNT_ptr,                         batch_cpt,      hidden_dim,
                            tkw1 ? NULL : nullptr,
                            tkw1 ? weight : 1.0f);
                    if (dbg_trace) {
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM1 DEQUANT-BUF-IN:\n",    b, e);
                        fmha_dumpMatrixInHex(GEMM1DQNT_ptr, f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM1 DEQUANT-OUT:\n",       b, e);
                        fmha_dumpMatrixInHex(GEMM1_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    }
                }

                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          batch_cpt,      hidden_dim);
                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0*GEMM1 OUT:\n",             b, e);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  batch_cpt,      hidden_dim,     FP32,   0);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      batch_cpt,      hidden_dim);
                    if(dbg_trace) {
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-BUF-IN:\n",     b, e);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,   f_trace,            1,              hidden_dim,     FP32,   0);
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-QUANT-OUT:\n",  b, e);
                        fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    }
                }

                //Quant GEMM0, and generate GEMM2 dequant vector; 
                quant(GEMM0_float, GEMM2DQNT_vec,                           batch_cpt,      hidden_dim, quant_deno);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-OUT:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }

                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
                //Generate GEMM2 dequant matrix GEMM2DQNT_ptr=GEMM2DQNT_vec X D_DQNT_ptr batch_cpt*dim=batch_cpt*1 X 1*dim
                fmha_matrix_mul(GEMM2DQNT_vec, D_DQNT_ptr, GEMM2DQNT_ptr,   batch_cpt,      dim,    1,      FP32,   FP32, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            } else {
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM0_T,           f_trace,            batch_cpt,      hidden_dim,     in_type, 0);
                fprintf(f_trace, "token:%d, expert:%d, ++++D: \n",                          b, e);
                fmha_dumpMatrixInHex(D_ptr,             f_trace,            dim,            hidden_dim,     in_type, 1);
            }
            //GEMM2=GEMM0xDOWN  INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*dim
            matrix_mul_fast_in_K(GEMM0_T, D_ptr, GEMM2_float,               batch_cpt,      dim,            hidden_dim, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 OUT: \n",                  b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            if (in_type == INT8 || in_type == FP8) {
                if (in_type == INT8) {
                    //Convert to F32 before dequant
                    matrix_v_cvt_f32_i32(GEMM2_int32,                       batch_cpt,      dim);
                }
                //GEMM2 dequant and multiple weight
                dequant(GEMM2_float, GEMM2DQNT_ptr,                         batch_cpt,      dim,            GEMM2_float,
                        tkw1 ? 1.0f : weight);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 DEQUANT-BUF-IN: \n",   b, e);
                    fmha_dumpMatrixInHex(GEMM2DQNT_ptr, f_trace,            batch_cpt,      dim,            FP32,   0);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 DEQUANT-OUT: \n",      b, e);
                    fmha_dumpMatrixInHex(GEMM2_float,   f_trace,            batch_cpt,      dim,            FP32,   0);
                }
            } else {
                //just multiple weight
                matrix_multi_weight(GEMM2_float,                            batch_cpt,      dim,            weight);
            }

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-VALUE: \n",         b, e);
                fmha_dumpMatrixInHex(&weight,           f_trace,            1,              1,              FP32,   0);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-OUT: \n",           b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            if (o_elemSize == 2) {
                //convert to target output
                matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,               batch_cpt,      dim,            o_elemType, fp_format_des, f8_bias_des);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM2_half,        f_trace,            batch_cpt,      dim,            BF16,   0);
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_half,  GEMM2_half,  (cl_float*)cpu_O_buf_half,   batch_cpt, dim, BF16,   BF16);
            } else {
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_ptr,   GEMM2_float, cpu_O_buf_ptr,               batch_cpt, dim, FP32,   FP32);
            }
        }
    }
    fclose(f_trace);

    delete []X_DQNT;
    delete []GEMM0_float;
    delete []GEMM1_float;
    delete []GEMM2_float;
    delete []GEMM0DQNT;
    delete []GEMM1DQNT;
    delete []GEMM2DQNT_vec;
    delete []GEMM2DQNT_ptr;
    return;
}
//when used inside moe_ref_dev; shuffle may move to start point of single little tile;
//then when majorInN==true, specify M=tileSizeMinor*M_num_of_tiles_to_shuffleback,N=tileSizeMajor*N_num_of_tiles_to_shuffleback
//minimal granularity is one single tile when M=tileSizeMinor, N=tileSizeMajor
template<typename TT>
static void moe_shuffleback_one(TT *shuffle, uint32 M, uint32 N, bool majorInN=true, uint32 tileSizeMajor=8, uint32 tileSizeMinor=16, TT *out=NULL) {
    uint32 tilesInM;
    uint32 tilesInN;
    uint32 tileStride = tileSizeMajor*tileSizeMinor;

    if (majorInN) {
        if (M % tileSizeMinor != 0 || N % tileSizeMajor != 0) {
            printf("Not divisible M:%d,tileSizeMinor:%d N:%d,tileSizeMajor:%d\n", M, tileSizeMinor, N, tileSizeMajor);
            assert(0);
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

    TT *buffer = new TT[M*N];
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
                    *(buffer + originM*N+originN) = *(tilePtr + m*tileSizeMajor+k);
                }
            }
        }
    }

    if (out == NULL) {
        out = shuffle;
    }
    memcpy(out, buffer, sizeof(TT)*M*N);
    delete []buffer;
    return;
}
//shuffle is M*N row-major, fast-changing is N;
//out is blockM*blockN row-major, fast-changing is blockN
//shuffle back a block size of blockM*blockN, top-left coordinate is idxM, idxN
template<typename TT>
static void moe_shuffleback_block(TT *shuffle, TT *out, uint32 M, uint32 N, uint32 idxM, uint32 idxN, uint32 blockM, uint32 blockN, uint32 tileSizeMajor, uint32 tileSizeMinor) {
    uint32 tileStride;
    bool majorInN = true;
    uint32 tilesInN;
    uint32 tileIdInM;
    uint32 tileIdInN;
    uint32 tileId;
    if (majorInN) {
        tileStride = tileSizeMinor*blockN;
        tilesInN   = (N+tileSizeMajor-1)/tileSizeMajor;
        tileIdInN  = (idxN+tileSizeMajor-1)/tileSizeMajor;
        if (M % tileSizeMinor != 0 || N % tileSizeMajor != 0) {
            printf("Not divisible M:%d,tileSizeMinor:%d N:%d,tileSizeMajor:%d\n", M, tileSizeMinor, N, tileSizeMajor);
            assert(0);
        }
        if (idxM % tileSizeMinor != 0 || idxN % tileSizeMajor != 0) {
            printf("Not divisible idxM:%d,tileSizeMinor:%d idxN:%d,tileSizeMajor:%d\n", idxM, tileSizeMinor, idxN, tileSizeMajor);
            assert(0);
        }
        if (blockM % tileSizeMinor != 0 || blockN % tileSizeMajor != 0) {
            printf("Not divisible blockM:%d,tileSizeMinor:%d blockN:%d,tileSizeMajor:%d\n", blockM, tileSizeMinor, blockN, tileSizeMajor);
            assert(0);
        }
    } else {
        if (M % tileSizeMajor != 0 || N % tileSizeMinor != 0) {
            printf("Not divisible M:%d,tileSizeMajor:%d N:%d,tileSizeMinor:%d\n", M, tileSizeMajor, N, tileSizeMinor);
            assert(0);
        }
    }

    TT *buffer = new TT[tileStride];
    uint32  t = 0;
    for (uint32 blockM_idx = 0; blockM_idx < blockM; blockM_idx += tileSizeMinor) {
        tileIdInM  = (idxM+blockM_idx+tileSizeMinor-1)/tileSizeMinor;
        tileId     = tileIdInM*tilesInN + tileIdInN;
        moe_shuffleback_one(shuffle+(tileSizeMajor*tileSizeMinor)*tileId, tileSizeMinor, blockN, majorInN, tileSizeMajor, tileSizeMinor, buffer);
        memcpy(out+t*tileStride, buffer, tileStride*sizeof(TT));
        t++;
    }

    delete []buffer;
    return;
}

//shuffle is M*N row-major, fast-changing is N;
//out is blockM*blockN row-major, fast-changing is blockN
//shuffle back a block size of blockM*blockN, top-left coordinate is idxM, idxN
//tileSizeM,tileSizeK defines shuffleback e8m0 for 16x128 or 32x64
template<typename TT>
static void scale_e8m0_shuffleback_block(TT *shuffle, TT *out, uint32 M, uint32 N, uint32 idxM, uint32 idxN, uint32 blockM, uint32 blockN, uint32 tileSizeM=16, uint32 tileSizeK=4) {
    uint32 tileStride;
    bool majorInN = true;
    uint32 tileSizeMinor = MX_FP_M;             //32
    uint32 tileSizeMajor = MX_FP_K/MX_FP_BS;    //8
    uint32 tilesInN;
    uint32 tileIdInM;
    uint32 tileIdInN;
    uint32 tileId;
    if (majorInN) {
        tileStride = tileSizeMinor*blockN;
        tilesInN   = (N+tileSizeMajor-1)/tileSizeMajor;
        tileIdInN  = (idxN+tileSizeMajor-1)/tileSizeMajor;
        if (M % tileSizeMinor != 0 || N % tileSizeMajor != 0) {
            printf("Not divisible M:%d,tileSizeMinor:%d N:%d,tileSizeMajor:%d\n", M, tileSizeMinor, N, tileSizeMajor);
            assert(0);
        }
        if (idxM % tileSizeMinor != 0 || idxN % tileSizeMajor != 0) {
            printf("Not divisible idxM:%d,tileSizeMinor:%d idxN:%d,tileSizeMajor:%d\n", idxM, tileSizeMinor, idxN, tileSizeMajor);
            assert(0);
        }
        if (blockM % tileSizeMinor != 0 || blockN % tileSizeMajor != 0) {
            printf("Not divisible blockM:%d,tileSizeMinor:%d blockN:%d,tileSizeMajor:%d\n", blockM, tileSizeMinor, blockN, tileSizeMajor);
            assert(0);
        }
    } else {
        if (M % tileSizeMajor != 0 || N % tileSizeMinor != 0) {
            printf("Not divisible M:%d,tileSizeMajor:%d N:%d,tileSizeMinor:%d\n", M, tileSizeMajor, N, tileSizeMinor);
            assert(0);
        }
    }

    TT *buffer = new TT[tileStride];
    uint32  t = 0;
    for (uint32 blockM_idx = 0; blockM_idx < blockM; blockM_idx += tileSizeMinor) {
        tileIdInM  = (idxM+blockM_idx+tileSizeMinor-1)/tileSizeMinor;
        tileId     = tileIdInM*tilesInN + tileIdInN;
        scale_shuffleback_one(shuffle+(tileSizeMajor*tileSizeMinor)*tileId, tileSizeMinor, blockN, buffer, tileSizeM, tileSizeK);
        memcpy(out+t*tileStride, buffer, tileStride*sizeof(TT));
        t++;
    }

    delete []buffer;
    return;
}

template<typename TT>
static uint32 moe_check_result(TT *gpu_O_buf, TT *cpu_O_buf, uint32 batch, uint32 dim, DATA_TYPE in_type,
    int check_mode = 0, double eps = 5e-4, int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false) {
    return fmha_check_result(gpu_O_buf, cpu_O_buf, 1, 1, batch, dim, in_type, check_mode, eps, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1);
}

//Difference between moe_ref_dev are:
//X_buf type changed from TT* to cl_half*
//parameter X_dqn_buf:X_topk*batch*1 changed to expt_scale:eprt*dim*1
template<typename TT>
static void moe_ref_dev_XBF16_dev(cl_half *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    cl_float *expt_scale, cl_float *GU_dqn_buf, cl_float *D_dqn_buf, cl_float *Smooth_qnt_buf,
    uint32 *sorted_token_ids, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids, uint32 &sub_X_cnt,
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU, uint32 dbg_subD, uint32 dbg_subK,
    DATA_TYPE in_type=BF16, uint32 dbg_trace=1, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = true,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   X_topk     = 1;
    cl_half  *X_ptr_BF16;                               //offset of X; temporary storage; type is BF16
    cl_half  *X_step_BF16;                              //for matrix accumulation in dim dimension; type is BF16
    cl_float *X_step_F32;                               //for matrix accumulation in dim dimension; type is FP32
    TT        *X_ptr;                                    //offset of X; temporary storage; type is TT int8
    TT        *G_ptr;                                    //offset of G
    TT        *U_ptr;                                    //offset of U
    TT        *D_ptr;                                    //offset of D
    TT        *GEMM0_T;                                  //for GEMM2 operation

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;                              //float pointer to GEMM0 result
    cl_float *GEMM0_step;                               //float pointer to GEMM0 result
    //int32    *GEMM0_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;                              //float pointer to GEMM0 result
    cl_float *GEMM1_step;                               //float pointer to GEMM0 result
    int32    *GEMM1_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM2_float;                              //float pointer to GEMM2 result
    int32    *GEMM2_int32;                              //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;                               //half  pointer to GEMM2 result, for 16bits

    cl_float *X_DQNT_vec;                               //dequant vector for GEMM0, size sub_X*1
    cl_float *G_DQNT_ptr;                               //offset of G_dqn_buf,      size 1*sub_GU
    cl_float *U_DQNT_ptr;                               //offset of U_dqn_buf,      size 1*sub_GU
    cl_float *GEMM0DQNT_ptr;                            //dequant matrix for GEMM0, size sub_X*sub_GU
    cl_float *GEMM1DQNT_ptr;                            //dequant matrix for GEMM0, size sub_X*sub_GU

    cl_float *SMT_QNT_ptr;                              //offset of Smooth_qnt_buf, size 1*sub_GU

    cl_float *GEMM2DQNT_vec;                            //dequant vector for GEMM2, size sub_X*1
    cl_float *rowMax_vec;                               //for debug purpose
    cl_float *D_DQNT_ptr;                               //offset of D_dqn_buf,      size 1*dim
    cl_float *GEMM2DQNT_ptr;                            //dequant matrix for GEMM2, size sub_X*dim

    cl_float *expt_scale_ptr;                           //offset for expt_scale

    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    TileSize  tileSize;

    cl_float *sorted_weight_ptr;                        //offset of sorted_weight_buf
    uint32   *sorted_token_ids_ptr;                     //offset of sorted_token_ids

    if (tWithTopk) {
        X_topk = topk;
    }

    FILE *f_trace = fopen("moe_data_trace_xbf16.hex", "w+t");
    if (f_trace == NULL) {
        printf("Failed to open moe_data_trace_xbf16.hex!!!!!!\n");
        return;
    }

    //alloc temporary compute results
    X_ptr_BF16    = new cl_half [sub_X*dim];            //size sub_X*dim;
    X_step_BF16   = new cl_half [sub_X*dbg_subK];       //size sub_X*dbg_subK;
    X_step_F32    = new cl_float[sub_X*dbg_subK];       //size sub_X*dbg_subK;
    X_ptr         = new TT       [sub_X*dbg_subK];       //size sub_X*dbg_subK;
    X_DQNT_vec    = new cl_float[sub_X*1];              //size sub_X*1;
    GEMM0DQNT_ptr = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1DQNT_ptr = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2DQNT_vec = new cl_float[sub_X*1];              //size sub_X*1;
    rowMax_vec    = new cl_float[sub_X*2];              //size sub_X*2;
    GEMM2DQNT_ptr = new cl_float[sub_X*dim];            //size sub_X*dim;
    GEMM0_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM0_step    = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_step    = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2_float   = new cl_float[sub_X*dbg_subD];       //size sub_X*dbg_subD;
    //GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    GEMM1_int32   = (int32*)   GEMM1_float;
    GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    getTileSize(in_type, layout, &tileSize);
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    if (hidden_dim % sub_GU != 0) {
        printf("Not divisible hidden_dim:%d,sub_GU:%d\n", hidden_dim, sub_GU);
        assert(0);
    }
    if (dim % dbg_subD != 0) {
        printf("Not divisible dim:%d,dbg_subD:%d\n", dim, dbg_subD);
        assert(0);
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d, sub_X_cnt:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU,    sub_X_cnt);
        fprintf(f_trace, "TGS_Y_AXIS:%d, TGS_X_AXIS:%d\n",          sub_X_cnt, hidden_dim/sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d, X_topk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk,    X_topk);
        fprintf(f_trace, "DBG_SUB_D:%d, DBG_SUB_K:%d\n", dbg_subD, dbg_subK);
    }

    TT       *G_step_ptr     = new TT[sub_GU   *dbg_subK];                                                //subGU *dbg_subK,  fast changing dbg_subK
    TT       *U_step_ptr     = new TT[sub_GU   *dim];                                                     //sub_GU*dim, fast changing dim
    TT       *D_step_ptr     = new TT[dbg_subD *sub_GU];                                                  //dbg_subD*sub_GU, fast changing sub_GU

    for(uint32 y = 0; y < sub_X_cnt; y++) {                                                             //thread group Y axis
        uint32 expert           = sorted_expert_ids[y];                                                 //Get expert ID according to y AXIS
        //offset pointers
        sorted_weight_ptr       = sorted_weight_buf + sub_X*y;                                          //size sub_X*1
        sorted_token_ids_ptr    = sorted_token_ids  + sub_X*y;                                          //size 1*sub_X
        G_ptr                   = GU_buf            + expert*hidden_dim*dim + u1*expert*hidden_dim*dim; //size hidden_dim*dim; in shuffle format
        G_DQNT_ptr              = GU_dqn_buf        + expert*hidden_dim     + u1*expert*hidden_dim;     //size 1*hidden_dim
        SMT_QNT_ptr             = Smooth_qnt_buf    + expert*hidden_dim;                                //size 1*hidden_dim
        D_ptr                   = D_buf             + expert*dim*hidden_dim;                            //size dim*hidden_dim; in shuffle format
        D_DQNT_ptr              = D_dqn_buf         + expert*dim;                                       //size 1*dim
        U_ptr                   = G_ptr             + hidden_dim*dim;                                   //size hidden_dim*dim; in shuffle format
        U_DQNT_ptr              = G_DQNT_ptr        + hidden_dim;                                       //size 1*hidden_dim

        expt_scale_ptr          = expt_scale        + expert*dim;

        //Prepare X data and dequant vector for this expert
        for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
            uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
            if (tokenIdx == batch) {
                memset(X_ptr_BF16+sub_X_idx*dim, 0,                  dim*sizeof(cl_half));
            } else {
                memcpy(X_ptr_BF16+sub_X_idx*dim, X_buf+tokenIdx*dim, dim*sizeof(cl_half));
            }
        }

        uint32 x = 0;                                                                   //thread group X axis
        uint32 col_major = 1;
        uint32 row_major = 0;
        
        for(uint32 TG_idx = 0;  TG_idx < hidden_dim; TG_idx += sub_GU) {                //Thread group offset
            memset(GEMM0_float, 0, sizeof(cl_float)*sub_X*sub_GU);
            uint32 G_HD_idx = TG_idx;                                                   //G's hidden_dim idx
            for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                matrix_crop_block(X_ptr_BF16, X_step_BF16,  sub_X,      dim, 0,         sub_K_idx, sub_X,   dbg_subK);
                moe_shuffleback_block(G_ptr, G_step_ptr,    hidden_dim, dim, G_HD_idx,  sub_K_idx, sub_GU,  dbg_subK, tileSize.tileSizeMajor, tileSize.tileSizeMinor);

                //prepare data
                moe_v_cvt_f32_bf16(X_step_BF16,                             sub_X,      dbg_subK,       X_step_F32);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-BF16-IN: \n",                  y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_BF16,       f_trace,        sub_X,      dbg_subK,       BF16);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-FP32-OUT: \n",                 y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                }

                smooth_quant(X_step_F32,  expt_scale_ptr+sub_K_idx,         sub_X,      dbg_subK);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++SCALE-IN: \n",                   y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(expt_scale_ptr+sub_K_idx,   f_trace,       1,          dbg_subK,       FP32);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++SCALE-OUT: \n",                  y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                }

                quant(X_step_F32,  X_DQNT_vec,                              sub_X,      dbg_subK, quant_deno);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++QUANT-OUT: \n",                  y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++DEQUANT-VEC-OUT: \n",            y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,              FP32);
                }

                if (in_type == INT8) {
                    matrix_v_cvt_i8_f32(X_step_F32,                             sub_X,      dbg_subK,    (int8*)X_ptr);
                } else {
                    matrix_v_cvt_to_type(X_step_F32, X_ptr,                     sub_X,      dbg_subK,    in_type, fp_format_des, f8_bias_des);
                }

                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-BITS8-OUT: \n",                 y, x, expert,    sub_K_idx);
                    fmha_dumpMatrixInHex(X_ptr,             f_trace,        sub_X,      dbg_subK,       in_type);
                }

                matrix_mul_fast_in_K(X_ptr, G_step_ptr, GEMM0_step,         sub_X,      sub_GU,     dbg_subK, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_ptr,             f_trace,        sub_X,      dbg_subK,   in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                    fmha_dumpMatrixInHex(G_step_ptr,        f_trace,        sub_GU,     dbg_subK,   in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-STEP-OUT: \n",                             y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_step,        f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                }

                if (in_type == INT8) {
                    //Convert to F32 before dequant
                    matrix_v_cvt_f32_i32((int32*)GEMM0_step,                    sub_X,      sub_GU);
                }
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-CONVERT-F32-OUT: \n",                      y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_step,        f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                }

                //GEMM0 dequant
                moe_dequant_onCol(GEMM0_step, X_DQNT_vec,                   sub_X,      sub_GU);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_DEQUANT_VEC: \n",                              y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,         FP32,        row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-DEQUANT-OUT: \n",                          y, x, sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_step,        f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }

                matrix_accumlate(GEMM0_step, GEMM0_float, GEMM0_float,      sub_X,      sub_GU,    FP32,    FP32);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-STEP-OUT: \n",                             y, x, sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }
            } //end of sub_K_idx

            //GEMM0 dequant
            smooth_quant(GEMM0_float, G_DQNT_ptr,                           sub_X,      sub_GU);
            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_DEQUANT_VEC[%04d]: \n",                                               y, x, expert);
                fmha_dumpMatrixInHex(G_DQNT_ptr,            f_trace,        1,          sub_GU,     FP32,       row_major);
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0-FINAL-OUT: \n",                                                   y, x);
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    sub_X,      sub_GU);
            } else {
                //GEMM0 SILU
                matrix_SILU(GEMM0_float,                                    sub_X,      sub_GU);
            }
            if(dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++GELU-OUT: \n",                                    y, x, expert);
                } else {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++SILU-OUT: \n",                                    y, x, expert);
                }
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            if (u1) {
                memset(GEMM1_float, 0, sizeof(cl_float)*sub_X*sub_GU);
                for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                    //GEMM1
                    matrix_crop_block(X_ptr_BF16, X_step_BF16,  sub_X,      dim, 0,         sub_K_idx, sub_X,   dbg_subK);
                    moe_shuffleback_block(U_ptr, U_step_ptr,    hidden_dim, dim, G_HD_idx,  sub_K_idx, sub_GU,  dbg_subK, tileSize.tileSizeMajor, tileSize.tileSizeMinor);

                    //prepare data
                    moe_v_cvt_f32_bf16(X_step_BF16,                             sub_X,      dbg_subK,       X_step_F32);
                    if (dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-BF16-IN: \n",                  y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_BF16,       f_trace,        sub_X,      dbg_subK,       BF16);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-FP32-OUT: \n",                 y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                    }

                    smooth_quant(X_step_F32,  expt_scale_ptr+sub_K_idx,         sub_X,      dbg_subK);
                    if (dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++SCALE-IN: \n",                   y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(expt_scale_ptr+sub_K_idx,   f_trace,       1,          dbg_subK,       FP32);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++SCALE-OUT: \n",                  y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                    }

                    quant(X_step_F32,  X_DQNT_vec,                              sub_X,      dbg_subK, quant_deno);
                    if (dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++QUANT-OUT: \n",                  y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_F32,        f_trace,        sub_X,      dbg_subK,       FP32);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++DEQUANT-VEC-OUT: \n",            y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,              FP32);
                    }

                    if (in_type == INT8) {
                        matrix_v_cvt_i8_f32(X_step_F32,                             sub_X,      dbg_subK,    (int8*)X_ptr);
                    } else {
                        matrix_v_cvt_to_type(X_step_F32, X_ptr,                     sub_X,      dbg_subK,    in_type, fp_format_des, f8_bias_des);
                    }

                    if (dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++EXPERT[%04d]++++sub_K_idx[%04d]++++X-BITS8-OUT: \n",                 y, x, expert,    sub_K_idx);
                        fmha_dumpMatrixInHex(X_ptr,             f_trace,        sub_X,      dbg_subK,       in_type);
                    }

                    matrix_mul_fast_in_K(X_ptr, U_step_ptr, GEMM1_step,         sub_X,      sub_GU,     dbg_subK, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_ptr,             f_trace,        sub_X,      dbg_subK,   in_type,    row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                        fmha_dumpMatrixInHex(U_step_ptr,        f_trace,        sub_GU,     dbg_subK,   in_type,    col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-STEP-OUT: \n",                             y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_step,        f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }

                    if (in_type == INT8) {
                        //Convert to F32 before dequant
                        matrix_v_cvt_f32_i32((int32*)GEMM1_step,                    sub_X,      sub_GU);
                    }
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-CONVERT-F32-OUT: \n",                      y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_step,        f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }

                    //GEMM1 dequant
                    moe_dequant_onCol(GEMM1_step, X_DQNT_vec,                   sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_DEQUANT_VEC: \n",                              y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,         FP32,        row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-DEQUANT-OUT: \n",                          y, x, sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_step,        f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                    }

                    matrix_accumlate(GEMM1_step, GEMM1_float, GEMM1_float,      sub_X,      sub_GU,    FP32,    FP32);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-STEP-OUT: \n",                             y, x, sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                    }
                }

                //GEMM1 dequant
                smooth_quant(GEMM1_float, U_DQNT_ptr,                           sub_X,      sub_GU);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_DEQUANT_VEC[%04d]: \n",                                               y, x, expert);
                    fmha_dumpMatrixInHex(U_DQNT_ptr,            f_trace,        1,          sub_GU,     FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1-FINAL-OUT: \n",                                                   y, x);
                    fmha_dumpMatrixInHex(GEMM1_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                }
                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          sub_X,      sub_GU);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0*GEMM1 OUT:\n",            y, x);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  sub_X,      sub_GU,    FP32,        row_major);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH_QUANT_VEC: \n",                                              y, x);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,       f_trace,        1,          sub_GU,     FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH-QUANT-OUT: \n",                                              y, x);
                        fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }
                }

                //Quant GEMM0, and generate GEMM2 dequant vector;
                quant(GEMM0_float, GEMM2DQNT_vec,                           sub_X,      sub_GU,     quant_deno,  GEMM0_float, rowMax_vec);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++QUANT-OUT: \n",                                                     y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-VEC-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      1,          FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-ROWMAX-VEC-OUT: \n",                                          y, x);
                    fmha_dumpMatrixInHex(rowMax_vec,        f_trace,        sub_X,      2,          FP32,       row_major);
                }
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            } else {
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++ConvertType[%04d]: \n",                               y, x, expert,   in_type);
                fmha_dumpMatrixInHex(GEMM0_T,               f_trace,        sub_X,      sub_GU,     in_type,    row_major);
            }

            //start GEMM2; input is sub_X*sub_GU row-major; sub_GU*dbg_subD col-major; out is sub_X*dbg_subD row-major
            D_DQNT_ptr = D_dqn_buf + expert*dim;                                        //size 1*dim; reset position for different TGs
            for (uint32 sub_D_idx = 0; sub_D_idx < dim; sub_D_idx += dbg_subD) {
                memset(GEMM2_float, 0, sizeof(cl_float)*sub_X*dbg_subD);
                uint32 D_HD_idx = TG_idx;                                               //D's hidden_dim idx
                moe_shuffleback_block(D_ptr,  D_step_ptr, dim, hidden_dim, sub_D_idx, D_HD_idx, dbg_subD,   sub_GU, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                matrix_mul_fast_in_K(GEMM0_T, D_step_ptr, GEMM2_float,      sub_X,      dbg_subD,           sub_GU, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM0_T,           f_trace,        sub_X,      sub_GU,     in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(D_step_ptr,        f_trace,        dbg_subD,   sub_GU,     in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GEMM2-OUT: \n",                                  y, x,           sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (in_type == INT8 || in_type == FP8) {
                    if (in_type == INT8) {
                        //Convert to F32 before dequant
                        matrix_v_cvt_f32_i32(GEMM2_int32,                       sub_X,      dbg_subD);
                    }
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-CONVERT-F32-OUT: \n",                                     y, x);
                        fmha_dumpMatrixInHex(GEMM2_float,   f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }

                    //Generate GEMM2 dequant matrix GEMM2DQNT_ptr=GEMM2DQNT_vec X D_DQNT_ptr sub_X*dbg_subD=sub_X*1 X 1*dbg_subD
                    fmha_matrix_mul(GEMM2DQNT_vec, D_DQNT_ptr,GEMM2DQNT_ptr,sub_X,      dbg_subD,   1,      FP32, FP32, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_DEQUANT_VEC[%04d]: \n",                                       y, x,           expert);
                        fmha_dumpMatrixInHex(D_DQNT_ptr,    f_trace,        1,          dbg_subD,   FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-MATRIX: \n",                                      y, x);
                        fmha_dumpMatrixInHex(GEMM2DQNT_ptr, f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }

                    //GEMM2 dequant and multiple weight
                    dequant_with_weight_vec(GEMM2_float, GEMM2DQNT_ptr,     sub_X,      dbg_subD,   sorted_weight_ptr);
                } else {
                    //just multiple weight
                    matrix_multi_weight_vec(GEMM2_float,                    sub_X,      dbg_subD,   sorted_weight_ptr);
                }

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-VALUE: \n",             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(sorted_weight_ptr, f_trace,        sub_X,      1,          FP32,       row_major);
                    if (in_type == INT8 || in_type == FP8) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++DEQUANT-WEIGHT-OUT: \n",   y, x, expert,   sub_D_idx);
                    } else {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-OUT: \n",           y, x, expert,   sub_D_idx);
                    }
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (o_elemSize == 2) {
                    //convert to target output
                    matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,           sub_X,      dbg_subD,   o_elemType, fp_format_des, f8_bias_des);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++++++D_EXPERT[%04d]++++ConvertType[%04d]: \n",    y, x, sub_D_idx, expert, in_type);
                    fmha_dumpMatrixInHex(GEMM2_half,        f_trace,        sub_X,      dbg_subD,   BF16,       row_major);
                }

                //accumulate tokens for this expert
                for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
                    uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
                    uint32 tokenOffset  = tokenIdx*dim;
                    if (tokenIdx != batch) {
                        // accumulate 1*dim one by one
                        if (o_elemSize == 2) {
                            matrix_accumulate_block(cpu_O_buf_half+tokenOffset,  GEMM2_half+sub_X_idx*dbg_subD,  (cl_float*)(cpu_O_buf_half+tokenOffset),   1, dim, 0, sub_D_idx, 1, dbg_subD, BF16, BF16);
                        } else {
                            matrix_accumulate_block(cpu_O_buf_ptr+tokenOffset,   GEMM2_float+sub_X_idx*dbg_subD, cpu_O_buf_ptr+tokenOffset,                 1, dim, 0, sub_D_idx, 1, dbg_subD, FP32, FP32);
                        }
                    }
                }
                D_DQNT_ptr += dbg_subD;                                                 //dequant offset
            }//end of sub_D_idx
            x++;
            G_DQNT_ptr     += sub_GU;                                                   //dequant offset
            U_DQNT_ptr     += sub_GU;
            SMT_QNT_ptr    += sub_GU;
        }//end of TG_idx
    }//end of y

    delete []X_ptr_BF16;
    delete []X_step_BF16;
    delete []X_step_F32;
    delete []X_ptr;
    delete []X_DQNT_vec;
    delete []GEMM0DQNT_ptr;
    delete []GEMM1DQNT_ptr;
    delete []GEMM2DQNT_vec;
    delete []rowMax_vec;
    delete []GEMM2DQNT_ptr;
    delete []GEMM0_float;
    delete []GEMM0_step;
    delete []GEMM1_float;
    delete []GEMM1_step;
    delete []GEMM2_float;

    delete []G_step_ptr;
    delete []U_step_ptr;
    delete []D_step_ptr;
    fclose(f_trace);
    return;
}

template<typename TT>
static void moe_block_scale_ref_std(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    cl_float *X_dqn_buf, cl_float *GU_dqn_buf, cl_float *D_dqn_buf, cl_float *Smooth_qnt_buf, 
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU,
    uint32 group_in_k, uint32 group_in_n,
    DATA_TYPE in_type=BF16, uint32 dbg_trace=0, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = false,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   batch_cpt  = 1;//batch in compute, 1 means compute token one by one
    uint32   X_topk     = 1;
    TT        *X_ptr;        //offset of X
    TT        *G_ptr;        //offset of G
    TT        *U_ptr;        //offset of U
    TT        *D_ptr;        //offset of D
    TT        *GEMM0_T;      //for GEMM2 operation

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;  //float pointer to GEMM0 result
    int32    *GEMM0_int32;  //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;  //float pointer to GEMM1 result
    int32    *GEMM1_int32;  //int32 pointer to GEMM1 result
    cl_float *GEMM2_float;  //float pointer to GEMM2 result
    int32    *GEMM2_int32;  //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;   //half  pointer to GEMM2 result, for 16bits

    cl_float *GEMM0DQNT;    //dequant matrix for GEMM0, size eprt*batch*hidden_dim
    cl_float *GEMM1DQNT;    //dequant matrix for GEMM1, size eprt*batch*hidden_dim
    cl_float *GEMM2DQNT_vec;//dequant vector for GEMM2, size batch_cpt*1
    cl_float *G_DQNT_ptr;   //offset of G_dqn_buf, size GU_dqn_n_exp*GU_dqn_k
    cl_float *U_DQNT_ptr;   //offset of U_dqn_buf, size GU_dqn_n_exp*GU_dqn_k
    cl_float *D_DQNT_ptr;   //offset of D_dqn_buf, size D_dqn_n_exp *D_dqn_k
    cl_float *X_DQNT_ptr;   //offset of X_dqn_buf, size 1*X_dqn_k
    cl_float *SMT_QNT_ptr;  //offset of Smooth_qnt_buf
    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    do_smooth = false;
    printf("do_smooth set to false internally\n");
    if (tWithTopk) {
        printf("WARNING, tWithTopk should be false!!!!!\n");
        X_topk = topk;
    }
    uint32 X_dqn_m      = batch;
    uint32 X_dqn_k      = dim/group_in_k;
    uint32 GU_dqn_k     = dim/group_in_k;
    uint32 GU_dqn_n_exp = hidden_dim;
    uint32 D_dqn_k      = hidden_dim/group_in_k;
    uint32 D_dqn_n_exp  = dim;

    FILE *f_trace = fopen("moe_data_trace_block_scale_std.hex", "w+t");
    if (f_trace == NULL) {
       printf("Failed to open moe_data_trace_block_scale_std.hex!!!!!!\n");
       return;
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk);
        fprintf(f_trace, "fp8_format:%d fp8_bias:%d\n", fp_format_src0, f8_bias_src0);
    }

    //alloc temporary compute results
    GEMM2DQNT_vec = new cl_float[batch_cpt*D_dqn_k];    //size batch_cpt*D_dqn_k
    GEMM0_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM1_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM2_float   = new cl_float[batch_cpt*dim];        //size batch_cpt*dim
    GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    GEMM1_int32   = (int32*)   GEMM1_float;
    GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    bool col_major= true;
    bool row_major= false;

    for (uint32 b = 0; b < batch; b += batch_cpt) { //use batch_cpt make below code looks general and easy to extract in future
        //each token need to interact with topk experts and combine result into output
        for (uint32 tk = 0; tk < topk; tk++) {
            uint32   e      = getTokenExpert(*(TKI_buf+b*topk+tk), tWithTopk);   //real expert idx may reside in low 24bits
            uint32   t_topk = getTokenTopk  (*(TKI_buf+b*topk+tk), tWithTopk);
            cl_float weight = *(W_buf  +b*topk+tk);
            //offset pointers
            X_ptr           = X_buf                 + b*dim     + t_topk*batch*dim;             //size batch_cpt*dim
            G_ptr           = GU_buf                + e*hidden_dim*dim + u1*e*hidden_dim*dim;   //size hidden_dim*dim
            U_ptr           = G_ptr                 + hidden_dim*dim;                           //size hidden_dim*dim
            D_ptr           = D_buf                 + e*dim*hidden_dim;                         //size dim*hidden_dim
            X_DQNT_ptr      = X_dqn_buf             + b*X_dqn_k;
            G_DQNT_ptr      = GU_dqn_buf            + e*GU_dqn_k*GU_dqn_n_exp + u1*e*GU_dqn_k*GU_dqn_n_exp;
            U_DQNT_ptr      = G_DQNT_ptr            + GU_dqn_k*GU_dqn_n_exp;
            D_DQNT_ptr      = D_dqn_buf             + e*D_dqn_k*D_dqn_n_exp;                    //size D_dqn_k*D_dqn_n_exp
            SMT_QNT_ptr     = Smooth_qnt_buf        + e*hidden_dim;                             //size 1*hidden_dim
            cpu_O_buf_ptr   = cpu_O_buf             + b*dim;                                    //size batch_cpt*dim
            cpu_O_buf_half  = (cl_half*) cpu_O_buf  + b*dim;                                    //size batch_cpt*dim
            //clean temporay buffers
            memset(GEMM0_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM1_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM2_float,   0, batch_cpt*dim       *sizeof(cl_float));
            memset(GEMM2DQNT_vec, 0, batch_cpt*1         *sizeof(cl_float));

            //GEMM0=XxGATE INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*hidden_dim
            matrix_mul_block_scale_fast_in_K(X_ptr, G_ptr, GEMM0_float, X_DQNT_ptr, G_DQNT_ptr, 
                                                                            batch_cpt,      hidden_dim,     dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            if (dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++X-IN\n",                         b, e);
                fmha_dumpMatrixInHex(X_ptr,             f_trace,            batch_cpt,      dim,            in_type,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++G-IN\n",                         b, e);
                fmha_dumpMatrixInHex(G_ptr,             f_trace,            hidden_dim,     dim,            in_type,   col_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++X-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(X_DQNT_ptr,        f_trace,            batch_cpt,      X_dqn_k,        FP32,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++G-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(G_DQNT_ptr,        f_trace,            GU_dqn_n_exp,   GU_dqn_k,       FP32,   col_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0-OUT\n",                    b, e);
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            } else {
                matrix_SILU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            }
            if (dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 GELU-OUT: \n",         b, e);
                } else {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SILU-OUT: \n",         b, e);
                }
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }

            if (u1) {
                //GEMM1=XxGATE INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*hidden_dim
                matrix_mul_block_scale_fast_in_K(X_ptr, U_ptr, GEMM1_float, X_DQNT_ptr, U_DQNT_ptr, 
                                                                            batch_cpt,      hidden_dim,     dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++X-IN\n",                         b, e);
                    fmha_dumpMatrixInHex(X_ptr,             f_trace,            batch_cpt,      dim,            in_type,   row_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++U-IN\n",                         b, e);
                    fmha_dumpMatrixInHex(U_ptr,             f_trace,            hidden_dim,     dim,            in_type,   col_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++X-SCALE\n",                      b, e);
                    fmha_dumpMatrixInHex(X_DQNT_ptr,        f_trace,            batch_cpt,      X_dqn_k,        FP32,   row_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++U-SCALE\n",                      b, e);
                    fmha_dumpMatrixInHex(U_DQNT_ptr,        f_trace,            GU_dqn_n_exp,   GU_dqn_k,       FP32,   col_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM1-OUT\n",                    b, e);
                    fmha_dumpMatrixInHex(GEMM1_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }

                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          batch_cpt,      hidden_dim);
                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0*GEMM1 OUT:\n",             b, e);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  batch_cpt,      hidden_dim,     FP32,   0);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      batch_cpt,      hidden_dim);
                    if(dbg_trace) {
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-BUF-IN:\n",     b, e);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,   f_trace,            1,              hidden_dim,     FP32,   0);
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-QUANT-OUT:\n",  b, e);
                        fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    }
                }

                //Quant GEMM0, and generate GEMM2 dequant vector; 
                act_quant(GEMM0_float,  GEMM2DQNT_vec,                      batch_cpt,      hidden_dim,     group_in_k, quant_deno);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-OUT:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-VEC:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec, f_trace,            batch_cpt,      D_dqn_k,        FP32,   0);
                }

                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
            } else {
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM0_T,           f_trace,            batch_cpt,      hidden_dim,     in_type, 0);
                fprintf(f_trace, "token:%d, expert:%d, ++++D: \n",                          b, e);
                fmha_dumpMatrixInHex(D_ptr,             f_trace,            dim,            hidden_dim,     in_type, 1);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,            batch_cpt,      D_dqn_k,        FP32,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++D-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(D_DQNT_ptr,        f_trace,            D_dqn_n_exp,    D_dqn_k,        FP32,   col_major);
            }

            if (true) {
                //GEMM2=GEMM0xDOWN  INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*dim
                matrix_mul_block_scale_fast_in_K(GEMM0_T, D_ptr, GEMM2_float,   GEMM2DQNT_vec, D_DQNT_ptr, 
                                                                            batch_cpt,      dim,            hidden_dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            } else {
                /*
                //for debug subGU purpose, just leave it here, and disabled
                cl_float *gemm2_tmp = new cl_float[batch_cpt*dim]();
                uint32 subGU = 256;
                for (uint32 i = 0; i < hidden_dim/subGU; i++) {
                    memset(gemm2_tmp, 0, sizeof(cl_float)*batch_cpt*dim);
                    TT *gemm0_tmp = new TT[batch_cpt*subGU]();
                    TT *D_tmp     = new TT[subGU*dim]();
                    cl_float *gemm0_scale = new cl_float [batch_cpt*subGU/group_in_k]();
                    cl_float *D_scale     = new cl_float [dim*subGU/group_in_k]();
                    moe_matrix_crop_back(GEMM0_T+i*subGU,                   batch_cpt,  dim,                    batch_cpt,  subGU,              gemm0_tmp);
                    moe_matrix_crop_back(D_ptr  +i*subGU,                   dim,        hidden_dim,             dim,        subGU,              D_tmp);
                    moe_matrix_crop_back(GEMM2DQNT_vec+i*subGU/group_in_k,  batch_cpt,  dim/group_in_k,         batch_cpt,  subGU/group_in_k,   gemm0_scale);
                    moe_matrix_crop_back(D_DQNT_ptr   +i*subGU/group_in_k,  dim,        hidden_dim/group_in_k,  dim,        subGU/group_in_k,   D_scale);
                    matrix_mul_block_scale_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,   gemm0_scale, D_scale, 
                                                                            batch_cpt,      dim,            subGU,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GM0-IN\n",                          b, e, i);
                    fmha_dumpMatrixInHex(gemm0_tmp,         f_trace,            batch_cpt,      subGU,              in_type,    row_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++D-IN\n",                            b, e, i);
                    fmha_dumpMatrixInHex(D_tmp,             f_trace,            dim,            subGU,              in_type,    col_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GM0-SCALE\n",                       b, e, i);
                    fmha_dumpMatrixInHex(gemm0_scale,       f_trace,            batch_cpt,      subGU/group_in_k,   FP32,       row_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++D-SCALE\n",                         b, e, i);
                    fmha_dumpMatrixInHex(D_scale,           f_trace,            subGU/group_in_k,   dim,            FP32,       col_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GEMM2-OUT\n",                       b, e, i);
                    fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,            batch_cpt,          dim,            FP32,       row_major);
                    
                    matrix_accumlate(GEMM2_float,  gemm2_tmp,  (cl_float*)GEMM2_float,   batch_cpt, dim,            FP32,       FP32);
                    delete []gemm0_tmp;
                    delete []D_tmp;
                    delete []gemm0_scale;
                    delete []D_scale;
                }

                delete []gemm2_tmp;*/
            }

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 FINAL OUT: \n",                  b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            matrix_multi_weight(GEMM2_float,                            batch_cpt,      dim,            weight);

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-VALUE: \n",         b, e);
                fmha_dumpMatrixInHex(&weight,           f_trace,            1,              1,              FP32,   0);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-OUT: \n",           b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            if (o_elemSize == 2) {
                //convert to target output
                matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,               batch_cpt,      dim,            o_elemType, fp_format_des, f8_bias_des);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM2_half,        f_trace,            batch_cpt,      dim,            BF16,   0);
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_half,  GEMM2_half,  (cl_float*)cpu_O_buf_half,   batch_cpt, dim, BF16,   BF16);
            } else {
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_ptr,   GEMM2_float, cpu_O_buf_ptr,               batch_cpt, dim, FP32,   FP32);
            }
        }
    }
    fclose(f_trace);

    delete []GEMM0_float;
    delete []GEMM1_float;
    delete []GEMM2_float;
    delete []GEMM2DQNT_vec;
    return;
}

//for UP enabled, GEMM2-input = quant[Silu(dequant(GEMM0)) * (dequant(GEMM1))]; no smooth quant before quant
//standard golden compute token one by one
template<typename TT>
static void moe_mxfpX_ref_std(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    uint8 *X_dqn_buf, uint8 *GU_dqn_buf, uint8 *D_dqn_buf, cl_float *Smooth_qnt_buf, 
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU,
    uint32 group_in_k, uint32 group_in_n,
    DATA_TYPE in_type=FP4, uint32 dbg_trace=0, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = false,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   batch_cpt  = 1;//batch in compute, 1 means compute token one by one
    //uint32   X_topk     = 1;
    TT        *X_ptr;        //offset of X
    TT        *G_ptr;        //offset of G
    TT        *U_ptr;        //offset of U
    TT        *D_ptr;        //offset of D
    TT        *GEMM0_T;      //for GEMM2 operation

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;  //float pointer to GEMM0 result
    //int32    *GEMM0_int32;  //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;  //float pointer to GEMM1 result
    //int32    *GEMM1_int32;  //int32 pointer to GEMM1 result
    cl_float *GEMM2_float;  //float pointer to GEMM2 result
    //int32    *GEMM2_int32;  //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;   //half  pointer to GEMM2 result, for 16bits

    //cl_float *GEMM0DQNT;    //dequant matrix for GEMM0, size eprt*batch*hidden_dim
    //cl_float *GEMM1DQNT;    //dequant matrix for GEMM1, size eprt*batch*hidden_dim
    uint8 *GEMM2DQNT_vec;   //dequant vector for GEMM2, size batch_cpt*1
    uint8 *G_DQNT_ptr;      //offset of G_dqn_buf, size GU_dqn_n_exp*GU_dqn_k
    uint8 *U_DQNT_ptr;      //offset of U_dqn_buf, size GU_dqn_n_exp*GU_dqn_k
    uint8 *D_DQNT_ptr;      //offset of D_dqn_buf, size D_dqn_n_exp *D_dqn_k
    uint8 *X_DQNT_ptr;      //offset of X_dqn_buf, size 1*X_dqn_k
    cl_float *SMT_QNT_ptr;  //offset of Smooth_qnt_buf
    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    do_smooth = false;
    printf("do_smooth set to false internally\n");
    if (tWithTopk) {
        printf("WARNING, tWithTopk should be false!!!!!\n");
        //X_topk = topk;
    }
    //uint32 X_dqn_m      = batch;
    uint32 X_dqn_k      = dim/group_in_k;
    uint32 GU_dqn_k     = dim/group_in_k;
    uint32 GU_dqn_n_exp = hidden_dim;
    uint32 D_dqn_k      = hidden_dim/group_in_k;
    uint32 D_dqn_n_exp  = dim;

    FILE *f_trace = fopen("moe_data_trace_mxfpX_std.hex", "w+t");
    if (f_trace == NULL) {
       printf("Failed to open moe_data_trace_mxfpX_std.hex!!!!!!\n");
       return;
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk);
        fprintf(f_trace, "fp8_format:%d fp8_bias:%d\n", fp_format_src0, f8_bias_src0);
    }

    //alloc temporary compute results
    GEMM2DQNT_vec = new uint8[batch_cpt*D_dqn_k];    //size batch_cpt*D_dqn_k
    GEMM0_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM1_float   = new cl_float[batch_cpt*hidden_dim]; //size batch_cpt*hidden_dim
    GEMM2_float   = new cl_float[batch_cpt*dim];        //size batch_cpt*dim
    //GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    //GEMM1_int32   = (int32*)   GEMM1_float;
    //GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    bool col_major= true;
    bool row_major= false;
    int offset_scl= 1;
    if (in_type == FP4) {
        offset_scl = 2;
    }

    for (uint32 b = 0; b < batch; b += batch_cpt) { //use batch_cpt make below code looks general and easy to extract in future
        //each token need to interact with topk experts and combine result into output
        for (uint32 tk = 0; tk < topk; tk++) {
            uint32   e      = getTokenExpert(*(TKI_buf+b*topk+tk), tWithTopk);   //real expert idx may reside in low 24bits
            uint32   t_topk = getTokenTopk  (*(TKI_buf+b*topk+tk), tWithTopk);
            cl_float weight = *(W_buf  +b*topk+tk);
            //offset pointers
            X_ptr           = X_buf                 + (b*dim     + t_topk*batch*dim)/offset_scl;             //size batch_cpt*dim
            G_ptr           = GU_buf                + (e*hidden_dim*dim + u1*e*hidden_dim*dim)/offset_scl;   //size hidden_dim*dim
            U_ptr           = G_ptr                 + hidden_dim*dim/offset_scl;                           //size hidden_dim*dim
            D_ptr           = D_buf                 + e*dim*hidden_dim/offset_scl;                         //size dim*hidden_dim
            X_DQNT_ptr      = X_dqn_buf             + b*X_dqn_k;
            G_DQNT_ptr      = GU_dqn_buf            + e*GU_dqn_k*GU_dqn_n_exp + u1*e*GU_dqn_k*GU_dqn_n_exp;
            U_DQNT_ptr      = G_DQNT_ptr            + GU_dqn_k*GU_dqn_n_exp;
            D_DQNT_ptr      = D_dqn_buf             + e*D_dqn_k*D_dqn_n_exp;                    //size D_dqn_k*D_dqn_n_exp
            SMT_QNT_ptr     = Smooth_qnt_buf        + e*hidden_dim;                             //size 1*hidden_dim
            cpu_O_buf_ptr   = cpu_O_buf             + b*dim;                                    //size batch_cpt*dim
            cpu_O_buf_half  = (cl_half*) cpu_O_buf  + b*dim;                                    //size batch_cpt*dim
            //clean temporay buffers
            memset(GEMM0_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM1_float,   0, batch_cpt*hidden_dim*sizeof(cl_float));
            memset(GEMM2_float,   0, batch_cpt*dim       *sizeof(cl_float));
            memset(GEMM2DQNT_vec, 0, batch_cpt*1         *sizeof(cl_float));

            //GEMM0=XxGATE output is batch_cpt*hidden_dim
            matrix_mul_block_scale_fast_in_K(X_ptr, G_ptr, GEMM0_float, X_DQNT_ptr, G_DQNT_ptr, 
                                                                            batch_cpt,      hidden_dim,     dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            if (dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++X-IN\n",                         b, e);
                fmha_dumpMatrixInHex(X_ptr,             f_trace,            batch_cpt,      dim,            in_type,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++G-IN\n",                         b, e);
                fmha_dumpMatrixInHex(G_ptr,             f_trace,            hidden_dim,     dim,            in_type,   col_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++X-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(X_DQNT_ptr,        f_trace,            batch_cpt,      X_dqn_k,        INT8,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++G-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(G_DQNT_ptr,        f_trace,            GU_dqn_n_exp,   GU_dqn_k,       INT8,   col_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0-OUT\n",                    b, e);
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            } else {
                matrix_SILU(GEMM0_float,                                    batch_cpt,      hidden_dim);
            }
            if (dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 GELU-OUT: \n",         b, e);
                } else {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SILU-OUT: \n",         b, e);
                }
                fmha_dumpMatrixInHex(GEMM0_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
            }

            if (u1) {
                //GEMM1=XxGATE INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*hidden_dim
                matrix_mul_block_scale_fast_in_K(X_ptr, U_ptr, GEMM1_float, X_DQNT_ptr, U_DQNT_ptr, 
                                                                            batch_cpt,      hidden_dim,     dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++X-IN\n",                         b, e);
                    fmha_dumpMatrixInHex(X_ptr,             f_trace,            batch_cpt,      dim,            in_type,   row_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++U-IN\n",                         b, e);
                    fmha_dumpMatrixInHex(U_ptr,             f_trace,            hidden_dim,     dim,            in_type,   col_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++X-SCALE\n",                      b, e);
                    fmha_dumpMatrixInHex(X_DQNT_ptr,        f_trace,            batch_cpt,      X_dqn_k,        INT8,   row_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++U-SCALE\n",                      b, e);
                    fmha_dumpMatrixInHex(U_DQNT_ptr,        f_trace,            GU_dqn_n_exp,   GU_dqn_k,       INT8,   col_major);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM1-OUT\n",                    b, e);
                    fmha_dumpMatrixInHex(GEMM1_float,       f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }

                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          batch_cpt,      hidden_dim);
                if (dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0*GEMM1 OUT:\n",             b, e);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  batch_cpt,      hidden_dim,     FP32,   0);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      batch_cpt,      hidden_dim);
                    if(dbg_trace) {
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-BUF-IN:\n",     b, e);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,   f_trace,            1,              hidden_dim,     FP32,   0);
                        fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 SMOOTH-QUANT-OUT:\n",  b, e);
                        fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    }
                }

                //Quant GEMM0, and generate GEMM2 dequant vector; 
                //act_quant(GEMM0_float,  GEMM2DQNT_vec,                      batch_cpt,      hidden_dim,     group_in_k, quant_deno);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-OUT:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-VEC:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec, f_trace,            batch_cpt,      D_dqn_k,        FP32,   0);
                }

                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
            } else {
                /*
                debug purpose
                unsigned short  *torch_O1   = new unsigned short[batch_cpt*hidden_dim];
                init_fromfile(torch_O1,     "dumpdata/torch_O1.bin",        batch_cpt*hidden_dim);
                moe_v_cvt_f32_bf16(torch_O1, batch_cpt, hidden_dim, GEMM0_float);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 fromBF16:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                }*/

                mxFPX_quant(GEMM0_float,  GEMM2DQNT_vec,                    batch_cpt,      hidden_dim,     group_in_k, quant_deno, in_type);
                if(dbg_trace) {
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-OUT:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM0_float,   f_trace,            batch_cpt,      hidden_dim,     FP32,   0);
                    fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 QUANT-VEC:\n",         b, e);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec, f_trace,            batch_cpt,      D_dqn_k,        INT8,   0);
                }

                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  batch_cpt,      hidden_dim,     in_type, fp_format_des, f8_bias_des);
            }

            //debug purpose
            //init_fromfile(GEMM0_T,        "dumpdata/a2_qt.bin",           batch_cpt*hidden_dim/2);

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM0 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM0_T,           f_trace,            batch_cpt,      hidden_dim,     in_type, 0);
                fprintf(f_trace, "token:%d, expert:%d, ++++D: \n",                          b, e);
                fmha_dumpMatrixInHex(D_ptr,             f_trace,            dim,            hidden_dim,     in_type, 1);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,            batch_cpt,      D_dqn_k,        INT8,   row_major);
                fprintf(f_trace, "token:%d, expert:%d, ++++D-SCALE\n",                      b, e);
                fmha_dumpMatrixInHex(D_DQNT_ptr,        f_trace,            D_dqn_n_exp,    D_dqn_k,        INT8,   col_major);
            }

            if (true) {
                //GEMM2=GEMM0xDOWN  INT8*INT8->INT32 or FP16*FP16->FP32 output is batch_cpt*dim
                matrix_mul_block_scale_fast_in_K(GEMM0_T, D_ptr, GEMM2_float,   GEMM2DQNT_vec, D_DQNT_ptr, 
                                                                            batch_cpt,      dim,            hidden_dim,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
            } else {
                /*
                //for debug subGU purpose, just leave it here, and disabled
                cl_float *gemm2_tmp = new cl_float[batch_cpt*dim]();
                uint32 subGU = 256;
                for (uint32 i = 0; i < hidden_dim/subGU; i++) {
                    memset(gemm2_tmp, 0, sizeof(cl_float)*batch_cpt*dim);
                    TT *gemm0_tmp = new TT[batch_cpt*subGU]();
                    TT *D_tmp     = new TT[subGU*dim]();
                    cl_float *gemm0_scale = new cl_float [batch_cpt*subGU/group_in_k]();
                    cl_float *D_scale     = new cl_float [dim*subGU/group_in_k]();
                    moe_matrix_crop_back(GEMM0_T+i*subGU,                   batch_cpt,  dim,                    batch_cpt,  subGU,              gemm0_tmp);
                    moe_matrix_crop_back(D_ptr  +i*subGU,                   dim,        hidden_dim,             dim,        subGU,              D_tmp);
                    moe_matrix_crop_back(GEMM2DQNT_vec+i*subGU/group_in_k,  batch_cpt,  dim/group_in_k,         batch_cpt,  subGU/group_in_k,   gemm0_scale);
                    moe_matrix_crop_back(D_DQNT_ptr   +i*subGU/group_in_k,  dim,        hidden_dim/group_in_k,  dim,        subGU/group_in_k,   D_scale);
                    matrix_mul_block_scale_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,   gemm0_scale, D_scale, 
                                                                            batch_cpt,      dim,            subGU,    group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GM0-IN\n",                          b, e, i);
                    fmha_dumpMatrixInHex(gemm0_tmp,         f_trace,            batch_cpt,      subGU,              in_type,    row_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++D-IN\n",                            b, e, i);
                    fmha_dumpMatrixInHex(D_tmp,             f_trace,            dim,            subGU,              in_type,    col_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GM0-SCALE\n",                       b, e, i);
                    fmha_dumpMatrixInHex(gemm0_scale,       f_trace,            batch_cpt,      subGU/group_in_k,   FP32,       row_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++D-SCALE\n",                         b, e, i);
                    fmha_dumpMatrixInHex(D_scale,           f_trace,            subGU/group_in_k,   dim,            FP32,       col_major);
                    fprintf(f_trace, "token:%d, expert:%d, step:%d, ++++GEMM2-OUT\n",                       b, e, i);
                    fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,            batch_cpt,          dim,            FP32,       row_major);
                    
                    matrix_accumlate(GEMM2_float,  gemm2_tmp,  (cl_float*)GEMM2_float,   batch_cpt, dim,            FP32,       FP32);
                    delete []gemm0_tmp;
                    delete []D_tmp;
                    delete []gemm0_scale;
                    delete []D_scale;
                }

                delete []gemm2_tmp;*/
            }

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 FINAL OUT: \n",                  b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            matrix_multi_weight(GEMM2_float,                            batch_cpt,      dim,            weight);

            if(dbg_trace) {
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-VALUE: \n",         b, e);
                fmha_dumpMatrixInHex(&weight,           f_trace,            1,              1,              FP32,   0);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 WEIGHT-OUT: \n",           b, e);
                fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            batch_cpt,      dim,            FP32,   0);
            }

            if (o_elemSize == 2) {
                //convert to target output
                matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,               batch_cpt,      dim,            o_elemType, fp_format_des, f8_bias_des);
                fprintf(f_trace, "token:%d, expert:%d, ++++GEMM2 ConvertType[%04d]: \n",    b, e, in_type);
                fmha_dumpMatrixInHex(GEMM2_half,        f_trace,            batch_cpt,      dim,            BF16,   0);
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_half,  GEMM2_half,  (cl_float*)cpu_O_buf_half,   batch_cpt, dim, BF16,   BF16);
            } else {
                //accumulate topk experts for single token
                matrix_accumlate(cpu_O_buf_ptr,   GEMM2_float, cpu_O_buf_ptr,               batch_cpt, dim, FP32,   FP32);
            }
        }
    }
    fclose(f_trace);

    delete []GEMM0_float;
    delete []GEMM1_float;
    delete []GEMM2_float;
    delete []GEMM2DQNT_vec;
    return;
}

template<typename TT>
static void moe_block_scale_ref_dev(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    cl_float *X_dqn_buf, cl_float *GU_dqn_buf, cl_float *D_dqn_buf, cl_float *Smooth_qnt_buf,
    uint32 *sorted_token_ids, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids, uint32 &sub_X_cnt,
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU, uint32 dbg_subD, uint32 dbg_subK,
    uint32 group_in_k, uint32 group_in_n,
    DATA_TYPE in_type=BF16, uint32 dbg_trace=1, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = true,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   X_topk     = 1;
    TT        *X_ptr;                                    //offset of X; temporary storage; type is TT int8
    TT        *G_ptr;                                    //offset of G
    TT        *U_ptr;                                    //offset of U
    TT        *D_ptr;                                    //offset of D
    TT        *GEMM0_T;                                  //for GEMM2 operation
    TT        *X_step_ptr;

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;                              //float pointer to GEMM0 result
    cl_float *GEMM0_step;                               //float pointer to GEMM0 result
    //int32    *GEMM0_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;                              //float pointer to GEMM0 result
    cl_float *GEMM1_step;                               //float pointer to GEMM0 result
    //int32    *GEMM1_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM2_float;                              //float pointer to GEMM2 result
    //int32    *GEMM2_int32;                              //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;                               //half  pointer to GEMM2 result, for 16bits

    uint32   *X_DQNT_addr;                              //size sub_X*1, token ids, used to extrace X scale when each step
    cl_float *X_DQNT_ptr;                               //offset of X_dqn_buf, increase by one stride, when advance group_in_k
    cl_float *G_DQNT_ptr;                               //offset of G_dqn_buf, size 1*sub_GU/group_in_n, increase by one stride, when advance group_in_k
    cl_float *U_DQNT_ptr;                               //offset of U_dqn_buf, size 1*sub_GU/group_in_n, increase by one stride, when advance group_in_k

    cl_float *X_DQNT_vec;                               //dequant vector for GEMM0, size sub_X*X_dqn_k
    cl_float *G_DQNT_vec;                               //dequant vector for GEMM0, size GU_dqn_n_exp*GU_dqn_k
    cl_float *U_DQNT_vec;                               //dequant vector for GEMM1, size GU_dqn_n_exp*GU_dqn_k
    cl_float *D_DQNT_vec;                               //dequant vector for GEMM2, size D_dqn_n_exp *D_dqn_k

    cl_float *SMT_QNT_ptr;                              //offset of Smooth_qnt_buf, size 1*sub_GU

    cl_float *GEMM2DQNT_vec;                            //dequant vector for GEMM2, size sub_X*1
    cl_float *rowMax_vec;                               //for debug purpose
    cl_float *D_DQNT_ptr;                               //offset of D_dqn_buf,      size 1*dim

    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    TileSize  tileSize;

    cl_float *sorted_weight_ptr;                        //offset of sorted_weight_buf
    uint32   *sorted_token_ids_ptr;                     //offset of sorted_token_ids

    do_smooth = false;
    printf("do_smooth set to false internally\n");
    if (tWithTopk) {
        printf("WARNING, tWithTopk should be false!!!!!\n");
        X_topk = topk;
    }

    uint32 GU_dqn_stride = hidden_dim/group_in_n;                   //used to offset from G_DQNT_ptr to U_DQNT_ptr
    uint32 GU_eprt_dqn_stride = GU_dqn_stride + u1*GU_dqn_stride;   //used to offset during accumulation
    uint32 X_dqn_stride  = batch;                                   //used to offset during accumulation
    uint32 D_dqn_strideK = dim/group_in_n;                          //used to offset during accumulation

    //uint32 X_dqn_m      = sub_X;
    uint32 X_dqn_k      = dbg_subK/group_in_k;
    uint32 GU_dqn_k     = dbg_subK/group_in_k;
    uint32 GU_dqn_n     = sub_GU/group_in_n;
    uint32 GU_dqn_n_exp = sub_GU;
    uint32 D_dqn_k      = sub_GU/group_in_k;
    uint32 D_dqn_n      = dbg_subD/group_in_n;
    uint32 D_dqn_n_exp  = dbg_subD;
    uint32 GEMM2_dqn_k  = sub_GU/group_in_k;

    FILE *f_trace = fopen("moe_data_trace_block_scale_dev.hex", "w+t");
    if (f_trace == NULL) {
        printf("Failed to open moe_data_trace_block_scale_dev.hex!!!!!!\n");
        return;
    }

    //alloc temporary compute results
    X_ptr         = new TT       [sub_X*dim];            //size sub_X*dim;
    X_step_ptr    = new TT       [sub_X*dbg_subK];       //size sub_X*dbg_subK;
    X_DQNT_addr   = new uint32  [sub_X];
    X_DQNT_vec    = new cl_float[sub_X*X_dqn_k];        //size sub_X*X_dqn_k;
    G_DQNT_vec    = new cl_float[GU_dqn_n_exp*GU_dqn_k];//size sub_GU*GU_dqn_k;
    U_DQNT_vec    = new cl_float[GU_dqn_n_exp*GU_dqn_k];//size sub_GU*GU_dqn_k;
    D_DQNT_vec    = new cl_float[D_dqn_n_exp*D_dqn_k];  //size D_dqn_n_exp*D_dqn_k
    GEMM2DQNT_vec = new cl_float[sub_X*GEMM2_dqn_k];    //size sub_X*GEMM2_dqn_k;
    rowMax_vec    = new cl_float[sub_X*2*GEMM2_dqn_k];  //size sub_X*2*GEMM2_dqn_k;
    GEMM0_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM0_step    = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_step    = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2_float   = new cl_float[sub_X*dbg_subD];       //size sub_X*dbg_subD;
    //GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    //GEMM1_int32   = (int32*)   GEMM1_float;
    //GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    getTileSize(in_type, layout, &tileSize);
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    if (hidden_dim % sub_GU != 0) {
        printf("Not divisible hidden_dim:%d,sub_GU:%d\n", hidden_dim, sub_GU);
        assert(0);
    }
    if (dim % dbg_subD != 0) {
        printf("Not divisible dim:%d,dbg_subD:%d\n", dim, dbg_subD);
        assert(0);
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d, sub_X_cnt:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU,    sub_X_cnt);
        fprintf(f_trace, "TGS_Y_AXIS:%d, TGS_X_AXIS:%d\n",          sub_X_cnt, hidden_dim/sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d, X_topk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk,    X_topk);
        fprintf(f_trace, "DBG_SUB_D:%d, DBG_SUB_K:%d\n", dbg_subD, dbg_subK);
    }

    TT       *G_step_ptr     = new TT[sub_GU   *dbg_subK];                                                //subGU *dbg_subK, fast changing dbg_subK
    TT       *U_step_ptr     = new TT[sub_GU   *dbg_subK];                                                //sub_GU*dbg_subK, fast changing dbg_subK
    TT       *D_step_ptr     = new TT[dbg_subD *sub_GU];                                                  //dbg_subD*sub_GU, fast changing sub_GU

    int stride_expert_GUDQN  = hidden_dim*dim/group_in_k/group_in_n;
    for(uint32 y = 0; y < sub_X_cnt; y++) {                                                             //thread group Y axis
        uint32 expert           = sorted_expert_ids[y];                                                 //Get expert ID according to y AXIS
        //offset pointers
        sorted_weight_ptr       = sorted_weight_buf + sub_X*y;                                          //size sub_X*1
        sorted_token_ids_ptr    = sorted_token_ids  + sub_X*y;                                          //size 1*sub_X
        G_ptr                   = GU_buf            + expert*hidden_dim*dim + u1*expert*hidden_dim*dim; //size hidden_dim*dim; in shuffle format
        G_DQNT_ptr              = GU_dqn_buf        + expert*stride_expert_GUDQN + u1*expert*stride_expert_GUDQN;     //size 
        SMT_QNT_ptr             = Smooth_qnt_buf    + expert*hidden_dim;                                //size 1*hidden_dim
        D_ptr                   = D_buf             + expert*dim*hidden_dim;                            //size dim*hidden_dim; in shuffle format
//        D_DQNT_ptr              = D_dqn_buf         + expert*dim;                                       //size 1*dim
        U_ptr                   = G_ptr             + hidden_dim*dim;                                   //size hidden_dim*dim; in shuffle format
        U_DQNT_ptr              = G_DQNT_ptr        + GU_dqn_stride;                                    //size 1*hidden_dim/group_in_n

        //Prepare X data and dequant vector for this expert
        for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
            uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
            X_DQNT_addr[sub_X_idx] = tokenIdx;
            if (tokenIdx == batch) {
                memset(X_ptr+sub_X_idx*dim, 0,                  dim*sizeof(TT));
            } else {
                memcpy(X_ptr+sub_X_idx*dim, X_buf+tokenIdx*dim, dim*sizeof(TT));
            }
        }

        uint32 x = 0;                                                                   //thread group X axis
        uint32 col_major = 1;
        uint32 row_major = 0;
        
        for(uint32 TG_idx = 0;  TG_idx < hidden_dim; TG_idx += sub_GU) {                //Thread group offset
            memset(GEMM0_float, 0, sizeof(cl_float)*sub_X*sub_GU);
            uint32 G_HD_idx = TG_idx;                                                   //G's hidden_dim idx
            //for each dbg_subK, first prepare X and G data; then prepare scale data; then matrix multiple with scale
            //if dbg_subK==group_in_k, then should match kernel
            //if dbg_subK==dim, then should match std golden
            X_DQNT_ptr      = X_dqn_buf;
            cl_float *G_DQNT_ptr_k = G_DQNT_ptr;  //TG offset for G scale
            for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                matrix_crop_block(X_ptr, X_step_ptr,        sub_X,      dim, 0,         sub_K_idx, sub_X,   dbg_subK);
                moe_shuffleback_block(G_ptr, G_step_ptr,    hidden_dim, dim, G_HD_idx,  sub_K_idx, sub_GU,  dbg_subK, tileSize.tileSizeMajor, tileSize.tileSizeMinor);

                uint32 k_idx = 0;
                for (uint32 group_k_idx = 0; group_k_idx < dbg_subK; group_k_idx+=group_in_k) {
                    //X_DQNT_vec fast-changing is X_dqn_k
                    for (uint32 x_idx = 0; x_idx < sub_X; x_idx++) {
                        uint32 tokenIdx = X_DQNT_addr[x_idx];
                        if (tokenIdx == batch) {
                            *(X_DQNT_vec+x_idx*X_dqn_k+k_idx) = 0;
                        } else {
                            *(X_DQNT_vec+x_idx*X_dqn_k+k_idx) = *(X_DQNT_ptr+tokenIdx);
                        }
                    }

                    //G_DQNT_vec fast-changing is GU_dqn_k
                    for (uint32 g_idx = 0; g_idx < GU_dqn_n_exp; g_idx++) {
                        uint32 g_idx_grped = g_idx/group_in_n;
                        *(G_DQNT_vec+g_idx*GU_dqn_k+k_idx) = *(G_DQNT_ptr_k+g_idx_grped);
                    }

                    G_DQNT_ptr_k += GU_eprt_dqn_stride;
                    X_DQNT_ptr   += X_dqn_stride;
                    k_idx++;
                }

                matrix_mul_block_scale_fast_in_K(X_step_ptr, G_step_ptr, GEMM0_step, X_DQNT_vec, G_DQNT_vec,
                                                                            sub_X,          sub_GU,     dbg_subK,   group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_ptr,        f_trace,        sub_X,          dbg_subK,   in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                    fmha_dumpMatrixInHex(G_step_ptr,        f_trace,        sub_GU,         dbg_subK,   in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X-SCALE: \n",                                    y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,          X_dqn_k,    FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++sub_K_idx[%04d]-G-SCALE: \n",                     y, x, expert,   sub_K_idx);
                    fmha_dumpMatrixInHex(G_DQNT_vec,        f_trace,        GU_dqn_n_exp,   GU_dqn_k,   FP32,       col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-STEP-OUT: \n",                             y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_step,        f_trace,        sub_X,          sub_GU,     FP32,       row_major);
                }

                matrix_accumlate(GEMM0_step, GEMM0_float, GEMM0_float,      sub_X,      sub_GU,    FP32,    FP32);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-ACC-OUT: \n",                              y, x, sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }
            } //end of sub_K_idx

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    sub_X,      sub_GU);
            } else {
                //GEMM0 SILU
                matrix_SILU(GEMM0_float,                                    sub_X,      sub_GU);
            }
            if(dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++GELU-OUT: \n",                                    y, x, expert);
                } else {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++SILU-OUT: \n",                                    y, x, expert);
                }
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            if (u1) {
                memset(GEMM1_float, 0, sizeof(cl_float)*sub_X*sub_GU);
                //for each dbg_subK, first prepare X and U data; then prepare scale data; then matrix multiple with scale
                //if dbg_subK==group_in_k, then should match kernel
                //if dbg_subK==dim, then should match std golden
                X_DQNT_ptr      = X_dqn_buf;
                cl_float *U_DQNT_ptr_k = U_DQNT_ptr;        //TG offset for U scale;
                for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                    matrix_crop_block(X_ptr, X_step_ptr,        sub_X,      dim, 0,         sub_K_idx, sub_X,   dbg_subK);
                    moe_shuffleback_block(U_ptr, U_step_ptr,    hidden_dim, dim, G_HD_idx,  sub_K_idx, sub_GU,  dbg_subK, tileSize.tileSizeMajor, tileSize.tileSizeMinor);

                    uint32 k_idx = 0;
                    for (uint32 group_k_idx = 0; group_k_idx < dbg_subK; group_k_idx+=group_in_k) {
                        //X_DQNT_vec fast-changing is X_dqn_k
                        for (uint32 x_idx = 0; x_idx < sub_X; x_idx++) {
                            uint32 tokenIdx = X_DQNT_addr[x_idx];
                            if (tokenIdx == batch) {
                                *(X_DQNT_vec+x_idx*X_dqn_k+k_idx) = 0;
                            } else {
                                *(X_DQNT_vec+x_idx*X_dqn_k+k_idx) = *(X_DQNT_ptr+tokenIdx);
                            }
                        }

                        //U_DQNT_vec fast-changing is GU_dqn_k
                        for (uint32 g_idx = 0; g_idx < GU_dqn_n_exp; g_idx++) {
                            uint32 g_idx_grped = g_idx/group_in_n;
                            *(U_DQNT_vec+g_idx*GU_dqn_k+k_idx) = *(U_DQNT_ptr_k+g_idx_grped);
                        }

                        U_DQNT_ptr_k += GU_eprt_dqn_stride;
                        X_DQNT_ptr   += X_dqn_stride;
                        k_idx++;
                    }

                    matrix_mul_block_scale_fast_in_K(X_step_ptr, U_step_ptr, GEMM1_step, X_DQNT_vec, U_DQNT_vec,
                                                                                sub_X,          sub_GU,     dbg_subK,   group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_ptr,        f_trace,        sub_X,          dbg_subK,   in_type,    row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                        fmha_dumpMatrixInHex(U_step_ptr,        f_trace,        sub_GU,         dbg_subK,   in_type,    col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X-SCALE: \n",                                    y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,          X_dqn_k,    FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]++++sub_K_idx[%04d]-U-SCALE: \n",                     y, x, expert,   sub_K_idx);
                        fmha_dumpMatrixInHex(U_DQNT_vec,        f_trace,        GU_dqn_n_exp,   GU_dqn_k,   FP32,       col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-STEP-OUT: \n",                             y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_step,        f_trace,        sub_X,          sub_GU,     FP32,       row_major);
                    }

                    matrix_accumlate(GEMM1_step, GEMM1_float, GEMM1_float,      sub_X,      sub_GU,    FP32,    FP32);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-ACC-OUT: \n",                              y, x, sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                    }
                }

                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          sub_X,      sub_GU);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0*GEMM1 OUT:\n",            y, x);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  sub_X,      sub_GU,    FP32,        row_major);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH_QUANT_VEC: \n",                                              y, x);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,       f_trace,        1,          sub_GU,     FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH-QUANT-OUT: \n",                                              y, x);
                        fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }
                }

                 //Quant GEMM0, and generate GEMM2 dequant vector; 
                act_quant(GEMM0_float,  GEMM2DQNT_vec,                          sub_X,      sub_GU,     group_in_k, quant_deno, GEMM0_float, rowMax_vec);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++QUANT-OUT: \n",                                                     y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,         FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-VEC-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      GEMM2_dqn_k,    FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-ROWMAX-VEC-OUT: \n",                                          y, x);
                    fmha_dumpMatrixInHex(rowMax_vec,        f_trace,        sub_X,      GEMM2_dqn_k*2,  FP32,       row_major);
                }
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            } else {
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++ConvertType[%04d]: \n",                               y, x, expert,   in_type);
                fmha_dumpMatrixInHex(GEMM0_T,               f_trace,        sub_X,      sub_GU,     in_type,    row_major);
            }

            //start GEMM2; input is sub_X*sub_GU row-major; sub_GU*dbg_subD col-major; out is sub_X*dbg_subD row-major
            D_DQNT_ptr = D_dqn_buf + expert*stride_expert_GUDQN;                    //reset position for different TGs
            D_DQNT_ptr = D_DQNT_ptr + TG_idx/group_in_k*D_dqn_strideK;              //TG offset D scale
            //prepare D scale; fast-changing is D_dqn_k
            for (uint32 sub_D_idx = 0; sub_D_idx < dim; sub_D_idx += dbg_subD) {
                memset(GEMM2_float, 0, sizeof(cl_float)*sub_X*dbg_subD);
                uint32 D_HD_idx = TG_idx;                                               //D's hidden_dim idx
                moe_shuffleback_block(D_ptr,  D_step_ptr, dim, hidden_dim, sub_D_idx, D_HD_idx, dbg_subD,   sub_GU, tileSize.tileSizeMajor, tileSize.tileSizeMinor);

                cl_float *D_DQNT_ptr_k = D_DQNT_ptr;
                uint32 k_idx = 0;
                for (uint32 group_k_idx = 0; group_k_idx < sub_GU; group_k_idx+=group_in_k) {
                    //G_DQNT_vec fast-changing is GU_dqn_k
                    for (uint32 g_idx = 0; g_idx < D_dqn_n_exp; g_idx++) {
                        uint32 g_idx_grped = g_idx/group_in_n;
                        *(D_DQNT_vec+g_idx*D_dqn_k+k_idx) = *(D_DQNT_ptr_k+g_idx_grped);
                    }
                    //offset in hidden_dim direction
                    D_DQNT_ptr_k += D_dqn_strideK;
                    k_idx++;
                }

                if (true) {    //also respect dbg_subK
                    cl_float *gemm2_tmp = new cl_float[sub_X*dbg_subD]();
                    for (uint32 i = 0; i < sub_GU/dbg_subK; i++) {
                        memset(gemm2_tmp, 0, sizeof(cl_float)*sub_X*dbg_subD);
                        TT *gemm0_tmp = new TT[sub_X*dbg_subD]();
                        TT *D_tmp     = new TT[dbg_subD*dbg_subK]();
                        cl_float *gemm0_scale = new cl_float [sub_X*dbg_subK/group_in_k]();
                        cl_float *D_scale     = new cl_float [dbg_subD*dbg_subK/group_in_k]();
                        matrix_crop_back(GEMM0_T      +i*dbg_subK,              sub_X,          sub_GU,                 sub_X,      dbg_subK,              gemm0_tmp);
                        matrix_crop_back(D_step_ptr   +i*dbg_subK,              dbg_subD,       sub_GU,                 dbg_subD,   dbg_subK,              D_tmp);
                        matrix_crop_back(GEMM2DQNT_vec+i*dbg_subK/group_in_k,   sub_X,          sub_GU/group_in_k,      sub_X,      dbg_subK/group_in_k,   gemm0_scale);
                        matrix_crop_back(D_DQNT_vec   +i*dbg_subK/group_in_k,   dbg_subD,       sub_GU/group_in_k,      dbg_subD,   dbg_subK/group_in_k,   D_scale);
                        
                        if (dbg_trace) {
                            matrix_mul_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,
                                                                                    sub_X,          dbg_subD,               dbg_subK,               in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-NONE-BLOCK-STEP-OUT: \n",                             y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,        sub_X,          dbg_subD,               FP32,       row_major);
                        }
                        matrix_mul_block_scale_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,   gemm0_scale, D_scale, 
                                                                                    sub_X,          dbg_subD,               dbg_subK,   group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                        if(dbg_trace) {
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm0_tmp,         f_trace,        sub_X,      dbg_subK,     in_type,    row_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx, i);
                            fmha_dumpMatrixInHex(D_tmp,             f_trace,        dbg_subD,   dbg_subK,     in_type,    col_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_D_idx[%04d]++++SUB_K_IDX[%04d]++++GEMM2-SCALE: \n",                                y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm0_scale,       f_trace,        sub_X,      dbg_subK/group_in_k,    FP32,       row_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++sub_D_idx[%04d]++++SUB_K_IDX[%04d]-D-SCALE: \n",                     y, x, expert,   sub_D_idx, i);
                            fmha_dumpMatrixInHex(D_scale,           f_trace,        dbg_subD,   dbg_subK/group_in_k,    FP32,       col_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-STEP-OUT: \n",                             y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,        sub_X,      dbg_subD,               FP32,       row_major);
                        }
                        
                        matrix_accumlate(GEMM2_float,  gemm2_tmp,  (cl_float*)GEMM2_float,      sub_X, dbg_subD,            FP32,       FP32);
                        if (dbg_trace) {
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-ACC-OUT: \n",                               y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                        }
                        delete []gemm0_tmp;
                        delete []D_tmp;
                        delete []gemm0_scale;
                        delete []D_scale;
                    }
                    delete []gemm2_tmp;
                }
                else {
                    matrix_mul_block_scale_fast_in_K(GEMM0_T, D_step_ptr, GEMM2_float, GEMM2DQNT_vec, D_DQNT_vec,
                                                                                sub_X,      dbg_subD,     sub_GU,   group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM0_T,           f_trace,        sub_X,      sub_GU,     in_type,    row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx);
                        fmha_dumpMatrixInHex(D_step_ptr,        f_trace,        dbg_subD,   sub_GU,     in_type,    col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_D_idx[%04d]++++GEMM2-SCALE: \n",                                y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      GEMM2_dqn_k,FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++sub_D_idx[%04d]-D-SCALE: \n",                     y, x, expert,   sub_D_idx);
                        fmha_dumpMatrixInHex(D_DQNT_vec,        f_trace,        D_dqn_n_exp,D_dqn_k,    FP32,       col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GEMM2-OUT: \n",                                  y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }
                }

                matrix_multi_weight_vec(GEMM2_float,                    sub_X,      dbg_subD,   sorted_weight_ptr);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-VALUE: \n",             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(sorted_weight_ptr, f_trace,        sub_X,      1,          FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-OUT: \n",           y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (o_elemSize == 2) {
                    //convert to target output
                    matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,           sub_X,      dbg_subD,   o_elemType, fp_format_des, f8_bias_des);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++++++D_EXPERT[%04d]++++ConvertType[%04d]: \n",    y, x, sub_D_idx, expert, in_type);
                        fmha_dumpMatrixInHex(GEMM2_half,        f_trace,        sub_X,      dbg_subD,   BF16,       row_major);
                    }
                }

                //accumulate tokens for this expert
                for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
                    uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
                    uint32 tokenOffset  = tokenIdx*dim;
                    if (tokenIdx != batch) {
                        // accumulate 1*dim one by one
                        if (o_elemSize == 2) {
                            matrix_accumulate_block(cpu_O_buf_half+tokenOffset,  GEMM2_half+sub_X_idx*dbg_subD,  (cl_float*)(cpu_O_buf_half+tokenOffset),   1, dim, 0, sub_D_idx, 1, dbg_subD, BF16, BF16);
                        } else {
                            matrix_accumulate_block(cpu_O_buf_ptr+tokenOffset,   GEMM2_float+sub_X_idx*dbg_subD, cpu_O_buf_ptr+tokenOffset,                 1, dim, 0, sub_D_idx, 1, dbg_subD, FP32, FP32);
                        }
                    }
                }

                //offset in dim direction
                D_DQNT_ptr += D_dqn_n;
            }//end of sub_D_idx
            x++;
            G_DQNT_ptr     += GU_dqn_n;                                                   //dequant offset
            U_DQNT_ptr     += GU_dqn_n;
            SMT_QNT_ptr    += sub_GU;
        }//end of TG_idx
    }//end of y

    delete []X_ptr;
    delete []X_step_ptr;
    delete []X_DQNT_addr;
    delete []X_DQNT_vec;
    delete []G_DQNT_vec;
    delete []U_DQNT_vec;
    delete []D_DQNT_vec;
    delete []GEMM2DQNT_vec;
    delete []rowMax_vec;
    delete []GEMM0_float;
    delete []GEMM0_step;
    delete []GEMM1_float;
    delete []GEMM1_step;
    delete []GEMM2_float;

    delete []G_step_ptr;
    delete []U_step_ptr;
    delete []D_step_ptr;
    fclose(f_trace);
    return;
}

template<typename TT>
static void moe_mxfpX_ref_dev(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    uint8 *X_dqn_buf, uint8 *GU_dqn_buf, uint8 *D_dqn_buf, cl_float *Smooth_qnt_buf,
    uint32 *sorted_token_ids, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids, uint32 &sub_X_cnt,
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU, uint32 dbg_subD, uint32 dbg_subK,
    uint32 group_in_k, uint32 group_in_n,
    DATA_TYPE in_type=BF16, uint32 dbg_trace=1, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = true,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   X_topk     = 1;
    TT        *X_ptr;                                    //offset of X; temporary storage; type is TT int8
    TT        *G_ptr;                                    //offset of G
    TT        *U_ptr;                                    //offset of U
    TT        *D_ptr;                                    //offset of D
    TT        *GEMM0_T;                                  //for GEMM2 operation
    TT        *X_step_ptr;

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;                              //float pointer to GEMM0 result
    //int32    *GEMM0_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;                              //float pointer to GEMM0 result
    //int32    *GEMM1_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM2_float;                              //float pointer to GEMM2 result
    //int32    *GEMM2_int32;                              //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;                               //half  pointer to GEMM2 result, for 16bits

    uint8    *X_DQNT_ptr;                               //offset of X_dqn_buf, increase by one stride, when advance group_in_k
    uint8    *G_DQNT_ptr;                               //offset of G_dqn_buf, size 1*sub_GU/group_in_n, increase by one stride, when advance group_in_k
    uint8    *U_DQNT_ptr;                               //offset of U_dqn_buf, size 1*sub_GU/group_in_n, increase by one stride, when advance group_in_k

    uint8    *X_DQNT_vec;                               //dequant vector for GEMM0, size sub_X*X_dqn_k
    uint8    *G_DQNT_vec;                               //dequant vector for GEMM0, size GU_dqn_n_exp*GU_dqn_k
    uint8    *U_DQNT_vec;                               //dequant vector for GEMM1, size GU_dqn_n_exp*GU_dqn_k
    uint8    *D_DQNT_vec;                               //dequant vector for GEMM2, size D_dqn_n_exp *D_dqn_k

    cl_float *SMT_QNT_ptr;                              //offset of Smooth_qnt_buf, size 1*sub_GU

    uint8    *GEMM2DQNT_vec;                            //dequant vector for GEMM2, size sub_X*1
    cl_float *rowMax_vec;                               //for debug purpose
    uint8    *D_DQNT_ptr;                               //offset of D_dqn_buf,      size 1*dim

    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    TileSize  tileSize;

    cl_float *sorted_weight_ptr;                        //offset of sorted_weight_buf
    uint32   *sorted_token_ids_ptr;                     //offset of sorted_token_ids

    do_smooth = false;
    printf("do_smooth set to false internally\n");
    if (tWithTopk) {
        printf("WARNING, tWithTopk should be false!!!!!\n");
        X_topk = topk;
    }

    uint32 GU_dqn_stride      = hidden_dim*dim/group_in_n/group_in_k;    //used to offset from G_DQNT_ptr to U_DQNT_ptr
    uint32 GU_eprt_dqn_stride = GU_dqn_stride + u1*GU_dqn_stride;        //used to offset during accumulation
    uint32 X_dqn_stride       = sub_X*dim/group_in_k;                    //used to offset during accumulation
    uint32 D_dqn_strideK      = dim/group_in_n;                          //used to offset during accumulation
    int stride_expert_GUDQN   = hidden_dim*dim/group_in_k/group_in_n;

    //uint32 X_dqn_m      = sub_X;
    uint32 X_dqn_k      = dbg_subK/group_in_k;
    uint32 GU_dqn_k     = dbg_subK/group_in_k;
    uint32 D_dqn_k      = sub_GU/group_in_k;
    uint32 GEMM2_dqn_k  = sub_GU/group_in_k;

    FILE *f_trace = fopen("moe_mxfpX_ref_dev.hex", "w+t");
    if (f_trace == NULL) {
        printf("Failed to open moe_mxfpX_ref_dev.hex!!!!!!\n");
        return;
    }

    int offset_scl = 1;
    if (in_type == FP4) {
        offset_scl = 2;
    }

    //alloc temporary compute results
    X_ptr         = new TT       [sub_X*dim/offset_scl];      //size sub_X*dim;
    X_step_ptr    = new TT       [sub_X*dbg_subK/offset_scl]; //size sub_X*dbg_subK;
    X_DQNT_vec    = new uint8   [sub_X*X_dqn_k];        //size sub_X*X_dqn_k;
    G_DQNT_vec    = new uint8   [sub_GU*GU_dqn_k];      //size sub_GU*GU_dqn_k;
    U_DQNT_vec    = new uint8   [sub_GU*GU_dqn_k];      //size sub_GU*GU_dqn_k;
    D_DQNT_vec    = new uint8   [dbg_subD*D_dqn_k];     //size dbg_subD*D_dqn_k
    GEMM2DQNT_vec = new uint8   [sub_X*GEMM2_dqn_k];    //size sub_X*GEMM2_dqn_k;
    rowMax_vec    = new cl_float[sub_X*2*GEMM2_dqn_k];  //size sub_X*2*GEMM2_dqn_k;
    GEMM0_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2_float   = new cl_float[sub_X*dbg_subD];       //size sub_X*dbg_subD;
    //GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    //GEMM1_int32   = (int32*)   GEMM1_float;
    //GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    getTileSize(in_type, layout, &tileSize);
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    if (hidden_dim % sub_GU != 0) {
        printf("Not divisible hidden_dim:%d,sub_GU:%d\n", hidden_dim, sub_GU);
        assert(0);
    }
    if (dim % dbg_subD != 0) {
        printf("Not divisible dim:%d,dbg_subD:%d\n", dim, dbg_subD);
        assert(0);
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d, sub_X_cnt:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,    sub_X,    sub_GU,    sub_X_cnt);
        fprintf(f_trace, "TGS_Y_AXIS:%d, TGS_X_AXIS:%d\n",          sub_X_cnt, hidden_dim/sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d, X_topk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk,    X_topk);
        fprintf(f_trace, "DBG_SUB_D:%d, DBG_SUB_K:%d\n", dbg_subD, dbg_subK);
    }

    TT       *G_step_ptr     = new TT[sub_GU   *dbg_subK/offset_scl];                                                     //subGU *dbg_subK, fast changing dbg_subK
    TT       *U_step_ptr     = new TT[sub_GU   *dbg_subK/offset_scl];                                                     //sub_GU*dbg_subK, fast changing dbg_subK
    TT       *D_step_ptr     = new TT[dbg_subD *sub_GU/offset_scl];                                                       //dbg_subD*sub_GU, fast changing sub_GU

    for(uint32 y = 0; y < sub_X_cnt; y++) {                                                                             //thread group Y axis
        uint32 expert           = sorted_expert_ids[y];                                                                 //Get expert ID according to y AXIS
        //offset pointers
        sorted_weight_ptr       = sorted_weight_buf + sub_X*y;                                                          //size sub_X*1
        sorted_token_ids_ptr    = sorted_token_ids  + sub_X*y;                                                          //size 1*sub_X
        G_ptr                   = GU_buf            + (expert*hidden_dim*dim + u1*expert*hidden_dim*dim)/offset_scl;    //size hidden_dim*dim; in shuffle format
        G_DQNT_ptr              = GU_dqn_buf        + expert*stride_expert_GUDQN + u1*expert*stride_expert_GUDQN;       //size 
        SMT_QNT_ptr             = Smooth_qnt_buf    + expert*hidden_dim;                                                //size 1*hidden_dim
        D_ptr                   = D_buf             + (expert*dim*hidden_dim)/offset_scl;                               //size dim*hidden_dim; in shuffle format
//        D_DQNT_ptr              = D_dqn_buf         + expert*dim;                                                     //size 1*dim
        U_ptr                   = G_ptr             + hidden_dim*dim/offset_scl;                                        //size hidden_dim*dim; in shuffle format
        U_DQNT_ptr              = G_DQNT_ptr        + GU_dqn_stride;                                                    //size 1*hidden_dim/group_in_n
        X_DQNT_ptr              = X_dqn_buf         + X_dqn_stride*y;

        //Prepare X data and dequant vector for this expert
        for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
            uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
            if (tokenIdx == batch) {
                memset(X_ptr+sub_X_idx*dim/offset_scl, 0,                               dim*sizeof(TT)/offset_scl);
            } else {
                memcpy(X_ptr+sub_X_idx*dim/offset_scl, X_buf+tokenIdx*dim/offset_scl,   dim*sizeof(TT)/offset_scl);
            }
        }

        uint32 x = 0;                                                                   //thread group X axis
        uint32 col_major = 1;
        uint32 row_major = 0;
        uint32 add_c = 1;
        
        for(uint32 TG_idx = 0;  TG_idx < hidden_dim; TG_idx += sub_GU) {                //Thread group offset
            memset(GEMM0_float, 0, sizeof(cl_float)*sub_X*sub_GU);
            uint32 G_HD_idx = TG_idx;                                                   //G's hidden_dim idx
            //for each dbg_subK, first prepare X and G data; then prepare scale data; then matrix multiple with scale
            //if dbg_subK==group_in_k, then should match kernel
            //if dbg_subK==dim, then should match std golden
            for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                matrix_crop_block(           X_ptr,      X_step_ptr,        sub_X,      dim/offset_scl, 0,         sub_K_idx/offset_scl, sub_X,   dbg_subK/offset_scl);
                scale_e8m0_shuffleback_block(X_DQNT_ptr, X_DQNT_vec,        sub_X,      dim/group_in_k, 0,         sub_K_idx/group_in_k, sub_X,   dbg_subK/group_in_k);
                moe_shuffleback_block(       G_ptr,      G_step_ptr,        hidden_dim, dim/offset_scl, G_HD_idx,  sub_K_idx/offset_scl, sub_GU,  dbg_subK/offset_scl, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                scale_e8m0_shuffleback_block(G_DQNT_ptr, G_DQNT_vec,        hidden_dim, dim/group_in_k, G_HD_idx,  sub_K_idx/group_in_k, sub_GU,  dbg_subK/group_in_k);

                matrix_mul_block_scale_fast_in_K(X_step_ptr, G_step_ptr, GEMM0_float, X_DQNT_vec, G_DQNT_vec,
                                                                            sub_X,      sub_GU,     dbg_subK,   group_in_k, in_type, auto_out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_step_ptr,        f_trace,        sub_X,          dbg_subK,   in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                    fmha_dumpMatrixInHex(G_step_ptr,        f_trace,        sub_GU,         dbg_subK,   in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X-SCALE: \n",                                    y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,          X_dqn_k,    INT8,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++sub_K_idx[%04d]-G-SCALE: \n",                     y, x, expert,   sub_K_idx);
                    fmha_dumpMatrixInHex(G_DQNT_vec,        f_trace,        sub_GU,         GU_dqn_k,   INT8,       col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM0-STEP-OUT: \n",                             y, x,           sub_K_idx);
                    fmha_dumpMatrixInHex(GEMM0_float,        f_trace,       sub_X,          sub_GU,     FP32,       row_major);
                }
            } //end of sub_K_idx
            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0-ACC-OUT: \n",                              y, x);
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,    FP32,        row_major);
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    sub_X,      sub_GU);
            } else {
                //GEMM0 SILU
                matrix_SILU(GEMM0_float,                                    sub_X,      sub_GU);
            }
            if(dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++GELU-OUT: \n",                                    y, x, expert);
                } else {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++SILU-OUT: \n",                                    y, x, expert);
                }
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            if (u1) {
                memset(GEMM1_float, 0, sizeof(cl_float)*sub_X*sub_GU);
                //for each dbg_subK, first prepare X and U data; then prepare scale data; then matrix multiple with scale
                //if dbg_subK==group_in_k, then should match kernel
                //if dbg_subK==dim, then should match std golden
                for (uint32 sub_K_idx = 0; sub_K_idx < dim; sub_K_idx += dbg_subK) {
                    matrix_crop_block(           X_ptr,      X_step_ptr,    sub_X,      dim/offset_scl, 0,         sub_K_idx/offset_scl, sub_X,   dbg_subK/offset_scl);
                    scale_e8m0_shuffleback_block(X_DQNT_ptr, X_DQNT_vec,    sub_X,      dim/group_in_k, 0,         sub_K_idx/group_in_k, sub_X,   dbg_subK/group_in_k);
                    moe_shuffleback_block(       U_ptr,      U_step_ptr,    hidden_dim, dim/offset_scl, G_HD_idx,  sub_K_idx/offset_scl, sub_GU,  dbg_subK/offset_scl, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                    scale_e8m0_shuffleback_block(U_DQNT_ptr, U_DQNT_vec,    hidden_dim, dim/group_in_k, G_HD_idx,  sub_K_idx/group_in_k, sub_GU,  dbg_subK/group_in_k);

                    matrix_mul_block_scale_fast_in_K(X_step_ptr, U_step_ptr, GEMM1_float, X_DQNT_vec, U_DQNT_vec,
                                                                            sub_X,      sub_GU,     dbg_subK,   group_in_k, in_type, auto_out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X_TOKEN-IN: \n",                                 y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_step_ptr,        f_trace,        sub_X,          dbg_subK,   in_type,    row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]++++sub_K_idx[%04d]-IN: \n",                          y, x, expert,   sub_K_idx);
                        fmha_dumpMatrixInHex(U_step_ptr,        f_trace,        sub_GU,         dbg_subK,   in_type,    col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++X-SCALE: \n",                                    y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,          X_dqn_k,    INT8,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]++++sub_K_idx[%04d]-U-SCALE: \n",                     y, x, expert,   sub_K_idx);
                        fmha_dumpMatrixInHex(U_DQNT_vec,        f_trace,        sub_GU,         GU_dqn_k,   INT8,       col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_K_idx[%04d]++++GEMM1-STEP-OUT: \n",                             y, x,           sub_K_idx);
                        fmha_dumpMatrixInHex(GEMM1_float,        f_trace,       sub_X,          sub_GU,     FP32,       row_major);
                    }
                }
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1-ACC-OUT: \n",                              y, x);
                    fmha_dumpMatrixInHex(GEMM1_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }

                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          sub_X,      sub_GU);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0*GEMM1 OUT:\n",            y, x);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  sub_X,      sub_GU,    FP32,        row_major);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH_QUANT_VEC: \n",                                              y, x);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,       f_trace,        1,          sub_GU,     FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH-QUANT-OUT: \n",                                              y, x);
                        fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }
                }

                 //Quant GEMM0, and generate GEMM2 dequant vector; 
                //act_quant(GEMM0_float,  GEMM2DQNT_vec,                          sub_X,      sub_GU,     group_in_k, quant_deno, GEMM0_float, rowMax_vec);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++QUANT-OUT: \n",                                                     y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,         FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-VEC-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      GEMM2_dqn_k,    FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-ROWMAX-VEC-OUT: \n",                                          y, x);
                    fmha_dumpMatrixInHex(rowMax_vec,        f_trace,        sub_X,      GEMM2_dqn_k*2,  FP32,       row_major);
                }
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,         in_type, fp_format_des, f8_bias_des);
            } else {
                mxFPX_quant(GEMM0_float,  GEMM2DQNT_vec,                    sub_X,      sub_GU,         group_in_k, quant_deno, in_type, GEMM0_float, rowMax_vec);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++QUANT-OUT: \n",                                                     y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,         FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-VEC-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      GEMM2_dqn_k,    INT8,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-ROWMAX-VEC-OUT: \n",                                          y, x);
                    fmha_dumpMatrixInHex(rowMax_vec,        f_trace,        sub_X,      GEMM2_dqn_k*2,  FP32,       row_major);
                }

                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,         in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0[%04d]++++ConvertType[%04d]: \n",                               y, x, expert,   in_type);
                fmha_dumpMatrixInHex(GEMM0_T,               f_trace,        sub_X,      sub_GU,     in_type,    row_major);
            }

            //start GEMM2; input is sub_X*sub_GU row-major; sub_GU*dbg_subD col-major; out is sub_X*dbg_subD row-major
            D_DQNT_ptr = D_dqn_buf + expert*stride_expert_GUDQN;                    //reset position for different TGs
            //prepare D scale; fast-changing is D_dqn_k
            for (uint32 sub_D_idx = 0; sub_D_idx < dim; sub_D_idx += dbg_subD) {
                memset(GEMM2_float, 0, sizeof(cl_float)*sub_X*dbg_subD);
                uint32 D_HD_idx = TG_idx;                                               //D's hidden_dim idx
                moe_shuffleback_block(       D_ptr,      D_step_ptr,    dim, hidden_dim/offset_scl, sub_D_idx,  D_HD_idx/offset_scl, dbg_subD,  sub_GU/offset_scl, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                scale_e8m0_shuffleback_block(D_DQNT_ptr, D_DQNT_vec,    dim, hidden_dim/group_in_k, sub_D_idx,  D_HD_idx/group_in_k, dbg_subD,  sub_GU/group_in_k);

                if (false) {
                    /*
                    //also respect dbg_subK
                    cl_float *gemm2_tmp = new cl_float[sub_X*dbg_subD]();
                    for (uint32 i = 0; i < sub_GU/dbg_subK; i++) {
                        memset(gemm2_tmp, 0, sizeof(cl_float)*sub_X*dbg_subD);
                        TT *gemm0_tmp = new TT[sub_X*dbg_subD]();
                        TT *D_tmp     = new TT[dbg_subD*dbg_subK]();
                        cl_float *gemm0_scale = new cl_float [sub_X*dbg_subK/group_in_k]();
                        cl_float *D_scale     = new cl_float [dbg_subD*dbg_subK/group_in_k]();
                        moe_matrix_crop_back(GEMM0_T      +i*dbg_subK,              sub_X,          sub_GU,                 sub_X,      dbg_subK,              gemm0_tmp);
                        moe_matrix_crop_back(D_step_ptr   +i*dbg_subK,              dbg_subD,       sub_GU,                 dbg_subD,   dbg_subK,              D_tmp);
                        moe_matrix_crop_back(GEMM2DQNT_vec+i*dbg_subK/group_in_k,   sub_X,          sub_GU/group_in_k,      sub_X,      dbg_subK/group_in_k,   gemm0_scale);
                        moe_matrix_crop_back(D_DQNT_vec   +i*dbg_subK/group_in_k,   dbg_subD,       sub_GU/group_in_k,      dbg_subD,   dbg_subK/group_in_k,   D_scale);
                        
                        if (dbg_trace) {
                            matrix_mul_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,
                                                                                    sub_X,          dbg_subD,               dbg_subK,               in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-NONE-BLOCK-STEP-OUT: \n",                             y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,        sub_X,          dbg_subD,               FP32,       row_major);
                        }
                        matrix_mul_block_scale_fast_in_K(gemm0_tmp, D_tmp, gemm2_tmp,   gemm0_scale, D_scale, 
                                                                                    sub_X,          dbg_subD,               dbg_subK,   group_in_k, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                        if(dbg_trace) {
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm0_tmp,         f_trace,        sub_X,      dbg_subK,     in_type,    row_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx, i);
                            fmha_dumpMatrixInHex(D_tmp,             f_trace,        dbg_subD,   dbg_subK,     in_type,    col_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_D_idx[%04d]++++SUB_K_IDX[%04d]++++GEMM2-SCALE: \n",                                y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm0_scale,       f_trace,        sub_X,      dbg_subK/group_in_k,    FP32,       row_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++sub_D_idx[%04d]++++SUB_K_IDX[%04d]-D-SCALE: \n",                     y, x, expert,   sub_D_idx, i);
                            fmha_dumpMatrixInHex(D_scale,           f_trace,        dbg_subD,   dbg_subK/group_in_k,    FP32,       col_major);
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-STEP-OUT: \n",                             y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(gemm2_tmp,         f_trace,        sub_X,      dbg_subD,               FP32,       row_major);
                        }
                        
                        matrix_accumlate(GEMM2_float,  gemm2_tmp,  (cl_float*)GEMM2_float,      sub_X, dbg_subD,            FP32,       FP32);
                        if (dbg_trace) {
                            fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++SUB_K_IDX[%04d]++++GEMM2-ACC-OUT: \n",                               y, x,           sub_D_idx, i);
                            fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                        }
                        delete []gemm0_tmp;
                        delete []D_tmp;
                        delete []gemm0_scale;
                        delete []D_scale;
                    }
                    delete []gemm2_tmp;*/
                }
                else {
                    matrix_mul_block_scale_fast_in_K(GEMM0_T, D_step_ptr, GEMM2_float, GEMM2DQNT_vec, D_DQNT_vec,
                                                                                sub_X,      dbg_subD,     sub_GU,   group_in_k, in_type, auto_out_type, add_c, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM0_T,           f_trace,        sub_X,      sub_GU,     in_type,    row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx);
                        fmha_dumpMatrixInHex(D_step_ptr,        f_trace,        dbg_subD,   sub_GU,     in_type,    col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++sub_D_idx[%04d]++++GEMM2-SCALE: \n",                                y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      GEMM2_dqn_k,INT8,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++sub_D_idx[%04d]-D-SCALE: \n",                     y, x, expert,   sub_D_idx);
                        fmha_dumpMatrixInHex(D_DQNT_vec,        f_trace,        dbg_subD,   D_dqn_k,    INT8,       col_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GEMM2-OUT: \n",                                  y, x,           sub_D_idx);
                        fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }
                }

                matrix_multi_weight_vec(GEMM2_float,                            sub_X,      dbg_subD,   sorted_weight_ptr);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-VALUE: \n",             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(sorted_weight_ptr, f_trace,            sub_X,      1,          FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-OUT: \n",           y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,            sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (o_elemSize == 2) {
                    //convert to target output
                    matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,               sub_X,      dbg_subD,   o_elemType, fp_format_des, f8_bias_des);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++++++D_EXPERT[%04d]++++ConvertType[%04d]: \n",    y, x, sub_D_idx, expert, in_type);
                        fmha_dumpMatrixInHex(GEMM2_half,        f_trace,        sub_X,      dbg_subD,   BF16,       row_major);
                    }
                }

                //accumulate tokens for this expert
                for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
                    uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
                    uint32 tokenOffset  = tokenIdx*dim;
                    if (tokenIdx != batch) {
                        // accumulate 1*dim one by one
                        if (o_elemSize == 2) {
                            matrix_accumulate_block(cpu_O_buf_half+tokenOffset,  GEMM2_half+sub_X_idx*dbg_subD,  (cl_float*)(cpu_O_buf_half+tokenOffset),   1, dim, 0, sub_D_idx, 1, dbg_subD, BF16, BF16);
                        } else {
                            matrix_accumulate_block(cpu_O_buf_ptr+tokenOffset,   GEMM2_float+sub_X_idx*dbg_subD, cpu_O_buf_ptr+tokenOffset,                 1, dim, 0, sub_D_idx, 1, dbg_subD, FP32, FP32);
                        }
                    }
                }

                //offset in dim direction
                //D_DQNT_ptr += dbg_subD;
            }//end of sub_D_idx*/
            x++;
            //G_DQNT_ptr     += sub_GU*dim/group_in_k;                                                   //dequant offset
            ///U_DQNT_ptr     += sub_GU*dim/group_in_k;
            SMT_QNT_ptr    += sub_GU;
        }//end of TG_idx
    }//end of y

    delete []X_ptr;
    delete []X_step_ptr;
    delete []X_DQNT_vec;
    delete []G_DQNT_vec;
    delete []U_DQNT_vec;
    delete []D_DQNT_vec;
    delete []GEMM2DQNT_vec;
    delete []rowMax_vec;
    delete []GEMM0_float;
    delete []GEMM1_float;
    delete []GEMM2_float;

    delete []G_step_ptr;
    delete []U_step_ptr;
    delete []D_step_ptr;
    fclose(f_trace);
    return;
}

//dbg_subD is for GEMM2
template<typename TT>
static void moe_ref_dev(TT *X_buf, TT *GU_buf, TT *D_buf, cl_float *W_buf, uint32 *TKI_buf, 
    cl_float *X_dqn_buf, cl_float *GU_dqn_buf, cl_float *D_dqn_buf, cl_float *Smooth_qnt_buf,
    uint32 *sorted_token_ids, cl_float *sorted_weight_buf, uint32 *sorted_expert_ids, uint32 &sub_X_cnt,
    cl_float *cpu_O_buf, uint32 atm_f32, //cast to correct type inside base on in_type, and atm_f32
    uint32 batch, uint32 hidden_dim, uint32 dim, uint32 eprt, uint32 topk, uint32 sub_X, uint32 sub_GU, uint32 dbg_subD,
    DATA_TYPE in_type=BF16, uint32 dbg_trace=1, DATA_LAYOUT layout=LAYOUT_NONE,
    bool useGelu = true, bool u1 = false, bool do_smooth = true, bool tWithTopk = false,
    int fp_format_src0 = FP8_FMT, bool f8_bias_src0 = false, int fp_format_src1 = FP8_FMT, bool f8_bias_src1 = false, int fp_format_des = FP8_FMT, bool f8_bias_des = false) {

    uint32   X_topk     = 1;
    TT        *X_ptr;                                    //offset of X; temporary storage
    TT        *G_ptr;                                    //offset of G
    TT        *U_ptr;                                    //offset of U
    TT        *D_ptr;                                    //offset of D
    TT        *GEMM0_T;                                  //for GEMM2 operation

    cl_float *cpu_O_buf_ptr;
    cl_half  *cpu_O_buf_half;
    cl_float *GEMM0_float;                              //float pointer to GEMM0 result
    int32    *GEMM0_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM1_float;                              //float pointer to GEMM0 result
    int32    *GEMM1_int32;                              //int32 pointer to GEMM0 result
    cl_float *GEMM2_float;                              //float pointer to GEMM2 result
    int32    *GEMM2_int32;                              //int32 pointer to GEMM2 result
    cl_half  *GEMM2_half;                               //half  pointer to GEMM2 result, for 16bits

    cl_float *X_DQNT_vec;                               //dequant vector for GEMM0, size sub_X*1
    cl_float *G_DQNT_ptr;                               //offset of G_dqn_buf,      size 1*sub_GU
    cl_float *U_DQNT_ptr;                               //offset of U_dqn_buf,      size 1*sub_GU
    cl_float *GEMM0DQNT_ptr;                            //dequant matrix for GEMM0, size sub_X*sub_GU
    cl_float *GEMM1DQNT_ptr;                            //dequant matrix for GEMM0, size sub_X*sub_GU

    cl_float *SMT_QNT_ptr;                              //offset of Smooth_qnt_buf, size 1*sub_GU

    cl_float *GEMM2DQNT_vec;                            //dequant vector for GEMM2, size sub_X*1
    cl_float *rowMax_vec;                               //for debug purpose
    cl_float *D_DQNT_ptr;                               //offset of D_dqn_buf,      size 1*dim
    cl_float *GEMM2DQNT_ptr;                            //dequant matrix for GEMM2, size sub_X*dim

    uint32    o_elemSize;
    DATA_TYPE o_elemType;
    DATA_TYPE auto_out_type;
    TileSize  tileSize;

    cl_float *sorted_weight_ptr;                        //offset of sorted_weight_buf
    uint32   *sorted_token_ids_ptr;                     //offset of sorted_token_ids
    float quant_deno = getQuantDeno(in_type, fp_format_src0, f8_bias_src0);

    if (tWithTopk) {
        X_topk = topk;
    }

    FILE *f_trace = fopen("moe_data_trace.hex", "w+t");
    if (f_trace == NULL) {
        printf("Failed to open moe_data_trace.hex!!!!!!\n");
        return;
    }

    //alloc temporary compute results
    X_ptr         = new TT[sub_X*dim];                   //size sub_X*dim;
    X_DQNT_vec    = new cl_float[sub_X*1];              //size sub_X*1;
    GEMM0DQNT_ptr = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1DQNT_ptr = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2DQNT_vec = new cl_float[sub_X*1];              //size sub_X*1;
    rowMax_vec    = new cl_float[sub_X*2];              //size sub_X*2;
    GEMM2DQNT_ptr = new cl_float[sub_X*dim];            //size sub_X*dim;
    GEMM0_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM1_float   = new cl_float[sub_X*sub_GU];         //size sub_X*sub_GU;
    GEMM2_float   = new cl_float[sub_X*dbg_subD];       //size sub_X*dbg_subD;
    GEMM0_int32   = (int32*)   GEMM0_float;
    GEMM0_T       = (TT*)       GEMM0_float;
    GEMM1_int32   = (int32*)   GEMM1_float;
    GEMM2_int32   = (int32*)   GEMM2_float;
    GEMM2_half    = (cl_half*) GEMM2_float;
    cpu_O_buf_half= (cl_half*) cpu_O_buf;
    cpu_O_buf_ptr =            cpu_O_buf;
    auto_out_type = TYPE_NUM;                           //auto out_type
    o_elemSize    = getMOEOutElemSize(in_type, atm_f32);
    o_elemType    = getMOEOutType(in_type, atm_f32);
    getTileSize(in_type, layout, &tileSize);

    if (hidden_dim % sub_GU != 0) {
        printf("Not divisible hidden_dim:%d,sub_GU:%d\n", hidden_dim, sub_GU);
        assert(0);
    }
    if (dim % dbg_subD != 0) {
        printf("Not divisible dim:%d,dbg_subD:%d\n", dim, dbg_subD);
        assert(0);
    }

    if (dbg_trace) {
        fprintf(f_trace, "in_type:%d, batch:%d, dim:%d, hidden_dim:%d, eprt:%d, topk:%d, sub_X:%d, sub_GU:%d, sub_X_cnt:%d \n",
                          in_type,    batch,    dim,    hidden_dim,    eprt,    topk,      sub_X,    sub_GU,    sub_X_cnt);
        fprintf(f_trace, "TGS_Y_AXIS:%d, TGS_X_AXIS:%d\n",              sub_X_cnt, hidden_dim/sub_GU);
        fprintf(f_trace, "use_gelu:%d, use_up:%d, use_smooth:%d, tWithTopk:%d, X_topk:%d\n",
                          useGelu,     u1,        do_smooth,     tWithTopk,    X_topk);
        fprintf(f_trace, "DBG_SUB_D:%d fp8_format:%d fp8_bias:%d\n", dbg_subD, fp_format_src0, f8_bias_src0);
    }

    TT     *G_step_ptr     = new TT[sub_GU*dim];                                                          //sub_GU*dim, fast changing dim
    TT     *U_step_ptr     = new TT[sub_GU*dim];                                                          //sub_GU*dim, fast changing dim
    TT     *D_step_ptr     = new TT[dbg_subD *sub_GU];                                                    //dbg_subD*sub_GU, fast changing sub_GU

    for(uint32 y = 0; y < sub_X_cnt; y++) {                                                             //thread group Y axis
        uint32 expert           = sorted_expert_ids[y];                                                 //Get expert ID according to y AXIS
        //offset pointers
        sorted_weight_ptr       = sorted_weight_buf + sub_X*y;                                          //size sub_X*1
        sorted_token_ids_ptr    = sorted_token_ids  + sub_X*y;                                          //size 1*sub_X
        G_ptr                   = GU_buf            + expert*hidden_dim*dim + u1*expert*hidden_dim*dim; //size hidden_dim*dim; in shuffle format
        G_DQNT_ptr              = GU_dqn_buf        + expert*hidden_dim     + u1*expert*hidden_dim;     //size 1*hidden_dim
        SMT_QNT_ptr             = Smooth_qnt_buf    + expert*hidden_dim;                                //size 1*hidden_dim
        D_ptr                   = D_buf             + expert*dim*hidden_dim;                            //size dim*hidden_dim; in shuffle format
        D_DQNT_ptr              = D_dqn_buf         + expert*dim;                                       //size 1*dim
        U_ptr                   = G_ptr             + hidden_dim*dim;                                   //size hidden_dim*dim; in shuffle format
        U_DQNT_ptr              = G_DQNT_ptr        + hidden_dim;                                       //size 1*hidden_dim

        //Prepare X data and dequant vector for this expert
        for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
            uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
            uint32 t_topk       = getTokenTopk  (sorted_token_ids_ptr[sub_X_idx], tWithTopk);
            if (tokenIdx == batch) {
                X_DQNT_vec[sub_X_idx] = 0;
                memset(X_ptr+sub_X_idx*dim, 0,                                   dim*sizeof(TT));
            } else {
                X_DQNT_vec[sub_X_idx] = X_dqn_buf[tokenIdx*1  +t_topk*batch*1];
                memcpy(X_ptr+sub_X_idx*dim, X_buf+tokenIdx*dim+t_topk*batch*dim, dim*sizeof(TT));
            }
        }

        uint32 x = 0;                                                                   //thread group X axis
        uint32 col_major = 1;
        uint32 row_major = 0;
        for(uint32 TG_idx = 0;  TG_idx < hidden_dim; TG_idx += sub_GU) {                //Thread group offset
            memset(GEMM0_float, 0, sizeof(cl_float)*sub_X*sub_GU);
            uint32 G_HD_idx = TG_idx;                                                   //G's hidden_dim idx
            moe_shuffleback_block(G_ptr, G_step_ptr, hidden_dim, dim, G_HD_idx, 0,      sub_GU,     dim, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
            matrix_mul_fast_in_K(X_ptr,  G_step_ptr, GEMM0_float,           sub_X,      sub_GU,     dim, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++X_TOKEN: \n",                                                           y, x);
                fmha_dumpMatrixInHex(X_ptr,                 f_trace,        sub_X,      dim,        in_type,    row_major);
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]: \n",                                                    y, x, expert);
                fmha_dumpMatrixInHex(G_step_ptr,            f_trace,        sub_GU,     dim,        in_type,    col_major);
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0 OUT: \n",                                                         y, x);
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            //GEMM0 done;
            if (in_type == INT8 || in_type == FP8) {
                fmha_matrix_mul(X_DQNT_vec, G_DQNT_ptr, GEMM0DQNT_ptr,      sub_X,      sub_GU, 1,  FP32, FP32, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++X_DEQUANT_VEC: \n",                                                 y, x);
                    fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,          FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_DEQUANT_VEC[%04d]: \n",                                           y, x, expert);
                    fmha_dumpMatrixInHex(G_DQNT_ptr,        f_trace,        1,          sub_GU,     FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0-DEQUANT-MATRIX: \n",                                          y, x);
                    fmha_dumpMatrixInHex(GEMM0DQNT_ptr,     f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                }

                if (in_type == INT8) {
                    //Convert to F32 before dequant
                    matrix_v_cvt_f32_i32(GEMM0_int32,                       sub_X,      sub_GU);
                }
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0-CONVERT-F32-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }

                //GEMM0 dequant
                dequant(GEMM0_float, GEMM0DQNT_ptr,                         sub_X,      sub_GU);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0-DEQUANT-OUT: \n",                                             y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                }
            }

            if (useGelu) {
                //GEMM0 GELU
                matrix_GELU(GEMM0_float,                                    sub_X,      sub_GU);
            } else {
                //GEMM0 SILU
                matrix_SILU(GEMM0_float,                                    sub_X,      sub_GU);
            }
            if(dbg_trace) {
                if (useGelu) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++GELU-OUT: \n",                                    y, x, expert);
                } else {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++SILU-OUT: \n",                                    y, x, expert);
                }
                fmha_dumpMatrixInHex(GEMM0_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
            }

            if (u1) {
                //GEMM1
                moe_shuffleback_block(U_ptr, U_step_ptr, hidden_dim, dim, G_HD_idx, 0,      sub_GU,     dim, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                matrix_mul_fast_in_K(X_ptr,  U_step_ptr, GEMM1_float,           sub_X,      sub_GU,     dim, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++X_TOKEN: \n",                                                           y, x);
                    fmha_dumpMatrixInHex(X_ptr,                 f_trace,        sub_X,      dim,        in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_EXPERT[%04d]: \n",                                                    y, x, expert);
                    fmha_dumpMatrixInHex(U_step_ptr,            f_trace,        sub_GU,     dim,        in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1 OUT: \n",                                                         y, x);
                    fmha_dumpMatrixInHex(GEMM1_float,           f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                }

                //GEMM1 done;
                if (in_type == INT8 || in_type == FP8) {
                    fmha_matrix_mul(X_DQNT_vec, U_DQNT_ptr, GEMM1DQNT_ptr,      sub_X,      sub_GU, 1,  FP32, FP32, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++X_DEQUANT_VEC: \n",                                                 y, x);
                        fmha_dumpMatrixInHex(X_DQNT_vec,        f_trace,        sub_X,      1,          FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++U_DEQUANT_VEC[%04d]: \n",                                           y, x, expert);
                        fmha_dumpMatrixInHex(U_DQNT_ptr,        f_trace,        1,          sub_GU,     FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1-DEQUANT-MATRIX: \n",                                          y, x);
                        fmha_dumpMatrixInHex(GEMM1DQNT_ptr,     f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }

                    if (in_type == INT8) {
                        //Convert to F32 before dequant
                        matrix_v_cvt_f32_i32(GEMM1_int32,                           sub_X,      sub_GU);
                    }
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1-CONVERT-F32-OUT: \n",                                         y, x);
                        fmha_dumpMatrixInHex(GEMM1_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                    }

                    //GEMM1 dequant
                    dequant(GEMM1_float, GEMM1DQNT_ptr,                         sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM1-DEQUANT-OUT: \n",                                             y, x);
                        fmha_dumpMatrixInHex(GEMM1_float,       f_trace,        sub_X,      sub_GU,    FP32,        row_major);
                    }
                }
                //GEMM0*GEMM1
                matrix_multiple(GEMM0_float, GEMM1_float, GEMM0_float,          sub_X,      sub_GU);
                if (dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM0*GEMM1 OUT:\n",            y, x);
                    fmha_dumpMatrixInHex(GEMM0_float, f_trace,                  sub_X,      sub_GU,    FP32,        row_major);
                }
            }

            if (in_type == INT8 || in_type == FP8) {
                if (do_smooth) {
                    //GEMM0 Smooth quant
                    smooth_quant(GEMM0_float, SMT_QNT_ptr,                      sub_X,      sub_GU);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH_QUANT_VEC: \n",                                              y, x);
                        fmha_dumpMatrixInHex(SMT_QNT_ptr,       f_trace,        1,          sub_GU,     FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++SMOOTH-QUANT-OUT: \n",                                              y, x);
                        fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    }
                }

                //Quant GEMM0, and generate GEMM2 dequant vector; 
                quant(GEMM0_float, GEMM2DQNT_vec,                           sub_X,      sub_GU,     quant_deno, GEMM0_float, rowMax_vec);
                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++QUANT-OUT: \n",                                                     y, x);
                    fmha_dumpMatrixInHex(GEMM0_float,       f_trace,        sub_X,      sub_GU,     FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-VEC-OUT: \n",                                         y, x);
                    fmha_dumpMatrixInHex(GEMM2DQNT_vec,     f_trace,        sub_X,      1,          FP32,       row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-ROWMAX-VEC-OUT: \n",                                          y, x);
                    fmha_dumpMatrixInHex(rowMax_vec,        f_trace,        sub_X,      2,          FP32,       row_major);
                }
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            } else {
                matrix_v_cvt_to_type(GEMM0_float, GEMM0_T,                  sub_X,      sub_GU,     in_type, fp_format_des, f8_bias_des);
            }

            if(dbg_trace) {
                fprintf(f_trace, "++++Y[%04d]X[%04d]++++G_EXPERT[%04d]++++ConvertType[%04d]: \n",                               y, x, expert,   in_type);
                fmha_dumpMatrixInHex(GEMM0_T,               f_trace,        sub_X,      sub_GU,     in_type,    row_major);
            }

            //start GEMM2; input is sub_X*sub_GU row-major; sub_GU*dbg_subD col-major; out is sub_X*dbg_subD row-major
            D_DQNT_ptr = D_dqn_buf + expert*dim;                                        //size 1*dim; reset position for different TGs
            for (uint32 sub_D_idx = 0; sub_D_idx < dim; sub_D_idx += dbg_subD) {
                memset(GEMM2_float, 0, sizeof(cl_float)*sub_X*dbg_subD);
                uint32 D_HD_idx = TG_idx;                                               //D's hidden_dim idx
                moe_shuffleback_block(D_ptr,  D_step_ptr, dim, hidden_dim, sub_D_idx, D_HD_idx, dbg_subD,   sub_GU, tileSize.tileSizeMajor, tileSize.tileSizeMinor);
                matrix_mul_fast_in_K(GEMM0_T, D_step_ptr, GEMM2_float,      sub_X,      dbg_subD,           sub_GU, in_type, auto_out_type, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GM0_TOKEN: \n",                                  y, x,           sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM0_T,           f_trace,        sub_X,      sub_GU,     in_type,    row_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]: \n",                             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(D_step_ptr,        f_trace,        dbg_subD,   sub_GU,     in_type,    col_major);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++GEMM2-OUT: \n",                                  y, x,           sub_D_idx);
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (in_type == INT8 || in_type == FP8) {
                    if (in_type == INT8) {
                        //Convert to F32 before dequant
                        matrix_v_cvt_f32_i32(GEMM2_int32,                   sub_X,      dbg_subD);
                    }
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-CONVERT-F32-OUT: \n",                                     y, x);
                        fmha_dumpMatrixInHex(GEMM2_float,   f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }

                    //Generate GEMM2 dequant matrix GEMM2DQNT_ptr=GEMM2DQNT_vec X D_DQNT_ptr sub_X*dbg_subD=sub_X*1 X 1*dbg_subD
                    fmha_matrix_mul(GEMM2DQNT_vec, D_DQNT_ptr,GEMM2DQNT_ptr,sub_X,      dbg_subD,   1,      FP32, FP32, 0, fp_format_src0, f8_bias_src0, fp_format_src1, f8_bias_src1, fp_format_des, f8_bias_des, layout);
                    if(dbg_trace) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_DEQUANT_VEC[%04d]: \n",                                       y, x,           expert);
                        fmha_dumpMatrixInHex(D_DQNT_ptr,    f_trace,        1,          dbg_subD,   FP32,       row_major);
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++GEMM2-DEQUANT-MATRIX: \n",                                      y, x);
                        fmha_dumpMatrixInHex(GEMM2DQNT_ptr, f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                    }

                    //GEMM2 dequant and multiple weight
                    dequant_with_weight_vec(GEMM2_float, GEMM2DQNT_ptr,     sub_X,      dbg_subD,   sorted_weight_ptr);
                } else {
                    //just multiple weight
                    matrix_multi_weight_vec(GEMM2_float,                    sub_X,      dbg_subD,   sorted_weight_ptr);
                }

                if(dbg_trace) {
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-VALUE: \n",             y, x, expert,   sub_D_idx);
                    fmha_dumpMatrixInHex(sorted_weight_ptr, f_trace,        sub_X,      1,          FP32,       row_major);
                    if (in_type == INT8 || in_type == FP8) {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++DEQUANT-WEIGHT-OUT: \n",   y, x, expert,   sub_D_idx);
                    } else {
                        fprintf(f_trace, "++++Y[%04d]X[%04d]++++D_EXPERT[%04d]++++SUB_D_IDX[%04d]++++WEIGHT-OUT: \n",           y, x, expert,   sub_D_idx);
                    }
                    fmha_dumpMatrixInHex(GEMM2_float,       f_trace,        sub_X,      dbg_subD,   FP32,       row_major);
                }

                if (o_elemSize == 2) {
                    //convert to target output
                    matrix_v_cvt_to_type(GEMM2_float, GEMM2_half,           sub_X,      dbg_subD,   o_elemType, fp_format_des, f8_bias_des);
                    fprintf(f_trace, "++++Y[%04d]X[%04d]++++SUB_D_IDX[%04d]++++++++D_EXPERT[%04d]++++ConvertType[%04d]: \n",    y, x, sub_D_idx, expert, in_type);
                    fmha_dumpMatrixInHex(GEMM2_half,        f_trace,        sub_X,      dbg_subD,   BF16,       row_major);
                }

                //accumulate tokens for this expert
                for (uint32 sub_X_idx = 0; sub_X_idx < sub_X; sub_X_idx++) {
                    uint32 tokenIdx     = getTokenExpert(sorted_token_ids_ptr[sub_X_idx], tWithTopk); //real token idx may reside in low 24bits
                    uint32 tokenOffset  = tokenIdx*dim;
                    if (tokenIdx != batch) {
                        // accumulate 1*dim one by one
                        if (o_elemSize == 2) {
                            matrix_accumulate_block(cpu_O_buf_half+tokenOffset,  GEMM2_half+sub_X_idx*dbg_subD,  (cl_float*)(cpu_O_buf_half+tokenOffset),   1, dim, 0, sub_D_idx, 1, dbg_subD, BF16, BF16);
                        } else {
                            matrix_accumulate_block(cpu_O_buf_ptr+tokenOffset,   GEMM2_float+sub_X_idx*dbg_subD, cpu_O_buf_ptr+tokenOffset,                 1, dim, 0, sub_D_idx, 1, dbg_subD, FP32, FP32);
                        }
                    }
                }
                D_DQNT_ptr += dbg_subD;                                                 //dequant offset
            }//end of sub_D_idx
            x++;
            G_DQNT_ptr     += sub_GU;                                                   //dequant offset
            U_DQNT_ptr     += sub_GU;
            SMT_QNT_ptr    += sub_GU;
        }//end of TG_idx
    }//end of y

    delete []X_ptr;
    delete []X_DQNT_vec;
    delete []GEMM0DQNT_ptr;
    delete []GEMM1DQNT_ptr;
    delete []GEMM2DQNT_vec;
    delete []rowMax_vec;
    delete []GEMM2DQNT_ptr;
    delete []GEMM0_float;
    delete []GEMM1_float;
    delete []GEMM2_float;

    delete []G_step_ptr;
    delete []U_step_ptr;
    delete []D_step_ptr;
    fclose(f_trace);
    return;
}
#endif