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

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from agentic_cxo.config import settings, validate_production_config
from agentic_cxo.infrastructure.agent_pool import AgentPool
from agentic_cxo.infrastructure.auth import AuthManager, get_current_user_dep
from agentic_cxo.infrastructure.database import init_db
from agentic_cxo.infrastructure.notifications import (
    NotificationManager,
    NotificationPriority,
    NotificationType,
)
from agentic_cxo.infrastructure.scheduler import (
    add_interval_job,
    start_scheduler,
    stop_scheduler,
)
from agentic_cxo.infrastructure.streaming import stream_chat_response
from agentic_cxo.infrastructure.teams import TeamRole, TeamStore
from agentic_cxo.infrastructure.usage import UsageTracker
from agentic_cxo.integrations.connectors import ConnectorRegistry
from agentic_cxo.integrations.live.manager import ConnectorManager
from agentic_cxo.integrations.oauth import OAuthManager
from agentic_cxo.integrations.permissions import PermissionChoice, PermissionManager
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
from agentic_cxo.tools.presentation import generate_pptx

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

def _rate_limit_key(request: Request) -> str:
    """Use unique key per request in test to avoid test rate-limit collisions."""
    if os.getenv("CXO_ENV") == "test":
        import uuid
        return f"test-{uuid.uuid4().hex[:8]}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
app = FastAPI(
    title="Agentic CXO",
    description="Your AI Co-Founder",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

HAS_LLM = bool(settings.llm.api_key)
_logger.info(
    "LLM mode: %s (model: %s)", "ON" if HAS_LLM else "OFF", settings.llm.model
)

refinery = ContextRefinery(
    enricher=MetadataEnricher(use_llm=False),
    summarizer=RecursiveSummarizer(use_llm=False),
)
agent_pool = AgentPool(refinery=refinery, use_llm=HAS_LLM)
# Default vault for health check (uses default collection)
_health_vault = ContextVault()
connector_registry = ConnectorRegistry()
connector_manager = ConnectorManager()
permission_manager = PermissionManager()
oauth_manager = OAuthManager()
validate_production_config()
auth_manager = AuthManager()
auth_manager.ensure_admin()
team_store = TeamStore()
notification_manager = NotificationManager()
usage_tracker = UsageTracker()

get_current_user = get_current_user_dep(auth_manager)

init_db()

_logger.info("Admin user ready — login at /login")


@app.on_event("startup")
async def on_startup():
    start_scheduler()
    add_interval_job(
        "auto_check_due_jobs", _run_due_jobs_background, hours=1
    )
    _logger.info("Background scheduler started with hourly job check")


@app.on_event("shutdown")
async def on_shutdown():
    stop_scheduler()


def _run_due_jobs_background():
    """Background function for scheduled jobs — runs per-user agents."""
    for user_id, agent in list(agent_pool._cache.items()):
        due = agent.job_scheduler.due_jobs
        for job in due:
            try:
                agent.chat(job.action_template)
                agent.job_scheduler.mark_run(job.job_id)
                _logger.info("Auto-ran job: %s for user %s", job.name, user_id[:8])
            except Exception as e:
                _logger.error("Job %s failed for user %s: %s", job.name, user_id[:8], e)


# ── Auth endpoints ───────────────────────────────────────────────


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/signup")
@limiter.limit("5/minute")
async def signup(req: SignupRequest, request: Request) -> dict[str, Any]:
    result = auth_manager.signup(req.email, req.password, req.name)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/auth/login")
@limiter.limit("10/minute")
async def login(req: LoginRequest, request: Request) -> dict[str, Any]:
    result = auth_manager.login(req.email, req.password)
    if "error" in result:
        raise HTTPException(401, result["error"])
    return result


# ── Streaming chat endpoint ──────────────────────────────────────


@app.get("/chat/stream")
async def chat_stream(message: str, user=Depends(get_current_user)):
    """Stream LLM response token by token via Server-Sent Events."""
    agent = agent_pool.get_agent(user.user_id)
    assembled = agent.context_assembler.assemble(
        user_message=message, agent_role="Co-Founder"
    )
    return EventSourceResponse(
        stream_chat_response(
            system_prompt=assembled.system_prompt,
            user_message=assembled.user_message,
            agent_role="agent",
        )
    )


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

@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness + readiness: DB, vault connectivity."""
    checks: dict[str, str] = {}
    try:
        from sqlalchemy import text
        from agentic_cxo.infrastructure.database import get_session
        with get_session() as session:
            session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:60]}"
    try:
        _ = _health_vault.count()
        checks["vault"] = "ok"
    except Exception as e:
        checks["vault"] = f"error: {str(e)[:60]}"
    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }


@app.get("/")
async def dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/welcome")
async def landing_page():
    return FileResponse(str(STATIC_DIR / "landing.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


# ── Chat ─────────────────────────────────────────────────────────

@app.post("/chat")
@limiter.limit("60/minute")
async def chat(
    req: ChatRequest, request: Request, user=Depends(get_current_user)
) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    try:
        usage_tracker.track("messages_sent")
        responses = agent.chat(req.message)
        usage_tracker.track("messages_received", len(responses))

        for r in responses:
            try:
                if r.actions:
                    for a in r.actions:
                        if a.status == "pending_approval":
                            notification_manager.notify(
                                NotificationType.APPROVAL_NEEDED,
                                f"Action needs approval: {a.action_type}",
                                a.description[:200],
                                NotificationPriority.HIGH,
                                user.user_id,
                            )
                if r.metadata.get("type") == "pattern_alert":
                    notification_manager.notify(
                        NotificationType.PATTERN_WARNING,
                        "Pattern warning detected",
                        r.content[:200],
                        NotificationPriority.URGENT,
                        user.user_id,
                    )
            except Exception:
                pass

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
    except Exception as e:
        _logger.error("Chat error: %s", e, exc_info=True)
        return {
            "responses": [
                {
                    "role": "system",
                    "content": f"Something went wrong: {str(e)[:200]}. "
                    "Please try again.",
                    "actions": [],
                    "metadata": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }


@app.post("/upload")
async def upload(file: UploadFile, user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    usage_tracker.track("documents_ingested")
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
async def briefing(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
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
async def reminders(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    store = agent.reminder_store
    return {
        "active": [r.model_dump(mode="json") for r in store.active],
        "critical": [r.model_dump(mode="json") for r in store.critical],
        "overdue": [r.model_dump(mode="json") for r in store.overdue()],
        "total": len(store.active),
    }


@app.post("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: str, user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    ok = agent.reminder_store.complete(reminder_id)
    if not ok:
        raise HTTPException(404, "Reminder not found")
    return {"status": "completed"}


@app.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str, hours: int = 24, user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    ok = agent.reminder_store.snooze(reminder_id, hours)
    if not ok:
        raise HTTPException(404, "Reminder not found")
    return {"status": "snoozed", "hours": hours}


# ── Profile ──────────────────────────────────────────────────────

@app.get("/profile")
async def profile(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    p = agent.profile_store.profile
    return {
        **p.model_dump(mode="json"),
        "completeness": p.completeness,
        "summary_text": p.summary(),
    }


# ── Status ───────────────────────────────────────────────────────

@app.get("/status")
async def status(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    return {
        "vault_chunks": agent.vault.count(),
        "messages": agent.memory.message_count,
        "memories": agent.ltm.count,
        "events": agent.event_store.count,
        "reminders_active": len(agent.reminder_store.active),
        "reminders_critical": len(agent.reminder_store.critical),
        "actions_pending": len(agent.action_queue.pending),
        "actions_completed": len(agent.action_queue.completed),
        "decisions": agent.decision_log.count,
        "goals_active": len(agent.goal_tracker.active_goals),
        "goals_at_risk": len(agent.goal_tracker.at_risk),
        "jobs_due": len(agent.job_scheduler.due_jobs),
        "profile_completeness": agent.profile_store.profile.completeness,
        "scenarios_available": len(SCENARIO_REGISTRY),
    }


@app.get("/history")
async def history(limit: int = 50, user=Depends(get_current_user)) -> list[dict[str, Any]]:
    agent = agent_pool.get_agent(user.user_id)
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
async def scenarios_list(category: str | None = None, user=Depends(get_current_user)) -> list[dict[str, Any]]:
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
async def run_scenario(scenario_id: str, user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    scenario_engine = ScenarioEngine(vault=agent.vault)
    analyst_instance = ScenarioAnalyst(vault=agent.vault, use_llm=HAS_LLM)
    result = scenario_engine.execute(scenario)
    analysis = analyst_instance.analyze(scenario, result)
    return {
        "scenario": result.scenario_name,
        "status": result.status,
        "analysis": analysis,
        "summary": result.summary(),
    }


@app.post("/scenarios/{scenario_id}/ppt")
async def generate_scenario_ppt(
    scenario_id: str, user=Depends(get_current_user)
) -> StreamingResponse:
    """Run a scenario and return a downloadable .pptx slide deck from the analysis."""
    agent = agent_pool.get_agent(user.user_id)
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    scenario_engine = ScenarioEngine(vault=agent.vault)
    analyst_instance = ScenarioAnalyst(vault=agent.vault, use_llm=HAS_LLM)
    result = scenario_engine.execute(scenario)
    analysis = analyst_instance.analyze(scenario, result)
    report = analysis.get("report", "")
    if not report:
        raise HTTPException(500, "Scenario produced no report")
    filepath = generate_pptx(
        report,
        title=scenario.name,
        theme="dark",
        agent_role=scenario.agent_role,
        sources=analysis.get("sources"),
        add_title_slide=True,
        add_closing_slide=True,
    )

    def iterfile():
        with open(str(filepath), "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
    )


class GeneratePptRequest(BaseModel):
    message: str


@app.post("/generate-ppt")
async def generate_ppt_from_text(
    req: GeneratePptRequest, user=Depends(get_current_user)
) -> StreamingResponse:
    """Generate a .pptx slide deck from arbitrary text/report content."""
    filepath = generate_pptx(
        req.message,
        title="Custom Report",
        theme="dark",
        agent_role="CXO",
        add_title_slide=True,
        add_closing_slide=True,
    )

    def iterfile():
        with open(str(filepath), "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
    )


# ── Seed & Reset ─────────────────────────────────────────────────

@app.post("/seed")
async def seed(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    total_chunks = 0
    for source, text in SAMPLE_DOCS:
        result = refinery.refine_text(text, source=source)
        agent.vault.store(result.chunks)
        total_chunks += result.total_chunks
        agent.reminder_store.extract_from_text(text, source=source)
    return {"documents": len(SAMPLE_DOCS), "chunks": total_chunks}


@app.post("/reset")
async def reset(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    agent.memory.clear()
    agent.profile_store.clear()
    agent.reminder_store.clear()
    agent.action_queue.clear()
    agent.decision_log.clear()
    agent.goal_tracker.clear()
    try:
        agent.vault.clear()
    except Exception:
        pass
    return {"status": "reset"}


# ── Actions ──────────────────────────────────────────────────────

@app.get("/actions")
async def actions_list(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    return {
        "pending": [a.to_dict() for a in agent.action_queue.pending],
        "completed": [a.to_dict() for a in agent.action_queue.completed[-20:]],
        "total": len(agent.action_queue.all_actions),
    }


@app.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    result = agent.action_queue.approve(action_id)
    if not result:
        raise HTTPException(404, "Action not found")
    return result.to_dict()


@app.post("/actions/{action_id}/reject")
async def reject_action(action_id: str, reason: str = "", user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    result = agent.action_queue.reject(action_id, reason)
    if not result:
        raise HTTPException(404, "Action not found")
    return result.to_dict()


# ── Decision Log ─────────────────────────────────────────────────

@app.get("/decisions")
async def decisions(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    return {
        "decisions": [d.to_dict() for d in agent.decision_log.all_decisions],
        "open": len(agent.decision_log.open_decisions),
        "total": agent.decision_log.count,
    }


# ── Goals ────────────────────────────────────────────────────────

@app.get("/goals")
async def goals(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    return {
        "active": [g.to_dict() for g in agent.goal_tracker.active_goals],
        "at_risk": [g.to_dict() for g in agent.goal_tracker.at_risk],
        "total": len(agent.goal_tracker.all_goals),
        "formatted": agent.goal_tracker.format_status(),
    }


# ── Scheduled Jobs ───────────────────────────────────────────────

@app.get("/jobs")
async def jobs_list(user=Depends(get_current_user)) -> list[dict[str, Any]]:
    agent = agent_pool.get_agent(user.user_id)
    return agent.job_scheduler.get_status()


@app.post("/jobs/run-due")
async def run_due_jobs(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    due = agent.job_scheduler.due_jobs
    results: list[dict[str, str]] = []
    for job in due:
        responses = agent.chat(job.action_template)
        agent.job_scheduler.mark_run(job.job_id)
        results.append({
            "job": job.name,
            "agent": job.agent_role,
            "responses": len(responses),
        })
    return {"jobs_run": len(results), "results": results}


# ── Connectors / Settings ────────────────────────────────────────

@app.get("/connectors")
async def connectors_list(
    category: str | None = None,
    user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    if category:
        from agentic_cxo.integrations.connectors import ConnectorCategory

        try:
            cat = ConnectorCategory(category)
            return [c.to_dict() for c in connector_registry.by_category(cat)]
        except ValueError:
            pass
    return connector_registry.to_list()


@app.get("/connectors/summary")
async def connectors_summary(user=Depends(get_current_user)) -> dict[str, Any]:
    return connector_registry.summary()


@app.get("/connectors/by-agent/{role}")
async def connectors_by_agent(role: str, user=Depends(get_current_user)) -> list[dict[str, Any]]:
    return [c.to_dict() for c in connector_registry.by_agent(role.upper())]


# ── Permissions ──────────────────────────────────────────────────

@app.get("/permissions")
async def permissions_status(user=Depends(get_current_user)) -> dict[str, Any]:
    return permission_manager.get_rules_summary()


@app.get("/permissions/pending")
async def permissions_pending(user=Depends(get_current_user)) -> list[dict[str, Any]]:
    return [r.to_dict() for r in permission_manager.pending_requests]


class PermissionResponse(BaseModel):
    choice: str  # allow_once, allow_always, deny


@app.post("/permissions/{request_id}")
async def respond_to_permission(
    request_id: str, body: PermissionResponse, user=Depends(get_current_user)
) -> dict[str, Any]:
    try:
        choice = PermissionChoice(body.choice)
    except ValueError:
        raise HTTPException(400, f"Invalid choice: {body.choice}")
    result = permission_manager.respond(request_id, choice)
    if not result:
        raise HTTPException(404, "Permission request not found")
    return result.to_dict()


@app.post("/permissions/revoke/{action_type}")
async def revoke_permission(action_type: str, user=Depends(get_current_user)) -> dict[str, str]:
    permission_manager.revoke(action_type)
    return {"status": "revoked", "action_type": action_type}


# ── Settings ─────────────────────────────────────────────────────

@app.get("/settings")
async def get_settings(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    return {
        "llm": {
            "enabled": HAS_LLM,
            "model": settings.llm.model,
        },
        "connectors": connector_registry.summary(),
        "live_connectors": connector_manager.get_status(),
        "permissions": permission_manager.get_rules_summary(),
        "profile": agent.profile_store.profile.model_dump(mode="json"),
        "jobs": len(agent.job_scheduler.all_jobs),
        "tools": [
            "web_search", "cost_analyzer",
            "vendor_due_diligence", "travel_analyzer",
        ],
    }


# ── Live Connector Wizard ────────────────────────────────────────

@app.get("/connect/{connector_id}/setup")
async def connector_setup(connector_id: str, user=Depends(get_current_user)) -> dict[str, Any]:
    """Get setup info for a connector — what credentials are needed."""
    info = connector_manager.get_setup_info(connector_id)
    if info is None:
        registry_entry = connector_registry.get(connector_id)
        if registry_entry:
            return {
                "connector_id": connector_id,
                "name": registry_entry.name,
                "status": "not_implemented",
                "message": (
                    f"{registry_entry.name} is defined but doesn't have "
                    "a live integration yet. Set environment variables "
                    f"({', '.join(registry_entry.env_vars)}) to use it."
                ),
                "env_vars": registry_entry.env_vars,
            }
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    return info


class ConnectRequest(BaseModel):
    credentials: dict[str, str]


@app.post("/connect/{connector_id}")
async def connect_connector(
    connector_id: str, body: ConnectRequest, user=Depends(get_current_user)
) -> dict[str, Any]:
    """Test credentials and connect a connector."""
    result = connector_manager.connect(connector_id, body.credentials)
    return {
        "connector_id": connector_id,
        "success": result.success,
        "message": result.message,
        "details": result.details,
    }


@app.post("/connect/{connector_id}/disconnect")
async def disconnect_connector(connector_id: str, user=Depends(get_current_user)) -> dict[str, Any]:
    connector_manager.disconnect(connector_id)
    return {"connector_id": connector_id, "status": "disconnected"}


@app.get("/connect/{connector_id}/fetch/{data_type}")
async def fetch_connector_data(
    connector_id: str,
    data_type: str,
    repo: str = "",
    org: str = "",
    query: str = "",
    channel: str = "",
    workspace: str = "",
    path: str = "/",
    file_id: str = "",
    item_id: str = "",
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch live data from a connected connector."""
    kwargs: dict[str, Any] = {}
    if repo:
        kwargs["repo"] = repo
    if org:
        kwargs["org"] = org
    if query:
        kwargs["query"] = query
    if channel:
        kwargs["channel"] = channel
    if workspace:
        kwargs["workspace"] = workspace
    if path != "/":
        kwargs["path"] = path
    if file_id:
        kwargs["file_id"] = file_id
    if item_id:
        kwargs["item_id"] = item_id

    data = connector_manager.fetch_data(connector_id, data_type, **kwargs)
    return {
        "connector_id": data.connector_id,
        "data_type": data.data_type,
        "records": data.records[:100],
        "summary": data.summary,
        "error": data.error,
        "fetched_at": data.fetched_at,
    }


@app.get("/connect/status")
async def live_connector_status(user=Depends(get_current_user)) -> dict[str, Any]:
    return connector_manager.get_status()


# ── Teams ────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: str
    name: str = ""
    role: str = "member"


@app.post("/team/create")
async def create_team(name: str = "My Company", user=Depends(get_current_user)) -> dict[str, Any]:
    team = team_store.create(name, user.user_id, user.email, user.name or "Founder")
    return team.to_dict()


@app.get("/team")
async def get_team(user=Depends(get_current_user)) -> dict[str, Any]:
    teams = team_store.all_teams
    if teams:
        return teams[0].to_dict()
    return {"error": "No team created yet"}


@app.post("/team/invite")
async def invite_member(req: InviteRequest, user=Depends(get_current_user)) -> dict[str, Any]:
    teams = team_store.all_teams
    if not teams:
        raise HTTPException(404, "No team exists")
    import uuid

    member = team_store.invite(
        teams[0].team_id,
        uuid.uuid4().hex[:16], req.email, req.name,
        TeamRole(req.role), "founder",
    )
    if not member:
        raise HTTPException(400, "Could not invite member")
    return member.to_dict()


# ── Notifications ────────────────────────────────────────────────

@app.get("/notifications")
async def get_notifications(user=Depends(get_current_user)) -> dict[str, Any]:
    return {
        "unread": [n.to_dict() for n in notification_manager.unread],
        "unread_count": notification_manager.unread_count,
        "urgent": [n.to_dict() for n in notification_manager.urgent],
        "recent": [n.to_dict() for n in notification_manager.recent()],
    }


@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user=Depends(get_current_user)) -> dict[str, str]:
    notification_manager.mark_read(notification_id)
    return {"status": "read"}


@app.post("/notifications/read-all")
async def mark_all_read(user=Depends(get_current_user)) -> dict[str, int]:
    count = notification_manager.mark_all_read()
    return {"marked_read": count}


# ── Usage ────────────────────────────────────────────────────────

@app.get("/usage")
async def get_usage(user=Depends(get_current_user)) -> dict[str, Any]:
    return usage_tracker.summary()


# ── Sessions ─────────────────────────────────────────────────────

@app.get("/sessions")
async def list_sessions(user=Depends(get_current_user)) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    sm = agent.session_manager
    return {
        "active": sm.active_session_id,
        "sessions": [s.to_dict() for s in sm.all_sessions],
    }


@app.post("/sessions")
async def create_session(
    title: str = "New conversation", user=Depends(get_current_user)
) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    session = agent.session_manager.create(title)
    return session.to_dict()


@app.post("/sessions/{session_id}/switch")
async def switch_session(
    session_id: str, user=Depends(get_current_user)
) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    session = agent.session_manager.switch(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.to_dict()


@app.post("/sessions/{session_id}/rename")
async def rename_session(
    session_id: str, title: str, user=Depends(get_current_user)
) -> dict[str, Any]:
    agent = agent_pool.get_agent(user.user_id)
    session = agent.session_manager.rename(session_id, title)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.to_dict()


@app.post("/sessions/{session_id}/archive")
async def archive_session(
    session_id: str, user=Depends(get_current_user)
) -> dict[str, str]:
    agent = agent_pool.get_agent(user.user_id)
    agent.session_manager.archive(session_id)
    return {"status": "archived"}


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, user=Depends(get_current_user)
) -> dict[str, str]:
    agent = agent_pool.get_agent(user.user_id)
    agent.session_manager.delete(session_id)
    return {"status": "deleted"}


# ── OAuth2 Flows ─────────────────────────────────────────────────

@app.get("/oauth/providers")
async def oauth_providers(user=Depends(get_current_user)) -> list[dict[str, Any]]:
    """List all OAuth providers with connection status."""
    return oauth_manager.get_providers()


@app.get("/oauth/start/{provider_id}")
async def oauth_start(
    provider_id: str, shop: str = "", user=Depends(get_current_user)
):
    """Start OAuth flow — redirects to provider's auth page."""
    from fastapi.responses import RedirectResponse

    host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    if host:
        oauth_manager.base_url = f"https://{host}"
    elif not oauth_manager.base_url:
        oauth_manager.base_url = "http://localhost:8000"

    result = oauth_manager.start_auth(provider_id, shop)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return RedirectResponse(result["auth_url"])


@app.get("/oauth/callback/{provider_id}")
async def oauth_callback(
    provider_id: str, code: str = "", state: str = ""
):
    """OAuth callback — exchanges code for token, redirects to dashboard."""
    from fastapi.responses import HTMLResponse

    if not code:
        return HTMLResponse(
            "<h3>Authorization cancelled</h3>"
            '<p><a href="/">Back to dashboard</a></p>'
        )

    result = oauth_manager.handle_callback(provider_id, code, state)
    if result.get("success"):
        return HTMLResponse(
            f"<h3>Connected {provider_id} successfully!</h3>"
            '<p>Redirecting to dashboard...</p>'
            '<script>setTimeout(()=>window.location="/",1500)</script>'
        )
    return HTMLResponse(
        f"<h3>Connection failed</h3>"
        f"<p>{result.get('error', 'Unknown error')}</p>"
        f'<p><a href="/">Back to dashboard</a></p>'
    )
