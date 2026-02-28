"""
Connector Registry — all external systems the agent can connect to.

Each connector has:
  - Name, description, category
  - Which CXO agent(s) use it
  - Required credentials (env vars or OAuth)
  - Connection status
  - What data it provides
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class ConnectorStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectorCategory(str, Enum):
    EMAIL = "email"
    COMMUNICATION = "communication"
    FINANCE = "finance"
    SALES = "sales"
    MARKETING = "marketing"
    SOCIAL_MEDIA = "social_media"
    OPERATIONS = "operations"
    LEGAL = "legal"
    PEOPLE = "people"
    STORAGE = "storage"
    ANALYTICS = "analytics"
    AUTOMATION = "automation"


@dataclass
class Connector:
    """Definition of an external system connector."""

    connector_id: str
    name: str
    description: str
    category: ConnectorCategory
    used_by: list[str]  # CXO roles
    env_vars: list[str]  # required environment variables
    oauth: bool = False
    data_provided: list[str] = field(default_factory=list)
    icon: str = ""
    setup_url: str = ""

    @property
    def status(self) -> ConnectorStatus:
        if self.oauth:
            cfg_path = DATA_DIR / f"oauth_{self.connector_id}.json"
            if cfg_path.exists():
                return ConnectorStatus.CONNECTED
            return ConnectorStatus.NOT_CONFIGURED

        if not self.env_vars:
            return ConnectorStatus.CONFIGURED

        all_set = all(os.getenv(v) for v in self.env_vars)
        if all_set:
            return ConnectorStatus.CONFIGURED
        return ConnectorStatus.NOT_CONFIGURED

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "used_by": self.used_by,
            "status": self.status.value,
            "env_vars": self.env_vars,
            "oauth": self.oauth,
            "data_provided": self.data_provided,
            "icon": self.icon,
            "setup_url": self.setup_url,
        }


# ═══════════════════════════════════════════════════════════════
# All Connectors
# ═══════════════════════════════════════════════════════════════

ALL_CONNECTORS: list[Connector] = [
    # ── Email ────────────────────────────────────────────────
    Connector(
        "gmail", "Gmail / Google Workspace", "Send and receive emails, access contacts",
        ConnectorCategory.EMAIL, ["CFO", "CSO", "CHRO", "CLO"],
        ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"],
        data_provided=["send_email", "read_inbox", "contacts"],
        icon="M", setup_url="https://myaccount.google.com/apppasswords",
    ),
    Connector(
        "outlook", "Outlook / Microsoft 365",
        "Send emails, calendar, contacts via Microsoft Graph API",
        ConnectorCategory.EMAIL, ["CFO", "CSO", "CHRO", "CLO"],
        ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_TENANT_ID"],
        oauth=True,
        data_provided=["send_email", "read_inbox", "calendar", "contacts"],
        icon="O", setup_url="https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps",
    ),

    # ── Communication ────────────────────────────────────────
    Connector(
        "slack", "Slack", "Monitor channels, post messages, culture analysis",
        ConnectorCategory.COMMUNICATION, ["CHRO", "COO", "CMO"],
        ["SLACK_WEBHOOK_URL"],
        data_provided=["post_message", "monitor_channels", "sentiment"],
        icon="S",
    ),
    Connector(
        "teams", "Microsoft Teams", "Team communication and collaboration",
        ConnectorCategory.COMMUNICATION, ["CHRO", "COO"],
        ["TEAMS_WEBHOOK_URL"],
        data_provided=["post_message", "monitor_channels"],
        icon="T",
    ),

    # ── Finance ──────────────────────────────────────────────
    Connector(
        "stripe", "Stripe", "Live MRR, subscriptions, churn, payments",
        ConnectorCategory.FINANCE, ["CFO"],
        ["STRIPE_API_KEY"],
        data_provided=["mrr", "churn", "subscriptions", "payments", "invoices"],
        icon="$",
    ),
    Connector(
        "quickbooks", "QuickBooks", "Accounting, expenses, invoices, P&L",
        ConnectorCategory.FINANCE, ["CFO"],
        ["QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET"],
        oauth=True,
        data_provided=["expenses", "invoices", "profit_loss", "balance_sheet"],
        icon="Q",
    ),
    Connector(
        "xero", "Xero", "Cloud accounting and bookkeeping",
        ConnectorCategory.FINANCE, ["CFO"],
        ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET"],
        oauth=True,
        data_provided=["expenses", "invoices", "profit_loss"],
        icon="X",
    ),
    Connector(
        "plaid", "Plaid (Bank)", "Real-time bank balance, transactions, cash flow",
        ConnectorCategory.FINANCE, ["CFO"],
        ["PLAID_CLIENT_ID", "PLAID_SECRET"],
        data_provided=["bank_balance", "transactions", "cash_flow"],
        icon="B",
    ),
    Connector(
        "brex", "Brex / Expensify", "Employee expenses, travel receipts, cards",
        ConnectorCategory.FINANCE, ["CFO"],
        ["BREX_API_KEY"],
        data_provided=["expenses", "receipts", "card_transactions"],
        icon="E",
    ),

    # ── Sales ────────────────────────────────────────────────
    Connector(
        "salesforce", "Salesforce", "CRM pipeline, deals, contacts, forecasts",
        ConnectorCategory.SALES, ["CSO"],
        ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"],
        oauth=True,
        data_provided=["pipeline", "deals", "contacts", "forecasts"],
        icon="SF",
    ),
    Connector(
        "hubspot", "HubSpot CRM", "Deals, contacts, marketing automation",
        ConnectorCategory.SALES, ["CSO", "CMO"],
        ["HUBSPOT_API_KEY"],
        data_provided=["pipeline", "deals", "contacts", "marketing"],
        icon="HS",
    ),
    Connector(
        "linkedin_sales", "LinkedIn Sales Navigator",
        "Prospect research, company intel, lead recommendations",
        ConnectorCategory.SALES, ["CSO", "CHRO"],
        ["LINKEDIN_ACCESS_TOKEN"],
        oauth=True,
        data_provided=["prospect_research", "company_intel"],
        icon="Li",
    ),
    Connector(
        "calendly", "Calendly", "Meeting scheduling and availability",
        ConnectorCategory.SALES, ["CSO", "CHRO"],
        ["CALENDLY_API_KEY"],
        data_provided=["schedule_meeting", "availability"],
        icon="Ca",
    ),

    # ── Marketing ────────────────────────────────────────────
    Connector(
        "ga4", "Google Analytics 4", "Website traffic, conversions, user behavior",
        ConnectorCategory.MARKETING, ["CMO"],
        ["GA4_PROPERTY_ID", "GA4_CREDENTIALS_JSON"],
        data_provided=["traffic", "conversions", "user_behavior", "funnel"],
        icon="GA",
    ),
    Connector(
        "google_ads", "Google Ads", "Search/display ad campaigns, ROAS, keywords",
        ConnectorCategory.MARKETING, ["CMO"],
        ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID"],
        data_provided=["campaigns", "roas", "keywords", "spend"],
        icon="GA",
    ),
    Connector(
        "meta_ads", "Meta Ads (Facebook/Instagram)",
        "Social ad campaigns, audiences, creative performance",
        ConnectorCategory.MARKETING, ["CMO"],
        ["META_ADS_ACCESS_TOKEN"],
        data_provided=["campaigns", "audiences", "creative_performance"],
        icon="M",
    ),
    Connector(
        "tiktok_ads", "TikTok Ads", "TikTok advertising campaigns",
        ConnectorCategory.MARKETING, ["CMO"],
        ["TIKTOK_ADS_ACCESS_TOKEN"],
        data_provided=["campaigns", "creative_performance"],
        icon="TT",
    ),
    Connector(
        "linkedin_ads", "LinkedIn Ads", "B2B advertising campaigns",
        ConnectorCategory.MARKETING, ["CMO"],
        ["LINKEDIN_ADS_ACCESS_TOKEN"],
        data_provided=["campaigns", "audience_targeting"],
        icon="Li",
    ),
    Connector(
        "mailchimp", "Mailchimp / SendGrid", "Email marketing, newsletters, automation",
        ConnectorCategory.MARKETING, ["CMO"],
        ["MAILCHIMP_API_KEY"],
        data_provided=["campaigns", "open_rates", "subscribers"],
        icon="MC",
    ),
    Connector(
        "semrush", "Semrush / Ahrefs", "SEO rankings, backlinks, competitor analysis",
        ConnectorCategory.MARKETING, ["CMO"],
        ["SEMRUSH_API_KEY"],
        data_provided=["rankings", "backlinks", "competitor_analysis"],
        icon="SR",
    ),
    Connector(
        "branch", "Branch / Appsflyer", "Mobile app attribution, deep links",
        ConnectorCategory.ANALYTICS, ["CMO"],
        ["BRANCH_KEY"],
        data_provided=["attribution", "deep_links", "installs"],
        icon="Br",
    ),

    # ── Social Media ─────────────────────────────────────────
    Connector(
        "twitter_x", "X (Twitter)", "Brand monitoring, posting, analytics",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["TWITTER_BEARER_TOKEN"],
        data_provided=["monitoring", "posting", "analytics"],
        icon="X",
    ),
    Connector(
        "linkedin_page", "LinkedIn Page", "Company page, posts, engagement",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["LINKEDIN_PAGE_ACCESS_TOKEN"],
        oauth=True,
        data_provided=["posting", "engagement", "followers"],
        icon="Li",
    ),
    Connector(
        "instagram", "Instagram", "Brand content, stories, analytics",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["INSTAGRAM_ACCESS_TOKEN"],
        oauth=True,
        data_provided=["posting", "stories", "analytics"],
        icon="IG",
    ),
    Connector(
        "facebook_page", "Facebook Page", "Page management, posts, insights",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["FACEBOOK_PAGE_TOKEN"],
        data_provided=["posting", "insights", "audience"],
        icon="FB",
    ),
    Connector(
        "tiktok", "TikTok", "Content posting, analytics",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["TIKTOK_ACCESS_TOKEN"],
        oauth=True,
        data_provided=["posting", "analytics"],
        icon="TT",
    ),
    Connector(
        "reddit", "Reddit", "Community monitoring, posting",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
        data_provided=["monitoring", "posting"],
        icon="R",
    ),

    # ── Analytics/BI ─────────────────────────────────────────
    Connector(
        "tableau", "Tableau", "Business intelligence dashboards",
        ConnectorCategory.ANALYTICS, ["CFO", "CMO", "COO"],
        ["TABLEAU_SERVER_URL", "TABLEAU_TOKEN"],
        data_provided=["dashboards", "reports", "data_exports"],
        icon="T",
    ),
    Connector(
        "looker", "Looker / Google Data Studio",
        "Data visualization and reporting",
        ConnectorCategory.ANALYTICS, ["CFO", "CMO"],
        ["LOOKER_CLIENT_ID", "LOOKER_CLIENT_SECRET"],
        data_provided=["dashboards", "reports"],
        icon="L",
    ),

    # ── Operations ───────────────────────────────────────────
    Connector(
        "jira", "Jira / Linear", "Sprint tracking, tickets, engineering velocity",
        ConnectorCategory.OPERATIONS, ["COO", "CHRO"],
        ["JIRA_URL", "JIRA_API_TOKEN", "JIRA_EMAIL"],
        data_provided=["sprints", "tickets", "velocity", "backlog"],
        icon="J",
    ),
    Connector(
        "asana", "Asana", "Project management, tasks, timelines",
        ConnectorCategory.OPERATIONS, ["COO"],
        ["ASANA_ACCESS_TOKEN"],
        data_provided=["projects", "tasks", "timelines"],
        icon="A",
    ),
    Connector(
        "notion", "Notion", "Knowledge base, wikis, databases",
        ConnectorCategory.OPERATIONS, ["COO", "CHRO", "CSO"],
        ["NOTION_API_KEY"],
        data_provided=["pages", "databases", "wikis"],
        icon="N",
    ),
    Connector(
        "confluence", "Confluence", "Team documentation and wikis",
        ConnectorCategory.OPERATIONS, ["COO"],
        ["CONFLUENCE_URL", "CONFLUENCE_API_TOKEN"],
        data_provided=["pages", "spaces"],
        icon="C",
    ),
    Connector(
        "aws_billing", "AWS Billing", "Cloud infrastructure costs",
        ConnectorCategory.OPERATIONS, ["CFO", "COO"],
        ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        data_provided=["monthly_cost", "service_breakdown"],
        icon="AW",
    ),
    Connector(
        "gcp_billing", "GCP Billing", "Google Cloud costs",
        ConnectorCategory.OPERATIONS, ["CFO", "COO"],
        ["GCP_CREDENTIALS_JSON"],
        data_provided=["monthly_cost", "service_breakdown"],
        icon="GC",
    ),

    # ── Legal ────────────────────────────────────────────────
    Connector(
        "docusign", "DocuSign", "E-signatures, contract tracking",
        ConnectorCategory.LEGAL, ["CLO"],
        ["DOCUSIGN_INTEGRATION_KEY", "DOCUSIGN_SECRET_KEY"],
        oauth=True,
        data_provided=["contract_status", "signatures", "templates"],
        icon="DS",
    ),
    Connector(
        "pandadoc", "PandaDoc", "Proposals, contracts, document tracking",
        ConnectorCategory.LEGAL, ["CLO", "CSO"],
        ["PANDADOC_API_KEY"],
        data_provided=["documents", "proposals", "signatures"],
        icon="PD",
    ),

    # ── People ───────────────────────────────────────────────
    Connector(
        "bamboohr", "BambooHR", "Employee data, PTO, performance reviews",
        ConnectorCategory.PEOPLE, ["CHRO"],
        ["BAMBOOHR_API_KEY", "BAMBOOHR_SUBDOMAIN"],
        data_provided=["employees", "pto", "reviews", "org_chart"],
        icon="BH",
    ),
    Connector(
        "gusto", "Gusto / Rippling", "Payroll, benefits, tax filings",
        ConnectorCategory.PEOPLE, ["CHRO", "CFO"],
        ["GUSTO_API_KEY"],
        data_provided=["payroll", "benefits", "tax_filings"],
        icon="G",
    ),
    Connector(
        "greenhouse", "Greenhouse / Lever", "Recruiting pipeline, candidates",
        ConnectorCategory.PEOPLE, ["CHRO"],
        ["GREENHOUSE_API_KEY"],
        data_provided=["candidates", "pipeline", "job_postings"],
        icon="GH",
    ),
    Connector(
        "github", "GitHub", "Engineering activity, PRs, contributors",
        ConnectorCategory.PEOPLE, ["CHRO", "COO"],
        ["GITHUB_TOKEN"],
        data_provided=["repos", "pull_requests", "contributors", "activity"],
        icon="GH",
    ),

    # ── Storage ──────────────────────────────────────────────
    Connector(
        "google_drive", "Google Drive", "Documents, spreadsheets, shared files",
        ConnectorCategory.STORAGE, ["COO", "CFO", "CLO"],
        ["GOOGLE_DRIVE_CREDENTIALS_JSON"],
        oauth=True,
        data_provided=["files", "folders", "shared_drives"],
        icon="GD",
    ),
    Connector(
        "onedrive", "OneDrive / SharePoint", "Microsoft 365 file storage",
        ConnectorCategory.STORAGE, ["COO", "CFO", "CLO"],
        ["ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET"],
        oauth=True,
        data_provided=["files", "folders", "sharepoint_sites"],
        icon="OD",
    ),
    Connector(
        "dropbox", "Dropbox", "File storage and sharing",
        ConnectorCategory.STORAGE, ["COO"],
        ["DROPBOX_ACCESS_TOKEN"],
        data_provided=["files", "folders", "sharing"],
        icon="DB",
    ),

    # ── Automation ───────────────────────────────────────────
    Connector(
        "zapier", "Zapier", "Connect any app with automated workflows",
        ConnectorCategory.AUTOMATION, ["COO"],
        ["ZAPIER_WEBHOOK_URL"],
        data_provided=["trigger_workflows", "app_connections"],
        icon="Z",
    ),
    Connector(
        "make", "Make (Integromat)", "Advanced workflow automation",
        ConnectorCategory.AUTOMATION, ["COO"],
        ["MAKE_WEBHOOK_URL"],
        data_provided=["trigger_workflows", "app_connections"],
        icon="M",
    ),
    Connector(
        "webhooks", "Custom Webhooks", "HTTP POST/GET to any system",
        ConnectorCategory.AUTOMATION, ["COO"],
        [],
        data_provided=["trigger_any_api"],
        icon="W",
    ),
]


class ConnectorRegistry:
    """Manages all available connectors and their status."""

    def __init__(self) -> None:
        self._connectors = {c.connector_id: c for c in ALL_CONNECTORS}

    @property
    def all_connectors(self) -> list[Connector]:
        return list(self._connectors.values())

    def get(self, connector_id: str) -> Connector | None:
        return self._connectors.get(connector_id)

    def by_category(self, category: ConnectorCategory) -> list[Connector]:
        return [
            c for c in self._connectors.values()
            if c.category == category
        ]

    def by_agent(self, agent_role: str) -> list[Connector]:
        return [
            c for c in self._connectors.values()
            if agent_role in c.used_by
        ]

    @property
    def connected(self) -> list[Connector]:
        return [
            c for c in self._connectors.values()
            if c.status in (ConnectorStatus.CONFIGURED, ConnectorStatus.CONNECTED)
        ]

    @property
    def not_configured(self) -> list[Connector]:
        return [
            c for c in self._connectors.values()
            if c.status == ConnectorStatus.NOT_CONFIGURED
        ]

    def summary(self) -> dict[str, Any]:
        total = len(self._connectors)
        configured = len(self.connected)
        return {
            "total_connectors": total,
            "configured": configured,
            "not_configured": total - configured,
            "by_category": {
                cat.value: len(self.by_category(cat))
                for cat in ConnectorCategory
            },
        }

    def to_list(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.all_connectors]
