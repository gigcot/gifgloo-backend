#!/usr/bin/env bash
set -euo pipefail

pid_file="${1:?PID file path is required}"

if [[ -f "$pid_file" ]]; then
  capture_pid="$(cat "$pid_file")"
  kill "$capture_pid" 2> /dev/null || true
fi
