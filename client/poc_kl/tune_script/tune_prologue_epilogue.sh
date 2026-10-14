#!/usr/bin/env bash
# Tune the ANCHOR-LESS tail regions (prologue + epilogue), ROUNDS rounds EACH.
# Self-contained (takes NO command-line arguments): edit the CONFIG block below.
# Mirrors tune_quick.sh -- --no-transcript (don't save LLM prompts/outputs) +
# --results (save per-round results). Runs tune.mjs once per region SEQUENTIALLY,
# writing REGION-TAGGED result files so the two regions are easy to compare.
#
# prologue/epilogue usually have no MFMA anchors, so the agent automatically uses
# the DAG / linear-order vocabulary (--order) rather than MFMA-gap layouts.
#
# IMPORTANT: the tuner is client-AGNOSTIC (see tune_quick.sh). CLIENT picks
# WHICH project case to tune (a path below client/), SEED_REL is its seed .s, and
# PARAMS are forwarded VERBATIM (after `--`) to the client. For GEMM that's
# m=/n=/k=; another case uses its own, e.g. PARAMS=(--qhead 64 --ctx_len 128).
#
# API key: from env CURSOR_API_KEY or tools/sdk/cursor.config.json (see tools/sdk/README.md).
set -euo pipefail

if [[ $# -gt 0 ]]; then
  echo "tune_prologue_epilogue.sh takes NO arguments; edit the CONFIG block." >&2
  exit 2
fi

# ---- CONFIG (edit these) --------------------------------------------------
ROUNDS=5                     # rounds PER region
REGIONS="prologue epilogue"  # which tail regions to tune (space-separated)
CLIENT="poc_kl/fp8_blockscale_gemm"     # tuning client (path below client/)
SEED_REL="client/poc_kl/fp8_blockscale_gemm/shader/fp8gemm_blockscase_32mx1_32nx4.s"  # seed kernel (repo-relative)
PARAMS=(m=2560 n=2560 k=256) # client params forwarded VERBATIM to the exe
# ---------------------------------------------------------------------------

# Locate the repo root by walking up from this script until we find the engine.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [[ "$REPO" != "/" && ! -f "$REPO/tools/sdk/tune.mjs" ]]; do
  REPO="$(dirname "$REPO")"
done
SEED="$REPO/$SEED_REL"

# All outputs go under the client's tune_out (never the code tree).
OUT_DIR="$REPO/client/${CLIENT%%/*}/tune_out/transcripts"
mkdir -p "$OUT_DIR"
cd "$REPO/tools/sdk"
STAMP="$(date +%Y%m%d-%H%M%S)"
for REGION in $REGIONS; do
  echo "=== tuning region: $REGION ($ROUNDS rounds) ==="
  node tune.mjs "$SEED" \
    --client "$CLIENT" \
    --rounds "$ROUNDS" --region "$REGION" \
    --no-transcript --results \
    --results-path "$OUT_DIR/tune-${STAMP}-${REGION}.results.jsonl" \
    -- "${PARAMS[@]}"
done

echo
echo "done. per-region results:"
for REGION in $REGIONS; do
  echo "  $OUT_DIR/tune-${STAMP}-${REGION}.results.{jsonl,md}"
done
