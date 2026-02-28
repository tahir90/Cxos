"""Real Google Drive + OneDrive integration — list and read files."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class GoogleDriveClient(BaseConnectorClient):
    """Google Drive via API key or OAuth token."""

    @property
    def connector_id(self) -> str:
        return "google_drive"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["files", "file_content", "shared_drives", "recent"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token is required")
        try:
            resp = httpx.get(
                "https://www.googleapis.com/drive/v3/about",
                headers=self._headers(credentials),
                params={"fields": "user,storageQuota"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                quota = data.get("storageQuota", {})
                used_gb = int(quota.get("usage", 0)) / (1024**3)
                return ConnectionResult(
                    True,
                    f"Connected as {user.get('displayName', '?')} "
                    f"({user.get('emailAddress', '?')}). "
                    f"Storage used: {used_gb:.1f} GB",
                )
            return ConnectionResult(
                False, f"Status {resp.status_code}: {resp.text[:200]}"
            )
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        h = self._headers(credentials)

        if data_type == "files":
            return self._fetch_files(h, kwargs.get("query", ""))
        elif data_type == "recent":
            return self._fetch_recent(h)
        elif data_type == "file_content":
            return self._fetch_file_content(
                h, kwargs.get("file_id", "")
            )
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_files(self, headers: dict, query: str) -> ConnectorData:
        try:
            params: dict[str, Any] = {
                "pageSize": 50,
                "fields": "files(id,name,mimeType,modifiedTime,size,owners)",
            }
            if query:
                params["q"] = f"name contains '{query}'"
            resp = httpx.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers, params=params, timeout=10,
            )
            data = resp.json()
            files = [
                {
                    "id": f["id"],
                    "name": f.get("name", ""),
                    "type": f.get("mimeType", ""),
                    "modified": f.get("modifiedTime", ""),
                    "size": int(f.get("size", 0)),
                    "owner": (
                        f.get("owners", [{}])[0].get("displayName", "")
                        if f.get("owners") else ""
                    ),
                }
                for f in data.get("files", [])
            ]
            return ConnectorData(
                self.connector_id, "files",
                records=files,
                summary=f"{len(files)} files found",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "files", error=str(e))

    def _fetch_recent(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params={
                    "pageSize": 20,
                    "orderBy": "modifiedTime desc",
                    "fields": "files(id,name,mimeType,modifiedTime)",
                },
                timeout=10,
            )
            data = resp.json()
            files = [
                {
                    "id": f["id"],
                    "name": f.get("name", ""),
                    "type": f.get("mimeType", ""),
                    "modified": f.get("modifiedTime", ""),
                }
                for f in data.get("files", [])
            ]
            return ConnectorData(
                self.connector_id, "recent",
                records=files,
                summary=f"{len(files)} recently modified files",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "recent", error=str(e)
            )

    def _fetch_file_content(
        self, headers: dict, file_id: str
    ) -> ConnectorData:
        if not file_id:
            return ConnectorData(
                self.connector_id, "file_content",
                error="file_id required",
            )
        try:
            resp = httpx.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
                timeout=15,
            )
            content = resp.text[:10000]
            return ConnectorData(
                self.connector_id, "file_content",
                records=[{"file_id": file_id, "content": content}],
                summary=f"File content fetched ({len(content)} chars)",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "file_content", error=str(e)
            )


class OneDriveClient(BaseConnectorClient):
    """OneDrive / SharePoint via Microsoft Graph API."""

    @property
    def connector_id(self) -> str:
        return "onedrive"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["files", "file_content", "recent", "shared"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token is required")
        try:
            resp = httpx.get(
                "https://graph.microsoft.com/v1.0/me/drive",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                owner = data.get("owner", {}).get("user", {})
                quota = data.get("quota", {})
                used_gb = quota.get("used", 0) / (1024**3)
                return ConnectionResult(
                    True,
                    f"Connected: {owner.get('displayName', '?')}. "
                    f"Used: {used_gb:.1f} GB",
                )
            return ConnectionResult(
                False, f"Status {resp.status_code}"
            )
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        h = self._headers(credentials)

        if data_type == "files":
            return self._fetch_files(h, kwargs.get("path", "/"))
        elif data_type == "recent":
            return self._fetch_recent(h)
        elif data_type == "file_content":
            return self._fetch_content(h, kwargs.get("item_id", ""))
        elif data_type == "shared":
            return self._fetch_shared(h)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_files(self, headers: dict, path: str) -> ConnectorData:
        try:
            if path == "/":
                url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
            else:
                url = (
                    f"https://graph.microsoft.com/v1.0/me/drive/root:"
                    f"{path}:/children"
                )
            resp = httpx.get(url, headers=headers, timeout=10)
            data = resp.json()
            files = [
                {
                    "id": f.get("id", ""),
                    "name": f.get("name", ""),
                    "size": f.get("size", 0),
                    "modified": (
                        f.get("lastModifiedDateTime", "")
                    ),
                    "type": (
                        "folder" if "folder" in f else
                        f.get("file", {}).get("mimeType", "file")
                    ),
                    "web_url": f.get("webUrl", ""),
                }
                for f in data.get("value", [])
            ]
            return ConnectorData(
                self.connector_id, "files",
                records=files,
                summary=f"{len(files)} items in {path}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "files", error=str(e))

    def _fetch_recent(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://graph.microsoft.com/v1.0/me/drive/recent",
                headers=headers, timeout=10,
            )
            data = resp.json()
            files = [
                {
                    "name": f.get("name", ""),
                    "modified": f.get("lastModifiedDateTime", ""),
                    "web_url": f.get("webUrl", ""),
                }
                for f in data.get("value", [])[:20]
            ]
            return ConnectorData(
                self.connector_id, "recent",
                records=files,
                summary=f"{len(files)} recently modified",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "recent", error=str(e)
            )

    def _fetch_content(
        self, headers: dict, item_id: str
    ) -> ConnectorData:
        if not item_id:
            return ConnectorData(
                self.connector_id, "file_content",
                error="item_id required",
            )
        try:
            resp = httpx.get(
                f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content",
                headers=headers, timeout=15,
                follow_redirects=True,
            )
            content = resp.text[:10000]
            return ConnectorData(
                self.connector_id, "file_content",
                records=[{"item_id": item_id, "content": content}],
                summary=f"Content fetched ({len(content)} chars)",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "file_content", error=str(e)
            )

    def _fetch_shared(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://graph.microsoft.com/v1.0/me/drive/sharedWithMe",
                headers=headers, timeout=10,
            )
            data = resp.json()
            files = [
                {
                    "name": f.get("name", ""),
                    "shared_by": (
                        f.get("remoteItem", {}).get("shared", {})
                        .get("sharedBy", {}).get("user", {})
                        .get("displayName", "")
                    ),
                    "web_url": f.get("webUrl", ""),
                }
                for f in data.get("value", [])[:20]
            ]
            return ConnectorData(
                self.connector_id, "shared",
                records=files,
                summary=f"{len(files)} shared files",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "shared", error=str(e)
            )
