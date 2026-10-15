"""gfx942 / CDNA3 counter model.

Counters (see amdgpu-asm-codebase .../gfx942/13-waitcnt.md):
  vm   (vmcnt)   6-bit  -- VMEM loads + atomic-with-return complete
  lgkm (lgkmcnt) 4-bit  -- LDS (ds_*) + scalar memory (s_load) + s_sendmsg
  exp  (expcnt)  3-bit  -- export / GDS / ``lds`` direct-write data consumed
  vs   (vscnt)   6-bit  -- VMEM stores complete (separate counter on gfx942)

``s_waitcnt`` packs vm/lgkm/exp into a 16-bit immediate; ``s_waitcnt_vscnt``
carries vs separately. The assembler may emit any of:
    s_waitcnt 0x0000                 (raw simm16)
    s_waitcnt lgkmcnt(0)
    s_waitcnt vmcnt(10) & lgkmcnt(0) (note the '&' separator)
    s_waitcnt_vscnt null, 0
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from ..counters import CounterModel, WaitSpec

# simm16 bit layout for s_waitcnt on gfx9/CDNA family.
_VM_LO_MASK = 0x000F     # bits [3:0]
_EXP_MASK = 0x0070       # bits [6:4]
_LGKM_MASK = 0x0F00      # bits [11:8]
_VM_HI_MASK = 0xC000     # bits [15:14]

_SYM_RE = re.compile(r"(vmcnt|lgkmcnt|expcnt|vscnt)\s*\(\s*(\d+)\s*\)")

_NAME_BY_SYM = {"vmcnt": "vm", "lgkmcnt": "lgkm", "expcnt": "exp", "vscnt": "vs"}
_SYM_BY_NAME = {v: k for k, v in _NAME_BY_SYM.items()}


class Gfx942CounterModel(CounterModel):
    names = ["vm", "lgkm", "exp", "vs"]
    widths = {"vm": 63, "lgkm": 15, "exp": 7, "vs": 63}
    # Prologue loads can still be live on the first loop iteration. Their
    # issue order need not match the software-pipelined steady-state body.
    seed_loop_entry = True

    def is_wait(self, opcode: str) -> bool:
        return opcode.lower() in (
            "s_waitcnt", "s_waitcnt_vscnt",
            "s_waitcnt_vmcnt", "s_waitcnt_expcnt", "s_waitcnt_lgkmcnt",
        )

    # --- decoding helpers --------------------------------------------------
    @staticmethod
    def _decode_simm16(val: int) -> Dict[str, Optional[int]]:
        vm = (val & _VM_LO_MASK) | ((val & _VM_HI_MASK) >> 10)
        exp = (val & _EXP_MASK) >> 4
        lgkm = (val & _LGKM_MASK) >> 8
        return {"vm": vm, "lgkm": lgkm, "exp": exp}

    @staticmethod
    def _encode_simm16(vm: int, lgkm: int, exp: int) -> int:
        val = 0
        val |= vm & 0x0F
        val |= (vm & 0x30) << 10            # high 2 bits -> [15:14]
        val |= (exp & 0x7) << 4
        val |= (lgkm & 0xF) << 8
        return val

    def parse_wait(self, opcode: str, operands: List[str]) -> WaitSpec:
        op = opcode.lower()
        spec = WaitSpec(targets={})

        if op == "s_waitcnt_vscnt":
            # e.g. operands: ["null", "0"] or ["null", "0x0"] ; or vscnt(N) form
            spec.targets["vs"] = self._parse_scalar_count(operands)
            return spec

        joined = " ".join(operands)
        syms = _SYM_RE.findall(joined)
        if syms:
            for sym, num in syms:
                spec.targets[_NAME_BY_SYM[sym]] = int(num)
            return spec

        # numeric simm16 form: s_waitcnt 0x0000
        num = self._parse_scalar_count(operands)
        if num is not None:
            spec.targets.update(self._decode_simm16(num))
        return spec

    @staticmethod
    def _parse_scalar_count(operands: List[str]) -> Optional[int]:
        for f in operands:
            tok = f.strip().split()[0] if f.strip() else ""
            if not tok or tok.lower() == "null":
                continue
            try:
                return int(tok, 0)
            except ValueError:
                continue
        return None

    def format_wait(self, spec: WaitSpec) -> str:
        # vs is emitted via a separate instruction; here format the s_waitcnt body.
        parts = []
        for name in ("vm", "lgkm", "exp"):
            v = spec.targets.get(name)
            if v is not None and v < self.widths[name]:
                parts.append(f"{_SYM_BY_NAME[name]}({v})")
        return " & ".join(parts) if parts else "0x0000"

    def format_waits(self, targets: Dict[str, int]):
        out = []
        body_targets = {c: v for c, v in targets.items() if c in ("vm", "lgkm", "exp")}
        if body_targets:
            body = self.format_wait(WaitSpec(targets=body_targets))
            out.append(("s_waitcnt", [body], body))
        if "vs" in targets:
            out.append(("s_waitcnt_vscnt", ["null", str(targets["vs"])],
                        "null, {}".format(targets["vs"])))
        return out
