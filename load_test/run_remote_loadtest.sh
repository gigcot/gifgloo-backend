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
LOADTEST_PROFILE="${LOADTEST_PROFILE:-manual}"
LOADTEST_REMOTE_PROM_OUTPUT="${LOADTEST_REMOTE_PROM_OUTPUT:-/tmp/gifgloo-node-exporter/credit_consistency.prom}"
LOADTEST_REMOTE_PYTHON="${LOADTEST_REMOTE_PYTHON:-${LOADTEST_REMOTE_DIR}/venv/bin/python}"

timestamp="$(date +%Y%m%d_%H%M%S)"
result_dir="load_test/results/${LOADTEST_PROFILE}/${timestamp}_${LOADTEST_USERS}u"
mkdir -p "$(dirname "$LOADTEST_TOKEN_OUTPUT_PATH")" "$result_dir"

if [[ "$LOADTEST_TOKEN_OUTPUT_PATH" = /* ]]; then
  remote_token_path="$LOADTEST_TOKEN_OUTPUT_PATH"
else
  remote_token_path="${LOADTEST_REMOTE_DIR}/${LOADTEST_TOKEN_OUTPUT_PATH}"
fi

echo "[1/5] remote reset and seed"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && ${LOADTEST_REMOTE_PYTHON} load_test/reset.py && ${LOADTEST_REMOTE_PYTHON} load_test/seed.py"

echo "[2/5] copy token csv from remote"
scp "${LOADTEST_EC2_HOST}:${remote_token_path}" "$LOADTEST_TOKEN_OUTPUT_PATH"

echo "[3/5] run locust"
locust -f load_test/locustfile.py \
  --host "$LOADTEST_LOCUST_HOST" \
  --users "$LOADTEST_USERS" \
  --spawn-rate "$LOADTEST_SPAWN_RATE" \
  --run-time "$LOADTEST_RUN_TIME" \
  --headless \
  --html "${result_dir}/report.html" \
  --csv "${result_dir}/result"

echo "[4/5] remote credit consistency check"
ssh "$LOADTEST_EC2_HOST" "cd ${LOADTEST_REMOTE_DIR} && mkdir -p \"\$(dirname ${LOADTEST_REMOTE_PROM_OUTPUT})\" && ${LOADTEST_REMOTE_PYTHON} load_test/verify_credit_consistency.py --prometheus-output ${LOADTEST_REMOTE_PROM_OUTPUT}"

echo "[5/5] done"
echo "result_dir=${result_dir}"
echo "credit_consistency_prom=${LOADTEST_REMOTE_PROM_OUTPUT}"
