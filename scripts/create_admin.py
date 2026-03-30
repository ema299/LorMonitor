"""Create admin and test accounts for Lorcana Monitor."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import SessionLocal
from backend.models.user import User
from backend.services.auth_service import hash_password


def create_user(db, email, password, tier="free", is_admin=False, display_name=None):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"  [skip] {email} already exists (tier={existing.tier})")
        return existing

    user = User(
        email=email,
        password_hash=hash_password(password),
        tier=tier,
        is_admin=is_admin,
        display_name=display_name or email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"  [created] {email} (tier={tier}, admin={is_admin})")
    return user


def main():
    parser = argparse.ArgumentParser(description="Create admin and test accounts")
    parser.add_argument("--admin-password", default="admin123!")
    parser.add_argument("--test-password", default="test1234")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Creating accounts...")
        create_user(db, "admin@metamonitor.app", args.admin_password,
                    tier="team", is_admin=True, display_name="Admin")
        create_user(db, "free@metamonitor.app", args.test_password,
                    tier="free", display_name="Test Free")
        create_user(db, "pro@metamonitor.app", args.test_password,
                    tier="pro", display_name="Test Pro")
        create_user(db, "team@metamonitor.app", args.test_password,
                    tier="team", display_name="Test Team")
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
