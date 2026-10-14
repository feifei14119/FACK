# 2026-10-14：正式入口的迁移验证

已在独立 clone 和新容器中完成单算子验证。该次运行验证环境脚本、op_test driver 和比较入口，
两侧使用同一个 seed，不产生调优收益结论。完整样本、依赖版本、运行参数和代码散列见
[20261014-portability.json](20261014-portability.json)；早先实际重排的结果见 [历史调优记录](20261014.md)。

## 验证环境

- 机器仍为 `hjbog-srdc-39`，选择 8 张 gfx942 中倒数第二张：物理 GPU 6，PCI `0001:a5:00.0`，
  UUID `GPU-460ffdd2f4d1f04a`。容器只见一张 GPU，doctor 核验 PCI 和架构一致。
- checkout 使用包含空格的路径 `.../portability-20261014/checkout with spaces`，容器挂载为 `/workspace/FACK`。
  从基础提交 `2734e37435f25fc9b489779703b7e7c6facf8720` 建立 clone 后应用本次改动。
  固定 submodule 使用已有本地 Git 仓库传输，工作区独立；没有复制旧 `tune_out/` 或 JIT 缓存。
- 宿主机使用 Python 3.8.17；默认 `python3` 是 3.6，因此操作步骤显式选择并检查宿主解释器。
- 镜像使用 `env/gfx942.json` 的 repository digest，本地固定 image ID 启动。
  容器 Python 3.12.3、PyTorch `2.10.0+rocm7.2.4.git3d3aa833`、Triton 3.7.0、HIP 7.2.53211。
- 容器按宿主机 UID/GID 10708 运行。所有保留的输出文件都属于该 UID；aiter 和 selfstudy 工作区保持干净。

## 实际修复的迁移问题

1. 镜像中没有 UID 10708 的 passwd 条目。PyTorch 导入 Dynamo 时查询默认 Inductor 缓存，用户名查询失败。
   启动脚本传入宿主实际 `USER`/`LOGNAME` 和显式 Inductor 缓存目录；doctor 增加 Dynamo 导入检查。
2. aiter 的 `cpp_itfs` 不使用 `AITER_JIT_DIR`，仍尝试创建 `//.aiter`。
   client 为其额外设置 `AITER_ROOT_DIR`，放在已隔离的 JIT 输出目录中，不修改 HOME 或上游代码。

两次失败各保留一条失败评估记录，比较立即非零退出。修复后新建比较目录完成验证，未覆盖失败记录。

## 正确性和计时

重新从固定上游 `.co` 导出 seed，严格回编通过：5984 字节 `.text`、KD（排除链接入口偏移）、metadata 和 ELF flags 一致。
比较采用 `--client aiter/hsa/gfx942`、`optest_manifest.json`，M=N=256、K=1024、splitK=1，
`--seed 987 --warmup 5 --iters 20 --samples 3`。固定 6 对，AB/BA 各 3 对，收益门槛 1%，单侧 alpha=0.05。

- 12 次编译与 client 评估全部通过，12 次均核验目标 symbol/.co 装载日志。
- 36 项基本完整输出检查通过：每次两个随机输入，再检查计时后 graph replay 的输出。
- 24 行 op_test 结果，包含 constant/constant 和 uniform/auto。
  CK、strided CK、ASM、Triton 共 96 项完整输出比较均通过，其中 ASM 24 项；错误率全部为 0。

| 计时方式 | 第一份 seed 中位数 µs | 同一份 seed 再测中位数 µs | 配对判定 |
|---|---:|---:|---|
| HIP graph | 7.3580 | 7.3590 | inconclusive |
| op_test constant/constant | 7.0876 | 7.0975 | inconclusive |
| op_test uniform/auto | 7.0821 | 7.0925 | inconclusive |

三个指标都没有确认收益或回退，符合本次同代码流程自检的预期。op_test 的 profiler/轮换输入计时与
固定输入 HIP graph 分开分析；本次缩短了 graph 参数，不拿绝对时间与历史运行直接比较。
一次同代码比较不能证明测量系统在所有条件下无偏，也不校准未来调优的统计假设。

## 工程检查与保留产物

CPU 全量测试 `python3 -m pytest -q unittests`：658 passed、19 subtests passed（79.16 秒）。
skill 校验、Python 3.8 语法检查和 diff 空白检查通过。远端实际执行的 10 个 runtime/config 文件散列与本地一致。
本次创建的两个容器均已停止，Docker inspect 状态为 `exited`；日志和候选 overlay 保留。

原始比较位于独立 checkout 下 `client/aiter/tune_out/comparisons/paired-40jodnsw/comparison.json`，
完整采集记录位于 `client/aiter/tune_out/portable-smoke/migration-evidence.json`。
这些目录只用于追溯；后续 clone 可用随仓库保存的脚本、profile 和本目录精简证据复现流程。

本次验证覆盖同一台真机、同一镜像的新 checkout 和新容器；未验证另一台机器或重新从 registry 下载镜像。
新环境仍需运行 doctor 和 seed 验证，不能把历史结果直接视为本机通过。
