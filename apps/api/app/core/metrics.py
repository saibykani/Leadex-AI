"""Prometheus-format metrics without extra dependencies.

GET /metrics exposes request counts, latency histograms and error counts per route template, plus business gauges
(active calls, open DSRs) read live from the database. In production it requires METRICS_TOKEN as a Bearer token
(or is disabled when METRICS_TOKEN is unset). Scrape it with Prometheus / Grafana Agent / any compatible tool.
"""
import os
import threading
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.routing import Match

from app.core.config import get_settings

BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_lock = threading.Lock()
_requests: dict[tuple[str, str, str], int] = defaultdict(int)
_hist: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0] * (len(BUCKETS) + 1))
_sum: dict[tuple[str, str], float] = defaultdict(float)
_errors: dict[str, int] = defaultdict(int)
_started = time.time()


def _route(app: FastAPI, request: Request) -> str:
    for r in app.router.routes:
        m, _ = r.matches(request.scope)
        if m == Match.FULL:
            return getattr(r, "path", "other")
    return "unmatched"


def record(method: str, route: str, status: int, seconds: float) -> None:
    with _lock:
        _requests[(method, route, str(status))] += 1
        h = _hist[(method, route)]
        for i, b in enumerate(BUCKETS):
            if seconds <= b:
                h[i] += 1
        h[-1] += 1
        _sum[(method, route)] += seconds
        if status >= 500:
            _errors[route] += 1


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def render(extra: dict[str, float] | None = None) -> str:
    out = ["# HELP leadex_http_requests_total HTTP requests", "# TYPE leadex_http_requests_total counter"]
    with _lock:
        for (m, r, s), n in sorted(_requests.items()):
            out.append(f'leadex_http_requests_total{{method="{m}",route="{_esc(r)}",status="{s}"}} {n}')
        out += ["# HELP leadex_http_request_duration_seconds Request latency",
                "# TYPE leadex_http_request_duration_seconds histogram"]
        for (m, r), h in sorted(_hist.items()):
            lbl = f'method="{m}",route="{_esc(r)}"'
            for i, b in enumerate(BUCKETS):
                out.append(f'leadex_http_request_duration_seconds_bucket{{{lbl},le="{b}"}} {h[i]}')
            out.append(f'leadex_http_request_duration_seconds_bucket{{{lbl},le="+Inf"}} {h[-1]}')
            out.append(f"leadex_http_request_duration_seconds_sum{{{lbl}}} {_sum[(m, r)]:.6f}")
            out.append(f"leadex_http_request_duration_seconds_count{{{lbl}}} {h[-1]}")
        out += ["# HELP leadex_http_errors_total 5xx responses", "# TYPE leadex_http_errors_total counter"]
        for r, n in sorted(_errors.items()):
            out.append(f'leadex_http_errors_total{{route="{_esc(r)}"}} {n}')
    out += ["# TYPE leadex_uptime_seconds gauge", f"leadex_uptime_seconds {time.time() - _started:.0f}"]
    for k, v in (extra or {}).items():
        out += [f"# TYPE {k} gauge", f"{k} {v}"]
    return "\n".join(out) + "\n"


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _measure(request: Request, call_next):
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            if request.url.path != "/metrics":
                record(request.method, _route(app, request), status, time.perf_counter() - t0)

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request):
        token = os.getenv("METRICS_TOKEN")
        if token:
            if request.headers.get("authorization") != f"Bearer {token}":
                return PlainTextResponse("unauthorized\n", status_code=401)
        elif get_settings().is_production:
            return PlainTextResponse("metrics disabled: set METRICS_TOKEN\n", status_code=404)
        return PlainTextResponse(render(), media_type="text/plain; version=0.0.4")


def init_error_tracking() -> str:
    """Optional Sentry-protocol error tracking (works with self-hosted GlitchTip, free). Needs `sentry-sdk`."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return "disabled"
    try:
        import sentry_sdk
    except ImportError:
        return "sdk_missing"
    sentry_sdk.init(dsn=dsn, environment=get_settings().app_env, traces_sample_rate=0.0, send_default_pii=False)
    return "enabled"
