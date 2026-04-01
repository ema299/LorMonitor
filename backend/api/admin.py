"""Admin endpoints — health, metrics, refresh.
Health is public (for uptime checks). Everything else requires admin.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.deps import get_db, require_admin
from backend.models.user import User
from backend.services import dashboard_bridge

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """System health: DB connection, table counts. Public (for uptime monitors)."""
    try:
        counts = {}
        for table in ["matches", "killer_curves", "daily_snapshots", "users"]:
            row = db.execute(text(f"SELECT COUNT(*) AS c FROM {table}")).fetchone()
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
):
    """Recent audit log entries."""
    return dashboard_bridge.get_recent_logs(level=level, limit=limit)
