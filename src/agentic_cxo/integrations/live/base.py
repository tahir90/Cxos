"""
Base connector client — framework for real integrations.

Every live connector:
1. Accepts credentials
2. Tests the connection (validates creds with a real API call)
3. Fetches specific data types
4. Handles errors gracefully
5. Stores credentials securely to disk (encrypted in production)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    """Stores connector credentials to disk."""

    def __init__(self) -> None:
        CREDS_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, connector_id: str, credentials: dict[str, str]) -> None:
        path = CREDS_DIR / f"{connector_id}.json"
        path.write_text(json.dumps({
            "connector_id": connector_id,
            "credentials": credentials,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        logger.info("Credentials saved for %s", connector_id)

    def load(self, connector_id: str) -> dict[str, str] | None:
        path = CREDS_DIR / f"{connector_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return data.get("credentials", {})
        except Exception:
            return None

    def delete(self, connector_id: str) -> None:
        path = CREDS_DIR / f"{connector_id}.json"
        if path.exists():
            path.unlink()

    def list_connected(self) -> list[str]:
        return [
            p.stem for p in CREDS_DIR.glob("*.json")
        ]

    def is_connected(self, connector_id: str) -> bool:
        return (CREDS_DIR / f"{connector_id}.json").exists()
