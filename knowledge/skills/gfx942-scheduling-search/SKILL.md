---
name: gfx942-scheduling-search
description: 在 FACK 中使用 gfx942 候选生成器搜索完整 SALU 链、MFMA 间隙和重复阶段访存调度，检查来源与组合合法性。适用于任意 client 的 gfx942 汇编调度，不负责 workload 或项目验证协议。
---

# gfx942 候选搜索

命令在 FACK 根执行。`python3 tools/tune_run.py suggest RUN --n 6` 会按冻结的搜索策略生成候选，
返回当前 observation、spec、hypothesis、provider、分组 details 和构造后的 candidate_sha256。
将返回的完整 spec / hypothesis 保存到本次输出目录，再交给 `prepare`；不复制旧实验的指令编号。

默认同时启用通用局部移动与以下架构生成器：

| provider | 搜索内容 |
|---|---|
| `gfx942_salu_chains` | 识别连续 SALU 中的 RAW/SCC 依赖分组，将完整链向前移动 1–3 个 MFMA 间隙 |
| `gfx942_repeated_salu_chains` | 在栅栏分隔、MFMA 数量与局部位置匹配的阶段中重复移动标量链，或将拥挤处前 2–3 条链分散到不同间隙 |
| `gfx942_repeated_operand_prefetch` | 在匹配阶段中将操作数加载单元提前 1–2 个间隙；m0 bundle 由引擎整体移动 |

这些是结构化搜索假设，不是周期预测或收益保证。依赖链识别限于连续 SALU 区间；
区间外的依赖仍由引擎检查。不同阶段按当前 opcode、局部间隙和出现顺序匹配，不要求寄存器号相同。
整组任一成员无法放置时，候选不通过；不悄悄只保留成功移动的部分。

`--search-policy FILE` 可以选择生成器和单次 suggest 的 CPU 尝试上限，例如：

```json
{
  "candidate_providers": ["generic", "gfx942_repeated_salu_chains", "gfx942_salu_chains", "gfx942_repeated_operand_prefetch"],
  "candidate_attempt_limit": 96
}
```

省略列表时在 init 按实际 ISA 展开并冻结。未知生成器报错；其他架构不会回退到 gfx942。
尝试上限约束候选提案验证次数，不代表 GPU 预算或穷举范围。最多检查 12 条指令的标量链、
12 个匹配阶段、每候选 96 条指令。列表顺序影响轮流枚举的起点，不保证输出每一种方向。

先用少量不同机制的候选检查方向，再根据当前 workload 的确认结果细化。结合
`knowledge/skills/mfma-interleave-gfx942/SKILL.md` 查询实际指令窗口，区分 SALU 与普通 VALU；
不要假设所有 MFMA 类都提供普通 VALU 空隙。候选生成器本身不执行窗口查询或自学。

prepare 自动记录与该 observation 匹配的生成器来源，并核对最终 SHA。保持建议的 direction；
改 spec 后视为新的假设，重新走完整检查。已经注册的产物不会再次出现在建议池；
空池只表示本次有界搜索没有新候选，不表示达到最优。

normalize、wait/NOP 修补也是最终汇编变化的一部分。查看 materialized diagnostics，
需要区分调度与修补贡献时，对固定的控制候选另做配对实验；不能把原版到候选的收益全部归因于某条链。
所有性能判断继续遵守所选 client 的完整输出、计时、确认与关联 workload 要求。

实现及配置接口见 `isa/gfx942/candidates.py`、`agent/directions.py` 和 `tools/sdk/README.md`。
这些操作来自已审核的调度接口及 MFMA 技能；新候选仍须实测，结果写入 client 的 `tune_out/`。
