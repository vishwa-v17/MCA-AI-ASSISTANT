import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    secret = (os.getenv("USER_KEY_ENCRYPTION_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("USER_KEY_ENCRYPTION_SECRET is not configured.")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key):
    if not api_key:
        return ""
    return _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_api_key):
    if not encrypted_api_key:
        return ""
    try:
        return _fernet().decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored personal OpenRouter API key could not be decrypted.") from exc


def key_last4(api_key):
    return api_key[-4:] if api_key else ""
