"""Lorcana Monitor — FastAPI entrypoint."""
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api import auth, promo, monitor, coach, lab, admin, dashboard, team, user, community, subscription
from backend.deps import get_db
from backend.middleware.error_handler import global_exception_handler
from backend.middleware.rate_limit import RateLimitMiddleware

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="Lorcana Monitor API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Global error handler
app.add_exception_handler(Exception, global_exception_handler)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

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
app.include_router(community.router, prefix="/api/v1/community", tags=["Community"])
app.include_router(subscription.router, prefix="/api/v1", tags=["Subscription"])
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


# Cards DB for replay viewer and profile tech card images (public, no auth)
@app.get("/api/replay/cards_db")
def replay_cards_db(db: Session = Depends(get_db)):
    """Slim cards DB: name → {cost, type, ink, str, will, lore, ability, set, number}."""
    rows = db.execute(text(
        "SELECT name, cost, card_type, ink, str, will, lore, ability, set_code, card_number FROM cards"
    )).fetchall()
    slim = {}
    for r in rows:
        slim[r.name] = {
            "cost": r.cost or "",
            "type": r.card_type or "",
            "ink": r.ink or "",
            "str": r.str or "",
            "will": r.will or "",
            "lore": r.lore or "",
            "ability": r.ability or "",
            "set": r.set_code or "",
            "number": r.card_number or "",
        }
    return JSONResponse(content=slim)


# Serve all frontend static files (icons, manifest, chart.js, assets/)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
