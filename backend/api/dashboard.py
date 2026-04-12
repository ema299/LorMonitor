"""Dashboard data — assembles the full dashboard blob from PostgreSQL tables."""
import gzip
import json
import logging
import threading
import time

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from backend.deps import get_db
from backend.models import SessionLocal
from backend.services.snapshot_assembler import assemble

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache: store both raw dict and pre-compressed gzip bytes
_cache: dict = {"blob": None, "gz": None, "ts": 0}
CACHE_TTL = 7200  # 2 hours (matches cron import cycle)
STALE_SERVE_WINDOW = 3600  # serve stale cache up to 1h past TTL while rebuilding
_rebuilding = False  # guard against concurrent background rebuilds


def _rebuild_cache(db: Session) -> None:
    """Rebuild cache (called in foreground or background thread)."""
    global _rebuilding
    t0 = time.time()
    try:
        blob = assemble(db)
        raw_json = json.dumps(blob, separators=(",", ":")).encode()
        gz_bytes = gzip.compress(raw_json, compresslevel=6)
        _cache["blob"] = blob
        _cache["gz"] = gz_bytes
        _cache["ts"] = time.time()
        elapsed = time.time() - t0
        logger.info("Dashboard cached in %.1fs: %d KB raw, %d KB gzip",
                     elapsed, len(raw_json) // 1024, len(gz_bytes) // 1024)
    except Exception:
        logger.exception("Background cache rebuild failed")
    finally:
        _rebuilding = False


def _rebuild_in_background() -> None:
    """Spawn a thread to rebuild cache without blocking the request."""
    global _rebuilding
    if _rebuilding:
        return
    _rebuilding = True

    def _worker():
        db = SessionLocal()
        try:
            _rebuild_cache(db)
        finally:
            db.close()

    threading.Thread(target=_worker, daemon=True).start()
    logger.info("Background cache rebuild started")


def warmup_cache() -> None:
    """Pre-populate cache at startup so the first user never waits."""
    if _cache["blob"]:
        return
    logger.info("Warming up dashboard cache...")
    db = SessionLocal()
    try:
        _rebuild_cache(db)
    finally:
        db.close()


@router.get("/dashboard-data")
def get_dashboard_data(
    request: Request,
    db: Session = Depends(get_db),
    refresh: bool = Query(False, description="Force cache refresh"),
):
    """Assemble dashboard data live from PostgreSQL tables.

    Uses stale-while-revalidate: if cache is expired but data exists,
    serves the stale version instantly and rebuilds in background.
    """
    now = time.time()
    cache_age = now - _cache["ts"]
    has_cache = _cache["blob"] is not None
    expired = cache_age >= CACHE_TTL

    if refresh and not has_cache:
        # Forced refresh with no cache — must block
        _rebuild_cache(db)
    elif refresh or (expired and not has_cache):
        # No stale data to serve — must block and build
        _rebuild_cache(db)
    elif expired and has_cache:
        # Stale-while-revalidate: serve old data, rebuild in background
        _rebuild_in_background()

    if not _cache["blob"]:
        return JSONResponse(content={"error": "cache building"}, status_code=503)

    # Serve pre-compressed if client accepts gzip
    accept_enc = request.headers.get("accept-encoding", "")
    if "gzip" in accept_enc and _cache["gz"]:
        return Response(
            content=_cache["gz"],
            media_type="application/json",
            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )

    return JSONResponse(content=_cache["blob"])
