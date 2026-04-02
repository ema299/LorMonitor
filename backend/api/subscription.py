"""Subscription — Stripe checkout, status, cancel, webhook."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db
from backend.models.user import User
from backend.services import subscription_service

router = APIRouter()


class SubscribeRequest(BaseModel):
    tier: str  # "pro" or "team"
    success_url: str = "https://metamonitor.app/dashboard.html?upgraded=true"
    cancel_url: str = "https://metamonitor.app/dashboard.html"


@router.post("/subscribe")
def subscribe(
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        url = subscription_service.create_checkout_session(
            db, user, body.tier, body.success_url, body.cancel_url,
        )
        return {"checkout_url": url}
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/subscription/status")
def subscription_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = subscription_service.get_subscription_status(db, user)
    if not status:
        return {"tier": user.tier, "status": "none"}
    return status


@router.post("/subscription/cancel")
def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return subscription_service.cancel_subscription(db, user)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event_type = subscription_service.handle_webhook(payload, sig, db)
        return {"status": "ok", "event": event_type}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
