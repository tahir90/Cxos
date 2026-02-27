"""
FastAPI server — Conversational AI Co-Founder interface.

Chat-first API: the founder talks, the AI co-founder routes to CXO agents.

  GET  /                   — Chat dashboard
  POST /chat               — Send a message, get CXO responses
  POST /upload             — Upload a document into chat
  GET  /briefing           — Morning briefing with critical reminders
  GET  /reminders          — All active reminders
  POST /reminders/{id}/complete — Mark a reminder done
  POST /reminders/{id}/snooze   — Snooze a reminder
  GET  /profile            — Business profile
  GET  /status             — System health
  GET  /history            — Conversation history
  POST /reset              — Clear all data (for demos)
  POST /seed               — Load sample data
  GET  /scenarios           — List scenarios
  POST /scenarios/{id}/run — Run a scenario
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentic_cxo.conversation.agent import CoFounderAgent
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.pipeline.enricher import MetadataEnricher
from agentic_cxo.pipeline.refinery import ContextRefinery
from agentic_cxo.pipeline.summarizer import RecursiveSummarizer
from agentic_cxo.scenarios.analyst import ScenarioAnalyst
from agentic_cxo.scenarios.engine import ScenarioEngine
from agentic_cxo.scenarios.registry import (
    SCENARIO_REGISTRY,
    get_scenario,
    list_scenarios,
)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Agentic CXO",
    description="Your AI Co-Founder",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

vault = ContextVault()
refinery = ContextRefinery(
    enricher=MetadataEnricher(use_llm=False),
    summarizer=RecursiveSummarizer(use_llm=False),
)

agent = CoFounderAgent(vault=vault, refinery=refinery, use_llm=False)
analyst = ScenarioAnalyst(vault=vault, use_llm=False)
scenario_engine = ScenarioEngine(vault=vault)

SAMPLE_DOCS = [
    ("quarterly_report.pdf",
     "Q3 2025 revenue was $12.5 million, up 22% year-over-year. "
     "Operating expenses rose to $4.1 million. Burn rate increased 12% "
     "due to new SaaS tools ($45k/mo) and contractor fees ($80k). "
     "Net profit margin improved to 18.3%. Cash reserves: $8.2M. "
     "Marketing budget: $500k/quarter. Payroll: $2.1M/month."),
    ("vendor_contracts.pdf",
     "Contract #VC-2025-089 with Vendor ABC Corp. Term: 24 months, "
     "auto-renewal clause with 60-day opt-out. Penalty: $50k. "
     "Volume discount: 5% above $100k. Payment: Net 30. "
     "Non-compete: 12 months. Liability cap: $500k. "
     "Expiration: December 15, 2026."),
    ("sales_pipeline.csv",
     "Deal: Acme Corp (Fortune 500), Stage: Negotiation, "
     "Last activity: 18 days ago, Value: $450k. "
     "Deal: GlobalTech, Closed-Lost, Reason: Missing SSO. "
     "Deal: MegaCorp, Closed-Lost, Reason: No Rust SDK. "
     "Deal: DataFlow Inc, Closed-Lost, Reason: Missing webhook API."),
    ("engineering_roadmap.md",
     "Q1 2026: SSO integration (shipped). Q2 2026: Rust SDK (in progress). "
     "Q3 2026: Webhook API v2 (planned). Q4 2026: ZK-proof module. "
     "Deadline: June 1, 2026 for California AI Transparency Act compliance."),
    ("invoices_ar.csv",
     "Invoice #1042: Client Apex ($25,000), 22 days overdue, VIP. "
     "Invoice #1055: Client Beta ($8,000), 18 days overdue, standard. "
     "Invoice #1061: Client Gamma ($45,000), 16 days overdue, VIP."),
    ("marketing_campaigns.csv",
     "Campaign Alpha: 2.1M impressions, $8.5k spend, ROI 3.2x. "
     "Campaign Beta: 800K impressions, $15k spend, ROI 0.8x. "
     "Campaign Gamma: 5.4M impressions, $22k spend, ROI 5.1x."),
]


class ChatRequest(BaseModel):
    message: str


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


# ── Dashboard ────────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Chat ─────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    responses = agent.chat(req.message)
    return {
        "responses": [
            {
                "role": r.role.value,
                "content": r.content,
                "actions": [a.model_dump() for a in r.actions],
                "metadata": r.metadata,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in responses
        ]
    }


@app.post("/upload")
async def upload(file: UploadFile) -> dict[str, Any]:
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    filename = file.filename or "upload.txt"
    responses = agent.chat(
        f"Please review this document: {filename}",
        attachments=[{
            "filename": filename,
            "text": text,
            "content_type": file.content_type or "text/plain",
            "size_bytes": len(content),
        }],
    )
    return {
        "responses": [
            {
                "role": r.role.value,
                "content": r.content,
                "actions": [a.model_dump() for a in r.actions],
                "metadata": r.metadata,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in responses
        ]
    }


# ── Briefing ─────────────────────────────────────────────────────

@app.get("/briefing")
async def briefing() -> dict[str, Any]:
    b = agent.morning_briefing()
    return {
        "greeting": b.greeting,
        "summary": b.summary,
        "critical_alerts": [
            {"title": s.title, "items": s.items, "priority": s.priority.value}
            for s in b.critical_alerts
        ],
        "reminders": [
            {"title": s.title, "items": s.items, "priority": s.priority.value}
            for s in b.reminders
        ],
        "insights": [
            {"title": s.title, "items": s.items, "priority": s.priority.value}
            for s in b.insights
        ],
        "formatted": agent.format_briefing(b),
    }


# ── Reminders ────────────────────────────────────────────────────

@app.get("/reminders")
async def reminders() -> dict[str, Any]:
    store = agent.reminder_store
    return {
        "active": [r.model_dump(mode="json") for r in store.active],
        "critical": [r.model_dump(mode="json") for r in store.critical],
        "overdue": [r.model_dump(mode="json") for r in store.overdue()],
        "total": len(store.active),
    }


@app.post("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: str) -> dict[str, Any]:
    ok = agent.reminder_store.complete(reminder_id)
    if not ok:
        raise HTTPException(404, "Reminder not found")
    return {"status": "completed"}


@app.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str, hours: int = 24) -> dict[str, Any]:
    ok = agent.reminder_store.snooze(reminder_id, hours)
    if not ok:
        raise HTTPException(404, "Reminder not found")
    return {"status": "snoozed", "hours": hours}


# ── Profile ──────────────────────────────────────────────────────

@app.get("/profile")
async def profile() -> dict[str, Any]:
    p = agent.profile_store.profile
    return {
        **p.model_dump(mode="json"),
        "completeness": p.completeness,
        "summary_text": p.summary(),
    }


# ── Status ───────────────────────────────────────────────────────

@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "vault_chunks": vault.count(),
        "messages": agent.memory.message_count,
        "reminders_active": len(agent.reminder_store.active),
        "reminders_critical": len(agent.reminder_store.critical),
        "profile_completeness": agent.profile_store.profile.completeness,
        "scenarios_available": len(SCENARIO_REGISTRY),
    }


@app.get("/history")
async def history(limit: int = 50) -> list[dict[str, Any]]:
    msgs = agent.memory.recent(limit)
    return [
        {
            "role": m.role.value,
            "content": m.content,
            "actions": [a.model_dump() for a in m.actions],
            "timestamp": m.timestamp.isoformat(),
        }
        for m in msgs
    ]


# ── Scenarios ────────────────────────────────────────────────────

@app.get("/scenarios")
async def scenarios_list(category: str | None = None) -> list[dict[str, Any]]:
    items = list_scenarios(category)
    return [
        {
            "id": s.scenario_id, "name": s.name,
            "description": s.description, "agent": s.agent_role,
            "category": s.category, "steps": len(s.steps), "tags": s.tags,
        }
        for s in items
    ]


@app.post("/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    result = scenario_engine.execute(scenario)
    analysis = analyst.analyze(scenario, result)
    return {
        "scenario": result.scenario_name,
        "status": result.status,
        "analysis": analysis,
        "summary": result.summary(),
    }


# ── Seed & Reset ─────────────────────────────────────────────────

@app.post("/seed")
async def seed() -> dict[str, Any]:
    total_chunks = 0
    for source, text in SAMPLE_DOCS:
        result = refinery.refine_text(text, source=source)
        vault.store(result.chunks)
        total_chunks += result.total_chunks
        agent.reminder_store.extract_from_text(text, source=source)
    return {"documents": len(SAMPLE_DOCS), "chunks": total_chunks}


@app.post("/reset")
async def reset() -> dict[str, Any]:
    agent.memory.clear()
    agent.profile_store.clear()
    agent.reminder_store.clear()
    try:
        vault.clear()
    except Exception:
        pass
    return {"status": "reset"}
