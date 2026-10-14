"""Diagnostic: rewrite wait values in a candidate .s to bisect the under-sync bug.

  force_lgkm0 : every lgkmcnt(N) -> lgkmcnt(0)
  clamp_vm K  : every vmcnt(N) with N>K -> vmcnt(K)
"""
import re
import sys

mode = sys.argv[1]
src_path = sys.argv[2]
out_path = sys.argv[3]
with open(src_path) as f:
    text = f.read()

if mode == "force_lgkm0":
    text = re.sub(r"lgkmcnt\(\d+\)", "lgkmcnt(0)", text)
elif mode == "clamp_vm":
    K = int(sys.argv[4])
    text = re.sub(r"vmcnt\((\d+)\)",
                  lambda m: "vmcnt({})".format(min(int(m.group(1)), K)), text)
else:
    raise SystemExit("unknown mode")

with open(out_path, "w") as f:
    f.write(text)
print("wrote", out_path)
