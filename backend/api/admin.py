"""Admin endpoints — health, metrics, refresh.
Health is public (for uptime checks). Everything else requires admin.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.deps import get_db, require_admin
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
