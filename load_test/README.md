# Load Test

이 폴더는 loadtest 브랜치에서 쓰는 데이터 준비와 Locust 시나리오를 둔다.

## Seed

EC2에서 `.env.loadtest`를 작성한 뒤 실행한다.

```bash
docker compose --env-file .env.loadtest -f load_test/docker-compose.yml up -d db
python load_test/reset.py
python load_test/seed.py
```

생성된 token CSV는 Locust에서 `user_token` 쿠키로 사용한다.
`LOADTEST_USER_COUNT=1`이면 smoke용 단일 유저 seed로 쓸 수 있다.
단계별 결과가 섞이지 않도록 smoke/baseline/load/stress 실행 전에는 `reset.py` 후 `seed.py`를 다시 실행한다.

필수 `.env.loadtest`:

```text
DATABASE_URL
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
LOADTEST_POSTGRES_PORT
JWT_SECRET_KEY
INTERNAL_SECRET
CORS_ORIGINS
LOADTEST_CALLBACK_URL
LOADTEST_PIPELINE_FAIL_MARKER
LOADTEST_DELAY_EXTRACTING_FRAMES_SECONDS
LOADTEST_DELAY_ANALYZING_SECONDS
LOADTEST_DELAY_GENERATING_DRAFT_SECONDS
LOADTEST_DELAY_COMPOSITING_SECONDS
LOADTEST_DELAY_BUILDING_GIF_SECONDS
LOADTEST_DELAY_COMPLETION_SECONDS
LOADTEST_STORAGE_PUBLIC_URL
LOADTEST_FEASIBILITY_BLOCK_MARKER
LOADTEST_FEASIBILITY_FRAME_COUNT
LOADTEST_USER_PREFIX
LOADTEST_USER_EMAIL_DOMAIN
LOADTEST_USER_COUNT
LOADTEST_CREDIT_BALANCE
LOADTEST_TOKEN_OUTPUT_PATH
```

## Locust

`LOADTEST_PIPELINE_FAIL_MARKER`가 `gif_url`에 포함되면 fake pipeline은 `fail` callback을 호출한다.
`LOADTEST_PIPELINE_FAIL_STAGE`를 `ANALYZING`, `GENERATING_DRAFT`, `COMPOSITING`, `BUILDING_GIF` 중 하나로 지정하면 해당 checkpoint 이후 fail callback을 호출한다. 비워두면 기존처럼 모든 checkpoint 이후 fail callback을 호출한다.
`LOADTEST_*_WEIGHT` 값으로 페이지 조회와 success/fail flow 비율을 조절한다.

```bash
locust -f load_test/locustfile.py \
  --host https://api-loadtest.gifgloo.com \
  --users 5 \
  --spawn-rate 1 \
  --run-time 5m \
  --headless
```

필수 Locust env:

```text
LOADTEST_TOKEN_OUTPUT_PATH
LOADTEST_TARGET_IMAGE_PATH
LOADTEST_GIF_URL
LOADTEST_PIPELINE_FAIL_MARKER
LOADTEST_HOME_PAGE_WEIGHT
LOADTEST_COMPOSE_PAGE_WEIGHT
LOADTEST_SUCCESS_WEIGHT
LOADTEST_FAIL_WEIGHT
LOADTEST_MY_ASSETS_PAGE_WEIGHT
LOADTEST_STATUS_TIMEOUT_SECONDS
```

선택 Locust env:

```text
LOADTEST_CONFIRMATION_WEIGHT
LOADTEST_FEASIBILITY_REJECT_WEIGHT
LOADTEST_PIPELINE_FAIL_STAGE
```

로컬에서 Locust를 실행하고 EC2에서 reset/seed/verify를 수행하려면:

```bash
LOADTEST_EC2_HOST=ubuntu@<ec2-host> \
LOADTEST_REMOTE_DIR=~/gifgloo-backend-loadtest \
LOADTEST_USERS=100 \
LOADTEST_SPAWN_RATE=10 \
LOADTEST_RUN_TIME=10m \
LOADTEST_PROFILE=load \
./load_test/run_remote_loadtest.sh
```

흐름:

```text
EC2 reset.py
EC2 seed.py
EC2 token CSV -> local scp
local locust
EC2 verify_credit_consistency.py
```

## Credit consistency

테스트 후 크레딧 정합성을 확인한다.

```bash
python load_test/verify_credit_consistency.py
```

Grafana에서 보려면 node-exporter textfile collector 경로에 Prometheus 포맷으로 쓴다.

```bash
python load_test/verify_credit_consistency.py \
  --prometheus-output /tmp/gifgloo-node-exporter/credit_consistency.prom
```

노출되는 주요 지표:

```text
loadtest_credit_checked_users
loadtest_credit_inconsistent_users
loadtest_credit_balance_mismatch_users
loadtest_credit_deduct_mismatch_users
loadtest_credit_refund_mismatch_users
```

## DB/SQL observability

loadtest Postgres는 `pg_stat_statements`와 `log_min_duration_statement=200`으로 실행된다.
FastAPI `/metrics`에는 SQLAlchemy 기반 지표가 추가된다.

```text
db_query_total
db_query_duration_seconds
db_pool_checkout_total
db_pool_checked_out
```
