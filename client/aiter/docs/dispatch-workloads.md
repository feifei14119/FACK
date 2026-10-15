# 从 aiter dispatch CSV 生成调优 workload

使用 `client/aiter/dispatch.py` 固定执行 CSV 解析、catalog 关联、任务标识、参数锁定和覆盖率汇总。
`knowledge/skills/aiter-gfx942-validation/SKILL.md` 指导 agent 选择环境、执行这些命令、调优和解释证据。
aiter client 的数值验证与计时仍由 Python driver 完成；skill 不代替程序实现派发规则。

这里寻找的是**当前配置选择某个 kernel 的 workload**，不证明这是该 `.co` 的全局最优尺寸，也不证明
该 kernel 在新机器、新版本或其他 backend 中最快。CSV 中的 `us` 只是来源数据，不能代替新机器上的基线。

## 1. 获取目标环境，然后在 CPU 上生成计划

按 [环境与验证步骤](validation.md) 确认 GPU、依赖和固定 aiter 提交。需要倒数第二张卡时继续使用
`docker_env.py start --gpu second-last`，不要硬编码 GPU 6。通过目标容器中的 torch 读取实际 CU 数：

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 -c \
  'import torch; p=torch.cuda.get_device_properties(0); print(p.gcnArchName, p.multi_processor_count)'
```

`80` 是已验证 MI308X 的 CU 数，不是所有 gfx942 的默认值。下例中的值要替换为当前设备结果：

```bash
python3 client/aiter/dispatch.py plan --arch gfx942 --cu 80 \
  --out client/aiter/tune_out/dispatch-my-run
```

规划器只用 Python 标准库，不导入 torch/aiter，不启动 Docker、JIT、汇编器或 GPU。
默认扫描 BF16、A8W8 preshuffle、blockscale、blockscale preshuffle 和 MoE；可重复 `--family` 缩小范围。
数据来源按以下规则选择：

1. 显式 `--config FAMILY=PATH[:PATH]`。
2. 当前环境对应的 `AITER_CONFIG_*` 变量；注意在本地生成计划不会自动读取远端环境变量。
3. 固定 aiter 的默认 CSV，加匹配的 `aiter/configs/model_configs/*tuned*.csv`。

例如，仅使用一个指定部署配置：

```bash
python3 client/aiter/dispatch.py plan --cu 80 --family a8w8 \
  --config a8w8=client/aiter/upstream/aiter/configs/a8w8_bpreshuffle_tuned_gemm.csv \
  --out client/aiter/tune_out/dispatch-explicit-config
```

规划器保存源文件散列、行号和原始字段，按 gfx/CU 过滤后导出独立 CSV 快照。运行时显式使用这份
**限定架构和 CU 的配置覆盖**；这不等于声称目标进程继承的所有默认配置都已验证。旧表缺少 gfx 时仅使用
上游已知 CU 映射；未知 CU 不猜架构。空 gfx、其他设备记录和缺失依赖都有可见诊断。

上游 `AITER_CONFIGS` 合并重复记录时可能改写输入 CSV 再报错。因此本工具只读原文件；选定 family 的
dispatch key 有冲突时禁止为该 family 导出可运行任务，不按最后一行或最小 `us` 静默选赢家。
通过显式选择与实际部署相符的配置来源解决冲突，再生成新计划。不要为了得到更多任务而随意排除配置。

## 2. 正查与反查

`plan.json` 包含：

| 字段 | 内容 |
|---|---|
| `families` | 来源模式、源文件 SHA、过滤数量和冲突数量 |
| `references` | 原始行、有效行、backend、symbol、catalog/.co、状态及原因 |
| `co_to_workloads` | `.co` 到所有关联 workload ID；不只保留一个 MNK |
| `tasks` | 可验证 workload 的 manifest 和 prepare/validate/tune_init/compare 命令数组 |
| `unreferenced_co` | 在所选来源与设备范围中未找到引用的 catalog `.co`；不表示 kernel 无用 |

任务 ID 包含完整配置行、来源/快照、入口及具体测试输入。adapter 补全的 dtype、scale、bias、shuffle
和行 padding 也写入 manifest。INT8 表的 key 未包含全部测试输入字段，因此结果仅覆盖这些明确声明的输入契约。

```bash
python3 client/aiter/dispatch.py lookup \
  client/aiter/tune_out/dispatch-my-run/plan.json \
  --co i8gemm/I8gemm_bf16_perTokenI8_BpreShuffle_32x128.co
```

`other_backend`（如 CK/CKTile/HIPBLASLt/OPUS/Triton/FlyDSL）保留来源，不能伪造成 HSA 调优任务。
`unmapped`、`ambiguous_catalog`、`missing_co`、`config_conflict` 和 `unsupported_adapter` 分别记录原因。
`ready_for_validation` 仅代表可以开始验证，**不代表 seed 已通过或 kernel 已调优**。

当前可导出执行任务的 adapter 范围：

- INT8 per-token ASM，BF16 输出、FP32 scales/bias、preshuffle、splitK=1，N 为 256 的倍数、K 为 128 的倍数。
- BF16 TN ASM，BF16 输出、无 bias/scaleAB、splitK=1，N 为 64 的倍数、K 为 128 的倍数，layout 与 catalog 一致。
- FP8 blockscale preshuffle ASM，gfx942 FP8 输入、BF16 输出、无 bias、splitK=1，N/K 为 128 的倍数。
  仅支持已审核的 tile M=32/48/64/80/96/128、tile N=128 对象。FP32 A scales 按 1×128、B scales 按
  128×128 分块；A scale 的连续存储是逻辑 `(M,K/128)` 的转置字节再 view 回原形状，B scale 为行主序。
  B 使用 `(16,16)` shuffle，A 不补行尾 padding。上述选择全部写入 `inputs`，不使用 MX scales 或普通 blockscale 入口。
- CSV 已报告非零或非有限误差的行不能直接导出；先调查原始 kernel 的数值问题。

其他 GEMM/splitK/layout 需要匹配的 driver，不能把 splitK 改成 1 或缩小 MNK 来强行接入。
MoE 保留两个 stage、token/expert/topk/activation/量化及 routing 相关字段；目前作为待适配清单。
MLA 的 `mla_asm.csv` 是 kernel 属性目录，不含完整 batch/KV 分布，记录在 `unreferenced_co` 中待补显式 workload。
这里不把目录条目伪装成可以运行的 MLA 测例。

## 3. 在目标机器验证与调优

可将仓库和新计划一起复制到目标 checkout；计划中的 manifest/driver/快照路径可随仓库迁移。
固定源码、原始 `.co`、catalog 和快照的散列必须匹配。源码更新后重新审核、生成计划，不手改散列绕过检查。
blockscale plan 还在 binding 中保存 `adapter_sha256` 与 `validation_sha256`，分别冻结本地 adapter 链和
上游测试、benchmark、dtype/shuffle、CK/ASM/Triton 实现；加载 manifest 时即检查。所有资源也进入 client
fingerprint。扩展 adapter 后应生成新目录，不修改正在运行的冻结 plan。
`tasks[].commands` 是从仓库根执行的 argv 数组；将 `CANDIDATE.s` 替换成确定的候选文件。
引擎使用 `python3.8`（没有时用 `python3`）；runner 通过 `--python` 选择已验证 ROCm Python。

以下 `WORKLOAD_ID` 使用 `plan.json` 中对应任务的 ID：

```bash
AIT_PLAN=client/aiter/tune_out/dispatch-my-run
AIT_TASK=WORKLOAD_ID

docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/prepare.py gfx942 \
  --manifest "$AIT_PLAN/$AIT_TASK.json" --out "$AIT_PLAN/$AIT_TASK.s"

docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 tools/eval_candidate.py \
  "$AIT_PLAN/$AIT_TASK.s" --client aiter/hsa/gfx942 -- \
  --manifest "$AIT_PLAN/$AIT_TASK.json" --python /opt/venv/bin/python3 \
  --warmup 20 --iters 100 --samples 7
```

CSV-bound manifest 会拒绝改变 `--m/--n/--k`。driver 也不能换成默认 blockscale 的 `optest_manifest.json`。
每个 candidate 使用新 runner，并按顺序执行：

1. 校验实际 gfx/CU；在导入 aiter 前配置独立的 CSV 副本。
2. 用正常入口 `aiter.gemm_a8w8_ASM`、`aiter.tuned_gemm.gemm_a16w16` 或
   `aiter.ops.gemm_op_a8w8.gemm_a8w8_blockscale_bpreshuffle` 选择 kernel。
   观察入口传给 ASM 的 symbol/splitK/layout；不在这个检查中强制替换选中值。不同选择直接失败。
3. 校验正常入口的完整输出，确认 host `LoadKernel` 指向当前 candidate overlay。
4. 复用 reviewed driver：两组独立数值参考、上游单目标 op_test、HIP graph 计时和计时后完整输出检查。
   blockscale 复用 `driver.py` 的共享输入和 `optest_driver.py` 的完整验证，正常入口自行分配零 bias，
   不注入固定目标运行的 `zero_bias_buf`。op_test 保持 constant/constant 与 uniform/auto 两组分布，
   检查 CK、strided CK、目标 ASM 和 Triton 的完整输出，沿用已审核 CK 默认分支与 symbol 绑定。

`result.json.dispatch_check` 记录入口、workload ID、CU、快照 SHA 和观察到的选择。
这是正常入口与 host loader 的证据，仍不等于 GPU ATT；性能报告测的是选定 ASM 算子，不含 Python dispatch 开销。
BF16/INT8 op_test 是锁定上游文件中的单目标 benchmark wrapper；blockscale 调用锁定文件的单 shape
`test_gemm` 多 backend 验证，不执行 CLI 或其他 shape 的 split-K 扫描。

original 验证通过后，用任务的 `tune_init` 命令接入 `tools/tune_run.py`，再按现有调优流程执行。
MFMA 调度继续读取 `selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/`，不重跑自学。
新计划独立按 workload ID 管理；**不要直接喂给按 `.co` 去重的旧 `campaign_runner.py`**，否则同 `.co` 的第二个尺寸可能被跳过。

## 4. 固定候选，逐尺寸对比和汇总

对同一个 `.co` 的全部关联尺寸使用同一份 candidate；每个尺寸保持原 manifest 和对应 baseline。
在筛选前约定配对次数、收益门槛、显著性水平及容许回退，避免测完再挑门槛。例：

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/compare.py \
  "$AIT_PLAN/$AIT_TASK.s" client/aiter/tune_out/candidate.s \
  --client aiter/hsa/gfx942 --pairs 6 --min-gain 0.01 --alpha 0.05 -- \
  --manifest "$AIT_PLAN/$AIT_TASK.json" --python /opt/venv/bin/python3 \
  --warmup 20 --iters 100 --samples 7
```

保留命令输出的 `comparison.json` 路径，并为其余关联尺寸重复对比。只读汇总命令：

```bash
python3 client/aiter/dispatch.py assess "$AIT_PLAN/plan.json" \
  --co i8gemm/I8gemm_bf16_perTokenI8_BpreShuffle_32x128.co \
  --max-regression 0.01 \
  --comparison client/aiter/tune_out/comparisons/paired-FIRST/comparison.json \
  --comparison client/aiter/tune_out/comparisons/paired-SECOND/comparison.json
```

`assess` 校验 workload/manifest、原始与候选源码摘要、设备/环境、数值/op_test 证据，并从配对记录重新计算结果。
每种计时的速度比下界需至少达到 `1/(1+max_regression)`。报告分开列出 `pass`、`regression`、`inconclusive`、
`pending` 和 `unsupported`；任何未覆盖行都阻止 `all_referenced_workloads_pass`。
这些是逐 workload 的区间；要控制整组多重比较的错误率，应事先分配各测试的 alpha 和足够样本数。
汇总通过说明本计划范围内未发现超过门槛的回退；是否有值得采用的收益仍看各 `compare` 的收益检验结果。

不要平均掉回退，不把 `.co` 的完成状态用于跳过其他尺寸，不将一组尺寸的结论推广到 padding/heuristic 的所有输入。
目前只枚举 CSV 精确行；M padding、MoE token-tier fallback 和 MLA 启发式的覆盖要另列实际 workload 及验证记录。

## 本次实现验证的边界

2026-10-15 在固定上游版本和 gfx942/80 CU 条件下，CPU 扫描得到 4964 条 stage/reference、42 个关联 `.co`，
可导出 22 个 INT8 workload，涉及 6 个 `.co`。例如 `I8gemm_bf16_perTokenI8_BpreShuffle_32x128.co` 的
M/N/K=192/1280/1024 和 192/1536/1024 都保留，splitK 均为 1；192/128/5120 的 splitK=8 行保留为待调查，
没有改尺寸或把原始 CSV 非零误差当成通过。新派发检查已做 CPU 协议测试，尚未在 GPU 上实测；本次不产生新的性能收益结论。

blockscale preshuffle 扩展另以 CPU 协议检查上游真实公开函数的 ASM 分支、完整输入转发、正常零 bias
分配、错选/回退/异常恢复及源码漂移拒绝。它复用已有数值验证，并不证明新 CSV workload 的 seed 已通过；
新 manifest 仍须在目标机器逐 workload 验证原版。
