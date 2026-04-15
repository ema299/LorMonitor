"""Replay archive service — PG-backed source for replay viewer endpoints."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.analysis import ReplayArchive

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


def build_replay_list(archive: ReplayArchive) -> list[dict]:
    games = archive.games or []
    return [
        {
            "i": i,
            "r": "W" if g.get("we_won") else "L",
            "otp": g.get("we_otp", False),
            "on": g.get("our_name", ""),
            "en": g.get("opp_name", ""),
            "om": g.get("our_mmr", 0),
            "em": g.get("opp_mmr", 0),
            "l": g.get("length", 0),
            "d": g.get("date", ""),
        }
        for i, g in enumerate(games)
    ]


def get_replay_game(archive: ReplayArchive, idx: int) -> dict | None:
    games = archive.games or []
    if idx < 0 or idx >= len(games):
        return None
    return games[idx]
