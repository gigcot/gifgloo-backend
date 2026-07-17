import logging
import os
import socket

import gevent
from gevent.event import Event
from locust import events
from locust.stats import StatsEntry
from prometheus_client import CollectorRegistry, Gauge, delete_from_gateway, push_to_gateway


logger = logging.getLogger(__name__)

PUSHGATEWAY_URL = os.environ.get("LOADTEST_PUSHGATEWAY_URL", "")
PUSH_INTERVAL_SECONDS = float(
    os.environ.get("LOADTEST_PUSHGATEWAY_INTERVAL_SECONDS", "5")
)
PROFILE = os.environ.get("LOADTEST_PROFILE", "manual")
RUN_ID = os.environ.get("LOADTEST_RUN_ID", "direct")
PUSHGATEWAY_INSTANCE = os.environ.get(
    "LOADTEST_PUSHGATEWAY_INSTANCE", socket.gethostname()
)
PUSHGATEWAY_JOB = "gifgloo_locust"


class LocustPushgatewayReporter:
    def __init__(self) -> None:
        self.grouping_key = {"instance": PUSHGATEWAY_INSTANCE}
        self.stop_event = Event()
        self.greenlet = None

    def start(self, environment) -> None:
        delete_from_gateway(
            PUSHGATEWAY_URL,
            job=PUSHGATEWAY_JOB,
            grouping_key=self.grouping_key,
            timeout=5,
        )
        self._push(environment, running=True)
        self.greenlet = gevent.spawn(self._run, environment)

    def stop(self, environment) -> None:
        self.stop_event.set()
        if self.greenlet is not None:
            self.greenlet.join(timeout=1)

        try:
            self._push(environment, running=False)
        except OSError as exc:
            logger.warning("Failed to push final Locust metrics: %s", exc)

    def _run(self, environment) -> None:
        while not self.stop_event.wait(PUSH_INTERVAL_SECONDS):
            try:
                self._push(environment, running=True)
            except OSError as exc:
                logger.warning("Failed to push Locust metrics: %s", exc)

    def _push(self, environment, running: bool) -> None:
        registry = self._build_registry(environment, running)
        push_to_gateway(
            PUSHGATEWAY_URL,
            job=PUSHGATEWAY_JOB,
            registry=registry,
            grouping_key=self.grouping_key,
            timeout=5,
        )

    def _build_registry(self, environment, running: bool) -> CollectorRegistry:
        registry = CollectorRegistry()
        run_labels = ["profile", "run_id"]
        request_labels = ["profile", "run_id", "method", "name"]

        running_metric = Gauge(
            "locust_test_running",
            "Whether the Locust test is currently running.",
            run_labels,
            registry=registry,
        )
        users_metric = Gauge(
            "locust_users",
            "Current number of Locust users.",
            run_labels,
            registry=registry,
        )
        request_count_metric = Gauge(
            "locust_request_count",
            "Cumulative Locust request count for the current run.",
            request_labels,
            registry=registry,
        )
        failure_count_metric = Gauge(
            "locust_failure_count",
            "Cumulative Locust failure count for the current run.",
            request_labels,
            registry=registry,
        )
        rps_metric = Gauge(
            "locust_requests_per_second",
            "Current Locust requests per second.",
            request_labels,
            registry=registry,
        )
        failures_per_second_metric = Gauge(
            "locust_failures_per_second",
            "Current Locust failures per second.",
            request_labels,
            registry=registry,
        )
        failure_ratio_metric = Gauge(
            "locust_failure_ratio",
            "Cumulative Locust failure ratio for the current run.",
            request_labels,
            registry=registry,
        )
        average_metric = Gauge(
            "locust_response_time_average_seconds",
            "Cumulative average Locust response time in seconds.",
            request_labels,
            registry=registry,
        )
        p50_metric = Gauge(
            "locust_response_time_p50_seconds",
            "Cumulative Locust p50 response time in seconds.",
            request_labels,
            registry=registry,
        )
        p95_metric = Gauge(
            "locust_response_time_p95_seconds",
            "Cumulative Locust p95 response time in seconds.",
            request_labels,
            registry=registry,
        )
        p99_metric = Gauge(
            "locust_response_time_p99_seconds",
            "Cumulative Locust p99 response time in seconds.",
            request_labels,
            registry=registry,
        )
        max_metric = Gauge(
            "locust_response_time_max_seconds",
            "Maximum Locust response time in seconds.",
            request_labels,
            registry=registry,
        )

        running_metric.labels(PROFILE, RUN_ID).set(1 if running else 0)
        users_metric.labels(PROFILE, RUN_ID).set(environment.runner.user_count)

        request_entries = list(environment.stats.entries.values())
        http_total = StatsEntry(environment.stats, "HTTP Aggregated", "")
        for entry in request_entries:
            if entry.method != "SSE":
                http_total.extend(entry)

        stats_entries = [environment.stats.total, http_total, *request_entries]
        for entry in stats_entries:
            method = entry.method or ""
            name = entry.name
            labels = (PROFILE, RUN_ID, method, name)
            request_count = entry.num_requests

            request_count_metric.labels(*labels).set(request_count)
            failure_count_metric.labels(*labels).set(entry.num_failures)
            rps_metric.labels(*labels).set(entry.current_rps)
            failures_per_second_metric.labels(*labels).set(entry.current_fail_per_sec)
            failure_ratio_metric.labels(*labels).set(
                entry.num_failures / request_count if request_count else 0
            )
            average_metric.labels(*labels).set(entry.avg_response_time / 1000)
            p50_metric.labels(*labels).set(
                entry.get_response_time_percentile(0.50) / 1000
            )
            p95_metric.labels(*labels).set(
                entry.get_response_time_percentile(0.95) / 1000
            )
            p99_metric.labels(*labels).set(
                entry.get_response_time_percentile(0.99) / 1000
            )
            max_metric.labels(*labels).set((entry.max_response_time or 0) / 1000)

        return registry


if PUSHGATEWAY_URL:
    reporter = LocustPushgatewayReporter()

    @events.test_start.add_listener
    def start_pushgateway_reporter(environment, **kwargs) -> None:
        reporter.start(environment)

    @events.test_stop.add_listener
    def stop_pushgateway_reporter(environment, **kwargs) -> None:
        reporter.stop(environment)
