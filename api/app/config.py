from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # По умолчанию dotenv ПОСЛЕ env и перебивает compose. Тогда printenv в api
    # совпадает с radius, а settings.internal_api_token — нет → 403 на /internal/*.
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, file_secret_settings, dotenv_settings, env_settings

    database_url: str = "postgresql+psycopg2://mfa:mfa@db:5432/mfa"
    redis_url: str = "redis://redis:6379/0"
    app_encryption_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    internal_api_token: str

    admin_username: str = "admin"
    admin_password: str = "admin"

    ldap_url: str = ""
    ldap_servers: str = ""
    ldap_use_ssl: bool = True
    ldap_base_dn: str = ""
    ldap_user_attr: str = "sAMAccountName"
    ldap_bind_user: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_sync_ou: str = ""
    ldap_sync_group: str = ""
    panel_operator_group: str = ""
    panel_auditor_group: str = ""

    totp_issuer: str = "MK2FA"
    totp_window_steps: int = 1
    otp_ttl_seconds: int = 60
    max_otp_attempts: int = 5
    challenge_ttl_seconds: int = 120

    expressms_dry_run: bool = True
    expressms_api_url: str = ""
    expressms_token: str = ""

    telegram_dry_run: bool = True
    telegram_bot_token: str = ""

    radius_secret: str = "testing123"
    radius_allowed_clients: str = ""

    public_base_url: str = ""
    smtp_dry_run: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_ssl: bool = False
    smtp_from: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_invite_subject: str = ""
    smtp_invite_body_template: str = ""

    demo_username: str = "demo"
    demo_password: str = "demo"
    demo_totp_secret: str = "JBSWY3DPEHPK3PXP"

    rate_limit_radius_per_minute: int = 30
    rate_limit_login_per_minute: int = 10
    seed_on_startup: bool = True


settings = Settings()
