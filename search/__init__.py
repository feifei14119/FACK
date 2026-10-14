"""Search / strategy layer (M6c): move-DSL, weighted list scheduler, search loop.

  * ``movedsl``        -- declarative per-position move-DSL (mechanism B): the
                          AI's fine-grained surface over stable instruction
                          handles; compiled into RegionEditor primitives.
  * ``list_scheduler`` -- tunable-weight greedy list scheduler (mechanism A).
  * ``driver``         -- the search loop: voted ``direction`` prior (M6b) +
                          candidate generation (ladder / compact / list-sched /
                          move-DSL) + real-HW GFLOPS verdict + fixed fallback.
"""
from .driver import (DirectionVote, SearchResult, Trial, build_candidate,
                     direction_to_specs, fallback_specs, search, vote_direction)
from .list_scheduler import Weights, schedule
from . import movedsl

__all__ = [
    "movedsl", "schedule", "Weights",
    "search", "build_candidate", "vote_direction", "direction_to_specs",
    "fallback_specs", "DirectionVote", "SearchResult", "Trial",
]
