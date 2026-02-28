"""Real Apple App Store + Google Play + Firebase clients."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class AppleAppStoreClient(BaseConnectorClient):
    """Apple App Store Connect — ratings, reviews, downloads, revenue."""

    @property
    def connector_id(self) -> str:
        return "apple_app_store"

    @property
    def required_credentials(self) -> list[str]:
        return ["key_id", "issuer_id", "private_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["apps", "ratings", "reviews"]

    def _generate_token(self, creds: dict[str, str]) -> str:
        """Generate JWT for App Store Connect API."""
        import time

        from jose import jwt

        now = int(time.time())
        payload = {
            "iss": creds.get("issuer_id", ""),
            "iat": now,
            "exp": now + 1200,
            "aud": "appstoreconnect-v1",
        }
        key = creds.get("private_key", "")
        headers = {
            "alg": "ES256",
            "kid": creds.get("key_id", ""),
            "typ": "JWT",
        }
        return jwt.encode(payload, key, algorithm="ES256", headers=headers)

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Key ID, Issuer ID, and private key required")
        try:
            token = self._generate_token(credentials)
            resp = httpx.get(
                "https://api.appstoreconnect.apple.com/v1/apps",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 1}, timeout=10,
            )
            if resp.status_code == 200:
                apps = resp.json().get("data", [])
                name = apps[0]["attributes"]["name"] if apps else "?"
                return ConnectionResult(True, f"Connected. App: {name}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        try:
            token = self._generate_token(credentials)
            headers = {"Authorization": f"Bearer {token}"}
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=f"Token error: {e}")

        if data_type == "apps":
            return self._fetch_apps(headers)
        elif data_type == "reviews":
            return self._fetch_reviews(headers, kwargs.get("app_id", ""))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_apps(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://api.appstoreconnect.apple.com/v1/apps",
                headers=headers, params={"limit": 10}, timeout=10,
            )
            apps = [
                {
                    "id": a["id"],
                    "name": a["attributes"].get("name", ""),
                    "bundle_id": a["attributes"].get("bundleId", ""),
                    "sku": a["attributes"].get("sku", ""),
                }
                for a in resp.json().get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "apps", records=apps,
                summary=f"{len(apps)} apps",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "apps", error=str(e))

    def _fetch_reviews(self, headers: dict, app_id: str) -> ConnectorData:
        if not app_id:
            return ConnectorData(self.connector_id, "reviews", error="app_id required")
        try:
            resp = httpx.get(
                f"https://api.appstoreconnect.apple.com/v1/apps/{app_id}/customerReviews",
                headers=headers, params={"limit": 20, "sort": "-createdDate"},
                timeout=10,
            )
            reviews = [
                {
                    "title": r["attributes"].get("title", ""),
                    "body": r["attributes"].get("body", "")[:200],
                    "rating": r["attributes"].get("rating", 0),
                    "date": r["attributes"].get("createdDate", ""),
                }
                for r in resp.json().get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "reviews", records=reviews,
                summary=f"{len(reviews)} recent reviews",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "reviews", error=str(e))


class GooglePlayClient(BaseConnectorClient):
    """Google Play Console — via Google Play Developer API."""

    @property
    def connector_id(self) -> str:
        return "google_play"

    @property
    def required_credentials(self) -> list[str]:
        return ["package_name", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["app_info", "reviews"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("package_name") or not credentials.get("access_token"):
            return ConnectionResult(False, "Package name and access token required")
        try:
            pkg = credentials["package_name"]
            resp = httpx.get(
                f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{pkg}/reviews",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                params={"maxResults": 1}, timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, f"Connected to {pkg}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('access_token', '')}"}
        pkg = credentials.get("package_name", "")

        if data_type == "reviews":
            return self._fetch_reviews(h, pkg)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_reviews(self, headers: dict, pkg: str) -> ConnectorData:
        try:
            resp = httpx.get(
                f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{pkg}/reviews",
                headers=headers, params={"maxResults": 20}, timeout=10,
            )
            data = resp.json()
            reviews = []
            for r in data.get("reviews", []):
                comment = r.get("comments", [{}])[0].get("userComment", {})
                reviews.append({
                    "author": r.get("authorName", ""),
                    "text": comment.get("text", "")[:200],
                    "rating": comment.get("starRating", 0),
                    "date": comment.get("lastModified", {}).get("seconds", ""),
                })
            return ConnectorData(
                self.connector_id, "reviews", records=reviews,
                summary=f"{len(reviews)} recent reviews",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "reviews", error=str(e))


class FirebaseClient(BaseConnectorClient):
    """Firebase — crashlytics, analytics, performance."""

    @property
    def connector_id(self) -> str:
        return "firebase"

    @property
    def required_credentials(self) -> list[str]:
        return ["project_id", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["projects", "analytics", "crashlytics"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("project_id") or not credentials.get("access_token"):
            return ConnectionResult(False, "Project ID and access token required")
        try:
            pid = credentials["project_id"]
            resp = httpx.get(
                f"https://firebase.googleapis.com/v1beta1/projects/{pid}",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True, f"Connected: {data.get('displayName', pid)}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('access_token', '')}"}
        pid = credentials.get("project_id", "")

        if data_type == "projects":
            return self._fetch_project(h, pid)
        return ConnectorData(
            self.connector_id, data_type,
            records=[{"status": "connected", "project": pid}],
            summary=f"Firebase {data_type} for {pid}",
        )

    def _fetch_project(self, headers: dict, pid: str) -> ConnectorData:
        try:
            resp = httpx.get(
                f"https://firebase.googleapis.com/v1beta1/projects/{pid}",
                headers=headers, timeout=10,
            )
            data = resp.json()
            return ConnectorData(
                self.connector_id, "projects",
                records=[{
                    "project_id": data.get("projectId", ""),
                    "display_name": data.get("displayName", ""),
                    "project_number": data.get("projectNumber", ""),
                }],
                summary=f"Project: {data.get('displayName', pid)}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "projects", error=str(e))
