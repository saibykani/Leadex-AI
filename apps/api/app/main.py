from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError, register_error_handlers
from app.modules.registry import import_models, routers

settings = get_settings()
settings.validate_for_runtime()

app = FastAPI(
    title="LEADEX AI API",
    version="0.1.0",
    description="Discover Opportunities. Engage Intelligently. Convert Businesses.",
)
register_error_handlers(app)
from app.core import metrics as _metrics  # noqa: E402

_metrics.init_error_tracking()
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # httpOnly refresh cookie; origins are an explicit list, never "*"
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "Idempotency-Key", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


API = "/api/v1"
import_models()
for _r in routers():
    app.include_router(_r, prefix=API)

from app.worker.runner import install_runner  # noqa: E402

install_runner()  # CELERY_ENABLED=true -> workflow executions run on the Celery worker


_metrics.install(app)


@app.get("/health", tags=["health"])
def health():
    mode = "simulated" if settings.outbound_simulated else "live"
    return {"status": "ok", "env": settings.app_env, "outbound_mode": mode}


@app.get("/health/ready", tags=["health"])
def ready(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    if settings.redis_url:
        try:
            import redis

            redis.Redis.from_url(settings.redis_url, socket_timeout=1).ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
    else:
        checks["redis"] = "not_configured"
    if "error" in checks.values():
        raise AppError(503, "not_ready", "Dependencies unavailable", checks)
    return {"status": "ready", "checks": checks}
