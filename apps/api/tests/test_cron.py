def test_cron_disabled_without_secret(client, monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert client.get("/api/v1/internal/cron/minute").status_code == 404


def test_cron_requires_secret_and_runs(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value")
    assert client.get("/api/v1/internal/cron/minute").status_code == 401
    assert client.get("/api/v1/internal/cron/minute", headers={"Authorization": "Bearer nope"}).status_code == 401
    r = client.get("/api/v1/internal/cron/minute", headers={"Authorization": "Bearer s3cret-value"})
    assert r.status_code == 200, r.text
    assert set(r.json()["results"]) == {"saved_searches", "campaigns", "workflows"}
    assert client.get("/api/v1/internal/cron/nope", headers={"Authorization": "Bearer s3cret-value"}).status_code == 404
