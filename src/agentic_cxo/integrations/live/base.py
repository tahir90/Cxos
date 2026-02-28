"""
Base connector client — framework for real integrations.

Every live connector:
1. Accepts credentials
2. Tests the connection (validates creds with a real API call)
3. Fetches specific data types
4. Handles errors gracefully with retry + rate-limit logic
5. Stores credentials securely to disk
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CREDS_DIR = Path(".cxo_data") / "credentials"

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RATE_LIMIT_WAIT_DEFAULT = 5.0


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


def resilient_request(
    method: str,
    url: str,
    *,
    max_retries: int = MAX_RETRIES,
    **kwargs: Any,
) -> httpx.Response:
    """HTTP request with retry on transient failures and rate-limit back-off.

    Retries on: 429 (rate limit), 500, 502, 503, 504, and network errors.
    Respects ``Retry-After`` header when present.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = httpx.request(method, url, **kwargs)

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after
                    else RATE_LIMIT_WAIT_DEFAULT * (2 ** attempt)
                )
                wait = min(wait, 60.0)
                logger.warning(
                    "Rate limited on %s (attempt %d/%d), waiting %.1fs",
                    url, attempt + 1, max_retries + 1, wait,
                )
                time.sleep(wait)
                continue

            if resp.status_code in (500, 502, 503, 504) and attempt < max_retries:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "Server error %d on %s (attempt %d/%d), retrying in %.1fs",
                    resp.status_code, url, attempt + 1, max_retries + 1, wait,
                )
                time.sleep(wait)
                continue

            return resp

        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < max_retries:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "Network error on %s (attempt %d/%d): %s, retrying in %.1fs",
                    url, attempt + 1, max_retries + 1, e, wait,
                )
                time.sleep(wait)
            else:
                raise

    if last_exc:
        raise last_exc
    return resp  # type: ignore[possibly-undefined]


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
            logger.exception("Failed to load credentials for %s", connector_id)
            return None

    def delete(self, connector_id: str) -> None:
        path = CREDS_DIR / f"{connector_id}.json"
        if path.exists():
            path.unlink()
            logger.info("Credentials deleted for %s", connector_id)

    def list_connected(self) -> list[str]:
        return [
            p.stem for p in CREDS_DIR.glob("*.json")
        ]

    def is_connected(self, connector_id: str) -> bool:
        return (CREDS_DIR / f"{connector_id}.json").exists()
