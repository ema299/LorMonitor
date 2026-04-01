"""
Backfill history.db per giorni passati.
Esegue la pipeline di daily_routine.py per ogni giorno specificato,
salvando solo nel DB (non sovrascrive il report/dashboard corrente).

Uso:
  python3 backfill_history.py              # ultimi 3 giorni (20,21,22/03)
  python3 backfill_history.py 5            # ultimi 5 giorni
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Assicura che Daily_routine/ sia nel path
sys.path.insert(0, str(Path(__file__).parent))

import daily_routine as dr
from history_db import save_daily


def run_for_date(target_date: datetime):
    """Esegue la pipeline per una data specifica (target + giorno prima)."""
    # Simula get_last_n_days(2) per la data target
    days = []
    for i in range(2):
        d = target_date - timedelta(days=i)
        days.append(d.strftime("%d%m%y"))

    day_labels = [f"{d[:2]}/{d[2:4]}" for d in days]
    iso_date = target_date.strftime("%Y-%m-%d")
    now_str = target_date.strftime("%d/%m/%Y 07:00")

    print(f"\n{'='*60}")
    print(f"BACKFILL: {iso_date} (folders: {', '.join(day_labels)})")
    print(f"{'='*60}")

    # Verifica che le cartelle match esistano
    matches_dir = Path("/mnt/HC_Volume_104764377/finanza/Lor") / "matches"
    existing = [d for d in days if (matches_dir / d).exists()]
    if not existing:
        print(f"  SKIP: nessuna cartella match trovata per {days}")
        return

    print(f"  Cartelle trovate: {existing}")

    # Load data
    print(f"  Caricamento SET11 (MMR >= {dr.MIN_MMR_HIGH})...")
    set11 = dr.load_matches(days, "SET11", min_mmr=dr.MIN_MMR_HIGH)
    print(f"    → {len(set11)} match")

    # Community stats: usa None per backfill (non possiamo recuperare dati passati)
    duelsink_data = None

    print("  Caricamento PRO + TOP...")
    pro = dr.load_matches(days, "PRO")
    top = dr.load_matches(days, "TOP")
    seen = set()
    protop = []
    for m in pro + top:
        if m["game_id"] not in seen:
            seen.add(m["game_id"])
            protop.append(m)
    print(f"    → {len(protop)} match")

    # Combined (dedup)
    all_seen = set()
    all_matches = []
    for m in set11 + protop:
        if m["game_id"] not in all_seen:
            all_seen.add(m["game_id"])
            all_matches.append(m)

    if not all_matches:
        print(f"  SKIP: 0 match totali")
        return

    # Stats
    stats_set11 = dr.deck_stats(set11)
    stats_protop = dr.deck_stats(protop)
    w_set11, t_set11 = dr.build_matrix(set11)
    w_protop, t_protop = dr.build_matrix(protop)

    # Build dashboard data (stessa logica di export_dashboard_json)
    # ma NON sovrascrive i file — salva solo nel DB
    consensus = dr.load_snapshot_consensus()
    player_cards = dr._build_player_cards_data(days)

    data = {
        "meta": {
            "updated": now_str,
            "period": " + ".join(day_labels),
            "games": {
                "set11": len(set11),
                "protop": len(protop),
                "total": len(all_matches),
            }
        },
    }

    # Usa export_dashboard_json internamente per costruire il dict completo
    # Salvo temporaneamente e poi importo
    import json
    import tempfile

    # Trick: chiamo export_dashboard_json che scrive su file, poi leggo il JSON
    # e lo salvo nel DB. I file vengono sovrascritti ma poi ripristinati.
    original_json = dr.DASHBOARD_JSON
    original_html = dr.DAILY_DIR / "output" / "dashboard.html"

    # Backup files correnti
    json_backup = None
    html_backup = None
    if original_json.exists():
        json_backup = original_json.read_text()
    if original_html.exists():
        html_backup = original_html.read_text()

    try:
        # Esegui export (sovrascrive temporaneamente)
        dr.export_dashboard_json(
            now_str, day_labels, days,
            set11, protop, all_matches,
            stats_set11, stats_protop,
            w_set11, t_set11, w_protop, t_protop,
            duelsink_data
        )

        # Leggi il JSON generato e salvalo nel DB
        with open(original_json) as f:
            full_data = json.load(f)

        save_daily(full_data, iso_date)

    finally:
        # Ripristina i file originali
        if json_backup is not None:
            original_json.write_text(json_backup)
        if html_backup is not None:
            original_html.write_text(html_backup)

    print(f"  ✓ {iso_date} salvato nel DB")


def main():
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    today = datetime.now()

    for i in range(n_days - 1, -1, -1):  # dal più vecchio al più recente
        target = today - timedelta(days=i)
        run_for_date(target)

    print(f"\nBackfill completato.")

    # Mostra date disponibili
    from history_db import get_available_dates
    dates = get_available_dates()
    print(f"Date nel DB: {', '.join(dates)}")


if __name__ == "__main__":
    main()
