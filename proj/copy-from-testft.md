# FACK 复制范围

2026-10-14，从 `/home/feifei/repo/testft` 复制当前工作目录到 `/home/feifei/repo/FACK`。
原工程保持不变。未复制原 `.git`、Python/pytest 缓存或依赖安装目录。

保留 gfx942 ISA、通用重排与搜索引擎、client 接口、poc_kl 的 gfx942 GEMM 用例、
SDK、Web UI、通用知识库结构与适用测试。

排除 gfx1250 的内容：

- `isa/gfx1250/`、`tools/gfx1250/` 与专属测试。
- `selfstudy/`：原副本只包含 gfx1250 WMMA 自学工程及其数据、理论、探针和导出物。
- `knowledge/skills/` 中原有的 gfx1250 skill；保留空目录供后续添加资料。
- `client/poc_kl/mla_qh32_sparse/`、专属 ATT launcher、MLA 评测适配与测试。
- gfx1250 专属 code-object 构建、rocprofv3 采集及解码适配。

SDK 和 Web UI 的输入统一为可编辑 `.s` 汇编，不再调用被排除的 `.co` 转换器。
代码对象仍由 gfx942 client 在构建阶段生成。
通用的 Target、计数器和调度扩展接口继续保留。

历史实施记录中的测试数字属于原 testft，不能视为本副本的验收结果。
本次仅做文件完整性、语法与引用等静态检查，没有执行测试、构建、GPU 任务或模型会话。

## 后续同步：selfstudy submodule

初次复制排除的是 testft 内置的旧 WMMA 自学副本。后续已同步新的 submodule 接入方式：
FACK 初始化了独立的本地 Git 仓库，以 gitlink 引入 gfx_hw_prob，并仅稀疏检出 `gfx942/`。
`knowledge/skills/mfma-interleave-gfx942` 直接引用上游已有导出；默认不执行自学。
未重新引入 gfx1250 后端、WMMA 模型加载器或对应用例。
路径和初始化方式见 [submodule 接入说明](selfstudy-submodule.md)。
