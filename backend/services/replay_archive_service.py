"""Replay archive service — PG-backed source for replay viewer endpoints."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.analysis import ReplayArchive
from backend.models.match import Match

_LEGACY_TO_PG = {"AS": "AmSa", "ES": "EmSa"}


def normalize_deck_code(code: str) -> str:
    return _LEGACY_TO_PG.get(code, code)


def get_latest_archive(
    db: Session,
    deck: str,
    opp: str,
    game_format: str = "core",
) -> ReplayArchive | None:
    stmt = (
        select(ReplayArchive)
        .where(
            ReplayArchive.game_format == game_format,
            ReplayArchive.our_deck == normalize_deck_code(deck),
            ReplayArchive.opp_deck == normalize_deck_code(opp),
        )
        .order_by(
            ReplayArchive.generated_at.desc(),
            ReplayArchive.imported_at.desc(),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _game_won(g: dict) -> bool:
    # Legacy analisidef archives carry `result: "W"|"L"`; App_tool-native
    # archives carry `we_won: bool`. Support both.
    if g.get("we_won") is not None:
        return bool(g["we_won"])
    return str(g.get("result", "")).upper().startswith("W")


def build_replay_list(archive: ReplayArchive) -> list[dict]:
    games = archive.games or []
    refs = _lookup_match_refs(archive, games)
    return [
        {
            "i": i,
            "r": "W" if _game_won(g) else "L",
            "otp": g.get("we_otp", False),
            "on": g.get("our_name", ""),
            "en": g.get("opp_name", ""),
            "om": g.get("our_mmr", 0),
            "em": g.get("opp_mmr", 0),
            "l": g.get("length", 0),
            "d": g.get("date", ""),
            "match_id": refs.get(i, {}).get("match_id"),
            "external_id": refs.get(i, {}).get("external_id"),
        }
        for i, g in enumerate(games)
    ]


def get_replay_game(archive: ReplayArchive, idx: int) -> dict | None:
    games = archive.games or []
    if idx < 0 or idx >= len(games):
        return None
    game = dict(games[idx])
    refs = _lookup_match_refs(archive, [game])
    game.update(refs.get(0, {}))
    return game


def _extract_external_id(game: dict) -> str | None:
    file_name = game.get("file") or ""
    if not file_name:
        return None
    stem = Path(file_name).stem.strip()
    return stem or None


def _lookup_match_refs(archive: ReplayArchive, games: list[dict]) -> dict[int, dict]:
    if not games:
        return {}
    db = Session.object_session(archive)
    if db is None:
        return {}

    ext_ids = []
    positions = {}
    for idx, game in enumerate(games):
        ext_id = _extract_external_id(game)
        if not ext_id:
            continue
        ext_ids.append(ext_id)
        positions[idx] = ext_id
    if not ext_ids:
        return {}

    rows = db.execute(
        select(Match.id, Match.external_id).where(Match.external_id.in_(ext_ids))
    ).all()
    by_ext = {row.external_id: {"match_id": row.id, "external_id": row.external_id} for row in rows}
    return {idx: by_ext[ext_id] for idx, ext_id in positions.items() if ext_id in by_ext}
