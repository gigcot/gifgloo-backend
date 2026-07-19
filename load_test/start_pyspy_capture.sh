#!/usr/bin/env bash
set -euo pipefail

service_name="${1:?Systemd service name is required}"
output_path="${2:?Output path is required}"
pid_file="${3:?PID file path is required}"
log_path="${4:?Log path is required}"
pyspy_bin="${5:-venv/bin/py-spy}"
sample_rate="${LOADTEST_PYSPY_RATE:-50}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"
main_pid="$(systemctl show -p MainPID --value "$service_name")"
control_group="$(systemctl show -p ControlGroup --value "$service_name")"
cgroup_procs="/sys/fs/cgroup${control_group}/cgroup.procs"
profile_pid="$main_pid"

if [[ -r "$cgroup_procs" ]]; then
  while read -r candidate_pid; do
    if [[ "$candidate_pid" = "$main_pid" || ! -r "/proc/${candidate_pid}/cmdline" ]]; then
      continue
    fi
    if tr '\0' ' ' < "/proc/${candidate_pid}/cmdline" | grep -q "multiprocessing.spawn"; then
      profile_pid="$candidate_pid"
      break
    fi
  done < "$cgroup_procs"
fi

if [[ ! -x "${repo_dir}/${pyspy_bin}" ]]; then
  echo "py-spy executable not found: ${repo_dir}/${pyspy_bin}" >&2
  exit 1
fi

mkdir -p "$(dirname "$output_path")" "$(dirname "$log_path")"
printf 'profiled_pid=%s service_main_pid=%s\n' "$profile_pid" "$main_pid" > "$log_path"
sudo -n nohup "${repo_dir}/${pyspy_bin}" record \
  --pid "$profile_pid" \
  --rate "$sample_rate" \
  --format speedscope \
  --threads \
  --full-filenames \
  --output "$output_path" \
  >> "$log_path" 2>&1 < /dev/null &
capture_pid="$!"
printf '%s\n' "$capture_pid" > "$pid_file"

sleep 1
if ! sudo -n kill -0 "$capture_pid" 2> /dev/null; then
  cat "$log_path"
  exit 1
fi
