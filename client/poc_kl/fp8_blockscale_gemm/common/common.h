#ifndef COMMON_H
#define COMMON_H
/*
Defines various common stuff, does not depend on anything
*/

using cl_float          = float;
using cl_char           = unsigned char;
using float16           = unsigned short;
using cl_half           = float16;
using cl_int            = int;

using int8              = signed char;
using int32             = int;
using int64             = long;

using uint8             = unsigned char;
using uint16            = unsigned short;
using uint32            = unsigned int;
using uint64            = unsigned long;

//added for fp4 and fp6
typedef struct {
    uint32 val : 4;
} uint4_t;

typedef struct {
    uint32 val : 6;
} uint6_t;

enum //F6 formats
{
    BF6_FMT = 0,
    FP6_FMT
};

enum //F8 formats
{
    BF8_FMT,
    FP8_FMT
};

const float f_log2E     = log2f(expf(1));
const float  QNT_DENO   = 127.0f;
const float  QNT_DENO_FP8_E4M3_BIAS8  = 240.0f;
const float  QNT_DENO_FP8_E4M3_BIAS7  = 448.0f;
const float  QNT_DENO_FP8_E5M2_BIAS16 = 57344.0f;
const float  QNT_DENO_MXFP4_LARGEST_POWER_OF_TWO = 4.0f;

enum DATA_TYPE
{
    FP16,
    BF16,
    FP8,
    FP32,
    INT32,
    INT8,
    INT4,
    FP4,
    FP6,
    TYPE_NUM
};

enum DATA_LAYOUT 
{
    LAYOUT_NONE=0,
    LAYOUT_32X32=1,
    LAYOUT_16X16=2,
    LAYOUT_32x8= 3
};

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

#define FP4_BS_SIZE 32
//mini granularity of MXFP4 input is 32x256
#define MX_FP_M     32
#define MX_FP_K     256
#define MX_FP_BS    32

const char* typeString(unsigned int type) {
    switch (type) {
        case FP16:
            return "FP16";
        case BF16:
            return "BF16";
        case FP8:
            return "FP8";
        case FP32:
            return "FP32";
        case INT32:
            return "INT32";
        case INT8:
            return "INT8";
        case INT4:
            return "INT4";
        case FP4:
            return "FP4";
        case FP6:
            return "FP6";
    }
    return "UNKNOWN";
}

static uint4_t getlow(cl_char twoFp4) {
    uint ret = twoFp4 & 0xf;
    uint4_t fp4 = {0};
    fp4.val = ret;
    return fp4;
}

static uint4_t gethigh(cl_char twoFp4) {
    uint ret = (twoFp4 >> 4) & 0xf;
    uint4_t fp4 = {0};
    fp4.val = ret;
    return fp4;
}

static uint4_t getFp4(cl_char twoFp4, int high) {
    if (high == 1) {
        return gethigh(twoFp4);
    } else {
        return getlow(twoFp4);
    }
}

static void setlow(cl_char* twoFp4, uint4_t fp4) {
    uint value = fp4.val;
    *twoFp4 = *twoFp4 & 0xf0;
    value = value & 0xf;
   *twoFp4 = *twoFp4 | value;
}

static void sethigh(cl_char* twoFp4, uint4_t fp4) {
    uint value = fp4.val;
    *twoFp4 = *twoFp4 & 0x0f;
    value = value & 0xf;
    value = value << 4;
    *twoFp4 = *twoFp4 | value;
}

static void setFp4(cl_char* twoFp4, uint4_t value, int high) {
    if (high == 1) {
        sethigh(twoFp4, value);
    } else {
        setlow(twoFp4, value);
    }
}

// get uint4 at row i, column j from matrix of m rows, n columns
static uint4_t getFp4(cl_char* buffer, int m, int n, int i, int j, int rowmajor, bool debug=false) {
    int index = 0;
    if (rowmajor == 1) {
        index = i*n + j;
    } else {
        index = j*m + i;
    }
    int high = index % 2;

    cl_char twoFp4 = buffer[index/2];
    uint4_t ret = getFp4(twoFp4, high);
    if (debug) {
        printf("m:%d, n:%d, i:%d, j:%d, index:%d, rowmajor:%d, ret:%01x\n",m,n,i,j,index,rowmajor,ret.val);
    }
    return ret;
}

static void setFp4(cl_char* buffer, uint4_t value, int m, int n, int i, int j, int rowmajor) {
    int index = 0;
    if (rowmajor == 1) {
        index = i*n + j;
    } else {
        index = j*m + i;
    }
    int high = index % 2;

    setFp4(buffer+index/2, value, high);
}

static uint4_t getBit4(cl_char twoBit4, int high) {
    return getFp4(twoBit4, high);
}

static void setBit4(cl_char* twoBit4, uint4_t value, int high) {
    return setFp4(twoBit4, value, high);
}

// get uint4 at row i, column j from matrix of m rows, n columns
static uint4_t getBit4(cl_char* buffer, int m, int n, int i, int j, int rowmajor, bool debug=false) {
    return getFp4(buffer, m, n, i, j, rowmajor, debug);
}

static void setBit4(cl_char* buffer, uint4_t value, int m, int n, int i, int j, int rowmajor) {
    return setFp4(buffer, value, m, n, i, j, rowmajor);
}

//combine discrete 4 points together
//M should be multiple of 32
//K should be multiple of 256/32
//major in K
//there are two types of shuffle, one is for 16x128, the other is for 32x64
//for 16x128 type, 32x256/32 is separated into below 4 portions; each portion is 16x4
// 0 2
// 1 3
//every portion has 16x4 points, every bunch of disrete 4 points come from 4 portions
//for 32x64 type, 32x256/32 is separated into below 4 portions; each portion is 32x2
// 0 1 2 3
template<typename TT>
static void scale_shuffle_one(TT *buffer, uint32 M, uint32 K, uint32 tileSizeM=16, uint32 tileSizeK=4) {
    uint32 miniM = 32;
    uint32 miniK = 256/FP4_BS_SIZE;
    uint32 tilesInM = M/miniM;
    uint32 tilesInK = K/miniK;
    uint32 tileStride = miniM*miniK;

    if (M % miniM != 0 || K % miniK != 0) {
        printf("Not divisible M:%d,miniM:%d K:%d,miniK:%d\n", M, miniM, K, miniK);
        assert(0);
    }
    uint32 points16x128[8] = {0,0,  16,0,                   0,128/FP4_BS_SIZE, 16,128/FP4_BS_SIZE};
    uint32 points32x64 [8] = {0,0,  0, 64/FP4_BS_SIZE,      0,128/FP4_BS_SIZE, 0, 192/FP4_BS_SIZE};
    uint32 *points;
    if (tileSizeM == 16) {
        assert(tileSizeK==4);
        points = points16x128;
    } else {
        assert(tileSizeM==32);
        assert(tileSizeK==2);
        points = points32x64;
    }

    TT *shuffle = new TT[M*K];
    TT *tilePtr;
    TT *origPtr;
    uint32 originM;
    uint32 originK;
    for (uint32 tileM = 0; tileM < tilesInM; tileM++) {
        for (uint32 tileK = 0; tileK < tilesInK; tileK++) {     //fast changing in tileK direction
            //first find tile's position
            tilePtr = shuffle+(tileM*tilesInK+tileK)*tileStride;
            originM = tileM * miniM;
            originK = tileK * miniK;
            origPtr = buffer + originM*K+originK;
            for (uint32 k = 0; k <tileSizeK; k++) {
                for (uint32 m = 0; m < tileSizeM; m++) {
                    //iterate tileSizeK*tileSizeM total 64 points, pick from 4 portions
                    for (uint32 dot = 0; dot < 4; dot++) {
                        uint32 dotM = *(points+dot*2);
                        uint32 dotK = *(points+dot*2+1);
                        *tilePtr++  = *(origPtr + (m+dotM)*K + (k+dotK));
                    }
                }
            }
        }
    }

    memcpy(buffer, shuffle, sizeof(TT)*M*K);
    delete []shuffle;
    return;
}

template<typename TT>
static void scale_shuffleback_one(TT *buffer, uint32 M, uint32 K, TT *out=NULL, uint32 tileSizeM=16, uint32 tileSizeK=4) {
    uint32 miniM = 32;
    uint32 miniK = 256/FP4_BS_SIZE;
    uint32 tilesInM = M/miniM;
    uint32 tilesInK = K/miniK;
    uint32 tileStride = miniM*miniK;

    if (M % miniM != 0 || K % miniK != 0) {
        printf("Not divisible M:%d,miniM:%d K:%d,miniK:%d\n", M, miniM, K, miniK);
        assert(0);
    }
    uint32 points16x128[8] = {0,0,  16,0,                   0,128/FP4_BS_SIZE, 16,128/FP4_BS_SIZE};
    uint32 points32x64 [8] = {0,0,  0, 64/FP4_BS_SIZE,      0,128/FP4_BS_SIZE, 0, 192/FP4_BS_SIZE};
    uint32 *points;
    if (tileSizeM == 16) {
        assert(tileSizeK==4);
        points = points16x128;
    } else {
        assert(tileSizeM==32);
        assert(tileSizeK==2);
        points = points32x64;
    }

    TT *shuffle = new TT[M*K];
    TT *tilePtr;
    TT *origPtr;
    uint32 originM;
    uint32 originK;
    for (uint32 tileM = 0; tileM < tilesInM; tileM++) {
        for (uint32 tileK = 0; tileK < tilesInK; tileK++) {     //fast changing in tileK direction
            //first find tile's position
            tilePtr = buffer + (tileM*tilesInK+tileK)*tileStride;
            originM = tileM * miniM;
            originK = tileK * miniK;
            origPtr = shuffle + originM*K+originK;
            for (uint32 k = 0; k <tileSizeK; k++) {
                for (uint32 m = 0; m < tileSizeM; m++) {
                    //iterate tileSizeK*tileSizeM total 64 points, pick from 4 portions
                    for (uint32 dot = 0; dot < 4; dot++) {
                        uint32 dotM = *(points+dot*2);
                        uint32 dotK = *(points+dot*2+1);
                        *(origPtr + (m+dotM)*K + (k+dotK)) = *tilePtr++;
                    }
                }
            }
        }
    }

    if (out == NULL) {
        out = buffer;
    }
    memcpy(out, shuffle, sizeof(TT)*M*K);
    delete []shuffle;
    return;
}

template<typename TT>
static void init_fromfile(TT *buffer, std::string fileName, int size) {
    FILE *file = fopen(fileName.c_str(), "rb");
    if (file == NULL) {
        printf("Failed to open file\n");
        return;
    }
    for(int b = 0; b < size; b++) {
        TT *offset = buffer + b;
        fread(offset, sizeof(TT), 1, file);
    }//batch
    fclose(file);
}

uint32 FloatMapToInt(float in)
{
	return *((uint32 *)&in);
}

float IntMapToFloat(uint32 in)
{
	return *((float *)&in);
}

static bool isNanF32(uint data) {
    if ((((data & 0x7F800000) >> 23) == 0xFF) && ((data & 0x007FFFFF) != 0))
        return true;
    else
        return false;
}

double gaussrand()
{
    static double V1, V2, S;
    static int phase = 0;
    double X;

    //srand((unsigned)time(NULL));
    if ( phase == 0 ) 
    {
        do 
        {
            double U1 = (double)rand() / RAND_MAX;
            double U2 = (double)rand() / RAND_MAX;
            V1 = 2 * U1 - 1;
            V2 = 2 * U2 - 1;
            S = V1 * V1 + V2 * V2;
        } 
        while(S >= 1 || S == 0);
        X = V1 * sqrt(-2 * log(S) / S);
    } 
    else
       X = V2 * sqrt(-2 * log(S) / S);

    phase = 1 - phase;
    return X;
}

static float V_CVT_F32_I32(int32 src) {
/*case SQ_V_CVT_F32_I32:
				vdst.f32[0] = (float)(src0.i32[0]);
				power_inst_type = POWER_CVT_F32_I32;
				break;
*/
    return (float)src;
}

static int32 V_CVT_I32_F32(float src) {
    /* reference CM9's code below
#define INT8_MIN         (-127i8 - 1)
#define INT16_MIN        (-32767i16 - 1)
#define INT32_MIN        (-2147483647i32 - 1)
#define INT64_MIN        (-9223372036854775807i64 - 1)
#define INT8_MAX         127i8
#define INT16_MAX        32767i16
#define INT32_MAX        2147483647i32
#define INT64_MAX        9223372036854775807i64
#define UINT8_MAX        0xffui8
#define UINT16_MAX       0xffffui16
#define UINT32_MAX       0xffffffffui32
#define UINT64_MAX       0xffffffffffffffffui64

			case SQ_V_CVT_I32_F32:

				if((bool)ALU::isNanF32((uint32)src0.u32[0]))
				{
					vdst.i32[0] = 0;
					//assert(0);
				}
				else if(((int64)(src0.f32[0])) > INT32_MAX)
				{
					vdst.i32[0] = INT32_MAX;
				}
				else if(((int64)(src0.f32[0])) < INT32_MIN)
				{
					vdst.i32[0] = INT32_MIN;
				}
				else
				{
					vdst.i32[0] = (int32)(src0.f32[0]);
				}*/
    int32 dst = 0;
    if (isNanF32(FloatMapToInt(src))) {
        dst = 0;
    } else if (((int64)src) > 2147483647) {
        dst = 2147483647;
    } else if (((int64)src) < -2147483648) {
        dst = -2147483648;
    } else {
        dst = (int32)src;
    }

    return dst;
}

uint32 prngB32(uint32 in)
{
    //if (in == 0) {
    //    return 0;
    //} else {
    //    uint32 in1  = (in >>  1) & 0x1;
    //    uint32 in5  = (in >>  1) & 0x1;
    //    uint32 in6  = (in >>  1) & 0x1;
    //    uint32 in31 = (in >> 31) & 0x1;

    //    return ( (in << 1) | (in1 ^ in5 ^ in6 ^ in31) );
    //}

    return ( (in << 1) ^ ( ( (in >> 31) & 0x1 ) ? 0xC5 : 0x00 ) );
}

union Float32Rand 
{ 
	struct {
	   	unsigned long Frac:23; 
		unsigned long Exp:8; 
		unsigned long Signed:1; 
	} BitArea; 
	float Value;
       //algorithm: (-1)^S*(1.M)*2^(E-127)	
};
float GetFloat32Rand() 
{ 
	union Float32Rand r;
	r.BitArea.Signed = rand() & 0x1;

	r.BitArea.Frac = (rand() * rand()) % 0x800000;
	//r.BitArea.Exp  = (rand() % 0x100) & 0xF;
	//r.BitArea.Exp  = (rand() % 0x100) & 0x7F;
	r.BitArea.Exp  = (rand() & 0x3F) + 95; //range [95, 158], so exp-127 range [-32, 31]
        //r.BitArea.Exp  = (rand() % 4) + 127;

	float RandDataTmp = r.Value;
/*
	while(abs(RandDataTmp) > 1)
	{
		RandDataTmp = RandDataTmp / 10.0;
	}

	while(abs(RandDataTmp) < 0.1)
	{
		RandDataTmp = RandDataTmp * 10.0;
	}
*/
	return RandDataTmp;
}


//rowin is row major without padding; columnout is column major with padding
template<typename TT>
static void padRowToColumn(TT *columnout, TT *rowin, int m, int n, int pad) {
    for (int iii = 0; iii < m; iii++)
    {
        for (int jjj = 0; jjj < n; jjj++)
        {
            columnout[jjj * (m + pad) + iii] = rowin[iii * n + jjj];
        }
    }
}

//rowin is row major without padding; columnout is column major, then combine each combs cols and adding padding
template<typename TT>
static void padRowToColTiling1D(TT *columnout, TT *rowin, int m, int n, int pad, int combs) {
    if(n%combs != 0)
      printf("not supported tiling");

    for (int iii = 0; iii < m; iii++)
    {
        for (int jjj = 0; jjj < n/combs; jjj++)
        {
            for(int k = 0; k < combs; k++)
                columnout[jjj * (m*combs + pad) + iii*combs + k] = rowin[iii * n + jjj*combs + k];
        }
    }
}

//RowToCol 2D tiling follow this step
// 1. input must row major
// 2. combine each comb_m point in col direction, as a unit
// 3. combine above each comb_n units in row direction, as a tile
// 4. place tiles in col major.
// in brief, col->row->col,

template<typename TT>
static void padRowToColTiling2D(TT *columnout, TT *rowin, int m, int n, int comb_m, int comb_n, int tile_pad, int pad) {
    int pos = 0;
    int tile_idx_x = 0;
    int tile_idx_y = 0;
    int tile_szx = 0;
    int tile_szy = 0;
    int tile_sz = 0;
    int tile_stride = 0;
    int tile_addr_offset = 0;
    int offset_x = 0;
    int offset_y = 0;
    int sub_addr_offset = 0;

    int Kdim = m;
    int Ndim = n;

    if(m%comb_m != 0 || n%comb_n != 0 )
      printf("not supported tiling");

    tile_szx = comb_n;
    tile_szy = comb_m;
    tile_sz = tile_szx * tile_szy;
    tile_stride = Kdim / tile_szy;

    for (int j = 0; j < Kdim; j++)
    {
        for (int i = 0; i < Ndim; i++)
        {
            tile_idx_y = j / tile_szy;
            tile_idx_x = i / tile_szx;

            offset_y = j % tile_szy;
            offset_x = i % tile_szx;

            tile_addr_offset = (tile_idx_x * tile_stride + tile_idx_y) * (tile_sz + tile_pad) + tile_idx_x * pad;
            sub_addr_offset = offset_x * tile_szy + offset_y;
            pos = tile_addr_offset + sub_addr_offset;

            columnout[pos] = rowin[j * Ndim + i];
        }
   }
}

//rowin is row major without padding; rowout is row major with padding
template<typename TT>
static void padRowToRow(TT *rowout, TT *rowin, int m, int n, int pad) {
    for (int iii = 0; iii < m; iii++) 
    {
        for (int jjj = 0; jjj < n; jjj++)
        {
            //row major
            rowout[iii * (n + pad) + jjj] = rowin[iii * n + jjj];
        }
    }
}

//rowin is row major without padding; rowout is row major, then combine each combs rows and adding padding
template<typename TT>
static void padRowToRowTiling1D(TT *rowout, TT *rowin, int m, int n, int pad, int combs) {
    //combined in col
    if(m%combs != 0)
      printf("not supported tiling");

    for (int iii = 0; iii < m/combs; iii++) 
    {
        for (int jjj = 0; jjj < n; jjj++)
        {
            for(int k = 0; k < combs; k++)
                 rowout[iii * (n*combs + pad) + jjj*combs + k] = rowin[(iii * combs + k )* n + jjj];
        }
    }
}

//columnin is column major with padding; rowout is row major without padding
template<typename TT>
static void unpadColumnToRow(TT *rowout, TT *columnin, int m, int n, int pad) {
    for (int iii = 0; iii < m; iii++) {
        for (int jjj = 0; jjj < n; jjj++) {
            rowout[iii * n + jjj] = columnin[jjj * (m + pad) + iii];
        }
    }
}

//rowin is row major with padding; rowout is row major without padding
template<typename TT>
static void unpadRowToRow(TT *rowout, TT *rowin, int m, int n, int pad) {
    for (int iii = 0; iii < m; iii++) {
        for (int jjj = 0; jjj < n; jjj++) {
            rowout[iii * n + jjj] = rowin[iii * (n + pad) + jjj];
        }
    }
}

template<typename TT>
static void unpadRowToRowDetiling1D(TT *rowout, TT *rowin, int m, int n, int pad, int combs) {
    //combined in col
    if(m%combs != 0)
      printf("not supported tiling");

    for (int iii = 0; iii < m/combs; iii++) 
    {
        for (int jjj = 0; jjj < n; jjj++)
        {
            for(int k = 0; k < combs; k++)
              rowout[(iii * combs + k )* n + jjj] = rowin[iii * (n*combs + pad) + jjj*combs + k];
        }
    }
}

//Return 1 means succeed
//bit match check
template<typename TT>
static uint32 check_result(TT *result, TT *golden, int Mdim, int Ndim, int pad, int c_col_major) 
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
            if ((c_col_major ? result[i * strideC + j] : result[j * strideC + i]) != golden[j * Ndim + i]) {
                SameResult = 0;

                uint32 *aaa, *bbb;
                aaa = (uint32 *)&(c_col_major ? result[i * strideC + j] : result[j * strideC + i]);
                bbb = (uint32 *)&golden[j * Ndim + i];

                printf("#######  diff index is [y = %d, x = %d]\n", j, i);
                //printf("#######  gpu results      = %f   \n", (c_col_major ? result[i * strideC + j] : result[j * strideC + i]));
                //printf("#######  golden           = %f   \n", golden[j * Ndim + i]);
                if (sizeof(TT) == 4) {
                    printf("#######  gpu results hex  = %08x    \n", aaa[0]);
                    printf("#######  golden      hex  = %08x    \n", bbb[0]);
                } else if (sizeof(TT) == 8) {
                    printf("#######  gpu results hex  = %08x %08x    \n", aaa[1], aaa[0]);
                    printf("#######  golden      hex  = %08x %08x    \n", bbb[1], bbb[0]);
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
#endif