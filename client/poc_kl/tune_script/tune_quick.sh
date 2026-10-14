#!/usr/bin/env bash
# Quick tune (self-contained). Takes NO command-line arguments: the tuning
# budget (ROUNDS), the code region (REGION), the seed kernel, the CLIENT and its
# PARAMS are ALL fixed in the CONFIG block below. Edit those values to change a
# run. Wraps tools/sdk/tune.mjs; always runs with --no-transcript (don't save
# LLM prompts/outputs) + --results (save per-round result rows under
# client/poc_kl/tune_out/transcripts).
#
# IMPORTANT: the tuner is client-AGNOSTIC. NOTHING about GEMM is hardwired.
#   * CLIENT picks WHICH project case to tune (a path below client/, see
#     client/README.md), e.g. poc_kl/fp8_blockscale_gemm.
#   * SEED_REL is that kernel's seed .s (the shader the tuner mutates).
#   * PARAMS are forwarded VERBATIM (after the `--` sentinel) to the client. For
#     THIS GEMM case that's m=/n=/k=; another case uses ITS own params,
#     e.g. PARAMS=(--qhead 64 --ctx_len 128 --pagesize 1).
#
# API key: from env CURSOR_API_KEY or tools/sdk/cursor.config.json (see tools/sdk/README.md).
set -euo pipefail

if [[ $# -gt 0 ]]; then
  echo "tune_quick.sh takes NO arguments; edit the CONFIG block in the script." >&2
  exit 2
fi

# ---- CONFIG (edit these) --------------------------------------------------
ROUNDS=5        # number of commit rounds the agent may spend
REGION=loop     # which code region to tune: loop | prologue | epilogue | inter | loop#1 | all
CLIENT="poc_kl/fp8_blockscale_gemm"     # tuning client (path below client/)
SEED_REL="client/poc_kl/fp8_blockscale_gemm/shader/fp8gemm_blockscase_32mx1_32nx4.s"  # seed kernel (repo-relative)
# Client params forwarded VERBATIM to the program under test (this GEMM exe):
PARAMS=(m=256 n=256 k=512)
# ---------------------------------------------------------------------------

# Locate the repo root by walking up from this script until we find the engine
# (works whether the script sits at the repo root or under tune_script/, etc.).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [[ "$REPO" != "/" && ! -f "$REPO/tools/sdk/tune.mjs" ]]; do
  REPO="$(dirname "$REPO")"
done
SEED="$REPO/$SEED_REL"

# Wipe all previous tuning outputs (absolute path -> independent of where this
# script is invoked from; the relative form silently no-ops off the repo root).
OUT="$REPO/client/${CLIENT%%/*}/tune_out"
rm -rf "$OUT"
mkdir -p "$OUT"

cd "$REPO/tools/sdk"

exec node tune.mjs "$SEED" \
  --client "$CLIENT" \
  --rounds "$ROUNDS" --region "$REGION" \
  --transcript --results \
  -- "${PARAMS[@]}"
