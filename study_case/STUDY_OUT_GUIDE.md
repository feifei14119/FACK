# `study_out/` 产物说明:流程与各文件作用

> 本文档说明 `bash study_case/study_script/mine_skills.sh` 运行后,`study_case/study_out/`
> 下各文件的**生成顺序、由谁产出、作用**,以及清理规则。
> 配套设计见 [`../proj/skill/ai_assisted_skill_mining.md`](../proj/skill/ai_assisted_skill_mining.md)
> 与 [`../proj/skill/STATUS.md`](../proj/skill/STATUS.md);SDK 无头 agent 见
> [`../tools/sdk/README.md`](../tools/sdk/README.md)。

---

## 一、整体数据流

`mine_skills.sh` 一条命令端到端跑完两个 **GPU-free** 阶段(Layer 1 静态挖掘 + Layer 2 离线 AI 归纳):

```
gold 语料 (/data/feifei/poc_kl/mi300/bf16gemm/shaders)
        │
        │  ① Layer 1: tools/mine_corpus.py        (纯静态, 无 AI, 无 GPU)
        ▼
  skills/gold-*.json  ───────────────►  mine_report.md        (挖掘结果, 人读)
        │  (其中 gold-*-quant.json = 逐 gap 实测量化约束)
        │
        │  ② Layer 2: tools/sdk/articulate.mjs    (无头 Cursor agent, 一条命令内完成 2a~2c)
        │
        │   2a. ai_skill_brief.py  导出 ──►  ai_brief.json + ai_brief.md
        │                                         │
        │   2b. SDK agent 读简报、写  ──────►  ai_proposal.json  (+ ai_articulate.out.txt 原始输出)
        │                                         │
        │   2c. ingest_ai_skills.py 闸门校验 ◄────┘
        ▼
  skills/ai-*.json  ───────────────►  ai_skills.md          (AI 技能, 人读)
```

> 唯一开关是**真机验证 `VALIDATE`**(默认 `0`,关闭);上面两个阶段不受其影响,始终静态执行。

---

## 二、各文件作用一览

| 文件 | 第几步生成 | 谁产出 | 作用 | 本次运行 |
|---|---|---|---|---|
| `skills/gold-*.json` | ① | `mine_corpus.py` | **Layer 1 实测技能**(含 `gold-*-quant.json` 量化约束)——挖掘的可信内核 | 删后重建 |
| `mine_report.md` | ① | `mine_corpus.py` | 挖掘结果的**人读总结**(分类 / 区域 / 各技能);审阅用,不进程序流程 | 覆盖 |
| `ai_brief.json` | ②-2a | `ai_skill_brief.py` | 给 AI 的**简报(机器版)**,也是摄入时的 **ground truth 基准** | 覆盖 |
| `ai_brief.md` | ②-2a | `ai_skill_brief.py` | 同简报的**人读版**(红线 + 提案 schema + 可引用 ref) | 覆盖 |
| `ai_proposal.json` | ②-2b | **SDK agent** | AI 的**归纳提案**(选实测约束 + 标注外推);摄入的输入 | 覆盖 |
| `ai_articulate.out.txt` | ②-2b | `articulate.mjs` | SDK agent 的**原始输出存档**(解析失败时排查用) | 覆盖 |
| `skills/ai-*.json` | ②-2c | `ingest_ai_skills.py` | **Layer 2 AI 技能**(经闸门:实测复制 · 外推封顶 · 恒 candidate) | 摄入前清旧 `ai-*`,重生成 |
| `ai_skills.md` | ②-2c | `ingest_ai_skills.py` | `ai-*.json` 的**人读版**:实测项 vs AI 外推分区呈现 + AI 归因,供工程师审阅有效性/学习 | 覆盖 |

---

## 三、三类关键产物的区别

- **`skills/gold-*.json`** —— 纯实测,最可信,是 Layer 3 在线消费的核心。
  其中 `gold-*-quant.json` 是逐 gap 的量化约束(`mfma_gap_size` / `per_slot_capacity` /
  `burst_runlen` / `intra_gap_order` / `adjacent_cooccur`),AI 简报就是从它导出。
  这些约束还**按指令子类型细分**:按开启 gap 的 **MFMA 形状**(`mfma_class`,如 `16x16x16`/`32x32x8`,
  周期不同则间隙容量不同)与**访存位宽**(`width`,如 `128b`/`32b`)分别实测;`mine_report.md`
  末尾另有 "per-MFMA-class gap breakdown" 小节按形状+位宽列出 gap 大小与容量,供人工核对。
- **`skills/ai-*.json`** —— AI 把实测"表达得更具体 + 加了**未验证外推**",全部 `status=candidate`、
  低置信(`c=0.30`),`source=gold_corpus(modeB-ai)`;真机验证后才可能晋升 `trusted`。
- **`ai_skills.md`** —— `skills/ai-*.json` 的**人读伴随文档**(由摄入确定性生成,与 JSON 一一对应):
  把**实测约束**(带真实数字)与 **AI 外推**(💡,标注未验证)分区呈现,并附 AI 的一句话总结 + 归因。
  供工程师**判断有效性、学习调度直觉**;不被程序消费。
- **`ai_brief.*` / `ai_proposal.json` / `ai_articulate.out.txt`** —— 都是 Layer 2 的**中间产物 / 留档**,
  不被在线 agent 直接消费;真正供消费的只有 `skills/` 目录里的 JSON。

---

## 四、闸门红线(为什么 AI 不会污染)

`ingest_ai_skills.py` 对 SDK agent 的提案逐条校验,模型输出再离谱也只会被丢弃 / 封顶:

- `extrapolated=false` 的约束按 ref **从 Layer 1 逐字复制权威数字**——模型改不动,查无此 ref 即丢弃;
- `extrapolated=true` 的规则必须带 `note`,`weight` 封顶 `0.3`、标 `source:ai-hypothesis`;
- scope 只取组内结构键(`arch`/`loop_kind`/`region`),模型加不了 shape / kernel 名;
- 产物**恒 `candidate`**,`confidence` 封顶(恒低于 gold 量化 ~0.89,故在线去重时实测项永远胜出);
- 只有真机验证(`VALIDATE=1` / `tools/validate_skills.py`)才可能把技能晋升 `trusted`。

---

## 五、清理规则

- `skills/` **整目录每次删后重建**(脚本开头 `rm -rf "$OUT/skills"`):`gold-*` 重新挖掘,`ai-*` 重新摄入;
  `articulate.mjs` 在摄入前还会再清一次旧 `ai-*.json`(只清 AI 的,`gold-*` 不动)。
- 其余文件(`mine_report.md` / `ai_brief.*` / `ai_proposal.json` / `ai_articulate.out.txt` / `ai_skills.md`)都是**覆盖**。
- 因此 `study_out/` 不会出现"上次旧技能悄悄混进本次结果"的情况。
- 反面情况:若某次 Layer 2 因缺 `node` / `@cursor/sdk` / `CURSOR_API_KEY` 被跳过,则 `skills/` 里
  **只有 `gold-*`、没有 `ai-*`**(上次的 `ai-*` 已在开头被清),这是预期行为。

---

## 六、一句话总结

**`mine_report.md` 看挖掘、`ai_brief.*` 喂 AI、`ai_proposal.json` 是 AI 的答卷、`ai_skills.md` 给工程师审阅 AI 技能、
`skills/` 才是最终被消费的技能库**(`gold-*` 实测可信 + `ai-*` AI 归纳待验证)。
