"""
FastAPI server — REST interface to the Agentic CXO Cockpit.

Endpoints:
  POST /ingest          — push documents into the Context Vault
  POST /objective       — dispatch a business objective
  GET  /status          — system health and agent status
  GET  /approvals       — pending human-in-the-loop approvals
  POST /approve/{id}    — approve a pending action
  POST /reject/{id}     — reject a pending action
  POST /query           — query the Context Vault directly
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from agentic_cxo.orchestrator import Cockpit

app = FastAPI(
    title="Agentic CXO",
    description="AI-driven C-suite agents with modular context management",
    version="0.1.0",
)

cockpit = Cockpit()


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


class ApprovalResponse(BaseModel):
    action_id: str
    approved: bool | None
    description: str
    risk: str
    result: str | None


@app.get("/status")
async def status() -> dict[str, Any]:
    return cockpit.status()


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
    from pathlib import Path

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


@app.post("/query")
async def query_vault(req: QueryRequest) -> list[dict[str, Any]]:
    where = req.filters if req.filters else None
    return cockpit.vault.query(req.query, top_k=req.top_k, where=where)


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
        raise HTTPException(404, f"Action {action_id} not found in pending queue")
    return {
        "action_id": action.action_id,
        "approved": action.approved,
        "result": action.result,
    }


@app.post("/reject/{action_id}")
async def reject(action_id: str, reason: str = "") -> dict[str, Any]:
    action = cockpit.reject_action(action_id, reason)
    if action is None:
        raise HTTPException(404, f"Action {action_id} not found in pending queue")
    return {
        "action_id": action.action_id,
        "approved": action.approved,
        "result": action.result,
    }
