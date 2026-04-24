"""Replay payload anonymizer — replaces player nicknames with stable placeholders.

Applied on the PUBLIC Replay Viewer pipeline (API /api/replay/list,
/api/replay/game, /api/replay/public-log). Board Lab (owner-view) payloads
bypass anonymization — that surface shows user-uploaded data to the owner.

Ref: ARCHITECTURE.md §24.7

Design notes:
- Idempotent: calling twice yields identical output. "Player"/"Opponent"
  strings pass through _anonymize_fields_inplace unchanged.
- Whitelist-based: only explicit known fields are masked. Card names, ability
  text, board state, etc. pass through untouched.
- Shallow + one-level deep for match_meta.player_names (dict): no recursive
  scan for PII across unknown schemas — reduces risk of breaking consumers.
"""
from __future__ import annotations


# Fields known to carry a player nickname as a plain string value.
# Source side (the "our" deck perspective in archive-based analytics).
_PLAYER_NAME_FIELDS = frozenset({
    "our_name",       # replay_archive: our side full name
    "player_a_name",  # match.player_a_name
})
# Opponent side.
_OPPONENT_NAME_FIELDS = frozenset({
    "opp_name",       # replay_archive: opp side full name
    "player_b_name",  # match.player_b_name
})
# Compact field names in build_replay_list output.
_SHORT_PLAYER_NAME_FIELDS = frozenset({"on"})       # our name (compact)
_SHORT_OPPONENT_NAME_FIELDS = frozenset({"en"})     # enemy name (compact)


def _anonymize_fields_inplace(obj: dict) -> None:
    """In-place mask nickname fields at a single dict level."""
    for k in obj.keys():
        if k in _PLAYER_NAME_FIELDS or k in _SHORT_PLAYER_NAME_FIELDS:
            obj[k] = "Player"
        elif k in _OPPONENT_NAME_FIELDS or k in _SHORT_OPPONENT_NAME_FIELDS:
            obj[k] = "Opponent"


def anonymize_replay_list_item(item: dict) -> dict:
    """Mask nicknames in a single compact replay list entry.

    Used by replay_archive_service.build_replay_list output.
    """
    if not isinstance(item, dict):
        return item
    out = dict(item)
    _anonymize_fields_inplace(out)
    return out


def anonymize_replay_game(game: dict | None) -> dict | None:
    """Mask nicknames in a full game payload (dict from ReplayArchive.games[idx]).

    Shallow mask at top level. Turn-level internals reference cards and ids,
    not plain nicknames, so no deep scan is required in the current schema.
    """
    if not isinstance(game, dict):
        return game
    out = dict(game)
    _anonymize_fields_inplace(out)
    return out


def anonymize_viewer_public_log(log: dict | None) -> dict | None:
    """Mask nicknames in a viewer_public_log JSONB payload.

    Targets match_meta.player_names ({"1": ..., "2": ...}) plus any top-level
    player_a_name / player_b_name fields that may appear.
    """
    if not isinstance(log, dict):
        return log
    out = dict(log)

    meta = out.get("match_meta")
    if isinstance(meta, dict):
        meta = dict(meta)
        names = meta.get("player_names")
        if isinstance(names, dict):
            # Neutral labeling: "Player 1" / "Player 2" (we do not know which
            # side is the viewing user's perspective on a public endpoint).
            masked = {}
            for k, _v in names.items():
                if k == "1":
                    masked[k] = "Player 1"
                elif k == "2":
                    masked[k] = "Player 2"
                else:
                    masked[k] = "Player"
            meta["player_names"] = masked
        out["match_meta"] = meta

    _anonymize_fields_inplace(out)
    return out
