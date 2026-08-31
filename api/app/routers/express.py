import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.express_push import record_decision
from app.mfa_channels import sync_otp_method_from_channels
from app.models import OtpChallenge, User
from app.routers.radius import require_internal

log = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["express"])


class BindIn(BaseModel):
    email: str = ""
    user_huid: str = ""
    chat_id: str = ""
    name: str = ""


class DecisionIn(BaseModel):
    state: str
    decision: str
    user_huid: str = ""


@router.post("/internal/express/bind")
def express_bind(body: BindIn, db: Session = Depends(get_db), _: None = Depends(require_internal)):
    email = (body.email or "").strip().lower()
    chat = (body.chat_id or "").strip()
    if not chat:
        raise HTTPException(400, "chat_id required")
    user = None
    if email:
        user = db.query(User).filter(User.ldap_email.ilike(email)).first()
    if user is None and email:
        local = email.split("@", 1)[0]
        user = db.query(User).filter(User.ad_username.ilike(local)).first()
    if user is None:
        audit(db, "EXPRESS_BIND_MISS", username=email or body.user_huid, reason="user_not_found")
        return {"ok": False, "error": "user_not_found"}
    user.expressms_id = chat
    user.express_channel_enabled = True
    sync_otp_method_from_channels(user)
    db.commit()
    audit(db, "EXPRESS_BIND_OK", user_id=user.id, username=user.ad_username)
    return {"ok": True, "ad_username": user.ad_username}


@router.post("/internal/express/decision")
def express_decision(body: DecisionIn, db: Session = Depends(get_db), _: None = Depends(require_internal)):
    decision = (body.decision or "").strip().lower()
    if decision not in ("approve", "deny"):
        raise HTTPException(400, "decision")
    state = (body.state or "").strip()
    row = db.query(OtpChallenge).filter(OtpChallenge.state_token == state).first()
    if not row:
        record_decision(state, decision, 60)
        log.warning("express decision late: unknown state=%s decision=%s", state[:8], decision)
        return {"ok": False, "error": "unknown_or_used"}
    if row.consumed:
        record_decision(state, decision, 60)
        log.warning(
            "express decision late: challenge consumed user_id=%s state=%s decision=%s",
            row.user_id,
            state[:8],
            decision,
        )
        audit(db, "EXPRESS_PUSH_LATE", user_id=row.user_id, reason=decision)
        return {"ok": False, "error": "unknown_or_used"}
    ttl = 120
    if row.expires_at and row.created_at:
        ttl = max(int((row.expires_at - row.created_at).total_seconds()), 30)
    record_decision(state, decision, ttl)
    audit(db, "EXPRESS_PUSH_DECISION", user_id=row.user_id, reason=decision)
    return {"ok": True}
