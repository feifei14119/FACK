#!/usr/bin/env bash
# 启动 FACK 交互式控制台 (后端 server.py + 静态页面), 绑定 0.0.0.0,
# 同网段其它机器可用 http://<本机IP>:<PORT> 访问。
#
#   ./serve.sh [PORT]        # 默认端口 8080
set -euo pipefail

PORT="${1:-8080}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# server.py 需要 Python 3.7+ (ThreadingHTTPServer); 优先 python3.8, 回退 python3。
PY=""
for cand in python3.8 python3.9 python3.10 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "[serve] 未找到 python3.7+ " >&2
  exit 1
fi

exec "$PY" server.py "$PORT"
