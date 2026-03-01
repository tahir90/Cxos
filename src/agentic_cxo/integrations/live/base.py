"""
Base connector client — framework for real integrations.

Every live connector:
1. Accepts credentials
2. Tests the connection (validates creds with a real API call)
3. Fetches specific data types
4. Handles errors gracefully
5. Stores credentials encrypted at rest (EncryptedStore)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_cxo.config import settings
from agentic_cxo.infrastructure.encryption import EncryptedStore

logger = logging.getLogger(__name__)

CREDS_DIR = Path(".cxo_data") / "credentials"


@dataclass
class ConnectionResult:
    """Result of testing a connector."""

    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorData:
    """Data fetched from a live connector."""

    connector_id: str
    data_type: str
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    fetched_at: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not self.fetched_at:
            self.fetched_at = datetime.now(timezone.utc).isoformat()


class BaseConnectorClient(ABC):
    """Abstract base for all live connector clients."""

    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Must match the ID in the connector registry."""

    @property
    @abstractmethod
    def required_credentials(self) -> list[str]:
        """List of credential field names needed."""

    @abstractmethod
    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        """Validate credentials with a real API call."""

    @abstractmethod
    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        """Fetch a specific type of data."""

    @property
    def available_data_types(self) -> list[str]:
        """What data types this connector can fetch."""
        return []


class CredentialStore:
    """Stores connector credentials encrypted at rest."""

    def __init__(self) -> None:
        CREDS_DIR.mkdir(parents=True, exist_ok=True)
        self._encrypted = EncryptedStore()

    def save(self, connector_id: str, credentials: dict[str, str]) -> None:
        path = CREDS_DIR / f"{connector_id}.enc"
        data = {
            "connector_id": connector_id,
            "credentials": credentials,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._encrypted.save_encrypted(path, data)
        logger.info("Credentials saved (encrypted) for %s", connector_id)

    def load(self, connector_id: str) -> dict[str, str] | None:
        enc_path = CREDS_DIR / f"{connector_id}.enc"
        if enc_path.exists():
            data = self._encrypted.load_encrypted(enc_path)
            if data:
                return data.get("credentials", {})
        # Migrate legacy plain JSON if present
        json_path = CREDS_DIR / f"{connector_id}.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                creds = data.get("credentials", {})
                if creds:
                    self.save(connector_id, creds)
                    json_path.unlink()
                return creds
            except Exception:
                pass
        return None

    def delete(self, connector_id: str) -> None:
        for ext in (".enc", ".json"):
            path = CREDS_DIR / f"{connector_id}{ext}"
            if path.exists():
                path.unlink()

    def list_connected(self) -> list[str]:
        stems = {p.stem for p in CREDS_DIR.glob("*.enc")}
        stems |= {p.stem for p in CREDS_DIR.glob("*.json")}
        return list(stems)

    def is_connected(self, connector_id: str) -> bool:
        return (CREDS_DIR / f"{connector_id}.enc").exists() or (
            CREDS_DIR / f"{connector_id}.json"
        ).exists()
