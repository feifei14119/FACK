#!/usr/bin/env bash
# Multi-level HW validation (gfx942 / MI308X): build & run the hand-written
# baseline plus each OptLevel candidate (L0..Lmax), reporting per-k PASS/FAIL
# counts and best-of-N GFLOPS so correctness AND performance can be compared.
#
#   tools/hw_validate_levels.sh [runs] [-- k1 k2 ...]
#   tools/hw_validate_levels.sh 20 -- 2048 4096 8192
#
# Env overrides: LEVELS="0 1 2 3"  PY=python3.8
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TC="$HERE/client/poc_kl/fp8_blockscale_gemm"
PY="${PY:-python3.8}"
CLANG=/opt/rocm/llvm/bin/clang++
LEVELS="${LEVELS:-0 1}"

RUNS="${1:-15}"; [ $# -ge 1 ] && shift
[ "${1:-}" = "--" ] && shift
KS=("$@"); [ ${#KS[@]} -eq 0 ] && KS=(2048 4096 8192)

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SHADER="$TC/shader/fp8gemm_blockscase_32mx1_32nx4.s"

# build one .s -> a private .co (do NOT clobber the repo's gemm.co)
build() {  # <src.s> <out.co>
  ( cd "$TC" && "$CLANG" -x assembler -target amdgcn--amdhsa \
      --offload-arch=gfx942 "$1" -o "$2" ) 2>"$WORK/build.err"
}

# run RUNS times at every k against <co>; prints a result row per k
run_co() {  # <label> <co>
  local label="$1" co="$2" k pass fail best out g
  cp "$co" "$TC/gemm.co"            # gemm.exe loads ./gemm.co from cwd
  for k in "${KS[@]}"; do
    pass=0; fail=0; best=0
    for _ in $(seq 1 "$RUNS"); do
      out="$(cd "$TC" && ./gemm.exe k="$k" 2>/dev/null)"
      if echo "$out" | grep -q "TEST PASSED"; then pass=$((pass+1)); else fail=$((fail+1)); fi
      g="$(echo "$out" | sed -n 's/.*gflops:\([0-9.]*\).*/\1/p' | head -1)"
      [ -n "$g" ] && awk "BEGIN{exit !($g>$best)}" && best="$g"
    done
    printf "  %-10s k=%-6s PASS=%2d/%-2d  best=%8s GFLOPS\n" "$label" "$k" "$pass" "$RUNS" "$best"
  done
}

echo "== HW validate (runs=$RUNS, k=${KS[*]}, levels=$LEVELS) =="

# baseline = hand-written shader (unmodified)
if build "$SHADER" "$WORK/baseline.co"; then
  run_co "baseline" "$WORK/baseline.co"
else
  echo "  baseline   BUILD FAILED"; sed -n '1,5p' "$WORK/build.err"
fi

for lv in $LEVELS; do
  s="$WORK/cand_l$lv.s"; co="$WORK/cand_l$lv.co"
  if ! "$PY" "$HERE/tools/make_candidate.py" level "$lv" "$s" >"$WORK/gen.err" 2>&1; then
    echo "  L$lv        GEN FAILED"; sed -n '1,5p' "$WORK/gen.err"; continue
  fi
  v="$(grep -o 'verify ok=[A-Za-z]*' "$WORK/gen.err" | head -1)"
  if ! build "$s" "$co"; then
    echo "  L$lv        BUILD FAILED ($v)"; sed -n '1,5p' "$WORK/build.err"; continue
  fi
  run_co "L$lv($v)" "$co"
done

# restore the repo's original gemm.co (rebuild from the shader)
build "$SHADER" "$TC/gemm.co" && echo "restored client/poc_kl/fp8_blockscale_gemm/gemm.co from shader"
