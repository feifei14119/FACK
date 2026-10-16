# Finetune-Amd-Co-Kernel — 架构可插拔的指令级 AI 辅助优化引擎

把"AI 逐字改 ASM"反转为 **AI 发结构化操作 / 固定逻辑保合法重排 + 修补 pass 流水线 / 真机测量** 的指令级优化引擎。

## 自学成果：直接读取已有 skill

`selfstudy/` 是 [gfx_hw_prob](https://github.com/feifei14119/gfx_hw_prob.git) 的 submodule

新 clone 或恢复依赖时，在 FACK 根目录运行：

```bash
bash tools/init_selfstudy.sh
```

## 调优用法 (client 无关)

框架**不绑定任何具体项目**:用 `--client` 选调优项目

## Aiter HSA client

通过 `client/aiter/upstream` submodule 接入 ROCm/aiter；先在目标机器运行 `bash tools/init_aiter.sh`。

### 调优结果

<!-- fack:tuning-results:start -->

以下为各输入尺寸下通过最终验证的候选，性能提升按配对比值计算；不表示整份 `.co` 的所有尺寸均可替换。

| 序号 | co 名字（含路径） | 输入尺寸 | 性能提升 | 调优时间（UTC） |
|---|---|---|---|---|
| 1 <!-- fack:result:6e782f668307041d2335bad4e56a0b17755ed679d5b2cd3b3c012869c0be50a1 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co](client/aiter/co_out/.versions/b409b1ba9c475edf195487999c715453fc7c638df0a8b8eb0c00dea07d7c17d3/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_32x128.co) | M=32; N=8192; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +8.28%<br>op_test:constant/constant: +6.25%<br>op_test:uniform/auto: +6.17% | 2026-10-15T02:46:22+00:00（耗时 9.0 分钟） |
| 2 <!-- fack:result:123ed1358d0849dd2ca23fac5f2540defdb6cbb3e89d1e1369f7723c1ca66a33 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_48x128.co](client/aiter/co_out/.versions/8d8fc556490e5a338d7a90a2acb08cadf9ab9b72b097693016cff0f9beb93af6/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_48x128.co) | M=144; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +3.04%<br>op_test:constant/constant: +2.99%<br>op_test:uniform/auto: +2.85% | 2026-10-16T04:52:46+00:00（耗时 20.9 分钟） |
| 3 <!-- fack:result:e9c427ade33956e0b409d771c0e5c258eb580d3ff241c76ae4d0dd5e472cfb38 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=208; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.39%<br>op_test:constant/constant: +1.98%<br>op_test:uniform/auto: +2.25% | 2026-10-16T06:07:59+00:00（耗时 20.9 分钟） |
| 4 <!-- fack:result:d3eafbfa6354bf345ce1e0612c2e45cd7b0247b6ffa01f823957606037e4f361 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=224; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.41%<br>op_test:constant/constant: +2.17%<br>op_test:uniform/auto: +2.15% | 2026-10-16T06:29:10+00:00（耗时 20.9 分钟） |
| 5 <!-- fack:result:6e034194e1df0ffbcf3eb0a27e06c18c59194233860aa373efddb6a7c8f19293 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=240; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.44%<br>op_test:constant/constant: +1.92%<br>op_test:uniform/auto: +2.04% | 2026-10-16T06:50:35+00:00（耗时 21.0 分钟） |
| 6 <!-- fack:result:78aa5ab8611eecb1cbc75e748d08bed64dba630e183a446fd40e3386330f13b6 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co](client/aiter/co_out/.versions/2b5e5e2d0db82b76ed47a4f9cb1289db66179fd6501d806b26bc464321b9363d/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co) | M=256; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +1.50%<br>op_test:constant/constant: +1.35%<br>op_test:uniform/auto: +1.45% | 2026-10-16T07:11:57+00:00（耗时 21.1 分钟） |
| 7 <!-- fack:result:4398cb202d489293bb2db73dee7b39dbbc4969f5e664ef13259834632cd0522a --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co](client/aiter/co_out/.versions/0243dce83eb2a337550087569b649fe633f03f7e912cf662d42d25809cf6696c/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co) | M=288; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.02%<br>op_test:constant/constant: +1.72%<br>op_test:uniform/auto: +1.89% | 2026-10-16T07:33:05+00:00（耗时 20.8 分钟） |
| 8 <!-- fack:result:49b00134cc249604e73204ba569901aff76defe0cb8041d9d8c70c26e6c82ed3 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_128x128.co](client/aiter/co_out/.versions/c1b0da2f9be9e76e34f1a1a539feaad872a8f4464b9afa54ad5adac1459b4b57/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_128x128.co) | M=320; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +1.69%<br>op_test:constant/constant: +1.77%<br>op_test:uniform/auto: +1.69% | 2026-10-16T07:55:09+00:00（耗时 21.7 分钟） |
| 9 <!-- fack:result:487496d262edce50213eb7fcaa9743f15dc228e1c4ab8681d021273a95571789 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=480; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.46%<br>op_test:constant/constant: +2.02%<br>op_test:uniform/auto: +2.20% | 2026-10-16T08:23:31+00:00（耗时 21.7 分钟） |
| 10 <!-- fack:result:555545e9bad908267fdb762f868500d09476c086996b7a1217526255d6da4c7a --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co](client/aiter/co_out/.versions/0243dce83eb2a337550087569b649fe633f03f7e912cf662d42d25809cf6696c/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_96x128.co) | M=512; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.13%<br>op_test:constant/constant: +1.83%<br>op_test:uniform/auto: +1.98% | 2026-10-16T08:46:21+00:00（耗时 22.5 分钟） |
| 11 <!-- fack:result:89731a2dae826bf632466823a3f3558953a3a215e534a0cfe135671f383935b6 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=736; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.49%<br>op_test:constant/constant: +2.20%<br>op_test:uniform/auto: +2.20% | 2026-10-16T09:37:39+00:00（耗时 22.8 分钟） |
| 12 <!-- fack:result:bc3ef265c4c120535f0ade992efa537944a8809b1930aad5d33529ca2ae5a92d --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=768; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.47%<br>op_test:constant/constant: +2.07%<br>op_test:uniform/auto: +2.24% | 2026-10-16T10:00:02+00:00（耗时 22.0 分钟） |
| 13 <!-- fack:result:46f6412d15a8b97d564954e17759496165a73a09fce7a959aa4cb2bb11f4c6d4 --> | [gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co](client/aiter/co_out/.versions/6a5b26619be8582c9894e2ff6cde2a597827975d1a9d99da117637a3893848c1/gfx942/fp8gemm_blockscale/fp8gemm_bf16_blockscale_BpreShuffle_80x128.co) | M=800; N=3072; K=7168; dtype=torch.float8_e4m3fnuz; outdtype=torch.bfloat16; splitK=1 | hip_graph: +2.38%<br>op_test:constant/constant: +2.27%<br>op_test:uniform/auto: +2.27% | 2026-10-16T10:26:40+00:00（耗时 26.3 分钟） |
<!-- fack:tuning-results:end -->
