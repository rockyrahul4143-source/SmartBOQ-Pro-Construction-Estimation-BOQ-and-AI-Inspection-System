from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import time
import logging

from app.core.config import settings
from app.api.v1 import (
    auth, users, projects, buildings, materials,
    estimates, boq, reports, analytics, dxf, inspection,
    sor, measurement, rate_analysis, billing, drawing_takeoff,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow all origins in local dev ────────────
origins = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Process time header ───────────────────────────────
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round((time.time() - start) * 1000, 2))
    return response

# ── Static uploads (only mount if directory exists) ──
upload_dir = settings.UPLOAD_DIR
os.makedirs(upload_dir, exist_ok=True)
try:
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
except Exception:
    pass  # skip if empty on first run

# ── Routers ───────────────────────────────────────────
P = settings.API_V1_STR
app.include_router(auth.router,          prefix=f"{P}/auth",          tags=["Authentication"])
app.include_router(users.router,         prefix=f"{P}/users",          tags=["Users"])
app.include_router(projects.router,      prefix=f"{P}/projects",       tags=["Projects"])
app.include_router(buildings.router,     prefix=f"{P}/buildings",      tags=["Buildings"])
app.include_router(materials.router,     prefix=f"{P}/materials",      tags=["Materials"])
app.include_router(estimates.router,     prefix=f"{P}/estimates",      tags=["Quantity Estimation"])
app.include_router(boq.router,           prefix=f"{P}/boq",            tags=["BOQ"])
app.include_router(reports.router,       prefix=f"{P}/reports",        tags=["Reports"])
app.include_router(analytics.router,     prefix=f"{P}/analytics",      tags=["Analytics"])
app.include_router(dxf.router,           prefix=f"{P}/dxf",            tags=["DXF Import"])
app.include_router(inspection.router,    prefix=f"{P}/inspection",     tags=["AI Inspection"])
app.include_router(sor.router,           prefix=f"{P}/sor",            tags=["SOR / Item Master"])
app.include_router(measurement.router,   prefix=f"{P}/measurements",   tags=["Measurement Book"])
app.include_router(rate_analysis.router, prefix=f"{P}/rate-analysis",  tags=["Rate Analysis"])
app.include_router(billing.router,          prefix=f"{P}/billing",         tags=["RA Billing"])
app.include_router(drawing_takeoff.router,  prefix=f"{P}/drawing-takeoff",  tags=["Drawing Takeoff"])

@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}

@app.get("/", tags=["Root"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME} API", "docs": "/docs"}
