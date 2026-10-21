import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.cache import cache_ping
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.modules.admin.router import router as admin_router
from app.modules.agent.router import router as agent_router
from app.modules.airports.router import router as airports_router
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import me_router
from app.modules.auth.router import router as auth_router
from app.modules.flights.router import router as flights_router
from app.modules.journey.router import router as journey_router
from app.modules.map_flow.router import portal as map_portal_router
from app.modules.map_flow.router import public as map_public_router
from app.modules.notifications.router import router as notifications_router
from app.modules.onboarding.router import router as onboarding_router
from app.modules.rides.router import router as rides_router
from app.modules.support.router import router as support_router
from app.modules.tickets.router import router as tickets_router

setup_logging()
log = logging.getLogger("airpal")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"request_id": rid, "path": request.url.path})
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    response.headers["x-request-id"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    log.info("request", extra={"request_id": rid, "path": request.url.path, "status": response.status_code,
                               "duration_ms": int((time.perf_counter() - start) * 1000)})
    return response


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
def ready():
    checks = {"cache": cache_ping(), "db": False}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass
    ok = all(checks.values())
    return JSONResponse({"status": "ready" if ok else "degraded", **checks}, status_code=200 if ok else 503)


API = "/api/v1"
for r in (auth_router, me_router, airports_router, flights_router, journey_router, map_public_router,
          map_portal_router, agent_router, tickets_router, support_router, rides_router, notifications_router,
          onboarding_router, analytics_router, admin_router):
    app.include_router(r, prefix=API)
