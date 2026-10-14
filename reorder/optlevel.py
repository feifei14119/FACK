"""Optimization-level ladder for the reorder engine (architecture-agnostic).

A single integer the caller (AI / search / user) sets to trade *robustness* for
*aggressiveness*. Each level is a superset of the transformations of the level
below it; correctness is preserved at every level (validated on gfx942 HW), the
levels differ only in how much they trust the static models / how aggressively
they relax synchronization.

  L0 CONSERVATIVE  recompute waitcnt; the barrier LDS-release fence drains ALL
                   outstanding lds-direct loads (does NOT rely on the LDS buffer
                   model for the barrier -> robust even if band resolution is
                   imperfect).
  L1 BALANCED      like L0 but the barrier fence uses band look-ahead: it drains
                   only the lds-loads of the buffer bands actually READ before
                   the next barrier, leaving the other bands' prefetch in flight
                   (reproduces / beats the hand-tuned vmcnt). [default]
  L2 SCHEDULED     like L1 plus fine-grained PER-INSTRUCTION reordering on top of
                   the current (already-optimized) kernel as seed: slide async
                   memory ops to their legal-window extreme (e.g. hoist loads ->
                   longer load->use distance / more overlap), then recompute. This
                   only tightens placement of individual ops; it does NOT
                   even-distribute / scatter the schedule.
  L3 SEARCH        HW-in-the-loop autotune: search the space of L2 reorder
                   transforms (kind x direction x composition/order), static-
                   verify each, measure best/median-of-N GFLOPS on real hardware,
                   and pick the fastest correct schedule. Not a single pure
                   transform -- realized by ``tools/search_schedule.py``; its
                   PRODUCT is an L2-class schedule (so policy caps == L2).
  L4 AGGRESSIVE    like L2 but the movable set is extended to VALU and SALU ops
                   (not just async memory ops). This is safe by construction: the
                   dep graph carries RAW/WAR/WAW edges over every register def/use
                   (incl. implicit scc/m0), so a v/s op's legal window is bounded
                   by its consumers -- e.g. a v_* that computes a VGPR a later
                   buffer_load uses as its address can never slide past that load.
                   Strategy may be arbitrarily aggressive; the Verifier (dep-order
                   + waitcnt/barrier sufficiency) and HW cull any wrong result.

The design contract: the FIXED logic only guarantees a trustworthy per-instruction
move interface + correct waitcnt / barrier recompute after moves; the AI picks the
optimization direction/strategy, and verification discards incorrect kernels.

NOT part of this ladder -- two separate, orthogonal things:
  * ``recompute_waitcnt=False`` (production default, even safer than L0): keep the
    hand-written waits as fences and never recompute -- for warm, hand-tuned
    kernels.
  * *even-distribution* (``RegionEditor.distribute_evenly``): only bootstraps a
    COMPLETELY UNOPTIMIZED kernel (ops still clustered by type: all MFMA
    together, all buffer_load together, all ds_read/write together) into a usable
    seed by spreading memory ops into the MFMA stream. The seed of an
    already-optimized kernel is the kernel itself (and the perf baseline) -- the
    opt-level ladder runs directly on it and never re-distributes.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class OptLevel(enum.IntEnum):
    CONSERVATIVE = 0      # recompute; barrier drains ALL lds-loads
    BALANCED = 1          # + barrier band look-ahead
    SCHEDULED = 2         # + per-instruction reorder (hoist loads) on the seed
    SEARCH = 3            # HW-autotune over L2 transforms (tools/search_schedule.py)
    AGGRESSIVE = 4        # + reorder VALU/SALU too (RAW/WAR/WAW-bounded)

    @classmethod
    def coerce(cls, value) -> "OptLevel":
        if isinstance(value, cls):
            return value
        iv = int(value)
        # clamp into the implemented range (unknown high values -> most aggressive
        # currently implemented level, NOT a silent no-op).
        iv = max(int(min(cls)), min(iv, int(max(cls))))
        return cls(iv)


DEFAULT = OptLevel.BALANCED


@dataclass(frozen=True)
class OptPolicy:
    """Decoded capabilities for an OptLevel (what each knob does)."""

    level: OptLevel
    barrier_band_scoped: bool      # band look-ahead barrier fence (vs drain-all)
    reorder: bool                  # per-instruction reorder on the seed (L2)
    reorder_alu: bool              # also move VALU/SALU ops, not just mem (L4)

    @property
    def recompute(self) -> bool:
        return True                # the whole ladder is on the recompute path


def policy(level) -> OptPolicy:
    lv = OptLevel.coerce(level)
    return OptPolicy(
        level=lv,
        barrier_band_scoped=(lv >= OptLevel.BALANCED),
        reorder=(lv >= OptLevel.SCHEDULED),
        reorder_alu=(lv >= OptLevel.AGGRESSIVE),
    )
