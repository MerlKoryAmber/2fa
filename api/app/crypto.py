from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.app_encryption_key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()
