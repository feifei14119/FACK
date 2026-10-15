// Current FACK aiter workflow. This file is presentation only; commands are never auto-run.
window.TESTFT_DOCS = {
  meta: {title: "FACK 使用手册", subtitle: "gfx942 · aiter · 按 CSV 工作负载调优",
    tagline: "固定代码生成和校验任务，agent skill 指导操作。每个结果对应明确的测试尺寸、配置来源和测量证据。"},
  sections: [
    {id:"dispatch", icon:"◎", title:"当前调优流程", blurb:"同一 .co 的不同尺寸分别管理。", cards:[
      {type:"flow", heading:"从配置到可对比的结果", steps:[
        "选择目标 GPU，读取实际 gfx 和 CU 数",
        "dispatch.py plan：冻结 CSV、完整 workload 与 .co",
        "prepare：导出 seed；client：验证原始派发、完整输出和 op_test",
        "tune_run.py：创建任务，observe / prepare / eval / confirm / final",
        "compare.py：固定候选，逐尺寸独立配对比较",
        "dispatch.py assess：汇总同一 .co 的全部关联尺寸与未完成项"]},
      {type:"prose", heading:"代码与 skill 的分工", html:`<p><code>client/aiter/dispatch.py</code> 负责确定性解析、正反查、参数锁定和覆盖检查。<code>knowledge/skills/aiter-gfx942-validation/SKILL.md</code> 指导环境、派发验证和验收；MFMA 调度读取已导出的自学成果。</p><p>CSV 表明配置选择了某个 kernel，不证明它在新机器上全局最优。未完成原始验证的任务显示“待原始验证”。</p>`}
    ]},
    {id:"environment",icon:"⚙",title:"环境与 GPU",blurb:"网页操作在运行 Web UI 的环境中执行。",cards:[
      {type:"prose",heading:"本机执行与远端进度",html:`<p>执行按钮使用 Web UI 进程所在仓库、解释器和设备。要执行 GPU 操作，应在已准备好的目标环境启动服务，或者将等价命令交给远端 agent。远端进度标签只读本机同步快照，不隐式 SSH 或启动 GPU。</p><p>在多卡机器使用 <code>docker_env.py start --gpu second-last</code> 选择倒数第二张卡；容器中按可见设备 0 使用。不要把 GPU 6、80 CU 或旧机器目录当成通用默认值。</p>`},
      {type:"cmd",heading:"初始化固定依赖（缺失时）",lang:"bash",code:"bash tools/init_aiter.sh\nbash tools/init_selfstudy.sh"},
      {type:"cmd",heading:"读取目标设备架构和 CU 数",lang:"bash",code:"python3 -c 'import torch; p=torch.cuda.get_device_properties(0); print(p.gcnArchName, p.multi_processor_count)'"},
      {type:"prose",heading:"依赖检查",html:`<p>按 <code>client/aiter/docs/validation.md</code> 和 <code>client/aiter/env/gfx942.json</code> 准备 ROCm Python 与工具链。引擎优先 Python 3.8，没有时使用 Python 3；client 的 <code>--python</code> 指向匹配 aiter 的 ROCm 环境。</p>`}
    ]},
    {id:"plans",icon:"▤",title:"计划、尺寸与 CSV 来源",blurb:"规划只用 CPU，不运行 aiter 或 GPU。",cards:[
      {type:"cmd",heading:"生成计划（CU 替换为目标实测值）",lang:"bash",code:"python3 client/aiter/dispatch.py plan --cu 80 --out client/aiter/tune_out/dispatch-new-run"},
      {type:"cmd",heading:"反查一个 .co 的全部配置引用",lang:"bash",code:"python3 client/aiter/dispatch.py lookup client/aiter/tune_out/dispatch-new-run/plan.json --co i8gemm/I8gemm_bf16_perTokenI8_BpreShuffle_32x128.co"},
      {type:"prose",heading:"网页中的计划",html:`<p>“CSV 工作负载”页显示每条引用的 MNK 或算子参数、CSV 文件、行号、backend 和可执行状态。可按尺寸、文件和行号筛选，并选择可验证的 workload。参数由 manifest 锁定，不能修改 MNK/splitK 让原本不支持的任务通过。</p><p>明确区分其他 backend、缺少 .co、目录匹配歧义、配置冲突和待适配。MoE 保留 stage 与路由参数；MLA 目录缺少完整 batch/KV workload 时继续列为待补充。</p><p>来源优先级：显式 CSV → AITER_CONFIG_* 环境 → 默认及 model CSV。独立快照不会改写上游原 CSV。</p>`}
    ]},
    {id:"tuning",icon:"↗",title:"验证与持久化调优",blurb:"创建任务只冻结输入，不表示已执行调优。",cards:[
      {type:"prose",heading:"调优页",html:`<p>先选择计划和 workload，填写 ROCm Python 与单卡 GPU（已在容器限制可见设备时可留空）。依次导出 seed、验证原始 / op_test、创建调优任务。需要 confirm/final 时事先提供比较策略 JSON。</p><p>创建后使用 run 目录执行 <code>eval original</code>，然后 observe / suggest 获取信息，由 agent 提出操作 JSON，使用 prepare 后评测候选，最后 confirm/final。每个 workload 的任务、预算和结果独立。</p><p>高级 SDK agent 入口沿用同一 manifest；SDK 筛选结果仍需要独立配对比较，不能作为最终采用证据。</p>`},
      {type:"prose",heading:"正常入口验证",html:`<p>每次 candidate 先检查实际 gfx/CU，再让正常 aiter 入口读取冻结 CSV，观察实际传入 ASM 的 symbol、splitK 和 layout。完整输出、op_test 与目标 overlay 装载检查通过后才接受计时。这是主机入口和装载证据，不等于 GPU ATT。</p>`}
    ]},
    {id:"results",icon:"≋",title:"结果与跨尺寸对比",blurb:"分别展示 HIP graph 与 op_test，不平均掉回退。",cards:[
      {type:"prose",heading:"结果如何阅读",html:`<p>测试尺寸、CSV 文件及行号直接显示；产物路径信息默认折叠。µs 越低越好，吞吐量越高越好。逐对速度比的统计值可能不同于两列中位数的直接比值。</p><p>历史结果若没有 CSV 来源，显示“未记录”，不会用现在的配置反查补填。独立比较、同代码自检、筛选记录、保留原始和最终采用分别标注。</p>`},
      {type:"prose",heading:"固定候选逐尺寸比较",html:`<p>“测试 / 验证”页沿用所选 workload，可以验证候选、比较原始与候选，再提供各尺寸 comparison.json 汇总覆盖。配对次数、收益门槛、alpha 和允许回退在测试前确定。</p><p>同一 .co 采用同一份固定候选。pending、unsupported、inconclusive 和 regression 都保持可见；某个尺寸的成功不代表整个 .co 已完成。</p>`},
      {type:"prose",heading:"远端进度",html:`<p>远端进度页每 15 秒读本地快照。后台监控按任务配置同步并每 10 分钟记录报告。通信失败、旧快照、停止未核验都会明确标注。已核验本机产物的下载入口在折叠的“产物路径信息”内。</p>`}
    ]},
    {id:"skills",icon:"◇",title:"技能与 CPU 检查",blurb:"普通调优复用已有成果。",cards:[
      {type:"prose",heading:"默认跳过自学",html:`<p>读取 <code>selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/</code> 和已审核知识库。缺依赖时初始化固定 submodule，不运行探针、fit 或 pipeline 补齐。</p><p>静态语料挖掘和离线 AI 归纳是独立的可选任务；产出仍是待审核候选，不直接写入知识库。</p>`},
      {type:"cmd",heading:"CPU 单元测试",lang:"bash",code:"python3 -m pytest -q unittests"},
      {type:"prose",heading:"长期操作文档",html:`<p>详细步骤维护在 <code>client/aiter/docs/dispatch-workloads.md</code>、<code>client/aiter/docs/validation.md</code> 和根 <code>AGENTS.md</code>。运行输出保存在 <code>client/aiter/tune_out/</code>。</p>`}
    ]}
  ]
};
