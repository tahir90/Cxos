# Agentic CXO

**AI-driven C-suite agents with modular context management.**

Agentic CXO turns raw business documents into high-density, structured knowledge and routes business objectives to specialized AI agents (CFO, COO, CMO, CLO, CHRO, CSO) that reason, plan, and act — with human-in-the-loop guardrails. Includes 14 pre-built multi-step business scenarios.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       THE COCKPIT (Orchestrator)                     │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│  │ AI CFO │ │ AI COO │ │ AI CMO │ │ AI CLO │ │AI CHRO │ │ AI CSO │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ │
│      └──────────┴──────────┴─────┬────┴──────────┴──────────┘      │
│                                  │                                   │
│               ┌──────────────────▼───────────────────┐              │
│               │  SCENARIO ENGINE (14 Workflows)       │              │
│               │  Multi-step, dependency-resolved,     │              │
│               │  context-threaded execution            │              │
│               └──────────────────┬───────────────────┘              │
│                                  │                                   │
│                         ┌────────▼────────┐                         │
│                         │  CONTEXT VAULT  │  (ChromaDB)              │
│                         └────────┬────────┘                         │
│                                  │                                   │
│               ┌──────────────────┴───────────────────┐              │
│               │     CONTEXT REFINERY PIPELINE         │              │
│               │  1. Semantic Chunker                  │              │
│               │  2. Metadata Enricher                 │              │
│               │  3. Recursive Summarizer              │              │
│               └──────────────────────────────────────┘              │
│                                                                      │
│  ┌──────────────────────────────────────────────────────┐           │
│  │                   GUARDRAILS                          │           │
│  │  Risk Assessor → Approval Gate → Human Pilot          │           │
│  └──────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────┘
```

## Agentic CXO Agents

| Agent | Role | Specialization |
|---|---|---|
| **AI CFO** | Finance & Risk | Expense auditing, tax strategy, cash flow, collections |
| **AI COO** | Operations | Supply chain, vendor management, logistics |
| **AI CMO** | Growth & Brand | Campaigns, churn prevention, localization, viral response |
| **AI CLO** | Legal & Compliance | Contract scanning, IP defense, regulatory audits |
| **AI CHRO** | People & Culture | Recruiting, culture health, automated onboarding |
| **AI CSO** | Sales & Revenue | Deal recovery, pipeline optimization, re-engagement |

## 14 Pre-Built Business Scenarios

Each scenario is a multi-step workflow with dependency resolution, context threading between steps, risk assessment, and human-in-the-loop guardrails.

### CFO Scenarios (Finance)

| # | Scenario | What It Does |
|---|---|---|
| 1 | **The Cash-Flow Guardian** | Detects expense spikes → audits vendors for duplicate billing → re-forecasts runway with budget cuts |
| 2 | **The Tax Strategist** | Scans comms for R&D keywords → cross-refs payroll → generates IRS-compliant R&D Tax Credit report |
| 3 | **The Collections Enforcer** | Flags overdue invoices → drafts escalating reminders → offers VIP clients early-bird discounts |

### CMO Scenarios (Marketing)

| # | Scenario | What It Does |
|---|---|---|
| 4 | **The Viral Responder** | Monitors competitor outage mentions → builds comparison landing page → launches targeted $500 ad set |
| 5 | **The Churn Architect** | Flags inactive Pro users → analyzes support ticket pain points → sends personalized Loom invitations |
| 6 | **The Global Localizer** | Picks top US creative → adjusts pricing via PPP → localizes assets for Brazil → schedules launch |

### CHRO Scenarios (People)

| # | Scenario | What It Does |
|---|---|---|
| 7 | **The Headhunter** | Scrapes GitHub for ZK-proof Rust contributors → enriches profiles → drafts personalized outreach |
| 8 | **The Culture Pulse** | Anonymizes Slack messages → runs sentiment analysis → identifies friction → drafts 3-point action plan |
| 9 | **The Automated Onboarder** | Provisions SaaS accounts → builds training curriculum → schedules exec intros → sends welcome package |

### CLO Scenarios (Legal)

| # | Scenario | What It Does |
|---|---|---|
| 10 | **The Contract Sentinel** | Parses MSA → flags auto-renewal/liability shifts → generates redlined version → emails vendor legal |
| 11 | **The IP Defender** | Sweeps app stores for trademark violations → checks partner DB → drafts Cease & Desist letters |
| 12 | **The Regulatory Auditor** | Parses AI Transparency Act → maps data flows → flags non-compliant agents → builds remediation plan |

### CSO Scenarios (Sales)

| # | Scenario | What It Does |
|---|---|---|
| 13 | **The Ghostbuster** | Identifies stalled Fortune 500 deals → researches prospect news → drafts personalized follow-ups |
| 14 | **The Pipeline Optimizer** | Analyzes Closed-Lost deals → finds top feature gaps → cross-refs roadmap → re-engages top prospects |

## Quick Start

### Install

```bash
pip install -e ".[dev]"
```

### Launch the Web Dashboard (recommended)

The fastest way to explore everything:

```bash
cxo serve
# Open http://localhost:8000 in your browser
```

This gives you a full interactive dashboard where you can:
- **See all 6 agents** and their status on the Dashboard
- **Seed sample data** with one click (9 business documents)
- **Run any of the 14 scenarios** and watch steps execute with risk badges
- **Dispatch custom objectives** (try the example prompts)
- **Ingest your own documents** into the Context Vault
- **Query the Vault** with semantic search
- **Approve or reject** high-risk actions in the Approvals tab

The Swagger API docs are also available at `http://localhost:8000/docs`.

### Run the terminal demos (no browser needed)

```bash
python examples/scenarios_demo.py   # All 14 scenarios
python examples/quickstart.py       # Basic quickstart
```

### Run with OpenAI (full LLM mode)

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
cxo serve
```

### CLI

```bash
# Ingest a document
cxo ingest path/to/document.pdf

# Dispatch an objective
cxo objective "Budget optimization" "Find $100k in savings for Q4"

# List all 14 scenarios
cxo scenarios

# Execute a specific scenario
cxo run cfo-cash-flow-guardian
cxo run cmo-viral-responder
cxo run chro-headhunter
cxo run clo-contract-sentinel
cxo run cso-ghostbuster

# Query the Context Vault
cxo query "What are our vendor contracts?"

# System status
cxo status

# Start the REST API
cxo serve
```

### REST API

```bash
cxo serve  # starts on http://localhost:8000

# List scenarios
curl http://localhost:8000/scenarios
curl http://localhost:8000/scenarios?category=finance

# Execute a scenario
curl -X POST http://localhost:8000/scenarios/cfo-cash-flow-guardian/run

# Ingest documents
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Q3 revenue was $12.5M...", "source": "report.pdf"}'

# Dispatch objective
curl -X POST http://localhost:8000/objective \
  -H "Content-Type: application/json" \
  -d '{"title": "Vendor issue", "description": "Vietnam supplier is lagging"}'

# Check pending approvals
curl http://localhost:8000/approvals

# Approve / reject an action
curl -X POST http://localhost:8000/approve/ACTION_ID
curl -X POST http://localhost:8000/reject/ACTION_ID?reason=too+risky
```

## Testing

```bash
pytest tests/ -v    # 91 tests covering all components
```

## Project Structure

```
src/agentic_cxo/
├── __init__.py
├── config.py                 # Central configuration
├── models.py                 # Domain models (Pydantic)
├── orchestrator.py           # The Cockpit — coordinates agents + scenarios
├── cli.py                    # Typer CLI
├── pipeline/
│   ├── chunker.py            # Semantic Chunking
│   ├── enricher.py           # Metadata Enrichment
│   ├── summarizer.py         # Recursive Summarization
│   ├── refinery.py           # End-to-end pipeline
│   └── ingest.py             # PDF, DOCX, text ingestors
├── memory/
│   ├── vault.py              # Context Vault (ChromaDB)
│   └── versioning.py         # Document version management
├── agents/
│   ├── base.py               # Base agent with reasoning loop
│   ├── cfo.py                # AI CFO
│   ├── coo.py                # AI COO
│   ├── cmo.py                # AI CMO
│   ├── clo.py                # AI CLO
│   ├── chro.py               # AI CHRO (People & Culture)
│   └── cso.py                # AI CSO (Sales & Revenue)
├── scenarios/
│   ├── engine.py             # Scenario Engine (multi-step executor)
│   └── registry.py           # All 14 scenario definitions
├── guardrails/
│   ├── risk.py               # Risk Assessor
│   └── approval.py           # Human-in-the-loop Approval Gate
└── api/
    └── server.py             # FastAPI REST endpoints
```

---

## Implementation Assessment & Next Steps

*Audit performed 2026-02-28 — covers every major subsystem.*

### 1. Agents (`agents/base.py`, `cfo.py`, `cmo.py`, `coo.py`, etc.)

**Status: Fully Functional**

| Component | Assessment |
|---|---|
| `BaseAgent` | Complete reasoning loop: gather context → LLM plan → risk assess → approval gate. Falls back to deterministic planning when LLM is unavailable. Proper OpenAI client setup, JSON parsing of LLM output, citation extraction, and message logging. |
| `AgentCFO`, `AgentCMO`, `AgentCOO`, `AgentCLO`, `AgentCHRO`, `AgentCSO` | Each subclass is intentionally thin — they override `system_prompt()` with domain-specific instructions and rules. All reasoning logic is inherited from `BaseAgent`. This is a clean design, not a stub. |

**Gaps:**
- Agent subclasses have no domain-specific _tools_ (e.g., the CFO cannot call Stripe directly; the CMO cannot pause a campaign). Agents reason via LLM prompt only and never invoke live integrations themselves.
- No agent-to-agent communication protocol beyond the orchestrator's message bus. Agents cannot autonomously delegate sub-tasks to each other.
- No per-agent memory or learning — all agents share the same vault. There is no mechanism for an agent to remember outcomes of its own past recommendations.

---

### 2. Action Executor (`actions/executor.py`)

**Status: Fully Functional (with graceful degradation)**

| Action | Real? | Notes |
|---|---|---|
| `send_email` | **Yes** | Real SMTP with Gmail/Outlook support. Gracefully queues if SMTP not configured. |
| `post_slack` | **Yes** | Real Slack webhook POST. Queues if webhook URL not set. |
| `fire_webhook` | **Yes** | Real HTTP POST/GET to arbitrary URLs via `httpx`. |
| `create_task` | **Simulated** | Returns a string — no external task system (Jira, Asana) integration. |
| `book_meeting` | **Simulated** | Returns a queued message — no Google Calendar or Outlook Calendar API integration. |
| `generate_report` | **Real (local)** | Writes Markdown files to `.cxo_data/`. No cloud storage or PDF generation. |

The `ActionQueue` is complete: persistent JSON storage, submit/approve/reject lifecycle, auto-execute for low-risk actions, hold-for-approval for high-risk. This is production-usable as-is.

**Gaps:**
- `create_task` needs a real Jira/Linear/Asana connector.
- `book_meeting` needs Google Calendar API or similar.
- `generate_report` should support PDF export and cloud upload.
- No retry logic for transient failures on email/Slack/webhook.
- No rate limiting on action execution.

---

### 3. Integrations (`integrations/live/manager.py` + connector clients)

**Status: Fully Functional — 26 live connectors with real API calls**

| Connector | Real API Calls? | Data Types |
|---|---|---|
| Slack | **Yes** — `slack.com/api/auth.test`, `conversations.list`, `conversations.history`, `users.list`, `chat.postMessage` | channels, messages, users, post_message |
| Stripe | **Yes** — `/v1/balance`, `/v1/subscriptions`, `/v1/customers`, `/v1/charges`, `/v1/invoices` + MRR calculation | balance, subscriptions, customers, charges, invoices, mrr |
| HubSpot | **Yes** — `/crm/v3/objects/deals`, `/contacts`, `/companies`, `/pipelines/deals` | deals, contacts, companies, pipeline, owners |
| Gmail | **Yes** — IMAP4_SSL for inbox/search/unread, SMTP for sending | inbox, send_email, search, unread_count |
| GitHub, Bitbucket | **Yes** — repos, issues, PRs, contributors | repos, issues, pull_requests, contributors |
| Google Drive, OneDrive | **Yes** — file listing, metadata, content retrieval | files, folders, search, file_content |
| Jira | **Yes** — issues, projects, sprints | issues, projects, sprints |
| Notion | **Yes** — pages, databases, search | pages, databases, search |
| Shopify | **Yes** — products, orders, customers | products, orders, customers |
| Chargebee, QuickBooks, Salesforce | **Yes** — subscriptions/invoices/contacts/accounts | Various financial and CRM data types |
| GA4, Google Ads, Meta Ads | **Yes** — analytics and ad performance data | reports, campaigns, ad_sets |
| Mixpanel, Amplitude, Zendesk, Intercom, Avalara | **Yes** — analytics, support, and tax data | events, users, tickets, conversations, tax rates |
| Apple App Store, Google Play, Firebase | **Yes** — app reviews and analytics | reviews, ratings, analytics |

The `ConnectorManager` has a complete lifecycle: setup info → credential validation (real API test) → credential storage → data fetching → disconnect. `CredentialStore` persists credentials to disk as JSON.

**Gaps:**
- Credentials are stored as plaintext JSON files on disk. Production needs encrypted secret storage (Vault, AWS Secrets Manager, etc.).
- No OAuth2 token refresh logic for connectors that use OAuth (Shopify, Google, etc.). The `OAuthManager` exists in `oauth.py` but its token refresh flow is not wired into the connector clients.
- No webhook/real-time data ingestion — all connectors are poll-based (fetch on demand).
- No pagination for connectors that return large datasets (most are limited to 50-100 records).
- Connectors don't feed data back into the Context Vault automatically. Data must be manually ingested.

---

### 4. Orchestrator (`orchestrator.py`)

**Status: Fully Functional**

The `Cockpit` class is complete:
- **Agent registration**: All 6 CXO agents registered with shared vault, risk assessor, and approval gate.
- **Keyword-based routing**: Maps ~40 keywords to the correct agent role. Falls back to COO for unmatched queries.
- **Objective dispatch**: Routes to matched agents, runs `agent.reason()`, collects actions.
- **Scenario execution**: Delegates to `ScenarioEngine` with all 14 registry scenarios accessible.
- **Document ingestion**: Full pipeline — text → Context Refinery → Context Vault.
- **Approval management**: Approve/reject actions via the shared `ApprovalGate`.
- **Status reporting**: Vault size, pending approvals, action counts, scenario history.

**Gaps:**
- Routing is purely keyword-based. No semantic/LLM-based intent classification for the orchestrator itself (the conversation agent has this, but `Cockpit.route_objective()` does not).
- No multi-agent collaboration — when multiple agents are routed, they run independently. No result aggregation, conflict resolution, or consensus mechanism.
- No priority queue for objectives — all dispatches are synchronous and serial.
- No async execution — `dispatch()` blocks on each agent sequentially.

---

### 5. Conversation Agent (`conversation/agent.py`)

**Status: Fully Functional — most complete module in the codebase**

The `CoFounderAgent` is a comprehensive conversational AI with:
- **Chat loop**: User message → profile extraction → long-term memory extraction → event extraction → intent routing → tool execution → response generation.
- **Onboarding**: 8-question structured onboarding with nudges woven naturally into conversation.
- **Intent routing**: Routes to CFO/COO/CMO/CLO/CHRO/CSO based on message content.
- **Document handling**: Upload → refine → store in vault → extract reminders → assign to CXO agent.
- **Reminder system**: Parses natural language dates ("by next Monday", "tomorrow"), creates and manages reminders.
- **Morning briefing**: Generates daily briefing with overdue items, due today, coming up this week, critical alerts, system stats.
- **Tool execution**: Web search, cost analyzer, vendor due diligence, travel analyzer — all wired in.
- **LLM + fallback**: Full LLM response path with graceful fallback to vault-based responses when LLM is unavailable.
- **Context assembly**: Token-budget-aware context building with vault hits, conversation history, business profile, and long-term memory.
- **Session management**: Multiple conversation sessions with switch/create/archive.
- **Pattern detection**: Proactive alerts when repeated patterns are detected.
- **Product self-knowledge**: Can answer questions about its own capabilities without LLM.

**Gaps:**
- No streaming in the `chat()` method itself — streaming is handled separately by the `/chat/stream` SSE endpoint.
- No multi-turn tool use — tools are fire-and-forget, the agent cannot chain tool calls based on results.
- No file type detection for uploads — all files are decoded as UTF-8 text (no PDF/DOCX parsing in the upload flow, though the pipeline supports it).
- Action queue submissions from conversation are not yet wired (the `action_queue` is initialized but `chat()` doesn't create `ExecutableAction` objects from conversation).

---

### 6. Infrastructure — Billing (`infrastructure/billing.py`)

**Status: Partially Implemented (structure complete, no Stripe integration)**

The `BillingManager` has:
- Plan tiers: Free, Starter ($49/mo), Pro ($199/mo), Enterprise (custom).
- Subscription CRUD: create, upgrade, cancel, get.
- JSON persistence to `.cxo_data/billing.json`.
- Stripe customer/subscription ID fields on the `Subscription` model.

**Gaps:**
- **No actual Stripe billing integration.** The `stripe_customer_id` and `stripe_subscription_id` fields exist but are never populated. No Stripe Checkout, no webhook handling for payment events.
- No usage-based billing enforcement — the `UsageTracker` counts events but doesn't enforce plan limits.
- No payment method management.
- No invoice generation.

---

### 7. Infrastructure — Notifications (`infrastructure/notifications.py`)

**Status: Partially Implemented (in-app only)**

The `NotificationManager` is complete for in-app notifications:
- Create, read, mark-read, mark-all-read, recent, urgent filtering.
- 9 notification types (approval_needed, critical_reminder, deadline_approaching, etc.).
- 4 priority levels (low, medium, high, urgent).
- JSON persistence with 500-notification cap.

**Gaps:**
- **No email delivery.** The docstring promises email notifications via SMTP, but `notify()` only stores in-app — no email is sent.
- **No Slack delivery.** Same — the docstring promises Slack notifications, but no Slack message is posted.
- **No push notifications or WebSocket real-time delivery** to the browser.

---

### 8. API Server (`api/server.py`)

**Status: Fully Functional — comprehensive REST API**

The server is production-grade with 40+ endpoints:

| Category | Endpoints | Status |
|---|---|---|
| Auth | `/auth/signup`, `/auth/login` | Real JWT auth with bcrypt password hashing |
| Chat | `/chat`, `/chat/stream`, `/upload` | Full chat + SSE streaming + file upload |
| Briefing | `/briefing` | Complete morning briefing |
| Reminders | `/reminders`, `/complete`, `/snooze` | Full CRUD |
| Profile | `/profile` | Business profile with completeness |
| Status | `/status`, `/health` | Comprehensive system health |
| Scenarios | `/scenarios`, `/scenarios/{id}/run` | List + execute with analysis |
| Actions | `/actions`, `/approve`, `/reject` | Full action lifecycle |
| Decisions | `/decisions` | Decision log |
| Goals | `/goals` | Goal tracking |
| Jobs | `/jobs`, `/jobs/run-due` | Scheduled job execution |
| Connectors | `/connectors`, `/connect/{id}`, `/connect/{id}/fetch/{type}` | Full connect/test/fetch wizard |
| Permissions | `/permissions`, `/permissions/pending`, `/permissions/{id}` | Permission management |
| Teams | `/team/create`, `/team`, `/team/invite` | Basic team management |
| Notifications | `/notifications`, `/notifications/{id}/read`, `/notifications/read-all` | In-app notifications |
| Sessions | `/sessions` CRUD | Multi-session support |
| OAuth | `/oauth/providers`, `/oauth/start/{id}`, `/oauth/callback/{id}` | OAuth2 flow |
| Seed/Reset | `/seed`, `/reset` | Demo data management |

**Gaps:**
- No CORS middleware configured — browser-based clients from different origins will fail.
- No rate limiting middleware.
- Error handling in `/chat` catches all exceptions and returns 200 with error message — should return proper HTTP error codes.
- No request validation beyond Pydantic models (no input sanitization).
- Background scheduler uses deprecated `@app.on_event("startup")` instead of lifespan.
- Static file serving assumes a `static/` directory exists but it's not in the repo.
- `import os` is at the bottom of the file (line 931) — works but is a code smell.
- No WebSocket endpoint for real-time chat updates.
- Single-tenant — all API state is global. No per-user data isolation despite having auth.

---

### 9. Guardrails — Risk Assessor (`guardrails/risk.py`)

**Status: Fully Functional (dual-mode)**

- **LLM mode**: Sends action description to LLM, parses structured JSON risk assessment (risk_level, risk_score, concerns, requires_approval). Respects configurable threshold from `settings.guardrails.require_human_approval_above_risk`.
- **Rule-based mode**: Keyword matching against high-risk terms ("terminate", "transfer funds", "sign contract", etc.) and medium-risk terms. Checks prohibited actions from config.
- **Graceful fallback**: If LLM assessment fails, falls back to rule-based automatically.

**Gaps:**
- No historical risk calibration — the assessor doesn't learn from past approval/rejection decisions.
- No cost-based risk scoring (a $100 action and a $1M action get the same keyword-based score).
- Rule-based keywords are hardcoded — not configurable per tenant.

---

### 10. Guardrails — Approval Gate (`guardrails/approval.py`)

**Status: Fully Functional (in-memory)**

- Auto-approves low-risk actions, queues high-risk for human review.
- Approve/reject with reason tracking and audit history.
- Clean pending/history separation.

**Gaps:**
- **In-memory only** — pending approvals are lost on server restart. The docstring acknowledges this ("In production, this would be backed by a persistent store"). The `ActionQueue` in `executor.py` has persistence, but this `ApprovalGate` does not.
- No timeout/escalation — actions can sit in the pending queue indefinitely.
- No notification trigger — the gate doesn't notify anyone when an action needs approval (the server manually creates notifications).
- No multi-level approval (e.g., critical actions needing 2 approvers).

---

### Summary Table

| Area | Status | Grade |
|---|---|---|
| Agent Base + 6 CXO Agents | Fully functional | A |
| Action Executor | Fully functional (email, Slack, webhook real; task, meeting simulated) | A- |
| 26 Live Integration Connectors | Fully functional with real API calls | A |
| Connector Manager | Fully functional lifecycle | A- |
| Orchestrator (Cockpit) | Fully functional | A- |
| Conversation Agent | Fully functional — most complete module | A+ |
| Scenario Engine (14 workflows) | Fully functional with dependency resolution | A |
| Context Vault (ChromaDB) | Fully functional | A |
| API Server (40+ endpoints) | Fully functional, needs middleware hardening | B+ |
| Guardrails — Risk Assessor | Fully functional (LLM + rule-based) | A- |
| Guardrails — Approval Gate | Functional but in-memory only | B |
| Authentication | Functional (JWT + bcrypt) | B+ |
| Billing | Structure only — no Stripe integration | C |
| Notifications | In-app only — no email/Slack delivery | C+ |
| Database | Schema defined, tables created, but most modules still use JSON files | C+ |
| Streaming | Functional SSE streaming | A- |

### Priority Next Steps

1. **Persist the Approval Gate** — swap in-memory dict for database or JSON storage so pending approvals survive restarts.
2. **Wire Stripe billing** — connect the existing `stripe_client.py` connector to `BillingManager` for actual subscription charges and webhook handling.
3. **Add CORS middleware** — required for any browser-based frontend to work cross-origin.
4. **Encrypt stored credentials** — replace plaintext JSON credential files with encrypted storage.
5. **Connect action executor to conversation** — wire `CoFounderAgent.chat()` to create `ExecutableAction` objects when agents recommend actions.
6. **Add email/Slack notification delivery** — extend `NotificationManager.notify()` to actually send via the configured channels.
7. **Migrate from JSON files to database** — the SQLAlchemy models and tables exist but most modules still read/write JSON files directly.
8. **Add CORS, rate limiting, and input sanitization middleware** to the API server.
9. **Wire live connectors into agent reasoning** — let agents query Stripe, HubSpot, Slack, etc. directly during their reasoning loop instead of only through the vault.
10. **Add OAuth token refresh** — ensure connectors using OAuth2 can refresh expired tokens automatically.
