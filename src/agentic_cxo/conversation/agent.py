"""
Conversational Agent — the AI co-founder.

This is the brain. It:
1. Onboards the founder by asking questions and learning the business
2. Routes conversations to the right CXO agents
3. Ingests documents dropped into chat
4. Extracts reminders and deadlines
5. Generates morning briefings
6. Orchestrates real actions (emails, campaigns, etc.)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from openai import OpenAI

from agentic_cxo.actions.decision_log import DecisionLog
from agentic_cxo.actions.executor import ActionQueue
from agentic_cxo.actions.goal_tracker import GoalTracker
from agentic_cxo.actions.scheduler import JobScheduler
from agentic_cxo.config import settings
from agentic_cxo.infrastructure.llm_retry import with_retry
from agentic_cxo.conversation.context import ContextAssembler, TokenBudget
from agentic_cxo.conversation.long_term_memory import (
    LongTermMemory,
    MemoryExtractor,
)
from agentic_cxo.conversation.memory import (
    BusinessProfileStore,
    ConversationMemory,
    ReminderStore,
)
from agentic_cxo.conversation.models import (
    AgentActionRef,
    Attachment,
    BriefingSection,
    ChatMessage,
    MessageRole,
    MorningBriefing,
    Reminder,
    ReminderPriority,
)
from agentic_cxo.conversation.pattern_engine import (
    EventExtractor,
    EventStore,
    ProactiveAlertEngine,
)
from agentic_cxo.conversation.product_knowledge import (
    ProductKnowledgeBase,
    QueryClassifier,
    QueryType,
)
from agentic_cxo.conversation.router import IntentRouter, RoutingResult
from agentic_cxo.conversation.sessions import SessionManager
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.pipeline.refinery import ContextRefinery
from agentic_cxo.agents.agent_bus import AgentBus, CXO_ROLE_ICONS, CXO_ROLE_LABELS
from agentic_cxo.agents.creative_director import CreativeDirectorAgent
from agentic_cxo.tools.auditors.ads_auditor import AdsAuditorTool
from agentic_cxo.tools.auditors.seo_auditor import SEOAuditorTool
from agentic_cxo.tools.brand_intelligence import BrandIntelligenceTool
from agentic_cxo.tools.cost_analyzer import CostAnalyzerTool
from agentic_cxo.tools.framework import ToolExecutor, ToolRegistry
from agentic_cxo.tools.image_generator import ImageGeneratorTool
from agentic_cxo.tools.plan_executor import PlanExecutor
from agentic_cxo.tools.planner import PlannerTool
from agentic_cxo.tools.presentation_generator import PresentationGeneratorTool, set_creative_director
from agentic_cxo.tools.researcher import ResearcherTool
from agentic_cxo.tools.strategy_planner import StrategyPlannerTool
from agentic_cxo.tools.travel_analyzer import TravelAnalyzerTool
from agentic_cxo.tools.vendor_diligence import VendorDueDiligenceTool
from agentic_cxo.tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

ONBOARDING_QUESTIONS = [
    ("company_name", "What's the name of your company?"),
    ("industry", "What industry are you in?"),
    ("main_product", "What does your company do? What's your main product or service?"),
    ("revenue_model", "What's your revenue model? (SaaS, marketplace, services, etc.)"),
    ("arr", "What's your approximate annual revenue or ARR?"),
    ("team_size", "How big is your team right now?"),
    ("customers", "Who are your customers? (B2B enterprise, SMBs, consumers, etc.)"),
    ("pain_points", "What's your biggest operational headache right now?"),
]

CXO_SYSTEM_PROMPTS = {
    "CFO": (
        "You are the AI Chief Financial Officer. Your domain: financial analysis, "
        "budgets, cash flow, cost optimization, tax strategy, investor reporting, "
        "subscription audits, and revenue forecasting.\n\n"
        "RULES:\n"
        "- ALWAYS cite specific numbers and data sources\n"
        "- Present every recommendation with expected dollar impact\n"
        "- Flag any spending anomalies or budget overruns with severity\n"
        "- Prioritize capital preservation over yield optimization\n"
        "- Include risk/reward analysis for every financial recommendation\n"
        "- When discussing costs, always provide comparison benchmarks\n\n"
        "You can consult the CMO for marketing budget data, the COO for "
        "operational costs, and the CSO for revenue pipeline metrics."
    ),
    "COO": (
        "You are the AI Chief Operating Officer. Your domain: operations, "
        "supply chain, vendor management, logistics, process optimization, "
        "quality assurance, and capacity planning.\n\n"
        "RULES:\n"
        "- Present at least 3 alternatives for every vendor replacement\n"
        "- Include cost-benefit analysis for every operational change\n"
        "- Cite data sources for all vendor performance claims\n"
        "- Respect existing contractual obligations\n"
        "- Propose timelines with dependencies and milestones\n\n"
        "You can consult the CFO for budget constraints, the CLO for "
        "contract terms, and the CHRO for staffing availability."
    ),
    "CMO": (
        "You are the AI Chief Marketing Officer. Your domain: campaign strategy, "
        "brand positioning, audience segmentation, growth marketing, content "
        "strategy, SEO/SEM, social media, and competitive intelligence.\n\n"
        "RULES:\n"
        "- Be data-driven: cite campaign metrics, conversion rates, CAC/LTV\n"
        "- Present A/B test recommendations with expected uplift\n"
        "- Optimize for long-term customer lifetime value, not just clicks\n"
        "- Include budget allocation recommendations with ROI projections\n"
        "- Flag any campaign that could damage brand reputation\n\n"
        "You can consult the CFO for marketing budget, the CSO for sales "
        "conversion data, and the CHRO for employer brand alignment."
    ),
    "CLO": (
        "You are the AI Chief Legal Officer. Your domain: contracts, compliance, "
        "regulatory analysis, IP protection, data privacy (GDPR/CCPA/EU AI Act), "
        "and risk mitigation.\n\n"
        "RULES:\n"
        "- ALWAYS cite specific clause numbers and documents\n"
        "- Include legal disclaimers on all advisory outputs\n"
        "- Flag auto-renewal, IP assignment, and indemnification clauses\n"
        "- Present risk severity with recommended remediation steps\n"
        "- Escalate anything involving IP assignment immediately\n\n"
        "You can consult the CFO for financial exposure, the COO for "
        "vendor contracts, and the CHRO for employment law matters."
    ),
    "CHRO": (
        "You are the AI Chief Human Resources Officer. Your domain: talent "
        "acquisition, culture assessment, onboarding, employee engagement, "
        "performance management, compensation, and DEI.\n\n"
        "RULES:\n"
        "- ALWAYS respect candidate and employee privacy\n"
        "- Anonymize all sentiment analysis — never attribute quotes\n"
        "- Bias-check all outreach templates\n"
        "- Cite specific data points for culture recommendations\n"
        "- Be empathetic but actionable in people-related advice\n\n"
        "You can consult the CFO for compensation benchmarks, the CLO for "
        "employment law, and the CMO for employer brand strategy."
    ),
    "CSO": (
        "You are the AI Chief Sales Officer. Your domain: pipeline optimization, "
        "deal strategy, prospect research, sales forecasting, deal recovery, "
        "competitive positioning, and account planning.\n\n"
        "RULES:\n"
        "- ALWAYS cite data sources for prospect intelligence\n"
        "- Include specific, factual hooks in outreach — never generic\n"
        "- Quantify the revenue opportunity for every recommendation\n"
        "- Respect opt-out and do-not-contact lists\n"
        "- Cross-reference lost-deal reasons with product roadmap\n\n"
        "You can consult the CFO for deal financials, the CMO for lead "
        "quality data, and the CLO for contract negotiation guidance."
    ),
}


@dataclass
class CoFounderAgent:
    """The AI co-founder — primary conversational interface."""

    vault: ContextVault = field(default_factory=ContextVault)
    refinery: ContextRefinery | None = None
    use_llm: bool = False
    memory: ConversationMemory = field(default_factory=ConversationMemory)
    profile_store: BusinessProfileStore = field(
        default_factory=BusinessProfileStore
    )
    reminder_store: ReminderStore = field(default_factory=ReminderStore)
    router: IntentRouter = field(default_factory=IntentRouter)
    ltm: LongTermMemory = field(default_factory=LongTermMemory)
    memory_extractor: MemoryExtractor = field(
        default_factory=MemoryExtractor
    )
    event_store: EventStore = field(default_factory=EventStore)
    event_extractor: EventExtractor = field(default_factory=EventExtractor)
    product_kb: ProductKnowledgeBase = field(
        default_factory=ProductKnowledgeBase
    )
    query_classifier: QueryClassifier = field(
        default_factory=QueryClassifier
    )
    session_manager: SessionManager = field(
        default_factory=SessionManager
    )
    action_queue: ActionQueue = field(default_factory=ActionQueue)
    decision_log: DecisionLog = field(default_factory=DecisionLog)
    goal_tracker: GoalTracker = field(default_factory=GoalTracker)
    job_scheduler: JobScheduler = field(default_factory=JobScheduler)
    alert_engine: ProactiveAlertEngine | None = field(
        default=None, init=False
    )
    context_assembler: ContextAssembler | None = field(
        default=None, init=False
    )
    creative_director: CreativeDirectorAgent | None = field(
        default=None, init=False
    )
    agent_bus: AgentBus | None = field(default=None, init=False)
    planner: PlannerTool | None = field(default=None, init=False)
    plan_executor: PlanExecutor | None = field(default=None, init=False)
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.router = IntentRouter(use_llm=self.use_llm)
        self.memory_extractor = MemoryExtractor(use_llm=self.use_llm)
        self.alert_engine = ProactiveAlertEngine(
            event_store=self.event_store,
        )

        self.creative_director = CreativeDirectorAgent()
        set_creative_director(self.creative_director)

        self.agent_bus = AgentBus(use_llm=self.use_llm)

        self._tool_registry = ToolRegistry()
        self._tool_registry.register(WebSearchTool())
        self._tool_registry.register(
            CostAnalyzerTool(vault=self.vault, event_store=self.event_store)
        )
        self._tool_registry.register(VendorDueDiligenceTool(vault=self.vault))
        self._tool_registry.register(TravelAnalyzerTool(vault=self.vault))
        self._tool_registry.register(ImageGeneratorTool())
        self._tool_registry.register(AdsAuditorTool())
        self._tool_registry.register(SEOAuditorTool())
        self._tool_registry.register(StrategyPlannerTool())
        self._tool_registry.register(BrandIntelligenceTool())
        self._tool_registry.register(ResearcherTool())
        self._tool_registry.register(PresentationGeneratorTool())
        self._tool_executor = ToolExecutor(
            registry=self._tool_registry, use_llm=self.use_llm
        )

        self.planner = PlannerTool(use_llm=self.use_llm)
        self.plan_executor = PlanExecutor(
            tool_registry=self._tool_registry,
            creative_director=self.creative_director,
            use_llm=self.use_llm,
        )

        self.context_assembler = ContextAssembler(
            vault=self.vault,
            memory=self.memory,
            profile_store=self.profile_store,
            reminder_store=self.reminder_store,
            ltm=self.ltm,
            budget=TokenBudget.for_model(settings.llm.model),
        )

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    # ── Main entry point ────────────────────────────────────────

    def chat(
        self,
        message: str,
        attachments: list[dict[str, Any]] | None = None,
        session_id: str = "",
    ) -> list[ChatMessage]:
        """Process a user message and return agent response(s)."""
        has_attach = bool(attachments)

        if session_id:
            self.session_manager.switch(session_id)
        active = self.session_manager.active_session
        if active:
            self.session_manager.update_activity(active.session_id)

        user_msg = ChatMessage(
            role=MessageRole.USER,
            content=message,
            attachments=[
                Attachment(
                    filename=a.get("filename", "file"),
                    content_type=a.get("content_type", "text/plain"),
                    size_bytes=a.get("size_bytes", 0),
                )
                for a in (attachments or [])
            ],
        )
        self.memory.add(user_msg)

        self.profile_store.extract_and_update(message)
        extracted = self.memory_extractor.extract(
            message, role="user", source="conversation"
        )
        if extracted:
            self.ltm.add_many(extracted)

        events = self.event_extractor.extract(message)
        for ev in events:
            self.event_store.record(ev)

        route = self.router.route(message, has_attachment=has_attach)

        responses: list[ChatMessage] = []

        alerts = self.alert_engine.check(message)
        if alerts:
            alert_text = self.alert_engine.format_alerts(alerts)
            if alert_text:
                responses.append(ChatMessage(
                    role=MessageRole.AGENT,
                    content=alert_text,
                    metadata={"type": "pattern_alert"},
                ))

        if attachments:
            for att in attachments:
                doc_resp = self._handle_document(att)
                responses.append(doc_resp)

        if route.reminder_needed:
            reminder_resp = self._handle_reminder(message)
            if reminder_resp:
                responses.append(reminder_resp)

        intent_info = self.planner.should_plan(message) if self.planner else {}
        if intent_info.get("needs_planning") and self.planner and self.plan_executor:
            plan = self.planner.create_plan(message=message)
            if plan.steps:
                for event in self.plan_executor.execute_plan(plan):
                    if event.get("type") == "plan_complete":
                        combined = event.get("combined_summary", "")
                        if combined:
                            responses.append(ChatMessage(
                                role=MessageRole.AGENT,
                                content=combined,
                                actions=[AgentActionRef(
                                    action_type="plan_execution",
                                    description=plan.intent,
                                    details=event.get("combined_data", {}),
                                )],
                                metadata={"type": "plan_result"},
                            ))
            else:
                tool_results = self._tool_executor.decide_and_execute(message)
                for tr in tool_results:
                    if tr.success and tr.summary:
                        responses.append(ChatMessage(
                            role=MessageRole.AGENT,
                            content=f"**{tr.tool_name.replace('_', ' ').title()}:**\n\n{tr.summary}",
                            actions=[AgentActionRef(
                                action_type=f"tool_{tr.tool_name}",
                                description=tr.summary,
                                details=tr.data,
                            )],
                            metadata={"type": "tool_result", "tool": tr.tool_name},
                        ))
        else:
            topic, brand = self._extract_presentation_request(message)
            if topic:
                tool_results = self._run_presentation_workflow(topic, brand)
            else:
                tool_results = self._tool_executor.decide_and_execute(message)
            for tr in tool_results:
                if tr.success and tr.summary:
                    responses.append(ChatMessage(
                        role=MessageRole.AGENT,
                        content=f"**{tr.tool_name.replace('_', ' ').title()}:**\n\n{tr.summary}",
                        actions=[AgentActionRef(
                            action_type=f"tool_{tr.tool_name}",
                            description=tr.summary,
                            details=tr.data,
                        )],
                        metadata={"type": "tool_result", "tool": tr.tool_name},
                    ))

        is_first_message = self.memory.message_count <= 1

        if is_first_message and not attachments:
            responses.append(self._welcome_message())
        else:
            main_response = self._respond_naturally(message, route)
            responses.append(main_response)

            if (
                not self.profile_store.profile.onboarding_complete
                and self.profile_store.profile.completeness < 0.5
                and self.memory.message_count % 4 == 0
            ):
                nudge = self._onboarding_nudge()
                if nudge:
                    responses.append(nudge)

        for r in responses:
            self.memory.add(r)

        return responses

    def _extract_presentation_request(
        self, message: str
    ) -> tuple[str | None, str]:
        """Extract topic and optional brand domain from presentation requests.
        Handles follow-ups like 'create the ppt now' by pulling topic from conversation history.
        """
        msg_lower = message.lower().strip()
        ppt_triggers = (
            "create presentation", "make presentation", "create a presentation",
            "create ppt", "create a ppt", "make ppt", "creat ppt", "creat the ppt",
            "create powerpoint", "create deck", "make deck", "create slides",
            "make slides", "generate presentation", "generate deck", "the ppt",
            "ppt now", "create the ppt", "generate the ppt", "do it now", "go ahead",
            "ppt on", "presentation on", "deck on",
        )
        if not any(t in msg_lower for t in ppt_triggers):
            return None, ""

        topic = ""
        for pattern in [
            r"(?:create|make|generate)\s+(?:the\s+)?(?:a\s+)?(?:presentation|ppt|powerpoint|deck|slides)\s+(?:on|about|regarding)\s+(.+)",
            r"(?:presentation|ppt|deck|slides)\s+(?:on|about)\s+(.+)",
        ]:
            m = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if m:
                topic = m.group(1).strip()
                break
        if not topic:
            topic = re.sub(
                r"^(?:create|make|generate)\s+(?:the\s+)?(?:a\s+)?(?:presentation|ppt|deck|slides)\s*",
                "",
                message,
                flags=re.IGNORECASE,
            ).strip()
        followup_stubs = ("now", "it", "the ppt", "the presentation", "go ahead")
        if not topic or len(topic) < 5 or topic.lower() in followup_stubs:
            topic = self._extract_topic_from_conversation()
        if not topic or len(topic) < 5:
            return None, ""
        tlower = topic.lower()
        if any(x in tlower for x in ("ppt now", "the ppt", "create ", "make ", "generate ")):
            ctx_topic = self._extract_topic_from_conversation()
            if ctx_topic:
                topic = ctx_topic
        if len(topic) < 10:
            return None, ""

        brand = ""
        brand_match = re.search(
            r"\b(?:in|with)\s+([a-z0-9][-a-z0-9]*\.?[a-z]{2,})\s*(?:branding)?",
            message,
            re.IGNORECASE,
        )
        if brand_match:
            brand = brand_match.group(1).strip().replace(" ", "")
        if not brand:
            brand = self._extract_brand_from_conversation()

        return topic, brand

    def _extract_topic_from_conversation(self) -> str:
        """Pull presentation topic from recent conversation (for follow-ups like 'create ppt now')."""
        recent = self.memory.recent(15)
        for m in reversed(recent):
            content = (m.content or "").strip()
            for pattern in [
                r"(?:presentation|ppt|deck)\s+(?:on|about)\s+(.+)",
                r"(?:on|about)\s+(?:the\s+)?(.{10,120})",
                r"impact\s+of\s+[\w\s]+(?:\s+on\s+[\w\s]+)?",
                r"create\s+(?:a\s+)?presentation\s+on\s+(.+)",
            ]:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    t = match.group(1).strip() if match.lastindex else match.group(0).strip()
                    t = re.sub(r"[,;].*$", "", t).strip()
                    if len(t) > 10 and "ppt" not in t.lower() and "presentation" not in t.lower():
                        return t[:120]
        return ""

    def _extract_brand_from_conversation(self) -> str:
        """Pull brand domain from recent conversation."""
        recent = self.memory.recent(10)
        for m in reversed(recent):
            content = (m.content or "").lower()
            if "gmg" in content and ("branding" in content or "brand" in content or "gmg.com" in content):
                return "gmg.com"
            match = re.search(r"([a-z0-9-]+)\.(?:com|io|co)", content)
            if match:
                return match.group(0)
        return ""

    def _run_presentation_workflow(
        self, topic: str, brand_domain: str
    ) -> list[Any]:
        """Chain researcher -> presentation_generator for topic-based PPT requests."""
        researcher = self._tool_registry.get("researcher")
        presenter = self._tool_registry.get("presentation_generator")
        if not researcher or not presenter:
            return []

        research = researcher.execute(topic=topic, focus="general")
        if not research.success:
            return [research]

        outline = research.summary or research.data.get("summary", "")
        if not outline and research.data.get("findings"):
            outline = "## " + topic + "\n\n"
            for i, f in enumerate(research.data["findings"][:8], 1):
                outline += f"{i}. {str(f)[:200]}\n\n"

        if not outline:
            outline = f"## {topic}\n\n- Key points and discussion\n\n## Summary\n- Conclusions"

        return [
            research,
            presenter.execute(
                title=topic[:80],
                outline=outline,
                brand_domain=brand_domain,
            ),
        ]

    def chat_stream_events(
        self,
        message: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream agent activity as rich events for progressive disclosure UI.

        New event types for plan-and-execute transparency:
          plan_created, step_group_start, step_start, step_progress,
          step_complete, step_group_complete, source_found, agent_consulted,
          narration, document_ready, plan_complete

        Legacy event types (still supported):
          status, llm_thinking, tool_start, tool_end, progress,
          token, message, error, done
        """
        from agentic_cxo.tools.framework import ToolResult

        events: list[dict] = []

        def on_tool_start(tool_name: str, args: dict) -> None:
            events.append({
                "type": "tool_start",
                "tool": tool_name,
                "args": {k: (str(v)[:80] + "..." if isinstance(v, str) and len(v) > 80 else v)
                        for k, v in args.items()},
            })

        def on_tool_end(tool_name: str, result: ToolResult) -> None:
            data = result.data or {}
            safe_data = {k: v for k, v in data.items()
                        if k in ("url", "path", "title", "slides_count", "document_type") or
                        (not isinstance(v, (list, dict)) and k != "raw_results_count")}
            events.append({
                "type": "tool_end",
                "tool": tool_name,
                "success": result.success,
                "summary": (result.summary or "")[:500],
                "data": safe_data,
            })

        try:
            user_msg = ChatMessage(
                role=MessageRole.USER,
                content=message,
                attachments=[
                    Attachment(
                        filename=a.get("filename", "file"),
                        content_type=a.get("content_type", "text/plain"),
                        size_bytes=a.get("size_bytes", 0),
                    )
                    for a in (attachments or [])
                ],
            )
            self.memory.add(user_msg)

            has_attach = bool(attachments)

            # Detect short follow-up messages ("?", "status", "hello?", etc.)
            # and provide a contextual response using conversation history
            # instead of routing as a brand-new query.
            stripped = message.strip().lower().rstrip("?!.")
            is_short_followup = (
                len(message.strip()) <= 20
                and stripped in (
                    "", "?", "status", "update", "hello", "hi", "hey",
                    "what happened", "whats happening", "what's happening",
                    "anything", "progress", "still working", "are you there",
                    "you there", "stuck", "help", "continue",
                )
            )
            if is_short_followup:
                yield from self._handle_short_followup(message)
                return

            route = self.router.route(message, has_attachment=has_attach)

            yield {"type": "status", "message": "Understanding your request..."}

            intent_info = self.planner.should_plan(message) if self.planner else {}
            needs_plan = intent_info.get("needs_planning", False)

            if needs_plan and self.planner and self.plan_executor:
                yield from self._stream_planned_execution(message, route, has_attach, attachments)
            else:
                yield from self._stream_direct_execution(
                    message, route, has_attach, attachments,
                    on_tool_start, on_tool_end, events,
                )

        except Exception as e:
            logger.exception("Stream error")
            yield {"type": "error", "message": str(e)[:200]}
        finally:
            yield {"type": "done"}

    def _handle_short_followup(self, message: str) -> Iterator[dict[str, Any]]:
        """Handle short/ambiguous follow-up messages by referencing conversation history."""
        recent = self.memory.recent(6)
        if not recent:
            yield {"type": "message", "role": "agent",
                   "content": "I'm here! How can I help you? Could you describe what you need?"}
            self.memory.add(ChatMessage(
                role=MessageRole.AGENT,
                content="I'm here! How can I help you? Could you describe what you need?",
            ))
            return

        # Build context from recent conversation
        recent_summary = []
        for m in recent:
            prefix = "You" if m.role == MessageRole.USER else "Agent"
            recent_summary.append(f"{prefix}: {m.content[:150]}")
        context = "\n".join(recent_summary[-6:])

        if self.use_llm and settings.llm.api_key:
            try:
                client = OpenAI(
                    api_key=settings.llm.api_key,
                    base_url=settings.llm.base_url or None,
                )
                resp = with_retry(
                    lambda: client.chat.completions.create(
                        model=settings.llm.model,
                        temperature=0.3,
                        max_tokens=300,
                        messages=[
                            {"role": "system", "content": (
                                "You are an AI co-founder assistant. The user just sent a short "
                                "follow-up message (like '?' or 'status'). Based on the recent "
                                "conversation below, provide a brief, helpful status update or "
                                "ask a clarifying question. Be concise (2-3 sentences max). "
                                "If a task was recently completed, summarize what was done. "
                                "If a task seems to be in progress, reassure the user."
                            )},
                            {"role": "user", "content": (
                                f"Recent conversation:\n{context}\n\n"
                                f"User's follow-up: \"{message}\"\n\n"
                                "Respond helpfully based on the conversation context."
                            )},
                        ],
                    )
                )
                reply = (resp.choices[0].message.content or "").strip()
                if reply:
                    yield {"type": "message", "role": "agent", "content": reply}
                    self.memory.add(ChatMessage(role=MessageRole.AGENT, content=reply))
                    return
            except Exception:
                logger.debug("Short followup LLM failed", exc_info=True)

        # Fallback: summarize last agent message
        last_agent = None
        for m in reversed(recent):
            if m.role == MessageRole.AGENT:
                last_agent = m
                break

        if last_agent:
            reply = f"I'm here! My last update was: {last_agent.content[:200]}... Is there anything else you'd like me to help with?"
        else:
            reply = "I'm here and ready to help! What would you like me to work on?"
        yield {"type": "message", "role": "agent", "content": reply}
        self.memory.add(ChatMessage(role=MessageRole.AGENT, content=reply))

    def _stream_planned_execution(
        self,
        message: str,
        route: RoutingResult,
        has_attach: bool,
        attachments: list[dict[str, Any]] | None,
    ) -> Iterator[dict[str, Any]]:
        """Execute via plan-and-execute pattern with rich progress events."""
        from agentic_cxo.tools.framework import ToolResult

        yield {"type": "status", "message": "Planning the best approach..."}

        if self.use_llm and settings.llm.api_key:
            for tok in self._stream_llm_thinking(
                f"The user says: '{message[:200]}'. "
                "In 1-2 sentences, explain what you understand they need and what you'll do."
            ):
                yield {"type": "llm_thinking", "token": tok}

        business_context = ""
        if self.profile_store and self.profile_store.profile:
            p = self.profile_store.profile
            parts = []
            if p.company_name:
                parts.append(f"Company: {p.company_name}")
            if p.industry:
                parts.append(f"Industry: {p.industry}")
            business_context = ". ".join(parts)

        conversation_context = ""
        recent = self.memory.recent(5)
        if recent:
            conversation_context = " | ".join(
                m.content[:100] for m in recent if m.content
            )

        plan = self.planner.create_plan(
            message=message,
            context=conversation_context,
            business_profile=business_context,
        )

        if not plan.steps:
            yield from self._stream_direct_execution(
                message, route, has_attach, attachments,
                lambda *a: None, lambda *a: None, [],
            )
            return

        responses: list[ChatMessage] = []
        final_data: dict[str, Any] = {}

        for event in self.plan_executor.execute_plan(plan):
            yield event

            if event.get("type") == "document_ready":
                final_data.update(event)

            if event.get("type") == "plan_complete":
                combined_summary = event.get("combined_summary", "")
                if combined_summary:
                    responses.append(ChatMessage(
                        role=MessageRole.AGENT,
                        content=combined_summary,
                        actions=[AgentActionRef(
                            action_type="plan_execution",
                            description=plan.intent,
                            details=event.get("combined_data", {}),
                        )],
                        metadata={"type": "plan_result", "plan_intent": plan.intent},
                    ))
                    yield {"type": "message", "role": "agent", "content": combined_summary}

        if not responses:
            query_type = self.query_classifier.classify(message)
            if self.use_llm and settings.llm.api_key:
                for msg, token in self._llm_natural_response_streaming(
                    message, route, query_type
                ):
                    if token:
                        yield {"type": "token", "token": token}
                    elif msg:
                        responses.append(msg)
                        yield {"type": "message", "role": msg.role.value, "content": msg.content}
            else:
                main = self._respond_naturally(message, route)
                responses.append(main)
                yield {"type": "message", "role": main.role.value, "content": main.content}

        if attachments:
            for att in attachments:
                doc_resp = self._handle_document(att)
                responses.append(doc_resp)
                yield {"type": "message", "role": "agent", "content": doc_resp.content}

        for r in responses:
            self.memory.add(r)

    def _stream_direct_execution(
        self,
        message: str,
        route: RoutingResult,
        has_attach: bool,
        attachments: list[dict[str, Any]] | None,
        on_tool_start,
        on_tool_end,
        events: list[dict],
    ) -> Iterator[dict[str, Any]]:
        """Direct execution path — delegates to CXO agents when appropriate."""
        from agentic_cxo.tools.framework import ToolResult

        topic, brand = self._extract_presentation_request(message)
        tool_results: list[ToolResult] = []

        # Check if CXO orchestration is warranted (non-tool requests)
        if not topic and self._should_consult_cxos(message, route):
            yield from self._stream_cxo_orchestration(message, route)

            if attachments:
                for att in attachments:
                    doc_resp = self._handle_document(att)
                    yield {"type": "message", "role": "agent", "content": doc_resp.content}
                    self.memory.add(doc_resp)
            return

        if topic:
            yield {"type": "status", "message": f"Creating presentation on: {topic[:50]}..."}
            researcher = self._tool_registry.get("researcher")
            presenter = self._tool_registry.get("presentation_generator")
            if researcher and presenter:
                if self.use_llm and settings.llm.api_key:
                    for tok in self._stream_llm_thinking(
                        f"The user wants a presentation on: {topic}. "
                        "In 1-2 short sentences, say what you're about to do."
                    ):
                        yield {"type": "llm_thinking", "token": tok}
                yield {"type": "tool_start", "tool": "researcher", "args": {"topic": topic}}
                progress_events: list[dict] = []

                def on_progress(msg: str) -> None:
                    progress_events.append({"type": "progress", "message": msg})

                research = researcher.execute(
                    topic=topic, focus="general", progress_callback=on_progress
                )
                for ev in progress_events:
                    yield ev
                yield {"type": "tool_end", "tool": "researcher",
                       "success": research.success, "summary": (research.summary or "")[:500],
                       "data": {"topic": topic}}
                if research.success:
                    outline = research.summary or str(research.data.get("findings", ""))[:2000]
                    if not outline and research.data.get("findings"):
                        outline = "## " + topic + "\n\n" + "\n".join(
                            f"- {str(f)[:150]}" for f in research.data["findings"][:10]
                        )
                    if not outline:
                        outline = f"## {topic}\n\n- Key points\n\n## Summary"
                    yield {"type": "tool_start", "tool": "presentation_generator",
                           "args": {"title": topic[:80], "brand_domain": brand}}
                    progress_events = []

                    def on_progress_ppt(msg: str) -> None:
                        progress_events.append({"type": "progress", "message": msg})

                    ppt = presenter.execute(
                        title=topic[:80], outline=outline, brand_domain=brand,
                        progress_callback=on_progress_ppt,
                    )
                    for ev in progress_events:
                        yield ev
                    yield {"type": "tool_end", "tool": "presentation_generator",
                           "success": ppt.success, "summary": ppt.summary or "",
                           "data": ppt.data or {}}
                    tool_results = [research, ppt]
                else:
                    tool_results = [research]
            else:
                tool_results = self._tool_executor.decide_and_execute(
                    message, on_tool_start=on_tool_start, on_tool_end=on_tool_end
                )
        elif route.intent not in ("general", "onboarding"):
            yield {"type": "status", "message": "Deciding which tools to use..."}
            tool_results = self._tool_executor.decide_and_execute(
                message, context="",
                on_tool_start=on_tool_start, on_tool_end=on_tool_end,
            )

        for ev in events:
            yield ev

        responses: list[ChatMessage] = []
        for tr in tool_results:
            if tr.success and tr.summary:
                responses.append(ChatMessage(
                    role=MessageRole.AGENT,
                    content=f"**{tr.tool_name.replace('_', ' ').title()}:**\n\n{tr.summary}",
                    actions=[AgentActionRef(
                        action_type=f"tool_{tr.tool_name}",
                        description=tr.summary,
                        details=tr.data or {},
                    )],
                    metadata={"type": "tool_result", "tool": tr.tool_name},
                ))
                yield {"type": "message", "role": "agent", "content": responses[-1].content}
            elif not tr.success and tr.error:
                yield {"type": "message", "role": "system", "content": f"Tool error: {tr.error}"}

        if not responses and not has_attach:
            query_type = self.query_classifier.classify(message)
            if self.use_llm and settings.llm.api_key:
                for msg, token in self._llm_natural_response_streaming(
                    message, route, query_type
                ):
                    if token:
                        yield {"type": "token", "token": token}
                    elif msg:
                        responses.append(msg)
                        yield {"type": "message", "role": msg.role.value, "content": msg.content}
            else:
                main = self._respond_naturally(message, route)
                responses.append(main)
                yield {"type": "message", "role": main.role.value, "content": main.content}

        if attachments:
            for att in attachments:
                doc_resp = self._handle_document(att)
                responses.append(doc_resp)
                yield {"type": "message", "role": "agent", "content": doc_resp.content}

        for r in responses:
            self.memory.add(r)

    # ── CXO Orchestration ──────────────────────────────────────

    def _should_consult_cxos(self, message: str, route: RoutingResult) -> bool:
        """Determine if this message warrants CXO consultation."""
        if not self.use_llm or not settings.llm.api_key:
            return False
        if not self.agent_bus:
            return False
        # Only consult CXOs when the router explicitly identified domain-specific agents.
        # General/conversational messages should be answered directly.
        if route.agents and route.intent != "general":
            return True
        msg_lower = message.lower()
        cxo_triggers = [
            "how should", "what should", "help me", "advise", "strategy",
            "recommend", "optimize", "improve", "reduce", "increase",
            "analyze", "evaluate", "assess", "plan for", "deal with",
            "budget", "revenue", "costs", "hiring", "marketing",
            "legal", "compliance", "pipeline", "vendor", "campaign",
        ]
        return any(t in msg_lower for t in cxo_triggers)

    def _orchestrate_cxos(
        self, message: str, route: RoutingResult
    ) -> ChatMessage | None:
        """Orchestrate CXO agents for a comprehensive response."""
        if not self.agent_bus:
            return None

        # Determine which CXOs to consult
        if route.agents:
            cxo_roles = route.agents[:3]
        else:
            cxo_roles = self.agent_bus.determine_relevant_cxos(message)

        if not cxo_roles:
            return None

        # Build business context
        business_context = ""
        if self.profile_store and self.profile_store.profile:
            p = self.profile_store.profile
            parts = []
            if p.company_name:
                parts.append(f"Company: {p.company_name}")
            if p.industry:
                parts.append(f"Industry: {p.industry}")
            if p.main_product:
                parts.append(f"Product: {p.main_product}")
            if p.arr:
                parts.append(f"ARR: {p.arr}")
            if p.team_size:
                parts.append(f"Team: {p.team_size}")
            business_context = ". ".join(parts)

        # Get vault context
        vault_context = ""
        try:
            hits = self.vault.query(message, top_k=3)
            if hits:
                vault_context = "\n".join(
                    h.get("content", "")[:300] for h in hits
                )
        except Exception:
            pass

        # Consult each CXO
        analyses = []
        for role in cxo_roles:
            analysis = self.agent_bus.consult_cxo(
                role=role,
                user_message=message,
                business_context=business_context,
                vault_context=vault_context,
            )
            analyses.append(analysis)

        # If multiple CXOs, check for cross-consultation needs
        if len(analyses) >= 2:
            for analysis in analyses:
                text_lower = analysis.analysis.lower()
                for other_role in cxo_roles:
                    if other_role != analysis.role and (
                        f"consult {other_role.lower()}" in text_lower
                        or f"ask the {other_role.lower()}" in text_lower
                        or f"input from {other_role.lower()}" in text_lower
                    ):
                        consultation = self.agent_bus.cross_consult(
                            requester=analysis.role,
                            target=other_role,
                            question=f"The {analysis.role} needs your input on: {message[:200]}",
                            context=business_context,
                        )
                        analysis.consulted_peers.append(other_role)

        # Synthesize if multiple CXOs contributed
        if len(analyses) > 1:
            synthesis = self.agent_bus.synthesize_analyses(message, analyses)
        else:
            synthesis = analyses[0].analysis if analyses else ""

        if not synthesis:
            return None

        # Build the response with CXO attribution
        cxo_labels = [
            f"{CXO_ROLE_ICONS.get(a.role, '')} {CXO_ROLE_LABELS.get(a.role, a.role)}"
            for a in analyses
        ]
        metadata = {
            "type": "cxo_orchestrated",
            "agents_consulted": [a.role for a in analyses],
            "agent_labels": cxo_labels,
        }

        return ChatMessage(
            role=MessageRole.AGENT,
            content=synthesis,
            metadata=metadata,
        )

    def _stream_cxo_orchestration(
        self,
        message: str,
        route: RoutingResult,
    ) -> Iterator[dict[str, Any]]:
        """Stream CXO orchestration events for the UI."""
        if not self.agent_bus:
            return

        if route.agents:
            cxo_roles = route.agents[:3]
        else:
            cxo_roles = self.agent_bus.determine_relevant_cxos(message)

        if not cxo_roles:
            return

        # Build context
        business_context = ""
        if self.profile_store and self.profile_store.profile:
            p = self.profile_store.profile
            parts = []
            if p.company_name:
                parts.append(f"Company: {p.company_name}")
            if p.industry:
                parts.append(f"Industry: {p.industry}")
            if p.arr:
                parts.append(f"ARR: {p.arr}")
            business_context = ". ".join(parts)

        vault_context = ""
        try:
            hits = self.vault.query(message, top_k=3)
            if hits:
                vault_context = "\n".join(
                    h.get("content", "")[:300] for h in hits
                )
        except Exception:
            pass

        # Announce the consultation
        yield {
            "type": "orchestration_start",
            "agents": cxo_roles,
            "message": f"Consulting {', '.join(cxo_roles)} for a comprehensive analysis...",
        }

        # Stream each CXO analysis
        events = []
        self.agent_bus.set_event_callback(lambda e: events.append(e))

        analyses = []
        for role in cxo_roles:
            events.clear()
            analysis = self.agent_bus.consult_cxo(
                role=role,
                user_message=message,
                business_context=business_context,
                vault_context=vault_context,
            )
            analyses.append(analysis)
            for ev in events:
                yield ev

        # Cross-consultation
        if len(analyses) >= 2:
            events.clear()
            for analysis in analyses:
                text_lower = analysis.analysis.lower()
                for other_role in cxo_roles:
                    if other_role != analysis.role and (
                        f"consult {other_role.lower()}" in text_lower
                        or f"input from {other_role.lower()}" in text_lower
                    ):
                        self.agent_bus.cross_consult(
                            requester=analysis.role,
                            target=other_role,
                            question=f"{analysis.role} needs input on: {message[:200]}",
                            context=business_context,
                        )
                        analysis.consulted_peers.append(other_role)
            for ev in events:
                yield ev

        # Synthesize
        events.clear()
        synthesis = self.agent_bus.synthesize_analyses(message, analyses)
        for ev in events:
            yield ev

        if synthesis:
            cxo_labels = [
                f"{CXO_ROLE_ICONS.get(a.role, '')} {CXO_ROLE_LABELS.get(a.role, a.role)}"
                for a in analyses
            ]
            yield {
                "type": "message",
                "role": "agent",
                "content": synthesis,
                "metadata": {
                    "type": "cxo_orchestrated",
                    "agents_consulted": [a.role for a in analyses],
                    "agent_labels": cxo_labels,
                },
            }

            msg = ChatMessage(
                role=MessageRole.AGENT,
                content=synthesis,
                metadata={
                    "type": "cxo_orchestrated",
                    "agents_consulted": [a.role for a in analyses],
                },
            )
            self.memory.add(msg)

        yield {
            "type": "orchestration_complete",
            "agents": [a.role for a in analyses],
            "message": "C-Suite analysis complete",
        }

    # ── Core response logic ───────────────────────────────────

    def _welcome_message(self) -> ChatMessage:
        """First message only — friendly, brief, not robotic."""
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                "Hey! I'm your AI co-founder. I have seven specialists on my "
                "team:\n\n"
                "- **CFO** — watches your money, catches overspending, "
                "optimizes cash flow\n"
                "- **COO** — manages vendors, supply chain, operations\n"
                "- **CMO** — runs campaigns, kills bad ads, prevents churn\n"
                "- **CLO** — scans contracts, catches legal risks, "
                "compliance\n"
                "- **CHRO** — recruits talent, monitors team health, "
                "onboards hires\n"
                "- **CSO** — recovers stalled deals, optimizes your "
                "pipeline\n"
                "- **Creative Director** — ensures every output looks "
                "premium with consistent brand design\n\n"
                "I plan before I act — when you ask for something complex, "
                "I'll show you my step-by-step plan and keep you informed "
                "at every stage.\n\n"
                "You can ask me anything — I'll figure out which specialist "
                "to bring in. Drop documents and I'll analyze them. "
                "Or just tell me what's on your mind.\n\n"
                "The more I know about your business, the better I get. "
                "What are you working on?"
            ),
        )

    def _respond_naturally(
        self, message: str, route: RoutingResult
    ) -> ChatMessage:
        """Always respond to what the user actually said.

        When the message warrants CXO expertise, orchestrate the relevant
        C-Suite officers to provide a comprehensive, multi-perspective response.
        """
        query_type = self.query_classifier.classify(message)

        # For product/self-knowledge questions, answer directly
        if query_type == QueryType.SELF:
            if self.use_llm and settings.llm.api_key:
                return self._llm_natural_response(message, route, query_type)
            return self._self_knowledge_response(message)

        # For business questions that warrant CXO input, orchestrate
        if self._should_consult_cxos(message, route):
            cxo_response = self._orchestrate_cxos(message, route)
            if cxo_response:
                return cxo_response

        # Fall back to standard response
        if self.use_llm and settings.llm.api_key:
            return self._llm_natural_response(
                message, route, query_type
            )

        if route.agents:
            return self._agent_response(
                route.agents[0], message, route
            )
        return self._general_response(message, route)

    def _self_knowledge_response(self, message: str) -> ChatMessage:
        """Answer from product knowledge base (no LLM needed)."""
        hits = self.product_kb.query(message, top_k=3)
        if hits:
            content = "\n\n".join(h["content"] for h in hits)
            return ChatMessage(
                role=MessageRole.AGENT,
                content=content,
                metadata={"type": "product_knowledge"},
            )
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                "I can help with that! Try asking about specific "
                "capabilities like 'what can your CFO do?' or "
                "'how do I connect Stripe?' or 'what scenarios "
                "are available?'"
            ),
        )

    def _llm_natural_response(
        self, message: str, route: RoutingResult,
        query_type: QueryType = QueryType.GENERAL,
    ) -> ChatMessage:
        """Use LLM to give a natural, helpful response."""
        try:
            client = self._get_client()

            extra_context = ""
            if query_type in (QueryType.SELF, QueryType.MIXED):
                hits = self.product_kb.query(message, top_k=3)
                extra_context = self.product_kb.format_for_prompt(hits)

            instruction = self._build_agent_instruction(route)
            if extra_context:
                instruction = extra_context + "\n\n" + instruction

            assembled = self.context_assembler.assemble(
                user_message=message,
                agent_role=route.agents[0] if route.agents else "Co-Founder",
                agent_instruction=instruction,
            )
            create_fn = with_retry(client.chat.completions.create, max_attempts=3)
            resp = create_fn(
                model=settings.llm.model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                messages=assembled.to_messages(),
            )
            body = (resp.choices[0].message.content or "").strip()
            role = (
                MessageRole(route.agents[0].lower())
                if route.agents
                else MessageRole.AGENT
            )
            return ChatMessage(
                role=role,
                content=body,
                metadata={
                    "agent": route.agents[0] if route.agents else "agent",
                    "context_tokens": assembled.token_count,
                },
            )
        except Exception:
            logger.warning("LLM response failed, using fallback", exc_info=True)
            if route.agents:
                return self._agent_response(
                    route.agents[0], message, route
                )
            return self._general_response(message, route)

    def _llm_natural_response_streaming(
        self,
        message: str,
        route: RoutingResult,
        query_type: QueryType = QueryType.GENERAL,
    ) -> Iterator[tuple[ChatMessage | None, str | None]]:
        """Stream LLM response token by token. Yields (None, token) then (ChatMessage, None)."""
        if not self.use_llm or not settings.llm.api_key:
            msg = self._respond_naturally(message, route)
            yield (msg, None)
            return
        try:
            client = self._get_client()
            extra_context = ""
            if query_type in (QueryType.SELF, QueryType.MIXED):
                hits = self.product_kb.query(message, top_k=3)
                extra_context = self.product_kb.format_for_prompt(hits)
            instruction = self._build_agent_instruction(route)
            if extra_context:
                instruction = extra_context + "\n\n" + instruction
            assembled = self.context_assembler.assemble(
                user_message=message,
                agent_role=route.agents[0] if route.agents else "Co-Founder",
                agent_instruction=instruction,
            )
            stream = client.chat.completions.create(
                model=settings.llm.model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                messages=assembled.to_messages(),
                stream=True,
            )
            full_content = ""
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_content += delta.content
                    yield (None, delta.content)
            role = (
                MessageRole(route.agents[0].lower())
                if route.agents
                else MessageRole.AGENT
            )
            yield (
                ChatMessage(
                    role=role,
                    content=full_content.strip(),
                    metadata={"agent": route.agents[0] if route.agents else "agent"},
                ),
                None,
            )
        except Exception:
            logger.warning("LLM streaming failed", exc_info=True)
            msg = self._general_response(message, route)
            yield (msg, None)

    def _stream_llm_thinking(self, prompt: str) -> Iterator[str]:
        """Stream a short LLM response token by token (for thinking/status updates)."""
        if not self.use_llm or not settings.llm.api_key:
            return
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.3,
                max_tokens=80,
                messages=[
                    {"role": "system", "content": "Respond in 1-2 short sentences. Be natural."},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception:
            logger.warning("LLM thinking stream failed", exc_info=True)

    def _build_agent_instruction(self, route: RoutingResult) -> str:
        """Build instruction based on which agents are involved."""
        if not route.agents:
            return (
                "You are a helpful AI co-founder. Answer the user's question "
                "directly and naturally. Be conversational, not robotic. "
                "If you don't know something, say so. "
                "If you need more info about their business to help better, "
                "ask naturally within your response — don't redirect to a "
                "rigid onboarding script. "
                "NEVER ask the user to 'connect a presentation tool' or "
                "'connect search API' — researcher and presentation_generator "
                "are built-in and work immediately."
            )
        instructions = []
        for role in route.agents[:2]:
            if role in CXO_SYSTEM_PROMPTS:
                instructions.append(CXO_SYSTEM_PROMPTS[role])
        return " ".join(instructions) + (
            "\n\nIMPORTANT: Answer the user's actual question. "
            "Be conversational and natural. Never ignore what they said. "
            "If you need more context about their business, weave the "
            "question into your response naturally."
        )

    def _onboarding_nudge(self) -> ChatMessage | None:
        """Gentle nudge to learn more — never overrides the conversation."""
        profile = self.profile_store.profile
        missing: list[str] = []
        if not profile.company_name:
            missing.append("your company name")
        if not profile.industry:
            missing.append("what industry you're in")
        if not profile.main_product:
            missing.append("what your product/service is")
        if not profile.arr:
            missing.append("your approximate revenue")

        if not missing:
            return None

        nudge = missing[0]
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                f"By the way, to give you better recommendations, "
                f"it would help if I knew **{nudge}**. "
                f"Feel free to share whenever."
            ),
        )

    # ── Document handling ───────────────────────────────────────

    def _handle_document(self, attachment: dict[str, Any]) -> ChatMessage:
        """Ingest a document and assign it to the right CXO."""
        filename = attachment.get("filename", "document")
        text = attachment.get("text", "")

        actions: list[AgentActionRef] = []
        reminders: list[Any] = []

        if text and self.refinery:
            result = self.refinery.refine_text(text, source=filename)
            self.vault.store(result.chunks)
            actions.append(AgentActionRef(
                action_type="document_ingested",
                description=(
                    f"Ingested {filename}: {result.total_chunks} chunks, "
                    f"{result.total_tokens:,} tokens"
                ),
                details={"chunks": result.total_chunks, "tokens": result.total_tokens},
            ))

            reminders = self.reminder_store.extract_from_text(text, source=filename)
            if reminders:
                actions.append(AgentActionRef(
                    action_type="reminders_extracted",
                    description=f"Found {len(reminders)} deadline(s)/reminder(s) in {filename}",
                    details={"count": len(reminders)},
                ))

        route = self.router.route(f"document about {filename} {text[:200]}")
        assigned = route.agents[0] if route.agents else "COO"

        summary = ""
        if text:
            summary = text[:300].replace("\n", " ")

        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                f"Got it. I've ingested **{filename}** into the vault and "
                f"assigned it to the **{assigned}** for review.\n\n"
                f"**Preview:** {summary}..."
                + (f"\n\n*Found {len(reminders)} deadline(s) — "
                   f"added to your reminders.*"
                   if reminders else "")
            ),
            actions=actions,
            metadata={"assigned_to": assigned, "filename": filename},
        )

    # ── Reminder handling ───────────────────────────────────────

    def _handle_reminder(self, message: str) -> ChatMessage | None:
        """Extract and store a reminder from the message."""
        import re

        now = datetime.now(timezone.utc)
        due = now + timedelta(days=7)

        day_match = re.search(
            r"(?:by|on|next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            message.lower(),
        )
        if day_match:
            target = day_match.group(1)
            days_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            }
            target_day = days_map.get(target, 0)
            current_day = now.weekday()
            delta = (target_day - current_day) % 7
            if delta == 0:
                delta = 7
            due = now + timedelta(days=delta)

        tomorrow_match = re.search(r"\btomorrow\b", message.lower())
        if tomorrow_match:
            due = now + timedelta(days=1)

        title = message[:100]
        clean = re.sub(
            r"(?:remind me to|don't forget to|set a reminder to|remind me about)\s*",
            "", message, flags=re.IGNORECASE,
        ).strip()
        if clean:
            title = clean[:100]

        reminder = Reminder(
            title=title,
            description=message,
            due_date=due,
            priority=ReminderPriority.MEDIUM,
            source="user_request",
        )
        self.reminder_store.add(reminder)

        due_str = due.strftime("%A, %B %d")
        return ChatMessage(
            role=MessageRole.AGENT,
            content=f"Reminder set: **{title}** — due **{due_str}**.",
            actions=[AgentActionRef(
                action_type="reminder_created",
                description=f"Reminder: {title}",
                details={"due": due.isoformat(), "id": reminder.reminder_id},
            )],
        )

    # ── Onboarding ──────────────────────────────────────────────

    def _onboarding_response(self) -> ChatMessage:
        profile = self.profile_store.profile
        if self.memory.message_count <= 1:
            return ChatMessage(
                role=MessageRole.AGENT,
                content=(
                    "Hey! I'm your AI co-founder. I have a team of six "
                    "specialists behind me — CFO, COO, CMO, CLO, CHRO, "
                    "and CSO. Together we'll help you run your business.\n\n"
                    "But first, I need to understand your company. "
                    "Let's start simple:\n\n"
                    f"**{ONBOARDING_QUESTIONS[0][1]}**"
                ),
            )

        for field_name, question in ONBOARDING_QUESTIONS:
            val = getattr(profile, field_name, "")
            if isinstance(val, list):
                if not val:
                    return ChatMessage(
                        role=MessageRole.AGENT,
                        content=(
                            f"Great, thanks! Next question:\n\n**{question}**"
                        ),
                    )
            elif not val:
                return ChatMessage(
                    role=MessageRole.AGENT,
                    content=f"Got it. Next:\n\n**{question}**",
                )

        self.profile_store.update(onboarding_complete=True)
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                f"Alright, I have a good picture now:\n\n"
                f"{profile.summary()}\n\n"
                "My team is ready. You can:\n"
                "- **Ask me anything** about your business\n"
                "- **Drop a document** and I'll route it to the right officer\n"
                "- **Give me an objective** like 'find $100k in savings'\n"
                "- **Ask for a morning briefing** anytime\n\n"
                "What do you need first?"
            ),
        )

    # ── CXO Agent responses ─────────────────────────────────────

    def _agent_response(
        self, agent_role: str, message: str, route: RoutingResult
    ) -> ChatMessage:
        role_enum = MessageRole(agent_role.lower())

        context_hits = []
        try:
            context_hits = self.vault.query(message, top_k=5)
        except Exception:
            pass

        if self.use_llm and settings.llm.api_key:
            try:
                return self._llm_agent_response(
                    agent_role, message, context_hits, role_enum
                )
            except Exception:
                logger.warning("LLM agent response failed", exc_info=True)

        return self._smart_agent_response(
            agent_role, message, context_hits, role_enum
        )

    def _llm_agent_response(
        self,
        agent_role: str,
        message: str,
        context: list[dict[str, Any]],
        role_enum: MessageRole,
    ) -> ChatMessage:
        client = self._get_client()
        assembled = self.context_assembler.assemble(
            user_message=message,
            agent_role=agent_role,
            agent_instruction=CXO_SYSTEM_PROMPTS.get(agent_role, ""),
        )
        logger.info(
            "LLM call for %s: %d context tokens",
            agent_role, assembled.token_count,
        )
        create_fn = with_retry(client.chat.completions.create, max_attempts=3)
        resp = create_fn(
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            messages=assembled.to_messages(),
        )
        body = (resp.choices[0].message.content or "").strip()
        return ChatMessage(
            role=role_enum,
            content=body,
            metadata={
                "agent": agent_role,
                "context_tokens": assembled.token_count,
            },
        )

    def _smart_agent_response(
        self,
        agent_role: str,
        message: str,
        context: list[dict[str, Any]],
        role_enum: MessageRole,
    ) -> ChatMessage:
        """Generate a useful response using vault data, no LLM needed."""
        profile = self.profile_store.profile
        ctx_summary = ""
        sources = []
        if context:
            ctx_summary = "\n".join(
                f"- {h['content'][:150]}"
                for h in context[:5]
            )
            sources = list({
                h.get("metadata", {}).get("source", "")
                for h in context
                if h.get("metadata", {}).get("source")
            })

        biz_context = f" for {profile.company_name}" if profile.company_name else ""

        agent_labels = {
            "CFO": "finance", "COO": "operations", "CMO": "marketing",
            "CLO": "legal", "CHRO": "people", "CSO": "sales",
        }
        domain = agent_labels.get(agent_role, "business")

        if ctx_summary:
            content = (
                f"I've reviewed the {domain} data{biz_context}. "
                f"Here's what I found in the vault:\n\n{ctx_summary}\n\n"
                f"**Sources:** {', '.join(sources) or 'internal data'}\n\n"
                f"Would you like me to dig deeper into any of these, "
                f"or should I take action on something specific?"
            )
        else:
            content = (
                f"I don't have much {domain} data in the vault yet{biz_context}. "
                f"Could you upload some relevant documents? For example:\n\n"
            )
            doc_suggestions = {
                "CFO": "- Financial statements\n- Invoice records\n- Budget spreadsheets",
                "COO": "- Vendor contracts\n- Supply chain docs\n- Operations reports",
                "CMO": "- Campaign performance data\n- Marketing budgets\n- Analytics exports",
                "CLO": "- Contracts and MSAs\n- Compliance docs\n- Regulatory filings",
                "CHRO": "- Org charts\n- Employee handbooks\n- Hiring plans",
                "CSO": "- CRM exports\n- Pipeline reports\n- Call notes",
            }
            content += doc_suggestions.get(agent_role, "- Relevant business documents")
            content += "\n\nJust drop them in the chat and I'll handle the rest."

        return ChatMessage(
            role=role_enum,
            content=content,
            metadata={"agent": agent_role, "context_used": len(context)},
        )

    # ── General response ────────────────────────────────────────

    def _general_response(
        self, message: str, route: RoutingResult
    ) -> ChatMessage:
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                "I hear you. Could you give me a bit more context so I can "
                "route this to the right person on my team? For example:\n\n"
                "- **Finance/Budget** → my CFO handles it\n"
                "- **Vendors/Operations** → my COO is on it\n"
                "- **Marketing/Ads** → my CMO takes the lead\n"
                "- **Contracts/Legal** → my CLO reviews it\n"
                "- **Hiring/Culture** → my CHRO manages it\n"
                "- **Sales/Deals** → my CSO is your person\n\n"
                "Or just tell me what's on your mind and I'll figure it out."
            ),
        )

    # ── Morning briefing ────────────────────────────────────────

    def morning_briefing(self) -> MorningBriefing:
        """Generate the daily proactive briefing."""
        now = datetime.now(timezone.utc)
        profile = self.profile_store.profile
        greeting_name = profile.company_name or "there"

        hour = now.hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        briefing = MorningBriefing(
            greeting=f"{time_greeting}, {greeting_name}.",
        )

        overdue = self.reminder_store.overdue()
        if overdue:
            briefing.critical_alerts.append(BriefingSection(
                title="Overdue Items",
                items=[
                    f"**{r.title}** — was due {r.due_date.strftime('%b %d')} "
                    f"({r.source_detail or r.source})"
                    for r in overdue
                ],
                priority=ReminderPriority.CRITICAL,
            ))

        due_today = [
            r for r in self.reminder_store.active
            if r.due_date.date() == now.date() and r not in overdue
        ]
        if due_today:
            briefing.critical_alerts.append(BriefingSection(
                title="Due Today",
                items=[
                    f"**{r.title}** ({r.source_detail or r.source})"
                    for r in due_today
                ],
                priority=ReminderPriority.HIGH,
            ))

        due_week = self.reminder_store.due_within(days=7)
        upcoming = [
            r for r in due_week
            if r not in overdue and r not in due_today
        ]
        if upcoming:
            briefing.reminders.append(BriefingSection(
                title="Coming Up This Week",
                items=[
                    f"**{r.title}** — {r.due_date.strftime('%A, %b %d')} "
                    f"({r.source_detail or r.source})"
                    for r in upcoming
                ],
                priority=ReminderPriority.MEDIUM,
            ))

        critical_reminders = self.reminder_store.critical
        non_date = [
            r for r in critical_reminders
            if r not in overdue and r not in due_today
        ]
        if non_date:
            briefing.critical_alerts.append(BriefingSection(
                title="Critical Alerts",
                items=[
                    f"**{r.title}** — {r.description[:100]}"
                    for r in non_date
                ],
                priority=ReminderPriority.CRITICAL,
            ))

        vault_count = 0
        try:
            vault_count = self.vault.count()
        except Exception:
            pass

        stats = []
        if vault_count:
            stats.append(f"Knowledge vault: {vault_count} chunks indexed")
        stats.append(
            f"Active reminders: {len(self.reminder_store.active)}"
        )
        if profile.completeness < 1.0:
            pct = int(profile.completeness * 100)
            stats.append(
                f"Business profile: {pct}% complete — "
                "tell me more to improve my recommendations"
            )

        if stats:
            briefing.insights.append(BriefingSection(
                title="System Status",
                items=stats,
                priority=ReminderPriority.LOW,
            ))

        total_critical = sum(
            len(s.items) for s in briefing.critical_alerts
        )
        total_upcoming = sum(len(s.items) for s in briefing.reminders)
        parts = []
        if total_critical:
            parts.append(f"**{total_critical} critical item(s)** need attention")
        if total_upcoming:
            parts.append(f"{total_upcoming} upcoming reminder(s)")
        if not parts:
            parts.append("All clear — no urgent items today")
        briefing.summary = ". ".join(parts) + "."

        return briefing

    def format_briefing(self, briefing: MorningBriefing) -> str:
        """Render a morning briefing as a chat-friendly markdown string."""
        lines = [f"## {briefing.greeting}\n"]
        lines.append(f"*{briefing.summary}*\n")

        for section in briefing.critical_alerts:
            lines.append(f"### 🔴 {section.title}")
            for item in section.items:
                lines.append(f"- {item}")
            lines.append("")

        for section in briefing.reminders:
            lines.append(f"### 📅 {section.title}")
            for item in section.items:
                lines.append(f"- {item}")
            lines.append("")

        for section in briefing.insights:
            lines.append(f"### 📊 {section.title}")
            for item in section.items:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)
