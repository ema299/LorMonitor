"""Meta-relevance guard for killer curves.

A card is "Core-legal" if its set is in `meta_epochs.legal_sets` — but not
every Core-legal card is in the current meta. GPT has a habit of suggesting
pre-rotation staples (Fishbone Quill, Hiram Flaversham - Toymaker) in Core
response lists because the legality guard alone does not model "what do
players actually run today."

This module returns the set of card names that have been CARD_PLAYED at
least `min_plays` times in the last `days` of matches for a given game
format — the operational definition of "in the current meta."

Consumed by:
- `pipelines.kc.build_prompt._build_meta_relevance_guard`
- `scripts.generate_killer_curves._strip_non_meta_cards`
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_CACHE: dict[tuple[str, int, int], set[str]] = {}


def get_meta_relevant_cards(
    db: Session,
    game_format: str = "core",
    days: int = 30,
    min_plays: int = 20,
) -> set[str]:
    key = (game_format, days, min_plays)
    if key in _CACHE:
        return _CACHE[key]
    rows = db.execute(
        text(
            """
            SELECT (c->>'name') AS card_name, COUNT(*) AS n
            FROM matches m,
                 jsonb_array_elements(m.turns) evt,
                 jsonb_array_elements(evt->'cardRefs') c
            WHERE m.game_format = :fmt
              AND m.played_at >= NOW() - make_interval(days => :days)
              AND m.turns IS NOT NULL AND m.turns != 'null'::jsonb
              AND evt->>'type' = 'CARD_PLAYED'
            GROUP BY card_name
            HAVING COUNT(*) >= :min
            """
        ),
        {"fmt": game_format, "days": days, "min": min_plays},
    ).fetchall()
    result = {r.card_name for r in rows if r.card_name}
    _CACHE[key] = result
    return result


def reset_cache() -> None:
    _CACHE.clear()
