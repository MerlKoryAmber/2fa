from app.audit_labels import audit_event_label, format_audit_meta


def test_audit_event_label():
    assert audit_event_label("LDAP_SYNC_AUTO") == "Авто-синхронизация LDAP"
    assert audit_event_label("UNKNOWN_X") == "Unknown x"


def test_format_audit_meta_reason():
    text = format_audit_meta({"reason": "ldap_fail", "by": "admin"})
    assert "неверный пароль LDAP" in text
    assert "Администратор: admin" in text


def test_format_audit_meta_settings_keys():
    text = format_audit_meta({"keys": ["ldap_base_dn", "smtp_host"]})
    assert "Base DN" in text
    assert "SMTP хост" in text
