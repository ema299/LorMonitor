"""Lorcana Monitor — FastAPI entrypoint."""
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api import auth, promo, monitor, coach, lab, admin, dashboard, team, user, community, subscription
from backend.api.dashboard import warmup_cache
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

# Gzip compression (responses > 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

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


@app.on_event("startup")
def _startup_warmup():
    """Pre-populate dashboard cache so the first user never waits 12s."""
    import threading
    threading.Thread(target=warmup_cache, daemon=True).start()


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


# Serve dashboard
def _serve_dashboard():
    content = (FRONTEND_DIR / "dashboard.html").read_text()
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/")
def serve_dashboard():
    return _serve_dashboard()


@app.get("/dashboard.html")
def serve_dashboard_alias():
    return _serve_dashboard()


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


# Replay archive — serves game lists/details from analisidef archive files
import json as _json
from pathlib import Path as _Path

_ARCHIVE_DIR = _Path("/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output")
_DECK_ALIAS = {"AmSa": "AS", "EmSa": "ES"}  # dashboard code → archive code


def _load_archive(deck: str, opp: str, fmt: str = "core"):
    deck_f = _DECK_ALIAS.get(deck, deck)
    opp_f = _DECK_ALIAS.get(opp, opp)
    suffix = "_inf" if fmt == "infinity" else ""
    fname = f"archive_{deck_f}_vs_{opp_f}{suffix}.json"
    path = _ARCHIVE_DIR / fname
    if not path.is_file():
        return None
    with open(path) as f:
        return _json.load(f)


@app.get("/api/replay/list")
def replay_list(deck: str = "", opp: str = "", format: str = "core"):
    if not deck or not opp:
        return JSONResponse({"error": "deck and opp required"}, 400)
    archive = _load_archive(deck, opp, format)
    if not archive:
        return JSONResponse({"error": "archive not found", "games": []}, 404)
    games = archive.get("games", [])
    game_list = [{
        "i": i, "r": "W" if g.get("we_won") else "L",
        "otp": g.get("we_otp", False),
        "on": g.get("our_name", ""), "en": g.get("opp_name", ""),
        "om": g.get("our_mmr", 0), "em": g.get("opp_mmr", 0),
        "l": g.get("length", 0), "d": g.get("date", ""),
    } for i, g in enumerate(games)]
    return JSONResponse({"games": game_list, "total": len(games)})


@app.get("/api/replay/game")
def replay_game(deck: str = "", opp: str = "", idx: int = 0, format: str = "core"):
    if not deck or not opp:
        return JSONResponse({"error": "deck and opp required"}, 400)
    archive = _load_archive(deck, opp, format)
    if not archive:
        return JSONResponse({"error": "archive not found"}, 404)
    games = archive.get("games", [])
    if idx < 0 or idx >= len(games):
        return JSONResponse({"error": "game index out of range"}, 404)
    return JSONResponse(games[idx])


# Serve all frontend static files (icons, manifest, chart.js, assets/)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
