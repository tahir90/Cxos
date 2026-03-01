"""
Product Knowledge Base + Query Classifier.

Two problems solved:
1. The agent needs its OWN RAG — a vector index of product documentation,
   capabilities, how-to guides, and answers to common questions.
2. The agent needs to CLASSIFY every query: is this about me (the product),
   about the user's business, or general?

Architecture:
  User asks a question
    ↓
  QueryClassifier determines: SELF | BUSINESS | GENERAL | MIXED
    ↓
  If SELF → search product_vault for answer
  If BUSINESS → search business vault + long-term memory
  If GENERAL → let LLM answer with self-awareness context
  If MIXED → search both vaults, combine
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    SELF = "self"          # About the product itself
    BUSINESS = "business"  # About the user's business
    GENERAL = "general"    # General knowledge
    MIXED = "mixed"        # About both


SELF_KEYWORDS = [
    "what can you do", "what do you do", "your capabilities",
    "your features", "how do you work", "what are you",
    "your specialists", "your agents", "your cxo",
    "your cfo", "your coo", "your cmo", "your clo",
    "your chro", "your cso", "how to use", "how do i",
    "can you help", "what tools", "what integrations",
    "what connectors", "settings", "connect", "pricing",
    "your plan", "upgrade", "how to connect",
    "what scenarios", "morning briefing", "how does",
    "teach me", "show me how", "get started",
    "your role", "your team", "role of each",
    "help my business", "help me with",
    "what kind of", "your memory", "remember",
    "notification", "your actions", "can you send",
    "can you email", "can you search", "can you analyze",
]

BUSINESS_KEYWORDS = [
    "my company", "my business", "our revenue", "our team",
    "our product", "our customers", "our budget", "our pipeline",
    "my industry", "our vendor", "our contract", "our campaign",
    "our expenses", "our burn rate", "our arr", "our mrr",
    "invoice", "overdue", "employee", "hire",
    "stalled deal", "sales pipeline",
]


class QueryClassifier:
    """Determines what kind of question the user is asking."""

    def classify(self, message: str) -> QueryType:
        lower = message.lower()

        self_score = sum(1 for kw in SELF_KEYWORDS if kw in lower)
        biz_score = sum(1 for kw in BUSINESS_KEYWORDS if kw in lower)

        if self_score > 0 and biz_score > 0:
            return QueryType.MIXED
        if self_score >= 2:
            return QueryType.SELF
        if self_score == 1 and biz_score == 0:
            return QueryType.SELF
        if biz_score > 0:
            return QueryType.BUSINESS
        return QueryType.GENERAL


# ═══════════════════════════════════════════════════════════════
# Product Knowledge Base
# ═══════════════════════════════════════════════════════════════

PRODUCT_DOCS: list[dict[str, str]] = [
    {
        "id": "overview",
        "content": (
            "Agentic CXO is an AI co-founder product with 6 specialist "
            "AI officers: CFO (finance), COO (operations), CMO (marketing), "
            "CLO (legal), CHRO (people/HR), CSO (sales). The founder talks "
            "naturally in a chat interface and the system automatically "
            "routes to the right specialist. It remembers everything, "
            "catches repeated mistakes, and can actually execute actions "
            "like sending emails and posting to Slack."
        ),
    },
    {
        "id": "cfo-capabilities",
        "content": (
            "The AI CFO can: connect to Stripe and Chargebee for live MRR, "
            "ARR, subscriptions, and churn data. Connect to QuickBooks for "
            "P&L, balance sheet, expenses, and invoices. Run the Cash-Flow "
            "Guardian scenario to detect expense spikes, audit vendors for "
            "duplicate billing, and re-forecast runway. Run the Tax "
            "Strategist to generate R&D tax credit reports. Run the "
            "Collections Enforcer to find overdue invoices and draft "
            "escalating reminder emails. Analyze travel requests for "
            "overpriced flights and suggest cheaper alternatives. Track "
            "financial goals and KPIs."
        ),
    },
    {
        "id": "coo-capabilities",
        "content": (
            "The AI COO can: connect to Jira for sprint velocity, tickets, "
            "and backlogs. Connect to GitHub and Bitbucket for PRs, "
            "contributors, and engineering activity. Connect to Notion for "
            "knowledge base and wikis. Runs 7 automated daily/weekly jobs: "
            "invoice overdue check, contract expiry monitor, stalled deal "
            "detector, burn rate monitor, weekly executive report, culture "
            "pulse, campaign review. Manages vendor relationships, supply "
            "chain, logistics, and procurement."
        ),
    },
    {
        "id": "cmo-capabilities",
        "content": (
            "The AI CMO can: connect to Google Analytics 4 for real-time "
            "traffic, conversions, top pages, and traffic sources. Connect "
            "to Google Ads and Meta Ads for campaign performance and ROAS. "
            "Connect to Mixpanel and Amplitude for product analytics, "
            "funnels, and retention. Run the Viral Responder scenario to "
            "capitalize on competitor outages. Run the Churn Architect to "
            "save at-risk users with personalized outreach. Run the Global "
            "Localizer to adapt creatives for new markets. Search the web "
            "for competitor intel and market trends."
        ),
    },
    {
        "id": "clo-capabilities",
        "content": (
            "The AI CLO can: run the Contract Sentinel to scan MSAs for "
            "auto-renewal clauses, liability shifts, and generate redlined "
            "versions. Run the IP Defender to sweep app stores for trademark "
            "violations and draft Cease & Desist letters. Run the Regulatory "
            "Auditor to map AI regulations to data flows and build "
            "compliance remediation plans. Connect to Avalara for automated "
            "tax compliance. Review any document dropped into chat for "
            "legal risks and problematic clauses."
        ),
    },
    {
        "id": "chro-capabilities",
        "content": (
            "The AI CHRO can: connect to Slack to monitor team sentiment "
            "and culture health. Run the Headhunter scenario to find "
            "engineering candidates from GitHub, enrich their profiles, and "
            "draft personalized outreach referencing their commits. Run the "
            "Culture Pulse to analyze Slack sentiment, identify friction "
            "sources, and create 3-point action plans. Run the Automated "
            "Onboarder to provision accounts, build training curricula, and "
            "schedule executive intro calls for new hires."
        ),
    },
    {
        "id": "cso-capabilities",
        "content": (
            "The AI CSO can: connect to HubSpot and Salesforce for live "
            "pipeline, deals, contacts, and forecasts. Run the Ghostbuster "
            "scenario to find stalled Fortune 500 deals, research prospect "
            "news, and draft personalized follow-ups. Run the Pipeline "
            "Optimizer to analyze closed-lost deals, identify feature gaps, "
            "cross-reference the engineering roadmap, and identify "
            "re-engagement targets. Research companies online before "
            "meetings using web search."
        ),
    },
    {
        "id": "how-to-connect",
        "content": (
            "To connect an integration: click Settings in the header, find "
            "the connector you want, click Connect, enter your credentials "
            "(API key, token, etc.), click Test & Connect. The system "
            "validates credentials with a real API call. Green checkmark "
            "means connected. 26 connectors have live click-to-connect "
            "support: Slack, Stripe, GitHub, Bitbucket, Google Drive, "
            "OneDrive, Gmail, HubSpot, Jira, Notion, Shopify, Chargebee, "
            "Mixpanel, Amplitude, Zendesk, Intercom, Avalara, Webhooks, "
            "GA4, Google Ads, Meta Ads, Salesforce, QuickBooks, Apple App "
            "Store, Google Play, Firebase."
        ),
    },
    {
        "id": "memory-system",
        "content": (
            "The agent remembers everything from every conversation. It "
            "extracts facts, decisions, preferences, deadlines, pain points, "
            "goals, and financial figures automatically. When you mention "
            "something once, it's stored permanently. The Pattern Engine "
            "tracks business events with outcomes — if a campaign failed "
            "2 years ago and you're about to try the same thing, the agent "
            "warns you with the full history of what went wrong. Morning "
            "briefings surface overdue items, approaching deadlines, and "
            "critical alerts proactively."
        ),
    },
    {
        "id": "actions-permissions",
        "content": (
            "The agent can execute real actions: send emails via Gmail or "
            "Outlook, post to Slack channels, fire webhooks to any system, "
            "create tracked tasks, and generate reports. Every action "
            "requires permission: Allow Once (do it this time, ask again "
            "next time), Allow Always (auto-approve this action type), or "
            "Deny (block for today, ask again tomorrow). High-risk actions "
            "like sending emails always require explicit approval."
        ),
    },
    {
        "id": "pricing-plans",
        "content": (
            "Pricing: Free plan ($0/mo) includes 50 messages/day, 2 "
            "connectors, 1 user, 10 documents. Starter plan ($49/mo) "
            "includes 500 messages/day, 10 connectors, 5 users, 100 "
            "documents. Pro plan ($199/mo) includes 5000 messages/day, "
            "50 connectors, 25 users, 1000 documents. Enterprise plan "
            "(custom pricing) includes unlimited everything, custom "
            "integrations, dedicated support, and on-premise option."
        ),
    },
    {
        "id": "scenarios",
        "content": (
            "14 pre-built business scenarios: CFO has Cash-Flow Guardian, "
            "Tax Strategist, Collections Enforcer. CMO has Viral Responder, "
            "Churn Architect, Global Localizer. CHRO has Headhunter, "
            "Culture Pulse, Automated Onboarder. CLO has Contract Sentinel, "
            "IP Defender, Regulatory Auditor. CSO has Ghostbuster and "
            "Pipeline Optimizer. Each scenario is a multi-step workflow "
            "with dependency resolution and risk-gated approvals."
        ),
    },
    {
        "id": "tools",
        "content": (
            "Tools the agent can use: Web Search, Cost Analyzer, Vendor Due "
            "Diligence, Travel Analyzer. Researcher and Presentation Generator "
            "are BUILT-IN — they work immediately without any connection. When "
            "the user wants a PPT, the agent researches the topic and generates "
            "a .pptx file. Never ask to 'connect a presentation tool' or "
            "'connect search API' — those tools are built-in."
        ),
    },
    {
        "id": "presentation-built-in",
        "content": (
            "Presentation generation is built-in. When the user asks for a "
            "PowerPoint, deck, or slides, the agent uses the researcher tool "
            "to gather content and the presentation_generator to create a "
            ".pptx file. No connection or setup required. Never ask the user "
            "to connect a presentation tool."
        ),
    },
    {
        "id": "document-upload",
        "content": (
            "Drop any document into the chat — PDFs, text files, CSVs, "
            "DOCX files. The Context Refinery pipeline processes it: "
            "semantic chunking splits at thought boundaries (not character "
            "counts), metadata enrichment tags urgency, entities, and "
            "domain, recursive summarization builds a pyramid (page → "
            "chapter → executive summary). The document is automatically "
            "assigned to the right CXO agent. Deadlines and auto-renewal "
            "clauses are extracted as reminders."
        ),
    },
]


class ProductKnowledgeBase:
    """Vector-indexed product documentation for self-aware responses."""

    def __init__(self) -> None:
        self._client = chromadb.Client(
            ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name="product_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        self._load_docs()

    def _load_docs(self) -> None:
        if self._collection.count() >= len(PRODUCT_DOCS):
            return
        ids = [d["id"] for d in PRODUCT_DOCS]
        documents = [d["content"] for d in PRODUCT_DOCS]
        self._collection.upsert(ids=ids, documents=documents)
        logger.info(
            "Loaded %d product knowledge docs", len(PRODUCT_DOCS)
        )

    def query(self, question: str, top_k: int = 3) -> list[dict[str, Any]]:
        results = self._collection.query(
            query_texts=[question], n_results=top_k
        )
        hits: list[dict[str, Any]] = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "distance": (
                    results["distances"][0][i]
                    if results["distances"] else None
                ),
            })
        return hits

    def format_for_prompt(self, hits: list[dict[str, Any]]) -> str:
        if not hits:
            return ""
        lines = ["PRODUCT KNOWLEDGE (answer from this when asked about yourself):"]
        for h in hits:
            lines.append(f"  - {h['content']}")
        return "\n".join(lines)
