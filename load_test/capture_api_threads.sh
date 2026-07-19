#!/usr/bin/env bash
set -euo pipefail

process_pids="${1:?Process PID list is required}"
interval_seconds="${LOADTEST_THREAD_CAPTURE_INTERVAL_SECONDS:-1}"

echo "captured_pids=${process_pids}"
if command -v pidstat > /dev/null 2>&1; then
  exec pidstat -t -u -r -p "$process_pids" "$interval_seconds"
fi

main_pid="${process_pids%%,*}"
while kill -0 "$main_pid" 2> /dev/null; do
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  ps -L -p "$process_pids" -o pid,tid,pcpu,pmem,stat,comm
  sleep "$interval_seconds"
done
