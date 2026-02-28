"""Twitter/X — brand monitoring, competitor tracking, mentions, and posting."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

_BASE = "https://api.twitter.com/2"


class TwitterClient(BaseConnectorClient):
    """Real Twitter/X API v2 client.

    API docs: https://developer.twitter.com/en/docs/twitter-api
    Auth: Bearer token (App-only) for read endpoints, OAuth 2.0 User
    Context for posting.  This client supports both modes — bearer_token
    is required, oauth_access_token is optional (needed only for tweet
    posting).
    """

    @property
    def connector_id(self) -> str:
        return "twitter_x"

    @property
    def required_credentials(self) -> list[str]:
        return ["bearer_token"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "search_recent",
            "user_tweets",
            "user_mentions",
            "user_info",
            "post_tweet",
        ]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('bearer_token', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        token = credentials.get("bearer_token", "")
        if not token:
            return ConnectionResult(False, "Twitter/X bearer token required")
        try:
            resp = httpx.get(
                f"{_BASE}/users/me",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                user = resp.json().get("data", {})
                return ConnectionResult(
                    True,
                    f"Connected to X as @{user.get('username', '?')}",
                    details={"username": user.get("username", ""), "id": user.get("id", "")},
                )
            if resp.status_code == 403:
                test_resp = httpx.get(
                    f"{_BASE}/tweets/search/recent",
                    headers=self._headers(credentials),
                    params={"query": "test", "max_results": 10},
                    timeout=10,
                )
                if test_resp.status_code == 200:
                    return ConnectionResult(
                        True, "Connected to X (App-only bearer token — search works)"
                    )
                return ConnectionResult(
                    False, f"Bearer token rejected: {test_resp.status_code}"
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        headers = self._headers(credentials)
        handlers = {
            "search_recent": self._search_recent,
            "user_tweets": self._user_tweets,
            "user_mentions": self._user_mentions,
            "user_info": self._user_info,
            "post_tweet": self._post_tweet,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error=f"Unknown data type: {data_type}"
            )
        return handler(headers, credentials, **kwargs)

    def _search_recent(
        self, headers: dict, creds: dict, **kwargs: Any
    ) -> ConnectorData:
        query = kwargs.get("query", "")
        if not query:
            return ConnectorData(
                self.connector_id, "search_recent",
                error="query parameter required for search",
            )
        try:
            params: dict[str, Any] = {
                "query": query,
                "max_results": min(kwargs.get("max_results", 25), 100),
                "tweet.fields": "created_at,public_metrics,author_id,lang",
            }
            resp = httpx.get(
                f"{_BASE}/tweets/search/recent",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "search_recent",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            tweets = []
            for t in data.get("data", []):
                metrics = t.get("public_metrics", {})
                tweets.append({
                    "id": t.get("id", ""),
                    "text": t.get("text", ""),
                    "author_id": t.get("author_id", ""),
                    "created_at": t.get("created_at", ""),
                    "lang": t.get("lang", ""),
                    "retweets": metrics.get("retweet_count", 0),
                    "likes": metrics.get("like_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                })
            meta = data.get("meta", {})
            return ConnectorData(
                self.connector_id, "search_recent", records=tweets,
                summary=f"{meta.get('result_count', len(tweets))} tweets for '{query}'",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "search_recent", error=str(e))

    def _user_tweets(
        self, headers: dict, creds: dict, **kwargs: Any
    ) -> ConnectorData:
        user_id = kwargs.get("user_id", "")
        if not user_id:
            return ConnectorData(
                self.connector_id, "user_tweets",
                error="user_id parameter required",
            )
        try:
            resp = httpx.get(
                f"{_BASE}/users/{user_id}/tweets",
                headers=headers,
                params={
                    "max_results": min(kwargs.get("max_results", 25), 100),
                    "tweet.fields": "created_at,public_metrics",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "user_tweets",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            tweets = [
                {
                    "id": t.get("id", ""),
                    "text": t.get("text", ""),
                    "created_at": t.get("created_at", ""),
                    "likes": t.get("public_metrics", {}).get("like_count", 0),
                    "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
                }
                for t in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "user_tweets", records=tweets,
                summary=f"{len(tweets)} tweets from user {user_id}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "user_tweets", error=str(e))

    def _user_mentions(
        self, headers: dict, creds: dict, **kwargs: Any
    ) -> ConnectorData:
        user_id = kwargs.get("user_id", "")
        if not user_id:
            return ConnectorData(
                self.connector_id, "user_mentions",
                error="user_id parameter required",
            )
        try:
            resp = httpx.get(
                f"{_BASE}/users/{user_id}/mentions",
                headers=headers,
                params={
                    "max_results": min(kwargs.get("max_results", 25), 100),
                    "tweet.fields": "created_at,public_metrics,author_id",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "user_mentions",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            mentions = [
                {
                    "id": t.get("id", ""),
                    "text": t.get("text", ""),
                    "author_id": t.get("author_id", ""),
                    "created_at": t.get("created_at", ""),
                    "likes": t.get("public_metrics", {}).get("like_count", 0),
                    "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
                }
                for t in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "user_mentions", records=mentions,
                summary=f"{len(mentions)} mentions of user {user_id}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "user_mentions", error=str(e))

    def _user_info(
        self, headers: dict, creds: dict, **kwargs: Any
    ) -> ConnectorData:
        username = kwargs.get("username", "")
        if not username:
            return ConnectorData(
                self.connector_id, "user_info",
                error="username parameter required",
            )
        try:
            resp = httpx.get(
                f"{_BASE}/users/by/username/{username}",
                headers=headers,
                params={"user.fields": "public_metrics,description,created_at,verified"},
                timeout=10,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "user_info",
                    error=f"Status {resp.status_code}",
                )
            user = resp.json().get("data", {})
            metrics = user.get("public_metrics", {})
            info = {
                "id": user.get("id", ""),
                "username": user.get("username", ""),
                "name": user.get("name", ""),
                "description": user.get("description", ""),
                "followers": metrics.get("followers_count", 0),
                "following": metrics.get("following_count", 0),
                "tweet_count": metrics.get("tweet_count", 0),
                "verified": user.get("verified", False),
                "created_at": user.get("created_at", ""),
            }
            return ConnectorData(
                self.connector_id, "user_info", records=[info],
                summary=f"@{info['username']}: {info['followers']} followers",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "user_info", error=str(e))

    def _post_tweet(
        self, headers: dict, creds: dict, **kwargs: Any
    ) -> ConnectorData:
        access_token = creds.get("oauth_access_token", "")
        if not access_token:
            return ConnectorData(
                self.connector_id, "post_tweet",
                error="oauth_access_token credential required to post tweets",
            )
        text = kwargs.get("text", "")
        if not text:
            return ConnectorData(
                self.connector_id, "post_tweet",
                error="text parameter required",
            )
        try:
            resp = httpx.post(
                f"{_BASE}/tweets",
                headers={"Authorization": f"Bearer {access_token}",
                         "Content-Type": "application/json"},
                json={"text": text},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                tweet = resp.json().get("data", {})
                return ConnectorData(
                    self.connector_id, "post_tweet",
                    records=[{"tweet_id": tweet.get("id", ""), "text": tweet.get("text", "")}],
                    summary=f"Tweet posted: {tweet.get('id', '')}",
                )
            return ConnectorData(
                self.connector_id, "post_tweet",
                error=f"Status {resp.status_code}: {resp.text[:200]}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "post_tweet", error=str(e))
