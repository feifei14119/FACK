// FACK 使用手册 —— 所有使用方法数据（供 app.js 渲染）
// 内容全部源自仓库 README / tools/sdk/README / 入口脚本与工具头注释。
window.TESTFT_DOCS = {
  meta: {
    title: "FACK 使用手册",
    subtitle: "架构可插拔的指令级 AI 辅助优化引擎 · 交互式使用指南",
    tagline:
      "把「AI 逐字改 ASM」反转为「AI 发结构化操作 / 固定逻辑保合法重排 + 修补 pass 流水线 / 真机测量」。完全独立，核心引擎架构无关，硬件指令集收敛到 isa/Target 层（首个实现 gfx942）。",
  },

  sections: [
    // ============================ 概览 ============================
    {
      id: "overview",
      icon: "◎",
      title: "项目概览",
      blurb: "先理解分工与工作流，再看具体命令。",
      cards: [
        {
          type: "prose",
          heading: "核心思路：反转分工",
          html: `
            <ul>
              <li><b>AI / 优化器</b>：只输出<b>结构化策略</b>（move-DSL / 权重 / layout / order），针对稳定指令 ID，<b>绝不直接写 ASM</b>。</li>
              <li><b>固定逻辑引擎</b>：合法重排 + 重算 <code>s_waitcnt</code> + 插 nop（legal-by-construction）+ 校验。</li>
              <li><b>自带 harness</b>：真机三阶段评测 —— 正确性 → 性能(TFLOPS) → ATT 线程跟踪反哺方向。</li>
            </ul>
            <p>优化范围：<b>prologue / core loop / epilogue 三区各自独立重排，指令绝不跨区</b>（唯一跨界动作是只读校验/重算边界 waitcnt）。可从 GEMM 泛化到 MLA / MoE。</p>`,
        },
        {
          type: "prose",
          heading: "工程红线：client 无关",
          html: `
            <p>框架<b>不绑定任何具体项目</b>。用 <code>--client</code> 选调优项目（<code>client/</code> 下的路径，如 <code>poc_kl/fp8_blockscale_gemm</code>），怎么构建/判正确/计时由 <code>client/&lt;项目&gt;/client.py</code> 决定；<code>--</code> 哨兵之后的参数<b>原样透传</b>给 client（引擎不认识 <code>m/n/k</code> 等 shape）。换 kernel 只需换 <code>--client</code>、seed <code>.s</code> 与透传参数；接新项目只需写一个 client（见 <code>client/README.md</code>）。</p>
            <p>所有运行时输出与代码分离：调优产出落各 client 的 <code>client/&lt;名&gt;/tune_out/</code>，静态挖掘产出落 <code>study_case/study_out/</code>（均 gitignore）。</p>`,
        },
        {
          type: "flow",
          heading: "SDK 调优时的调用链",
          steps: [
            "node tune.mjs（SDK 编排：起一个本地 Cursor agent）",
            "Cursor agent（local runtime, cwd=FACK，用 shell 工具）",
            "python3.8 tools/agent_session.py {observe|propose|eval}（决策面 CLI）",
            "AgentSession → 固定逻辑引擎（重排/重算/Verifier/真机评测）",
          ],
        },
      ],
    },

    // ============================ 环境准备 ============================
    {
      id: "setup",
      icon: "⚙",
      title: "环境准备",
      blurb: "Python 3.8+、Node（SDK）、Cursor API key。测试与静态挖掘无需 GPU。",
      cards: [
        {
          type: "cmd",
          heading: "安装 Cursor SDK（仅 SDK 驱动器需要）",
          desc: "tune.mjs / articulate.mjs 依赖 @cursor/sdk（已锁 ^1.0.18）。",
          lang: "bash",
          code: "cd tools/sdk && npm install",
        },
        {
          type: "cmd",
          heading: "提供 API key —— 方式 A：配置文件",
          desc: "tune.mjs 自动读 tools/sdk/cursor.config.json（已 gitignore，务必 chmod 600）。",
          lang: "bash",
          code: `# tools/sdk/cursor.config.json
# { "apiKey": "cursor_...", "model": "auto" }
chmod 600 tools/sdk/cursor.config.json`,
        },
        {
          type: "cmd",
          heading: "提供 API key —— 方式 B：环境变量（覆盖配置文件）",
          desc: "静默输入，不进 shell history；用完 unset。",
          lang: "bash",
          code: `read -rs CURSOR_API_KEY && export CURSOR_API_KEY
# ... 跑完 ...
unset CURSOR_API_KEY`,
        },
        {
          type: "note",
          tone: "warn",
          heading: "共享 root 机器安全提醒",
          html: `明文 key 文件 / env <b>挡不住其他 root 用户</b>。请用<b>可随时吊销的 service-account key</b>，用完即 rotate/revoke。<code>cursor.config.json</code> 已加入 <code>.gitignore</code>，切勿提交。`,
        },
        {
          type: "note",
          tone: "info",
          heading: "语言/运行时说明",
          html: `Python SDK 需 ≥3.10，本机只有 3.8 → SDK 驱动用 <b>TypeScript/Node</b>；引擎本身跑在 <code>python3.8</code>，由 agent 通过 shell 调用。<code>observe</code>/<code>propose</code> 不需 GPU，<code>eval</code> 需要真机 GPU 测试链。`,
        },
      ],
    },

    // ============================ 调优工作流 ============================
    {
      id: "tune",
      icon: "▶",
      title: "调优工作流",
      blurb: "把某个 seed kernel 调快。最简单用入口脚本（改 CONFIG 块即可）。",
      cards: [
        {
          type: "cmd",
          heading: "① 入口脚本（推荐，不接受任何参数）",
          desc: "每个 client 自带入口脚本，调参写在脚本顶部 CONFIG 块。tune_quick 每次运行会先清空该 client 的 tune_out。",
          lang: "bash",
          code: `# 快跑 5 轮，主循环区
./client/poc_kl/tune_script/tune_quick.sh

# 无锚点尾段（prologue+epilogue，各 N 轮，结果按区分文件）
./client/poc_kl/tune_script/tune_prologue_epilogue.sh`,
        },
        {
          type: "table",
          heading: "入口脚本 CONFIG 项",
          columns: ["脚本", "用途", "CONFIG 项"],
          rows: [
            ["tune_quick.sh", "快跑 5 轮（--no-transcript --results；先清空 tune_out）", "ROUNDS / REGION / CLIENT / SEED_REL / PARAMS"],
            ["tune_prologue_epilogue.sh", "无锚点尾段，各 ROUNDS 轮，结果按区分文件", "ROUNDS / REGIONS / CLIENT / SEED_REL / PARAMS"],
          ],
          note: "切换被调优 case 只改三行：CLIENT（client spec）、SEED_REL（seed .s）、PARAMS（原样透传的入参）。脚本与 GEMM 无任何硬编码绑定。",
        },
        {
          type: "cmd",
          heading: "② 直接调 Node 驱动 tune.mjs",
          desc: "-- 哨兵之后的参数原样透传给 client（GEMM 即 m/n/k）。",
          lang: "bash",
          code: `cd tools/sdk
node tune.mjs <seed.s> --client poc_kl/fp8_blockscale_gemm \\
      --rounds 5 --region loop -- m=2560 n=2560 k=256`,
        },
        {
          type: "cmd",
          heading: "tune.mjs 更多示例",
          desc: "换 kernel 只改 client + seed + 它自己的入参；也可只留结果表。",
          lang: "bash",
          code: `# 调主循环区，2 轮
node tune.mjs ../../client/poc_kl/fp8_blockscale_gemm/shader/fp8gemm_blockscase_32mx1_32nx4.s \\
      --client poc_kl/fp8_blockscale_gemm --rounds 2 -- m=2560 n=2560 k=256

# 另一个 case（示意）：换 client + seed + 它自己的入参
node tune.mjs <mla seed.s> --client poc_kl/mla -- --qhead 64 --ctx_len 128 --pagesize 1

# 只看结果表、不留逐轮提示词/输出
node tune.mjs <seed.s> --client poc_kl/fp8_blockscale_gemm --no-transcript -- m=2560 n=2560 k=256`,
        },
        {
          type: "table",
          heading: "tune.mjs 参数（引擎/调优器侧，都在 -- 之前）",
          columns: ["参数", "默认", "说明"],
          rows: [
            ["<seed.s>", "必填", "待调优 kernel 的 .s 路径"],
            ["--client SPEC", "必填", "调优 client（client/ 下的路径）；决定怎么评测候选，输出落其 tune_out/"],
            ["--region SEL", "loop", "调优区域：loop / prologue / epilogue / inter / loop#1；all/auto 让 agent 跨区"],
            ["--rounds N", "6", "agent 最多提交评测多少个候选（每个都过真机门控）"],
            ["--loop N", "20", "真机性能测量循环次数（取中位数）"],
            ["--model ID", "auto", "LLM 模型 id；auto=服务端选"],
            ["--config P", "tools/sdk/cursor.config.json", "API key/model 配置文件路径"],
            ["--transcript / --no-transcript", "开", "是否保存每轮提示词+LLM输出+工具调用/结果"],
            ["--transcript-path P", "<client>/tune_out/transcripts/tune-<ts>.jsonl", "自定义 transcript 路径（.md 同名生成）"],
            ["--results / --no-results", "开", "是否保存每轮结果"],
            ["--results-path P", "<client>/tune_out/transcripts/tune-<ts>.results.jsonl", "结果文件路径（.md 表格同名生成）"],
            ["-- <...>", "—", "哨兵之后原样透传给 client（如 m=2560 n=2560 k=256）"],
          ],
          note: "env CURSOR_API_KEY 始终覆盖 --config 文件里的 key。",
        },
        {
          type: "table",
          heading: "--region 取值",
          columns: ["--region", "含义"],
          rows: [
            ["loop（默认）", "core loop 主循环体，通常杠杆最大"],
            ["prologue", "进入循环前的设置代码"],
            ["epilogue", "循环结束后的收尾/写回"],
            ["inter", "两个循环之间的代码"],
            ["loop#1", "第 2 个循环（多循环 kernel，0 基序号）"],
            ["all / auto", "让 agent 自己跨区切换"],
          ],
        },
      ],
    },

    // ============================ 手动决策面 ============================
    {
      id: "manual",
      icon: "⌘",
      title: "手动决策面（agent_session.py）",
      blurb: "observe / propose / eval 三个子命令，可被 agent 调用，也可手动跑。observe/propose 不需 GPU。",
      cards: [
        {
          type: "cmd",
          heading: "observe：看有哪些区、各多大",
          desc: "始终在 regions 里列出全部区域（index/kind/行号区间/指令数）；--no-direction 跳过真机方向投票。",
          lang: "bash",
          code: `python3.8 tools/agent_session.py observe <seed.s> --no-direction`,
        },
        {
          type: "cmd",
          heading: "有锚点区（loop，含 MFMA）：用 --layout 填 MFMA 间隙",
          desc: "observe 返回 anchors/slots/fillers；layout 指定每个 slot 塞哪些指令 iid。",
          lang: "bash",
          code: `python3.8 tools/agent_session.py eval <seed.s> --region epilogue \\
      --client poc_kl/fp8_blockscale_gemm --layout '{"0":[...]}' -- m=2560 n=2560 k=256`,
        },
        {
          type: "cmd",
          heading: "无锚点区（prologue/epilogue）：用 --order 线性重排",
          desc: "observe 自动切到 DAG 视图（deps/window/bumps_counter/waits_on + waitcnt_preview），目标降 est_cycles。",
          lang: "bash",
          code: `python3.8 tools/agent_session.py observe <seed.s> --no-direction --region epilogue
python3.8 tools/agent_session.py propose <seed.s> --region epilogue --order '[893,894,...]'
python3.8 tools/agent_session.py eval    <seed.s> --client poc_kl/fp8_blockscale_gemm --region epilogue \\
      --order '[893,894,...]' -- m=2560 n=2560 k=256`,
        },
        {
          type: "table",
          heading: "两套词汇：有锚点 vs 无锚点（M9）",
          columns: ["区类型", "observe 返回", "动作"],
          rows: [
            ["有锚点（loop，含 MFMA）", "anchors / slots / fillers", "--layout '{\"<slot>\":[<iid>,...]}' 填 MFMA 间隙"],
            ["无锚点（prologue/epilogue）", "dag（deps/window/bumps_counter/waits_on）+ waitcnt_preview", "--order '[<iid>,...]' 线性重排，降 est_cycles"],
          ],
          note: "regions[] 还带 est_cycles/trip_count/est_share（=trip×est_cycles），Agent 据 est_share 选当前尺寸下真正占耗时的区。eval 裁决以真机 TFLOPS 为准，仅在噪声带内才用 est_cycles 打破平局。",
        },
        {
          type: "table",
          heading: "agent_session.py 参数",
          columns: ["参数", "默认", "说明"],
          rows: [
            ["observe/propose/eval <seed.s>", "必填", "子命令 + seed"],
            ["--client SPEC", "eval / 带方向的 observe 必填", "调优 client；propose / suggest / observe --no-direction 不需要"],
            ["--loop N", "20", "真机测量循环次数"],
            ["--region SEL", "loop", "选区"],
            ["--kernel NAME", "自动检测", "ATT 抓取目标 kernel 符号名"],
            ["--no-direction", "—", "observe 跳过真机方向投票（无 GPU 也能看事实地图）"],
            ["--layout '{...}' / --order '[...]'", "—", "propose/eval 的布局意图（锚点用 layout，无锚点用 order）"],
            ["--results-path P", "无", "仅 eval：把本次裁决权威追加一行到 .jsonl 及同名 .md"],
            ["-- <...>", "无", "哨兵之后原样透传给被测程序"],
          ],
        },
      ],
    },

    // ============================ Skill 挖掘 ============================
    {
      id: "mine",
      icon: "⛏",
      title: "Skill 挖掘（静态，无需 GPU）",
      blurb: "把人工调好的 gold kernel 当标准答案，静态挖出按区域的调优先验。三层：L1 量化提取 / L2 离线 AI 归纳 / L3 在线消费。",
      cards: [
        {
          type: "cmd",
          heading: "① 入口脚本（推荐，不接受任何参数）",
          desc: "每次运行前自动清空 study_out/skills；含 L1 静态挖掘 + L2 离线 AI 归纳（常开，GPU-free）。",
          lang: "bash",
          code: `bash study_case/study_script/mine_skills.sh`,
        },
        {
          type: "cmd",
          heading: "② 直接调用挖掘器（Layer 1）",
          desc: "Mode A 静态语料挖掘：特征只来自语义 Kind + CFG 区域 + 依赖 DAG，绝不假设 GEMM/shape，产物一律 candidate。",
          lang: "bash",
          code: `python3.8 tools/mine_corpus.py [--corpus DIR] [--out DIR]`,
        },
        {
          type: "table",
          heading: "mine_skills.sh CONFIG / mine_corpus 参数",
          columns: ["项", "默认", "说明"],
          rows: [
            ["CORPUS / --corpus", "study_case/gold_corpus/（脚本默认指向外部 bf16gemm/shaders）", "gold 语料目录：每 kernel 一子目录（kernel.s 优先 + 可选 meta.json），或裸 *.s"],
            ["OUT_REL / --out", "study_case/study_out", "产出：skills/gold-<class>-<region>.json（粗） + -quant.json（细量化） + mine_report.md"],
            ["VALIDATE", "0", "0=仅静态产 candidate（无 GPU）；1=在配置的 client（VAL_CLIENT）上额外做真机验证"],
          ],
        },
        {
          type: "cmd",
          heading: "③ Layer 2 离线 AI 归纳（无头 SDK agent）",
          desc: "脱离 Cursor IDE、无需 GPU：导出简报 → Cursor agent 产 ai_proposal.json → 闸门摄入 ai-*.json。需先跑过挖掘且有 gold-*-quant.json。",
          lang: "bash",
          code: `cd /home/feifei/repo/FACK
node tools/sdk/articulate.mjs               # 默认产 proposal 并摄入
node tools/sdk/articulate.mjs --dry-run     # 摄入只打印不落盘
node tools/sdk/articulate.mjs --no-ingest   # 只产 ai_proposal.json
node tools/sdk/articulate.mjs --skip-brief  # 简报已在，跳过导出
# 或: cd tools/sdk && npm run articulate`,
        },
        {
          type: "table",
          heading: "articulate.mjs 参数",
          columns: ["参数", "默认", "说明"],
          rows: [
            ["--out P", "study_case/study_out", "读 ai_brief.*、写 ai_proposal.json、落 skills/ai-*.json"],
            ["--model ID", "auto", "LLM 模型 id"],
            ["--config P", "tools/sdk/cursor.config.json", "API key/model 配置文件"],
            ["--skip-brief", "—", "跳过导出简报（已存在时）"],
            ["--no-ingest", "—", "只产 proposal，不调闸门摄入"],
            ["--dry-run", "—", "摄入走 dry-run（只打印）"],
          ],
        },
        {
          type: "note",
          tone: "info",
          heading: "红线（由 Python 闸门强制，与模型输出无关）",
          html: `实测数字按 ref 从 Layer 1 <b>逐字复制</b>（模型改不动/查无即丢弃）；外推项必带 <code>note</code> 且 <code>weight</code>/<code>confidence</code> 封顶并标 <code>source:ai-hypothesis</code>；scope 只取结构键；产物<b>恒 candidate</b>。模型输出再离谱也只会被丢弃/封顶，绝不污染 store。`,
        },
        {
          type: "flow",
          heading: "无头全自动流程",
          steps: [
            "bash study_case/study_script/mine_skills.sh（挖掘：产 gold-* + 简报）",
            "node tools/sdk/articulate.mjs（SDK agent 产 proposal 并摄入 → ai-*）",
            "人工审核后手工复制进 knowledge/engine/skills/（永不自动晋升 trusted）",
          ],
        },
      ],
    },

    // ============================ 真机验证 ============================
    {
      id: "validate",
      icon: "✔",
      title: "真机验证（需 GPU）",
      blurb: "构建候选 .s → .co → 跑 gemm.exe，报告 PASS/FAIL 与 GFLOPS。",
      cards: [
        {
          type: "cmd",
          heading: "hw_validate.sh：单个候选多 k 值验证",
          desc: "构建候选 .s -> gemm.co，在若干 k 值上跑 N 次，统计 PASS/FAIL。",
          lang: "bash",
          code: `tools/hw_validate.sh <candidate.s> [runs] [k1 k2 ...]
# 例：tools/hw_validate.sh cand.s 10 512 2048 4096`,
        },
        {
          type: "cmd",
          heading: "hw_validate_levels.sh：多 OptLevel 对比",
          desc: "构建并运行手写 baseline 加每个 OptLevel 候选（L0..Lmax），报告 per-k PASS/FAIL + best-of-N GFLOPS。",
          lang: "bash",
          code: `tools/hw_validate_levels.sh [runs] [-- k1 k2 ...]
# 例：tools/hw_validate_levels.sh 20 -- 2048 4096 8192
# 环境覆盖：LEVELS="0 1 2 3"  PY=python3.8`,
        },
        {
          type: "cmd",
          heading: "validate_skills.py：gold 挖出的 layout 约束真机验证（Layer 3）",
          desc: "把 candidate 约束派生候选 layout → commit_and_eval 真机裁决；--promote 可晋升 trusted。也是 mine_skills.sh VALIDATE=1 调的入口。",
          lang: "bash",
          code: `python3.8 tools/validate_skills.py \\
    --seed <seed.s> --client poc_kl/fp8_blockscale_gemm \\
    --store study_case/study_out --out study_case/study_out \\
    --region loop --arch gfx942 --loop-kind mfma_dense \\
    [--promote] -- m=256 n=256 k=512`,
        },
        {
          type: "cmd",
          heading: "eval_candidate.py：单个候选端到端三阶段评测",
          desc: "在真机上跑完整评估契约（正确性→性能→ATT）。",
          lang: "bash",
          code: `python3.8 tools/eval_candidate.py <candidate.s> --client poc_kl/fp8_blockscale_gemm -- m=2560 n=2560 k=256`,
        },
      ],
    },

    // ============================ 测试 ============================
    {
      id: "test",
      icon: "✓",
      title: "运行测试（零安装）",
      blurb: "Python 3.8+，标准库 unittest，无需安装 pytest。",
      cards: [
        {
          type: "cmd",
          heading: "跑全部单元测试",
          desc: "标准库 unittest discover。",
          lang: "bash",
          code: `cd /home/feifei/repo/FACK
python3.8 -m unittest discover -s unittests -t . -v`,
        },
        {
          type: "cmd",
          heading: "（可选）用 pytest",
          desc: "若已安装 pytest 亦可。",
          lang: "bash",
          code: `python3.8 -m pytest`,
        },
      ],
    },

    // ============================ 工具参考 ============================
    {
      id: "tools",
      icon: "🛠",
      title: "CLI 工具参考",
      blurb: "tools/ 下的辅助脚本（诊断 / 冷启动 / 汇总 / 知识库等）。",
      cards: [
        {
          type: "table",
          heading: "tools/*.py",
          columns: ["工具", "作用"],
          rows: [
            ["agent_session.py", "CLI 桥：把 AgentSession 决策面暴露为 observe/propose/eval，供 LLM agent 驱动引擎"],
            ["mine_corpus.py", "Mode A 静态语料挖掘器：从 gold kernel 挖按区域 skill（kernel 无关红线）"],
            ["ai_skill_brief.py", "Layer 2 STAGE 1：把 L1 量化 skill 导出为 ai_brief.json/.md（measured=ground truth）"],
            ["ingest_ai_skills.py", "Layer 2 STAGE 2：读 ai_proposal.json，经严格闸门校验后落 ai-*.json"],
            ["validate_skills.py", "Layer 3 可选真机验证：gold 挖出的 layout 约束 → 真机裁决（可 --promote）"],
            ["eval_candidate.py", "单个候选 .s 的端到端三阶段真机评测"],
            ["make_candidate.py", "从真实 shader 构建候选 .s（含 OptLevel 生成）供 HW 验证"],
            ["coldstart_demo.py", "冷启动演示：把 gemm seed 打散成冷 kernel，证明引擎能恢复性能"],
            ["tune_summarize.py", "把一次 tune run 汇总进 tune_result/（最好/最坏 kernel + 最好 .s）"],
            ["seed_knowledge.py", "用真实实测实验给 M7 知识库播种（无臆造）"],
            ["search_loop.py", "M6c：在 poc_kl GEMM case 上跑 direction 引导的真机搜索循环"],
            ["validate_direction.py", "M6b：验证 EvalResult.direction 的可靠性"],
            ["diag_lds.py", "M5 诊断：追踪 LDS round-trip 的 waitcnt 重算"],
            ["diag_verify.py", "M5 校验器 sanity：接受手写代码 + 重算候选，flag under-sync"],
            ["tweak_waits.py", "诊断：改写候选 .s 里的 wait 值以二分 under-sync bug"],
          ],
        },
      ],
    },

    // ============================ 输出与存放 ============================
    {
      id: "outputs",
      icon: "📂",
      title: "输出与存放",
      blurb: "所有运行时输出与代码分离（gitignore）。",
      cards: [
        {
          type: "table",
          heading: "client/<名>/tune_out/（该 client 调优的全部输出）",
          columns: ["文件/目录", "内容"],
          rows: [
            ["experiments.log", "每次真机评测一行 JSON（权威记录）"],
            ["transcripts/tune-<ts>.jsonl / .md", "SDK 会话 transcript：初始提示词、每个事件、每次工具调用及结果"],
            ["transcripts/*.results.jsonl / .md", "每次 eval 一行（确定性写入）：round/region/layout/correct/tflops/baseline/improvement/accepted/note/est_cycles/shader"],
            ["tune_shaders/<ts>_<kernel>_<region>_<verdict>_tf<TFLOPS>_pid<pid>.s", "每轮提交评测的候选 .s 全量存档，可回溯/重放"],
            ["artifacts/<sha256>.s", "原始 seed、规范化 baseline、候选的汇编快照"],
            ["tune_result/<stem>.summary.md / .json", "筛选最高/最低分及相对规范化 baseline 的差异；尚未独立确认"],
            ["tune_result/<stem>.screening_best_tf<TFLOPS>.s", "待独立复测的候选 .s"],
            ["skills/", "induce_skills 归纳出的技能 JSON（在线实验），人工审核后复制进 knowledge/engine/skills/"],
          ],
        },
        {
          type: "table",
          heading: "study_case/study_out/（静态 skill 挖掘产出）",
          columns: ["文件/目录", "内容"],
          rows: [
            ["skills/gold-<class>-<region>.json", "粗粒度 spec 先验"],
            ["skills/gold-<class>-<region>-quant.json", "细粒度量化约束（Layer 1，全部来自 gold 实测）"],
            ["skills/ai-<class>-<region>-*.json", "Layer 2 离线 AI 归纳（candidate，封顶低置信）"],
            ["mine_report.md", "挖掘报告"],
            ["ai_brief.json / .md", "Layer 2 导出（供外部 agent 引用）"],
            ["ai_proposal.json", "外部 agent 写入的提案（articulate.mjs 或人手写）"],
          ],
        },
        {
          type: "note",
          tone: "info",
          heading: "knowledge/（只读策展知识，git 跟踪，与工具无关）",
          html: `<code>engine/skills/*.json</code>：人工审核过的引擎技能，引擎在 seed 阶段从这里读先验；<code>skills/&lt;name&gt;/SKILL.md</code>：给任何 Agent 读的经验（入口 <code>AGENTS.md</code>，<code>.cursor/skills</code> 是指向它的软链接）。调优运行<b>不会</b>写入它；tune_out / study_out 里的产物<b>人工审核后</b>才手工复制进来。`,
        },
      ],
    },
  ],
};
