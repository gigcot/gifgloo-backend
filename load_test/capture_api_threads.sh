#!/usr/bin/env bash
set -euo pipefail

api_pid="${1:?API PID is required}"
interval_seconds="${LOADTEST_THREAD_CAPTURE_INTERVAL_SECONDS:-1}"

if command -v pidstat > /dev/null 2>&1; then
  exec pidstat -t -u -r -p "$api_pid" "$interval_seconds"
fi

while kill -0 "$api_pid" 2> /dev/null; do
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  ps -L -p "$api_pid" -o pid,tid,pcpu,pmem,stat,comm
  sleep "$interval_seconds"
done
