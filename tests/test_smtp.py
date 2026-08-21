from app.mail_service import run_smtp_test
from app.settings_service import SmtpConfig


def test_smtp_test_requires_host():
    cfg = SmtpConfig(
        dry_run=True,
        host="",
        port=587,
        use_ssl=False,
        from_addr="a@b.c",
        username="",
        password="",
    )
    out = run_smtp_test(cfg, "user@example.com")
    assert out["ok"] is False
    assert "host" in out["message"].lower()


def test_smtp_test_requires_recipient():
    cfg = SmtpConfig(
        dry_run=False,
        host="mail.example",
        port=587,
        use_ssl=False,
        from_addr="a@b.c",
        username="",
        password="",
    )
    out = run_smtp_test(cfg, "")
    assert out["ok"] is False
    assert "email" in out["message"].lower() or "получател" in out["message"].lower()


def test_smtp_config_for_test_overrides(db_session):
    from app.settings_service import set_raw, smtp_config_for_test

    set_raw(db_session, "smtp.host", "old.example")
    set_raw(db_session, "smtp.from_addr", "old@example.com")
    set_raw(db_session, "smtp.password", "stored-secret")
    cfg = smtp_config_for_test(
        db_session,
        {
            "smtp_host": "new.example",
            "smtp_port": 465,
            "smtp_use_ssl": True,
            "smtp_from": "new@example.com",
            "smtp_password_use_stored": True,
        },
    )
    assert cfg.host == "new.example"
    assert cfg.port == 465
    assert cfg.use_ssl is True
    assert cfg.from_addr == "new@example.com"
    assert cfg.password == "stored-secret"
