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
DB_POOL_PRE_PING
ASYNC_DB_POOL_SIZE
ASYNC_DB_MAX_OVERFLOW
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

부하 테스트 DB가 안정적으로 유지되는 환경에서는 checkout마다 ping 쿼리를 추가하지 않도록
다음 값을 사용한다. 운영 환경의 기본값은 `true`다.

```text
DB_POOL_PRE_PING=false
ASYNC_DB_POOL_SIZE=8
ASYNC_DB_MAX_OVERFLOW=2
```

API의 Uvicorn access log는 Nginx JSON access log와 중복되므로 기본적으로 비활성화된다.
일시적으로 필요하면 다음 값을 설정한다.

```text
LOADTEST_UVICORN_ACCESS_LOG=true
```

fake pipeline 실행 방식은 다음 환경 변수로 선택한다.

```text
LOADTEST_PIPELINE_MODE=in_process
```

기본값인 `in_process`는 API의 Uvicorn event loop에서 fake pipeline을 실행한다.
같은 EC2의 별도 프로세스로 분리하려면 로컬과 EC2의 `.env.loadtest`에 다음을 설정한다.

```text
LOADTEST_PIPELINE_MODE=external
LOADTEST_PIPELINE_WORKER_URL=http://127.0.0.1:8012
```

worker는 callback만 별도 프로세스에서 예약하고 전송한다. `LOADTEST_CALLBACK_URL`,
checkpoint 횟수와 지연 설정은 기존 값을 그대로 사용하므로 API가 받는 callback 부하는 유지된다.

EC2의 repository 경로와 가상환경 경로가 unit 파일의 기본값과 같다면 다음과 같이 설치한다.

```bash
sudo cp load_test/systemd/gifgloo-loadtest-fake-pipeline.service \
  /etc/systemd/system/gifgloo-loadtest-fake-pipeline.service
sudo systemctl daemon-reload
sudo systemctl enable --now gifgloo-loadtest-fake-pipeline
curl --fail http://127.0.0.1:8012/healthz
```

경로가 다르면 unit 파일의 `WorkingDirectory`, `EnvironmentFile`, `ExecStart`를 EC2 환경에 맞게
수정한다. worker는 loopback에만 bind하므로 Security Group 포트를 추가할 필요가 없다.

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
LOADTEST_PUSHGATEWAY_URL
LOADTEST_PUSHGATEWAY_INTERVAL_SECONDS
LOADTEST_RUN_ID
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

## Live Locust metrics

EC2 monitoring stack의 Pushgateway를 SSH tunnel로 연결한다.

```bash
ssh -N \
  -L 3000:127.0.0.1:3000 \
  -L 9090:127.0.0.1:9090 \
  -L 9091:127.0.0.1:9091 \
  gifgloo-loadtest
```

`run_remote_loadtest.sh`는 기본적으로 `http://127.0.0.1:9091`에 5초마다
현재 users, RPS, failure, 평균 및 p50/p95/p99/max 응답시간을 보낸다.
`Aggregated`는 SSE 대기 합성 이벤트를 포함하며, `HTTP Aggregated`는 실제 HTTP 요청만 집계한다.
모든 Locust 요청에는 `X-Loadtest-Run-ID`를 넣어 Nginx access log에서 같은 테스트의
`request_time`과 `upstream_response_time`을 분리해 확인한다.
Pushgateway 전송 없이 실행하려면 빈 값을 명시한다.

```bash
LOADTEST_PUSHGATEWAY_URL= ./load_test/run_remote_loadtest.sh
```

`LOADTEST_PIPELINE_MODE=external`이면 실행기가 Locust 시작 전에
`gifgloo-loadtest-fake-pipeline` 서비스를 재시작하고 readiness를 확인한다. thread capture가
활성화되어 있으면 API와 worker를 각각 수집해 결과 폴더에 다음 파일을 저장한다.

```text
api-thread-diagnostics.log
fake-pipeline-thread-diagnostics.log
```

## py-spy

원격 실행기는 성능 비교를 방해하지 않도록 기본적으로 py-spy를 비활성화한다. 함수 단위
프로파일이 필요한 run에서만 `LOADTEST_REMOTE_PYSPY_ENABLED=1`로 켠다. EC2 loadtest
가상환경에는 한 번 설치한다.

```bash
venv/bin/pip install py-spy
```

활성화하면 기본 sample rate 50Hz로 모든 Python thread를 구분한 speedscope 형식을 수집한다.

```text
api-speedscope.json
api-pyspy.log
```

`api-speedscope.json`은 https://www.speedscope.app 에서 열 수 있다. 첫 번째 조사는 FastAPI
프로세스만 대상으로 하며 fake pipeline worker에는 동시에 py-spy를 연결하지 않는다.
프로파일링을 끄거나 sample rate를 바꾸려면 로컬 실행 환경에 설정한다.

```text
LOADTEST_REMOTE_PYSPY_ENABLED=0
LOADTEST_PYSPY_RATE=50
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
