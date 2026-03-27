"""Dashboard data bridge — serves analisidef's dashboard_data.json as-is."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import ORJSONResponse, JSONResponse

from backend.config import ANALISIDEF_DAILY_DIR

router = APIRouter()

DASHBOARD_JSON = ANALISIDEF_DAILY_DIR / "dashboard_data.json"


@router.get("/dashboard-data")
def get_dashboard_data():
    """Serve the full dashboard_data.json produced by analisidef's daily routine.
    This is the bridge: analisidef calculates, App_tool serves."""
    if not DASHBOARD_JSON.exists():
        raise HTTPException(404, "dashboard_data.json not found. Is analisidef daily routine running?")

    with open(DASHBOARD_JSON) as f:
        data = json.load(f)

    return JSONResponse(content=data)
