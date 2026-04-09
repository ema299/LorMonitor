"""Team coaching — replay upload, viewer, roster management.
TODO: Re-enable JWT auth (require_tier) when frontend login is implemented.
Currently protected only by nginx basic auth.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from backend.deps import get_db
from backend.models.team import TeamReplay, TeamRoster
from backend.services import replay_service

router = APIRouter()


@router.post("/replay/upload")
async def upload_replay(
    file: UploadFile = File(...),
    player_override: str = Query(None, description="Override auto-matched player name"),
    db: Session = Depends(get_db),
):
    """Upload a .replay.gz file from duels.ink. Parses and stores compact coaching data."""
    if not file.filename or not file.filename.endswith((".gz", ".replay", ".replay.gz")):
        raise HTTPException(400, "File must be .replay.gz")

    contents = await file.read()
    if len(contents) > 500_000:  # 500KB max
        raise HTTPException(400, "File too large (max 500KB)")

    try:
        parsed = replay_service.parse_replay_gz(contents)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Check if already uploaded
    existing = db.query(TeamReplay).filter(TeamReplay.game_id == parsed["game_id"]).first()
    if existing:
        raise HTTPException(409, f"Game {parsed['game_id']} already uploaded")

    # Auto-match player or use override
    if player_override:
        matched_player = player_override
    else:
        roster = db.query(TeamRoster).all()
        roster_dicts = [{"name": r.name, "role": r.role} for r in roster]
        matched_player = replay_service.auto_match_player(parsed["player_names"], roster_dicts)

    if not matched_player:
        # Return player names so frontend can ask
        return {
            "status": "needs_assignment",
            "game_id": parsed["game_id"],
            "player_names": parsed["player_names"],
            "message": "No roster match found. Provide player_override.",
        }

    # Determine opponent
    perspective = parsed["perspective"]
    p_names = parsed["player_names"]
    our_name = p_names.get(str(perspective), "")
    opp_name = [n for k, n in p_names.items() if k != str(perspective)]
    opp_name = opp_name[0] if opp_name else ""

    replay = TeamReplay(
        player_name=matched_player,
        game_id=parsed["game_id"],
        perspective=perspective,
        opponent_name=opp_name,
        winner=parsed["winner"],
        victory_reason=parsed["victory_reason"],
        turn_count=parsed["turn_count"],
        replay_data=parsed,
    )
    db.add(replay)
    db.commit()

    return {
        "status": "ok",
        "game_id": parsed["game_id"],
        "player": matched_player,
        "opponent": opp_name,
        "turns": parsed["turn_count"],
        "winner": parsed["winner"],
    }


@router.get("/replay/list")
def list_replays(
    player: str = Query(None, description="Filter by player name"),
    db: Session = Depends(get_db),
):
    """List uploaded replays, optionally filtered by player."""
    q = db.query(TeamReplay).order_by(TeamReplay.created_at.desc())
    if player:
        q = q.filter(TeamReplay.player_name.ilike(player))

    replays = q.limit(100).all()
    return [
        {
            "id": str(r.id),
            "game_id": r.game_id,
            "player": r.player_name,
            "opponent": r.opponent_name,
            "winner": r.winner,
            "victory_reason": r.victory_reason,
            "turns": r.turn_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in replays
    ]


@router.get("/replay/{game_id}")
def get_replay(
    game_id: str,
    db: Session = Depends(get_db),
):
    """Get full replay data for the coaching viewer."""
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if not replay:
        raise HTTPException(404, f"Replay {game_id} not found")
    return replay.replay_data


@router.get("/roster")
def get_roster(
    db: Session = Depends(get_db),
):
    """Get team roster."""
    roster = db.query(TeamRoster).order_by(TeamRoster.added_at).all()
    return [{"name": r.name, "role": r.role, "added_at": r.added_at.isoformat()} for r in roster]


@router.get("/player/{name}/stats")
def player_stats(
    name: str,
    game_format: str = Query("core"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Get WR stats for a specific team player."""
    from backend.services import team_service
    return team_service.get_player_stats(db, name, game_format, days)


@router.get("/overview")
def team_overview(
    game_format: str = Query("core"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Get aggregated stats for all roster players."""
    from backend.services import team_service
    roster = db.query(TeamRoster).all()
    names = [r.name for r in roster]
    return team_service.get_team_overview(db, names, game_format, days)


@router.get("/weaknesses")
def team_weaknesses(
    game_format: str = Query("core"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Find worst matchups across the team."""
    from backend.services import team_service
    roster = db.query(TeamRoster).all()
    names = [r.name for r in roster]
    return team_service.get_team_weaknesses(db, names, game_format, days)


@router.put("/roster")
def update_roster(
    players: list[dict],
    db: Session = Depends(get_db),
):
    """Replace team roster. Input: [{"name": "CLOUD", "role": "grinder"}, ...]"""
    db.query(TeamRoster).delete()
    for p in players:
        name = p.get("name", "").strip()
        if not name:
            continue
        db.add(TeamRoster(name=name, role=p.get("role", "")))
    db.commit()
    return {"status": "ok", "count": len(players)}
