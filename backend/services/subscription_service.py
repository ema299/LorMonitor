"""Stripe subscription service — checkout, webhooks, tier management."""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO_MONTHLY, STRIPE_PRICE_TEAM_MONTHLY

logger = logging.getLogger(__name__)

try:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    stripe = None


def _check_stripe():
    if stripe is None:
        raise RuntimeError("stripe package not installed")
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe not configured (STRIPE_SECRET_KEY empty)")


def create_checkout_session(db: Session, user, tier: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout Session and return the URL."""
    _check_stripe()

    price_map = {"pro": STRIPE_PRICE_PRO_MONTHLY, "team": STRIPE_PRICE_TEAM_MONTHLY}
    price_id = price_map.get(tier)
    if not price_id:
        raise ValueError(f"Invalid tier: {tier}")

    # Get or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        user.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


def handle_webhook(payload: bytes, sig_header: str, db: Session) -> str:
    """Process Stripe webhook event."""
    _check_stripe()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise ValueError(f"Invalid webhook: {e}")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data)
    elif event_type == "invoice.paid":
        _handle_invoice_paid(db, data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(db, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data)

    return event_type


def _handle_checkout_completed(db: Session, data: dict):
    customer_id = data.get("customer")
    sub_id = data.get("subscription")
    if not customer_id:
        return

    user = db.execute(
        text("SELECT id, tier FROM users WHERE stripe_customer_id = :cid"),
        {"cid": customer_id},
    ).fetchone()
    if not user:
        return

    # Determine tier from price
    if sub_id:
        sub = stripe.Subscription.retrieve(sub_id)
        price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else ""
        tier = "team" if price_id == STRIPE_PRICE_TEAM_MONTHLY else "pro"
    else:
        tier = "pro"

    db.execute(
        text("UPDATE users SET tier = :tier, updated_at = now() WHERE id = :uid"),
        {"tier": tier, "uid": user.id},
    )

    db.execute(text("""
        INSERT INTO subscriptions (user_id, tier, status, stripe_sub_id, current_period_start, current_period_end)
        VALUES (:uid, :tier, 'active', :sid, now(), now() + interval '30 days')
    """), {"uid": user.id, "tier": tier, "sid": sub_id})

    db.commit()
    logger.info("Checkout completed: user=%s tier=%s", user.id, tier)


def _handle_invoice_paid(db: Session, data: dict):
    sub_id = data.get("subscription")
    if sub_id:
        db.execute(
            text("UPDATE subscriptions SET status = 'active', current_period_end = now() + interval '30 days' WHERE stripe_sub_id = :sid"),
            {"sid": sub_id},
        )
        db.commit()


def _handle_payment_failed(db: Session, data: dict):
    sub_id = data.get("subscription")
    if sub_id:
        db.execute(
            text("UPDATE subscriptions SET status = 'past_due' WHERE stripe_sub_id = :sid"),
            {"sid": sub_id},
        )
        db.commit()


def _handle_subscription_deleted(db: Session, data: dict):
    sub_id = data.get("id")
    customer_id = data.get("customer")
    if sub_id:
        db.execute(
            text("UPDATE subscriptions SET status = 'cancelled' WHERE stripe_sub_id = :sid"),
            {"sid": sub_id},
        )
    if customer_id:
        db.execute(
            text("UPDATE users SET tier = 'free', updated_at = now() WHERE stripe_customer_id = :cid"),
            {"cid": customer_id},
        )
    db.commit()


def cancel_subscription(db: Session, user) -> dict:
    """Cancel subscription at period end."""
    _check_stripe()

    sub_row = db.execute(
        text("SELECT stripe_sub_id FROM subscriptions WHERE user_id = :uid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"uid": user.id},
    ).fetchone()

    if not sub_row or not sub_row.stripe_sub_id:
        raise ValueError("No active subscription")

    stripe.Subscription.modify(sub_row.stripe_sub_id, cancel_at_period_end=True)
    return {"status": "cancelling_at_period_end"}


def get_subscription_status(db: Session, user) -> dict | None:
    row = db.execute(
        text("SELECT tier, status, stripe_sub_id, current_period_end FROM subscriptions WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"),
        {"uid": user.id},
    ).fetchone()

    if not row:
        return None
    return {
        "tier": row.tier,
        "status": row.status,
        "period_end": row.current_period_end.isoformat() if row.current_period_end else None,
    }
