def test_metrics_exposes_request_counters(client, monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    client.get("/health")
    body = client.get("/metrics").text
    assert 'leadex_http_requests_total{method="GET",route="/health",status="200"}' in body
    assert "leadex_http_request_duration_seconds_bucket" in body and "leadex_uptime_seconds" in body


def test_metrics_token_required_when_set(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200
