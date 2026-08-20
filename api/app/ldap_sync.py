from sqlalchemy.orm import Session

from app.audit import audit
from app.ldap_auth import list_ldap_users
from app.models import User
from app.settings_service import ldap_config


def run_ldap_sync(db: Session, *, by: str = "system") -> dict:
    cfg = ldap_config(db)
    rows, err = list_ldap_users(cfg)
    if err:
        return {"ok": False, "error": err}
    created = 0
    for row in rows:
        user = db.query(User).filter(User.ad_username == row["username"]).first()
        if not user:
            user = User(ad_username=row["username"], otp_method="NONE")
            db.add(user)
            created += 1
        if row.get("email"):
            user.ldap_email = row["email"]
        if row.get("display_name"):
            user.display_name = row["display_name"]
    db.commit()
    event = "LDAP_SYNC_AUTO" if by == "system" else "LDAP_SYNC"
    audit(db, event, username=by, created=created, total=len(rows))
    return {"ok": True, "created": created, "total": len(rows)}
