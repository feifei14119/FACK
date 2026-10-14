#!/usr/bin/env bash
# Initialize the pinned dependency and retain only gfx942 in its working tree.
# This performs Git operations only; it never runs the self-study project.
set -euo pipefail

FACK_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
git -C "$FACK_ROOT" submodule update --init --checkout -- selfstudy
git -C "$FACK_ROOT/selfstudy" sparse-checkout set --cone gfx942

FACK_SKILL="$FACK_ROOT/selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/SKILL.md"
if [[ ! -f "$FACK_SKILL" ]]; then
    printf '%s\n' 'The pinned submodule does not contain the gfx942 skill export; no self-study will be run.' >&2
    exit 1
fi
