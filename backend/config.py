import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set — check .env file")
DATABASE_URL_ASYNC = os.getenv("DATABASE_URL_ASYNC")
if not DATABASE_URL_ASYNC:
    raise RuntimeError("DATABASE_URL_ASYNC not set — check .env file")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

MATCHES_DIR = Path(os.getenv("MATCHES_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/matches"))
# Used by import scripts (not runtime API). Points to analisidef pipeline output.
ANALISIDEF_OUTPUT_DIR = Path(os.getenv("ANALISIDEF_OUTPUT_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output"))
ANALISIDEF_DAILY_DIR = Path(os.getenv("ANALISIDEF_DAILY_DIR", "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/daily/output"))

ENV = os.getenv("ENV", "development")

# D1 cutover: "native" reads from App_tool/output/digests/, "legacy" from analisidef/output/
DIGEST_SOURCE = os.getenv("DIGEST_SOURCE", "native")


def _parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


_default_cors_origins = (
    "https://metamonitor.app,https://www.metamonitor.app"
    if ENV == "production"
    else "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8100,http://127.0.0.1:8100"
)
CORS_ALLOW_ORIGINS = _parse_csv_env(os.getenv("CORS_ALLOW_ORIGINS", _default_cors_origins))
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower() == "true"
DUELS_SESSION = os.getenv("DUELS_SESSION", "").strip()
TEAM_API_REQUIRE_JWT = os.getenv("TEAM_API_REQUIRE_JWT", "false").strip().lower() == "true"

# Auth / JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY not set — check .env file")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
BCRYPT_ROUNDS = 12

# Stripe (empty = not configured, graceful degradation)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO_MONTHLY = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "")
STRIPE_PRICE_TEAM_MONTHLY = os.getenv("STRIPE_PRICE_TEAM_MONTHLY", "")
