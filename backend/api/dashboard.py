"""Dashboard data — serves the full dashboard blob from PostgreSQL daily_snapshots."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.deps import get_db

router = APIRouter()


@router.get("/dashboard-data")
def get_dashboard_data(db: Session = Depends(get_db)):
    """Serve the full dashboard data blob from daily_snapshots (perimeter='full').

    This replaces the old file-based bridge that read analisidef's dashboard_data.json.
    The snapshot is populated by scripts/import_snapshots.py during the daily routine.
    """
    row = db.execute(text("""
        SELECT data FROM daily_snapshots
        WHERE perimeter = 'full'
        ORDER BY snapshot_date DESC
        LIMIT 1
    """)).fetchone()

    if not row:
        raise HTTPException(404, "No dashboard snapshot found in database.")

    return JSONResponse(content=row.data)
