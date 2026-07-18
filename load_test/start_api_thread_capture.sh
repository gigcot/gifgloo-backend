#!/usr/bin/env bash
set -euo pipefail

service_name="${1:?Systemd service name is required}"
output_path="${2:?Output path is required}"
pid_file="${3:?PID file path is required}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
api_pid="$(systemctl show -p MainPID --value "$service_name")"

mkdir -p "$(dirname "$output_path")"
nohup "$script_dir/capture_api_threads.sh" "$api_pid" > "$output_path" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$pid_file"
