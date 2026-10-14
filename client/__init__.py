"""Tuning clients: how ONE external project builds, checks and times a candidate.

testft itself only knows the three-phase evaluation contract
(``harness.evaluator.Evaluator`` -> ``EvalResult``). Everything project-specific
-- which program runs, how a candidate ``.s`` is turned into something it loads,
what its correctness verdict and timing lines look like -- lives in a client
under ``client/<project>/``. Projects differ too much (an exe with ``m=/n=/k=``,
a pytest sweep over ``.sp3``, an aiter op benchmark, ...) to share one interface.

A client is a directory holding a ``client.py``. A client SPEC is a path below
``client/``; it names the client and, optionally, a case inside it::

    poc_kl                       -> client/poc_kl/client.py, case ""
    poc_kl/fp8_blockscale_gemm   -> client/poc_kl/client.py, case "fp8_blockscale_gemm"

The nearest ``client.py`` walking up from the spec directory wins, so a case may
ship its own ``client.py`` when it is unlike its siblings. ``client.py`` must
define::

    def make_evaluator(ctx: ClientContext) -> Evaluator

and may define ``describe(ctx) -> str`` (one paragraph on what the case
measures and what its params mean) and ``identity(ctx) -> dict``. The latter
declares ``resources={name: file_path_or_None}`` and ``environment=[names]``;
the loader reads only those files and allowed environment variables. It must
not run tests, import external test code, or list credentials. Runtime outputs go to
``<client dir>/tune_out/``.

CLI (used by tools/sdk/tune.mjs so both sides resolve specs identically)::

    python3 -m client list
    python3 -m client resolve <spec>
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

CLIENT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(CLIENT_ROOT)
CLIENT_FILE = "client.py"
OUT_DIRNAME = "tune_out"


@dataclass
class ClientContext:
    """What the engine hands a client when it needs an evaluator."""
    spec: str                     # "poc_kl/fp8_blockscale_gemm"
    name: str                     # client = dir of client.py, relative: "poc_kl"
    case: str                     # spec below the client dir ("" = none)
    client_dir: str               # absolute dir of client.py
    case_dir: str                 # absolute dir of the spec
    out_dir: str                  # <client_dir>/tune_out
    seed_src: str = ""            # the seed kernel text
    target: object = None         # isa Target of the seed
    params: List[str] = field(default_factory=list)  # forwarded verbatim (after `--`)
    loop: int = 20                # perf repeat hint
    kernel: Optional[str] = None  # explicit kernel symbol, else client decides


class Client:
    def __init__(self, spec: str, name: str, case: str, client_dir: str,
                 case_dir: str, module):
        self.spec, self.name, self.case = spec, name, case
        self.client_dir, self.case_dir = client_dir, case_dir
        self.out_dir = os.path.join(client_dir, OUT_DIRNAME)
        self.module = module

    def context(self, *, seed_src: str = "", params=(), loop: int = 20,
                kernel: Optional[str] = None) -> ClientContext:
        target = None
        if seed_src:
            from isa import registry
            target = registry.target_for_source(seed_src)
        return ClientContext(self.spec, self.name, self.case, self.client_dir,
                             self.case_dir, self.out_dir, seed_src, target,
                             [str(p) for p in params], int(loop), kernel)

    def make_evaluator(self, **kw):
        return self.module.make_evaluator(self.context(**kw))

    def describe(self, **kw) -> str:
        fn = getattr(self.module, "describe", None)
        if fn is not None:
            return fn(self.context(**kw))
        return (self.module.__doc__ or "").strip()

    def identity(self, **kw) -> dict:
        """Read-only optional client identity; legacy clients remain supported."""
        from harness.evidence import collect_identity, unavailable_identity
        fn = getattr(self.module, "identity", None)
        if fn is None:
            return unavailable_identity()
        declaration = fn(self.context(**kw))
        if (not isinstance(declaration, dict) or "resources" not in declaration or
                set(declaration) - {"resources", "environment"}):
            raise ValueError("client identity must declare resources and optional environment")
        return collect_identity(**declaration)

    def info(self) -> dict:
        return {"spec": self.spec, "name": self.name, "case": self.case,
                "client_dir": self.client_dir, "case_dir": self.case_dir,
                "out_dir": self.out_dir}


def _normalize(spec: str) -> str:
    s = spec.strip()
    if os.path.isabs(s):
        s = os.path.relpath(s, CLIENT_ROOT)
    elif s.startswith("client" + os.sep) or s.startswith("client/"):
        s = s[len("client/"):]
    s = os.path.normpath(s).replace(os.sep, "/")
    if s in ("", ".") or s.startswith(".."):
        raise ValueError("client spec {!r} is not below {}".format(spec, CLIENT_ROOT))
    return s


def resolve(spec: str) -> Client:
    """Load the client for ``spec`` (see module doc)."""
    rel = _normalize(spec)
    case_dir = os.path.join(CLIENT_ROOT, rel)
    if not os.path.isdir(case_dir):
        raise ValueError("unknown client {!r}: {} does not exist (known: {})".format(
            spec, case_dir, ", ".join(list_clients()) or "none"))
    d = case_dir
    while True:
        if os.path.isfile(os.path.join(d, CLIENT_FILE)):
            break
        if d == CLIENT_ROOT or os.path.dirname(d) == d:
            raise ValueError("no {} for client {!r} (looked from {} up to {})".format(
                CLIENT_FILE, spec, case_dir, CLIENT_ROOT))
        d = os.path.dirname(d)
    if d == CLIENT_ROOT:
        raise ValueError("client {!r} has no {} of its own".format(spec, CLIENT_FILE))
    name = os.path.relpath(d, CLIENT_ROOT).replace(os.sep, "/")
    case = os.path.relpath(case_dir, d).replace(os.sep, "/")
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    mod_name = "testft_client_" + name.replace("/", "__")
    module = sys.modules.get(mod_name)
    if module is None:
        ms = importlib.util.spec_from_file_location(mod_name, os.path.join(d, CLIENT_FILE))
        module = importlib.util.module_from_spec(ms)
        sys.modules[mod_name] = module
        ms.loader.exec_module(module)
    if not hasattr(module, "make_evaluator"):
        raise ValueError("{} does not define make_evaluator(ctx)".format(
            os.path.join(d, CLIENT_FILE)))
    return Client(rel, name, "" if case == "." else case, d, case_dir, module)


def list_clients() -> List[str]:
    """Every directory below client/ that holds a client.py (relative names)."""
    out = []
    for root, dirs, files in os.walk(CLIENT_ROOT):
        dirs[:] = sorted(x for x in dirs if not x.startswith((".", "_")) and x != OUT_DIRNAME
                         and not os.path.exists(os.path.join(root, x, ".git")))
        if root != CLIENT_ROOT and CLIENT_FILE in files:
            out.append(os.path.relpath(root, CLIENT_ROOT).replace(os.sep, "/"))
    return out


def main(argv: List[str]) -> int:
    if argv[:1] == ["list"]:
        for c in list_clients():
            print(c)
        return 0
    if len(argv) == 2 and argv[0] == "resolve":
        try:
            print(json.dumps(resolve(argv[1]).info()))
        except ValueError as exc:
            sys.stderr.write("{}\n".format(exc))
            return 2
        return 0
    sys.stderr.write("usage: python3 -m client list | resolve <spec>\n")
    return 2
