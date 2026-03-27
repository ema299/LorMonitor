"""Dependency injection for FastAPI endpoints."""
from sqlalchemy.orm import Session
from backend.models import SessionLocal


def get_db():
    """Yield a DB session, auto-close on request end."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
