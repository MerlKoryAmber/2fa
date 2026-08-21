import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
    nas = body.nas_ip or request.client.host if request.client else "unknown"
    cfg = radius_config(db)
    if not is_client_allowed(nas, cfg.allowed_rules()):
        return {"decision": "reject", "reply_message": "NAS not allowed"}
    enforce_rate_limit(
        "radius",
        f"{body.username}:{nas}",
        settings.rate_limit_radius_per_minute,
        60,
    )
    return handle_access_request(db, body.username, body.password, body.state)
