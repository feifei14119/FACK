#include <stdio.h>
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <random>
#include <map>
#include <vector>
#include <iostream>
#include <stdlib.h>
#include <math.h>
#ifdef USE_MKL
#include <mkl.h>
#endif
#define HALF
#ifdef HALF
#include "./common/half.hpp"
#endif

#define FMHA_MI300      //define MI300 before include header file
#include "gemm.hpp"

#define ASSERT_ON_FAIL
#define MFMA
// #define ASM_PRINT

#ifndef ABS
#define ABS(x) ((x) > 0 ? (x) : -1 * (x))
#endif

#define HIP_CALL(call)                                                 \
    do                                                                 \
    {                                                                  \
        hipError_t err = call;                                         \
        if (err != hipSuccess)                                         \
        {                                                              \
            printf("[hiperror](%d) fail to call %s", (int)err, #call); \
            exit(0);                                                   \
        }                                                              \
    } while (0)

static inline int get_int(const char *env_name, int def_value)
{
    char *v = getenv(env_name);
    if (v)
        return atoi(v);
    return def_value;
}

//change this for GEMM kernel
#define HSACO "gemm.co"
#define HSA_KERNEL "gemm_kernel_func"

std::map<std::string, unsigned int> parse_options(const std::vector<std::string> &optionList)
{
    std::map<std::string, unsigned int> options;
    for (const std::string &option : optionList)
    {
        size_t equalPos = option.find('=');
        if (equalPos != std::string::npos)
        {
            std::string key = option.substr(0, equalPos);
            std::string value = option.substr(equalPos + 1);
            options[key] = std::stoull(value);
        }
        else
        {
            // Handle error or ignore options with no equal sign
            std::cerr << "Error: Invalid option format: " << option << std::endl;
        }
    }
    return options;
}

void get_param(std::map<std::string, unsigned int> parsedOptions, std::string key, unsigned int &value)
{
    auto it = parsedOptions.find(key);
    if (it != parsedOptions.end())
    {
        value = it->second;
    }
}


int main(int argc, char **argv)
{
    hipModule_t module;
    hipFunction_t kernel_func;
    hipEvent_t evt_00, evt_11;
    HIP_CALL(hipSetDevice(1));
    HIP_CALL(hipModuleLoad(&module, HSACO));
    HIP_CALL(hipModuleGetFunction(&kernel_func, module, HSA_KERNEL));

    const unsigned int block_shape_k     = 128;
    const unsigned int block_shape_n     = 128;
    const unsigned int block_shape_m     = 1;

    int validate = get_int("VALIDATE", 0);
    unsigned int m               = 128*20;
    unsigned int n               = 128*20;
    unsigned int k               = 128*2;
    unsigned int pad_a           = 0;
    unsigned int pad_b           = 0;
    unsigned int pad_c           = 0;
    unsigned int sin_cos_init    = 0;
    unsigned int sub_m           = 32;  // make it correspond to the kernel
    unsigned int sub_n           = 128;
    unsigned int new_ks          = 1;
    unsigned int ks              = 1;    //this is for ksplit, 1 as default
    unsigned int dump_result     = 0;

    unsigned int total_loop = 20;
    unsigned int warm_ups = 0;

    std::vector<std::string> options;
    for (int i = 1; i < argc; i++)
    {
        options.push_back(argv[i]);
    }
    std::map<std::string, unsigned int> parsedOptions = parse_options(options);
    get_param(parsedOptions, "m",            m);
    get_param(parsedOptions, "n",            n);
    get_param(parsedOptions, "k",            k);
    get_param(parsedOptions, "pad_a",        pad_a);
    get_param(parsedOptions, "pad_b",        pad_b);
    get_param(parsedOptions, "pad_c",        pad_c);
    get_param(parsedOptions, "sin_cos_init", sin_cos_init);
    get_param(parsedOptions, "sub_m",        sub_m);
    get_param(parsedOptions, "sub_n",        sub_n);
    get_param(parsedOptions, "new_ks",       new_ks);
    get_param(parsedOptions, "ks",           ks);
    get_param(parsedOptions, "dump_result",  dump_result);
    get_param(parsedOptions, "total_loop",   total_loop);

    //print the parameter
    std::cout << "m:"                    << m            << std::endl;
    std::cout << "n:"                    << n            << std::endl;
    std::cout << "k:"                    << k            << std::endl;
    std::cout << "pad_a:"                << pad_a        << std::endl;
    std::cout << "pad_b:"                << pad_b        << std::endl;
    std::cout << "pad_c:"                << pad_c        << std::endl;
    std::cout << "sub_m:"                << sub_m        << std::endl;
    std::cout << "sub_n:"                << sub_n        << std::endl;
    std::cout << "ks:"                   << ks           << std::endl;
    std::cout << "dump_result:"          << dump_result  << std::endl;
    std::cout << "total_loop:"           << total_loop  << std::endl;

    int stride_a, stride_b, stride_c;
    int szA, szB, szC;

    stride_a = k + pad_a;
    stride_b = k + pad_b;
    stride_c = n + pad_c;

    szA = m * stride_a;
    szB = n * stride_b;

    szC = (m * stride_c) * sizeof(cl_half);
    stride_c = stride_c * sizeof(cl_half);

    unsigned int scale_m = m;
    unsigned int scale_n = (n+block_shape_n-1) / block_shape_n;
    unsigned int scale_k = (k+block_shape_k-1) / block_shape_k;

    printf("m:%d, n:%d, k:%d\n", m, n, k);
    printf("scale_m:%d, scale_n:%d, scale_k:%d\n", scale_m, scale_n, scale_k);

    //generate the input data and put into the device
    float *scale_a = new float[scale_m * scale_k];
    float *scale_a_t = new float[scale_m * scale_k];
    float *scale_b = new float[scale_n * scale_k];
    float *bias  = new float[n];
    //input buffer init
    cl_char *A_outbuffer  = new cl_char[szA];
    cl_char *AT_outbuffer = new cl_char[szA];
    cl_char *B_outbuffer  = new cl_char[szB];
    cl_char *BT_outbuffer = new cl_char[szB];
    cl_char *C_outbuffer  = new cl_char[szC];
    cl_char *CT_outbuffer = new cl_char[szC];
    cl_half *output_bf16  = new cl_half[m*n];
    memset(output_bf16, 0, sizeof(cl_half)*m*n);
    memset(CT_outbuffer, 0, szC);

    float *output_f32            = new float[m*n]; 
    float *output_f32_sa         = new float[m*n]; 
    float *output_f32_sa_sb      = new float[m*n]; 
    float *output_f32_sa_sb_bias = new float[m*n]; 
  

    srand((unsigned)time(NULL));
    initF32_scale(scale_a, scale_m * scale_k, 1);        
    for (unsigned int mi = 0; mi < scale_m; ++mi) {
        for (unsigned int ki = 0; ki < scale_k; ++ki) {
            scale_a_t[ki * scale_m + mi] = scale_a[mi * scale_k + ki];
        }
    }
    initF32_scale(scale_b, scale_n * scale_k, 1);        
    initFP32_bias(bias, n);
   
    initFP8MatrixInRowMajor(A_outbuffer, m, k);
    initFP8MatrixInRowMajor(B_outbuffer, n, k);
    // initFP8MatrixInRowMajor(CT_outbuffer, m, n, sin_cos_init, 0); //add dirty data
    memset(CT_outbuffer, 0x3F80, szC);


    if(dump_result)
    {
        total_loop = 1;
        GEMM_FP8_BLOCKSCALE_BIAS_dbg(output_bf16, output_f32,
                                     A_outbuffer, B_outbuffer, scale_a, scale_b, bias, m, n, k, 1, block_shape_n, block_shape_k, false, false);   //FP8 block scale version
    }
    padRowToRow<cl_char>(AT_outbuffer, A_outbuffer, m, k, pad_a);
    tiling_16x16x32_i8_dw4_sw(BT_outbuffer, B_outbuffer, n, k);

    //init the data pointer for kernel
    cl_char *dev_a, *dev_b; 
    cl_half *dev_c;
    float *dev_sa, *dev_sb;
    cl_half *dev_bias;

    HIP_CALL(hipSetDevice(1));
    HIP_CALL(hipMalloc(&dev_a,          szA));
    HIP_CALL(hipMalloc(&dev_b,          szB));
    HIP_CALL(hipMalloc(&dev_c,          szC));
    HIP_CALL(hipMalloc(&dev_sa,         scale_m * scale_k * sizeof(float)));
    HIP_CALL(hipMalloc(&dev_sb,         scale_n * scale_k * sizeof(float)));
    HIP_CALL(hipMalloc(&dev_bias,       n*sizeof(float)));

    //copy the data to device 
    HIP_CALL(hipMemcpy(dev_a, AT_outbuffer, szA, hipMemcpyHostToDevice));
    HIP_CALL(hipMemcpy(dev_b, BT_outbuffer, szB, hipMemcpyHostToDevice));
    HIP_CALL(hipMemcpy(dev_c, CT_outbuffer, szC, hipMemcpyHostToDevice));
    HIP_CALL(hipMemcpy(dev_sa, scale_a_t, scale_m * scale_k * sizeof(float), hipMemcpyHostToDevice));
    HIP_CALL(hipMemcpy(dev_sb, scale_b, scale_n * scale_k * sizeof(float), hipMemcpyHostToDevice));
    HIP_CALL(hipMemcpy(dev_bias, bias, n*sizeof(float), hipMemcpyHostToDevice));

    int bdx = 256;
    int bdy = 1;
    int bdz = 1;
    int gdx = (n + sub_n - 1) / sub_n;
    int gdy = (m + sub_m - 1) / sub_m;
    int gdz = 1;
    std::cout << "gdy:"                    << gdy            << std::endl;

    if (ks && new_ks) 
    {
        // ksplit means the real splits the Kdim is cut into.
            int k_per_split = (k + ks - 1) / ks;
            int k_per_split_aligned = ((k_per_split + 127) / 128) * 128;

            int actual_ksplit = (k + k_per_split_aligned - 1) / k_per_split_aligned;
            if (actual_ksplit != ks)
            {
                printf("warning: change ksplit form %d to %d to make sure every block deals with 128x k\n",
                       ks, actual_ksplit);
                ks = actual_ksplit;
            }

            k_per_split = (k + ks - 1) / ks;
            k_per_split_aligned = ((k_per_split + 127) / 128) * 128;
            printf("K info: _s_K=%d, _s_ksplit=%d, _s_K_per_tg=%d, k_per_split_aligned=%d\n",
                   k, ks, k_per_split, k_per_split_aligned);

            gdx = gdx * ks;
    }else{
            gdx = gdx << ks;
    }
    std::cout << "gdx:"                    << gdx            << std::endl;
    std::cout << "gdz:"                    << gdz            << std::endl;

    struct p3 
    {
        unsigned int _p0;
        unsigned int _p1;
        unsigned int _p2;
    };
    struct p2
    {
        unsigned int _p0;
        unsigned int _p1;
    };
    //start to prepare the input and output buffer
    struct __attribute__((packed)) {
        void*  ptr_c;
        p2 _p0;
        void*  ptr_a;
        p2 _p1;
        void*  ptr_b;
        p2 _p2;
        void*  ptr_sa;
        p2 _p3;
        void*  ptr_sb;
        p2 _p4;
        void*  ptr_bias;
        p2 _p5;
        //float alpha;
        unsigned int m;
        p3 _p12;
        unsigned int n;
        p3 _p13;
        unsigned int k;
        p3 _p14;
        unsigned int lda;
        p3 _p15;
        unsigned int ldb;
         p3 _p16;
        unsigned int ldc;
         p3 _p17;
        unsigned int ks;
         p3 _p18;
         unsigned int scale_m;
         p3 _p19;
         unsigned int scale_n;
         p3 _p20;
         unsigned int scale_k;
         p3 _p21;
        #ifdef ASM_PRINT
        void*  print;
        #endif
    } args;
    size_t arg_size = sizeof(args);
    args.ptr_c  = (void*)dev_c;
    args.ptr_a  = (void*)dev_a;
    args.ptr_b  = (void*)dev_b;
    args.ptr_sa = (void*)dev_sa;
    args.ptr_sb = (void*)dev_sb;
    args.ptr_bias = (void*)dev_bias;

    args.m      = m;
    args.n      = n;
    args.k      = k;
    args.lda    = stride_a;
    args.ldb    = stride_b;
    args.ldc    = stride_c;
    args.ks     = ks;
    args.scale_m = scale_m;
    args.scale_n = scale_n;
    args.scale_k = scale_k;
    #ifdef ASM_PRINT
    args.print  = (void*)print;
    #endif
    void* config[] = {HIP_LAUNCH_PARAM_BUFFER_POINTER, &args, HIP_LAUNCH_PARAM_BUFFER_SIZE,
                    &arg_size, HIP_LAUNCH_PARAM_END};

    //warm up
    for(int i=0;i<warm_ups;i++){
        HIP_CALL(hipModuleLaunchKernel(kernel_func, 1,1,1, 1,1,1,  0, 0, NULL, (void**)&config ));
        //std::cout<<"safe here"<<std::endl;
    }

    HIP_CALL(hipEventCreate(&evt_00));
    HIP_CALL(hipEventCreate(&evt_11));
    HIP_CALL(hipDeviceSynchronize());
    HIP_CALL(hipEventRecord(evt_00, NULL));
    //kernel call
    for(int i=0;i<total_loop;i++)
        //HIP_CALL(hipModuleLaunchKernel(kernel_func, 1,1,1, 1,1,1,  0, 0, NULL, (void**)&config ));
        HIP_CALL(hipModuleLaunchKernel(kernel_func, gdx, gdy, gdz, bdx, bdy, bdz, 0, 0, NULL, (void **)&config));

    float elapsed_ms = 0.0;
    HIP_CALL(hipEventRecord(evt_11, NULL));
    HIP_CALL(hipEventSynchronize(evt_11));
    HIP_CALL(hipDeviceSynchronize());
    HIP_CALL(hipEventElapsedTime(&elapsed_ms, evt_00, evt_11));
    HIP_CALL(hipEventDestroy(evt_00));
    HIP_CALL(hipEventDestroy(evt_11));

    float time_per_loop = elapsed_ms/total_loop;
    float gflops = (float)2*m*n*k/time_per_loop/(1e6);
    printf("m:%d,n:%d,k:%d,time: %.6f,gflops:%.3f\n",m,n,k,time_per_loop,gflops);


    //read the GPU result
    HIP_CALL(hipMemcpy(C_outbuffer, dev_c, szC, hipMemcpyDeviceToHost));

    //correctness check only -- do NOT dump any result data to disk
    if(dump_result) 
    {
        if(ks == 0) //for no k split check
            check_result((cl_half*)C_outbuffer, output_bf16, m, n, 0, 0); //for bitmatch
        else
            check_result_eps((cl_half*)C_outbuffer, output_bf16, m, n, 0, 0, 0.001f); //for abs check
    }

    delete [] A_outbuffer;
    delete [] AT_outbuffer;
    delete [] B_outbuffer;
    delete [] BT_outbuffer;
    delete [] C_outbuffer;
    delete [] CT_outbuffer;
    delete [] scale_a;
    delete [] scale_b;
    delete [] scale_a_t;
    delete [] bias;  
    delete [] output_bf16;
    delete [] output_f32;
    delete [] output_f32_sa;
    delete [] output_f32_sa_sb;
    delete [] output_f32_sa_sb_bias;

    HIP_CALL(hipFree(dev_a));
    HIP_CALL(hipFree(dev_b));
    HIP_CALL(hipFree(dev_c));
    HIP_CALL(hipFree(dev_sa));
    HIP_CALL(hipFree(dev_sb));
    HIP_CALL(hipFree(dev_bias));

    return 0;
}