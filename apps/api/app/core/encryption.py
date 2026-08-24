from cryptography.fernet import Fernet

from app.core.config import settings


fernet = Fernet(
    settings.token_encryption_key.encode()
)


def encrypt_token(token: str) -> str:
    return fernet.encrypt(
        token.encode()
    ).decode()


def decrypt_token(token: str) -> str:
    return fernet.decrypt(
        token.encode()
    ).decode()