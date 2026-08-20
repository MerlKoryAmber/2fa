import pyotp

from app.ldap_auth import authenticate_ldap
from app.otp import encrypt_totp_secret, generate_numeric_otp, hash_otp, otp_hash_matches, verify_totp
from app.settings_service import LdapConfig


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


def test_ldap_mock_ok():
    cfg = LdapConfig(True, "demo", [], True, "", "sAMAccountName", "", "")
    assert authenticate_ldap("demo", "demo", cfg) is True


def test_ldap_mock_fail():
    cfg = LdapConfig(True, "demo", [], True, "", "sAMAccountName", "", "")
    assert authenticate_ldap("demo", "wrong", cfg) is False
