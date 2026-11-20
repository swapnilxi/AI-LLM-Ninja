"""AgentForge API - multi-tenant multi-agent orchestration platform."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import BASE_DIR, settings
from app.core.db import init_db
from app.core.middleware import SecurityMiddleware
from app.core.seed import seed
from app.modules import routers
from app.modules.runs import service as run_engine
from app.modules.scheduler.service import scheduler_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agentforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed()
    await run_engine.recover_interrupted_runs()
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler_loop(stop)) if settings.scheduler_enabled else None
    log.info("%s ready (env=%s)", settings.app_name, settings.env)
    yield
    stop.set()
    if task:
        await asyncio.wait({task}, timeout=5)
    await run_engine.shutdown()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description="Multi-tenant multi-agent platform: agents, skills, tools, connectors, teams, workflows, automations.",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Middleware order: the last added runs first. CORS is outermost so even 429/413 carry CORS headers.
app.add_middleware(SecurityMiddleware)
if settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Org-Id", "X-Api-Key", "Last-Event-ID"],
    max_age=600,
)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg", "")} for e in exc.errors()][:20]
    first = errors[0] if errors else {"loc": [], "msg": "Invalid request"}
    return JSONResponse({"detail": f"{'.'.join(first['loc'][1:]) or 'request'}: {first['msg']}", "errors": errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok", "app": settings.app_name}


for r in routers():  # every feature module contributes its own router(s); see app/modules/__init__.py
    app.include_router(r, prefix="/api")


# ---------------------------------------------------------------- optional: serve the built frontend
_DIST = (BASE_DIR.parent / "frontend" / "dist").resolve()
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (_DIST / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(_DIST)):
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
