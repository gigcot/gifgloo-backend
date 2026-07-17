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

echo "[1/7] pushgateway readiness"
if [[ -n "$LOADTEST_PUSHGATEWAY_URL" ]]; then
  curl --max-time 5 -fsS "${LOADTEST_PUSHGATEWAY_URL%/}/-/ready" > /dev/null
else
  echo "Locust Pushgateway reporting is disabled"
fi

echo "[2/7] remote reset and seed"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && ${LOADTEST_REMOTE_PYTHON} load_test/reset.py && ${LOADTEST_REMOTE_PYTHON} load_test/seed.py"

echo "[3/7] remote restart api"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && sudo systemctl restart ${LOADTEST_REMOTE_API_SERVICE} && for attempt in \$(seq 1 ${LOADTEST_REMOTE_API_READY_ATTEMPTS}); do if ! sudo systemctl is-active --quiet ${LOADTEST_REMOTE_API_SERVICE}; then sudo systemctl status ${LOADTEST_REMOTE_API_SERVICE} --no-pager -l; exit 1; fi; main_pid=\"\$(systemctl show -p MainPID --value ${LOADTEST_REMOTE_API_SERVICE})\"; listen_pids=\"\$(lsof -ti tcp:${LOADTEST_REMOTE_API_PORT} -sTCP:LISTEN || true)\"; if printf '%s\n' \"\${listen_pids}\" | grep -qx \"\${main_pid}\" && curl --max-time 2 -fsS http://127.0.0.1:${LOADTEST_REMOTE_API_PORT}/metrics > /dev/null; then echo \"${LOADTEST_REMOTE_API_SERVICE} ready after \${attempt}s\"; exit 0; fi; sleep 1; done; echo \"${LOADTEST_REMOTE_API_SERVICE} did not become ready within ${LOADTEST_REMOTE_API_READY_ATTEMPTS}s\"; echo \"main_pid=\${main_pid}\"; echo \"listen_pids=\${listen_pids}\"; sudo systemctl status ${LOADTEST_REMOTE_API_SERVICE} --no-pager -l; sudo lsof -nP -iTCP:${LOADTEST_REMOTE_API_PORT} -sTCP:LISTEN || true; exit 1"

echo "[4/7] copy token csv from remote"
scp "${LOADTEST_EC2_HOST}:${remote_token_path}" "$LOADTEST_TOKEN_OUTPUT_PATH"

echo "[5/7] run locust"
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

cat > "${result_dir}/time_range.env" <<EOF
LOADTEST_STARTED_AT=${loadtest_started_at}
LOADTEST_ENDED_AT=${loadtest_ended_at}
LOADTEST_STARTED_AT_MS=${loadtest_started_at_ms}
LOADTEST_ENDED_AT_MS=${loadtest_ended_at_ms}
LOADTEST_GRAFANA_FROM=${loadtest_started_at_ms}
LOADTEST_GRAFANA_TO=${loadtest_ended_at_ms}
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
EOF
)"
printf "%s\n" "$run_prometheus_metrics" > "${result_dir}/loadtest_run.prom"
printf "%s\n" "$run_prometheus_metrics" | ssh "$LOADTEST_EC2_HOST" "mkdir -p \"\$(dirname ${LOADTEST_REMOTE_RUN_PROM_OUTPUT})\" && cat > ${LOADTEST_REMOTE_RUN_PROM_OUTPUT}"

echo "[6/7] remote credit consistency check"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && mkdir -p \"\$(dirname ${LOADTEST_REMOTE_PROM_OUTPUT})\" && ${LOADTEST_REMOTE_PYTHON} load_test/verify_credit_consistency.py --prometheus-output ${LOADTEST_REMOTE_PROM_OUTPUT}"

echo "[7/7] done"
echo "result_dir=${result_dir}"
echo "credit_consistency_prom=${LOADTEST_REMOTE_PROM_OUTPUT}"
echo "loadtest_run_prom=${LOADTEST_REMOTE_RUN_PROM_OUTPUT}"
echo "locust_pushgateway=${LOADTEST_PUSHGATEWAY_URL:-disabled}"
echo "loadtest_run_id=${LOADTEST_RUN_ID}"
echo "remote_api_log=${LOADTEST_REMOTE_API_LOG}"
echo "grafana_from=${loadtest_started_at_ms}"
echo "grafana_to=${loadtest_ended_at_ms}"
echo "grafana_url=${LOADTEST_GRAFANA_URL}/?from=${loadtest_started_at_ms}&to=${loadtest_ended_at_ms}"
exit "$locust_exit_code"
