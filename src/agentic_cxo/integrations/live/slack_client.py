"""Real Slack integration — posts messages and reads channels."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class SlackClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "slack"

    @property
    def required_credentials(self) -> list[str]:
        return ["bot_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["channels", "messages", "users", "post_message"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        token = credentials.get("bot_token", "")
        if not token:
            return ConnectionResult(False, "Bot token is required")
        try:
            resp = httpx.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                return ConnectionResult(
                    True,
                    f"Connected as {data.get('user', '?')} "
                    f"in workspace {data.get('team', '?')}",
                    details=data,
                )
            return ConnectionResult(False, data.get("error", "Auth failed"))
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        token = credentials.get("bot_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        if data_type == "channels":
            return self._fetch_channels(headers)
        elif data_type == "messages":
            return self._fetch_messages(
                headers, kwargs.get("channel", "")
            )
        elif data_type == "users":
            return self._fetch_users(headers)
        elif data_type == "post_message":
            return self._post_message(
                headers,
                kwargs.get("channel", ""),
                kwargs.get("text", ""),
            )
        return ConnectorData(
            self.connector_id, data_type, error="Unknown data type"
        )

    def _fetch_channels(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://slack.com/api/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": 100},
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                return ConnectorData(
                    self.connector_id, "channels",
                    error=data.get("error", "Failed"),
                )
            channels = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "members": c.get("num_members", 0),
                    "topic": c.get("topic", {}).get("value", ""),
                }
                for c in data.get("channels", [])
            ]
            return ConnectorData(
                self.connector_id, "channels",
                records=channels,
                summary=f"Found {len(channels)} channels",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "channels", error=str(e)
            )

    def _fetch_messages(
        self, headers: dict, channel: str
    ) -> ConnectorData:
        if not channel:
            return ConnectorData(
                self.connector_id, "messages",
                error="Channel ID required",
            )
        try:
            resp = httpx.get(
                "https://slack.com/api/conversations.history",
                headers=headers,
                params={"channel": channel, "limit": 50},
                timeout=10,
            )
            data = resp.json()
            messages = [
                {
                    "text": m.get("text", ""),
                    "user": m.get("user", ""),
                    "ts": m.get("ts", ""),
                }
                for m in data.get("messages", [])
            ]
            return ConnectorData(
                self.connector_id, "messages",
                records=messages,
                summary=f"Fetched {len(messages)} messages",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "messages", error=str(e)
            )

    def _fetch_users(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://slack.com/api/users.list",
                headers=headers, timeout=10,
            )
            data = resp.json()
            users = [
                {
                    "id": u["id"],
                    "name": u.get("real_name", u.get("name", "")),
                    "email": u.get("profile", {}).get("email", ""),
                    "is_bot": u.get("is_bot", False),
                }
                for u in data.get("members", [])
                if not u.get("deleted")
            ]
            return ConnectorData(
                self.connector_id, "users",
                records=users,
                summary=f"Found {len(users)} active users",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "users", error=str(e)
            )

    def _post_message(
        self, headers: dict, channel: str, text: str
    ) -> ConnectorData:
        if not channel or not text:
            return ConnectorData(
                self.connector_id, "post_message",
                error="Channel and text required",
            )
        try:
            resp = httpx.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json={"channel": channel, "text": text},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                return ConnectorData(
                    self.connector_id, "post_message",
                    records=[{"channel": channel, "text": text}],
                    summary=f"Posted to {channel}",
                )
            return ConnectorData(
                self.connector_id, "post_message",
                error=data.get("error", "Post failed"),
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "post_message", error=str(e)
            )
