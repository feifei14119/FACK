# 在新环境验证 gfx942 MLA stage1

先按 [环境步骤](validation.md) 初始化固定依赖、选择 GPU、启动容器并通过 doctor。
以下命令从 FACK 根目录执行，沿用该步骤的 `AIT_CONTAINER` 和 `AIT_HOST_PY`。宿主机 Python 至少为 3.8；
容器解释器为 `/opt/venv/bin/python3`。所有输出放在新的 `client/aiter/tune_out/` 子目录。

当前固定 aiter 提交为 `2abf8aaa44f9d81c88d6153024b21e6931c7f906`。这五个输入契约已核查
原生汇编的分页、输出类型和固定 workload 下的内存边界：

| `.co` | 输入 / heads | page_size | KV 物理尾部 | split1 输出 |
|---|---|---:|---:|---|
| `mla/mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co` | FP8 / 8 | 1 | 32 字节，初始化为零 | BF16 |
| `mla/mla_a8w8_qh16_qseqlen1_gqaratio16.co` | FP8 / 16 | 1 | 0 字节 | BF16 |
| `mla/mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co` | BF16 / 8 | 1 | 0 字节 | FP32 |
| `mla/mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co` | BF16 / 16 | 1 | 0 字节 | FP32 |
| `mla/mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co` | BF16 / 128 | 1 | 0 字节 | BF16 |

共同 workload 为 batch384、逻辑 KV1024、qseq1、Q/K 维度576、V 维度512、split1，
grid `(1,384,1)`、block `(256,1,1)`。新环境仍须先验证真正原版。
其他 `.co` 的分页、padding 和顺序证明需要单独核查，计划生成器会把未审查目标列入待适配清单。

## 生成一个明确的输入契约

此例选择 FP8 QH8。验证表中其他对象时，替换 `AIT_MLA_CO` 为完整文件名；生成器保留正确的类型和存储要求。
FP8 QH16 输出 BF16；BF16 QH8 和 BF16 QH16 输出 FP32，并保留下文的 scratch-LSE 使用范围。
使用新的输出目录，保留每次失败尝试。

```bash
AIT_MLA_OUT="client/aiter/tune_out/mla-check-$(date +%Y%m%dT%H%M%S)"
AIT_MLA_CO="mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co"
"$AIT_HOST_PY" - "$AIT_MLA_OUT" "$AIT_MLA_CO" <<'PY'
import csv
import json
import sys
from pathlib import Path
from client.aiter.campaign_future_plan import reviewed_mla_manifest

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
catalog = Path('client/aiter/upstream/hsa/gfx942/mla/mla_asm.csv')
with catalog.open() as stream:
    row = next(r for r in csv.DictReader(stream) if r['co_name'] == sys.argv[2])
manifest = reviewed_mla_manifest(row, out)
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(out / 'manifest.json')
PY

docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/prepare.py gfx942 \
  --manifest "$AIT_MLA_OUT/manifest.json" --exact --out "$AIT_MLA_OUT/seed.s"
```

检查 `seed.s.json` 中的原始 `.co`、manifest、汇编 SHA 以及 `exact=true`。
这一步只证明回编身份，尚未证明数值正确。SGPR 声明应使用真实寄存器 footprint，
由 `co2s.py` 和完整 KD roundtrip 决定，不手工套用“分配量减四”等公式。

## 先验证原版，再运行候选

下面的函数在第一次失败时返回非零并停止剩余验证。每次 evaluator 自动使用独立目录，
并进行两个输入 seed、计时后的完整输出和单目标 op_test 检查。

```bash
aiter_mla_validate_original() {
  for AIT_MLA_REPEAT in 0 1 2; do
    docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 tools/eval_candidate.py \
      "$AIT_MLA_OUT/seed.s" --client aiter/hsa/gfx942 -- \
      --manifest "$AIT_MLA_OUT/manifest.json" --python /opt/venv/bin/python3 \
      --m 384 --n 1024 --k 576 --seed 61024 \
      --warmup 20 --iters 100 --samples 7 --timeout 1800 \
      --output-dir "$AIT_MLA_OUT/evaluations" \
      > "$AIT_MLA_OUT/original-$AIT_MLA_REPEAT.log" 2>&1 || return "$?"
  done
}
aiter_mla_validate_original
```

只有三次都通过，才进入已完成顺序/访存核查的候选验证。失败时保留 log 和 evaluator 返回的
`detail.work_dir`，先定位构建、运行时、数值或契约错误，不降低容差。修改 driver、manifest 或
存储契约后使用新目录重新验证原版；此前计时不能混入新契约的筛选或最终比较。

结果必须包含 `correct=true`、有效时间、目标 symbol/装载路径及 `op_test.correct=true`。
`op_test.stage1_binding` 记录固定源、真实配置 CSV、库 SHA 和原始 26 参数签名；
`op_test.kv_storage` 记录逻辑 shape、byte stride、物理存储长度、offset 和 padding。
FP8 QH8 的逻辑/物理 KV 长度分别为 226492416/226492448 字节；
FP8 QH16 均为 226492416 字节。BF16 QH8、BF16 QH16 和 BF16 QH128 的逻辑和物理 KV
均为 452984832 字节。BF16 QH8 与 BF16 QH16 主输出分别为 `[384,8,512]`、`[384,16,512]` 的 FP32 tensor。

这里的 op_test 使用固定 `op_tests/test_mla.py` 的 `torch_mla_extend` /
`ref_masked_attention` 及独立 FP32 参考，验证唯一 catalog tuple 的低层 stage1。
它不覆盖完整高层 MLA、persistent、其他 split 或全部 shape。host loader 记录也不是 GPU dispatch attestation。

选定候选后，设置 `AIT_MLA_CANDIDATE` 为容器内仓库相对 `.s` 路径，执行新的独立配对：

```bash
docker exec "$AIT_CONTAINER" /opt/venv/bin/python3 client/aiter/compare.py \
  "$AIT_MLA_OUT/seed.s" "$AIT_MLA_CANDIDATE" \
  --client aiter/hsa/gfx942 --pairs 8 --min-gain 0.01 --alpha 0.05 --loop 20 -- \
  --manifest "$AIT_MLA_OUT/manifest.json" --python /opt/venv/bin/python3 \
  --m 384 --n 1024 --k 576 --seed 61024 \
  --warmup 20 --iters 100 --samples 7 --timeout 1800 \
  --output-dir "$AIT_MLA_OUT/evaluations"
```

性能基线始终为真正原版。筛选样本和加强等待控制实验的样本不进入最终八对。
完整正确性、候选顺序证明、冻结身份与两种计时方法都满足采用要求后才能采用；
不足 1% 的差异按预先声明的策略保留原版。BF16 QH128 原版的首循环 `v11` 等待义务和
`vmcnt(19)→vmcnt(18)` 控制证明仍是单独的调度条件，输入内存有界不代替该证明。
FP8 QH16 的原版在该固定输入下已通过三次完整真机验证，但保守 LDS 模型仍有同 wave 和
跨 wave 的排序义务。该次控制加强四处 `lgkmcnt(4)→lgkmcnt(2)` 并在四处已有
`lgkmcnt(0)` 后增加 barrier；动态四 wave 必须在相同 ordinal 会合。
不要把这类源码位置相关的补丁自动套用到其他 `.co`，也不要把模型义务直接报告为已发生的数值错误。

BF16 QH8 和 BF16 QH16 的 scratch-LSE 分别是独立的 12288、24576 字节分配，四个 wave 会写入相同位置。
BF16 QH8 在末尾缩小 EXEC 至低 8 lane；BF16 QH16 保持完整 EXEC，每个 wave 的 16 lane 写入有效，
另外 48 lane 的 store 由每 batch 64 字节的 buffer descriptor 抑制。
已分别核查这两个固定 kernel 只有最后的 LSE store，之后为 wait/end，整个 kernel 无 LSE payload load；
当前 driver 及其重复 launch、参考计算也不消费这段数据，只返回独立的 FP32 主输出。
这限定了本次单目标 adapter 的验证范围，未证明四 wave 写值相等，也未声明 scratch 写入无 race。
生成的 manifest 以 `native_scratch_lse` 保留这项限制；不能据此接入会读取该 scratch 的高层 MLA 流程。
BF16 QH16 原版也已通过三次完整真机验证。两个对象各自的四处 `lgkmcnt(8)→lgkmcnt(4)` 控制
由独立地址和排序证明支持，不需要照搬 FP8 QH16 的新增 barrier；输入或源码改变后须重新核查。

## 已定位问题及复用边界

- **稀疏检出导致 JIT schema 缺列。** 原 codegen 跨架构收集 CSV 的列，再只生成目标架构的行。
  driver 使用 `mla_codegen_metadata/` 中从同一固定提交导出的四份原始 CSV，逐项检查 SHA，
  在外置缓存运行完全相同的生成器并编译原 C++。这些配套文件需随 adapter 一起部署。
  缺文件或哈希变化应修复依赖；不要补虚构配置。
- **page16 只计算每页首 token。** 这五个 native kernel 将 log2(page_size) 强制置零。
  修正为 page1 保持逻辑输入值不变，但实际循环次数改变，已有 page16 顺序证书不能直接沿用。
- **FP8 QH8 最后一个 token 后的 32 字节 overfetch。** 完整地址枚举和故障 core 确认边界，
  extra lanes 只进入未使用的累加器。driver 以具有零初始化物理尾部的 contiguous view 承载原逻辑 KV；
  不增加有效 token。BF16 QH8、BF16 QH16 和 BF16 QH128 均经各自独立检查，无需该 padding。
- **已有导出只提供局部调度估计。** 使用 `selfstudy/gfx942/` 的固定导出提出候选；
  全局边界、循环入口/稳态、依赖和完整数值要分别验证。`search.driver.build_candidate` 会重算 wait，
  不能直接套用要求所有非 MFMA 指令不变的外置证书。此文档不放宽 runtime gate。

阶段状态、独立报告和最终未完成清单的约定见 [campaign.md](campaign.md)。
