from app.ldap_util import (
    LdapServer,
    build_sync_user_filter,
    domain_suffix_from_base_dn,
    is_group_dn,
    normalize_bind_user,
    parse_legacy_url,
    parse_servers_raw,
    serialize_servers,
)


def test_normalize_bind_user_domain_backslash():
    assert normalize_bind_user("CORP\\svc_mfa") == "CORP\\svc_mfa"
    assert normalize_bind_user("CORP\\svc_mfa", "DC=corp,DC=local") == "svc_mfa@corp.local"


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
