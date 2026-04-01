"""
History DB — Storico giornaliero meta Lorcana in SQLite.

Documentazione completa: Daily_routine/HISTORY_DB.md

Schema:
  daily_meta      → WR, games, meta_share per deck/perimetro/giorno
  daily_matchups  → WR per matchup con split OTP/OTD
  daily_pro       → Performance PRO player per deck/giorno
  daily_pro_matchups → PRO player WR vs ogni deck avversario/giorno
  daily_tech      → Tech choices (carte in/out/flex) per deck/giorno
  daily_snapshot  → JSON grezzo completo (backup)

Uso:
  from history_db import save_daily, query_trend, query_matchup_trend, query_pro_history
  save_daily(dashboard_data_dict, "2026-03-22")
  trend = query_trend("AS", days=30)
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "output" / "history.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_meta (
    date       TEXT NOT NULL,
    perimeter  TEXT NOT NULL,
    deck       TEXT NOT NULL,
    wins       INTEGER NOT NULL,
    losses     INTEGER NOT NULL,
    games      INTEGER NOT NULL,
    wr         REAL NOT NULL,
    meta_share REAL,
    PRIMARY KEY (date, perimeter, deck)
);

CREATE TABLE IF NOT EXISTS daily_matchups (
    date       TEXT NOT NULL,
    perimeter  TEXT NOT NULL,
    deck       TEXT NOT NULL,
    vs_deck    TEXT NOT NULL,
    wins       INTEGER,
    total      INTEGER,
    wr         REAL,
    otp_wins   INTEGER,
    otp_total  INTEGER,
    otd_wins   INTEGER,
    otd_total  INTEGER,
    PRIMARY KEY (date, perimeter, deck, vs_deck)
);

CREATE TABLE IF NOT EXISTS daily_pro (
    date       TEXT NOT NULL,
    player     TEXT NOT NULL,
    deck       TEXT NOT NULL,
    wins       INTEGER NOT NULL,
    losses     INTEGER NOT NULL,
    wr         REAL NOT NULL,
    PRIMARY KEY (date, player, deck)
);

CREATE TABLE IF NOT EXISTS daily_pro_matchups (
    date       TEXT NOT NULL,
    player     TEXT NOT NULL,
    vs_deck    TEXT NOT NULL,
    wins       INTEGER NOT NULL,
    losses     INTEGER NOT NULL,
    wr         REAL NOT NULL,
    PRIMARY KEY (date, player, vs_deck)
);

CREATE TABLE IF NOT EXISTS daily_tech (
    date       TEXT NOT NULL,
    perimeter  TEXT NOT NULL,
    deck       TEXT NOT NULL,
    card       TEXT NOT NULL,
    tech_type  TEXT NOT NULL,
    adoption   REAL,
    avg_wr     REAL,
    players    INTEGER,
    PRIMARY KEY (date, perimeter, deck, card)
);

CREATE TABLE IF NOT EXISTS daily_snapshot (
    date       TEXT PRIMARY KEY,
    json_data  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS killer_curves_history (
    date       TEXT NOT NULL,
    our_deck   TEXT NOT NULL,
    opp_deck   TEXT NOT NULL,
    games      INTEGER NOT NULL DEFAULT 0,
    losses     INTEGER NOT NULL DEFAULT 0,
    num_curves INTEGER NOT NULL DEFAULT 0,
    curves_json TEXT NOT NULL,
    PRIMARY KEY (date, our_deck, opp_deck)
);
"""


def _get_conn():
    """Open (or create) the SQLite database and ensure schema exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Write — chiamato da daily_routine.py
# ---------------------------------------------------------------------------

def save_daily(data: dict, date_str: str):
    """
    Salva i dati giornalieri nel DB. Idempotente (INSERT OR REPLACE).

    Args:
        data: il dizionario dashboard_data (stessa struttura di dashboard_data.json)
        date_str: data ISO "YYYY-MM-DD"
    """
    conn = _get_conn()
    try:
        _save_meta(conn, data, date_str)
        _save_matchups(conn, data, date_str)
        _save_pro(conn, data, date_str)
        _save_tech(conn, data, date_str)
        _save_snapshot(conn, data, date_str)
        conn.commit()
        count = conn.execute("SELECT COUNT(DISTINCT date) FROM daily_meta").fetchone()[0]
        print(f"History DB: salvato {date_str} → {DB_PATH} ({count} giorni totali)")
    finally:
        conn.close()


def _save_meta(conn, data, date_str):
    """Salva daily_meta da perimeters.<peri>.wr + .meta_share."""
    perimeters = data.get("perimeters", {})
    rows = []
    for peri, pdata in perimeters.items():
        if not isinstance(pdata, dict):
            continue
        wr_data = pdata.get("wr", {})
        share_data = pdata.get("meta_share", {})
        for deck, stats in wr_data.items():
            if not isinstance(stats, dict):
                continue
            share = None
            if deck in share_data and isinstance(share_data[deck], dict):
                share = share_data[deck].get("share")
            rows.append((
                date_str, peri, deck,
                stats.get("w", 0), stats.get("l", 0),
                stats.get("games", 0), stats.get("wr", 0),
                share
            ))
    conn.executemany(
        "INSERT OR REPLACE INTO daily_meta VALUES (?,?,?,?,?,?,?,?)", rows
    )


def _save_matchups(conn, data, date_str):
    """Salva daily_matchups da perimeters.<peri>.matrix + .otp_otd."""
    perimeters = data.get("perimeters", {})
    rows = []
    for peri, pdata in perimeters.items():
        if not isinstance(pdata, dict):
            continue
        wr_data = pdata.get("wr", {})
        otp_otd = pdata.get("otp_otd", {})
        matrix = pdata.get("matrix", {})
        deck_names = list(wr_data.keys())

        # matrix può essere lista di liste (NxN) o dict
        if isinstance(matrix, list) and len(matrix) == len(deck_names):
            for i, deck in enumerate(deck_names):
                for j, vs_deck in enumerate(deck_names):
                    if i == j:
                        continue
                    cell = matrix[i][j]
                    if isinstance(cell, dict):
                        w = cell.get("w", 0)
                        t = cell.get("t", 0)
                        wr = (w / t * 100) if t > 0 else None
                    elif isinstance(cell, (int, float)):
                        w, t, wr = None, None, cell
                    else:
                        continue
                    # OTP/OTD per questo matchup
                    otp_w, otp_t, otd_w, otd_t = None, None, None, None
                    if deck in otp_otd and isinstance(otp_otd[deck], dict):
                        mu = otp_otd[deck].get(vs_deck, {})
                        if isinstance(mu, dict):
                            otp_w = mu.get("otp_w")
                            otp_t = mu.get("otp_t")
                            otd_w = mu.get("otd_w")
                            otd_t = mu.get("otd_t")
                    rows.append((
                        date_str, peri, deck, vs_deck,
                        w, t, wr, otp_w, otp_t, otd_w, otd_t
                    ))
        elif isinstance(matrix, dict):
            # dict-based matrix: matrix[deck][vs_deck]
            for deck, matchups in matrix.items():
                if not isinstance(matchups, dict):
                    continue
                for vs_deck, cell in matchups.items():
                    if isinstance(cell, dict):
                        w = cell.get("w", 0)
                        t = cell.get("t", 0)
                        wr = (w / t * 100) if t > 0 else None
                    else:
                        continue
                    otp_w, otp_t, otd_w, otd_t = None, None, None, None
                    if deck in otp_otd and isinstance(otp_otd[deck], dict):
                        mu = otp_otd[deck].get(vs_deck, {})
                        if isinstance(mu, dict):
                            otp_w = mu.get("otp_w")
                            otp_t = mu.get("otp_t")
                            otd_w = mu.get("otd_w")
                            otd_t = mu.get("otd_t")
                    rows.append((
                        date_str, peri, deck, vs_deck,
                        w, t, wr, otp_w, otp_t, otd_w, otd_t
                    ))

    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO daily_matchups VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )


def _save_pro(conn, data, date_str):
    """Salva daily_pro + daily_pro_matchups da pro_players[]."""
    rows = []
    mu_rows = []
    for player in data.get("pro_players", []):
        name = player.get("name", "")
        decks = player.get("decks", {})
        if not decks:
            # player senza breakdown per deck: salva aggregato
            w = player.get("w", 0)
            l = player.get("l", 0)
            wr = player.get("wr", 0)
            rows.append((date_str, name, "ALL", w, l, wr))
        else:
            for deck, dstats in decks.items():
                w = dstats.get("w", 0)
                l = dstats.get("l", 0)
                total = w + l
                wr = (w / total * 100) if total > 0 else 0
                rows.append((date_str, name, deck, w, l, wr))
        # matchups vs deck
        matchups = player.get("matchups", {})
        for vs_deck, mstats in matchups.items():
            mw = mstats.get("w", 0)
            ml = mstats.get("l", 0)
            mt = mw + ml
            mwr = (mw / mt * 100) if mt > 0 else 0
            mu_rows.append((date_str, name, vs_deck, mw, ml, round(mwr, 1)))
    conn.executemany(
        "INSERT OR REPLACE INTO daily_pro VALUES (?,?,?,?,?,?)", rows
    )
    if mu_rows:
        conn.executemany(
            "INSERT OR REPLACE INTO daily_pro_matchups VALUES (?,?,?,?,?,?)",
            mu_rows
        )


def _save_tech(conn, data, date_str):
    """Salva daily_tech da tech_tornado.<peri>.<deck>.items[]."""
    tech = data.get("tech_tornado", {})
    rows = []
    for peri, peri_data in tech.items():
        if not isinstance(peri_data, dict):
            continue
        for deck, deck_data in peri_data.items():
            if not isinstance(deck_data, dict):
                continue
            items = deck_data.get("items", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                rows.append((
                    date_str, peri, deck,
                    item.get("card", ""),
                    item.get("type", "in"),
                    item.get("adoption"),
                    item.get("avg_wr"),
                    item.get("players"),
                ))
    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO daily_tech VALUES (?,?,?,?,?,?,?,?)", rows
        )


def _save_snapshot(conn, data, date_str):
    """Salva il JSON completo come backup."""
    conn.execute(
        "INSERT OR REPLACE INTO daily_snapshot VALUES (?,?)",
        (date_str, json.dumps(data, default=str, ensure_ascii=False))
    )


# ---------------------------------------------------------------------------
# Read — query helpers
# ---------------------------------------------------------------------------

def query_trend(deck: str, days: int = 30, perimeter: str = "set11") -> list[dict]:
    """
    Trend WR/games/meta_share di un deck negli ultimi N giorni.

    Returns:
        [{"date": "2026-03-22", "wr": 52.1, "games": 1124, "meta_share": 13.9}, ...]
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT date, wr, games, meta_share
               FROM daily_meta
               WHERE deck = ? AND perimeter = ?
               ORDER BY date DESC LIMIT ?""",
            (deck, perimeter, days)
        ).fetchall()
        return [
            {"date": r[0], "wr": r[1], "games": r[2], "meta_share": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


def query_matchup_trend(deck: str, vs_deck: str, days: int = 14,
                        perimeter: str = "set11") -> list[dict]:
    """
    Trend WR di un matchup specifico con split OTP/OTD.

    Returns:
        [{"date": ..., "wr": ..., "total": ..., "otp_wr": ..., "otd_wr": ...}, ...]
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT date, wr, total, otp_wins, otp_total, otd_wins, otd_total
               FROM daily_matchups
               WHERE deck = ? AND vs_deck = ? AND perimeter = ?
               ORDER BY date DESC LIMIT ?""",
            (deck, vs_deck, perimeter, days)
        ).fetchall()
        results = []
        for r in rows:
            otp_wr = (r[3] / r[4] * 100) if r[4] and r[4] > 0 else None
            otd_wr = (r[5] / r[6] * 100) if r[6] and r[6] > 0 else None
            results.append({
                "date": r[0], "wr": r[1], "total": r[2],
                "otp_wr": otp_wr, "otd_wr": otd_wr
            })
        return results
    finally:
        conn.close()


def query_pro_history(player: str, days: int = 30) -> list[dict]:
    """
    Storico di un PRO player.

    Returns:
        [{"date": ..., "deck": "AmAm", "w": 4, "l": 8, "wr": 33.3}, ...]
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT date, deck, wins, losses, wr
               FROM daily_pro
               WHERE player = ?
               ORDER BY date DESC LIMIT ?""",
            (player, days)
        ).fetchall()
        return [
            {"date": r[0], "deck": r[1], "w": r[2], "l": r[3], "wr": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def query_pro_matchups(player: str, days: int = 30) -> list[dict]:
    """
    Storico matchup di un PRO player vs ogni deck avversario.

    Returns:
        [{"date": ..., "vs_deck": "ES", "w": 2, "l": 1, "wr": 66.7}, ...]
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT date, vs_deck, wins, losses, wr
               FROM daily_pro_matchups
               WHERE player = ?
               ORDER BY date DESC LIMIT ?""",
            (player, days * 15)  # ~15 matchups per day max
        ).fetchall()
        return [
            {"date": r[0], "vs_deck": r[1], "w": r[2], "l": r[3], "wr": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def query_meta_evolution(days: int = 30, perimeter: str = "set11") -> list[dict]:
    """
    Evoluzione meta share di tutti i deck negli ultimi N giorni.

    Returns:
        [{"date": ..., "deck": ..., "meta_share": ..., "wr": ...}, ...]
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT date, deck, meta_share, wr
               FROM daily_meta
               WHERE perimeter = ? AND meta_share IS NOT NULL
               ORDER BY date DESC, meta_share DESC
               LIMIT ?""",
            (perimeter, days * 20)  # ~20 decks per day max
        ).fetchall()
        return [
            {"date": r[0], "deck": r[1], "meta_share": r[2], "wr": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


def get_available_dates() -> list[str]:
    """Lista di tutte le date presenti nel DB, ordinate."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT date FROM daily_meta ORDER BY date"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_snapshot(date_str: str) -> dict | None:
    """Recupera lo snapshot JSON completo di un giorno specifico."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT json_data FROM daily_snapshot WHERE date = ?", (date_str,)
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Killer Curves History
# ---------------------------------------------------------------------------

def save_killer_curves_from_file(filepath: str):
    """
    Salva killer curves da un file JSON nello storico.
    Idempotente (INSERT OR REPLACE per date+deck+opp).

    Il file deve avere: metadata.{our_deck, opp_deck, date, based_on_games, based_on_losses}
    e curves[].

    Schema identico a quello futuro PostgreSQL:
      killer_curves_history(date, our_deck, opp_deck, games, losses, num_curves, curves_json)
    """
    with open(filepath) as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    our = meta.get("our_deck", "")
    opp = meta.get("opp_deck", "")
    date = meta.get("date", "")
    games = meta.get("based_on_games", 0)
    losses = meta.get("based_on_losses", 0)
    curves = data.get("curves", [])

    if not our or not opp or not date:
        raise ValueError(f"Metadata incompleta: our={our}, opp={opp}, date={date}")

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO killer_curves_history
               (date, our_deck, opp_deck, games, losses, num_curves, curves_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, our, opp, games, losses, len(curves), json.dumps(data, ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()


def save_killer_curves(our_deck: str, opp_deck: str, date_str: str,
                       games: int, losses: int, curves_data: dict):
    """Salva killer curves direttamente (senza leggere file)."""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO killer_curves_history
               (date, our_deck, opp_deck, games, losses, num_curves, curves_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date_str, our_deck, opp_deck, games, losses,
             len(curves_data.get("curves", [])),
             json.dumps(curves_data, ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()


def query_killer_curves_history(our_deck: str = None, opp_deck: str = None,
                                 days: int = 30) -> list:
    """
    Query storico killer curves.
    Filtra per deck e/o opponent. Ritorna lista di dict.
    """
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    try:
        where = ["date >= date('now', ?)" ]
        params = [f"-{days} days"]
        if our_deck:
            where.append("our_deck = ?")
            params.append(our_deck)
        if opp_deck:
            where.append("opp_deck = ?")
            params.append(opp_deck)

        sql = f"""SELECT date, our_deck, opp_deck, games, losses, num_curves
                  FROM killer_curves_history
                  WHERE {' AND '.join(where)}
                  ORDER BY date DESC, our_deck, opp_deck"""
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_killer_curves(our_deck: str, opp_deck: str, date_str: str = None) -> dict:
    """
    Recupera killer curves per un matchup. Se date_str è None, prende il più recente.
    Ritorna il dict completo (metadata + curves) o None.
    """
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    try:
        if date_str:
            row = conn.execute(
                "SELECT curves_json FROM killer_curves_history WHERE our_deck=? AND opp_deck=? AND date=?",
                (our_deck, opp_deck, date_str)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT curves_json FROM killer_curves_history WHERE our_deck=? AND opp_deck=? ORDER BY date DESC LIMIT 1",
                (our_deck, opp_deck)
            ).fetchone()
        if row:
            return json.loads(row["curves_json"])
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI — per test e backfill
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso:")
        print("  python3 history_db.py backfill         # importa dashboard_data.json corrente")
        print("  python3 history_db.py trend AS 30       # trend AS ultimi 30gg")
        print("  python3 history_db.py matchup AS ES 14  # matchup AS vs ES ultimi 14gg")
        print("  python3 history_db.py pro Ben 30        # storico Ben ultimi 30gg")
        print("  python3 history_db.py pro-mu Ben 30     # matchup Ben vs deck ultimi 30gg")
        print("  python3 history_db.py dates              # date disponibili")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "backfill":
        # Importa il dashboard_data.json corrente
        json_path = Path(__file__).parent / "output" / "dashboard_data.json"
        if not json_path.exists():
            print(f"File non trovato: {json_path}")
            sys.exit(1)
        with open(json_path) as f:
            data = json.load(f)
        # Estrai data dal campo meta.updated ("22/03/2026 07:01" → "2026-03-22")
        updated = data.get("meta", {}).get("updated", "")
        parts = updated.split(" ")[0].split("/")
        if len(parts) == 3:
            date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            from datetime import date
            date_str = date.today().isoformat()
        save_daily(data, date_str)

    elif cmd == "trend":
        deck = sys.argv[2] if len(sys.argv) > 2 else "AS"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        for row in query_trend(deck, days):
            print(f"  {row['date']}  WR={row['wr']:.1f}%  games={row['games']}  share={row['meta_share']}")

    elif cmd == "matchup":
        deck = sys.argv[2] if len(sys.argv) > 2 else "AS"
        vs = sys.argv[3] if len(sys.argv) > 3 else "ES"
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 14
        for row in query_matchup_trend(deck, vs, days):
            otp = f"{row['otp_wr']:.0f}%" if row['otp_wr'] else "N/A"
            otd = f"{row['otd_wr']:.0f}%" if row['otd_wr'] else "N/A"
            print(f"  {row['date']}  WR={row['wr']:.1f}%  games={row['total']}  OTP={otp}  OTD={otd}")

    elif cmd == "pro":
        player = sys.argv[2] if len(sys.argv) > 2 else "Ben"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        for row in query_pro_history(player, days):
            print(f"  {row['date']}  {row['deck']}  {row['w']}W-{row['l']}L  WR={row['wr']:.1f}%")

    elif cmd == "pro-mu":
        player = sys.argv[2] if len(sys.argv) > 2 else "Ben"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        for row in query_pro_matchups(player, days):
            total = row['w'] + row['l']
            print(f"  {row['date']}  vs {row['vs_deck']:<6}  {row['w']}W-{row['l']}L  WR={row['wr']:.1f}%  ({total}g)")

    elif cmd == "dates":
        dates = get_available_dates()
        print(f"Date disponibili ({len(dates)}):")
        for d in dates:
            print(f"  {d}")

    elif cmd == "save-curves":
        # Save all killer curves from output/ to history
        from pathlib import Path
        import glob
        output_dir = Path(__file__).parent.parent / "output"
        files = sorted(output_dir.glob("killer_curves_*.json"))
        saved = 0
        for f in files:
            try:
                save_killer_curves_from_file(str(f))
                saved += 1
            except Exception as e:
                print(f"  ERRORE {f.name}: {e}")
        print(f"Salvate {saved}/{len(files)} killer curves nello storico")

    elif cmd == "curves":
        deck = sys.argv[2] if len(sys.argv) > 2 else None
        opp = sys.argv[3] if len(sys.argv) > 3 else None
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        for row in query_killer_curves_history(deck, opp, days):
            print(f"  {row['date']}  {row['our_deck']} vs {row['opp_deck']}  {row['num_curves']} curves  ({row['games']}g, {row['losses']}L)")

    else:
        print(f"Comando sconosciuto: {cmd}")
