"""
Intent Router — understands what the founder is saying and routes to the right CXO.

In LLM mode, uses the model to parse intent.
In offline mode, uses keyword matching + conversation context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

INTENT_MAP: dict[str, dict[str, Any]] = {
    "onboarding": {
        "keywords": [
            "who are you", "get started", "hello", "hi", "hey",
            "what can you do", "help me", "introduce",
        ],
        "agent": None,
    },
    "finance": {
        "keywords": [
            "budget", "expense", "revenue", "burn rate", "cash flow",
            "invoice", "overdue", "tax", "payroll", "subscription",
            "collections", "savings", "cost", "profit", "payment",
        ],
        "agent": "CFO",
    },
    "operations": {
        "keywords": [
            "supply chain", "vendor", "logistics", "operations",
            "procurement", "inventory", "shipping", "warehouse",
            "factory", "production",
        ],
        "agent": "COO",
    },
    "marketing": {
        "keywords": [
            "campaign", "marketing", "brand", "advertising", "ad",
            "churn", "retention", "social media", "viral", "creative",
            "audience", "conversion", "seo", "content", "localize",
        ],
        "agent": "CMO",
    },
    "legal": {
        "keywords": [
            "contract", "legal", "compliance", "regulation", "liability",
            "trademark", "ip", "patent", "nda", "msa", "terms",
            "cease and desist", "clause", "redline",
        ],
        "agent": "CLO",
    },
    "people": {
        "keywords": [
            "hire", "recruit", "onboarding", "culture", "sentiment",
            "headhunt", "employee", "talent", "training", "team",
            "morale", "retention", "engineer", "developer",
        ],
        "agent": "CHRO",
    },
    "sales": {
        "keywords": [
            "sales", "pipeline", "deal", "prospect", "closed-lost",
            "follow-up", "re-engage", "crm", "lead", "demo",
            "proposal", "negotiation",
        ],
        "agent": "CSO",
    },
    "reminder": {
        "keywords": [
            "remind me", "reminder", "set a reminder", "don't forget",
            "follow up on", "deadline", "by friday", "by monday",
            "next week", "schedule",
        ],
        "agent": None,
    },
    "document": {
        "keywords": [
            "look at this", "review this", "check this",
            "here's a", "attached", "uploaded", "this file",
            "this document", "this contract", "this report",
        ],
        "agent": None,
    },
}

ROUTER_PROMPT = """\
You are an intent router for an AI co-founder system with 6 CXO agents.
Given the user's message, determine:
1. The primary intent category
2. Which CXO agent(s) should handle it
3. Whether a reminder should be extracted

User message: {message}

Business context: {context}

Return JSON:
{{
  "intent": "finance|operations|marketing|legal|people|sales|onboarding|reminder|document|general",
  "agents": ["CFO", "COO", "CMO", "CLO", "CHRO", "CSO"],
  "reminder": {{"needed": false, "title": "", "due": ""}},
  "summary": "one-line summary of what the user needs"
}}
Return ONLY valid JSON.
"""


@dataclass
class RoutingResult:
    intent: str
    agents: list[str]
    reminder_needed: bool = False
    reminder_title: str = ""
    reminder_due: str = ""
    summary: str = ""
    has_document: bool = False


@dataclass
class IntentRouter:
    use_llm: bool = False
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def route(
        self, message: str, has_attachment: bool = False, context: str = ""
    ) -> RoutingResult:
        if self.use_llm and settings.llm.api_key:
            try:
                return self._llm_route(message, context)
            except Exception:
                logger.warning("LLM routing failed, using keyword fallback", exc_info=True)
        return self._keyword_route(message, has_attachment)

    def _llm_route(self, message: str, context: str) -> RoutingResult:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.0,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": ROUTER_PROMPT.format(
                    message=message[:500], context=context[:300]
                ),
            }],
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        reminder = data.get("reminder", {})
        return RoutingResult(
            intent=data.get("intent", "general"),
            agents=data.get("agents", []),
            reminder_needed=reminder.get("needed", False),
            reminder_title=reminder.get("title", ""),
            reminder_due=reminder.get("due", ""),
            summary=data.get("summary", ""),
        )

    def _keyword_route(
        self, message: str, has_attachment: bool = False
    ) -> RoutingResult:
        lower = message.lower()
        scores: dict[str, int] = {}

        for intent, config in INTENT_MAP.items():
            score = sum(1 for kw in config["keywords"] if kw in lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            if has_attachment:
                return RoutingResult(
                    intent="document", agents=[], has_document=True
                )
            return RoutingResult(intent="general", agents=["COO"])

        top_intent = max(scores, key=scores.get)

        agents: list[str] = []
        for intent, config in INTENT_MAP.items():
            if scores.get(intent, 0) > 0 and config["agent"]:
                agents.append(config["agent"])
        agents = list(dict.fromkeys(agents))

        if not agents and top_intent not in ("onboarding", "reminder", "document"):
            agents = ["COO"]

        reminder_needed = "reminder" in scores or any(
            kw in lower
            for kw in ["remind me", "don't forget", "deadline", "follow up"]
        )

        return RoutingResult(
            intent=top_intent,
            agents=agents,
            reminder_needed=reminder_needed,
            has_document=has_attachment,
        )
