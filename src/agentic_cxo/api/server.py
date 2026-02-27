"""
FastAPI server — REST interface + Web Dashboard for the Agentic CXO Cockpit.

Dashboard: GET /                — Interactive web UI
API:
  POST /ingest              — push documents into the Context Vault
  POST /objective           — dispatch a business objective
  GET  /status              — system health and agent status
  GET  /approvals           — pending human-in-the-loop approvals
  POST /approve/{id}        — approve a pending action
  POST /reject/{id}         — reject a pending action
  POST /query               — query the Context Vault directly
  GET  /scenarios           — list all available scenarios
  POST /scenarios/{id}/run  — execute a scenario
  GET  /scenarios/history   — past scenario execution results
  GET  /agents              — list all agents with metadata
  POST /seed                — load sample business data
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentic_cxo.orchestrator import Cockpit
from agentic_cxo.scenarios.analyst import ScenarioAnalyst
from agentic_cxo.scenarios.registry import get_scenario as _get_scenario_obj

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Agentic CXO",
    description="AI-driven C-suite agents with modular context management",
    version="0.4.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

cockpit = Cockpit(use_llm=False)
analyst = ScenarioAnalyst(vault=cockpit.vault, use_llm=False)

AGENT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "CFO": {
        "title": "Chief Financial Officer",
        "focus": "Expenses, tax strategy, cash flow, collections, burn rate",
    },
    "COO": {
        "title": "Chief Operating Officer",
        "focus": "Supply chain, vendor management, logistics, operations",
    },
    "CMO": {
        "title": "Chief Marketing Officer",
        "focus": "Campaigns, churn prevention, ad optimization, localization",
    },
    "CLO": {
        "title": "Chief Legal Officer",
        "focus": "Contracts, IP defense, regulatory compliance, liability",
    },
    "CHRO": {
        "title": "Chief HR Officer",
        "focus": "Recruiting, culture health, onboarding, sentiment analysis",
    },
    "CSO": {
        "title": "Chief Sales Officer",
        "focus": "Pipeline optimization, deal recovery, prospect re-engagement",
    },
}

SAMPLE_DOCS = [
    {
        "source": "quarterly_report.pdf",
        "text": (
            "Q3 2025 revenue was $12.5 million, up 22% year-over-year. "
            "Operating expenses rose to $4.1 million. Burn rate increased 12% "
            "due to new SaaS tools ($45k/mo) and contractor fees ($80k). "
            "Net profit margin improved to 18.3%. Cash reserves: $8.2M. "
            "Marketing budget: $500k/quarter. Payroll: $2.1M/month."
        ),
    },
    {
        "source": "vendor_contracts.pdf",
        "text": (
            "Contract #VC-2025-089 with Vendor ABC Corp. Term: 24 months, "
            "auto-renewal clause with 60-day opt-out. Penalty: $50k. "
            "Volume discount: 5% above $100k. Payment: Net 30. "
            "Non-compete clause: 12 months post-termination. "
            "Liability cap: $500k. Indemnification: mutual."
        ),
    },
    {
        "source": "sales_pipeline.csv",
        "text": (
            "Deal: Acme Corp (Fortune 500), Stage: Negotiation, "
            "Last activity: 18 days ago, Value: $450k. "
            "Deal: GlobalTech, Stage: Closed-Lost, Reason: Missing SSO feature. "
            "Deal: MegaCorp, Stage: Closed-Lost, Reason: No Rust SDK. "
            "Deal: DataFlow Inc, Stage: Closed-Lost, Reason: Missing webhook API."
        ),
    },
    {
        "source": "engineering_roadmap.md",
        "text": (
            "Q1 2026: SSO integration (shipped). Q2 2026: Rust SDK (in progress). "
            "Q3 2026: Webhook API v2 (planned). Q4 2026: ZK-proof module. "
            "Hiring: Lead Rust Engineer needed for ZK work."
        ),
    },
    {
        "source": "marketing_campaigns.csv",
        "text": (
            "Campaign Alpha: 2.1M impressions, $8.5k spend, ROI 3.2x. "
            "Campaign Beta: 800K impressions, $15k spend, ROI 0.8x. "
            "Campaign Gamma: 5.4M impressions, $22k spend, ROI 5.1x. "
            "Competitor XYZ had a 4-hour outage trending on Reddit."
        ),
    },
    {
        "source": "hr_slack_summary.txt",
        "text": (
            "Sentiment analysis of 30 days of Slack: 62% positive, 28% neutral, "
            "10% negative. Top friction: CI/CD pipeline slowness (47 mentions). "
            "Secondary: unclear sprint priorities. Sales Playbook updated Feb 2026."
        ),
    },
    {
        "source": "invoices_ar.csv",
        "text": (
            "Invoice #1042: Client Apex ($25,000), 22 days overdue, VIP client. "
            "Invoice #1055: Client Beta ($8,000), 18 days overdue, standard. "
            "Invoice #1061: Client Gamma ($45,000), 16 days overdue, VIP client."
        ),
    },
    {
        "source": "ip_registry.txt",
        "text": (
            "Trademark 'AgenticCXO' registered US #12345678. "
            "Logo assets version 3.1. Partner DB: PartnerAlpha (licensed), "
            "PartnerBeta (licensed). App Store listing 'CXO-Fake' detected, "
            "publisher: UnknownDev LLC - not in partner database."
        ),
    },
    {
        "source": "ca_ai_act.txt",
        "text": (
            "California AI Transparency Act 2026: all automated decision systems "
            "that affect consumer rights must disclose AI involvement. "
            "Human-in-the-loop required for: credit decisions, hiring, "
            "insurance underwriting. Penalty: $10k per violation. "
            "Deadline: June 1, 2026."
        ),
    },
]


class IngestRequest(BaseModel):
    text: str
    source: str = "api"


class ObjectiveRequest(BaseModel):
    title: str
    description: str
    constraints: list[str] = []
    assigned_to: str | None = None


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, str] = {}


# ── Dashboard ────────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Status & Agents ─────────────────────────────────────────────

@app.get("/status")
async def status() -> dict[str, Any]:
    return cockpit.status()


@app.get("/agents")
async def agents() -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "title": AGENT_DESCRIPTIONS.get(role, {}).get("title", role),
            "focus": AGENT_DESCRIPTIONS.get(role, {}).get("focus", ""),
            "actions": len(agent.action_log),
        }
        for role, agent in cockpit.all_agents.items()
    ]


# ── Ingestion ────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(req: IngestRequest) -> dict[str, Any]:
    result = cockpit.ingest(req.text, source=req.source)
    return {
        "chunks": result.total_chunks,
        "tokens": result.total_tokens,
        "executive_summary": result.executive_summary,
    }


@app.post("/ingest/file")
async def ingest_file(file: UploadFile) -> dict[str, Any]:
    import tempfile

    suffix = Path(file.filename or "upload.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        result = cockpit.ingest_file(tmp.name)
    return {
        "filename": file.filename,
        "chunks": result.total_chunks,
        "tokens": result.total_tokens,
        "executive_summary": result.executive_summary,
    }


@app.post("/seed")
async def seed_data() -> dict[str, Any]:
    total_chunks = 0
    total_tokens = 0
    for doc in SAMPLE_DOCS:
        result = cockpit.ingest(doc["text"], source=doc["source"])
        total_chunks += result.total_chunks
        total_tokens += result.total_tokens
    return {
        "documents": len(SAMPLE_DOCS),
        "chunks": total_chunks,
        "tokens": total_tokens,
    }


# ── Objectives ───────────────────────────────────────────────────

@app.post("/objective")
async def dispatch_objective(req: ObjectiveRequest) -> dict[str, Any]:
    from agentic_cxo.models import Objective

    obj = Objective(
        title=req.title,
        description=req.description,
        constraints=req.constraints,
        assigned_to=req.assigned_to,
    )
    results = cockpit.dispatch(obj)
    response: dict[str, Any] = {}
    for role, actions in results.items():
        response[role] = [
            {
                "action_id": a.action_id,
                "description": a.description,
                "risk": a.risk.value,
                "requires_approval": a.requires_approval,
                "approved": a.approved,
                "citations": a.citations,
            }
            for a in actions
        ]
    return response


# ── Vault Query ──────────────────────────────────────────────────

@app.post("/query")
async def query_vault(req: QueryRequest) -> list[dict[str, Any]]:
    where = req.filters if req.filters else None
    return cockpit.vault.query(req.query, top_k=req.top_k, where=where)


# ── Approvals ────────────────────────────────────────────────────

@app.get("/approvals")
async def pending_approvals() -> list[dict[str, Any]]:
    return [
        {
            "action_id": a.action_id,
            "agent_role": a.agent_role,
            "description": a.description,
            "risk": a.risk.value,
        }
        for a in cockpit.pending_approvals
    ]


@app.post("/approve/{action_id}")
async def approve(action_id: str, approver: str = "pilot") -> dict[str, Any]:
    action = cockpit.approve_action(action_id, approver)
    if action is None:
        raise HTTPException(
            404, f"Action {action_id} not found in pending queue"
        )
    return {
        "action_id": action.action_id,
        "approved": action.approved,
        "result": action.result,
    }


@app.post("/reject/{action_id}")
async def reject(action_id: str, reason: str = "") -> dict[str, Any]:
    action = cockpit.reject_action(action_id, reason)
    if action is None:
        raise HTTPException(
            404, f"Action {action_id} not found in pending queue"
        )
    return {
        "action_id": action.action_id,
        "approved": action.approved,
        "result": action.result,
    }


# ── Scenarios ────────────────────────────────────────────────────

@app.get("/scenarios")
async def scenarios(category: str | None = None) -> list[dict[str, Any]]:
    return cockpit.list_scenarios(category)


@app.post("/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str) -> dict[str, Any]:
    result = cockpit.run_scenario(scenario_id)
    if result is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")

    scenario_obj = _get_scenario_obj(scenario_id)
    analysis = {}
    if scenario_obj:
        analysis = analyst.analyze(scenario_obj, result)

    return {
        "scenario": result.scenario_name,
        "status": result.status,
        "summary": result.summary(),
        "analysis": analysis,
        "steps": [
            {
                "step_id": sr.step_id,
                "status": sr.status.value,
                "action": sr.action.description[:200],
                "risk": sr.action.risk.value,
                "approved": sr.action.approved,
                "citations": sr.action.citations,
            }
            for sr in result.step_results
        ],
    }


@app.get("/scenarios/history")
async def scenario_history() -> list[dict[str, Any]]:
    return [r.summary() for r in cockpit.scenario_history]
