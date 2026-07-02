import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DEBUG_LOG = Path("vault_debug.log")


def get_key() -> bytes:
    """Return the encryption key from the VAULT_KEY environment variable."""
    raw = os.environ.get("VAULT_KEY")
    if not raw:
        raise ValueError(
            "VAULT_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return raw.encode()


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string with Fernet symmetric encryption."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] encrypt failed | error={type(exc).__name__}\n")
        raise


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] decrypt failed | error={type(exc).__name__}\n")
        raise
