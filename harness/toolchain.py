"""Thin wrapper over the local ROCm/LLVM toolchain (no external project deps).

Used to check that a (reordered) .s still assembles. M0 only locates the tools
and provides the call surface; it is not exercised by M0 tests (which are
GPU/toolchain-free). Full wiring is M4.

The gfx architecture defaults to the one named by the source's
``.amdgcn_target`` (gfx942 when absent).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional

GFX_TARGET = "gfx942"
ROCM_LLVM_BIN = "/opt/rocm/llvm/bin"



def _read(s_path: str) -> str:
    with open(s_path) as f:
        return f.read()


def arch_of(s_path: str, default: str = GFX_TARGET) -> str:
    from isa.registry import arch_of_source
    try:
        return arch_of_source(_read(s_path), default)
    except OSError:
        return default




def _llvm_tool(name: str) -> Optional[str]:
    d = os.environ.get("ROCM_LLVM_BIN", ROCM_LLVM_BIN)
    p = os.path.join(d, name)
    return p if os.path.exists(p) else shutil.which(name)


def find_assembler() -> Optional[str]:
    """Locate an assembler capable of AMDGPU asm (llvm-mc or clang)."""
    for tool in ("llvm-mc", "clang", "clang++"):
        path = shutil.which(tool)
        if path:
            return path
    for tool in ("llvm-mc", "clang"):
        path = _llvm_tool(tool)
        if path:
            return path
    return None


def assemble(s_path: str, out_path: Optional[str] = None,
             gfx_target: Optional[str] = None) -> str:
    """Assemble ``s_path`` to an object/code-object; return the output path.

    Raises FileNotFoundError if no toolchain is available, or
    subprocess.CalledProcessError if assembly fails.
    """
    gfx_target = gfx_target or arch_of(s_path)
    tool = find_assembler()
    if tool is None:
        raise FileNotFoundError(
            "no AMDGPU assembler (llvm-mc/clang) on PATH; install ROCm/LLVM "
            "or inject a custom Evaluator (see harness/evaluator.py)"
        )
    if out_path is None:
        out_path = os.path.splitext(s_path)[0] + ".o"

    base = os.path.basename(tool)
    if base == "llvm-mc":
        cmd: List[str] = [tool, "-triple=amdgcn-amd-amdhsa", "-mcpu=" + gfx_target,
                          "-filetype=obj", s_path, "-o", out_path]
    else:  # clang / clang++
        cmd = [tool, "-x", "assembler", "-target", "amdgcn-amd-amdhsa",
               "-mcpu=" + gfx_target, "-c", s_path, "-o", out_path]

    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def assemble_codeobject(s_path: str, out_path: str,
                        gfx_target: Optional[str] = None,
                        clangpp: str = "/opt/rocm/llvm/bin/clang++") -> str:
    """Assemble a shader .s into a code object (.co), matching testcase/cmd:

        clang++ -x assembler -target amdgcn--amdhsa --offload-arch=gfx942 in.s -o out.co

    Falls back to a clang++ on PATH if the ROCm path is absent.
    """
    gfx_target = gfx_target or arch_of(s_path)
    tool = clangpp if os.path.exists(clangpp) else (shutil.which("clang++") or "")
    if not tool:
        raise FileNotFoundError("clang++ not found (need ROCm/LLVM for .co assembly)")
    cmd = [tool, "-x", "assembler", "-target", "amdgcn--amdhsa",
           "--offload-arch=" + gfx_target, s_path, "-o", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
