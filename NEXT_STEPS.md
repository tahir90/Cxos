# Agentic CXO — Next Steps

*Audit performed 2026-02-28 against branches `cursor/agentic-cxo-context-pipeline-f072` and `cursor/development-environment-setup-62ce`.*

This document captures the current state of every major subsystem and defines a prioritized implementation roadmap for what to build next.

---

## Current State Summary

| Area | Status | Grade | Notes |
|---|---|---|---|
| Agent Base + 6 CXO Agents | Fully functional | A | Clean inheritance; LLM + rule-based fallback |
| Conversation Agent | Fully functional | A+ | Most complete module — onboarding, routing, tools, memory, sessions |
| 26 Live Integration Connectors | Fully functional | A | Real API calls to Stripe, Slack, HubSpot, Gmail, GitHub, etc. |
| Scenario Engine (14 workflows) | Fully functional | A | Topological DAG resolution, context threading, risk gating |
| Action Executor | Functional | A- | Real email/Slack/webhook; task + meeting simulated |
| Orchestrator (Cockpit) | Functional | A- | Keyword routing, no semantic classification |
| Risk Assessor | Functional | A- | LLM + rule-based dual mode |
| Context Vault (ChromaDB) | Functional | A | Semantic storage and retrieval |
| SSE Streaming | Functional | A- | Works for `/chat/stream` |
| API Server (40+ endpoints) | Functional | B+ | Missing CORS, rate limiting, proper error codes |
| Authentication (JWT) | Functional | B+ | JWT + bcrypt, but single-tenant |
| Approval Gate | Functional | B | **In-memory only — data lost on restart** |
| Notifications | In-app only | C+ | No email/Slack delivery despite docstring promises |
| Database | Schema exists | C+ | SQLAlchemy tables created, but modules use JSON files |
| Billing | Structure only | C | Plan tiers defined, no Stripe integration |

### Test Suite

- **315 passing tests** across 22 test files
- Almost entirely unit tests with `use_llm=False`
- **Zero integration tests**, zero end-to-end tests
- Key untested modules: `scenarios/analyst.py` (770 lines), `integrations/oauth.py` (300 lines), all 4 original agent files, `conversation/product_knowledge.py`, 13 live connector clients

---

## Priority 1 — Production Blockers

These issues must be resolved before any production deployment.

### 1.1 Persist the Approval Gate

**File:** `src/agentic_cxo/guardrails/approval.py`

The `ApprovalGate` stores pending approvals in a Python dict. Server restart = all pending approvals lost. The `ActionQueue` in `executor.py` already has JSON persistence — the approval gate needs the same treatment, or better, should use the SQLAlchemy database.

**Work:**
- Add JSON or SQLite persistence to `ApprovalGate`
- Add timeout/escalation for stale approvals (actions stuck indefinitely)
- Add notification trigger when new approval is needed
- Test: approval survives server restart

### 1.2 Add CORS Middleware

**File:** `src/agentic_cxo/api/server.py`

No CORS middleware is configured. Any browser-based client on a different origin will fail. This is a one-liner with FastAPI's `CORSMiddleware`, but it needs to be added with configurable allowed origins.

**Work:**
- Add `CORSMiddleware` with configurable `ALLOWED_ORIGINS` env var
- Default to `["*"]` in development, restrict in production
- Test: cross-origin request succeeds

### 1.3 Encrypt Stored Credentials

**File:** `src/agentic_cxo/integrations/live/manager.py` (`CredentialStore`)

All 26 connector credentials (API keys, OAuth tokens) are stored as plaintext JSON on disk. The project already has `cryptography` as a dependency and `src/agentic_cxo/infrastructure/encryption.py` exists.

**Work:**
- Wire `EncryptionManager` into `CredentialStore` so credentials are encrypted at rest
- Add key rotation support
- Test: credentials are unreadable without decryption key

### 1.4 Fix API Error Handling

**File:** `src/agentic_cxo/api/server.py`

The `/chat` endpoint catches all exceptions and returns HTTP 200 with an error message in the body. Other endpoints have similar patterns. This breaks standard API conventions.

**Work:**
- Return proper HTTP status codes (400, 401, 403, 500) for errors
- Add global exception handler middleware
- Add input sanitization beyond Pydantic validation
- Test: error responses return correct HTTP codes

---

## Priority 2 — Core Feature Gaps

These features are partially built and need completion.

### 2.1 Migrate from JSON Files to Database

**Files:** Multiple modules in `actions/`, `infrastructure/`, `integrations/`

The SQLAlchemy schema in `infrastructure/database.py` defines 7 tables, and `init_db()` creates them at startup. But most modules still persist to JSON files in `.cxo_data/`:
- `ActionQueue` → `action_queue.json`
- `DecisionLog` → `decisions.json`
- `GoalTracker` → `goals.json`
- `BillingManager` → `billing.json`
- `NotificationManager` → `notifications.json`
- `CredentialStore` → `credentials.json`
- `UsageTracker` → `usage.json`

**Work:**
- Migrate each module from JSON file I/O to SQLAlchemy ORM operations
- Add proper database migrations (Alembic)
- Ensure all reads/writes are transactional
- Test: data persists across restarts via database, not JSON

### 2.2 Wire Stripe Billing

**Files:** `infrastructure/billing.py`, `integrations/live/stripe_client.py`

The `BillingManager` has plan tiers (Free, Starter $49/mo, Pro $199/mo, Enterprise) and subscription CRUD, but `stripe_customer_id` and `stripe_subscription_id` fields are never populated. The live `StripeConnector` already has real Stripe API access.

**Work:**
- Create Stripe Checkout sessions for subscription creation
- Handle Stripe webhooks for payment success/failure, subscription changes, cancellation
- Enforce plan limits based on subscription status
- Wire `UsageTracker` to enforce monthly limits per plan tier
- Test: complete signup-to-payment flow

### 2.3 Add Email and Slack Notification Delivery

**File:** `infrastructure/notifications.py`

`NotificationManager.notify()` stores in-app notifications but doesn't actually deliver via email or Slack, despite the docstring promising both channels.

**Work:**
- Add email delivery via SMTP (reuse the `ActionExecutor.send_email` logic)
- Add Slack delivery via webhook (reuse the `ActionExecutor.post_slack` logic)
- Add per-user notification preferences (which channels, which notification types)
- Add WebSocket push for real-time browser delivery
- Test: notification triggers email/Slack delivery

### 2.4 Wire Live Connectors into Agent Reasoning

**Files:** `agents/base.py`, `orchestrator.py`

Agents reason via LLM prompt + vault context only. They cannot query live data from Stripe, HubSpot, Slack, etc. during their reasoning loop. The connectors exist and work — they just aren't available to agents.

**Work:**
- Expose connected integrations as agent tools (e.g., CFO can call `stripe.fetch("mrr")`)
- Add a `ToolRegistry` that agents can query for available tools based on connected integrations
- Let agents dynamically decide which tools to call during reasoning
- Thread live data into context alongside vault results
- Test: agent reasoning includes live connector data

### 2.5 Connect Action Executor to Conversation

**Files:** `conversation/agent.py`, `actions/executor.py`

The `CoFounderAgent` initializes an `action_queue` but the `chat()` method never creates `ExecutableAction` objects. When the conversation agent recommends "let's send a reminder email to that vendor," it should create an action.

**Work:**
- Parse action-intent from LLM responses in `chat()`
- Create `ExecutableAction` objects with proper risk assessment
- Route through approval gate for high-risk actions
- Confirm execution status back to the user in the conversation
- Test: conversation leads to queued/executed action

---

## Priority 3 — Robustness and Scale

### 3.1 Multi-Tenant Data Isolation

**Files:** `api/server.py`, `infrastructure/tenant.py`

Auth exists (JWT + bcrypt) but all API state is global. User A can see User B's data. The `tenant.py` module exists but isn't wired into the API.

**Work:**
- Add tenant context middleware that extracts user/team from JWT
- Scope all database queries, vault queries, and file operations to tenant
- Add per-tenant data directories or database schemas
- Test: User A cannot access User B's data

### 3.2 OAuth Token Refresh

**Files:** `integrations/oauth.py`, `integrations/live/*.py`

The `OAuthManager` handles the initial OAuth2 authorization flow, but token refresh is not wired into the connector clients. Tokens expire (typically 1 hour for Google) and connectors will silently fail.

**Work:**
- Add `refresh_token()` method to `OAuthManager`
- Wire refresh into every OAuth-based connector's `fetch()` method
- Store refresh tokens securely (encrypted, per 1.3)
- Test: connector auto-refreshes expired token

### 3.3 Add Rate Limiting

**File:** `src/agentic_cxo/api/server.py`

No rate limiting on any endpoint. A single client can overwhelm the server.

**Work:**
- Add rate limiting middleware (e.g., `slowapi` or custom)
- Configure per-endpoint limits (e.g., `/chat` at 30 req/min, `/scenarios/*/run` at 5 req/min)
- Rate limit by API key/JWT identity, not just IP
- Return proper 429 responses
- Test: rate limit triggers correctly

### 3.4 Async Orchestration

**File:** `orchestrator.py`

`Cockpit.dispatch()` runs agents synchronously and serially. If 3 agents are routed for one objective, they execute one after another.

**Work:**
- Convert `dispatch()` to async with `asyncio.gather()` for parallel agent execution
- Add a priority queue for objectives
- Add cancellation support for long-running agent tasks
- Test: multiple agents run concurrently

### 3.5 Agent-to-Agent Communication

**Files:** `agents/base.py`, `orchestrator.py`

Agents operate independently. The CFO cannot ask the CLO to review a contract it found, and the CMO cannot ask the CSO for pipeline data.

**Work:**
- Add an inter-agent message protocol (request/response)
- Allow agents to delegate sub-tasks to other agents via the orchestrator
- Add result aggregation for multi-agent objectives
- Add conflict resolution when agents disagree
- Test: CFO delegates legal review to CLO and receives result

---

## Priority 4 — Test Coverage

### 4.1 Critical Untested Modules

| Module | Lines | Risk | What to Test |
|---|---|---|---|
| `scenarios/analyst.py` | ~770 | High | All output generation paths, edge cases, data formatting |
| `integrations/oauth.py` | ~300 | High | Auth flow, token exchange, error handling, CSRF protection |
| `agents/cfo.py`, `clo.py`, `cmo.py`, `coo.py` | ~60 each | Medium | System prompt content, domain-specific keyword coverage |
| `conversation/product_knowledge.py` | ~320 | Medium | Query classification, capability matching, response quality |
| `conversation/sessions.py` | ~150 | Medium | Session isolation, switching, archiving |

### 4.2 Integration Tests Needed

- API endpoint integration tests (error paths, auth failures, malformed input)
- Full scenario execution with mock LLM responses
- Connector `fetch()` with mocked HTTP responses (verify request construction and response parsing)
- Database persistence round-trip tests

### 4.3 End-to-End Tests Needed

- Complete user journey: signup → seed data → ask question → run scenario → approve action → verify result
- OAuth flow: start → callback → store token → fetch data
- Document lifecycle: upload → refine → store → query → return in chat

---

## Priority 5 — Developer Experience and Deployment

### 5.1 Migrate to FastAPI Lifespan

**File:** `api/server.py`

Replace deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` with the modern `lifespan` context manager pattern.

### 5.2 Add Alembic Database Migrations

Once modules migrate from JSON to database, add Alembic for schema migrations so database changes are versioned and reversible.

### 5.3 Add CI/CD Pipeline

No `.github/workflows/` exists. Add:
- Lint check (`ruff check src/ tests/`)
- Test suite (`pytest tests/ -v`)
- Build check (`pip install -e ".[dev]"`)
- Docker build verification

### 5.4 Add WebSocket Endpoint

Replace or supplement SSE streaming with WebSocket support for real-time bidirectional communication in the chat interface.

### 5.5 Add Pagination to Connectors

Most connectors are limited to 50-100 records. Add proper pagination support so large datasets (thousands of Stripe customers, HubSpot contacts, etc.) can be fully retrieved.

---

## Recommended Implementation Order

For a single developer, the recommended sequence is:

```
Week 1:  1.1 (Persist Approval Gate)
         1.2 (CORS Middleware)
         1.3 (Encrypt Credentials)
         1.4 (Fix Error Handling)

Week 2:  2.1 (JSON → Database Migration)
         5.1 (FastAPI Lifespan)
         5.3 (CI/CD Pipeline)

Week 3:  2.3 (Email/Slack Notifications)
         2.5 (Conversation → Action Executor)
         3.2 (OAuth Token Refresh)

Week 4:  2.4 (Connectors → Agent Reasoning)
         3.1 (Multi-Tenant Isolation)
         3.3 (Rate Limiting)

Week 5:  2.2 (Stripe Billing)
         3.4 (Async Orchestration)

Week 6:  4.1-4.3 (Test Coverage)
         3.5 (Agent-to-Agent Communication)
         5.2 (Alembic Migrations)
```

This sequence prioritizes security fixes first, then infrastructure correctness, then feature gaps, then scale.
