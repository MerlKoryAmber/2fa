import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import get_db
from app.internal_token import expected_internal_token, got_internal_token
from app.rate_limit import enforce_rate_limit
from app.radius_flow import handle_access_request
from app.radius_acl import is_client_allowed
from app.settings_service import radius_config

log = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["radius"])


class RadiusIn(BaseModel):
    username: str
    password: str
    state: str | None = None
    nas_ip: str | None = None


class RadiusEventIn(BaseModel):
    event_type: str
    username: str | None = None
    nas_ip: str | None = None
    reason: str | None = None


_GATEWAY_EVENTS = frozenset({"RADIUS_BAD_PACKET", "RADIUS_ERROR"})


def require_internal(request: Request):
    got = got_internal_token(request)
    exp = expected_internal_token() or (settings.internal_api_token or "").strip()
    if not exp or not secrets.compare_digest(got, exp):
        log.warning(
            "internal token reject got_len=%s exp_len=%s",
            len(got),
            len(exp),
        )
        raise HTTPException(
            403,
            {"msg": "Forbidden", "got_len": len(got), "exp_len": len(exp)},
        )


@router.get("/internal/radius/config")
def radius_runtime_config(db: Session = Depends(get_db), _: None = Depends(require_internal)):
    cfg = radius_config(db)
    return {
        "shared_secret": cfg.shared_secret,
        "port": cfg.port,
        "allowed_clients": cfg.allowed_clients,
    }


@router.post("/internal/radius/access-request")
def access_request(
    body: RadiusIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal),
):
    nas = body.nas_ip or (request.client.host if request.client else "unknown")
    cfg = radius_config(db)
    if not is_client_allowed(nas, cfg.allowed_rules()):
        audit(db, "RADIUS_NAS_DENIED", username=body.username, nas_ip=nas, reason="allowlist")
        return {"decision": "reject", "reply_message": "NAS not allowed"}
    try:
        enforce_rate_limit(
            "radius",
            f"{body.username}:{nas}",
            settings.rate_limit_radius_per_minute,
            60,
        )
    except HTTPException as exc:
        if exc.status_code == 429:
            audit(db, "RADIUS_ERROR", username=body.username, nas_ip=nas, reason="rate_limit")
            return {"decision": "reject", "reply_message": "Too many requests"}
        raise
    try:
        return handle_access_request(db, body.username, body.password, body.state, nas_ip=nas)
    except Exception:
        log.exception("radius access-request user=%s nas=%s", body.username, nas)
        audit(db, "RADIUS_ERROR", username=body.username, nas_ip=nas, reason="internal")
        return {"decision": "reject", "reply_message": "Internal error"}


@router.post("/internal/radius/event")
def radius_gateway_event(
    body: RadiusEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal),
):
    if body.event_type not in _GATEWAY_EVENTS:
        raise HTTPException(400, "unknown event")
    audit(db, body.event_type, username=body.username, nas_ip=body.nas_ip, reason=body.reason)
    return {"ok": True}
