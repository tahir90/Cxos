# Integration Layer — Production Readiness Audit

**Date:** 2026-02-28
**Auditor:** Cloud Agent
**Verdict:** NOT production-ready. Multiple critical gaps.

---

## 1. CredentialStore — Credentials are NOT encrypted

**File:** `src/agentic_cxo/integrations/live/base.py`, lines 81–117

### Finding: CRITICAL — Plaintext credentials on disk, no access logging

The `CredentialStore` writes raw JSON to disk:

```python
# base.py:88-93
def save(self, connector_id: str, credentials: dict[str, str]) -> None:
    path = CREDS_DIR / f"{connector_id}.json"
    path.write_text(json.dumps({
        "connector_id": connector_id,
        "credentials": credentials,   # <-- PLAINTEXT
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
```

API keys, OAuth tokens, and secrets are stored as human-readable JSON files under `.cxo_data/credentials/`. Anyone with filesystem access can read them.

**An `EncryptedStore` class exists** at `src/agentic_cxo/infrastructure/encryption.py` (lines 42–71) that uses Fernet symmetric encryption with a master key. It is completely functional. But `CredentialStore` does not use it. The two classes are entirely disconnected. The base.py docstring on line 9 even says "encrypted in production" — this is aspirational documentation, not reality.

**No access logging.** The `save` method logs "Credentials saved for X" (line 94), but `load` (lines 96–104) has zero logging. There is no audit trail of who/what accessed credentials, when, or how often. A compromised connector silently exfiltrating stored credentials would leave no trace.

**No file permissions.** The credential JSON files are created with default umask permissions. Compare with `encryption.py` line 37 which correctly does `key_path.chmod(0o600)` for the master key — the actual credential files don't get this treatment.

### Remediation needed:
- Wire `CredentialStore` to use `EncryptedStore` instead of raw `json.dumps`
- Add access logging on every `load()` call
- Set `0o600` permissions on credential files
- Add credential rotation/expiry tracking

---

## 2. OAuth Token Refresh — NOT implemented

**File:** `src/agentic_cxo/integrations/oauth.py`, lines 165–304

### Finding: CRITICAL — Tokens will silently expire and break all connected services

The `OAuthManager.handle_callback` method (lines 227–304) correctly stores the `refresh_token` from the OAuth response:

```python
# oauth.py:272-277
creds = {
    "access_token": access_token,
    "refresh_token": data.get("refresh_token", ""),  # stored but never used
    "token_type": data.get("token_type", "bearer"),
    "scope": data.get("scope", ""),
}
```

But there is **zero refresh logic anywhere in the codebase**. Searching for `refresh_token` usage beyond this storage point yields nothing. There is:
- No `refresh_access_token()` method on `OAuthManager`
- No token expiry tracking (no `expires_at` or `expires_in` is saved)
- No automatic refresh before API calls in any connector client
- No refresh wiring in `ConnectorManager.fetch_data()` (manager.py:159–181)

**Impact:** Google tokens expire in 1 hour. Microsoft tokens expire in 1 hour. Slack tokens don't expire but most others do. After initial OAuth connection, every Google/Microsoft/Salesforce/HubSpot connector will silently fail within 60 minutes. The user will see vague "API call failed" errors with no indication that re-authentication is needed.

**Not wired into any connector:** The connector clients (e.g., `mailchimp_client.py`, `twitter_client.py`) receive raw `credentials: dict[str, str]` and call the API directly. None of them check token freshness or attempt refresh.

### Remediation needed:
- Store `expires_at` alongside tokens
- Implement `refresh_access_token(provider_id)` on `OAuthManager`
- Call refresh proactively in `ConnectorManager.fetch_data()` before delegating to client
- Handle refresh failures gracefully (re-prompt for auth)

---

## 3. ConnectorManager — No error recovery, no circuit breaking, no health checks

**File:** `src/agentic_cxo/integrations/live/manager.py`, lines 107–205

### Finding: HIGH — Bare-minimum manager with zero resilience

The `ConnectorManager` is a thin passthrough. The `fetch_data` method (lines 159–181):

```python
def fetch_data(self, connector_id, data_type, **kwargs):
    client = self.clients.get(connector_id)
    if not client:
        return ConnectorData(...)  # error
    creds = self.cred_store.load(connector_id)
    if not creds:
        return ConnectorData(...)  # error
    return client.fetch(creds, data_type, **kwargs)  # raw delegation, no protection
```

What's missing:

| Feature | Status |
|---------|--------|
| **Retry with backoff** | Not implemented. A transient 503 kills the request permanently. |
| **Circuit breaker** | Not implemented. A down API will be hammered on every user request. |
| **Health checking** | Not implemented. `get_status()` (lines 183–196) only checks if credentials exist on disk, not if the API is actually reachable. |
| **Timeout enforcement** | Delegated to individual clients. Some use `timeout=10`, some don't specify. No global timeout policy. |
| **Error normalization** | Each client handles errors differently. Some return `ConnectorData(error=...)`, some raise exceptions. No consistent error contract. |
| **Connection pooling** | Not implemented. Each `fetch()` call creates a new `httpx.get()` — no connection reuse. |
| **Rate limit awareness** | Not implemented. No tracking of API rate limits, no backoff on 429 responses. |
| **Metrics/observability** | One `logger.info` on successful connect. No metrics on latency, error rates, or throughput. |

### Remediation needed:
- Add retry decorator with exponential backoff for transient failures
- Implement circuit breaker (open after N consecutive failures, half-open after cooldown)
- Add periodic health checks that actually call `test_connection()`
- Normalize all client errors into a consistent `ConnectorData.error` format
- Add connection pooling via `httpx.Client` sessions
- Track and respect per-API rate limits

---

## 4. API Server — Connector endpoints are UNPROTECTED

**File:** `src/agentic_cxo/api/server.py`, lines 572–749

### Finding: CRITICAL — No auth on connector endpoints, no rate limiting, no CORS policy

#### Authentication gaps

The connector endpoints are a mixed bag. Most are **completely unprotected**:

| Endpoint | Auth? |
|----------|-------|
| `GET /connectors` (line 575) | **NO** — `category` param only, no `Depends(get_current_user)` |
| `GET /connectors/summary` (line 589) | **NO** |
| `GET /connectors/by-agent/{role}` (line 594) | **NO** |
| `GET /connect/{id}/setup` (line 658) | **NO** |
| `POST /connect/{id}` (line 684) | **NO** — accepts credentials, no auth |
| `POST /connect/{id}/disconnect` (line 698) | **NO** |
| `GET /connect/{id}/fetch/{type}` (line 704) | **NO** — fetches live data, no auth |
| `GET /connect/status` (line 747) | **NO** |
| `GET /oauth/providers` (line 879) | **NO** |
| `GET /oauth/start/{id}` (line 885) | YES — `Depends(get_current_user)` |
| `GET /oauth/callback/{id}` (line 904) | **NO** — OAuth callbacks can't require auth |

The `POST /connect/{connector_id}` endpoint (line 684) accepts raw API keys in the request body with **zero authentication**. An attacker can connect arbitrary credentials, overwrite existing ones, or fetch live data from connected accounts — all without logging in.

#### Rate limiting

**None.** There is no rate limiting middleware anywhere in the codebase. Every endpoint can be hammered indefinitely. The `POST /connect/{id}` endpoint is particularly dangerous — it makes external API calls (`test_connection`) on every request, making it a potential amplification vector.

#### CORS

**No CORS middleware configured.** The FastAPI app (line 73) has no `CORSMiddleware`. This means:
- In development: browser-based requests from other origins will be blocked by default
- In production: no explicit allow/deny policy exists

#### Hardcoded JWT secret

`src/agentic_cxo/infrastructure/auth.py` line 22:
```python
SECRET_KEY = "cxo-secret-change-in-production-use-env-var"
```

The JWT signing key is a hardcoded string. The comment says "change in production" but there is no mechanism to override it via environment variable. Anyone who reads the source code can forge valid JWT tokens.

### Remediation needed:
- Add `Depends(get_current_user)` to ALL connector endpoints
- Add rate limiting middleware (e.g., `slowapi`)
- Configure `CORSMiddleware` with explicit allowed origins
- Move JWT secret to environment variable with startup validation

---

## 5. Tests — Shallow happy-path coverage only

**File:** `tests/test_cmo_connectors.py` (954 lines)

### Finding: MEDIUM-HIGH — Tests verify structure, not resilience

#### What the tests DO cover:
- Connector ID, required credentials, and data type assertions (good)
- Missing credential validation (good)
- Missing required parameter validation (good)
- Happy-path fetch with mocked 200 responses (adequate)
- Manager registration and status (good)

#### What the tests DO NOT cover:

| Gap | Impact |
|-----|--------|
| **HTTP 500 responses** | Zero tests. Every mock returns `status_code = 200`. No test verifies behavior when an API returns a server error. |
| **Network timeouts** | Zero tests. No mock raises `httpx.TimeoutException` or `httpx.ConnectError`. |
| **HTTP 429 (rate limit)** | Zero tests. No test verifies backoff or error messaging on rate limits. |
| **HTTP 401/403 (expired token)** | Zero tests. No test verifies behavior when credentials are revoked or expired. |
| **Malformed JSON responses** | Zero tests. Every mock `.json()` returns well-formed dicts. No test for truncated JSON, HTML error pages, or empty responses. |
| **Request construction** | Zero assertions on the actual HTTP calls. Tests never verify the URL, headers, query parameters, or auth sent to the API. `mock_get` is asserted implicitly by return value, but `mock_get.assert_called_once_with(url, headers=..., params=...)` is never used. |
| **Pagination** | Zero tests. All mocks return single-page responses. No test verifies correct handling of paginated APIs. |
| **Concurrent access** | Zero tests. No test verifies thread-safety of `CredentialStore` or `ConnectorManager`. |
| **Credential store cleanup** | The `clean_data` fixture (lines 20–24) runs after each test but only cleans up on teardown. If a test fails mid-write, stale files may persist. |

#### Specific example — Mailchimp `test_test_connection_success` (lines 81–94):

```python
@patch("agentic_cxo.integrations.live.mailchimp_client.httpx.get")
def test_test_connection_success(self, mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"account_name": "TestCo", ...}
    mock_get.return_value = mock_resp
    # ...
```

This never asserts:
- That `httpx.get` was called with the correct URL (e.g., `https://us21.api.mailchimp.com/3.0/`)
- That Basic auth was passed correctly
- That the timeout parameter was set
- What happens when `status_code = 401` (bad API key)
- What happens when `resp.json()` raises `json.JSONDecodeError`

### Remediation needed:
- Add error response tests for every connector (401, 403, 429, 500, timeout)
- Add request construction assertions (`assert_called_with`)
- Add malformed response tests (invalid JSON, empty body, HTML error pages)
- Add pagination tests for APIs that support it

---

## 6. CMO Agent Wiring — Connectors are COMPLETELY ISOLATED from reasoning

### Finding: CRITICAL — The CMO agent cannot use connectors during reasoning

The `AgentCMO` class (`src/agentic_cxo/agents/cmo.py`, lines 16–33) is a 17-line stub:

```python
@dataclass
class AgentCMO(BaseAgent):
    role: str = "CMO"

    def system_prompt(self) -> str:
        return "You are an AI Chief Marketing Officer..."
```

It inherits from `BaseAgent` (`src/agentic_cxo/agents/base.py`), which has a `reason()` method (lines 68–86) that:
1. Queries the `ContextVault` for text chunks
2. Sends them to the LLM for action planning
3. Routes actions through risk assessment and approval

**At no point does any agent interact with `ConnectorManager` or any live connector.** The reasoning loop has zero awareness that connectors exist:

- `BaseAgent` has no reference to `ConnectorManager`
- `AgentCMO` has no reference to `ConnectorManager`
- The `Cockpit` orchestrator (`src/agentic_cxo/orchestrator.py`) creates agents but never injects a `ConnectorManager`
- `CoFounderAgent` (`src/agentic_cxo/conversation/agent.py`) imports tools but not `ConnectorManager`

The `self_awareness.py` module (lines 17–22) does accept a `ConnectorManager` to list connected integrations in the system prompt, but this is purely descriptive text — it tells the LLM "these connectors are connected" but provides no mechanism for the LLM to actually invoke them.

**The architecture looks like this:**

```
User → API Server → CoFounderAgent → LLM (text generation)
                  ↓
              ConnectorManager → Live APIs (separate, disconnected path)
```

The user can manually hit `GET /connect/mailchimp/fetch/campaigns` to get data, but the CMO agent's reasoning loop never does this. When the CMO says "I'll analyze your campaign performance," it's generating text based on whatever was previously ingested into the ContextVault — not pulling live data from Mailchimp, Google Ads, or any other connected service.

**What's needed:** The connectors need to be exposed as tools in the LLM tool-calling framework. The `ToolRegistry` (`src/agentic_cxo/tools/framework.py`) already exists and is used for web search, cost analysis, etc. Connector data fetching should be registered as tools so the LLM can invoke them during reasoning.

---

## Summary Scorecard

| Area | Rating | Status |
|------|--------|--------|
| Credential encryption | 🔴 FAIL | `EncryptedStore` exists but is not wired to `CredentialStore` |
| Credential access logging | 🔴 FAIL | No audit trail on credential reads |
| OAuth token refresh | 🔴 FAIL | `refresh_token` stored but never used; tokens expire silently |
| Error recovery / circuit breaking | 🔴 FAIL | No retries, no circuit breaker, no health checks |
| API auth on connector endpoints | 🔴 FAIL | 8 of 10 connector endpoints have no authentication |
| Rate limiting | 🔴 FAIL | None anywhere |
| CORS policy | 🔴 FAIL | No `CORSMiddleware` configured |
| JWT secret management | 🔴 FAIL | Hardcoded in source code |
| Test coverage — happy path | 🟡 PARTIAL | Good structure tests, adequate happy-path mocks |
| Test coverage — error paths | 🔴 FAIL | Zero tests for 401/429/500/timeout/malformed |
| Test coverage — request verification | 🔴 FAIL | Never asserts correct URLs/headers/params |
| Agent-connector integration | 🔴 FAIL | Connectors exist but no agent can invoke them during reasoning |

**Bottom line:** The integration layer has good foundational abstractions (base classes, registries, data models) but is a prototype, not production code. The connector clients can make API calls, but they are isolated islands — not encrypted, not refreshed, not resilient, not auth-protected, not tested for failure, and not wired into the agent reasoning loop that is the entire point of the product.
