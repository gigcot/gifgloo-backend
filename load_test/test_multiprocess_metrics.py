import os
import subprocess
import sys
import tempfile
import unittest


class MultiprocessMetricsTest(unittest.TestCase):
    def test_aggregates_counters_and_live_gauges_across_workers(self):
        worker_code = """
from shared.metrics import DB_POOL_CHECKED_OUT, FASTAPI_WORKER_PROCESSES, HTTP_REQUESTS_TOTAL
FASTAPI_WORKER_PROCESSES.set(1)
DB_POOL_CHECKED_OUT.labels(pool="async").set(__DB_CONNECTIONS__)
HTTP_REQUESTS_TOTAL.labels(method="GET", path="/users/me", status="200").inc(__REQUEST_COUNT__)
"""
        scrape_code = """
from shared.metrics import metrics_response
print(metrics_response().body.decode())
"""

        with tempfile.TemporaryDirectory() as multiprocess_dir:
            env = os.environ.copy()
            env["PROMETHEUS_MULTIPROC_DIR"] = multiprocess_dir
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    worker_code.replace("__DB_CONNECTIONS__", "2").replace(
                        "__REQUEST_COUNT__", "1"
                    ),
                ],
                check=True,
                env=env,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    worker_code.replace("__DB_CONNECTIONS__", "3").replace(
                        "__REQUEST_COUNT__", "2"
                    ),
                ],
                check=True,
                env=env,
            )
            metrics = subprocess.run(
                [sys.executable, "-c", scrape_code],
                check=True,
                capture_output=True,
                env=env,
                text=True,
            ).stdout

        self.assertIn("fastapi_worker_processes 2.0", metrics)
        self.assertIn('db_pool_checked_out{pool="async"} 5.0', metrics)
        self.assertIn(
            'http_requests_total{method="GET",path="/users/me",status="200"} 3.0',
            metrics,
        )
