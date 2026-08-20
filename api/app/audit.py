from sqlalchemy.orm import Session

from app.models import AuditEvent


def audit(db: Session, event_type: str, user_id: int | None = None, username: str | None = None, **meta):
    db.add(
        AuditEvent(
            event_type=event_type,
            user_id=user_id,
            username=username,
            meta=meta or None,
        )
    )
    db.commit()
