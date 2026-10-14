#!/usr/bin/env bash
# Git-only initialization; retain shared upstream sources and gfx942 HSA files.
set -euo pipefail
AIT_CLIENT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
git -C "$AIT_CLIENT_ROOT" submodule update --init --checkout -- client/aiter/upstream
git -C "$AIT_CLIENT_ROOT/client/aiter/upstream" sparse-checkout set --no-cone \
    '/*' '!/hsa/*/' '/hsa/gfx942/'
git -C "$AIT_CLIENT_ROOT/client/aiter/upstream" submodule update --init --recursive
