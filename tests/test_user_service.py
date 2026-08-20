from app.models import User
from app.user_service import list_users


def test_list_users_contains_ad(db_session):
    db_session.add_all(
        [
            User(ad_username="alice", otp_method="NONE"),
            User(ad_username="bob", otp_method="TOTP", totp_confirmed=True),
            User(ad_username="alicia", otp_method="NONE"),
        ]
    )
    db_session.commit()
    names = {u["ad_username"] for u in list_users(db_session, ad="ali")}
    assert names == {"alice", "alicia"}


def test_list_users_contains_email(db_session):
    db_session.add_all(
        [
            User(ad_username="a", otp_method="NONE", ldap_email="alice@corp.local"),
            User(ad_username="b", otp_method="NONE", ldap_email="bob@corp.local"),
        ]
    )
    db_session.commit()
    assert len(list_users(db_session, email="corp")) == 2
    assert len(list_users(db_session, email="alice@")) == 1


def test_list_users_method_and_totp(db_session):
    from app.otp import encrypt_totp_secret

    db_session.add_all(
        [
            User(
                ad_username="t1",
                otp_method="TOTP",
                totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
                totp_confirmed=True,
                telegram_chat_id="12345",
            ),
            User(
                ad_username="t2",
                otp_method="TOTP",
                totp_secret_encrypted=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
                totp_confirmed=False,
            ),
            User(ad_username="n1", otp_method="NONE"),
        ]
    )
    db_session.commit()
    rows = list_users(db_session, method="TOTP")
    assert len(rows) == 2
    multi = next(r for r in rows if r["ad_username"] == "t1")
    assert multi["has_totp"] is True
    assert multi["telegram_chat_id"] == "12345"
    assert len(list_users(db_session, totp="yes")) == 1
    assert len(list_users(db_session, totp="no")) == 2
