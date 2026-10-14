#!/usr/bin/env bash
# Mine region-scoped CANDIDATE skills from a GOLD (hand-optimized, roofline-grade)
# kernel corpus. Takes NO command-line arguments: edit the CONFIG block below to
# change the corpus / out. Two GPU-FREE stages always run:
#   Layer 1  static miner (tools/mine_corpus.py): measured constraint skills.
#   Layer 2  offline AI articulation (ALWAYS ON, no switch): a headless Cursor
#            agent (tools/sdk/articulate.mjs via @cursor/sdk) reads the AI brief
#            exported from the mined quant skills, writes ai_proposal.json, and
#            the Python gate ingests it into capped, candidate-only ai-*.json
#            skills (measured numbers stay Layer-1 authoritative; extrapolations
#            flagged + low-confidence). Both stages are static -- no hardware, and
#            they do NOT touch the curated knowledge/engine; outputs land under
#            study_case/study_out (a human promotes reviewed skills manually).
#            Needs node + CURSOR_API_KEY (env or tools/sdk/cursor.config.json);
#            if unavailable, Layer 1 results are kept and Layer 2 is skipped.
#
# Only REAL-HARDWARE validation is gated (VALIDATE, default 0; see below).
#
# Before EACH run we delete study_case/study_out/skills so stale skills from a
# previous corpus/version never linger and silently mix into the new output.
set -euo pipefail

if [[ $# -gt 0 ]]; then
  echo "mine_skills.sh takes NO arguments; edit the CONFIG block in the script." >&2
  exit 2
fi

# ---- CONFIG (edit these) --------------------------------------------------
# Gold kernel corpus to mine (bare *.s files and/or per-kernel subdirs).
CORPUS="/data/feifei/poc_kl/mi300/bf16gemm/shaders"
# Where mined skills + report land (repo-relative).
OUT_REL="study_case/study_out"
PYTHON="python3.8"
NODE="node"   # for the Layer 2 headless SDK agent (tools/sdk/articulate.mjs)

# --- REAL-HARDWARE VALIDATION SWITCH ---------------------------------------
# Skill SUMMARISATION above is ALWAYS static + GPU-free: you can mine candidate
# skills for ANY architecture on ONE box (this stays on regardless of VALIDATE).
#
# VALIDATE=0 (default): stop after candidate skills -- no GPU, no testcase.
# VALIDATE=1: ALSO run real-HW validation of the mined layout constraints on a
#   runnable target kernel (commit_and_eval -> measured TFLOPS, gated + logged);
#   only meaningful on the MATCHING GPU with a runnable client below.
VALIDATE=0
# Validation target (used ONLY when VALIDATE=1):
VAL_SEED="client/poc_kl/fp8_blockscale_gemm/shader/fp8gemm_blockscase_32mx1_32nx4.s"  # repo-relative seed .s
VAL_CLIENT="poc_kl/fp8_blockscale_gemm"                                 # tuning client (path below client/)
VAL_REGION="loop"
VAL_ARCH="gfx942"
VAL_LOOP_KIND="mfma_dense"
VAL_PROMOTE=0          # 1 => induce_and_save to promote corroborated skills -> trusted
VAL_PARAMS=(m=256 n=256 k=512)   # forwarded VERBATIM to the client
# ---------------------------------------------------------------------------

# Locate the repo root by walking up from this script until we find the miner
# (works whether the script sits at the repo root or under study_script/, etc.).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [[ "$REPO" != "/" && ! -f "$REPO/tools/mine_corpus.py" ]]; do
  REPO="$(dirname "$REPO")"
done
if [[ ! -f "$REPO/tools/mine_corpus.py" ]]; then
  echo "[mine] could not locate repo root (tools/mine_corpus.py not found)" >&2
  exit 1
fi

OUT="$REPO/$OUT_REL"

if [[ ! -d "$CORPUS" ]]; then
  echo "[mine] corpus dir not found: $CORPUS" >&2
  echo "       edit CORPUS in $(basename "${BASH_SOURCE[0]}")." >&2
  exit 2
fi

# Wipe ONLY the previously-mined skills (absolute path -> independent of where
# this script is invoked from). The report is overwritten by the run itself.
echo "[mine] clearing stale skills: $OUT/skills"
rm -rf "$OUT/skills"
mkdir -p "$OUT"

cd "$REPO"
"$PYTHON" tools/mine_corpus.py --corpus "$CORPUS" --out "$OUT"

# Layer 2 offline AI articulation -- ALWAYS ON (no switch), GPU-free. One command:
# the headless SDK agent exports the brief, writes ai_proposal.json, and ingests
# it through the Python gate -> ai-*.json. Runs BEFORE validation so any admitted
# ai-*.json skills are HW-checked too when VALIDATE=1. A missing node/SDK/API key
# only SKIPS Layer 2 (Layer 1 results are already written) -- it never aborts.
echo "[mine] Layer 2 (offline AI) -> tools/sdk/articulate.mjs (headless Cursor agent)"
if ! command -v "$NODE" >/dev/null 2>&1; then
  echo "[mine] '$NODE' not found -> skipping Layer 2 (install Node, then run: $NODE tools/sdk/articulate.mjs)" >&2
elif [[ ! -d "$REPO/tools/sdk/node_modules/@cursor/sdk" ]]; then
  echo "[mine] @cursor/sdk not installed -> skipping Layer 2 (run: cd tools/sdk && npm install)" >&2
else
  if ! "$NODE" "$REPO/tools/sdk/articulate.mjs" --out "$OUT"; then
    echo "[mine] Layer 2 (articulate.mjs) failed (check CURSOR_API_KEY / network); Layer 1 skills kept." >&2
  fi
fi

# Optional real-HW validation of the mined layout constraints (switch above).
if [[ "$VALIDATE" == "1" ]]; then
  echo "[mine] VALIDATE=1 -> real-HW validation on client $VAL_CLIENT (seed $VAL_SEED)"
  promote_flag=()
  [[ "$VAL_PROMOTE" == "1" ]] && promote_flag=(--promote)
  exec "$PYTHON" tools/validate_skills.py \
    --seed "$REPO/$VAL_SEED" --client "$VAL_CLIENT" \
    --store "$OUT" --out "$OUT" --region "$VAL_REGION" \
    --arch "$VAL_ARCH" --loop-kind "$VAL_LOOP_KIND" \
    "${promote_flag[@]}" -- "${VAL_PARAMS[@]}"
else
  echo "[mine] VALIDATE=0 -> candidate skills only (offline; no GPU). "\
"Set VALIDATE=1 on a matching GPU box to validate + promote."
fi
