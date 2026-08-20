import pyotp

from app.otp import encrypt_totp_secret, generate_numeric_otp, hash_otp, otp_hash_matches, verify_totp


def test_otp_hash_roundtrip():
    otp = generate_numeric_otp()
    salt = "abc"
    digest = hash_otp(otp, salt)
    assert otp_hash_matches(otp, salt, digest)
    assert not otp_hash_matches("000000", salt, digest)


def test_totp_verify():
    secret = "JBSWY3DPEHPK3PXP"
    enc = encrypt_totp_secret(secret)
    code = pyotp.TOTP(secret).now()
    assert verify_totp(enc, code, 1)


def test_ldap_auth_empty_rejected():
    from app.ldap_auth import authenticate_ldap
    from app.ldap_util import LdapServer
    from app.settings_service import LdapConfig

    cfg = LdapConfig(
        servers=[LdapServer(host="dc.example", port=389)],
        use_ssl=False,
        base_dn="DC=example,DC=com",
        user_attr="sAMAccountName",
        bind_user="svc",
        bind_password="x",
    )
    assert authenticate_ldap("", "x", cfg) is False
    assert authenticate_ldap("u", "", cfg) is False
