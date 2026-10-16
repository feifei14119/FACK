"""Append verified result files and commit only publication changes, then push."""
from contextlib import contextmanager
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib.parse import quote

START = "<!-- fack:tuning-results:start -->"
END = "<!-- fack:tuning-results:end -->"
MARKER = re.compile(r"<!-- fack:result:([0-9a-f]{64}) -->")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def safe_path(repo, relative):
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts or "\\" in relative or rel.as_posix() != relative:
        raise ValueError("invalid publication path: " + relative)
    path = repo / relative
    current = path
    while current != repo:
        if current.is_symlink():
            raise ValueError("publication path is a symlink: " + relative)
        current = current.parent
    return path


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".publish-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(name, 0o644)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def git(repo, *args, data=None, env=None, allowed=(0,)):
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git {} timed out; inspect the existing commit before retrying".format(args[0])) from exc
    if result.returncode not in allowed:
        raise RuntimeError("git {} failed: {}".format(args[0], result.stderr.decode(errors="replace")[-2000:].strip()))
    return result.stdout


def git_file(repo, revision, filename):
    spec = revision + ":" + filename
    if not git(repo, "ls-tree", revision, "--", filename):
        return None
    return git(repo, "show", spec)


def index_file(repo, filename):
    entries = git(repo, "ls-files", "--stage", "--", filename).decode().splitlines()
    if not entries:
        return None
    if len(entries) != 1 or entries[0].split()[2] != "0":
        raise ValueError("publication path has unresolved index conflicts: " + filename)
    return git(repo, "show", ":" + filename)


def cell(value):
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\n", " ").replace("[", "&#91;").replace("]", "&#93;")


def table_row(record):
    shown = record.get("display_inputs", record["workload"]["inputs"])
    ordered = sorted(shown, key=lambda k: ({"m": 0, "n": 1, "k": 2}.get(k, 3), k))
    inputs = "; ".join("{}={}".format(k.upper() if k in ("m", "n", "k") else k,
                         json.dumps(shown[k], ensure_ascii=False, sort_keys=True) if isinstance(shown[k], (dict, list)) else shown[k])
                       for k in ordered)
    gains = "<br>".join("{}: {:+.2f}%".format(cell(name), (value["median_ratio"] - 1) * 100)
                       for name, value in sorted(record["methods"].items()))
    when = record["finished_at"] + "（耗时 {:.1f} 分钟）".format(record["duration_seconds"] / 60)
    return "| {} <!-- fack:result:{} --> | [{}]({}) | {} | {} | {} |".format(
        record["number"], record["id"], cell(record["relative_path"]), quote(record["archive_path"], safe="/"),
        cell(inputs), gains, cell(when))


def append_readme(raw, row, identity):
    text = raw.decode("utf-8")
    if identity in MARKER.findall(text):
        if row not in text:
            raise ValueError("existing README result differs from its recorded row")
        return raw
    if START not in text and END not in text:
        text = text.rstrip() + "\n\n" + START + "\n\n" + (
            "以下为各输入尺寸下通过最终验证的候选，性能提升按配对比值计算；不表示整份 `.co` 的所有尺寸均可替换。\n\n"
            "| 序号 | co 名字（含路径） | 输入尺寸 | 性能提升 | 调优时间（UTC） |\n"
            "|---|---|---|---|---|\n") + END + "\n"
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise ValueError("README tuning-results markers are incomplete or duplicated")
    return text.replace(END, row + "\n" + END).encode("utf-8")


@contextmanager
def publication_lock(repo):
    common = Path(git(repo, "rev-parse", "--git-common-dir").decode().strip())
    if not common.is_absolute():
        common = repo / common
    with (common / "fack-publication.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _push(repo, branch):
    remote = git(repo, "config", "--get", "branch." + branch + ".remote", allowed=(0, 1)).decode().strip() or "origin"
    merge = git(repo, "config", "--get", "branch." + branch + ".merge", allowed=(0, 1)).decode().strip() or "refs/heads/" + branch
    if remote == "." or not merge.startswith("refs/heads/"):
        raise ValueError("publication requires a remote branch, not a local tracking branch")
    git(repo, "push", remote, "HEAD:" + merge)
    return remote + "/" + merge[len("refs/heads/"):]


def publish(repo, plan):
    """Idempotent by code object, baseline and exact inputs; never stage unrelated edits."""
    repo = Path(repo).resolve()
    with publication_lock(repo):
        branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip()
        head = git(repo, "rev-parse", "HEAD").decode().strip()
        output = plan["publication"]["output_dir"]
        relative = plan["relative_path"]
        safe_path(repo, output)
        safe_path(repo, relative)
        identity = digest(json_bytes({k: plan[k] for k in (
            "client", "relative_path", "co_sha256", "original_sha256", "inputs_identity")}))
        record_path = output + "/records/" + identity + ".json"
        stored = git_file(repo, head, record_path)
        if stored is not None:
            record = json.loads(stored)
            # Retry after a push failure without overwriting a newer canonical .co.
            archive = git_file(repo, head, record["archive_path"])
            if archive is None or digest(archive) != record["co_sha256"] or table_row(record) not in git_file(repo, head, "README.md").decode():
                raise ValueError("committed publication evidence changed")
            commit = git(repo, "log", "-1", "--format=%H", "--", record_path).decode().strip()
            return dict(status="published", cached=True, id=identity, commit=commit,
                        remote=_push(repo, branch), code_object=str(repo / record["latest_path"]))

        readme_path = safe_path(repo, "README.md")
        original_readme = git_file(repo, head, "README.md")
        staged_readme, working_readme = index_file(repo, "README.md"), readme_path.read_bytes()
        if original_readme is None or staged_readme is None:
            raise ValueError("README.md must exist in HEAD and index before publication")
        known = set(MARKER.findall(original_readme.decode()))
        for version in (staged_readme, working_readme):
            ids = set(MARKER.findall(version.decode()))
            if ids - known - {identity} or known - ids:
                raise ValueError("README has another pending or removed publication; finish it first")
        numbers = re.findall(r"^\| (\d+) <!-- fack:result:", original_readme.decode(), re.M)
        number = max(map(int, numbers), default=0) + 1
        latest = output + "/" + relative
        archive = output + "/.versions/" + plan["co_sha256"] + "/" + relative
        assembly = output + "/.sources/" + plan["source_sha256"] + ".s"
        record = {k: v for k, v in plan.items() if k not in ("publication", "code_object", "assembly", "inputs_identity")}
        record.update(schema_version=1, id=identity, number=number, latest_path=latest,
                      archive_path=archive, assembly_path=assembly, recommendation_scope="workload")
        row = table_row(record)
        head_readme = append_readme(original_readme, row, identity)
        new_index_readme = append_readme(staged_readme, row, identity)
        new_work_readme = append_readme(working_readme, row, identity)
        files = {latest: plan["code_object"], archive: plan["code_object"],
                 assembly: plan["assembly"], record_path: json_bytes(record)}
        for filename, data in files.items():
            destination = safe_path(repo, filename)
            previous = git_file(repo, head, filename)
            staged = index_file(repo, filename)
            working = destination.read_bytes() if destination.exists() else None
            if staged not in (previous, data) or working not in (previous, data):
                raise ValueError("publication would overwrite modified output: " + filename)
            if filename != latest and previous not in (None, data):
                raise ValueError("immutable publication archive differs: " + filename)
        for filename, data in files.items():
            atomic(safe_path(repo, filename), data)
        atomic(readme_path, new_work_readme)

        # A private index commits HEAD + precisely these generated bytes. The
        # user's staged/unstaged README edits are preserved in their own versions.
        with tempfile.TemporaryDirectory(prefix="fack-publish-") as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
            git(repo, "read-tree", head, env=env)
            entries = dict(files, **{"README.md": head_readme})
            for filename, data in entries.items():
                oid = git(repo, "hash-object", "-w", "--stdin", data=data).decode().strip()
                git(repo, "update-index", "--add", "--cacheinfo", "100644", oid, filename, env=env)
            if git(repo, "rev-parse", "HEAD").decode().strip() != head:
                raise ValueError("HEAD changed during publication; retry explicitly")
            message = Path(directory) / "message.txt"
            message.write_text("Publish tuning result #{}: {}\n\nWorkload-scoped result {}.\n".format(number, relative, identity))
            git(repo, "commit", "-F", str(message), env=env)
        commit = git(repo, "rev-parse", "HEAD").decode().strip()
        for filename, data in dict(files, **{"README.md": new_index_readme}).items():
            oid = git(repo, "hash-object", "-w", "--stdin", data=data).decode().strip()
            git(repo, "update-index", "--add", "--cacheinfo", "100644", oid, filename)
        return dict(status="published", cached=False, id=identity, commit=commit,
                    remote=_push(repo, branch), code_object=str(repo / latest))
