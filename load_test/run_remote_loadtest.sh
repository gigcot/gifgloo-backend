#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env.loadtest" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.loadtest"
  set +a
fi

: "${LOADTEST_EC2_HOST:?LOADTEST_EC2_HOST is required. Example: ubuntu@1.2.3.4}"
: "${LOADTEST_TOKEN_OUTPUT_PATH:?LOADTEST_TOKEN_OUTPUT_PATH is required}"
: "${LOADTEST_TARGET_IMAGE_PATH:?LOADTEST_TARGET_IMAGE_PATH is required}"
: "${LOADTEST_GIF_URL:?LOADTEST_GIF_URL is required}"

LOADTEST_REMOTE_DIR="${LOADTEST_REMOTE_DIR:-~/gifgloo-backend-loadtest}"
LOADTEST_LOCUST_HOST="${LOADTEST_LOCUST_HOST:-https://api-loadtest.gifgloo.com}"
LOADTEST_USERS="${LOADTEST_USERS:-1}"
LOADTEST_SPAWN_RATE="${LOADTEST_SPAWN_RATE:-1}"
LOADTEST_RUN_TIME="${LOADTEST_RUN_TIME:-1m}"
LOADTEST_STOP_TIMEOUT="${LOADTEST_STOP_TIMEOUT:-180}"
LOADTEST_PROFILE="${LOADTEST_PROFILE:-manual}"
LOADTEST_REMOTE_PROM_OUTPUT="${LOADTEST_REMOTE_PROM_OUTPUT:-/tmp/gifgloo-node-exporter/credit_consistency.prom}"
LOADTEST_REMOTE_RUN_PROM_OUTPUT="${LOADTEST_REMOTE_RUN_PROM_OUTPUT:-/tmp/gifgloo-node-exporter/loadtest_run.prom}"
LOADTEST_REMOTE_PYTHON="${LOADTEST_REMOTE_PYTHON:-${LOADTEST_REMOTE_DIR}/venv/bin/python}"
LOADTEST_REMOTE_API_HOST="${LOADTEST_REMOTE_API_HOST:-0.0.0.0}"
LOADTEST_REMOTE_API_PORT="${LOADTEST_REMOTE_API_PORT:-8001}"
LOADTEST_REMOTE_API_LOG="${LOADTEST_REMOTE_API_LOG:-/var/log/gifgloo/loadtest-api.log}"
LOADTEST_REMOTE_API_SERVICE="${LOADTEST_REMOTE_API_SERVICE:-gifgloo-loadtest-api}"
LOADTEST_REMOTE_API_READY_ATTEMPTS="${LOADTEST_REMOTE_API_READY_ATTEMPTS:-30}"
LOADTEST_API_WORKERS="${LOADTEST_API_WORKERS:-2}"
LOADTEST_PIPELINE_MODE="${LOADTEST_PIPELINE_MODE:-in_process}"
LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE="${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE:-gifgloo-loadtest-fake-pipeline}"
LOADTEST_REMOTE_PIPELINE_WORKER_PORT="${LOADTEST_REMOTE_PIPELINE_WORKER_PORT:-8012}"
LOADTEST_REMOTE_THREAD_CAPTURE_ENABLED="${LOADTEST_REMOTE_THREAD_CAPTURE_ENABLED:-1}"
LOADTEST_REMOTE_THREAD_CAPTURE_DIR="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR:-/tmp/gifgloo-loadtest}"
LOADTEST_REMOTE_PYSPY_ENABLED="${LOADTEST_REMOTE_PYSPY_ENABLED:-0}"
LOADTEST_REMOTE_PYSPY_BIN="${LOADTEST_REMOTE_PYSPY_BIN:-venv/bin/py-spy}"
LOADTEST_PYSPY_RATE="${LOADTEST_PYSPY_RATE:-50}"
LOADTEST_GRAFANA_URL="${LOADTEST_GRAFANA_URL:-http://127.0.0.1:3000}"
LOADTEST_PUSHGATEWAY_URL="${LOADTEST_PUSHGATEWAY_URL-http://127.0.0.1:9091}"
LOADTEST_PUSHGATEWAY_INTERVAL_SECONDS="${LOADTEST_PUSHGATEWAY_INTERVAL_SECONDS:-5}"

timestamp="$(date +%Y%m%d_%H%M%S)"
LOADTEST_RUN_ID="${LOADTEST_RUN_ID:-${timestamp}_${LOADTEST_USERS}u}"
result_dir="load_test/results/${LOADTEST_PROFILE}/${timestamp}_${LOADTEST_USERS}u"
mkdir -p "$(dirname "$LOADTEST_TOKEN_OUTPUT_PATH")" "$result_dir"

export LOADTEST_PROFILE
export LOADTEST_PUSHGATEWAY_INTERVAL_SECONDS
export LOADTEST_PUSHGATEWAY_URL
export LOADTEST_RUN_ID

if [[ "$LOADTEST_TOKEN_OUTPUT_PATH" = /* ]]; then
  remote_token_path="$LOADTEST_TOKEN_OUTPUT_PATH"
else
  remote_token_path="${LOADTEST_REMOTE_DIR}/${LOADTEST_TOKEN_OUTPUT_PATH}"
fi

remote_thread_capture_output="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-api-threads.log"
remote_thread_capture_pid_file="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-api-threads.pid"
remote_pipeline_thread_capture_output="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-fake-pipeline-threads.log"
remote_pipeline_thread_capture_pid_file="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-fake-pipeline-threads.pid"
remote_pyspy_output="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-api-speedscope.json"
remote_pyspy_log="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-api-pyspy.log"
remote_pyspy_pid_file="${LOADTEST_REMOTE_THREAD_CAPTURE_DIR}/${LOADTEST_RUN_ID}-api-pyspy.pid"

echo "[1/9] pushgateway readiness"
if [[ -n "$LOADTEST_PUSHGATEWAY_URL" ]]; then
  curl --max-time 5 -fsS "${LOADTEST_PUSHGATEWAY_URL%/}/-/ready" > /dev/null
else
  echo "Locust Pushgateway reporting is disabled"
fi

echo "[2/9] remote reset and seed"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && ${LOADTEST_REMOTE_PYTHON} load_test/reset.py && ${LOADTEST_REMOTE_PYTHON} load_test/seed.py"

echo "[3/9] remote restart fake pipeline worker"
if [[ "$LOADTEST_PIPELINE_MODE" = "external" ]]; then
  ssh "$LOADTEST_EC2_HOST" "sudo systemctl restart ${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} && for attempt in \$(seq 1 ${LOADTEST_REMOTE_API_READY_ATTEMPTS}); do if ! sudo systemctl is-active --quiet ${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE}; then sudo systemctl status ${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} --no-pager -l; exit 1; fi; if curl --max-time 2 -fsS http://127.0.0.1:${LOADTEST_REMOTE_PIPELINE_WORKER_PORT}/healthz > /dev/null; then echo \"${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} ready after \${attempt}s\"; exit 0; fi; sleep 1; done; echo \"${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} did not become ready within ${LOADTEST_REMOTE_API_READY_ATTEMPTS}s\"; sudo systemctl status ${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} --no-pager -l; exit 1"
else
  echo "in-process fake pipeline mode"
fi

echo "[4/9] remote restart api"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && sudo systemctl restart ${LOADTEST_REMOTE_API_SERVICE} && for attempt in \$(seq 1 ${LOADTEST_REMOTE_API_READY_ATTEMPTS}); do if ! sudo systemctl is-active --quiet ${LOADTEST_REMOTE_API_SERVICE}; then sudo systemctl status ${LOADTEST_REMOTE_API_SERVICE} --no-pager -l; exit 1; fi; listen_pids=\"\$(lsof -ti tcp:${LOADTEST_REMOTE_API_PORT} -sTCP:LISTEN || true)\"; metrics_body=\"\$(curl --max-time 2 -fsS http://127.0.0.1:${LOADTEST_REMOTE_API_PORT}/metrics || true)\"; worker_count=\"\$(printf '%s\n' \"\${metrics_body}\" | awk '\$1 == \"fastapi_worker_processes\" { print int(\$2) }')\"; if [[ -n \"\${listen_pids}\" && \"\${worker_count}\" = \"${LOADTEST_API_WORKERS}\" ]]; then echo \"${LOADTEST_REMOTE_API_SERVICE} ready with \${worker_count} workers after \${attempt}s\"; exit 0; fi; sleep 1; done; echo \"${LOADTEST_REMOTE_API_SERVICE} did not become ready with ${LOADTEST_API_WORKERS} workers within ${LOADTEST_REMOTE_API_READY_ATTEMPTS}s\"; echo \"listen_pids=\${listen_pids}\"; echo \"worker_count=\${worker_count}\"; sudo systemctl status ${LOADTEST_REMOTE_API_SERVICE} --no-pager -l; sudo lsof -nP -iTCP:${LOADTEST_REMOTE_API_PORT} -sTCP:LISTEN || true; exit 1"

if [[ "$LOADTEST_REMOTE_THREAD_CAPTURE_ENABLED" = "1" ]]; then
  echo "[5/9] start remote process thread capture"
  ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && load_test/start_api_thread_capture.sh ${LOADTEST_REMOTE_API_SERVICE} ${remote_thread_capture_output} ${remote_thread_capture_pid_file}"
  if [[ "$LOADTEST_PIPELINE_MODE" = "external" ]]; then
    ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && load_test/start_api_thread_capture.sh ${LOADTEST_REMOTE_PIPELINE_WORKER_SERVICE} ${remote_pipeline_thread_capture_output} ${remote_pipeline_thread_capture_pid_file}"
  fi
fi

echo "[6/9] copy token csv from remote"
scp "${LOADTEST_EC2_HOST}:${remote_token_path}" "$LOADTEST_TOKEN_OUTPUT_PATH"

if [[ "$LOADTEST_REMOTE_PYSPY_ENABLED" = "1" ]]; then
  echo "start remote API py-spy capture"
  ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && LOADTEST_PYSPY_RATE=${LOADTEST_PYSPY_RATE} load_test/start_pyspy_capture.sh ${LOADTEST_REMOTE_API_SERVICE} ${remote_pyspy_output} ${remote_pyspy_pid_file} ${remote_pyspy_log} ${LOADTEST_REMOTE_PYSPY_BIN}"
fi

echo "[7/9] run locust"
loadtest_started_at="$(date +%s)"
loadtest_started_at_ms="$((loadtest_started_at * 1000))"
set +e
locust -f load_test/locustfile.py \
  --host "$LOADTEST_LOCUST_HOST" \
  --users "$LOADTEST_USERS" \
  --spawn-rate "$LOADTEST_SPAWN_RATE" \
  --run-time "$LOADTEST_RUN_TIME" \
  --stop-timeout "$LOADTEST_STOP_TIMEOUT" \
  --headless \
  --html "${result_dir}/report.html" \
  --csv "${result_dir}/result"
locust_exit_code=$?
set -e
loadtest_ended_at="$(date +%s)"
loadtest_ended_at_ms="$((loadtest_ended_at * 1000))"

if [[ "$LOADTEST_REMOTE_PYSPY_ENABLED" = "1" ]]; then
  ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && load_test/stop_pyspy_capture.sh ${remote_pyspy_pid_file}"
fi

cat > "${result_dir}/time_range.env" <<EOF
LOADTEST_STARTED_AT=${loadtest_started_at}
LOADTEST_ENDED_AT=${loadtest_ended_at}
LOADTEST_STARTED_AT_MS=${loadtest_started_at_ms}
LOADTEST_ENDED_AT_MS=${loadtest_ended_at_ms}
LOADTEST_GRAFANA_FROM=${loadtest_started_at_ms}
LOADTEST_GRAFANA_TO=${loadtest_ended_at_ms}
LOADTEST_API_WORKERS=${LOADTEST_API_WORKERS}
LOADTEST_PIPELINE_MODE=${LOADTEST_PIPELINE_MODE}
EOF

run_prometheus_metrics="$(cat <<EOF
# HELP loadtest_run_start_timestamp_seconds Last loadtest run start timestamp.
# TYPE loadtest_run_start_timestamp_seconds gauge
loadtest_run_start_timestamp_seconds{profile="${LOADTEST_PROFILE}"} ${loadtest_started_at}
# HELP loadtest_run_end_timestamp_seconds Last loadtest run end timestamp.
# TYPE loadtest_run_end_timestamp_seconds gauge
loadtest_run_end_timestamp_seconds{profile="${LOADTEST_PROFILE}"} ${loadtest_ended_at}
# HELP loadtest_run_users Last loadtest run virtual users.
# TYPE loadtest_run_users gauge
loadtest_run_users{profile="${LOADTEST_PROFILE}"} ${LOADTEST_USERS}
# HELP loadtest_run_spawn_rate Last loadtest run spawn rate.
# TYPE loadtest_run_spawn_rate gauge
loadtest_run_spawn_rate{profile="${LOADTEST_PROFILE}"} ${LOADTEST_SPAWN_RATE}
# HELP loadtest_run_api_workers Uvicorn worker processes used by the last loadtest run.
# TYPE loadtest_run_api_workers gauge
loadtest_run_api_workers{profile="${LOADTEST_PROFILE}"} ${LOADTEST_API_WORKERS}
# HELP loadtest_run_pipeline_mode_info Fake pipeline execution mode used by the last loadtest run.
# TYPE loadtest_run_pipeline_mode_info gauge
loadtest_run_pipeline_mode_info{profile="${LOADTEST_PROFILE}",mode="${LOADTEST_PIPELINE_MODE}"} 1
EOF
)"
printf "%s\n" "$run_prometheus_metrics" > "${result_dir}/loadtest_run.prom"
printf "%s\n" "$run_prometheus_metrics" | ssh "$LOADTEST_EC2_HOST" "mkdir -p \"\$(dirname ${LOADTEST_REMOTE_RUN_PROM_OUTPUT})\" && cat > ${LOADTEST_REMOTE_RUN_PROM_OUTPUT}"

if [[ "$LOADTEST_REMOTE_THREAD_CAPTURE_ENABLED" = "1" ]]; then
  echo "[8/9] collect remote process thread capture"
  ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && load_test/stop_api_thread_capture.sh ${remote_thread_capture_pid_file}"
  scp "${LOADTEST_EC2_HOST}:${remote_thread_capture_output}" "${result_dir}/api-thread-diagnostics.log"
  if [[ "$LOADTEST_PIPELINE_MODE" = "external" ]]; then
    ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && load_test/stop_api_thread_capture.sh ${remote_pipeline_thread_capture_pid_file}"
    scp "${LOADTEST_EC2_HOST}:${remote_pipeline_thread_capture_output}" "${result_dir}/fake-pipeline-thread-diagnostics.log"
  fi
fi

if [[ "$LOADTEST_REMOTE_PYSPY_ENABLED" = "1" ]]; then
  scp "${LOADTEST_EC2_HOST}:${remote_pyspy_output}" "${result_dir}/api-speedscope.json"
  scp "${LOADTEST_EC2_HOST}:${remote_pyspy_log}" "${result_dir}/api-pyspy.log"
fi

echo "[9/9] remote credit consistency check"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && mkdir -p \"\$(dirname ${LOADTEST_REMOTE_PROM_OUTPUT})\" && ${LOADTEST_REMOTE_PYTHON} load_test/verify_credit_consistency.py --prometheus-output ${LOADTEST_REMOTE_PROM_OUTPUT}"

echo "[done]"
echo "result_dir=${result_dir}"
echo "credit_consistency_prom=${LOADTEST_REMOTE_PROM_OUTPUT}"
echo "loadtest_run_prom=${LOADTEST_REMOTE_RUN_PROM_OUTPUT}"
echo "locust_pushgateway=${LOADTEST_PUSHGATEWAY_URL:-disabled}"
echo "loadtest_run_id=${LOADTEST_RUN_ID}"
if [[ "$LOADTEST_REMOTE_THREAD_CAPTURE_ENABLED" = "1" ]]; then
  echo "api_thread_diagnostics=${result_dir}/api-thread-diagnostics.log"
  if [[ "$LOADTEST_PIPELINE_MODE" = "external" ]]; then
    echo "fake_pipeline_thread_diagnostics=${result_dir}/fake-pipeline-thread-diagnostics.log"
  fi
fi
if [[ "$LOADTEST_REMOTE_PYSPY_ENABLED" = "1" ]]; then
  echo "api_speedscope=${result_dir}/api-speedscope.json"
  echo "api_pyspy_log=${result_dir}/api-pyspy.log"
fi
echo "remote_api_log=${LOADTEST_REMOTE_API_LOG}"
echo "grafana_from=${loadtest_started_at_ms}"
echo "grafana_to=${loadtest_ended_at_ms}"
echo "grafana_url=${LOADTEST_GRAFANA_URL}/?from=${loadtest_started_at_ms}&to=${loadtest_ended_at_ms}"
exit "$locust_exit_code"
