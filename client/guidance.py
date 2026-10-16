"""Read-only client/architecture skill composition for any agent frontend."""
import hashlib
import json
from pathlib import Path
import re

from harness.validation import validate_contract

REPO = Path(__file__).resolve().parent.parent
ARCHITECTURES = REPO / "knowledge/architectures.json"


def source_arch(source):
    match = re.search(r'^\s*\.amdgcn_target\s+"[^"\n]*--(gfx[0-9a-f]+)(?=[:"])', source, re.M)
    return match[1] if match else None


def skill_snapshot(relative, role):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.name != "SKILL.md":
        raise ValueError("skill must be a repository-relative SKILL.md: " + str(relative))
    resolved = (REPO / path).resolve()
    if REPO not in resolved.parents:
        raise ValueError("skill resolves outside repository: " + str(relative))
    if not resolved.is_file():
        raise ValueError("declared skill dependency missing: " + str(relative))
    raw = resolved.read_bytes()
    return {"role": role, "path": path.as_posix(), "resolved_path": resolved.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(), "content": raw.decode("utf-8")}


def compose(client, ctx, arch=None):
    hook = getattr(client.module, "agent_profile", None)
    if hook is not None and not callable(hook):
        raise ValueError("client agent_profile must be callable")
    declaration = hook(ctx) if hook else {}
    if not isinstance(declaration, dict) or set(declaration) - {"arch", "skills", "validation", "workload", "instructions", "requires_workload"}:
        raise ValueError("invalid client agent_profile declaration")
    candidates = [x for x in (arch, source_arch(ctx.seed_src), declaration.get("arch")) if x is not None]
    if any(not isinstance(x, str) or not re.fullmatch(r"gfx[0-9a-f]+", x) for x in candidates):
        raise ValueError("architecture must be a gfx identifier")
    if len(set(candidates)) > 1:
        raise ValueError("selected architecture, seed and client architecture disagree")
    selected = candidates[0] if candidates else None
    registry = json.loads(ARCHITECTURES.read_text())
    client_skills = declaration.get("skills", [])
    if not isinstance(client_skills, list) or any(not isinstance(p, str) for p in client_skills):
        raise ValueError("client skills must be a list of paths")
    if not isinstance(declaration.get("instructions", []), list) or any(
            not isinstance(x, str) for x in declaration.get("instructions", [])):
        raise ValueError("client instructions must be a list of strings")
    if type(declaration.get("requires_workload", False)) is not bool:
        raise ValueError("requires_workload must be a boolean")
    if declaration.get("workload") is not None and not isinstance(declaration["workload"], dict):
        raise ValueError("client workload must be an object")
    if not isinstance(registry, dict) or any(
            not isinstance(v, list) or any(not isinstance(p, str) for p in v) for v in registry.values()):
        raise ValueError("architecture registry must map targets to lists of skill paths")
    skills = [skill_snapshot(p, "client") for p in dict.fromkeys(client_skills)]
    skills += [skill_snapshot(p, "architecture") for p in registry.get(selected, [])]
    return {"schema_version": 1, "client": client.spec, "arch": selected,
            "client_profile_status": ("workload_unbound" if declaration.get("requires_workload") else "declared") if hook else "legacy_score_only",
            "architecture_skill_status": "available" if selected in registry else "unavailable",
            "skills": skills, "validation": validate_contract(declaration.get("validation")),
            "workload": declaration.get("workload"), "instructions": declaration.get("instructions", [])}
