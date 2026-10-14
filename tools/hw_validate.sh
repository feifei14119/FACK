#!/usr/bin/env bash
# M5 hardware validation: build a candidate .s -> .co and run gemm.exe N times
# at several k values, reporting PASS/FAIL counts.
#
#   tools/hw_validate.sh <candidate.s> [runs] [k1 k2 ...]
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TC="$HERE/client/poc_kl/fp8_blockscale_gemm"
CAND="${1:?usage: hw_validate.sh candidate.s [runs] [k...]}"
RUNS="${2:-10}"
shift $(( $# >= 2 ? 2 : 1 ))
KS=("$@"); [ ${#KS[@]} -eq 0 ] && KS=(512 2048 4096)

CLANG=/opt/rocm/llvm/bin/clang++
cp "$CAND" "$TC/cand.s"
( cd "$TC" && "$CLANG" -x assembler -target amdgcn--amdhsa --offload-arch=gfx942 \
    cand.s -o gemm.co ) || { echo "BUILD FAILED"; exit 1; }
echo "built $(basename "$CAND") -> gemm.co"

cd "$TC"
for k in "${KS[@]}"; do
  pass=0; fail=0
  for i in $(seq 1 "$RUNS"); do
    out="$(./gemm.exe k="$k" 2>/dev/null)"
    if echo "$out" | grep -q "TEST PASSED"; then pass=$((pass+1));
    elif echo "$out" | grep -q "TEST FAILED"; then fail=$((fail+1));
    else fail=$((fail+1)); fi
  done
  printf "k=%-6s PASS=%d/%d FAIL=%d\n" "$k" "$pass" "$RUNS" "$fail"
done
