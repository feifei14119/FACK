#ifndef COMMON_MI300_F16
#define COMMON_MI300_F16
/*
Defines f16 convert related stuff
*/
#include "common.h"
#ifdef USE_CBLAS
#include <cblas.h>
#endif

typedef union Index
{
    uint8 index:2;
} tIndex;

uint32 round_bf16_significand_rne(bool &is_significand_ovf, uint32 trail_sig_bf16)
{
    is_significand_ovf = false;
    // trail_sig_bf16 is of the form 1.31
    uint32 trail_significand = (trail_sig_bf16 >>  24) & 0x7f;
    uint32 ulp_half_ulp      = (trail_sig_bf16 >>  23) & 0x3;    // 1.31 >> 23 = 1.8
    uint32 or_remain         = (trail_sig_bf16 >>  0) & 0xffffff;
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
    is_significand_ovf = (((trail_significand >> 7) & 0x1) == 0x1);
    return (trail_significand & 0x7f);   // trail_significand is of the form .7
}

uint32 FP32toBFP16(uint32 in, bool clamp=0)
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

    // at this point the exponent is the output exponent range

    uint16_t bf16 = 0;

    if (is_f32_pre_scale_inf) {
        bf16 = (sign_f32 << 15) | ((clamp == 0) ? 0x7f80 : 0x7f7f);
    } else if (is_f32_pre_scale_nan) {
        bf16 = (sign_f32 << 15) | 0x7fff;
    } else if (is_f32_pre_scale_zero) {
        bf16 = (sign_f32 << 15) | 0x0;
    } else {
        if (unbiased_exp_f32 < -149) {
            // scaled number is less than bf16 min subnorm; output 0
            bf16 = (sign_f32 << 15) | 0x0;
        } else if (unbiased_exp_f32 < -126) {
            int32 exp_shift     = -126 - unbiased_exp_f32;
            int32 unbiased_exp_bf16
                                = unbiased_exp_f32 + exp_shift;
            assert(unbiased_exp_bf16 == -126);
            uint32 trail_sig_bf16 = (1 << 31) | (trailing_significand_f32 << 8);
            trail_sig_bf16      >>= exp_shift;
            bool   is_sig_ovf   = false;
            trail_sig_bf16        = round_bf16_significand_rne(is_sig_ovf, trail_sig_bf16);
            bf16 = (sign_f32 << 15)
                    | ((is_sig_ovf ? 0x01 : 0x00) << 7)
                    | (trail_sig_bf16 & 0x7f);
        } else if (unbiased_exp_f32 < +128) {
            // scaled number is in bf16 normal range
            //  apply rne
            uint32 biased_exp_bf16
                                = unbiased_exp_f32 + 127;
            uint32 trail_sig_bf16 = (1 << 31) | (trailing_significand_f32 << 8);
            bool   is_sig_ovf   = false;
            trail_sig_bf16        = round_bf16_significand_rne(is_sig_ovf, trail_sig_bf16);
            biased_exp_bf16      += (is_sig_ovf ? 1 : 0);
            if (biased_exp_bf16 == +255) {
                bf16 = (sign_f32 << 15) | ((clamp == 0) ? 0x7f80 : 0x7f7f);
            } else {
                bf16 = (sign_f32 << 15)
                        | ((biased_exp_bf16 & 0xff) << 7)
                        | (trail_sig_bf16 & 0x7f);
            }
        } else {
            // scaled number is greater than bf16 max normal output
            //  clamp to bf16 flt_max/inf based on clamp control
            bf16 = (sign_f32 << 15) | ((clamp == 0) ? 0x7f80 : 0x7f7f);
        }
    }

    return (uint32)bf16;
}

cl_half Int16MapToClhalf(uint16 in)
{
    return *((cl_half *)&in);
}

uint32 BFP16toFP32(uint32 in)
{
	return (in<<16);
}

union FloatBF16Rand
{
    struct {
            unsigned long Frac:7;
            unsigned long Exp:8;
            unsigned long Signed:1;
    } BitArea;
    short Value;
        //algorithm: (-1)^S*(1.M)*2^(E-127)
};

float GetFloatBF16Rand()
{
    union FloatBF16Rand r;
    r.BitArea.Signed = rand() & 0x1;

    r.BitArea.Frac = (rand() * rand()) % 0x80;
    //r.BitArea.Exp  = rand()%128; //rand() % 126 + 1;  //1--126 randon
    r.BitArea.Exp  = (rand() & 0x3F) + 95; //range [95, 158], so exp-127 range [-32, 31]
	
    float RandDataTmp = r.Value;
    return RandDataTmp;
}

uint32 FP16toFP32(uint32 in)
{
	uint32  mm, ee, ss;
	uint32  m, e, s;
	ss = SIGN16(in);
	ee = BEXP16(in);
	mm = MAN16(in);

	m = mm;
	m <<= 13;
	e = ee;
	e += (127 - 15);
	s = ss;

	if (ee == 0x1f)
	{
		if (mm)  // NaN
		{
			m |= (s << 31);
			m |= 0x7f800000;
			return m;
		}
		else    // inf
			return (s ? 0xff800000 : 0x7f800000);
	}

	if (ee == 0)
	{
		if (m == 0)  // zero
			return (s ? 0x80000000 : 0x0);
		else       // normalize input denorm
		{
			e++;
			while (!(m >> 23))
			{
				m <<= 1;
				e--;
			}
			m &= 0x7fffff;
		}
	}

	m |= (e << 23);
	m |= (s << 31);
	return m;
}

uint32 s_round_ieee_16(uint32 mant, uint32 guard, uint32 round, uint32 sticky, uint32 sign, int32 &exp)
{
    uint32 result = mant;

    // Round
    if (guard && ((mant&1) || round || sticky)) 
        result++;

    if(result >> 11)
    {
        result >>= 1;
        exp++;
    }

    // Overflow
    if(exp >= 0x1f && (mant || guard || round || sticky))
    {
        exp = 0x1f;
        result = 0x400;
    }

    // Underflow
    if(exp <= 0 || result==0)
    {
        exp = 0;
        if (result || guard || round || sticky )
        {
            result = 0;
        }
    }

    // Handle denorms
    else if (exp==1 && (result>>10)==0)
    {
        exp = 0;
    }
    return result;
}

uint32 FP32toFP16(uint32 in, bool isMi300=false)
{
	bool stick = false;
	uint32 m;
	int32  e;
	uint32 ss = SIGN32(in);
	uint32 ee = BEXP32(in);
	uint32 mm = MAN32(in);

	// Check Special cases
	if (ee == 0xff)
	{
		if (mm)  //NaN
		{
			m = (mm >> 13);
			m |= 0x7e00;
			m |= (ss << 15);
			return m;
		}
		else   //inf
			return (ss ? 0xfc00 : 0x7c00);
	}
	if (ee == 0 && mm == 0) // zero
		return (ss ? 0x8000 : 0);

	// Normal cases
	e = ee - 127 + 15;
	if (ee)
		mm |= 0x800000;

	m = (mm >> 11); // 1.12 (m + g + r)
	stick = (mm & 0x7ff) ? true : false;

	// Create denorm output
	if (e<1)
	{
		int32 shift = 1 - e;
		if (shift > 31) shift = 31;
		uint32 mask = (1 << shift) - 1;
		stick |= (m & mask) ? true : false;
		m >>= shift;
		if (shift > 31) m = 0;
		e = 1;
	}

#ifndef KL_MODEL
        //process denorm and rounding (RND_NEAREST_EVEN) is definitely nessary, 
        //but cm9 don't add this,--can't bitmatch if enable belowing.
        //so just enable it when it is run under RTL.
        m = s_round_ieee_16(m>>2, m&2, m&1, stick, ss, e);
#else
    if(!isMi300)
        m>>=2;
#endif
	return (FP16(ss, e, m));
}
//buffer is row major
static void initBF16_MatrixInRowMajor(cl_half *buffer, int m, int n, int sin_cos_init, int usesin) {
    for (int iii = 0; iii < m; ++iii)
    {
        for (int jjj = 0; jjj < n; ++jjj)
        {
            float temp_var = GetFloatBF16Rand();
            uint32 temp_var_int = FP32toBFP16(FloatMapToInt(temp_var));
            buffer[iii * n + jjj] = Int16MapToClhalf ((uint16)temp_var_int) ;

            if (sin_cos_init) {
                if (usesin == 1) {
                    temp_var = sin(iii * n + jjj);
                } else if (usesin == 0) {
                    temp_var = cos(iii * n + jjj);
                } else if (usesin == 2) {
                    temp_var = sin(iii * n + jjj) + cos(iii * n + jjj);
                }
  
                temp_var_int = FP32toBFP16(FloatMapToInt(temp_var));
                buffer[iii * n + jjj] = Int16MapToClhalf ((uint16)temp_var_int) ;
            }
        }
    }
}

static void dumpFP32MatrixInHex(cl_float *data, const char *fileName, int m, int n, int pad, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        fprintf(file, "R[%04d]: ",i);
        for (int j = 0; j < n; j++) {
            cl_float valueP;
            if (rowmajor == 1) {
                valueP = data[i * (n+pad) + j];
            } else {
                valueP = data[j * (m+pad) + i];
            }
            fprintf(file,"%08x ", *((uint32*)&valueP));
        }
        fprintf(file, "\n");
    }

    fclose(file);
}

static void dumpBFP16MatrixInHex(cl_half *data, const char *fileName, int m, int n, int pad, int rowmajor) {
    FILE *file = fopen(fileName, "w+t");
    for (int i = 0; i < m; i++) {
        fprintf(file, "R[%04d]: ",i);
        for (int j = 0; j < n; j++) {
            cl_half valueP;
            if (rowmajor == 1) {
                valueP = data[i * (n+pad) + j];
            } else {
                valueP = data[j * (m+pad) + i];
            }
            fprintf(file, "0x%04x ", (valueP & 0xffff));
        }
        fprintf(file, "\n");
    }

    fclose(file);
}


void matrix_mul_bf16_mi350(cl_half *a, cl_half *b, cl_float *c, int m, int n, int k, int pad, int is_c_b16 = 0)
//////////////////////////////////////////////////////////////////////////// 
//  a[M][K]   b[K][N]   c[M][N]
//  c_matrix=a_matrix*b_matrix  
////////////////////////////////////////////////////////////////////////////  
{
	short *pAbuffer = (short *)a;
	short *pBbuffer = (short *)b;
	unsigned short *pCbuffer = (unsigned short *)c;

	for (int iii = 0; iii < m; ++iii)
	{
		for (int jjj = 0; jjj < n; ++jjj)
		{
			float cData = IntMapToFloat(BFP16toFP32(0));
			for (int kkk = 0; kkk < k - pad; kkk = kkk + 8)
			{
                double result = 0.0f;
                for (int i = 0; i < 8; i++) 
                {
                    float a, b;
                    a = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[iii * k + kkk + i]));
                    b = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[(kkk + i) * n + jjj]));
                    result += (double)a * (double)b;
                }
                result += (double)cData;
                cData = (float)result;
			}
			if(is_c_b16)
				pCbuffer[iii*n + jjj] = (unsigned short)FP32toBFP16(FloatMapToInt(cData));
			else
				c[iii*n + jjj] = cData;
		}
	}

	return;
}

#ifdef USE_CBLAS
//using openblas to accelerate matmul
//matrix all row major, a: mxk, b: kxn, c:mxn;
void matrix_mul_bf16_mi350_cblas(cl_half *a, cl_half *b, cl_float *c, int m, int n, int k, int pad, int is_c_b16 = 0)
//////////////////////////////////////////////////////////////////////////// 
//  a[M][K]   b[K][N]   c[M][N]
//  c_matrix=a_matrix*b_matrix  
////////////////////////////////////////////////////////////////////////////  
{
	short *pAbuffer = (short *)a;
	short *pBbuffer = (short *)b;
	unsigned short *pCbuffer = (unsigned short *)c;

    std::vector<float> a_fp32(m * k), b_fp32(n * k), c_fp32(m * n, 0);

	for (int iii = 0; iii < m; ++iii) {
		for (int kkk = 0; kkk < k - pad; kkk = kkk + 8) {
                for (int i = 0; i < 8; i++)  {
                    a_fp32[iii * k + kkk + i] = IntMapToFloat(BFP16toFP32((uint32)pAbuffer[iii * k + kkk + i]));
                }
		}
	}

    for (int jjj = 0; jjj < n; ++jjj) {
		for (int kkk = 0; kkk < k - pad; kkk = kkk + 8) {
                for (int i = 0; i < 8; i++)  {
                    b_fp32[(kkk + i) * n + jjj] = IntMapToFloat(BFP16toFP32((uint32)pBbuffer[(kkk + i) * n + jjj]));
                }
		}
	}

    cblas_sgemm(CblasRowMajor,
                CblasNoTrans,   // A, row major
                CblasNoTrans,   // B, row major
                m, n, k,
                1,
                a_fp32.data(),
                k,              // A leading dimension
                b_fp32.data(),
                n,
                0,
                c_fp32.data(),
                n);

    for (int iii = 0; iii < m; ++iii) {
		for (int jjj = 0; jjj < n; ++jjj) {  
			if(is_c_b16)
				pCbuffer[iii*n + jjj] = (unsigned short)FP32toBFP16(FloatMapToInt(c_fp32[iii*n + jjj]));
			else
				c[iii*n + jjj] = c_fp32[iii*n + jjj];
		}
	}

	return;
}
#endif



#endif