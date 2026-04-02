from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Import all models so Alembic can see them
from backend.models.user import User, UserSession, PasswordResetToken  # noqa: E402, F401
from backend.models.subscription import Subscription  # noqa: E402, F401
from backend.models.user_deck import UserDeck  # noqa: E402, F401
from backend.models.match import Match  # noqa: E402, F401
from backend.models.analysis import KillerCurve, Archive, ThreatLLM, DailySnapshot  # noqa: E402, F401
from backend.models.audit import AuditLog  # noqa: E402, F401
from backend.models.promo import PromoCode, PromoRedemption  # noqa: E402, F401
from backend.models.team import TeamReplay, TeamRoster  # noqa: E402, F401
from backend.models.community import Video, Tournament  # noqa: E402, F401
