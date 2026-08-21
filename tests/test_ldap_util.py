from app.ldap_util import (
    LdapServer,
    build_sync_user_filter,
    decode_ad_display_text,
    domain_suffix_from_base_dn,
    is_group_dn,
    ldap_entry_attr,
    normalize_bind_user,
    parse_legacy_url,
    parse_servers_raw,
    serialize_servers,
)


def test_normalize_bind_user_domain_backslash():
    assert normalize_bind_user("CORP\\svc_mfa") == "CORP\\svc_mfa"
    assert normalize_bind_user("CORP\\svc_mfa", "DC=corp,DC=local") == "svc_mfa@corp.local"
    assert normalize_bind_user("CORP\\", "DC=corp,DC=local") == "CORP\\"


def test_normalize_bind_user_plain_with_base_dn():
    assert normalize_bind_user("svc_mfa", "DC=corp,DC=local") == "svc_mfa@corp.local"


def test_parse_servers_json():
    raw = '[{"host":"dc1.corp.local","port":636},{"host":"dc2.corp.local","port":636}]'
    servers = parse_servers_raw(raw, True)
    assert servers == [
        LdapServer("dc1.corp.local", 636),
        LdapServer("dc2.corp.local", 636),
    ]


def test_parse_servers_lines():
    assert parse_servers_raw("dc1.corp.local:636\ndc2.corp.local", True) == [
        LdapServer("dc1.corp.local", 636),
        LdapServer("dc2.corp.local", 636),
    ]


def test_parse_legacy_url():
    assert parse_legacy_url("ldaps://dc1.corp.local", True) == [LdapServer("dc1.corp.local", 636)]


def test_domain_suffix():
    assert domain_suffix_from_base_dn("DC=corp,DC=local") == "corp.local"


def test_build_sync_user_filter_no_group():
    assert build_sync_user_filter() == "(&(objectCategory=person)(objectClass=user))"


def test_build_sync_user_filter_with_group():
    filt = build_sync_user_filter("CN=G,DC=corp,DC=local")
    assert "memberOf:1.2.840.113556.1.4.1941:=" in filt
    assert "CN=G,DC=corp,DC=local" in filt


def test_is_group_dn():
    assert is_group_dn("CN=2FA Users,OU=Groups,DC=Merl,DC=loc")
    assert not is_group_dn("2FA-Users")


def test_serialize_roundtrip():
    servers = [LdapServer("dc1", 389), LdapServer("dc2", 389)]
    assert parse_servers_raw(serialize_servers(servers), False) == servers


def test_decode_ad_display_text_unicode_escapes():
    raw = r"\u041a\u043e\u043d\u043e\u043d\u043e\u0432\u0430"
    assert decode_ad_display_text(raw) == "Кононова"


def test_decode_ad_display_text_plain_cyrillic():
    assert decode_ad_display_text("Кононова Анна") == "Кононова Анна"


class _LdapAttr:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value.encode("unicode_escape").decode("ascii")


class _LdapEntry:
    def __init__(self):
        self.displayName = _LdapAttr("Кононова")
        self.sAMAccountName = _LdapAttr("A0561")
        self.mail = _LdapAttr("")


def test_ldap_entry_attr_uses_value_not_str_escape():
    entry = _LdapEntry()
    assert ldap_entry_attr(entry, "displayName") == "Кононова"
    assert ldap_entry_attr(entry, "sAMAccountName") == "A0561"
    assert ldap_entry_attr(entry, "mail") == ""
