import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)


def _derive_key_from_secret(secret: str) -> bytes:
    derived = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(derived)


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.strip() if settings.encryption_key else ""
    if key:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError):
            logger.warning(
                "ENCRYPTION_KEY is invalid — falling back to SECRET_KEY derivation. "
                "Generate a valid key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
    return Fernet(_derive_key_from_secret(settings.secret_key))


def encrypt_value(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(cipher: str) -> str:
    try:
        return _get_fernet().decrypt(cipher.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value — check ENCRYPTION_KEY")
        raise
