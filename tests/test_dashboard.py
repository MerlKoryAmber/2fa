from datetime import datetime, timedelta, timezone

from app.dashboard import build_dashboard
from app.models import AuditEvent, User
from app.otp import encrypt_totp_secret


def test_dashboard_people_and_empty_radius(db_session, fake_redis):
    db_session.add(User(ad_username="a", otp_method="NONE"))
    db_session.add(
        User(
            ad_username="b",
            otp_method="TOTP",
            totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_confirmed=False,
        )
    )
    db_session.add(
        User(
            ad_username="c",
            otp_method="TOTP",
            totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_confirmed=True,
        )
    )
    db_session.commit()
    out = build_dashboard(db_session)
    assert out["users"] == 3
    assert out["enrolled"] == 2
    assert out["without_2fa"] == 1
    assert out["totp_pending"] == 1
    assert out["radius_24h"]["accept"] == 0
    assert out["health"]["db"] is True
    assert "redis" in out["health"]
    assert out["recent"] == []


def test_dashboard_radius_24h_counts(db_session, fake_redis):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            AuditEvent(timestamp=now, event_type="RADIUS_ACCEPT", username="u1"),
            AuditEvent(timestamp=now, event_type="RADIUS_ACCEPT", username="u2"),
            AuditEvent(timestamp=now, event_type="RADIUS_REJECT", username="u3"),
            AuditEvent(timestamp=now, event_type="OTP_FAIL", username="u4"),
            AuditEvent(timestamp=now - timedelta(hours=30), event_type="RADIUS_ACCEPT", username="old"),
        ]
    )
    db_session.commit()
    out = build_dashboard(db_session)
    assert out["radius_24h"]["accept"] == 2
    assert out["radius_24h"]["reject"] == 1
    assert out["radius_24h"]["otp_fail"] == 1
    assert out["health"]["radius_events_1h"] >= 4
    assert len(out["recent"]) >= 4
    # как аудит: сверху новее
    assert out["recent"][0]["username"] != "old"
    ts0 = out["recent"][0]["timestamp"]
    ts1 = out["recent"][1]["timestamp"]
    assert ts0 >= ts1
