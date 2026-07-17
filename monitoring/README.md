# Monitoring

Loadtest EC2에서 Prometheus, Grafana, Loki, Alloy, exporter들을 함께 띄우는 설정이다.

## Run

```bash
docker compose --env-file .env.loadtest -f monitoring/docker-compose.yml up -d
```

Grafana는 기본적으로 `127.0.0.1:3000`에만 바인딩한다. EC2에서는 SSH tunnel로 접근한다.

```bash
ssh -L 3000:127.0.0.1:3000 <ec2>
```

로컬 Locust 실시간 지표까지 전달하려면 Pushgateway 포트를 함께 연결한다.

```bash
ssh -N \
  -L 3000:127.0.0.1:3000 \
  -L 9090:127.0.0.1:9090 \
  -L 9091:127.0.0.1:9091 \
  <ec2>
```

## Targets

Prometheus scrape 대상:

```text
node-exporter:9100
postgres-exporter:9187
nginx-exporter:9113
host.docker.internal:8001/metrics
pushgateway:9091
```

`nginx-exporter`는 host의 `http://127.0.0.1:8080/nginx_status`에 대응되는
`http://host.docker.internal:8080/nginx_status`를 scrape한다.

Nginx access log는 Loki에서 `request_time`, `upstream_connect_time`,
`upstream_header_time`, `upstream_response_time`을 LogQL p95/p99로 계산한다.
Locust 요청의 `X-Loadtest-Run-ID`는 `loadtest_run_id` Loki label로 보존되어
대시보드의 테스트 실행 선택에 사용된다.

nginx 예시는 `monitoring/nginx/loadtest.example.conf`에 있다. 실제 EC2에서는
nginx 설정 경로에 복사한 뒤 `nginx -t`로 검증하고 reload한다.

## Ports

```text
3000 Grafana      127.0.0.1 only
9090 Prometheus   127.0.0.1 only
9091 Pushgateway  127.0.0.1 only
3100 Loki         127.0.0.1 only
9100 node         127.0.0.1 only
9187 postgres     127.0.0.1 only
9113 nginx        127.0.0.1 only
12345 Alloy UI    127.0.0.1 only
```
