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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from openai import OpenAI

from agentic_cxo.actions.decision_log import DecisionLog
from agentic_cxo.actions.executor import ActionQueue
from agentic_cxo.actions.goal_tracker import GoalTracker
from agentic_cxo.actions.scheduler import JobScheduler
from agentic_cxo.config import settings
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
from agentic_cxo.tools.cost_analyzer import CostAnalyzerTool
from agentic_cxo.tools.framework import ToolExecutor, ToolRegistry
from agentic_cxo.tools.image_generator import ImageGeneratorTool
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
        "You are the AI CFO. Analyze financial matters. Be specific with numbers. "
        "Cite sources. Recommend concrete actions with expected dollar impact."
    ),
    "COO": (
        "You are the AI COO. Handle operations, supply chain, and vendor issues. "
        "Propose alternatives, timelines, and cost-benefit analyses."
    ),
    "CMO": (
        "You are the AI CMO. Handle marketing, campaigns, and growth. "
        "Be data-driven. Propose creatives, targeting, and budget allocation."
    ),
    "CLO": (
        "You are the AI CLO. Handle contracts, compliance, and legal risk. "
        "Flag specific clauses. Propose redlined language. Cite regulations."
    ),
    "CHRO": (
        "You are the AI CHRO. Handle hiring, culture, and people ops. "
        "Be empathetic but data-driven. Propose concrete actions."
    ),
    "CSO": (
        "You are the AI CSO. Handle sales pipeline, deal recovery, and revenue. "
        "Research prospects. Draft personalized outreach. Quantify opportunities."
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
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.router = IntentRouter(use_llm=self.use_llm)
        self.memory_extractor = MemoryExtractor(use_llm=self.use_llm)
        self.alert_engine = ProactiveAlertEngine(
            event_store=self.event_store,
        )

        self._tool_registry = ToolRegistry()
        self._tool_registry.register(WebSearchTool())
        self._tool_registry.register(
            CostAnalyzerTool(vault=self.vault, event_store=self.event_store)
        )
        self._tool_registry.register(VendorDueDiligenceTool(vault=self.vault))
        self._tool_registry.register(TravelAnalyzerTool(vault=self.vault))
        self._tool_registry.register(ImageGeneratorTool())
        self._tool_executor = ToolExecutor(
            registry=self._tool_registry, use_llm=self.use_llm
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

    # ── Core response logic ───────────────────────────────────

    def _welcome_message(self) -> ChatMessage:
        """First message only — friendly, brief, not robotic."""
        return ChatMessage(
            role=MessageRole.AGENT,
            content=(
                "Hey! I'm your AI co-founder. I have six specialists on my "
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
                "pipeline\n\n"
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
        """Always respond to what the user actually said."""
        query_type = self.query_classifier.classify(message)

        if self.use_llm and settings.llm.api_key:
            return self._llm_natural_response(
                message, route, query_type
            )

        if query_type == QueryType.SELF:
            return self._self_knowledge_response(message)

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
            resp = client.chat.completions.create(
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

    def _build_agent_instruction(self, route: RoutingResult) -> str:
        """Build instruction based on which agents are involved."""
        if not route.agents:
            return (
                "You are a helpful AI co-founder. Answer the user's question "
                "directly and naturally. Be conversational, not robotic. "
                "If you don't know something, say so. "
                "If you need more info about their business to help better, "
                "ask naturally within your response — don't redirect to a "
                "rigid onboarding script."
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
        resp = client.chat.completions.create(
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
