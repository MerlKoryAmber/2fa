from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_listen_host: str = "0.0.0.0"
    bot_listen_port: int = 8030
    bot_id: str = ""
    bot_secret_key: str = ""
    bot_app_id: str = "push2fa_bot"
    botx_api_host: str = ""
    mk2fa_api_url: str = ""
    internal_api_token: str = ""
    http_timeout_seconds: float = 10.0


settings = Settings()


def botx_base() -> str:
    raw = (settings.botx_api_host or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"https://{raw}"
