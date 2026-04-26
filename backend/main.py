"""Lorcana Monitor — FastAPI entrypoint."""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api import auth, promo, monitor, coach, lab, admin, dashboard, team, user, community, subscription, profile, news, feedback
from backend.config import CORS_ALLOW_CREDENTIALS, CORS_ALLOW_ORIGINS
from backend.api.dashboard import warmup_cache
from backend.deps import get_db
from backend.middleware.error_handler import global_exception_handler
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.services import replay_archive_service, match_log_features_service, replay_anonymizer
from backend.models.match import Match
from backend.models.log_feature import MatchLogFeature

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_LEGACY_DIR = BASE_DIR / "frontend"
FRONTEND_V3_DIR = BASE_DIR / "frontend_v3"
FRONTEND_VARIANT = os.getenv("APPTOOL_FRONTEND_VARIANT", "legacy").strip().lower()
FRONTEND_DIR = FRONTEND_V3_DIR if FRONTEND_VARIANT == "v3" else FRONTEND_LEGACY_DIR

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
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
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
app.include_router(news.router, prefix="/api/v1/news", tags=["News"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["Profile"])
app.include_router(subscription.router, prefix="/api/v1", tags=["Subscription"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(feedback.router, prefix="/api/v1", tags=["Feedback"])


@app.on_event("startup")
def _startup_warmup():
    """Pre-populate dashboard cache so the first user never waits 12s."""
    import threading
    threading.Thread(target=warmup_cache, daemon=True).start()


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "frontend": FRONTEND_VARIANT if FRONTEND_DIR == FRONTEND_V3_DIR else "legacy"}


# Serve dashboard
def _serve_dashboard():
    content = (FRONTEND_DIR / "dashboard.html").read_text()
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/")
def serve_dashboard():
    return _serve_dashboard()


@app.head("/")
def serve_dashboard_head():
    return _serve_dashboard()


@app.get("/dashboard.html")
def serve_dashboard_alias():
    return _serve_dashboard()


@app.head("/dashboard.html")
def serve_dashboard_alias_head():
    return _serve_dashboard()


@app.get("/about.html")
def serve_about():
    # About/legal policy remains canonical in the legacy static tree during the V3 cutover.
    return FileResponse(FRONTEND_LEGACY_DIR / "about.html", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.head("/about.html")
def serve_about_head():
    return serve_about()


@app.get("/chart.min.js")
def serve_chart_js():
    return FileResponse(FRONTEND_DIR / "chart.min.js")


@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(FRONTEND_DIR / "manifest.json")


@app.get("/sw.js")
def serve_service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/icon-192.svg")
def serve_icon_192():
    return FileResponse(FRONTEND_DIR / "icon-192.svg")


@app.get("/icon-512.svg")
def serve_icon_512():
    return FileResponse(FRONTEND_DIR / "icon-512.svg")


@app.get("/robots.txt")
def serve_robots_txt():
    path = FRONTEND_DIR / "robots.txt"
    if not path.exists():
        path = FRONTEND_LEGACY_DIR / "robots.txt"
    return FileResponse(path)


# V3 staging — served on /v3/ path (does NOT touch the production / root).
# Purpose: manual test of frontend_v3/ without swapping the default.
# Keep during cutover as an explicit preview/rollback comparison surface.
def _serve_dashboard_v3():
    content = (FRONTEND_V3_DIR / "dashboard.html").read_text()
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/v3")
def serve_dashboard_v3_redirect():
    # Force trailing slash so relative asset paths in V3 resolve under /v3/.
    return RedirectResponse(url="/v3/", status_code=308)


@app.get("/v3/")
def serve_dashboard_v3():
    return _serve_dashboard_v3()


@app.get("/v3/dashboard.html")
def serve_dashboard_v3_alias():
    return _serve_dashboard_v3()


# Cards DB for replay viewer and profile tech card images (public, no auth)
_DUELS_ENRICHMENT: dict | None = None

def _load_duels_enrichment() -> dict:
    """Lazy-load name → {inkable, subtypes} from the duels.ink cache JSON.
    Memo-cached once per process. Enriches the slim cards_db response
    without touching the PG schema — lets the frontend compute deck
    composition (inkable ratio, Character/Action/Song/Item/Location
    breakdown) from a single endpoint."""
    global _DUELS_ENRICHMENT
    if _DUELS_ENRICHMENT is not None:
        return _DUELS_ENRICHMENT
    import json
    from pathlib import Path
    cache_path = Path("/mnt/HC_Volume_104764377/finanza/Lor/duels_ink_cards_cache.json")
    result: dict[str, dict] = {}
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                cache = json.load(f)
            for name, card in cache.items():
                if not isinstance(card, dict):
                    continue
                entry: dict = {}
                if "inkable" in card and card["inkable"] is not None:
                    entry["inkable"] = bool(card["inkable"])
                subtypes = card.get("subtypes")
                if isinstance(subtypes, list) and subtypes:
                    entry["subtypes"] = [str(s) for s in subtypes if s]
                if entry:
                    result[name] = entry
        except Exception:
            pass
    _DUELS_ENRICHMENT = result
    return result


@app.get("/api/replay/cards_db")
def replay_cards_db(db: Session = Depends(get_db)):
    """Slim cards DB: name → {cost, type, ink, str, will, lore, ability, set, number, inkable, subtypes}."""
    rows = db.execute(text(
        "SELECT name, cost, card_type, ink, str, will, lore, ability, set_code, card_number FROM cards"
    )).fetchall()
    enrichment = _load_duels_enrichment()
    slim = {}
    for r in rows:
        entry = {
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
        extra = enrichment.get(r.name)
        if extra:
            if "inkable" in extra:
                entry["inkable"] = extra["inkable"]
            if "subtypes" in extra:
                entry["subtypes"] = extra["subtypes"]
        slim[r.name] = entry
    return JSONResponse(content=slim)


@app.get("/api/replay/list")
def replay_list(
    deck: str = "",
    opp: str = "",
    format: str = "core",
    game_format: str | None = Query(None, pattern="^(core|infinity)$"),
    db: Session = Depends(get_db),
):
    if not deck or not opp:
        return JSONResponse({"error": "deck and opp required"}, 400)
    fmt = game_format or format
    if fmt not in ("core", "infinity"):
        return JSONResponse({"error": "format must be core or infinity"}, 400)
    archive = replay_archive_service.get_latest_archive(db, deck, opp, fmt)
    if not archive:
        return JSONResponse({"error": "archive not found", "games": []}, 404)
    game_list = replay_archive_service.build_replay_list(archive)
    return JSONResponse({"games": game_list, "total": len(game_list), "format": fmt})


@app.get("/api/replay/game")
def replay_game(
    deck: str = "",
    opp: str = "",
    idx: int = 0,
    format: str = "core",
    game_format: str | None = Query(None, pattern="^(core|infinity)$"),
    db: Session = Depends(get_db),
):
    if not deck or not opp:
        return JSONResponse({"error": "deck and opp required"}, 400)
    fmt = game_format or format
    if fmt not in ("core", "infinity"):
        return JSONResponse({"error": "format must be core or infinity"}, 400)
    archive = replay_archive_service.get_latest_archive(db, deck, opp, fmt)
    if not archive:
        return JSONResponse({"error": "archive not found"}, 404)
    game = replay_archive_service.get_replay_game(archive, idx)
    if game is None:
        return JSONResponse({"error": "game index out of range"}, 404)
    return JSONResponse(game)


@app.get("/api/replay/public-log")
def replay_public_log(
    match_id: int = 0,
    db: Session = Depends(get_db),
):
    """Normalized viewer-safe public log extracted from matches.turns."""
    if not match_id:
        return JSONResponse({"error": "match_id required"}, 400)
    row = db.query(MatchLogFeature).filter(MatchLogFeature.match_id == match_id).first()
    if not row or (row.extractor_version or 0) < match_log_features_service.EXTRACTOR_VERSION:
        match = db.query(Match).filter(Match.id == match_id).first()
        if match:
            row = match_log_features_service.upsert_match_log_features(db, match)
            db.commit()
            db.refresh(row)
    if not row:
        return JSONResponse({"error": "public log not found"}, 404)
    # Privacy layer §24.7: anonymize nicknames on the public viewer path.
    # Row persists raw nicknames; masking happens only on the response.
    masked_log = replay_anonymizer.anonymize_viewer_public_log(row.viewer_public_log)
    return JSONResponse(
        {
            "match_id": row.match_id,
            "extractor_version": row.extractor_version,
            "match_summary": row.match_summary,
            "viewer_public_log": masked_log,
            "player1_features": row.player1_features,
            "player2_features": row.player2_features,
        }
    )


# Serve V3 static assets (mounted BEFORE root mount so /v3/assets/... wins)
app.mount("/v3", StaticFiles(directory=str(FRONTEND_V3_DIR)), name="frontend_v3")

# Serve active frontend assets. In V3 mode avoid a catch-all "/" static mount so API routes
# cannot be shadowed by the static app during the cutover.
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend_assets")
app.mount("/deck_icons", StaticFiles(directory=str(FRONTEND_DIR / "deck_icons")), name="frontend_deck_icons")

if FRONTEND_DIR == FRONTEND_LEGACY_DIR:
    # Legacy still relies on the root static mount for miscellaneous files.
    app.mount("/", StaticFiles(directory=str(FRONTEND_LEGACY_DIR)), name="frontend")
