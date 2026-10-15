# Pinned MLA codegen metadata

These four unchanged CSV files were exported with `git show` from aiter commit `2abf8aaa44f9d81c88d6153024b21e6931c7f906`; provenance.json records each original path, raw SHA-256 and byte count. They are required client dependencies for new environments using the sparse gfx942 upstream checkout. Keep them with mla_stage1_driver.py.

The pinned upstream codegen computes its C++ type schema from every architecture CSV, then emits configurations only for AITER_GPU_ARCHS. The driver requires exactly gfx942, stages these verified original bytes with the unchanged codegen outside upstream, and builds the unchanged C++ wrapper. Other architecture code objects are neither bundled nor selected. No schema fields or rows were fabricated.

Runtime verifies every CSV against fixed hashes in the driver; absent or changed files fail. This avoids depending on Git alternates that can point outside a container. The source submodule worktree and object database are unchanged.
