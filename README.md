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

### Production deployment

Before running in production, set these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `CXO_ENV` | Yes | Set to `production` |
| `CXO_JWT_SECRET` | Yes | Strong random string (e.g. `openssl rand -hex 32`) |
| `CXO_ADMIN_PASSWORD` | Yes | Strong password for the first admin user |
| `CXO_ENCRYPTION_KEY` | Recommended | For encrypted connector credentials |
| `OPENAI_API_KEY` | For LLM | Required for AI features |
| `DATABASE_URL` | Optional | Postgres URL; defaults to SQLite |

The app will refuse to start if `CXO_ENV=production` and insecure defaults are used.

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
