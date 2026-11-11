"""Integration tests for performance, concurrency, and reliability benchmarks."""

from __future__ import annotations

import concurrent.futures
import time

import pytest
from ai_services.api.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_concurrent_api_requests(client: TestClient):
    """Benchmark concurrent read requests and assert high throughput with zero failures."""
    total_workers = 10
    requests_per_worker = 2
    latencies: list[float] = []

    def make_request():
        t0 = time.perf_counter()
        resp = client.get("/api/v1/analytics/overview?environment=dev")
        lat = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200
        return lat

    with concurrent.futures.ThreadPoolExecutor(max_workers=total_workers) as executor:
        futures = [
            executor.submit(make_request) for _ in range(total_workers * requests_per_worker)
        ]
        for f in concurrent.futures.as_completed(futures):
            latencies.append(f.result())

    assert len(latencies) == 20
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]

    # Assert sub-second concurrent latency on local testing
    assert p50 < 350.0, f"p50 latency too high: {p50:.2f}ms"
    assert p95 < 500.0, f"p95 latency too high: {p95:.2f}ms"


def test_statement_timeout_kills_expensive_query():
    """Verify analytics_reader role kills queries exceeding statement timeout."""
    import psycopg
    from shared.db import get_postgres_reader_connection

    with (
        get_postgres_reader_connection() as conn,
        conn.cursor() as cur,
        pytest.raises(psycopg.errors.QueryCanceled),
    ):
        cur.execute("SELECT pg_sleep(6);")


def test_sql_execution_clamps_row_limits():
    """Verify large queries are strictly capped at 1000 rows by the execution engine."""
    from ai_services.execution.engine import SQLExecutionEngine

    engine = SQLExecutionEngine(use_test_db=False)
    # fct_transactions has 5,000 rows; execution engine must clamp to 1000
    res = engine.execute_query(
        sql_query="SELECT * FROM analytics.fct_transactions;",
        max_rows=1000,
    )
    assert res.error is None
    assert res.row_count == 1000
    assert res.truncated is True
