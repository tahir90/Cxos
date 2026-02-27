# Agentic CXO

**AI-driven C-suite agents with modular context management.**

Agentic CXO turns raw business documents into high-density, structured knowledge and routes business objectives to specialized AI agents (CFO, COO, CMO, CLO) that reason, plan, and act — with human-in-the-loop guardrails.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     THE COCKPIT (Orchestrator)              │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  AI CFO  │  │  AI COO  │  │  AI CMO  │  │  AI CLO  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│       └──────────────┴──────┬───────┴──────────────┘         │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │  CONTEXT VAULT  │  (ChromaDB)           │
│                    └────────┬────────┘                       │
│                             │                                │
│              ┌──────────────┴──────────────┐                │
│              │   CONTEXT REFINERY PIPELINE  │                │
│              │                              │                │
│              │  1. Semantic Chunker         │                │
│              │  2. Metadata Enricher        │                │
│              │  3. Recursive Summarizer     │                │
│              └──────────────────────────────┘                │
│                                                             │
│  ┌───────────────────────────────────────────────┐          │
│  │            GUARDRAILS                         │          │
│  │  Risk Assessor → Approval Gate → Human Pilot  │          │
│  └───────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### Context Refinery Pipeline

Solves the "Context Window Problem" by transforming raw documents into optimized knowledge:

| Stage | What It Does |
|---|---|
| **Semantic Chunker** | Splits text at thought boundaries (not character counts) using sentence-level similarity detection |
| **Metadata Enricher** | Tags every chunk with authority, urgency, entities, and domain labels |
| **Recursive Summarizer** | Builds a Summarization Pyramid: page → chapter → executive summary |

### Context Vault

ChromaDB-backed vector store that agents query instead of stuffing raw text into prompts. Includes automatic version management that deprecates old data when new versions arrive.

### Agentic CXO Agents

| Agent | Specialization |
|---|---|
| **AI CFO** | SaaS subscriptions, tax optimization, cash flow, spending anomalies |
| **AI COO** | Supply chain, vendor management, logistics, operational crises |
| **AI CMO** | Micro-campaigns, ad performance, budget reallocation, brand sentiment |
| **AI CLO** | Contract scanning, regulatory compliance, liability exposure |

### Guardrails

- **Risk Assessor** scores every proposed action (low → critical)
- **Approval Gate** holds high-risk actions for human approval
- Prohibited actions (e.g., terminating employees, signing large contracts) always require a human pilot

## Quick Start

### Install

```bash
pip install -e ".[dev]"
```

### Run without an API key (offline mode)

The system works fully offline using rule-based enrichment and extractive summarization:

```bash
python examples/quickstart.py
```

### Run with OpenAI (full LLM mode)

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
python examples/quickstart.py
```

### CLI

```bash
# Ingest a document
cxo ingest path/to/document.pdf

# Dispatch an objective
cxo objective "Budget optimization" "Find $100k in savings for Q4"

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

# Ingest
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Q3 revenue was $12.5M...", "source": "report.pdf"}'

# Dispatch objective
curl -X POST http://localhost:8000/objective \
  -H "Content-Type: application/json" \
  -d '{"title": "Vendor issue", "description": "Vietnam supplier is lagging"}'

# Check pending approvals
curl http://localhost:8000/approvals

# Approve an action
curl -X POST http://localhost:8000/approve/ACTION_ID
```

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
src/agentic_cxo/
├── __init__.py
├── config.py              # Central configuration
├── models.py              # Domain models (Pydantic)
├── orchestrator.py        # The Cockpit — coordinates all agents
├── cli.py                 # Typer CLI
├── pipeline/
│   ├── chunker.py         # Semantic Chunking
│   ├── enricher.py        # Metadata Enrichment
│   ├── summarizer.py      # Recursive Summarization
│   ├── refinery.py        # End-to-end pipeline
│   └── ingest.py          # PDF, DOCX, text ingestors
├── memory/
│   ├── vault.py           # Context Vault (ChromaDB)
│   └── versioning.py      # Document version management
├── agents/
│   ├── base.py            # Base agent with reasoning loop
│   ├── cfo.py             # AI CFO
│   ├── coo.py             # AI COO
│   ├── cmo.py             # AI CMO
│   └── clo.py             # AI CLO
├── guardrails/
│   ├── risk.py            # Risk Assessor
│   └── approval.py        # Human-in-the-loop Approval Gate
└── api/
    └── server.py          # FastAPI REST endpoints
```
