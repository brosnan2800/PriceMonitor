#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-daily}"
BASE_DIR="${BASE_DIR:-/root/Desktop/priceMonitor}"
BACKUP_ROOT="${BACKUP_ROOT:-/root/Desktop/priceMonitor-backups}"
DB_PATH="${DB_PATH:-$BASE_DIR/data/secretary.db}"
ENV_PATH="${ENV_PATH:-$BASE_DIR/.env}"
HOSTNAME_VALUE="$(hostname)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

case "$MODE" in
  daily)
    KEEP=7
    ;;
  weekly)
    KEEP=4
    ;;
  predeploy)
    KEEP=5
    ;;
  env-change)
    KEEP=4
    ;;
  manual)
    KEEP=10
    ;;
  *)
    echo "Usage: $0 [daily|weekly|predeploy|env-change|manual]" >&2
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for SQLite online backup" >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH" >&2
  exit 1
fi

BACKUP_DIR="$BACKUP_ROOT/$MODE/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

DB_BACKUP_PATH="$BACKUP_DIR/secretary.db"
ENV_BACKUP_PATH="$BACKUP_DIR/.env"
META_PATH="$BACKUP_DIR/backup_meta.txt"

DB_PATH="$DB_PATH" DB_BACKUP_PATH="$DB_BACKUP_PATH" python3 - <<'PY'
import os
import sqlite3

src = os.environ["DB_PATH"]
dst = os.environ["DB_BACKUP_PATH"]

src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(dst)
try:
    src_conn.backup(dst_conn)
finally:
    dst_conn.close()
    src_conn.close()
PY

if [[ -f "$ENV_PATH" ]]; then
  cp "$ENV_PATH" "$ENV_BACKUP_PATH"
fi

{
  echo "mode=$MODE"
  echo "timestamp=$TIMESTAMP"
  echo "host=$HOSTNAME_VALUE"
  echo "db_backup=$DB_BACKUP_PATH"
  if [[ -f "$ENV_BACKUP_PATH" ]]; then
    echo "env_backup=$ENV_BACKUP_PATH"
  else
    echo "env_backup=missing"
  fi
} > "$META_PATH"

cleanup_mode() {
  local mode="$1"
  local keep="$2"
  local mode_dir="$BACKUP_ROOT/$mode"
  [[ -d "$mode_dir" ]] || return 0

  mapfile -t entries < <(find "$mode_dir" -mindepth 1 -maxdepth 1 -type d | sort -r)
  if (( ${#entries[@]} <= keep )); then
    return 0
  fi

  for old_dir in "${entries[@]:keep}"; do
    rm -rf "$old_dir"
  done
}

cleanup_mode "$MODE" "$KEEP"

echo "Backup complete: $BACKUP_DIR"
