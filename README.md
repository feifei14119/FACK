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
<!-- fack:tuning-results:end -->
