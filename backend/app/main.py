import os
import gc
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.security import decode_token
from app.api.v1 import (
    auth, users, projects, buildings, materials,
    estimates, boq, reports, analytics, dxf, inspection,
    sor, measurement, rate_analysis, billing, drawing_takeoff,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify DB, warm ONNX runtime (don't preload models — saves RAM)."""
    logger.info("SmartBOQ starting up...")
    # Just check onnxruntime is importable — don't load models yet
    from app.services.ai_inspection import preload_all_models
    preload_all_models()
    # Force a GC pass after imports
    gc.collect()
    logger.info("Startup complete")
    yield
    # Shutdown
    gc.collect()
    logger.info("SmartBOQ shutdown")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────
origins = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Process-time header ───────────────────────────────
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round((time.time() - start) * 1000, 2))
    return response

# ── Upload directory ──────────────────────────────────
upload_dir = settings.UPLOAD_DIR
os.makedirs(upload_dir, exist_ok=True)

# ── Authenticated file serving ────────────────────────
# Replaces the old public StaticFiles mount.
# Every request must carry a valid JWT access token.
@app.get("/uploads/{file_path:path}", tags=["Files"], include_in_schema=False)
async def serve_upload(file_path: str, request: Request):
    # Token from Authorization header OR ?token= query param
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_str = auth_header[7:]
    else:
        token_str = request.query_params.get("token", "")

    if not token_str:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    payload = decode_token(token_str)
    if not payload or payload.get("type") != "access":
        return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

    # Path-traversal prevention
    safe_base = os.path.realpath(upload_dir)
    safe_path = os.path.realpath(os.path.join(safe_base, file_path))
    if not safe_path.startswith(safe_base + os.sep) and safe_path != safe_base:
        return JSONResponse({"detail": "Invalid path"}, status_code=400)

    if not os.path.isfile(safe_path):
        return JSONResponse({"detail": "File not found"}, status_code=404)

    return FileResponse(safe_path)


# ── Routers ───────────────────────────────────────────
P = settings.API_V1_STR
app.include_router(auth.router,             prefix=f"{P}/auth",           tags=["Authentication"])
app.include_router(users.router,            prefix=f"{P}/users",           tags=["Users"])
app.include_router(projects.router,         prefix=f"{P}/projects",        tags=["Projects"])
app.include_router(buildings.router,        prefix=f"{P}/buildings",       tags=["Buildings"])
app.include_router(materials.router,        prefix=f"{P}/materials",       tags=["Materials"])
app.include_router(estimates.router,        prefix=f"{P}/estimates",       tags=["Quantity Estimation"])
app.include_router(boq.router,              prefix=f"{P}/boq",             tags=["BOQ"])
app.include_router(reports.router,          prefix=f"{P}/reports",         tags=["Reports"])
app.include_router(analytics.router,        prefix=f"{P}/analytics",       tags=["Analytics"])
app.include_router(dxf.router,              prefix=f"{P}/dxf",             tags=["DXF Import"])
app.include_router(inspection.router,       prefix=f"{P}/inspection",      tags=["AI Inspection"])
app.include_router(sor.router,              prefix=f"{P}/sor",             tags=["SOR / Item Master"])
app.include_router(measurement.router,      prefix=f"{P}/measurements",    tags=["Measurement Book"])
app.include_router(rate_analysis.router,    prefix=f"{P}/rate-analysis",   tags=["Rate Analysis"])
app.include_router(billing.router,          prefix=f"{P}/billing",         tags=["RA Billing"])
app.include_router(drawing_takeoff.router,  prefix=f"{P}/drawing-takeoff", tags=["Drawing Takeoff"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["Root"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME} API", "docs": "/docs"}
