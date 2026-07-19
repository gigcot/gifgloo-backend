#!/usr/bin/env bash
set -euo pipefail

service_name="${1:?Systemd service name is required}"
output_path="${2:?Output path is required}"
pid_file="${3:?PID file path is required}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
main_pid="$(systemctl show -p MainPID --value "$service_name")"
control_group="$(systemctl show -p ControlGroup --value "$service_name")"
cgroup_procs="/sys/fs/cgroup${control_group}/cgroup.procs"

service_pids=()
if [[ -r "$cgroup_procs" ]]; then
  mapfile -t service_pids < "$cgroup_procs"
fi
if [[ "${#service_pids[@]}" -eq 0 ]]; then
  service_pids=("$main_pid")
fi
pid_list="$(IFS=,; echo "${service_pids[*]}")"

mkdir -p "$(dirname "$output_path")"
nohup "$script_dir/capture_api_threads.sh" "$pid_list" > "$output_path" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$pid_file"
