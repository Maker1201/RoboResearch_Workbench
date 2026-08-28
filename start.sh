#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/apps/server"
WEB_DIR="$ROOT_DIR/apps/web"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8770}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5176}"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\033[1;36m[start]\033[0m %s\n' "$1"
}

fail() {
  printf '\033[1;31m[start:error]\033[0m %s\n' "$1" >&2
  exit 1
}

port_is_open() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys
host, port = sys.argv[1], int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.4)
    sys.exit(0 if sock.connect_ex((host, port)) == 0 else 1)
PY
}

find_free_port() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys
host, start = sys.argv[1], int(sys.argv[2])
for port in range(start, start + 50):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            continue
        print(port)
        break
else:
    raise SystemExit(1)
PY
}

backend_healthy() {
  python3 - "$BACKEND_HOST" "$BACKEND_PORT" <<'PY'
import sys
import urllib.request
host, port = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

cleanup() {
  log "正在停止服务..."
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

[[ -d "$SERVER_DIR" ]] || fail "找不到后端目录：$SERVER_DIR"
[[ -d "$WEB_DIR" ]] || fail "找不到前端目录：$WEB_DIR"
[[ -x "$SERVER_DIR/.venv/bin/uvicorn" ]] || fail "找不到 $SERVER_DIR/.venv/bin/uvicorn，请先在 apps/server 安装后端依赖。"
[[ -d "$WEB_DIR/node_modules" ]] || fail "找不到 $WEB_DIR/node_modules，请先在 apps/web 运行 npm install。"

if port_is_open "$BACKEND_HOST" "$BACKEND_PORT"; then
  if backend_healthy; then
    log "后端已在 http://$BACKEND_HOST:$BACKEND_PORT 运行，将复用该服务。"
  else
    fail "端口 $BACKEND_PORT 已被占用，但不是 RoboResearch 后端。请换 BACKEND_PORT 或先停止占用进程。"
  fi
else
  log "启动后端：http://$BACKEND_HOST:$BACKEND_PORT"
  (
    cd "$SERVER_DIR"
    exec .venv/bin/uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  ) &
  BACKEND_PID=$!

  for _ in {1..40}; do
    if backend_healthy; then
      break
    fi
    sleep 0.25
  done
  backend_healthy || fail "后端启动失败，请查看上面的 uvicorn 日志。"
fi

if port_is_open "$FRONTEND_HOST" "$FRONTEND_PORT"; then
  NEW_PORT="$(find_free_port "$FRONTEND_HOST" "$((FRONTEND_PORT + 1))")"
  log "前端端口 $FRONTEND_PORT 已占用，改用 $NEW_PORT。"
  FRONTEND_PORT="$NEW_PORT"
fi

log "启动前端：http://$FRONTEND_HOST:$FRONTEND_PORT"
(
  cd "$WEB_DIR"
  VITE_API_BASE="http://$BACKEND_HOST:$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

log "RoboResearch Workbench 已启动。"
log "前端地址：http://$FRONTEND_HOST:$FRONTEND_PORT"
log "后端地址：http://$BACKEND_HOST:$BACKEND_PORT"
log "按 Ctrl+C 停止本次脚本启动的服务。"

wait "$FRONTEND_PID"
