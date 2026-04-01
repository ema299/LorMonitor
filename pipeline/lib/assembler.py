"""Assembler: concatena sezioni in un unico report .md e salva in reports/."""

import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')


def assemble_report(our, opp, our_long, opp_long, sections, warnings, n_games,
                     game_format='core'):
    """Assembla il report finale e salva in reports/<OurLong>/vs_<OppLong>.md.

    Le sezioni arrivano gia' nell'ordine corretto dalla pipeline.
    Le killer curves (draft o LLM) sono gia' incluse come sezione.
    game_format: 'core' o 'infinity'. I report infinity vanno in reports_infinity/.

    Returns:
        path del file salvato
    """
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    fmt_label = 'Core-Constructed' if game_format == 'core' else 'Infinity'

    parts = []
    parts.append(f"# Report Matchup: {our_long} vs {opp_long}")
    parts.append(f"> Generato: {now} — **{n_games} match** analizzati — Formato: **{fmt_label}**\n")
    parts.append("---\n")

    for sec in sections:
        if sec and sec.strip():
            parts.append(sec.strip())
            parts.append("\n---\n")

    # Warnings
    if warnings:
        parts.append("## Warnings di Validazione\n")
        for w in warnings:
            parts.append(f"- {w}")
        parts.append("")

    md = '\n'.join(parts)

    # Save — infinity in cartella separata
    if game_format == 'infinity':
        reports_root = os.path.join(BASE_DIR, 'reports_infinity')
    else:
        reports_root = REPORTS_DIR
    deck_dir = os.path.join(reports_root, our_long)
    os.makedirs(deck_dir, exist_ok=True)
    out_path = os.path.join(deck_dir, f"vs_{opp_long}.md")
    with open(out_path, 'w') as f:
        f.write(md)

    return out_path
