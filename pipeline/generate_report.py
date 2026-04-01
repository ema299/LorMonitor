#!/usr/bin/env python3
"""
Orchestratore pipeline report matchup unificato.

Uso:
  python3 generate_report.py AmAm ES                    # report core-constructed (default)
  python3 generate_report.py AmAm ES --format infinity  # report infinity
  python3 generate_report.py AmAm ES --killer           # solo killer curves (legacy)
  python3 generate_report.py AmAm ES --curve            # solo curve T1-T7 (legacy)
  python3 generate_report.py AmAm ES --validate         # solo validazione (legacy)
  python3 generate_report.py AmAm ES --all-turns        # solo dump turni (legacy)

Senza flag: produce UN singolo reports/<Deck>/vs_<Opp>.md con tutte le sezioni.
Con flag: produce report separati come prima.
--format core|infinity: seleziona il macro-perimetro (default: core).

Accetta sia sigle (AmAm, ES) che nomi lunghi (Amber-Amethyst, Emerald-Sapphire).
"""

import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.loader import (resolve_deck, deck_long, load_cards_db, load_cards_db_extended,
                         load_matches, load_deck_pool, build_extended_pool,
                         DECK_COLORS, DECK_LONG_NAMES, VALID_FORMATS)
from lib import (gen_killer_curves, gen_curve_t1t7, gen_validate, gen_all_turns,
                 gen_panoramica, gen_mani, gen_risposte,
                 gen_decklist, gen_review, gen_deck_actually,
                 investigate, validate, assembler)
from lib import gen_killer_curves_draft
from lib.gen_archive import generate_archive
from lib.gen_digest import generate_digest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

# Legacy generators (producono file separati)
LEGACY_GENERATORS = {
    'killer':    ('killer_curves',  gen_killer_curves, 7),
    'curve':     ('curve_t1t7',     gen_curve_t1t7,    7),
    'validate':  ('validate',       gen_validate,      None),
    'all-turns': ('all_turns',      gen_all_turns,     None),
}


def run_unified_pipeline(our, opp, our_long, opp_long, game_format='core'):
    """Pipeline completa: LOAD → INVESTIGATE → GENERATE → VALIDATE → ASSEMBLE."""

    fmt_label = game_format.upper()
    # ── FASE 1: LOAD ──
    print(f"[FASE 1] Caricamento dati ({fmt_label})...")
    db, ability_cost_map, id_map = load_cards_db_extended()
    games = load_matches(our, opp, max_turn=None, game_format=game_format)
    wins = sum(1 for g in games if g['we_won'])
    losses = len(games) - wins
    print(f"  {len(games)} match ({wins}W / {losses}L)")

    if not games:
        print("Nessun match trovato.")
        sys.exit(0)

    print(f"  Deck pool {our}...")
    our_pool, our_decks = load_deck_pool(our, db)
    opp_pool, _ = load_deck_pool(opp, db)
    ext_pool = build_extended_pool(our, db)
    print(f"    {len(our_pool)} carte nel pool, {len(our_decks)} decklist")

    # ── FASE 2: INVESTIGATE ──
    print(f"[FASE 2] Investigazione profonda...")
    investigate.enrich_games(games, db, ability_cost_map)
    synergies = investigate.analyze_synergies(games, db, ability_cost_map)
    loss_classes = investigate.classify_losses(games, db=db)
    print(f"  Board state, ink budget, sinergie calcolati")
    print(f"  {len(loss_classes)} sconfitte classificate")

    # ── FASE 2b: ARCHIVIO JSON ──
    print(f"[FASE 2b] Generazione archivio JSON...")
    archive_path = generate_archive(our, opp, our_long, opp_long, games, loss_classes,
                                     game_format=game_format)
    print(f"  → {archive_path}")

    # ── FASE 2c: DIGEST LLM ──
    print(f"[FASE 2c] Generazione digest LLM...")
    digest_path = generate_digest(archive_path)
    digest_kb = os.path.getsize(digest_path) / 1024
    print(f"  → {digest_path} ({digest_kb:.0f} KB)")

    # ── FASE 3: GENERATE ──
    print(f"[FASE 3] Generazione sezioni...")
    ctx = {
        'ability_cost_map': ability_cost_map,
        'synergies': synergies,
        'loss_classes': loss_classes,
        'our_pool': our_pool,
        'opp_pool': opp_pool,
        'ext_pool': ext_pool,
        'our_decks': our_decks,
        'game_format': game_format,
    }

    pipeline = [
        ('Sez.1 Panoramica',          gen_panoramica),
        ('Sez.2 Minacce Principali',  gen_killer_curves_draft),  # draft o LLM se esiste
        ('Sez.3 Playbook + Board',    gen_killer_curves),        # playbook aggregato per turno
        ('Sez.4 Mani Vincenti',       gen_mani),
        ('Sez.5 Toolkit',             gen_risposte),
        ('Sez.6 Decklist',            gen_decklist),
        ('Sez.7 Review',              gen_review),
        ('Sez.8 Deck Actually',       gen_deck_actually),
    ]

    sections = []
    for label, module in pipeline:
        print(f"  {label}...")
        md, data = module.generate(our, opp, games, db, **ctx)
        sections.append(md)
        ctx.update(data)  # passa dati alle sezioni successive

    # ── FASE 4: VALIDATE ──
    print(f"[FASE 4] Validazione meccanica...")
    warnings = validate.validate_report(ctx, games, db, ability_cost_map)
    if warnings:
        print(f"  {len(warnings)} warning trovati")
    else:
        print(f"  Nessun warning")

    # ── FASE 5: ASSEMBLE ──
    print(f"[FASE 5] Assemblaggio report...")
    out_path = assembler.assemble_report(our, opp, our_long, opp_long,
                                          sections, warnings, len(games),
                                          game_format=game_format)
    print(f"  → {out_path}")

    # ── OPZIONALE: dump turni separato ──
    if '--all-turns' in sys.argv:
        print(f"  Dump turni...")
        dump = gen_all_turns.generate(our, opp, games, db)
        dump_path = os.path.join(REPORTS_DIR, our_long, f"vs_{opp_long}_all_turns.md")
        with open(dump_path, 'w') as f:
            f.write(dump)
        print(f"  → {dump_path}")

    print("Done.")


def run_legacy(our, opp, our_long, opp_long, flags):
    """Modalità legacy: genera report separati come prima."""
    max_turn = 7
    for f in flags:
        if f in LEGACY_GENERATORS:
            mt = LEGACY_GENERATORS[f][2]
            if mt is None:
                max_turn = None
                break

    print(f"Caricamento match {our_long} vs {opp_long}...")
    db = load_cards_db()
    games = load_matches(our, opp, max_turn=max_turn)
    wins = sum(1 for g in games if g['we_won'])
    losses = len(games) - wins
    print(f"  {len(games)} match ({wins}W / {losses}L)")

    if not games:
        print("Nessun match trovato.")
        sys.exit(0)

    # Per killer curves con clustering, enrich games
    try:
        db_ext, ability_cost_map, _ = load_cards_db_extended()
        investigate.enrich_games(games, db_ext, ability_cost_map)
    except Exception:
        pass  # fallback: clustering non disponibile

    deck_dir = os.path.join(REPORTS_DIR, our_long)
    os.makedirs(deck_dir, exist_ok=True)

    for flag in flags:
        if flag not in LEGACY_GENERATORS:
            print(f"Flag sconosciuto: --{flag}")
            print(f"Disponibili: {', '.join(LEGACY_GENERATORS.keys())}")
            sys.exit(1)

        prefix, module, _ = LEGACY_GENERATORS[flag]
        print(f"Generazione {flag}...")
        result = module.generate(our, opp, games, db)
        # Handle both old (str) and new (tuple) return format
        if isinstance(result, tuple):
            md = result[0]
        else:
            md = result

        filename = f"vs_{opp_long}_{prefix}.md"
        out_path = os.path.join(deck_dir, filename)
        with open(out_path, 'w') as f:
            f.write(md)
        print(f"  → {out_path}")

    print("Done.")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print(f"\nDeck disponibili:")
        for k, v in DECK_LONG_NAMES.items():
            print(f"  {k:6s} → {v}")
        sys.exit(1)

    our = resolve_deck(sys.argv[1])
    opp = resolve_deck(sys.argv[2])
    if not our or not opp:
        print(f"Deck non riconosciuto.")
        print(f"Disponibili: {', '.join(f'{k} ({v})' for k, v in DECK_LONG_NAMES.items())}")
        sys.exit(1)

    our_long = deck_long(our)
    opp_long = deck_long(opp)

    # Parse --format
    game_format = 'core'
    args = sys.argv[3:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == '--format' and i + 1 < len(args):
            game_format = args[i + 1].lower()
            if game_format not in VALID_FORMATS:
                print(f"Formato sconosciuto: {game_format}. Validi: {', '.join(VALID_FORMATS)}")
                sys.exit(1)
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    # Parse flags (esclude --all-turns per la pipeline unificata)
    flags = [a.lstrip('-') for a in filtered_args if a.lstrip('-') != 'all-turns' or a.lstrip('-') in LEGACY_GENERATORS]
    legacy_flags = [f for f in flags if f in LEGACY_GENERATORS]

    if legacy_flags:
        # Modalità legacy: genera report separati
        run_legacy(our, opp, our_long, opp_long, legacy_flags)
    else:
        # Modalità unificata: pipeline completa
        run_unified_pipeline(our, opp, our_long, opp_long, game_format=game_format)


if __name__ == '__main__':
    main()
