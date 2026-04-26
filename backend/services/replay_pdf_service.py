"""B.2 — Export PDF sessione Board Lab.

Renders a single replay + session notes into a downloadable PDF. Used by
``GET /api/v1/team/replay/{game_id}/export-pdf`` (owner-only).

Uses reportlab (pure-Python, no system deps). Output is in-memory bytes,
suitable for FastAPI ``Response`` with ``application/pdf``.

Layout (intentionally minimal — Coach can tweak post-launch):
- Header: deck codes, game date, winner, turn count
- Match metadata block (player_name, opponent_name, perspective, victory_reason)
- Session notes block (if present, raw text wrapped at width)
- Footer: generated_at + metamonitor.app branding

Caller is responsible for permission checks (use ``require_replay_owner``).
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


GOLD = colors.HexColor("#D4A03A")
DARK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#777777")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    out = {
        "title": ParagraphStyle(
            name="LMTitle", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=GOLD,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            name="LMSubtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, textColor=MUTED, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            name="LMSection", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=GOLD,
            spaceBefore=10, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            name="LMBody", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14, textColor=DARK,
            spaceAfter=4,
        ),
        "muted": ParagraphStyle(
            name="LMMuted", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=MUTED,
            spaceAfter=2,
        ),
    }
    return out


def _escape(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _meta_table(replay) -> Table:
    rows = [
        ["Player", _escape(replay.player_name) or "—"],
        ["Opponent", _escape(replay.opponent_name) or "—"],
        ["Perspective", "side A" if replay.perspective == 1 else ("side B" if replay.perspective == 2 else "—")],
        ["Winner", "side A" if replay.winner == 1 else ("side B" if replay.winner == 2 else "—")],
        ["Victory reason", _escape(replay.victory_reason) or "—"],
        ["Turn count", str(replay.turn_count) if replay.turn_count is not None else "—"],
        ["Game ID", _escape(replay.game_id) or "—"],
        ["Uploaded", replay.created_at.strftime("%Y-%m-%d %H:%M UTC") if replay.created_at else "—"],
    ]
    table = Table(rows, colWidths=[40 * mm, 110 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def render_replay_pdf(
    replay,
    *,
    notes_body: str | None = None,
    notes_updated_at: datetime | None = None,
    title_suffix: str = "",
) -> bytes:
    """Render a single replay (+ optional notes) into a PDF as bytes.

    Args:
        replay: TeamReplay ORM row (ownership/auth handled by caller).
        notes_body: optional session note body (plain text, wrapped).
        notes_updated_at: optional timestamp displayed under notes header.
        title_suffix: appended to the title line (e.g. " — coaching session").

    Returns:
        PDF document bytes.
    """
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Lorcana Monitor — replay {replay.game_id}",
        author="Lorcana Monitor",
    )
    story = []

    deck_a = _escape(replay.player_name) or "?"
    deck_b = _escape(replay.opponent_name) or "?"
    title = f"Replay session — {deck_a} vs {deck_b}"
    if title_suffix:
        title = f"{title}{_escape(title_suffix)}"
    story.append(Paragraph(title, styles["title"]))

    subtitle = f"metamonitor.app · Board Lab export · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    story.append(Paragraph(subtitle, styles["subtitle"]))

    story.append(Paragraph("Match metadata", styles["section"]))
    story.append(_meta_table(replay))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Session notes", styles["section"]))
    if notes_body and notes_body.strip():
        if notes_updated_at:
            ts = notes_updated_at.strftime("%Y-%m-%d %H:%M UTC")
            story.append(Paragraph(f"Last updated: {ts}", styles["muted"]))
        # Render notes preserving paragraph breaks. We don't trust HTML in
        # the body (notes are user-typed), so escape and convert newlines.
        escaped = _escape(notes_body)
        for chunk in escaped.split("\n\n"):
            chunk = chunk.replace("\n", "<br/>")
            story.append(Paragraph(chunk, styles["body"]))
    else:
        story.append(Paragraph("<i>No session notes for this replay.</i>", styles["muted"]))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Generated by Lorcana Monitor · metamonitor.app — for training use only.",
        styles["muted"],
    ))

    doc.build(story)
    return buf.getvalue()
