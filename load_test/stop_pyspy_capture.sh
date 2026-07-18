#!/usr/bin/env bash
set -euo pipefail

pid_file="${1:?PID file path is required}"

if [[ ! -f "$pid_file" ]]; then
  exit 0
fi

capture_pid="$(cat "$pid_file")"
sudo -n kill -INT "$capture_pid" 2> /dev/null || true

for _ in $(seq 1 20); do
  if ! sudo -n kill -0 "$capture_pid" 2> /dev/null; then
    exit 0
  fi
  sleep 0.25
done

echo "py-spy did not stop after SIGINT: pid=${capture_pid}" >&2
exit 1
