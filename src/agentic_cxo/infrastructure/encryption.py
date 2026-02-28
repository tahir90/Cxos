"""
Credential Encryption — API keys and secrets stored encrypted at rest.

Uses Fernet symmetric encryption. The encryption key is derived
from a master secret (env var or generated on first run).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


def _get_master_key() -> bytes:
    """Get or generate the master encryption key."""
    env_key = os.getenv("CXO_ENCRYPTION_KEY", "")
    if env_key:
        return base64.urlsafe_b64encode(
            hashlib.sha256(env_key.encode()).digest()
        )
    key_path = DATA_DIR / ".master_key"
    DATA_DIR.mkdir(exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    logger.info("Generated new encryption master key")
    return key


class EncryptedStore:
    """Stores data encrypted on disk."""

    def __init__(self) -> None:
        self._fernet = Fernet(_get_master_key())

    def encrypt(self, data: dict) -> bytes:
        plaintext = json.dumps(data).encode()
        return self._fernet.encrypt(plaintext)

    def decrypt(self, token: bytes) -> dict:
        plaintext = self._fernet.decrypt(token)
        return json.loads(plaintext.decode())

    def save_encrypted(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.encrypt(data)
        path.write_bytes(encrypted)

    def load_encrypted(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return self.decrypt(path.read_bytes())
        except Exception:
            logger.warning("Could not decrypt %s", path)
            return None

    def delete(self, path: Path) -> None:
        if path.exists():
            path.unlink()
