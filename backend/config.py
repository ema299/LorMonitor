import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lorcana_app:lorcana_dev_2026@localhost:5432/lorcana")
DATABASE_URL_ASYNC = os.getenv("DATABASE_URL_ASYNC", "postgresql+asyncpg://lorcana_app:lorcana_dev_2026@localhost:5432/lorcana")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

MATCHES_DIR = Path(os.getenv("MATCHES_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/matches"))
ANALISIDEF_OUTPUT_DIR = Path(os.getenv("ANALISIDEF_OUTPUT_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output"))
ANALISIDEF_DAILY_DIR = Path(os.getenv("ANALISIDEF_DAILY_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/daily/output"))

ENV = os.getenv("ENV", "development")
