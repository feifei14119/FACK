#!/usr/bin/env python3
"""FACK 交互式控制台后端 (Python 3.8+ 标准库, 零依赖).

- 提供 webUI/ 下的静态页面 (控制台 index.html + 帮助 help.html)。
- 提供一组 API, 让网页按钮真正启动/监控/停止 FACK 的调优、学习(挖掘)、
  测试、验证等作业, 并把子进程输出实时流回页面。
- 只允许一份白名单动作 (ACTIONS), 参数以 argv 列表传给子进程 (不用 shell,
  杜绝命令注入)。

启动:  python3 server.py [PORT]     # 默认 8080, 绑定 0.0.0.0 供局域网访问
"""
import json
import os
import re
import shlex
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:  # Python 3.7+
    from http.server import ThreadingHTTPServer
except ImportError:  # Python 3.6 兼容
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                 # webUI 的上一级 = 仓库根
sys.path.insert(0, REPO)
import client as _clients  # noqa: E402
from webUI.results import read_results as _read_results, campaign_results  # noqa: E402
from webUI.campaigns import read_campaigns, read_export  # noqa: E402
from webUI.workloads import read_plans  # noqa: E402
from webUI.workflow import ACTIONS as WORKFLOW_ACTIONS, command as workflow_command  # noqa: E402
RUNS_DIR = os.path.join(HERE, ".runs")       # 作业日志落这里
os.makedirs(RUNS_DIR, exist_ok=True)

PY = sys.executable or "python3"
# 仓库里很多入口指定 python3.8; 若存在优先用它跑引擎作业。
PY38 = "python3.8"

REGIONS = {"loop", "prologue", "epilogue", "inter", "body", "outlined", "all", "auto",
           "loop#0", "loop#1", "loop#2"}
_LOOP_AT = re.compile(r"^loop@[A-Za-z_.$][\w.$]*$")


def _region_ok(region):
    return region in REGIONS or bool(_LOOP_AT.match(region or ""))

# ------------------------------------------------------------------ jobs
_jobs = {}          # id -> job dict
_jobs_lock = threading.Lock()


def _clip_int(v, lo, hi, default):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _tokens(s):
    """把透传参数字符串安全拆成 argv token (按 shell 词法, 但不执行 shell)。"""
    if not s:
        return []
    try:
        return shlex.split(s)
    except ValueError:
        return s.split()


def build_command(action, p):
    """返回 (title, argv, cwd, env_extra) 或抛 ValueError。p 是前端传来的参数 dict。"""
    p = p or {}

    if action in WORKFLOW_ACTIONS:
        try:
            return workflow_command(action, p, REPO)
        except (OSError, KeyError, TypeError) as exc:
            raise ValueError("workload 操作参数或依赖不完整: " + str(exc))

    if action == "tune":
        client_params, selected_env = None, {}
        if p.get("plan"):
            _, validation, _, selected_env = workflow_command("dispatch_validate", p, REPO)
            p = dict(p, seed=validation[2], client="aiter/hsa/gfx942")
            client_params = validation[validation.index("--") + 1:]
        region = p.get("region", "loop")
        if not _region_ok(region):
            raise ValueError("非法 region: %s" % region)
        seed = (p.get("seed") or "").strip()
        if not seed:
            raise ValueError("缺少 seed 路径（.s 汇编）")
        if not seed.endswith(".s"):
            raise ValueError("seed 必须是 .s 汇编文件")
        seed_abs = seed if os.path.isabs(seed) else os.path.join(REPO, seed)
        if not os.path.isfile(seed_abs):
            raise ValueError("seed 文件不存在: %s" % seed)
        spec = (p.get("client") or "").strip()
        if not spec:
            raise ValueError("缺少 client（例如 aiter/hsa/gfx942）")
        try:
            spec = _clients.resolve(spec).spec
        except ValueError as exc:
            raise ValueError("非法 client: %s" % exc)
        rounds = _clip_int(p.get("rounds"), 1, 100, 5)
        loop = _clip_int(p.get("loop"), 1, 1000, 20)
        argv = ["node", "tools/sdk/tune.mjs", seed_abs,
                "--client", spec,
                "--rounds", str(rounds),
                "--region", region,
                "--loop", str(loop)]
        argv.append("--transcript" if p.get("transcript") else "--no-transcript")
        argv.append("--results")
        if p.get("model"):
            argv += ["--model", str(p["model"]).strip()]
        for field, flag, label in (("policy", "--comparison-policy", "比较"),
                                   ("search_policy", "--search-policy", "搜索")):
            if p.get(field):
                policy = str(p[field]).strip()
                policy = policy if os.path.isabs(policy) else os.path.join(REPO, policy)
                if not os.path.isfile(policy):
                    raise ValueError(label + "策略文件不存在")
                argv += [flag, policy]
        argv += ["--"] + (client_params if client_params is not None else _tokens(p.get("params")))
        env = dict(selected_env)
        if p.get("apikey"):
            env["CURSOR_API_KEY"] = str(p["apikey"]).strip()
        return ("调优 tune.mjs · region=%s rounds=%d" % (region, rounds),
                argv, REPO, env)

    if action == "tune_quick":
        raise ValueError("旧 poc_kl 脚本已移除，请选择 CSV workload")

    if action == "tune_tail":
        raise ValueError("旧 poc_kl 脚本已移除，请选择 CSV workload")

    if action == "mine":
        corpus = (p.get("corpus") or "").strip()
        out = (p.get("out") or "study_case/study_out").strip()
        argv = [shutil.which(PY38) or PY, "tools/mine_corpus.py"]
        if corpus:
            argv += ["--corpus", corpus]
        if out:
            argv += ["--out", out]
        return ("学习/挖掘 mine_corpus.py (Layer 1)", argv, REPO, {})

    if action == "mine_full":
        raise ValueError("普通调优复用已有 skill；请使用独立的静态挖掘或自学流程")

    if action == "articulate":
        argv = ["node", "tools/sdk/articulate.mjs"]
        if p.get("dry"):
            argv.append("--dry-run")
        env = {}
        if p.get("apikey"):
            env["CURSOR_API_KEY"] = str(p["apikey"]).strip()
        return ("Layer 2 离线 AI 归纳 articulate.mjs", argv, REPO, env)

    if action == "test":
        return ("运行 CPU 单元测试 pytest",
                [PY, "-m", "pytest", "-q", "unittests"],
                REPO, {})

    if action == "hw_validate":
        raise ValueError("请使用逐 workload 的 client / op_test 验证")

    raise ValueError("未知动作: %s" % action)


def _run_job(job):
    logpath = job["logfile"]
    env = dict(os.environ)
    env.update(job["env"])
    header = "$ %s\n(cwd=%s)\n%s\n" % (
        " ".join(shlex.quote(a) for a in job["argv"]),
        job["cwd"], "-" * 60)
    with open(logpath, "w", encoding="utf-8", errors="replace") as lf:
        lf.write(header)
        lf.flush()
        try:
            proc = subprocess.Popen(
                job["argv"], cwd=job["cwd"], env=env,
                stdout=lf, stderr=subprocess.STDOUT,
                start_new_session=True)  # 独立进程组, 便于整组 kill
        except FileNotFoundError as e:
            lf.write("\n[启动失败] %s\n" % e)
            _finish(job, -1)
            return
        with _jobs_lock:
            job["pid"] = proc.pid
            job["status"] = "running"
        rc = proc.wait()
    _finish(job, rc)


def _finish(job, rc):
    with _jobs_lock:
        job["returncode"] = rc
        job["ended"] = time.time()
        if job["status"] == "stopping":
            job["status"] = "stopped"
        else:
            job["status"] = "done" if rc == 0 else "failed"


def start_job(action, params):
    title, argv, cwd, env = build_command(action, params)
    jid = time.strftime("%H%M%S-") + uuid.uuid4().hex[:6]
    job = {
        "id": jid, "action": action, "title": title, "argv": argv,
        "cwd": cwd, "env": env, "status": "starting", "pid": None,
        "returncode": None, "started": time.time(), "ended": None,
        "logfile": os.path.join(RUNS_DIR, jid + ".log"),
    }
    with _jobs_lock:
        _jobs[jid] = job
    t = threading.Thread(target=_run_job, args=(job,), daemon=True)
    t.start()
    return job


def stop_job(jid):
    with _jobs_lock:
        job = _jobs.get(jid)
        if not job:
            return False
        if job["status"] not in ("running", "starting"):
            return True
        job["status"] = "stopping"
        pid = job["pid"]
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    return True


def job_public(job):
    return {
        "id": job["id"], "action": job["action"], "title": job["title"],
        "status": job["status"], "returncode": job["returncode"],
        "started": job["started"], "ended": job["ended"],
        "elapsed": round((job["ended"] or time.time()) - job["started"], 1),
        "cmd": " ".join(shlex.quote(a) for a in job["argv"]),
    }


# ------------------------------------------------------------------ results
def read_results():
    result = _read_results(REPO, _clients.list_clients())
    remote = campaign_results(REPO)
    result['results'] = remote['results'] + result['results']
    result['errors'] += remote['errors']
    return result


def list_skills():
    res = {}
    for label, rel in (("store", os.path.join("knowledge", "engine", "skills")),
                       ("study", os.path.join("study_case", "study_out", "skills"))):
        p = os.path.join(REPO, rel)
        names = []
        if os.path.isdir(p):
            names = sorted(n for n in os.listdir(p) if n.endswith(".json"))
        res[label] = names
    from pathlib import Path
    res['agent'] = sorted(p.parent.name for p in (Path(REPO) / 'knowledge/skills').glob('*/SKILL.md'))
    return res


# ------------------------------------------------------------------ HTTP
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "FACKConsole/1.0"

    def log_message(self, *a):
        pass  # 静音默认访问日志

    # ---- helpers ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    # ---- GET ----
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path.startswith("/api/"):
            return self._api_get(path, parse_qs(u.query))
        return self._static(path)

    def _api_get(self, path, q):
        if path == "/api/health":
            return self._json({"ok": True, "repo": REPO, "py38": _which(PY38)})
        if path == "/api/actions":
            return self._json({"regions": sorted(REGIONS)})
        if path == "/api/jobs":
            with _jobs_lock:
                jobs = [job_public(j) for j in _jobs.values()]
            jobs.sort(key=lambda j: j["started"], reverse=True)
            return self._json({"jobs": jobs})
        if path == "/api/job":
            jid = (q.get("id") or [""])[0]
            offset = _clip_int((q.get("offset") or ["0"])[0], 0, 10**12, 0)
            with _jobs_lock:
                job = _jobs.get(jid)
            if not job:
                return self._json({"error": "no such job"}, 404)
            chunk, size = _read_log(job["logfile"], offset)
            pub = job_public(job)
            pub["offset"] = size
            pub["log"] = chunk
            return self._json(pub)
        if path == "/api/results":
            return self._json(read_results())
        if path == "/api/workloads":
            return self._json(read_plans(REPO))
        if path == "/api/campaigns":
            return self._json(read_campaigns(REPO))
        if path == "/api/campaign/export":
            try:
                export = read_export(REPO, (q.get('campaign') or [''])[0], (q.get('file') or [''])[0])
            except (OSError, ValueError, TypeError) as exc:
                return self._json({'error': str(exc)}, 404)
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(export['payload'])))
            self.send_header('Content-Disposition', 'attachment; filename="%s"' % export['name'])
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(export['payload'])
            return
        if path == "/api/skills":
            return self._json({"skills": list_skills()})
        if path == "/api/defaults":
            return self._json(_defaults())
        return self._json({"error": "not found"}, 404)

    # ---- POST ----
    def do_POST(self):
        u = urlparse(self.path)
        body = self._read_body()
        if u.path == "/api/run":
            action = body.get("action", "")
            try:
                job = start_job(action, body.get("params") or {})
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json(job_public(job))
        if u.path == "/api/stop":
            ok = stop_job(body.get("id", ""))
            return self._json({"ok": ok})
        return self._json({"error": "not found"}, 404)

    # ---- static ----
    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        full = os.path.normpath(os.path.join(HERE, rel))
        if not full.startswith(HERE) or not os.path.isfile(full):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = STATIC_TYPES.get(ext, "application/octet-stream")
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def _read_log(path, offset):
    if not os.path.isfile(path):
        return "", 0
    size = os.path.getsize(path)
    if offset >= size:
        return "", size
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read()
    return data.decode("utf-8", errors="replace"), size


def _which(name):
    from shutil import which
    return which(name) is not None


def _defaults():
    return {
        "seed": "",
        "client": "aiter/hsa/gfx942",
        "params": "",
        "region": "loop",
        "rounds": 5,
        "loop": 20,
        "corpus": "study_case/gold_corpus",
        "out": "study_case/study_out",
    }


def _local_ips():
    ips = []
    try:
        out = subprocess.check_output(["hostname", "-I"], universal_newlines=True)
        for ip in out.split():
            if ":" not in ip and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips


def main():
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    bar = "=" * 70
    print(bar)
    print(" FACK 交互式控制台 —— 已在局域网启动 (端口 %d)" % port)
    print("-" * 70)
    print(" 本机访问:   http://127.0.0.1:%d" % port)
    for ip in _local_ips():
        print(" 局域网访问: http://%s:%d" % (ip, port))
    print("-" * 70)
    print(" 帮助页:     /help.html      仓库根: %s" % REPO)
    print(" 按 Ctrl+C 停止。若其它机器打不开, 请检查防火墙是否放行 %d。" % port)
    print(bar)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] 正在停止...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
