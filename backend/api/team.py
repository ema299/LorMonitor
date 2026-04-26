"""Team coaching — replay upload, viewer, roster management.
TODO: Re-enable JWT auth (require_tier) when frontend login is implemented.
Currently protected only by nginx basic auth.

Privacy layer V3 (ARCHITECTURE.md §24.5):
- upload requires authenticated user (ownership non-negotiable)
- list/get filter by ownership when user is authenticated non-admin
- transitional nginx-only mode (user=None) preserves legacy behavior
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Response, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db, require_replay_owner, require_team_access, require_tier
from backend.models.team import ReplaySessionNote, TeamReplay, TeamRoster
from backend.models.user import User
from backend.services import replay_service

# B.2 MVP A — owner-only private notes. 50k chars cap is conservative for a
# coach-hobbyista (~10 A4 pages); raise if real usage hits the ceiling.
NOTE_BODY_MAX_CHARS = 50_000

# B.7.2 — Coach Workspace roster quotes.
COACH_ROSTER_QUOTA = 50  # max active students per coach
ROSTER_BULK_MAX_ROWS = 200  # CSV bulk per request

VALID_STATUS_ADMIN = {"invited", "active", "paused", "archived"}

router = APIRouter()


@router.post("/replay/upload")
async def upload_replay(
    file: UploadFile = File(...),
    player_override: str = Query(None, description="Override auto-matched player name"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a .replay.gz file from duels.ink. Parses and stores compact coaching data.

    Privacy layer §24.5/24.6:
    - authenticated user required (ownership non-negotiable)
    - explicit replay_upload consent required in preferences.consents.replay_upload
    - replay assigned user_id=current_user, is_private=true, uploaded_via='board_lab'
    """
    # Consent check — preferences.consents.replay_upload must exist with accepted_at
    consent = (user.preferences or {}).get("consents", {}).get("replay_upload")
    if not consent or not consent.get("accepted_at"):
        raise HTTPException(
            status_code=412,
            detail="replay_upload consent required — accept terms before uploading",
        )

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
        # Privacy layer — ownership + consent tracking
        user_id=user.id,
        is_private=True,
        consent_version=consent.get("version", "1.0"),
        uploaded_via="board_lab",
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
    user: User | None = Depends(require_team_access),
    db: Session = Depends(get_db),
):
    """List uploaded replays, optionally filtered by player.

    Privacy layer §24.5:
    - transitional mode (user=None, nginx-only): legacy behavior, all replays shown
    - authenticated admin: all replays shown
    - authenticated non-admin: only own replays + replays where user_id in shared_with
    """
    q = db.query(TeamReplay).order_by(TeamReplay.created_at.desc())
    if player:
        q = q.filter(TeamReplay.player_name.ilike(player))

    # Access-control: restrict to owned / shared when user is authenticated non-admin.
    # If user is None (transitional nginx-only mode) or admin, no filter applied.
    if user is not None and not user.is_admin:
        q = q.filter(
            or_(
                TeamReplay.user_id == user.id,
                TeamReplay.shared_with.op("@>")(f'["{user.id}"]'),
            )
        )

    replays = q.limit(100).all()
    user_id = user.id if user is not None else None
    is_admin = bool(user and user.is_admin)

    # has_note privacy-aware (B.2): true ONLY when the caller can author notes
    # (owner OR admin viewing the owner's note). Shared users / anonymous get
    # false even if a note exists — never leak existence of someone else's note.
    notes_replay_ids: set = set()
    if user_id is not None:
        target_replay_ids = []
        for r in replays:
            if is_admin and r.user_id is not None:
                target_replay_ids.append(r.id)
            elif r.user_id == user_id:
                target_replay_ids.append(r.id)
        if target_replay_ids:
            note_rows = (
                db.query(ReplaySessionNote.replay_id)
                .filter(
                    ReplaySessionNote.replay_id.in_(target_replay_ids),
                    # Match the user_id whose note will be returned by GET notes:
                    # admin sees owner's note, owner sees own.
                    or_(
                        ReplaySessionNote.user_id == user_id,
                        # Admin-viewing-owner branch: matches replay's user_id.
                        ReplaySessionNote.user_id == TeamReplay.user_id,
                    ) if is_admin else ReplaySessionNote.user_id == user_id,
                )
                .join(TeamReplay, TeamReplay.id == ReplaySessionNote.replay_id)
                .distinct()
                .all()
            )
            notes_replay_ids = {row[0] for row in note_rows}

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
            # is_owner drives client-side DELETE button visibility (B.3 UI trigger).
            # In transitional mode (user=None) it stays false — DELETE requires JWT.
            "is_owner": bool(user_id is not None and (is_admin or r.user_id == user_id)),
            # has_note hidden from shared / anonymous to avoid leaking existence.
            "has_note": r.id in notes_replay_ids,
        }
        for r in replays
    ]


@router.get("/replay/{game_id}")
def get_replay(
    game_id: str,
    user: User | None = Depends(require_team_access),
    db: Session = Depends(get_db),
):
    """Get full replay data for the coaching viewer.

    Privacy layer §24.5:
    - transitional mode (user=None): legacy behavior
    - admin: always allowed (incl. orphan records)
    - authenticated non-admin: owner or in shared_with only; 403 otherwise
    """
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if not replay:
        raise HTTPException(404, f"Replay {game_id} not found")

    # Access-control: apply only when user is authenticated
    if user is not None and not user.is_admin:
        if replay.user_id is None:
            # orphan legacy record, restricted to admin
            raise HTTPException(403, "replay access denied")
        if replay.user_id != user.id and str(user.id) not in (replay.shared_with or []):
            raise HTTPException(403, "replay access denied")

    return replay.replay_data


@router.delete("/replay/{game_id}", status_code=204)
def delete_replay(
    replay: TeamReplay = Depends(require_replay_owner),
    db: Session = Depends(get_db),
):
    """Delete an uploaded replay. Owner-only (admin bypasses).

    Privacy layer §24.5/24.6 — GDPR right to delete. Rejects shared users:
    only the owner (or admin) can permanently remove a replay.
    """
    db.delete(replay)
    db.commit()
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# Session notes (B.2 MVP A — owner-only private)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/replay/{game_id}/notes")
def get_replay_notes(
    replay: TeamReplay = Depends(require_replay_owner),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the owner's private note for this replay (or empty obj if none).

    Owner-only (admin bypasses). Shared users get 403 — they cannot read
    another user's private note.
    """
    # When admin acts on behalf of an owner, fetch the replay owner's note
    # (admin doesn't author notes; admin reads owner's note for ops/support).
    target_user_id = replay.user_id if (user.is_admin and replay.user_id) else user.id
    note = (
        db.query(ReplaySessionNote)
        .filter(
            ReplaySessionNote.replay_id == replay.id,
            ReplaySessionNote.user_id == target_user_id,
        )
        .first()
    )
    if not note:
        return {}
    return {
        "id": str(note.id),
        "body": note.body,
        "body_length_chars": note.body_length_chars,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.put("/replay/{game_id}/notes")
def upsert_replay_notes(
    replay: TeamReplay = Depends(require_replay_owner),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    payload: dict = Body(...),
):
    """Upsert the owner's note for this replay. Body schema: {"body": str}.

    Empty string is allowed (user explicitly cleared text but kept the row).
    For full deletion use DELETE.
    """
    body = payload.get("body")
    if not isinstance(body, str):
        raise HTTPException(status_code=400, detail="body must be a string")
    if len(body) > NOTE_BODY_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"body too long ({len(body)} chars; max {NOTE_BODY_MAX_CHARS})",
        )

    # Admin cannot author a note on behalf of an owner — admin can only READ.
    # Owner_id used for upsert.
    if user.is_admin and replay.user_id and replay.user_id != user.id:
        raise HTTPException(status_code=403, detail="admin cannot author notes for other users")

    note = (
        db.query(ReplaySessionNote)
        .filter(
            ReplaySessionNote.replay_id == replay.id,
            ReplaySessionNote.user_id == user.id,
        )
        .first()
    )
    if note is None:
        note = ReplaySessionNote(
            replay_id=replay.id,
            user_id=user.id,
            body=body,
            body_length_chars=len(body),
        )
        db.add(note)
    else:
        note.body = body
        note.body_length_chars = len(body)
        from sqlalchemy import func as _func
        note.updated_at = _func.now()
    db.commit()
    db.refresh(note)
    return {
        "id": str(note.id),
        "body": note.body,
        "body_length_chars": note.body_length_chars,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.delete("/replay/{game_id}/notes", status_code=204)
def delete_replay_notes(
    replay: TeamReplay = Depends(require_replay_owner),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the owner's note. Idempotent — 204 even if no note exists."""
    if user.is_admin and replay.user_id and replay.user_id != user.id:
        raise HTTPException(status_code=403, detail="admin cannot delete notes for other users")
    db.query(ReplaySessionNote).filter(
        ReplaySessionNote.replay_id == replay.id,
        ReplaySessionNote.user_id == user.id,
    ).delete()
    db.commit()
    return Response(status_code=204)


@router.get("/roster")
def get_roster(
    user: User | None = Depends(require_team_access),
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
    user: User | None = Depends(require_team_access),
    db: Session = Depends(get_db),
):
    """Get WR stats for a specific team player."""
    from backend.services import team_service
    return team_service.get_player_stats(db, name, game_format, days)


@router.get("/overview")
def team_overview(
    game_format: str = Query("core"),
    days: int = Query(30),
    user: User | None = Depends(require_team_access),
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
    user: User | None = Depends(require_team_access),
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
    user: User | None = Depends(require_team_access),
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


# ═══════════════════════════════════════════════════════════════════════════
# Coach roster (B.7.2 — per-coach students, separate from legacy team_roster)
# ═══════════════════════════════════════════════════════════════════════════


class StudentCreate(BaseModel):
    """Single student row creation. Coach is inferred from the JWT subject."""
    display_name: str = Field(..., min_length=1, max_length=100)
    duels_nick: str | None = Field(None, max_length=100)
    discord_username: str | None = Field(None, max_length=50)
    discord_id: str | None = Field(None, max_length=30)
    notes: str | None = None
    status_admin: str = Field("active")


class StudentBulkRow(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    duels_nick: str | None = Field(None, max_length=100)
    discord_username: str | None = Field(None, max_length=50)


class StudentBulkRequest(BaseModel):
    rows: list[StudentBulkRow] = Field(..., min_length=1, max_length=ROSTER_BULK_MAX_ROWS)


def _coach_active_students(db: Session, coach_id) -> int:
    """Count current non-archived, non-revoked students for the coach."""
    return (
        db.query(TeamRoster)
        .filter(
            TeamRoster.coach_id == coach_id,
            TeamRoster.revoked_at.is_(None),
            TeamRoster.status_admin != "archived",
        )
        .count()
    )


def _serialize_student(row: TeamRoster) -> dict:
    return {
        "id": str(row.id),
        "display_name": row.display_name or row.name,
        "status_admin": row.status_admin,
        "duels_nick": row.duels_nick,
        "duels_nick_status": row.duels_nick_status,
        "discord_username": row.discord_username,
        "discord_id": row.discord_id,
        "notes": row.notes,
        "added_at": row.added_at.isoformat() if row.added_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "student_user_id": str(row.student_user_id) if row.student_user_id else None,
    }


@router.get("/students")
def list_students(
    user: User = Depends(require_tier("coach")),
    db: Session = Depends(get_db),
    include_archived: bool = Query(False),
):
    """List the caller's coached students. Excludes revoked unless ``include_archived``."""
    q = db.query(TeamRoster).filter(TeamRoster.coach_id == user.id)
    if not include_archived:
        q = q.filter(
            TeamRoster.revoked_at.is_(None),
            TeamRoster.status_admin != "archived",
        )
    rows = q.order_by(TeamRoster.added_at.desc()).all()
    return {"students": [_serialize_student(r) for r in rows], "quota": COACH_ROSTER_QUOTA}


@router.post("/students", status_code=201)
def create_student(
    payload: StudentCreate,
    user: User = Depends(require_tier("coach")),
    db: Session = Depends(get_db),
):
    """Create a single student row attached to the caller's coach roster.

    Quote: ``COACH_ROSTER_QUOTA`` active students per coach. Duplicate
    ``display_name`` for the same coach is rejected by the unique idx.
    """
    status_admin = payload.status_admin if payload.status_admin in VALID_STATUS_ADMIN else "active"

    if status_admin != "archived":
        if _coach_active_students(db, user.id) >= COACH_ROSTER_QUOTA:
            raise HTTPException(
                status_code=400,
                detail=f"roster quota reached ({COACH_ROSTER_QUOTA} active students max). Archive a student first.",
            )

    duels_nick = (payload.duels_nick or "").strip() or None
    duels_nick_status = "unverified" if duels_nick else "missing"

    row = TeamRoster(
        # Legacy 'name' kept in sync with display_name to preserve readers
        # that still query the legacy column.
        name=payload.display_name.strip(),
        role=None,
        coach_id=user.id,
        display_name=payload.display_name.strip(),
        status_admin=status_admin,
        duels_nick=duels_nick,
        duels_nick_status=duels_nick_status,
        discord_username=(payload.discord_username or "").strip() or None,
        discord_id=(payload.discord_id or "").strip() or None,
        notes=payload.notes,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="display_name already exists for this coach")
    return _serialize_student(row)


@router.post("/students/bulk", status_code=200)
def create_students_bulk(
    payload: StudentBulkRequest,
    user: User = Depends(require_tier("coach")),
    db: Session = Depends(get_db),
):
    """CSV-style bulk import. Client parses CSV and posts a row list.

    Per-row failures (quota, duplicate display_name) reported in ``errors``.
    The remaining rows are still created. ``ROSTER_BULK_MAX_ROWS`` upper bound
    limits payload size; quota check still applies — total active students
    after import ≤ ``COACH_ROSTER_QUOTA``.
    """
    current_active = _coach_active_students(db, user.id)
    remaining_quota = max(0, COACH_ROSTER_QUOTA - current_active)
    created = 0
    errors: list[dict] = []

    for idx, r in enumerate(payload.rows):
        if remaining_quota <= 0:
            errors.append({"row": idx, "display_name": r.display_name, "error": "quota_exhausted"})
            continue
        duels_nick = (r.duels_nick or "").strip() or None
        row = TeamRoster(
            name=r.display_name.strip(),
            role=None,
            coach_id=user.id,
            display_name=r.display_name.strip(),
            status_admin="active",
            duels_nick=duels_nick,
            duels_nick_status="unverified" if duels_nick else "missing",
            discord_username=(r.discord_username or "").strip() or None,
        )
        db.add(row)
        try:
            db.flush()
            created += 1
            remaining_quota -= 1
        except Exception:
            db.rollback()
            errors.append({"row": idx, "display_name": r.display_name, "error": "duplicate_display_name"})

    if created:
        db.commit()

    return {"created": created, "errors": errors, "quota_remaining": remaining_quota}


@router.delete("/students/{student_id}", status_code=204)
def archive_student(
    student_id: str,
    user: User = Depends(require_tier("coach")),
    db: Session = Depends(get_db),
):
    """Soft-archive a student row (sets ``revoked_at`` + ``status_admin=archived``).

    Owner-coach only. Hard delete is intentionally NOT exposed — preserves
    audit trail of replay bindings (B.7.4) and notes (B.7.5) created during
    the coaching relationship.
    """
    row = (
        db.query(TeamRoster)
        .filter(TeamRoster.id == student_id, TeamRoster.coach_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="student not found")
    row.revoked_at = datetime.now(timezone.utc)
    row.status_admin = "archived"
    db.commit()
    return Response(status_code=204)
