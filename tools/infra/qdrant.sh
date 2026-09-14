#!/usr/bin/env bash
# Tải, chạy và dừng Qdrant — kho vector của C.Brain.
#
# Vì sao binary chứ không phải Docker: yêu cầu (e) của T0.1 là "chạy trọn trong
# hạ tầng khách hàng, mỗi khách hàng một bản cài đặt" (R2, R6). Không tài liệu
# nào trong 06/07/08 chốt cơ chế đóng gói. Binary native thoả (e) và không đòi
# thêm một tầng hạ tầng nào trên máy khách.
#
# Dùng: tools/infra/qdrant.sh {fetch|start|stop|status}

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="$REPO_ROOT/.runtime/qdrant"
BIN="$RUNTIME_DIR/qdrant"
STORAGE="$RUNTIME_DIR/storage"
LOG="$RUNTIME_DIR/qdrant.log"
PIDFILE="$RUNTIME_DIR/qdrant.pid"

# Cấu hình kết nối sống ở .env — không có mặc định trong mã.
ENV_FILE="$REPO_ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "LỖI: thiếu $ENV_FILE. Chạy: cp .env.example .env" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

require() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "LỖI: thiếu khoá cấu hình '$name' trong .env — từ chối chạy." >&2
    exit 1
  fi
}
require CBRAIN_QDRANT_VERSION
require CBRAIN_QDRANT_HTTP_PORT
require CBRAIN_QDRANT_GRPC_PORT

cmd_fetch() {
  local arch; arch="$(uname -m)"
  local os; os="$(uname -s)"
  local target
  case "$os/$arch" in
    Darwin/arm64)  target="qdrant-aarch64-apple-darwin.tar.gz" ;;
    Darwin/x86_64) target="qdrant-x86_64-apple-darwin.tar.gz" ;;
    Linux/aarch64) target="qdrant-aarch64-unknown-linux-musl.tar.gz" ;;
    Linux/x86_64)  target="qdrant-x86_64-unknown-linux-musl.tar.gz" ;;
    *) echo "LỖI: chưa hỗ trợ $os/$arch" >&2; exit 1 ;;
  esac

  mkdir -p "$RUNTIME_DIR"
  local url="https://github.com/qdrant/qdrant/releases/download/${CBRAIN_QDRANT_VERSION}/${target}"
  echo "Tải $url"
  curl -fL --retry 3 -o "$RUNTIME_DIR/$target" "$url"
  tar -xzf "$RUNTIME_DIR/$target" -C "$RUNTIME_DIR"
  rm -f "$RUNTIME_DIR/$target"
  chmod +x "$BIN"
  echo "Đã đặt binary tại $BIN"
  "$BIN" --version
}

cmd_start() {
  [[ -x "$BIN" ]] || { echo "LỖI: chưa có binary. Chạy: $0 fetch" >&2; exit 1; }
  if cmd_status >/dev/null 2>&1; then echo "Qdrant đã chạy sẵn."; return 0; fi
  mkdir -p "$STORAGE"
  QDRANT__STORAGE__STORAGE_PATH="$STORAGE" \
  QDRANT__SERVICE__HTTP_PORT="$CBRAIN_QDRANT_HTTP_PORT" \
  QDRANT__SERVICE__GRPC_PORT="$CBRAIN_QDRANT_GRPC_PORT" \
  QDRANT__TELEMETRY_DISABLED=true \
    nohup "$BIN" >"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  for _ in $(seq 1 40); do
    if curl -fsS "http://localhost:${CBRAIN_QDRANT_HTTP_PORT}/readyz" >/dev/null 2>&1; then
      echo "Qdrant sẵn sàng trên cổng $CBRAIN_QDRANT_HTTP_PORT (pid $(cat "$PIDFILE"))"
      return 0
    fi
    sleep 0.5
  done
  echo "LỖI: Qdrant không sẵn sàng sau 20s. Xem $LOG" >&2
  exit 1
}

cmd_stop() {
  [[ -f "$PIDFILE" ]] || { echo "Không có pidfile — coi như đã dừng."; return 0; }
  local pid; pid="$(cat "$PIDFILE")"
  if kill -0 "$pid" 2>/dev/null; then kill "$pid"; echo "Đã dừng pid $pid"; fi
  rm -f "$PIDFILE"
}

cmd_status() {
  curl -fsS "http://localhost:${CBRAIN_QDRANT_HTTP_PORT}/readyz" >/dev/null 2>&1 \
    && { echo "đang chạy"; return 0; } || { echo "chưa chạy"; return 1; }
}

case "${1:-}" in
  fetch)  cmd_fetch ;;
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  *) echo "Dùng: $0 {fetch|start|stop|status}" >&2; exit 2 ;;
esac
