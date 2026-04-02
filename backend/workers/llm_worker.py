"""Worker: async killer curves generation via LLM."""
import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import text
from backend.config import ANALISIDEF_OUTPUT_DIR
from backend.models import SessionLocal

logger = logging.getLogger(__name__)


def import_killer_curves_from_files():
    """Import killer curves JSON files from analisidef output into PostgreSQL."""
    db = SessionLocal()
    imported = 0
    try:
        kc_files = list(ANALISIDEF_OUTPUT_DIR.glob("killer_curves_*_vs_*.json"))
        logger.info("Found %d killer curves files", len(kc_files))

        for kc_file in kc_files:
            try:
                with open(kc_file) as f:
                    data = json.load(f)

                our = data.get("our_deck", "")
                opp = data.get("opp_deck", "")
                fmt = data.get("game_format", "core")
                curves = data.get("curves", [])

                if not our or not opp or not curves:
                    continue

                # Mark old as not current
                db.execute(text("""
                    UPDATE killer_curves SET is_current = false
                    WHERE our_deck = :our AND opp_deck = :opp AND game_format = :fmt AND is_current = true
                """), {"our": our, "opp": opp, "fmt": fmt})

                # Insert new
                db.execute(text("""
                    INSERT INTO killer_curves (generated_at, game_format, our_deck, opp_deck, curves,
                        match_count, loss_count, is_current)
                    VALUES (:gen, :fmt, :our, :opp, :curves::jsonb, :mc, :lc, true)
                    ON CONFLICT (game_format, our_deck, opp_deck, generated_at) DO UPDATE
                    SET curves = EXCLUDED.curves, is_current = true
                """), {
                    "gen": date.today(),
                    "fmt": fmt,
                    "our": our,
                    "opp": opp,
                    "curves": json.dumps(curves),
                    "mc": data.get("match_count", 0),
                    "lc": data.get("loss_count", 0),
                })

                imported += 1
            except Exception as e:
                logger.warning("Error importing %s: %s", kc_file.name, e)

        db.commit()
        logger.info("Imported %d killer curves", imported)
        return imported
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = import_killer_curves_from_files()
    print(f"Imported {n} killer curves")
