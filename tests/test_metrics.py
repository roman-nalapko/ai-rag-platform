import httpx
import pytest

from app.core.metrics import Counter, Histogram


def test_counter_render() -> None:
    counter = Counter(
        name="test_requests_total",
        description="Total test requests",
        label_names=("method", "status"),
    )
    counter.inc(method="GET", status="200")
    counter.inc(value=2.0, method="POST", status="201")

    rendered = counter.render()
    assert "# HELP test_requests_total Total test requests" in rendered
    assert "# TYPE test_requests_total counter" in rendered
    assert 'test_requests_total{method="GET",status="200"} 1.0' in rendered
    assert 'test_requests_total{method="POST",status="201"} 2.0' in rendered


def test_counter_escapes_prometheus_label_values() -> None:
    counter = Counter(name="test_total", description="Test", label_names=("path",))
    counter.inc(path='line\n"quoted"\\path')

    assert 'path="line\\n\\"quoted\\"\\\\path"' in counter.render()


def test_histogram_render() -> None:
    histogram = Histogram(
        name="test_duration_seconds",
        description="Duration test",
        label_names=("endpoint",),
        buckets=(0.1, 0.5, 1.0),
    )
    histogram.observe(0.05, endpoint="qa")
    histogram.observe(0.4, endpoint="qa")
    histogram.observe(0.8, endpoint="qa")

    rendered = histogram.render()
    assert "# HELP test_duration_seconds Duration test" in rendered
    assert "# TYPE test_duration_seconds histogram" in rendered
    assert 'test_duration_seconds_bucket{endpoint="qa",le="0.1"} 1.0' in rendered
    assert 'test_duration_seconds_bucket{endpoint="qa",le="0.5"} 2.0' in rendered
    assert 'test_duration_seconds_bucket{endpoint="qa",le="1.0"} 3.0' in rendered
    assert 'test_duration_seconds_bucket{endpoint="qa",le="+Inf"} 3.0' in rendered
    assert 'test_duration_seconds_count{endpoint="qa"} 3.0' in rendered


@pytest.mark.asyncio
async def test_get_metrics_endpoint_returns_prometheus_format(
    api_client: httpx.AsyncClient,
) -> None:
    # Perform a request to populate metrics
    await api_client.get("/health")

    response = await api_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "rag_http_requests_total" in response.text
    assert "rag_http_request_duration_seconds" in response.text


@pytest.mark.asyncio
async def test_metrics_collapse_unmatched_paths(
    api_client: httpx.AsyncClient,
) -> None:
    unique_path = "/missing-metrics-cardinality-probe"
    response = await api_client.get(unique_path)
    assert response.status_code == 404

    metrics_response = await api_client.get("/metrics")
    assert unique_path not in metrics_response.text
    assert 'path="/__unmatched__"' in metrics_response.text
