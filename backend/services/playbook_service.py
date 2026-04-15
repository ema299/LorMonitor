"""Playbook service — Blind Deck Playbook (Sprint-1 Liberation Day).

Espone le query principali per il frontend (Profile tab):
    get_playbook(db, deck, game_format) -> dict | None

E le primitive di scrittura usate dall'importer (mossa A) e in futuro dal
generatore nativo (mossa B).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_playbook(db: Session, deck: str, game_format: str = "core") -> dict | None:
    """Restituisce il playbook corrente per (deck, formato), o None.

    Selezione: il piu' recente con is_current=true. Se l'utente apre il Profile
    e il playbook non esiste ancora, il frontend nasconde l'accordion (fail
    closed: zero rumore).
    """
    row = db.execute(text("""
        SELECT playbook, strategic_frame, weekly_tech, pro_references,
               aggregated, meta, model, generated_at, total_games, digest_count
        FROM deck_playbooks
        WHERE deck = :deck
          AND game_format = :fmt
          AND is_current = true
        ORDER BY generated_at DESC
        LIMIT 1
    """), {"deck": deck, "fmt": game_format}).fetchone()

    if not row:
        return None

    return {
        "deck": deck,
        "format": game_format,
        "generated_at": row[7].isoformat() if row[7] else None,
        "playbook": row[0],
        "strategic_frame": row[1],
        "weekly_tech": row[2],
        "pro_references": row[3],
        "aggregated": row[4],
        "meta": row[5],
        "model": row[6],
        "total_games": row[8],
        "digest_count": row[9],
    }


def list_available(db: Session, game_format: str = "core") -> list[dict]:
    """Lista deck con playbook disponibile per il formato. Usato per debug/admin."""
    rows = db.execute(text("""
        SELECT deck, generated_at, total_games
        FROM deck_playbooks
        WHERE game_format = :fmt AND is_current = true
        ORDER BY deck
    """), {"fmt": game_format}).fetchall()
    return [{"deck": r[0], "generated_at": r[1].isoformat(), "total_games": r[2]} for r in rows]


def upsert_playbook(
    db: Session,
    deck: str,
    game_format: str,
    payload: dict[str, Any],
    *,
    generated_at: date | None = None,
) -> int:
    """Inserisce un nuovo playbook e marca i precedenti per (deck,fmt) come not current.

    Atomico via UPDATE+INSERT in singola transazione. Idempotente sulla coppia
    (deck, game_format, generated_at) — replay dello stesso input non duplica.

    payload deve avere chiave 'playbook' (obbligatoria). Le altre sezioni
    (strategic_frame, weekly_tech, pro_references, aggregated, meta) sono
    opzionali e tengono lo schema fluido.

    Returns: id della row inserita (o aggiornata).
    """
    if "playbook" not in payload:
        raise ValueError("payload must contain 'playbook' key")

    gen_at = generated_at or _extract_date(payload.get("meta", {})) or date.today()

    # Marca le vecchie come not-current (anche per la stessa data se idempotent retry)
    db.execute(text("""
        UPDATE deck_playbooks
        SET is_current = false
        WHERE deck = :deck AND game_format = :fmt AND is_current = true
    """), {"deck": deck, "fmt": game_format})

    meta = payload.get("meta") or {}
    cost_usd = meta.get("estimated_cost_usd")
    elapsed = meta.get("elapsed_sec")

    row = db.execute(text("""
        INSERT INTO deck_playbooks
            (deck, game_format, generated_at, playbook, strategic_frame,
             weekly_tech, pro_references, aggregated, meta, model,
             input_tokens, output_tokens, cost_usd, digest_count, total_games,
             elapsed_sec, is_current)
        VALUES
            (:deck, :fmt, :gen_at, :playbook, :strategic_frame,
             :weekly_tech, :pro_references, :aggregated, :meta, :model,
             :input_tokens, :output_tokens, :cost_usd, :digest_count, :total_games,
             :elapsed_sec, true)
        ON CONFLICT (deck, game_format, generated_at)
        DO UPDATE SET
            playbook = EXCLUDED.playbook,
            strategic_frame = EXCLUDED.strategic_frame,
            weekly_tech = EXCLUDED.weekly_tech,
            pro_references = EXCLUDED.pro_references,
            aggregated = EXCLUDED.aggregated,
            meta = EXCLUDED.meta,
            model = EXCLUDED.model,
            input_tokens = EXCLUDED.input_tokens,
            output_tokens = EXCLUDED.output_tokens,
            cost_usd = EXCLUDED.cost_usd,
            digest_count = EXCLUDED.digest_count,
            total_games = EXCLUDED.total_games,
            elapsed_sec = EXCLUDED.elapsed_sec,
            is_current = true
        RETURNING id
    """), {
        "deck": deck,
        "fmt": game_format,
        "gen_at": gen_at,
        "playbook": _json_dump(payload["playbook"]),
        "strategic_frame": _json_dump(payload.get("strategic_frame")),
        "weekly_tech": _json_dump(payload.get("weekly_tech")),
        "pro_references": _json_dump(payload.get("pro_references")),
        "aggregated": _json_dump(payload.get("aggregated")),
        "meta": _json_dump(meta),
        "model": meta.get("model"),
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "cost_usd": Decimal(str(cost_usd)) if cost_usd is not None else None,
        "digest_count": meta.get("digest_count"),
        "total_games": meta.get("total_games"),
        "elapsed_sec": Decimal(str(elapsed)) if elapsed is not None else None,
    }).scalar()

    db.commit()
    return row


def _extract_date(meta: dict) -> date | None:
    raw = meta.get("generated_at")
    if not raw:
        return None
    try:
        # Accetta sia "2026-04-15" che "2026-04-15T08:09:00" che timestamp ISO
        return datetime.fromisoformat(raw).date()
    except Exception:
        try:
            return date.fromisoformat(raw[:10])
        except Exception:
            return None


def _json_dump(obj):
    if obj is None:
        return None
    import json
    return json.dumps(obj, ensure_ascii=False)
