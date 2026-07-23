# Monitoring

운영 EC2에서 Prometheus, Grafana, Loki, Alloy, exporter들을 함께 띄우는 설정이다.

## Run

```bash
docker compose --env-file .env -f monitoring/docker-compose.yml up -d
```

Grafana는 기본적으로 `127.0.0.1:3000`에만 바인딩한다. EC2에서는 SSH tunnel로 접근한다.

```bash
ssh -L 3000:127.0.0.1:3000 <ec2>
```

## Targets

Prometheus scrape 대상:

```text
node-exporter:9100
postgres-exporter:9187
nginx-exporter:9113
host.docker.internal:8000/metrics
```

`nginx-exporter`는 host의 `http://127.0.0.1:8080/nginx_status`에 대응되는
`http://host.docker.internal:8080/nginx_status`를 scrape한다.

FastAPI는 Uvicorn multi-worker 환경에서 `PROMETHEUS_MULTIPROC_DIR`의 mmap 파일을 합산해
`/metrics`로 노출한다. API systemd unit이 시작할 때 이전 프로세스의 mmap 파일을 지우므로
unit 밖에서 Uvicorn을 직접 실행할 때는 같은 directory를 재사용하지 않는다.

Nginx access log는 Loki에서 `request_time`, `upstream_connect_time`,
`upstream_header_time`, `upstream_response_time`을 LogQL p95/p99로 계산한다.
## Ports

```text
3000 Grafana      127.0.0.1 only
9090 Prometheus   127.0.0.1 only
3100 Loki         127.0.0.1 only
9100 node         127.0.0.1 only
9187 postgres     127.0.0.1 only
9113 nginx        127.0.0.1 only
12345 Alloy UI    127.0.0.1 only
```
