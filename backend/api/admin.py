"""Admin endpoints — health, metrics, refresh.
Health is public (for uptime checks). Everything else requires admin.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.deps import get_db, require_admin, require_admin_or_server_token
from backend.models.user import User

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """System health: DB connection, table counts. Public (for uptime monitors)."""
    _HEALTH_TABLES = {
        "matches": text("SELECT COUNT(*) AS c FROM matches"),
        "killer_curves": text("SELECT COUNT(*) AS c FROM killer_curves"),
        "daily_snapshots": text("SELECT COUNT(*) AS c FROM daily_snapshots"),
        "users": text("SELECT COUNT(*) AS c FROM users"),
    }
    try:
        counts = {}
        for table, query in _HEALTH_TABLES.items():
            row = db.execute(query).fetchone()
            counts[table] = row.c
        return {"status": "healthy", "tables": counts}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.post("/refresh-views")
def refresh_materialized_views(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Refresh materialized views (mv_meta_share, mv_matchup_matrix)."""
    db.execute(text("REFRESH MATERIALIZED VIEW mv_meta_share"))
    db.execute(text("REFRESH MATERIALIZED VIEW mv_matchup_matrix"))
    db.commit()
    return {"status": "refreshed"}


@router.get("/metrics")
def metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Basic metrics: match count by day, format distribution."""
    rows = db.execute(text("""
        SELECT played_at::date AS day, game_format, COUNT(*) AS games
        FROM matches
        WHERE played_at >= now() - INTERVAL '7 days'
        GROUP BY played_at::date, game_format
        ORDER BY day DESC
    """)).fetchall()

    return [
        {"day": r.day.isoformat(), "format": r.game_format, "games": r.games}
        for r in rows
    ]


@router.post("/reset-legality-cache")
def reset_legality_cache(admin: User | None = Depends(require_admin_or_server_token)):
    """Invalidate in-process caches that depend on cards/meta_epochs.

    Call this after static_importer refreshes the `cards` table (new set
    reveal) or after an `alembic upgrade` that touches `meta_epochs`, so the
    running uvicorn picks up the change without a full restart.

    Cross-process use: the static importer cron runs in a separate process
    (uvicorn caches are unaffected by reset_checkers() from inside the worker).
    The wrapper `scripts/refresh_static_and_reset.sh` curls this endpoint
    immediately after the importer to keep the two in sync.
    """
    from backend.services.legality_service import reset_checkers
    reset_checkers()

    reset = ["legality_checkers"]
    # Invalidate the KC prompt-builder's cached legal_sets so the next batch
    # re-reads meta_epochs.legal_sets. Import inline to avoid cycles.
    try:
        from pipelines.kc import build_prompt
        build_prompt._core_legal_sets = None
        build_prompt._meta_relevant_by_fmt = {}
        reset.append("kc_legal_sets")
        reset.append("kc_meta_relevant")
    except Exception:
        pass
    # Also flush the meta_relevance module-level cache.
    try:
        from pipelines.kc import meta_relevance
        meta_relevance.reset_cache()
        reset.append("meta_relevance_cache")
    except Exception:
        pass

    return {"status": "ok", "reset": reset}


@router.post("/refresh-dashboard")
def refresh_dashboard(
    admin: User | None = Depends(require_admin_or_server_token),
    db: Session = Depends(get_db),
):
    """Force rebuild of the dashboard blob cache (2h TTL).

    Used after a cutover event (set rotation, legal_sets change) to make the
    fresh data visible immediately instead of waiting for the stale-while-
    revalidate window to flip.
    """
    from backend.api.dashboard import _rebuild_cache
    _rebuild_cache(db)
    return {"status": "ok", "refreshed": "dashboard_blob"}


@router.get("/logs")
def logs(
    level: str = Query("error"),
    limit: int = Query(100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recent audit log entries."""
    rows = db.execute(text("""
        SELECT id, event_type, user_id, ip_address, details, created_at
        FROM audit_log
        ORDER BY created_at DESC
        LIMIT :lim
    """), {"lim": limit}).fetchall()

    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "user_id": str(r.user_id) if r.user_id else None,
            "ip_address": str(r.ip_address) if r.ip_address else None,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
