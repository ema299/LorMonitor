"""Lorcana Monitor — FastAPI entrypoint."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import auth, promo, monitor, coach, lab, admin, dashboard, team, user
from backend.middleware.error_handler import global_exception_handler

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="Lorcana Monitor API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Global error handler
app.add_exception_handler(Exception, global_exception_handler)

# CORS — permissive in dev, da restringere in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(promo.router, prefix="/api/v1/promo", tags=["Promo"])
app.include_router(monitor.router, prefix="/api/v1/monitor", tags=["Monitor"])
app.include_router(coach.router, prefix="/api/v1/coach", tags=["Coach"])
app.include_router(lab.router, prefix="/api/v1/lab", tags=["Lab"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(team.router, prefix="/api/v1/team", tags=["Team"])
app.include_router(user.router, prefix="/api/v1/user", tags=["User"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


# Serve dashboard
@app.get("/")
def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/dashboard.html")
def serve_dashboard_alias():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


# Serve dashboard_data.json at paths the original template expects
from backend.config import ANALISIDEF_DAILY_DIR

@app.get("/output/dashboard_data.json")
@app.get("/dashboard_data.json")
def serve_dashboard_json():
    json_path = ANALISIDEF_DAILY_DIR / "dashboard_data.json"
    if json_path.exists():
        return FileResponse(str(json_path), media_type="application/json")
    return {"error": "dashboard_data.json not found"}


# Serve all frontend static files (icons, manifest, chart.js, assets/)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
