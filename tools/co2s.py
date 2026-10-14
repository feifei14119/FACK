#!/usr/bin/env python3
"""Disassemble an AMDGPU code object (.co) into a .s that rebuilds to an equivalent .co.

  co2s.py k.co                   # write k.s next to k.co and verify by rebuilding
  co2s.py k.co -o out/k.s        # choose the output path
  co2s.py k.co --exact           # require bit-identical .text (more .long lines)
  co2s.py k.co --no-verify       # skip the rebuild (no clang / ld.lld needed)
  co2s.py k.co --keep k2.co      # also keep the rebuilt code object

The .s holds:
  .text     llvm-objdump output; branch offsets rewritten as labels
  .rodata   each kernel descriptor decoded into .amdhsa_* directives
  metadata  the NT_AMDGPU_METADATA note as an .amdgpu_metadata YAML block

Verification rebuilds the .s with
  clang -x assembler -target amdgcn-amd-amdhsa -mcpu=<gfx> -mcode-object-version=<N> -c k.s -o k.o
  ld.lld -shared k.o -o k.co
and checks every instruction. One the assembler rejects, or rebuilds to
something else, is written as `.long <original words>  // <disassembly>`.
"Something else" means different disassembly by default; with --exact it
means different bytes. The default accepts encodings that differ only in
fields the hardware ignores (e.g. the unused src2 of a two-source VOP3,
which the original encoder left 0 and LLVM fills with inline constant 0).

This entry supports gfx942. Architecture-specific frontends can provide a decoder.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

BRANCH_RE = re.compile(r"^(s_branch|s_cbranch_\w+|s_call_b64)\b")
INSN_RE = re.compile(r"^\t(?P<text>.*?)\s*// (?P<addr>[0-9A-Fa-f]{12}):(?P<raw>(?: [0-9A-Fa-f]{8})+)")
SYM_RE = re.compile(r"^([0-9a-f]{16}) <(.+)>:$")
ABI_TO_COV = {2: 4, 3: 5, 4: 6}
MAX_FIX_ROUNDS = 64


def tool(name):
    for c in (os.environ.get("ROCM_LLVM_BIN") and os.path.join(os.environ["ROCM_LLVM_BIN"], name),
              "/opt/rocm/llvm/bin/" + name, shutil.which(name)):
        if c and os.path.isfile(c):
            return c
    sys.exit("cannot find {}; set ROCM_LLVM_BIN to the ROCm llvm/bin directory".format(name))


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        sys.exit("command failed: {}\n{}".format(" ".join(cmd), p.stderr))
    return p.stdout


# ---------------------------------------------------------------- ELF queries
def elf_header(co):
    out = run([tool("llvm-readelf"), "-h", co])
    flags = re.search(r"Flags:\s+\S+,\s*(gfx\w+)(.*)", out)
    abi = re.search(r"ABI Version:\s+(\d+)", out)
    if not flags:
        sys.exit("{}: no gfx target in ELF flags".format(co))
    return flags.group(1), tuple(f.strip() for f in flags.group(2).split(",") if f.strip()), int(abi.group(1))


def target_id(gfx, feats):
    """gfx942 + ('xnack+', 'sramecc') -> 'gfx942:xnack+'. Bare 'xnack'/'sramecc' means "any"."""
    on_off = sorted(f for f in feats if f[-1:] in "+-" and f[:-1] in ("sramecc", "xnack"))
    return ":".join([gfx] + on_off)


def metadata_yaml(co):
    out = run([tool("llvm-readelf"), "--notes", co])
    m = re.search(r"^\s*---\n(.*?)^\.\.\.$", out, re.S | re.M)
    if not m:
        sys.exit("{}: no NT_AMDGPU_METADATA note".format(co))
    return "---\n" + m.group(1) + "..."


def symbols(co):
    """FUNC symbols {name: (value, bind, vis)} and .kd OBJECT symbols {name: value}."""
    funcs, kds = {}, {}
    for line in run([tool("llvm-readelf"), "-s", "--wide", co]).splitlines():
        f = line.split()
        if len(f) < 8 or not f[0].rstrip(":").isdigit():
            continue
        value, typ, bind, vis, name = int(f[1], 16), f[3], f[4], f[5], f[7]
        if typ == "OBJECT" and name.endswith(".kd"):
            kds.setdefault(name, value)
        elif typ == "FUNC":
            funcs.setdefault(name, (value, bind, vis))
    return funcs, kds


def section(co, name):
    """(address, bytes) of a section."""
    sh = run([tool("llvm-readelf"), "-S", "--wide", co])
    m = re.search(r"\s{}\s+\S+\s+([0-9a-f]+)".format(re.escape(name)), sh)
    if not m:
        return None, b""
    data = bytearray()
    for line in run([tool("llvm-readelf"), "-x", name, co]).splitlines():
        m2 = re.match(r"\s*0x[0-9a-f]+ ((?:[0-9a-f]{2,8} ){1,4})", line + " ")
        if m2:
            data += bytes.fromhex(m2.group(1).replace(" ", ""))
    return int(m.group(1), 16), bytes(data)


def kd_bytes(co, kd):
    """64-byte kernel descriptor; bytes 16..23 (self-relative entry offset) masked."""
    _, kds = symbols(co)
    base, data = section(co, ".rodata")
    off = kds[kd] - base
    raw = data[off:off + 64]
    return raw[:16] + b"\0" * 8 + raw[24:]


# ------------------------------------------------------------ disassembly
def kernel_descriptor(mcpu, co, kd):
    # LLVM's disassembler defaults to XNACK off, whereas the assembler reserves
    # the mask for both XNACK on and "any". Decode with the same reservation so
    # a gfx942 object with unspecified XNACK can round-trip without narrowing
    # its target ID. The rebuilt descriptor is still checked byte for byte.
    gfx, *features = mcpu.split(":")
    attrs = [("+" if f.endswith("+") else "-") + f[:-1]
             for f in features if f.endswith(("+", "-"))]
    if gfx == "gfx942" and not any(f.startswith("xnack") for f in features):
        attrs.append("+xnack")
    cmd = [tool("llvm-objdump"), "-D", "--mcpu=" + gfx]
    if attrs:
        cmd.append("--mattr=" + ",".join(attrs))
    out = run(cmd + ["--disassemble-symbols=" + kd, co])
    m = re.search(r"^(\.amdhsa_kernel .*?^\.end_amdhsa_kernel)$", out, re.S | re.M)
    if not m:
        sys.exit("cannot decode kernel descriptor {}".format(kd))
    lines = [l.strip() for l in m.group(1).splitlines()]
    # The encoded SGPR allocation is rounded to a granule of eight. LLVM can
    # print 104 for gfx942's last granule, above the assembler's limit of 102.
    # Leave room for the special SGPR reservation when XNACK is on/any.
    # Both values encode the same final granule; compare() verifies the KD.
    if gfx == "gfx942":
        last = 102 if "xnack-" in features else 98
        lines = [".amdhsa_next_free_sgpr {}".format(last) if l == ".amdhsa_next_free_sgpr 104" else l
                 for l in lines]
    return lines


def _objdump(mcpu, co, start=None):
    cmd = [tool("llvm-objdump"), "-d", "--mcpu=" + mcpu]
    if start is not None:
        cmd.append("--start-address=0x{:x}".format(start))
    insts = []
    for line in run(cmd + [co]).splitlines():
        m = INSN_RE.match(line)
        if m:
            insts.append({"addr": int(m.group("addr"), 16), "orig": m.group("text").strip(),
                          "words": [int(w, 16) for w in m.group("raw").split()]})
    return insts


def disassemble(mcpu, co):
    """Generic LLVM instruction decoder; architecture frontends may extend it."""
    return _objdump(mcpu, co)


def relabel(insts, funcs):
    """Set it["text"]; SOPP branch immediates become labels. Returns ({addr: label}, warnings)."""
    starts = {it["addr"] for it in insts}
    func_at = {v[0]: n for n, v in funcs.items()}
    labels, warns = {}, []
    for it in insts:
        addr, text = it["addr"], it["orig"]
        it["text"] = text
        b = BRANCH_RE.match(text)
        if b:
            imm = it["words"][0] & 0xFFFF
            target = addr + 4 + 4 * (imm - 0x10000 if imm & 0x8000 else imm)
            if target in starts:
                labels.setdefault(target, func_at.get(target, "L_{:x}".format(target)))
                ops = [p.strip() for p in text[len(b.group(1)):].split(",") if p.strip()]
                it["text"] = b.group(1) + " " + ", ".join(ops[:-1] + [labels[target]])
            else:
                warns.append("0x{:x}: branch target 0x{:x} is not an instruction, kept numeric".format(addr, target))
        elif text.startswith("s_getpc_b64"):
            warns.append("0x{:x}: s_getpc_b64 -- PC-relative offsets after it are not relabeled; "
                         "keep the code between it and its use the same size".format(addr))
    return labels, warns


def rawify(it, why):
    it["raw"] = why
    it["text"] = ".long " + ", ".join("0x{:08x}".format(w) for w in it["words"]) + "  // " + it["orig"]


def write_asm(path, src, mcpu, target, cov, funcs, kd_blocks, meta, insts, labels, no_addr):
    """Write the .s; returns {line_number: index into insts}."""
    func_at = {v[0]: (n, v) for n, v in funcs.items()}
    out, line_map = [], {}
    nlines = [0]

    def emit(s=""):
        out.append(s)
        nlines[0] += s.count("\n") + 1

    emit("// disassembled from {} by co2s.py".format(os.path.basename(src)))
    emit("// rebuild: clang -x assembler -target amdgcn-amd-amdhsa -mcpu={} -mcode-object-version={} "
         "-c {} -o k.o && ld.lld -shared k.o -o k.co".format(mcpu, cov, os.path.basename(path)))
    emit()
    emit('\t.amdgcn_target "{}"'.format(target))
    emit("\t.amdhsa_code_object_version {}".format(cov))
    emit()
    emit("\t.text")
    open_func = None
    for i, it in enumerate(insts):
        addr = it["addr"]
        if addr in func_at:
            name, (_, bind, vis) = func_at[addr]
            if open_func:
                emit(".Lfunc_end_{0}:\n\t.size {0}, .Lfunc_end_{0}-{0}\n".format(open_func))
            if bind == "GLOBAL":
                emit("\t.globl {}".format(name))
            if vis == "PROTECTED":
                emit("\t.protected {}".format(name))
            emit("\t.p2align 8")
            emit("\t.type {},@function".format(name))
            emit("{}:".format(name))
            open_func = name
        elif addr in labels:
            emit("{}:".format(labels[addr]))
        emit("\t{}{}".format(it["text"], "" if no_addr else "  // {:06x}".format(addr)))
        line_map[nlines[0]] = i
    if open_func:
        emit(".Lfunc_end_{0}:\n\t.size {0}, .Lfunc_end_{0}-{0}".format(open_func))
    emit()
    emit("\t.rodata")
    for block in kd_blocks.values():
        emit("\t.p2align 6")
        for l in block:
            emit(l if l.startswith((".amdhsa_kernel", ".end_amdhsa_kernel")) else "\t" + l)
        emit()
    emit("\t.amdgpu_metadata")
    emit(meta)
    emit("\t.end_amdgpu_metadata")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    return line_map


# ------------------------------------------------------------- rebuild
def rebuild(s_path, mcpu, cov, workdir):
    obj, co = os.path.join(workdir, "k.o"), os.path.join(workdir, "k.co")
    p = subprocess.run([tool("clang"), "-x", "assembler", "-target", "amdgcn-amd-amdhsa", "-mcpu=" + mcpu,
                        "-mcode-object-version={}".format(cov), "-c", s_path, "-o", obj],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        bad = [int(n) for n in re.findall(r"^{}:(\d+):\d+: error".format(re.escape(s_path)), p.stderr, re.M)]
        return None, bad, p.stderr
    run([tool("ld.lld"), "-shared", obj, "-o", co])
    return co, [], ""


def mismatches(insts, new_insts, exact):
    """Indices whose rebuilt instruction is not acceptable; [first] only once the layout shifted."""
    new_at = {n["addr"] - new_insts[0]["addr"]: n for n in new_insts}
    base = insts[0]["addr"]
    bad, n_equiv = [], 0
    for i, it in enumerate(insts):
        n = new_at.get(it["addr"] - base)
        if n is None or len(n["words"]) != len(it["words"]):
            return [i], n_equiv
        if n["words"] == it["words"]:
            continue
        if not exact and "raw" not in it and n["orig"] == it["orig"]:
            n_equiv += 1
            continue
        bad.append(i)
    return bad, n_equiv


def compare(src, co, kds, n_equiv):
    ok = True
    _, t0 = section(src, ".text")
    _, t1 = section(co, ".text")
    if t0 == t1:
        print("  .text      identical ({} bytes)".format(len(t1)))
    elif len(t0) == len(t1) and n_equiv:
        print("  .text      same size ({} bytes), {} instruction(s) differ only in bits the disassembler "
              "does not show; disassembly identical".format(len(t1), n_equiv))
    else:
        ok = False
        print("  .text      DIFFERS")
    for kd in kds:
        a, b = kd_bytes(src, kd), kd_bytes(co, kd)
        ok &= a == b
        print("  KD         {} {}".format("identical" if a == b else "DIFFERS", kd))
        if a != b:
            print("    orig " + a.hex() + "\n    new  " + b.hex())
    same = metadata_yaml(src) == metadata_yaml(co)
    ok &= same
    print("  metadata   {}".format("identical" if same else "DIFFERS"))
    h0, h1 = elf_header(src), elf_header(co)
    desc = lambda h: "{} {} ABI {}".format(h[0], ",".join(h[1]) or "-", h[2])
    if h0 == h1:
        print("  ELF flags  identical ({})".format(desc(h1)))
    elif h0[0] == h1[0] and h0[2] == h1[2]:
        print("  ELF flags  WARN xnack/sramecc mode differs: original [{}], rebuilt [{}]. The local clang "
              "decides this for the target; the code is unchanged".format(desc(h0), desc(h1)))
    else:
        ok = False
        print("  ELF flags  DIFFERS: original [{}], rebuilt [{}]".format(desc(h0), desc(h1)))
    return ok


def main(disassembler=disassemble):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("co")
    ap.add_argument("-o", "--out", help="output .s (default: <co without .co>.s)")
    ap.add_argument("--mcpu", help="override target (default: from ELF flags)")
    ap.add_argument("--exact", action="store_true", help="require bit-identical .text")
    ap.add_argument("--no-addr", action="store_true", help="omit the trailing // address comments")
    ap.add_argument("--no-verify", action="store_true", help="do not rebuild; no .long fallback")
    ap.add_argument("--keep", help="copy the rebuilt .co here")
    args = ap.parse_args()

    gfx, feats, abi = elf_header(args.co)
    if gfx != "gfx942" and disassembler is disassemble:
        sys.exit("use an architecture-specific co2s frontend for " + gfx)
    cov = ABI_TO_COV.get(abi)
    if not cov:
        sys.exit("unsupported ELF ABI version {}".format(abi))
    mcpu = args.mcpu or target_id(gfx, feats)
    target = "amdgcn-amd-amdhsa--" + mcpu
    meta = metadata_yaml(args.co)

    funcs, kds = symbols(args.co)
    kd_blocks = {kd: kernel_descriptor(mcpu, args.co, kd) for kd in kds}
    insts = disassembler(mcpu, args.co)
    if not insts:
        sys.exit("no instructions in .text")
    labels, warns = relabel(insts, funcs)
    for it in insts:
        if it.get("raw_reason"):
            rawify(it, it["raw_reason"])
        elif "<unknown>" in it["orig"] or it["orig"].startswith(";"):
            rawify(it, "undecodable")

    out = args.out or os.path.splitext(args.co)[0] + ".s"
    line_map = write_asm(out, args.co, mcpu, target, cov, funcs, kd_blocks, meta, insts, labels, args.no_addr)
    print("wrote {}: {} kernel(s), {} instructions, {} labels, target {}, code object v{}".format(
        out, len(kds), len(insts), len(labels), target, cov))
    for kd, block in kd_blocks.items():
        for l in block:
            m = re.match(r";\s*(\w+)\s+(\d+)$", l)
            if m and m.group(2) != "0":
                print("WARN {}: KD field {}={} has no directive and will be rebuilt as 0".format(kd, *m.groups()))
    for w in warns:
        print("WARN " + w)
    if args.no_verify:
        return 0

    work = tempfile.mkdtemp(prefix="co2s_")
    co, n_equiv = None, 0
    for _round in range(MAX_FIX_ROUNDS):
        co, bad_lines, err = rebuild(out, mcpu, cov, work)
        if co is None:
            idx = sorted({line_map[n] for n in bad_lines if n in line_map})
            why = "assembler rejects"
            if not idx:
                print("assembler error outside the instruction stream:\n" + err[:3000])
                return 1
        else:
            idx, n_equiv = mismatches(insts, disassembler(mcpu, co), args.exact)
            why = "different bytes" if args.exact else "different disassembly"
            if not idx:
                break
        for i in idx:
            if "raw" in insts[i]:
                print("cannot fix instruction at 0x{:x}: {}".format(insts[i]["addr"], insts[i]["orig"]))
                return 1
            rawify(insts[i], why)
        line_map = write_asm(out, args.co, mcpu, target, cov, funcs, kd_blocks, meta, insts, labels, args.no_addr)
    else:
        print("gave up after {} fix rounds".format(MAX_FIX_ROUNDS))
        return 1

    raw = [it for it in insts if "raw" in it]
    print("kept as .long: {} of {} instruction(s)".format(len(raw), len(insts)))
    kinds = {}
    for it in raw:
        key = (it["orig"].split()[0], it["raw"])
        kinds[key] = kinds.get(key, 0) + 1
    for (mn, why), n in sorted(kinds.items(), key=lambda x: -x[1]):
        print("  {:6d}  {:40s} {}".format(n, mn, why))
    print("rebuild check:")
    ok = compare(args.co, co, kds, n_equiv)
    if args.keep:
        shutil.copyfile(co, args.keep)
        print("rebuilt .co copied to " + args.keep)
    shutil.rmtree(work, ignore_errors=True)
    print("ROUND-TRIP OK" if ok else "ROUND-TRIP MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
