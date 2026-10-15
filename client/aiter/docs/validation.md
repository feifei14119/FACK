# 在新环境复现 aiter gfx942 验证

命令从目标机器的 FACK 仓库根执行。使用宿主机 Python 3.8 或更新版本；不要假定 `python3` 已满足最低版本。
容器使用自己的 Python。所有产物位于 `client/aiter/tune_out/`，新 clone 不需要历史产物。

MLA stage1 的明确分页、物理 KV 存储和单目标 op_test 步骤见
[MLA 专用验证](mla-stage1-validation.md)。

```bash
AIT_HOST_PY=python3
if command -v python3.8 >/dev/null 2>&1; then AIT_HOST_PY=python3.8; fi
"$AIT_HOST_PY" -c 'import sys; assert sys.version_info >= (3, 8), "Host Python >= 3.8 required"'
```

## 1. 准备固定依赖

检查 `git status --short` 和 `git submodule status`。依赖缺失时运行：

```bash
bash tools/init_aiter.sh
bash tools/init_selfstudy.sh
```

按 gitlink 初始化，不执行 `--remote`，不运行自学流程。部署前应包含 `tools/co2s.py` 的 XNACK/SGPR 回编修复及
`tools/eval_candidate.py` 的失败退出码修复（2026-10-14 已纳入 FACK）。

## 2. 选择环境并启动容器

已验证配置在 `client/aiter/env/gfx942.json`：固定 aiter 提交、镜像仓库 digest、容器解释器及依赖检查。
镜像 digest 是可向仓库请求的引用；本地 image ID 只用于本机固定运行，不能代替可拉取引用。
首次下载镜像时需要对应 registry 的网络与访问权限。工具不会自动安装包、升级依赖或拉取镜像。

```bash
AIT_IMAGE=$("$AIT_HOST_PY" -c 'import json; print(json.load(open("client/aiter/env/gfx942.json"))["image"])')
docker image inspect "$AIT_IMAGE"
# 仅当本地不存在且需要该镜像时执行：
# docker pull "$AIT_IMAGE"

"$AIT_HOST_PY" client/aiter/docker_env.py inventory
AIT_RUN="smoke-$(date +%Y%m%dT%H%M%S)"
AIT_CONTAINER="fack-aiter-$AIT_RUN"
"$AIT_HOST_PY" client/aiter/docker_env.py start --gpu second-last --name "$AIT_CONTAINER"
```

`second-last` 按宿主机 rocm-smi 编号排序，选择 gfx942 设备中的倒数第二张；也可传物理编号、PCI 地址或 GPU UUID。
`start` 的成功条件是：容器内 ROCm PyTorch 只看到一张卡，架构和 PCI 地址与选择结果一致，依赖与工具齐全。
宿主机已有 `HIP_VISIBLE_DEVICES` 等限制时明确报错；先确认它们对应的任务范围，不机械清除限制。

工具挂载当前 checkout 到容器 `/workspace/FACK`，使用调用者 UID/GID 和设备组，将缓存写入本次输出目录。
同时传入实际用户名并显式设置 Inductor/Triton 缓存，避免镜像无此 UID 的 passwd 条目时 PyTorch 查询用户名失败。
client 同时设置 `AITER_JIT_DIR` 与 `AITER_ROOT_DIR`；上游的两套编译缓存各自使用不同变量，漏设后者会尝试写入不可写的 `~/.aiter`。
仓库路径可以包含空格；Docker `--mount` 不支持的逗号/换行路径会明确拒绝。
所有启动参数、实际 image ID、RepoDigests、设备清单和检查结果保存在
`client/aiter/tune_out/environments/<容器名>/`。启动失败时只停止本工具刚创建的容器并保留诊断。

使用其他已存在的兼容镜像可传 `--image ... --python ...`。检查配置的最低版本只针对记录中的 aiter 提交；
更换上游版本时先复核 `doctor.py`、环境配置和 op_test 适配。可手工重跑环境检查：

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/doctor.py
```

doctor 会导入 torch、读取设备属性，不执行 kernel 或 aiter JIT。默认已验证环境为 PyTorch 2.10 / Triton 3.7；
只有 PyTorch 而没有匹配的 Triton/JIT 依赖不够。不要在运行时随意 `pip install torch` 覆盖 ROCm 版本。

## 3. 验证原始 seed

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/prepare.py gfx942 \
  --exact --out "client/aiter/tune_out/$AIT_RUN/seed.s"

docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 tools/eval_candidate.py \
  "client/aiter/tune_out/$AIT_RUN/seed.s" --client aiter/hsa/gfx942 -- \
  --python /opt/venv/bin/python3 --m 256 --n 256 --k 1024 \
  --warmup 20 --iters 100 --samples 7 --seed 123
```

回编的 .text、KD、metadata/target 必须通过检查，随后要求 `assembled=True`、`correct=True` 和有效时间。
`--exact` 对此已验证 .co 要求字节相同；其他种子按 prepare 的默认等价性规则处理并如实记录。
不要手改 target、KD 或降低容差来绕过失败。首次运行会触发 JIT，编译与输入准备不计入 GPU 时间。

只验证接入时可进入下一步；需要调优时用 `tools/tune_run.py init/eval/prepare/confirm/final`，仍传
`--client aiter/hsa/gfx942 -- ...`。命令和冻结策略见 `client/README.md`，不要复制历史 run-id。

## 4. 运行指定 .co 对应的上游 op_test

下面是默认 FP8 blockscale 示例。按 dispatch CSV 生成的任务请使用其原 manifest，已经开启相应 GEMM
op_test 和正常入口选择检查；不要替换成这里的默认 manifest。完整流程见 [按 CSV 选择 workload](dispatch-workloads.md)。

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 tools/eval_candidate.py \
  "client/aiter/tune_out/$AIT_RUN/seed.s" --client aiter/hsa/gfx942 -- \
  --manifest client/aiter/hsa/gfx942/optest_manifest.json \
  --python /opt/venv/bin/python3 --m 256 --n 256 --k 1024 \
  --warmup 20 --iters 100 --samples 7 --seed 987
```

替换输入 `.s` 即可验证候选。seed=987 演示任意 seed 都会执行验证；不存在 seed 哨兵。
manifest 显式启用 `driver.validate(inputs, symbol, seed)`，每次 evaluator 在两组基本数值检查之后、
HIP graph 预热和计时之前调用一次。结果写入该次 `eval-*/result.json` 的 `op_test`，错误会让 evaluator/CLI 失败。

当前 blockscale adapter 支持 gfx942 catalog 的 `fp8gemm_bf16_blockscale_BpreShuffle_<M>x128.co`，
其中 tile M 为 32、48、64、80、96、128，固定 splitK=1。默认示例 manifest 仍选择 32x128。
它调用固定上游 `op_tests/test_gemm_a8w8_blockscale.py` 的 `test_gemm`，覆盖 constant/constant 与 uniform/auto，
包含 CK、strided CK、ASM、Triton 完整输出对比；不执行文件末尾其他 shape 的 split-K 扫描。
CK 比较显式调用固定 SHA 审核的 C++ 默认分支（`kernelName=""`），避免合并的调优 CSV 指向未编入
registry 的内核；该选择及实现 SHA 写入 `op_test.ck_dispatch`。不改上游代码或 CSV，目标 ASM 仍固定到 manifest symbol。

这是版本限定的适配：先核验测试文件 SHA，再通过 AST 截取 CLI 前的定义。上游 `run_asm` 当前不透传
`kernel_name`，adapter 临时绑定所选 symbol/splitK，并在失败时恢复调用；不得用自动选核代替目标候选。
runner 统一设置 HSA overlay、修正导入后的 `AITER_ASM_DIR`，并核验 LoadKernel 路径。无需复制上游包或覆盖上游 .co。

## 5. 对两个确定的候选进行配对比较

指定已经准备好的候选路径：

```bash
AIT_CANDIDATE="client/aiter/tune_out/$AIT_RUN/candidate.s"
# 调优应已生成上述 candidate.s；仅做流程自检可把 AIT_CANDIDATE 设为同一个 seed.s。
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/compare.py \
  "client/aiter/tune_out/$AIT_RUN/seed.s" "$AIT_CANDIDATE" \
  --client aiter/hsa/gfx942 --pairs 6 --min-gain 0.01 --alpha 0.05 -- \
  --manifest client/aiter/hsa/gfx942/optest_manifest.json \
  --python /opt/venv/bin/python3 --m 256 --n 256 --k 1024 \
  --warmup 20 --iters 100 --samples 7 --seed 987
```

6 对、1% 门槛和 alpha=0.05 是可执行的流程示例，不是经硬件校准的最佳采样配置；正式测量按 workload 事先选择。
比较采用固定偶数对，AB/BA 数量相同，每侧都是新的 evaluator/runner。脚本快照两份汇编并冻结 client 契约；
构建、数值、资源漂移、设备变化或 op_test 失败时立即停止，保留已完成及失败记录，不重试覆盖错误。

结果写入新建的 `client/aiter/tune_out/comparisons/paired-*/comparison.json`。每次 client 的 work_dir 来自其返回值，
不靠扫描“最新目录”猜测。中断后保留部分记录；重新比较会创建新目录。

`hip_graph` 与每个 `op_test:<数据>/<scale>` 分别调用现有 `harness/comparison.py` 的配对符号检验。
它们的缓存和计时方式不同，不混在一个总体分数里；结果不一致时报告分歧，脚本不自动采用候选。
这里比较已经确定的两份代码；大批筛选及多候选确认继续由 `tools/tune_run.py` 管理预算和确认规则。

## 6. 结束与故障定位

```bash
"$AIT_HOST_PY" client/aiter/docker_env.py stop "$AIT_CONTAINER"
```

stop 只接受本工具为当前 checkout 创建的容器。保留容器以便检查；需要删除时明确指定本次容器名，不批量删除。

| 现象 | 检查位置与处理 |
|---|---|
| 镜像不存在 | 核对 profile 的 repository digest，准备镜像；本地 image ID 不能用于跨机器拉取 |
| 权限或缓存写入失败 | 核对挂载目录所有者、设备组、输出目录；不要递归修改整个仓库权限 |
| torch/triton 导入失败 | `environments/<name>/doctor.*`；选匹配镜像，依照固定上游依赖准备环境 |
| GPU 不符或数量不是 1 | 比较 inventory、UUID、容器 PCI，检查已有可见设备限制 |
| XNACK/SGPR 回编失败 | 检查 FACK 是否包含已验证转换修复、实际 LLVM 版本；保留原始 .co 和失败日志 |
| JIT/数值/装载失败 | client 返回的 `detail.work_dir` 下 `build.log`、`runner.log`、`result.json`；CLI 必须非零退出 |
| op_test SHA 不符 | 上游结构已变，复核 driver 的导入边界与 symbol API；不能只换散列 |
| 有表观收益但确认不通过 | 保留基线，保留全部配对样本，不根据单次最快样本扩展结论 |

实际重排结果见 [历史调优记录](validated-runs/20261014.md)，正式脚本的新 checkout 验证见
[迁移验证记录](validated-runs/20261014-portability.md)。所有新运行结果继续写 `tune_out/`；
经审核的环境/接口变化才更新脚本、profile 和操作 skill，不写入调度先验 `knowledge/engine/skills/`。
