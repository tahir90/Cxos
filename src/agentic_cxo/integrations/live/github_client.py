"""Real GitHub + Bitbucket integration — repos, PRs, activity, contributors."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

GH_API = "https://api.github.com"
BB_API = "https://api.bitbucket.org/2.0"


class GitHubClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "github"

    @property
    def required_credentials(self) -> list[str]:
        return ["token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["repos", "pull_requests", "contributors", "activity", "issues"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('token', '')}",
            "Accept": "application/vnd.github+json",
        }

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("token"):
            return ConnectionResult(False, "GitHub token is required")
        try:
            resp = httpx.get(
                f"{GH_API}/user",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True,
                    f"Connected as {data.get('login', '?')} "
                    f"({data.get('name', '')})",
                    details={
                        "login": data.get("login"),
                        "repos": data.get("public_repos", 0),
                    },
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        h = self._headers(credentials)
        org = kwargs.get("org", "")

        if data_type == "repos":
            return self._fetch_repos(h, org)
        elif data_type == "pull_requests":
            return self._fetch_prs(h, kwargs.get("repo", ""))
        elif data_type == "contributors":
            return self._fetch_contributors(h, kwargs.get("repo", ""))
        elif data_type == "activity":
            return self._fetch_activity(h, org)
        elif data_type == "issues":
            return self._fetch_issues(h, kwargs.get("repo", ""))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_repos(self, headers: dict, org: str) -> ConnectorData:
        try:
            url = f"{GH_API}/orgs/{org}/repos" if org else f"{GH_API}/user/repos"
            resp = httpx.get(
                url, headers=headers,
                params={"sort": "updated", "per_page": 50},
                timeout=10,
            )
            repos = [
                {
                    "name": r["full_name"],
                    "language": r.get("language", ""),
                    "stars": r.get("stargazers_count", 0),
                    "open_issues": r.get("open_issues_count", 0),
                    "updated": r.get("updated_at", ""),
                    "private": r.get("private", False),
                }
                for r in resp.json() if isinstance(r, dict)
            ]
            return ConnectorData(
                self.connector_id, "repos",
                records=repos,
                summary=f"{len(repos)} repositories",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "repos", error=str(e))

    def _fetch_prs(self, headers: dict, repo: str) -> ConnectorData:
        if not repo:
            return ConnectorData(
                self.connector_id, "pull_requests",
                error="repo required (owner/repo)",
            )
        try:
            resp = httpx.get(
                f"{GH_API}/repos/{repo}/pulls",
                headers=headers,
                params={"state": "all", "per_page": 30, "sort": "updated"},
                timeout=10,
            )
            prs = [
                {
                    "number": p["number"],
                    "title": p["title"],
                    "state": p["state"],
                    "author": p.get("user", {}).get("login", ""),
                    "created": p.get("created_at", ""),
                    "merged": p.get("merged_at"),
                }
                for p in resp.json() if isinstance(p, dict)
            ]
            open_count = sum(1 for p in prs if p["state"] == "open")
            return ConnectorData(
                self.connector_id, "pull_requests",
                records=prs,
                summary=f"{len(prs)} PRs ({open_count} open)",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "pull_requests", error=str(e)
            )

    def _fetch_contributors(
        self, headers: dict, repo: str
    ) -> ConnectorData:
        if not repo:
            return ConnectorData(
                self.connector_id, "contributors",
                error="repo required",
            )
        try:
            resp = httpx.get(
                f"{GH_API}/repos/{repo}/contributors",
                headers=headers,
                params={"per_page": 50},
                timeout=10,
            )
            contribs = [
                {
                    "login": c["login"],
                    "contributions": c.get("contributions", 0),
                    "avatar": c.get("avatar_url", ""),
                }
                for c in resp.json() if isinstance(c, dict)
            ]
            return ConnectorData(
                self.connector_id, "contributors",
                records=contribs,
                summary=f"{len(contribs)} contributors",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "contributors", error=str(e)
            )

    def _fetch_activity(self, headers: dict, org: str) -> ConnectorData:
        try:
            url = (
                f"{GH_API}/orgs/{org}/events" if org
                else f"{GH_API}/events"
            )
            resp = httpx.get(
                url, headers=headers,
                params={"per_page": 30},
                timeout=10,
            )
            events = [
                {
                    "type": e.get("type", ""),
                    "actor": e.get("actor", {}).get("login", ""),
                    "repo": e.get("repo", {}).get("name", ""),
                    "created": e.get("created_at", ""),
                }
                for e in resp.json() if isinstance(e, dict)
            ]
            return ConnectorData(
                self.connector_id, "activity",
                records=events,
                summary=f"{len(events)} recent events",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "activity", error=str(e)
            )

    def _fetch_issues(self, headers: dict, repo: str) -> ConnectorData:
        if not repo:
            return ConnectorData(
                self.connector_id, "issues", error="repo required"
            )
        try:
            resp = httpx.get(
                f"{GH_API}/repos/{repo}/issues",
                headers=headers,
                params={"state": "open", "per_page": 30},
                timeout=10,
            )
            issues = [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "state": i["state"],
                    "labels": [lb["name"] for lb in i.get("labels", [])],
                    "assignee": (i.get("assignee") or {}).get("login", ""),
                    "created": i.get("created_at", ""),
                }
                for i in resp.json()
                if isinstance(i, dict) and "pull_request" not in i
            ]
            return ConnectorData(
                self.connector_id, "issues",
                records=issues,
                summary=f"{len(issues)} open issues",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "issues", error=str(e)
            )


class BitbucketClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "bitbucket"

    @property
    def required_credentials(self) -> list[str]:
        return ["username", "app_password"]

    @property
    def available_data_types(self) -> list[str]:
        return ["repos", "pull_requests", "pipelines"]

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (
            creds.get("username", ""),
            creds.get("app_password", ""),
        )

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("username") or not credentials.get("app_password"):
            return ConnectionResult(
                False, "Username and app password required"
            )
        try:
            resp = httpx.get(
                f"{BB_API}/user",
                auth=self._auth(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True,
                    f"Connected as {data.get('display_name', '?')}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        auth = self._auth(credentials)
        workspace = kwargs.get("workspace", credentials.get("username", ""))

        if data_type == "repos":
            return self._fetch_repos(auth, workspace)
        elif data_type == "pull_requests":
            return self._fetch_prs(auth, kwargs.get("repo", ""))
        elif data_type == "pipelines":
            return self._fetch_pipelines(auth, kwargs.get("repo", ""))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_repos(
        self, auth: tuple, workspace: str
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{BB_API}/repositories/{workspace}",
                auth=auth,
                params={"sort": "-updated_on", "pagelen": 50},
                timeout=10,
            )
            data = resp.json()
            repos = [
                {
                    "name": r.get("full_name", ""),
                    "language": r.get("language", ""),
                    "updated": r.get("updated_on", ""),
                    "is_private": r.get("is_private", False),
                }
                for r in data.get("values", [])
            ]
            return ConnectorData(
                self.connector_id, "repos",
                records=repos,
                summary=f"{len(repos)} repositories",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "repos", error=str(e))

    def _fetch_prs(self, auth: tuple, repo: str) -> ConnectorData:
        if not repo:
            return ConnectorData(
                self.connector_id, "pull_requests",
                error="repo required (workspace/repo)",
            )
        try:
            resp = httpx.get(
                f"{BB_API}/repositories/{repo}/pullrequests",
                auth=auth,
                params={"state": "OPEN", "pagelen": 30},
                timeout=10,
            )
            data = resp.json()
            prs = [
                {
                    "id": p.get("id"),
                    "title": p.get("title", ""),
                    "state": p.get("state", ""),
                    "author": p.get("author", {}).get(
                        "display_name", ""
                    ),
                    "created": p.get("created_on", ""),
                }
                for p in data.get("values", [])
            ]
            return ConnectorData(
                self.connector_id, "pull_requests",
                records=prs,
                summary=f"{len(prs)} open PRs",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "pull_requests", error=str(e)
            )

    def _fetch_pipelines(self, auth: tuple, repo: str) -> ConnectorData:
        if not repo:
            return ConnectorData(
                self.connector_id, "pipelines",
                error="repo required",
            )
        try:
            resp = httpx.get(
                f"{BB_API}/repositories/{repo}/pipelines/",
                auth=auth,
                params={"sort": "-created_on", "pagelen": 20},
                timeout=10,
            )
            data = resp.json()
            pipelines = [
                {
                    "uuid": p.get("uuid", ""),
                    "state": (
                        p.get("state", {}).get("name", "")
                    ),
                    "result": (
                        p.get("state", {}).get("result", {})
                        .get("name", "")
                    ),
                    "created": p.get("created_on", ""),
                    "duration": p.get("duration_in_seconds", 0),
                }
                for p in data.get("values", [])
            ]
            return ConnectorData(
                self.connector_id, "pipelines",
                records=pipelines,
                summary=f"{len(pipelines)} recent pipelines",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "pipelines", error=str(e)
            )
