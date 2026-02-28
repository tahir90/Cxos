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
    ERP = "erp"
    PROCUREMENT = "procurement"
    DATA_PLATFORM = "data_platform"
    DEVOPS = "devops"
    CUSTOMER_SUPPORT = "customer_support"
    ECOMMERCE = "ecommerce"
    SECURITY = "security"
    PIM = "pim"
    INVENTORY_WMS = "inventory_wms"
    SUPPLY_CHAIN = "supply_chain"
    OMS = "oms"
    RETURNS_FULFILLMENT = "returns_fulfillment"
    MARKETPLACE = "marketplace"
    TAX_COMPLIANCE = "tax_compliance"
    TRAVEL_EXPENSE = "travel_expense"
    LEARNING = "learning"
    REAL_ESTATE = "real_estate"
    CMS = "cms"
    DAM = "dam"
    PRODUCT_MANAGEMENT = "product_management"
    DESIGN = "design"
    OBSERVABILITY = "observability"


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
    Connector(
        "n8n", "n8n", "Open-source workflow automation, self-hosted",
        ConnectorCategory.AUTOMATION, ["COO"],
        ["N8N_URL", "N8N_API_KEY"],
        data_provided=["trigger_workflows", "custom_automations"],
        icon="n8",
    ),
    Connector(
        "power_automate", "Microsoft Power Automate",
        "Enterprise workflow automation in Microsoft 365",
        ConnectorCategory.AUTOMATION, ["COO"],
        ["POWER_AUTOMATE_CLIENT_ID", "POWER_AUTOMATE_CLIENT_SECRET"],
        oauth=True,
        data_provided=["trigger_flows", "m365_automations"],
        icon="PA",
    ),

    # ── ERP Systems ──────────────────────────────────────────
    Connector(
        "sap_erp", "SAP S/4HANA", "Enterprise resource planning, finance, supply chain",
        ConnectorCategory.ERP, ["CFO", "COO"],
        ["SAP_HOST", "SAP_CLIENT", "SAP_USER", "SAP_PASS"],
        data_provided=[
            "general_ledger", "accounts_payable", "accounts_receivable",
            "purchase_orders", "inventory", "production_orders",
        ],
        icon="SAP",
    ),
    Connector(
        "sap_business_one", "SAP Business One", "ERP for small-mid enterprises",
        ConnectorCategory.ERP, ["CFO", "COO"],
        ["SAP_B1_SERVICE_URL", "SAP_B1_USER", "SAP_B1_PASS"],
        data_provided=["financials", "inventory", "purchasing", "sales_orders"],
        icon="SB1",
    ),
    Connector(
        "oracle_erp", "Oracle ERP Cloud",
        "Enterprise financials, procurement, project management",
        ConnectorCategory.ERP, ["CFO", "COO"],
        ["ORACLE_ERP_URL", "ORACLE_ERP_CLIENT_ID", "ORACLE_ERP_CLIENT_SECRET"],
        oauth=True,
        data_provided=["financials", "procurement", "projects", "supply_chain"],
        icon="ORC",
    ),
    Connector(
        "netsuite", "Oracle NetSuite", "Cloud ERP for mid-market, financials and operations",
        ConnectorCategory.ERP, ["CFO", "COO"],
        ["NETSUITE_ACCOUNT_ID", "NETSUITE_CONSUMER_KEY", "NETSUITE_CONSUMER_SECRET"],
        data_provided=["financials", "inventory", "crm", "ecommerce"],
        icon="NS",
    ),
    Connector(
        "dynamics_365", "Microsoft Dynamics 365",
        "ERP and CRM: finance, supply chain, sales, service",
        ConnectorCategory.ERP, ["CFO", "COO", "CSO"],
        ["DYNAMICS_URL", "DYNAMICS_CLIENT_ID", "DYNAMICS_CLIENT_SECRET"],
        oauth=True,
        data_provided=["finance", "supply_chain", "sales", "customer_service"],
        icon="D365",
    ),
    Connector(
        "odoo", "Odoo", "Open-source ERP: accounting, inventory, CRM, HR",
        ConnectorCategory.ERP, ["CFO", "COO", "CHRO"],
        ["ODOO_URL", "ODOO_DB", "ODOO_API_KEY"],
        data_provided=["accounting", "inventory", "crm", "hr", "manufacturing"],
        icon="OD",
    ),
    Connector(
        "zoho_one", "Zoho One", "All-in-one business suite: CRM, books, desk, projects",
        ConnectorCategory.ERP, ["CFO", "COO", "CSO"],
        ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET"],
        oauth=True,
        data_provided=["crm", "accounting", "projects", "desk", "hr"],
        icon="ZO",
    ),

    # ── Procurement ──────────────────────────────────────────
    Connector(
        "coupa", "Coupa", "Procurement, invoicing, expense management",
        ConnectorCategory.PROCUREMENT, ["CFO", "COO"],
        ["COUPA_URL", "COUPA_API_KEY"],
        data_provided=[
            "purchase_orders", "invoices", "suppliers", "contracts",
            "expense_reports", "budgets",
        ],
        icon="CP",
    ),
    Connector(
        "sap_ariba", "SAP Ariba", "Procurement and supply chain collaboration",
        ConnectorCategory.PROCUREMENT, ["COO", "CFO"],
        ["ARIBA_REALM", "ARIBA_CLIENT_ID", "ARIBA_CLIENT_SECRET"],
        oauth=True,
        data_provided=["sourcing", "contracts", "suppliers", "purchase_orders"],
        icon="AR",
    ),
    Connector(
        "jaggaer", "Jaggaer", "Source-to-pay procurement platform",
        ConnectorCategory.PROCUREMENT, ["COO"],
        ["JAGGAER_URL", "JAGGAER_API_KEY"],
        data_provided=["sourcing", "procurement", "supplier_management"],
        icon="JG",
    ),
    Connector(
        "procurify", "Procurify", "Purchasing and spend management for mid-market",
        ConnectorCategory.PROCUREMENT, ["CFO", "COO"],
        ["PROCURIFY_API_KEY"],
        data_provided=["purchase_orders", "approvals", "budgets", "spend"],
        icon="PF",
    ),

    # ── HR / People (Enterprise) ─────────────────────────────
    Connector(
        "successfactors", "SAP SuccessFactors",
        "Enterprise HCM: recruiting, performance, learning, payroll",
        ConnectorCategory.PEOPLE, ["CHRO", "CFO"],
        ["SF_API_URL", "SF_CLIENT_ID", "SF_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "employee_central", "recruiting", "performance",
            "learning", "compensation", "succession",
        ],
        icon="SF",
    ),
    Connector(
        "workday", "Workday",
        "Enterprise HR, finance, and planning cloud platform",
        ConnectorCategory.PEOPLE, ["CHRO", "CFO"],
        ["WORKDAY_TENANT", "WORKDAY_CLIENT_ID", "WORKDAY_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "hr", "payroll", "benefits", "recruiting", "talent",
            "financials", "planning",
        ],
        icon="WD",
    ),
    Connector(
        "adp", "ADP", "Payroll, HR, tax, and benefits administration",
        ConnectorCategory.PEOPLE, ["CHRO", "CFO"],
        ["ADP_CLIENT_ID", "ADP_CLIENT_SECRET"],
        oauth=True,
        data_provided=["payroll", "time_attendance", "benefits", "tax"],
        icon="ADP",
    ),
    Connector(
        "namely", "Namely", "Mid-market HR, payroll, benefits, and talent",
        ConnectorCategory.PEOPLE, ["CHRO"],
        ["NAMELY_API_TOKEN", "NAMELY_SUBDOMAIN"],
        data_provided=["employees", "payroll", "benefits", "performance"],
        icon="NM",
    ),
    Connector(
        "lattice", "Lattice", "Performance management, engagement, OKRs",
        ConnectorCategory.PEOPLE, ["CHRO"],
        ["LATTICE_API_KEY"],
        data_provided=["reviews", "engagement", "okrs", "goals"],
        icon="LT",
    ),
    Connector(
        "deel", "Deel", "Global payroll, contractors, EOR for remote teams",
        ConnectorCategory.PEOPLE, ["CHRO", "CFO"],
        ["DEEL_API_KEY"],
        data_provided=["contractors", "payroll", "compliance", "invoices"],
        icon="DL",
    ),

    # ── Data Platforms ───────────────────────────────────────
    Connector(
        "databricks", "Databricks", "Unified data analytics, ML, lakehouse",
        ConnectorCategory.DATA_PLATFORM, ["CFO", "CMO", "COO"],
        ["DATABRICKS_HOST", "DATABRICKS_TOKEN"],
        data_provided=["sql_queries", "dashboards", "ml_models", "data_pipelines"],
        icon="DB",
    ),
    Connector(
        "snowflake", "Snowflake", "Cloud data warehouse, analytics, data sharing",
        ConnectorCategory.DATA_PLATFORM, ["CFO", "CMO", "COO"],
        ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"],
        data_provided=["sql_queries", "data_warehouse", "data_sharing"],
        icon="SF",
    ),
    Connector(
        "bigquery", "Google BigQuery", "Serverless data warehouse, analytics",
        ConnectorCategory.DATA_PLATFORM, ["CFO", "CMO"],
        ["BIGQUERY_PROJECT_ID", "BIGQUERY_CREDENTIALS_JSON"],
        data_provided=["sql_queries", "datasets", "ml"],
        icon="BQ",
    ),
    Connector(
        "redshift", "Amazon Redshift", "AWS cloud data warehouse",
        ConnectorCategory.DATA_PLATFORM, ["CFO", "CMO"],
        ["REDSHIFT_HOST", "REDSHIFT_USER", "REDSHIFT_PASSWORD", "REDSHIFT_DB"],
        data_provided=["sql_queries", "data_warehouse"],
        icon="RS",
    ),
    Connector(
        "power_bi", "Microsoft Power BI",
        "Business intelligence, interactive dashboards and reports",
        ConnectorCategory.DATA_PLATFORM, ["CFO", "CMO", "COO"],
        ["POWER_BI_CLIENT_ID", "POWER_BI_CLIENT_SECRET"],
        oauth=True,
        data_provided=["dashboards", "reports", "datasets"],
        icon="PBI",
    ),
    Connector(
        "dbt", "dbt (data build tool)", "Data transformation, modeling, testing",
        ConnectorCategory.DATA_PLATFORM, ["COO"],
        ["DBT_CLOUD_API_KEY"],
        data_provided=["models", "tests", "lineage", "freshness"],
        icon="dbt",
    ),
    Connector(
        "fivetran", "Fivetran", "Automated data integration and ETL pipelines",
        ConnectorCategory.DATA_PLATFORM, ["COO"],
        ["FIVETRAN_API_KEY", "FIVETRAN_API_SECRET"],
        data_provided=["connectors", "sync_status", "data_pipelines"],
        icon="FT",
    ),
    Connector(
        "airbyte", "Airbyte", "Open-source ELT data integration platform",
        ConnectorCategory.DATA_PLATFORM, ["COO"],
        ["AIRBYTE_URL", "AIRBYTE_API_KEY"],
        data_provided=["connections", "sync_status", "sources", "destinations"],
        icon="AB",
    ),

    # ── DevOps / Infrastructure ──────────────────────────────
    Connector(
        "datadog", "Datadog", "Infrastructure monitoring, APM, logs",
        ConnectorCategory.DEVOPS, ["COO"],
        ["DATADOG_API_KEY", "DATADOG_APP_KEY"],
        data_provided=["monitors", "incidents", "apm", "logs", "costs"],
        icon="DD",
    ),
    Connector(
        "pagerduty", "PagerDuty", "Incident management, on-call scheduling",
        ConnectorCategory.DEVOPS, ["COO"],
        ["PAGERDUTY_API_KEY"],
        data_provided=["incidents", "oncall", "services"],
        icon="PD",
    ),
    Connector(
        "sentry", "Sentry", "Application error tracking and performance monitoring",
        ConnectorCategory.DEVOPS, ["COO"],
        ["SENTRY_AUTH_TOKEN", "SENTRY_ORG"],
        data_provided=["errors", "performance", "releases"],
        icon="SN",
    ),
    Connector(
        "gitlab", "GitLab", "DevOps platform: code, CI/CD, security",
        ConnectorCategory.DEVOPS, ["COO", "CHRO"],
        ["GITLAB_URL", "GITLAB_TOKEN"],
        data_provided=["repos", "pipelines", "merge_requests", "issues"],
        icon="GL",
    ),
    Connector(
        "bitbucket", "Bitbucket", "Git repository hosting and CI/CD",
        ConnectorCategory.DEVOPS, ["COO"],
        ["BITBUCKET_USERNAME", "BITBUCKET_APP_PASSWORD"],
        data_provided=["repos", "pipelines", "pull_requests"],
        icon="BB",
    ),
    Connector(
        "vercel", "Vercel", "Frontend deployment and hosting platform",
        ConnectorCategory.DEVOPS, ["COO"],
        ["VERCEL_TOKEN"],
        data_provided=["deployments", "domains", "analytics"],
        icon="V",
    ),
    Connector(
        "cloudflare", "Cloudflare", "CDN, DNS, security, Workers",
        ConnectorCategory.DEVOPS, ["COO"],
        ["CLOUDFLARE_API_TOKEN"],
        data_provided=["dns", "analytics", "security_events", "workers"],
        icon="CF",
    ),

    # ── Customer Support ─────────────────────────────────────
    Connector(
        "zendesk", "Zendesk", "Customer support tickets, help center, chat",
        ConnectorCategory.CUSTOMER_SUPPORT, ["COO", "CMO"],
        ["ZENDESK_SUBDOMAIN", "ZENDESK_API_TOKEN", "ZENDESK_EMAIL"],
        data_provided=["tickets", "satisfaction", "agents", "help_center"],
        icon="ZD",
    ),
    Connector(
        "intercom", "Intercom", "Customer messaging, support, product tours",
        ConnectorCategory.CUSTOMER_SUPPORT, ["CMO", "COO"],
        ["INTERCOM_ACCESS_TOKEN"],
        data_provided=["conversations", "contacts", "articles", "product_tours"],
        icon="IC",
    ),
    Connector(
        "freshdesk", "Freshdesk", "Customer support and helpdesk",
        ConnectorCategory.CUSTOMER_SUPPORT, ["COO"],
        ["FRESHDESK_DOMAIN", "FRESHDESK_API_KEY"],
        data_provided=["tickets", "contacts", "satisfaction", "sla"],
        icon="FD",
    ),
    Connector(
        "servicenow", "ServiceNow",
        "Enterprise IT service management, workflows, and operations",
        ConnectorCategory.CUSTOMER_SUPPORT, ["COO"],
        ["SERVICENOW_INSTANCE", "SERVICENOW_USER", "SERVICENOW_PASS"],
        data_provided=["incidents", "changes", "requests", "cmdb", "workflows"],
        icon="SN",
    ),

    # ── E-commerce ───────────────────────────────────────────
    Connector(
        "shopify", "Shopify", "E-commerce: orders, products, customers, analytics",
        ConnectorCategory.ECOMMERCE, ["CFO", "CMO", "COO"],
        ["SHOPIFY_STORE_URL", "SHOPIFY_ACCESS_TOKEN"],
        data_provided=["orders", "products", "customers", "analytics", "inventory"],
        icon="SH",
    ),
    Connector(
        "woocommerce", "WooCommerce", "WordPress e-commerce plugin",
        ConnectorCategory.ECOMMERCE, ["CFO", "CMO"],
        ["WOOCOMMERCE_URL", "WOOCOMMERCE_KEY", "WOOCOMMERCE_SECRET"],
        data_provided=["orders", "products", "customers", "reports"],
        icon="WC",
    ),
    Connector(
        "amazon_seller", "Amazon Seller Central",
        "Amazon marketplace: orders, inventory, advertising, reports",
        ConnectorCategory.ECOMMERCE, ["CFO", "CMO", "COO"],
        ["AMAZON_SP_CLIENT_ID", "AMAZON_SP_CLIENT_SECRET", "AMAZON_SP_REFRESH_TOKEN"],
        data_provided=["orders", "inventory", "advertising", "reports", "fba"],
        icon="AMZ",
    ),

    # ── Security & Compliance ────────────────────────────────
    Connector(
        "okta", "Okta", "Identity and access management, SSO",
        ConnectorCategory.SECURITY, ["CLO", "COO"],
        ["OKTA_DOMAIN", "OKTA_API_TOKEN"],
        data_provided=["users", "groups", "apps", "logs", "mfa"],
        icon="OK",
    ),
    Connector(
        "onelogin", "OneLogin", "Identity management and SSO",
        ConnectorCategory.SECURITY, ["CLO", "COO"],
        ["ONELOGIN_CLIENT_ID", "ONELOGIN_CLIENT_SECRET"],
        data_provided=["users", "apps", "events"],
        icon="1L",
    ),
    Connector(
        "vanta", "Vanta", "Automated security compliance (SOC 2, ISO 27001)",
        ConnectorCategory.SECURITY, ["CLO"],
        ["VANTA_API_KEY"],
        data_provided=["compliance_status", "controls", "evidence", "vendors"],
        icon="VT",
    ),
    Connector(
        "drata", "Drata", "Continuous compliance automation",
        ConnectorCategory.SECURITY, ["CLO"],
        ["DRATA_API_KEY"],
        data_provided=["compliance", "controls", "audit_evidence"],
        icon="DR",
    ),

    # ── Additional Finance ───────────────────────────────────
    Connector(
        "bill_com", "Bill.com", "Accounts payable/receivable automation",
        ConnectorCategory.FINANCE, ["CFO"],
        ["BILL_COM_ORG_ID", "BILL_COM_API_KEY"],
        data_provided=["payables", "receivables", "approvals", "vendors"],
        icon="BC",
    ),
    Connector(
        "ramp", "Ramp", "Corporate card, expense management, bill pay",
        ConnectorCategory.FINANCE, ["CFO"],
        ["RAMP_API_KEY"],
        data_provided=["transactions", "expenses", "budgets", "vendors"],
        icon="RP",
    ),
    Connector(
        "mercury", "Mercury", "Startup banking, treasury, venture debt",
        ConnectorCategory.FINANCE, ["CFO"],
        ["MERCURY_API_KEY"],
        data_provided=["accounts", "transactions", "treasury"],
        icon="MR",
    ),
    Connector(
        "wise", "Wise (TransferWise)",
        "International payments, multi-currency accounts",
        ConnectorCategory.FINANCE, ["CFO"],
        ["WISE_API_KEY"],
        data_provided=["transfers", "balances", "exchange_rates"],
        icon="WS",
    ),

    # ── Additional Sales / CRM ───────────────────────────────
    Connector(
        "pipedrive", "Pipedrive", "Sales CRM for small teams",
        ConnectorCategory.SALES, ["CSO"],
        ["PIPEDRIVE_API_TOKEN"],
        data_provided=["deals", "contacts", "activities", "pipeline"],
        icon="PD",
    ),
    Connector(
        "close_crm", "Close CRM", "Inside sales CRM with calling and email",
        ConnectorCategory.SALES, ["CSO"],
        ["CLOSE_API_KEY"],
        data_provided=["leads", "opportunities", "calls", "emails"],
        icon="CL",
    ),
    Connector(
        "gong", "Gong", "Revenue intelligence, call recording, deal analytics",
        ConnectorCategory.SALES, ["CSO"],
        ["GONG_ACCESS_KEY", "GONG_ACCESS_KEY_SECRET"],
        data_provided=["calls", "deal_intelligence", "coaching", "forecasting"],
        icon="GG",
    ),
    Connector(
        "outreach", "Outreach", "Sales engagement, sequences, analytics",
        ConnectorCategory.SALES, ["CSO"],
        ["OUTREACH_API_KEY"],
        oauth=True,
        data_provided=["sequences", "prospects", "analytics", "tasks"],
        icon="OR",
    ),

    # ── Additional Marketing ─────────────────────────────────
    Connector(
        "mixpanel", "Mixpanel", "Product analytics, user behavior, funnels",
        ConnectorCategory.MARKETING, ["CMO"],
        ["MIXPANEL_PROJECT_TOKEN", "MIXPANEL_API_SECRET"],
        data_provided=["events", "funnels", "retention", "users"],
        icon="MP",
    ),
    Connector(
        "amplitude", "Amplitude", "Product analytics, experimentation",
        ConnectorCategory.MARKETING, ["CMO"],
        ["AMPLITUDE_API_KEY", "AMPLITUDE_SECRET_KEY"],
        data_provided=["events", "cohorts", "funnels", "experiments"],
        icon="AM",
    ),
    Connector(
        "segment", "Segment (Twilio)", "Customer data platform, event routing",
        ConnectorCategory.MARKETING, ["CMO"],
        ["SEGMENT_WRITE_KEY"],
        data_provided=["events", "sources", "destinations", "profiles"],
        icon="SG",
    ),
    Connector(
        "klaviyo", "Klaviyo", "E-commerce email/SMS marketing automation",
        ConnectorCategory.MARKETING, ["CMO"],
        ["KLAVIYO_API_KEY"],
        data_provided=["campaigns", "flows", "lists", "metrics"],
        icon="KL",
    ),
    Connector(
        "hootsuite", "Hootsuite", "Social media management, scheduling, analytics",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["HOOTSUITE_API_KEY"],
        oauth=True,
        data_provided=["scheduling", "analytics", "streams", "publishing"],
        icon="HS",
    ),
    Connector(
        "buffer", "Buffer", "Social media scheduling and analytics",
        ConnectorCategory.SOCIAL_MEDIA, ["CMO"],
        ["BUFFER_ACCESS_TOKEN"],
        data_provided=["scheduling", "analytics", "publishing"],
        icon="BF",
    ),

    # ── Additional Storage / Collaboration ───────────────────
    Connector(
        "sharepoint", "SharePoint", "Enterprise document management, intranets",
        ConnectorCategory.STORAGE, ["COO", "CLO", "CFO"],
        ["SHAREPOINT_SITE_URL", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET"],
        oauth=True,
        data_provided=["documents", "lists", "sites", "workflows"],
        icon="SP",
    ),
    Connector(
        "box", "Box", "Enterprise content management and collaboration",
        ConnectorCategory.STORAGE, ["COO", "CLO"],
        ["BOX_CLIENT_ID", "BOX_CLIENT_SECRET"],
        oauth=True,
        data_provided=["files", "folders", "metadata", "workflows"],
        icon="BX",
    ),
    Connector(
        "airtable", "Airtable", "Spreadsheet-database hybrid, project tracking",
        ConnectorCategory.STORAGE, ["COO"],
        ["AIRTABLE_API_KEY"],
        data_provided=["bases", "tables", "records", "views"],
        icon="AT",
    ),
    Connector(
        "monday_com", "Monday.com", "Work OS: project management, workflows",
        ConnectorCategory.OPERATIONS, ["COO"],
        ["MONDAY_API_KEY"],
        data_provided=["boards", "items", "updates", "automations"],
        icon="MN",
    ),
    Connector(
        "clickup", "ClickUp", "All-in-one project management",
        ConnectorCategory.OPERATIONS, ["COO"],
        ["CLICKUP_API_KEY"],
        data_provided=["tasks", "spaces", "goals", "time_tracking"],
        icon="CU",
    ),
    Connector(
        "basecamp", "Basecamp", "Project management and team communication",
        ConnectorCategory.OPERATIONS, ["COO"],
        ["BASECAMP_ACCOUNT_ID", "BASECAMP_ACCESS_TOKEN"],
        data_provided=["projects", "todos", "messages", "schedule"],
        icon="BC",
    ),

    # ── Communication (Enterprise) ───────────────────────────
    Connector(
        "twilio", "Twilio", "SMS, voice, WhatsApp messaging APIs",
        ConnectorCategory.COMMUNICATION, ["CMO", "CSO", "COO"],
        ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
        data_provided=["sms", "voice", "whatsapp", "messaging"],
        icon="TW",
    ),
    Connector(
        "whatsapp_business", "WhatsApp Business",
        "Customer messaging via WhatsApp Business API",
        ConnectorCategory.COMMUNICATION, ["CMO", "CSO"],
        ["WHATSAPP_PHONE_ID", "WHATSAPP_ACCESS_TOKEN"],
        data_provided=["messaging", "templates", "contacts"],
        icon="WA",
    ),
    Connector(
        "discord", "Discord", "Community management, server monitoring",
        ConnectorCategory.COMMUNICATION, ["CMO"],
        ["DISCORD_BOT_TOKEN"],
        data_provided=["messaging", "channels", "members"],
        icon="DC",
    ),
    Connector(
        "zoom", "Zoom", "Video meetings, webinars, recordings",
        ConnectorCategory.COMMUNICATION, ["COO", "CSO"],
        ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"],
        oauth=True,
        data_provided=["meetings", "recordings", "webinars", "reports"],
        icon="ZM",
    ),
    Connector(
        "google_meet", "Google Meet", "Video conferencing via Google Workspace",
        ConnectorCategory.COMMUNICATION, ["COO"],
        ["GOOGLE_WORKSPACE_CREDENTIALS_JSON"],
        oauth=True,
        data_provided=["meetings", "calendar_integration"],
        icon="GM",
    ),

    # ── Salesforce Ecosystem ─────────────────────────────────
    Connector(
        "sfcc", "Salesforce Commerce Cloud (SFCC)",
        "E-commerce storefront, orders, products, promotions, customer data",
        ConnectorCategory.ECOMMERCE, ["CMO", "CSO", "CFO"],
        ["SFCC_CLIENT_ID", "SFCC_CLIENT_SECRET", "SFCC_INSTANCE_URL"],
        oauth=True,
        data_provided=[
            "orders", "products", "promotions", "customers",
            "catalogs", "inventory", "price_books",
        ],
        icon="SFCC",
    ),
    Connector(
        "sfsc", "Salesforce Service Cloud (SFSC)",
        "Customer service: cases, knowledge base, omni-channel, SLA tracking",
        ConnectorCategory.CUSTOMER_SUPPORT, ["COO", "CMO", "CSO"],
        ["SFSC_CLIENT_ID", "SFSC_CLIENT_SECRET", "SFSC_INSTANCE_URL"],
        oauth=True,
        data_provided=[
            "cases", "knowledge_articles", "sla", "customer_satisfaction",
            "agent_performance", "omnichannel", "escalations",
        ],
        icon="SFSC",
    ),
    Connector(
        "sf_marketing_cloud", "Salesforce Marketing Cloud",
        "Email, mobile, social, advertising, and journey orchestration",
        ConnectorCategory.MARKETING, ["CMO"],
        ["SFMC_CLIENT_ID", "SFMC_CLIENT_SECRET", "SFMC_SUBDOMAIN"],
        oauth=True,
        data_provided=[
            "email_campaigns", "journeys", "audiences",
            "sms", "push_notifications", "analytics",
        ],
        icon="SFMC",
    ),
    Connector(
        "sf_cpq", "Salesforce CPQ",
        "Configure-price-quote: product config, pricing rules, proposals",
        ConnectorCategory.SALES, ["CSO", "CFO"],
        ["SF_CPQ_CLIENT_ID", "SF_CPQ_CLIENT_SECRET"],
        oauth=True,
        data_provided=["quotes", "products", "pricing", "contracts", "renewals"],
        icon="CPQ",
    ),

    # ── App Store / Mobile Performance ───────────────────────
    Connector(
        "apple_app_store", "Apple App Store Connect",
        "iOS app performance, ratings, reviews, downloads, revenue, crashes",
        ConnectorCategory.ANALYTICS, ["CMO", "COO"],
        ["APPLE_ISSUER_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY"],
        data_provided=[
            "downloads", "revenue", "ratings", "reviews",
            "crashes", "app_analytics", "subscriptions",
        ],
        icon="AS",
    ),
    Connector(
        "google_play", "Google Play Console",
        "Android app performance, ratings, reviews, installs, revenue, ANRs",
        ConnectorCategory.ANALYTICS, ["CMO", "COO"],
        ["GOOGLE_PLAY_CREDENTIALS_JSON"],
        data_provided=[
            "installs", "revenue", "ratings", "reviews",
            "crashes", "anrs", "vitals", "subscriptions",
        ],
        icon="GP",
    ),
    Connector(
        "appfollow", "AppFollow",
        "App store review monitoring, ASO, competitor tracking across stores",
        ConnectorCategory.ANALYTICS, ["CMO"],
        ["APPFOLLOW_API_KEY"],
        data_provided=[
            "reviews", "ratings", "aso_keywords", "competitors",
            "reply_to_reviews", "sentiment",
        ],
        icon="AF",
    ),
    Connector(
        "app_annie", "data.ai (App Annie)",
        "App market intelligence, download estimates, revenue estimates",
        ConnectorCategory.ANALYTICS, ["CMO", "CSO"],
        ["DATA_AI_API_KEY"],
        data_provided=[
            "market_estimates", "downloads", "revenue",
            "usage", "engagement", "competitor_intel",
        ],
        icon="DA",
    ),
    Connector(
        "firebase", "Google Firebase",
        "Mobile app platform: analytics, crashlytics, crash rates, ANR rates, "
        "A/B testing, remote config, performance monitoring, cloud messaging",
        ConnectorCategory.ANALYTICS, ["CMO", "COO", "CSO"],
        ["FIREBASE_CREDENTIALS_JSON", "FIREBASE_PROJECT_ID"],
        data_provided=[
            "analytics", "crashlytics", "crash_rate", "anr_rate",
            "stability_score", "performance_traces", "ab_testing",
            "remote_config", "cloud_messaging", "app_distribution",
        ],
        icon="FB",
    ),
    Connector(
        "appsflyer", "AppsFlyer",
        "Mobile attribution, marketing analytics, deep linking, fraud",
        ConnectorCategory.ANALYTICS, ["CMO"],
        ["APPSFLYER_API_TOKEN", "APPSFLYER_APP_ID"],
        data_provided=[
            "attribution", "installs", "in_app_events",
            "retargeting", "fraud_detection", "cohorts",
        ],
        icon="AF",
    ),
    Connector(
        "adjust", "Adjust",
        "Mobile measurement, fraud prevention, automation",
        ConnectorCategory.ANALYTICS, ["CMO"],
        ["ADJUST_API_TOKEN"],
        data_provided=[
            "attribution", "events", "fraud_prevention",
            "audience_builder", "analytics",
        ],
        icon="AD",
    ),

    # ── Review / Reputation Platforms ────────────────────────
    Connector(
        "g2", "G2",
        "B2B software reviews, competitor comparisons, buyer intent",
        ConnectorCategory.MARKETING, ["CMO", "CSO"],
        ["G2_API_TOKEN"],
        data_provided=[
            "reviews", "ratings", "competitor_comparison",
            "buyer_intent", "market_presence",
        ],
        icon="G2",
    ),
    Connector(
        "trustpilot", "Trustpilot",
        "Customer reviews, reputation management, trust score",
        ConnectorCategory.MARKETING, ["CMO"],
        ["TRUSTPILOT_API_KEY", "TRUSTPILOT_API_SECRET"],
        data_provided=[
            "reviews", "trust_score", "reply_to_reviews",
            "invitation_links", "analytics",
        ],
        icon="TP",
    ),
    Connector(
        "capterra", "Capterra / GetApp",
        "Software reviews and comparisons for B2B buyers",
        ConnectorCategory.MARKETING, ["CMO", "CSO"],
        ["CAPTERRA_API_KEY"],
        data_provided=["reviews", "ratings", "category_ranking"],
        icon="CA",
    ),
    Connector(
        "glassdoor", "Glassdoor",
        "Employer reviews, salary data, interview feedback",
        ConnectorCategory.PEOPLE, ["CHRO"],
        ["GLASSDOOR_PARTNER_ID", "GLASSDOOR_KEY"],
        data_provided=[
            "employer_reviews", "ratings", "salary_data",
            "interview_reviews", "benefits_reviews",
        ],
        icon="GD",
    ),
    Connector(
        "yelp", "Yelp",
        "Business reviews, ratings, customer feedback",
        ConnectorCategory.MARKETING, ["CMO"],
        ["YELP_API_KEY"],
        data_provided=["reviews", "ratings", "photos", "business_info"],
        icon="Y",
    ),
    Connector(
        "google_business", "Google Business Profile",
        "Google Maps listing, reviews, local SEO, insights",
        ConnectorCategory.MARKETING, ["CMO"],
        ["GOOGLE_BUSINESS_ACCOUNT_ID"],
        oauth=True,
        data_provided=[
            "reviews", "ratings", "insights", "posts",
            "q_and_a", "local_seo",
        ],
        icon="GB",
    ),
    Connector(
        "bbb", "Better Business Bureau",
        "Business accreditation, complaints, ratings",
        ConnectorCategory.LEGAL, ["CLO", "COO"],
        [],
        data_provided=["accreditation", "complaints", "rating"],
        icon="BBB",
    ),

    # ── Freshworks Suite ─────────────────────────────────────
    Connector(
        "freshsales", "Freshsales (Freshworks CRM)",
        "CRM, lead scoring, deal management, email tracking",
        ConnectorCategory.SALES, ["CSO"],
        ["FRESHSALES_DOMAIN", "FRESHSALES_API_KEY"],
        data_provided=[
            "leads", "contacts", "deals", "accounts",
            "email_tracking", "phone", "activities",
        ],
        icon="FS",
    ),
    Connector(
        "freshmarketer", "Freshmarketer",
        "Marketing automation, email campaigns, journeys",
        ConnectorCategory.MARKETING, ["CMO"],
        ["FRESHMARKETER_DOMAIN", "FRESHMARKETER_API_KEY"],
        data_provided=[
            "campaigns", "journeys", "contacts",
            "landing_pages", "forms", "analytics",
        ],
        icon="FM",
    ),
    Connector(
        "freshservice", "Freshservice",
        "IT service management, asset management, change management",
        ConnectorCategory.CUSTOMER_SUPPORT, ["COO"],
        ["FRESHSERVICE_DOMAIN", "FRESHSERVICE_API_KEY"],
        data_provided=[
            "tickets", "assets", "changes", "problems",
            "releases", "cmdb", "sla",
        ],
        icon="FS",
    ),

    # ── Payment Processors ───────────────────────────────────
    Connector(
        "paypal", "PayPal",
        "Payments, invoicing, subscriptions, payouts",
        ConnectorCategory.FINANCE, ["CFO"],
        ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"],
        data_provided=[
            "transactions", "invoices", "subscriptions",
            "payouts", "disputes",
        ],
        icon="PP",
    ),
    Connector(
        "square", "Square",
        "Payments, POS, invoicing, inventory, team management",
        ConnectorCategory.FINANCE, ["CFO", "COO"],
        ["SQUARE_ACCESS_TOKEN"],
        data_provided=[
            "payments", "orders", "inventory", "customers",
            "team", "loyalty",
        ],
        icon="SQ",
    ),
    Connector(
        "razorpay", "Razorpay",
        "India payment gateway: payments, subscriptions, payroll",
        ConnectorCategory.FINANCE, ["CFO"],
        ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"],
        data_provided=["payments", "subscriptions", "settlements", "invoices"],
        icon="RP",
    ),
    Connector(
        "chargebee", "Chargebee",
        "Subscription billing, revenue recognition, dunning",
        ConnectorCategory.FINANCE, ["CFO"],
        ["CHARGEBEE_SITE", "CHARGEBEE_API_KEY"],
        data_provided=[
            "subscriptions", "invoices", "customers",
            "revenue", "mrr", "churn", "dunning",
        ],
        icon="CB",
    ),
    Connector(
        "recurly", "Recurly",
        "Subscription management, billing, revenue optimization",
        ConnectorCategory.FINANCE, ["CFO"],
        ["RECURLY_API_KEY"],
        data_provided=["subscriptions", "invoices", "revenue", "churn"],
        icon="RC",
    ),

    # ── Advertising / Media ──────────────────────────────────
    Connector(
        "twitter_ads", "X (Twitter) Ads",
        "Twitter/X advertising campaigns and analytics",
        ConnectorCategory.MARKETING, ["CMO"],
        ["TWITTER_ADS_ACCOUNT_ID", "TWITTER_ADS_ACCESS_TOKEN"],
        data_provided=["campaigns", "audiences", "creatives", "analytics"],
        icon="XA",
    ),
    Connector(
        "spotify_ads", "Spotify Ad Studio",
        "Audio advertising on Spotify",
        ConnectorCategory.MARKETING, ["CMO"],
        ["SPOTIFY_ADS_ACCESS_TOKEN"],
        oauth=True,
        data_provided=["campaigns", "audio_creatives", "targeting", "analytics"],
        icon="SP",
    ),
    Connector(
        "taboola", "Taboola",
        "Native advertising, content discovery, performance marketing",
        ConnectorCategory.MARKETING, ["CMO"],
        ["TABOOLA_CLIENT_ID", "TABOOLA_CLIENT_SECRET"],
        data_provided=["campaigns", "creatives", "audiences", "analytics"],
        icon="TB",
    ),
    Connector(
        "criteo", "Criteo",
        "Retargeting, performance display, commerce media",
        ConnectorCategory.MARKETING, ["CMO"],
        ["CRITEO_CLIENT_ID", "CRITEO_CLIENT_SECRET"],
        data_provided=["campaigns", "retargeting", "audiences", "analytics"],
        icon="CR",
    ),

    # ── Surveys / Feedback ───────────────────────────────────
    Connector(
        "typeform", "Typeform",
        "Surveys, forms, quizzes, customer feedback collection",
        ConnectorCategory.MARKETING, ["CMO", "CHRO"],
        ["TYPEFORM_ACCESS_TOKEN"],
        data_provided=["responses", "forms", "analytics", "webhooks"],
        icon="TF",
    ),
    Connector(
        "surveymonkey", "SurveyMonkey",
        "Surveys, market research, employee engagement",
        ConnectorCategory.MARKETING, ["CMO", "CHRO"],
        ["SURVEYMONKEY_ACCESS_TOKEN"],
        data_provided=["surveys", "responses", "analytics"],
        icon="SM",
    ),
    Connector(
        "qualtrics", "Qualtrics",
        "Experience management: customer, employee, brand, product",
        ConnectorCategory.MARKETING, ["CMO", "CHRO"],
        ["QUALTRICS_API_TOKEN", "QUALTRICS_DATACENTER"],
        data_provided=[
            "surveys", "cx_metrics", "ex_metrics",
            "nps", "csat", "analytics",
        ],
        icon="QX",
    ),

    # ── CRM / Customer Data ──────────────────────────────────
    Connector(
        "customer_io", "Customer.io",
        "Messaging automation: email, push, SMS, in-app based on behavior",
        ConnectorCategory.MARKETING, ["CMO"],
        ["CUSTOMERIO_SITE_ID", "CUSTOMERIO_API_KEY"],
        data_provided=[
            "campaigns", "segments", "customers",
            "events", "deliveries",
        ],
        icon="CIO",
    ),
    Connector(
        "braze", "Braze",
        "Customer engagement: push, email, in-app, SMS, cross-channel",
        ConnectorCategory.MARKETING, ["CMO"],
        ["BRAZE_API_KEY", "BRAZE_INSTANCE_URL"],
        data_provided=[
            "campaigns", "canvases", "segments",
            "users", "messaging", "analytics",
        ],
        icon="BZ",
    ),
    Connector(
        "clevertap", "CleverTap",
        "Customer engagement and retention platform for mobile apps",
        ConnectorCategory.MARKETING, ["CMO"],
        ["CLEVERTAP_ACCOUNT_ID", "CLEVERTAP_PASSCODE"],
        data_provided=[
            "events", "profiles", "campaigns",
            "segments", "funnels", "analytics",
        ],
        icon="CT",
    ),

    # ── Document / Contract Intelligence ─────────────────────
    Connector(
        "ironclad", "Ironclad",
        "Contract lifecycle management, AI-powered review",
        ConnectorCategory.LEGAL, ["CLO"],
        ["IRONCLAD_API_KEY"],
        data_provided=[
            "contracts", "workflows", "approvals",
            "templates", "analytics",
        ],
        icon="IC",
    ),
    Connector(
        "icertis", "Icertis",
        "Enterprise contract management, AI-powered insights",
        ConnectorCategory.LEGAL, ["CLO"],
        ["ICERTIS_URL", "ICERTIS_API_KEY"],
        data_provided=[
            "contracts", "obligations", "compliance",
            "risk_scoring", "analytics",
        ],
        icon="IC",
    ),

    # ── Supply Chain / Logistics ─────────────────────────────
    Connector(
        "flexport", "Flexport",
        "Global freight forwarding, customs, supply chain visibility",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["FLEXPORT_API_KEY"],
        data_provided=[
            "shipments", "tracking", "customs",
            "invoices", "carbon_emissions",
        ],
        icon="FP",
    ),

    # ── PIM (Product Information Management) ─────────────────
    Connector(
        "akeneo", "Akeneo",
        "Product information management: catalog, attributes, assets, channels",
        ConnectorCategory.PIM, ["CMO", "COO"],
        ["AKENEO_URL", "AKENEO_CLIENT_ID", "AKENEO_SECRET"],
        data_provided=[
            "products", "families", "attributes", "categories",
            "assets", "channels", "locales", "completeness",
        ],
        icon="AK",
    ),
    Connector(
        "salsify", "Salsify",
        "Product experience management: PIM, DAM, syndication",
        ConnectorCategory.PIM, ["CMO", "COO"],
        ["SALSIFY_API_KEY", "SALSIFY_ORG_ID"],
        data_provided=[
            "products", "digital_assets", "channels",
            "syndication", "enrichment_score",
        ],
        icon="SL",
    ),
    Connector(
        "pimcore", "Pimcore",
        "Open-source PIM, MDM, DAM, and digital experience platform",
        ConnectorCategory.PIM, ["CMO", "COO"],
        ["PIMCORE_URL", "PIMCORE_API_KEY"],
        data_provided=[
            "products", "assets", "documents",
            "classifications", "data_quality",
        ],
        icon="PM",
    ),
    Connector(
        "inriver", "inRiver",
        "Product marketing cloud: PIM, digital shelf, syndication",
        ConnectorCategory.PIM, ["CMO"],
        ["INRIVER_URL", "INRIVER_API_KEY"],
        data_provided=[
            "products", "resources", "channels",
            "syndication", "completeness",
        ],
        icon="IR",
    ),
    Connector(
        "plytix", "Plytix",
        "PIM for SMBs: product data, channels, brand portals",
        ConnectorCategory.PIM, ["CMO", "COO"],
        ["PLYTIX_API_KEY"],
        data_provided=["products", "channels", "brand_portals", "analytics"],
        icon="PX",
    ),
    Connector(
        "syndigo", "Syndigo (Riversand)",
        "Master data management, product content, syndication to retailers",
        ConnectorCategory.PIM, ["CMO", "COO"],
        ["SYNDIGO_API_KEY"],
        data_provided=[
            "products", "master_data", "content",
            "syndication", "retailer_compliance",
        ],
        icon="SY",
    ),
    Connector(
        "contentserv", "Contentserv",
        "Product experience platform: PIM, MDM, marketing portal",
        ConnectorCategory.PIM, ["CMO"],
        ["CONTENTSERV_URL", "CONTENTSERV_API_KEY"],
        data_provided=["products", "marketing_content", "channels", "portals"],
        icon="CS",
    ),

    # ── Inventory & Warehouse Management ─────────────────────
    Connector(
        "skubana", "Extensiv (Skubana)",
        "Multi-channel inventory, order, and warehouse management",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["SKUBANA_API_KEY"],
        data_provided=[
            "inventory_levels", "sku_management", "warehouses",
            "orders", "purchase_orders", "demand_forecasting",
        ],
        icon="SK",
    ),
    Connector(
        "cin7", "Cin7",
        "Inventory management, POS, B2B, warehouse, 3PL",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["CIN7_API_KEY"],
        data_provided=[
            "stock_levels", "products", "warehouses",
            "purchase_orders", "sales_orders", "bom",
        ],
        icon="C7",
    ),
    Connector(
        "ordoro", "Ordoro",
        "Inventory management, dropshipping, shipping, supplier management",
        ConnectorCategory.INVENTORY_WMS, ["COO"],
        ["ORDORO_API_KEY"],
        data_provided=[
            "inventory", "suppliers", "dropship",
            "shipping", "purchase_orders",
        ],
        icon="OR",
    ),
    Connector(
        "fishbowl", "Fishbowl",
        "Inventory management and warehouse for QuickBooks",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["FISHBOWL_HOST", "FISHBOWL_USER", "FISHBOWL_PASS"],
        data_provided=[
            "inventory", "warehouses", "manufacturing",
            "pick_pack_ship", "barcoding",
        ],
        icon="FB",
    ),
    Connector(
        "logiwa", "Logiwa",
        "Cloud WMS: fulfillment, inventory, warehouse automation",
        ConnectorCategory.INVENTORY_WMS, ["COO"],
        ["LOGIWA_API_KEY"],
        data_provided=[
            "inventory", "warehouses", "fulfillment",
            "picking", "packing", "shipping",
        ],
        icon="LW",
    ),
    Connector(
        "shiphero", "ShipHero",
        "Warehouse management, inventory, pick-pack-ship",
        ConnectorCategory.INVENTORY_WMS, ["COO"],
        ["SHIPHERO_API_KEY"],
        data_provided=[
            "inventory", "orders", "warehouses",
            "shipping", "returns",
        ],
        icon="SH",
    ),
    Connector(
        "dear_inventory", "Cin7 Core (DEAR Inventory)",
        "Inventory, manufacturing, B2B portal, integrations",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["DEAR_ACCOUNT_ID", "DEAR_APPLICATION_KEY"],
        data_provided=[
            "stock_levels", "purchase_orders", "sale_orders",
            "manufacturing", "bom", "stocktake",
        ],
        icon="DI",
    ),
    Connector(
        "tradegecko", "QuickBooks Commerce (TradeGecko)",
        "Inventory and order management for SMBs",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["QBC_API_KEY"],
        data_provided=[
            "products", "variants", "stock_levels",
            "orders", "purchase_orders",
        ],
        icon="TG",
    ),
    Connector(
        "brightpearl", "Sage Brightpearl",
        "Retail operations platform: inventory, orders, accounting, POS",
        ConnectorCategory.INVENTORY_WMS, ["COO", "CFO"],
        ["BRIGHTPEARL_ACCOUNT", "BRIGHTPEARL_API_KEY"],
        data_provided=[
            "inventory", "orders", "purchasing",
            "accounting", "warehouses", "demand_planning",
        ],
        icon="BP",
    ),

    # ── Supply Chain ─────────────────────────────────────────
    Connector(
        "shipstation", "ShipStation",
        "Multi-carrier shipping, order management, automation",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["SHIPSTATION_API_KEY", "SHIPSTATION_API_SECRET"],
        data_provided=[
            "orders", "shipments", "carriers",
            "tracking", "warehouses",
        ],
        icon="SS",
    ),
    Connector(
        "easypost", "EasyPost",
        "Shipping API: rates, labels, tracking across carriers",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["EASYPOST_API_KEY"],
        data_provided=["rates", "labels", "tracking", "insurance"],
        icon="EP",
    ),
    Connector(
        "project44", "project44",
        "Supply chain visibility: real-time tracking, ETA predictions",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["P44_CLIENT_ID", "P44_CLIENT_SECRET"],
        data_provided=[
            "shipment_tracking", "eta_predictions",
            "carrier_performance", "exceptions",
        ],
        icon="P44",
    ),
    Connector(
        "fourkites", "FourKites",
        "Real-time supply chain visibility and predictive analytics",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["FOURKITES_API_KEY"],
        data_provided=[
            "tracking", "dwell_time", "eta",
            "carrier_scorecards", "yard_visibility",
        ],
        icon="4K",
    ),
    Connector(
        "oracle_scm", "Oracle SCM Cloud",
        "Supply chain management: planning, manufacturing, logistics",
        ConnectorCategory.SUPPLY_CHAIN, ["COO"],
        ["ORACLE_SCM_URL", "ORACLE_SCM_CLIENT_ID", "ORACLE_SCM_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "demand_planning", "supply_planning", "manufacturing",
            "order_management", "logistics", "procurement",
        ],
        icon="OSCM",
    ),
    Connector(
        "sap_ibp", "SAP Integrated Business Planning",
        "Demand planning, inventory optimization, supply planning",
        ConnectorCategory.SUPPLY_CHAIN, ["COO", "CFO"],
        ["SAP_IBP_URL", "SAP_IBP_CLIENT_ID", "SAP_IBP_CLIENT_SECRET"],
        data_provided=[
            "demand_forecast", "inventory_optimization",
            "supply_planning", "sales_ops_planning",
        ],
        icon="IBP",
    ),

    # ── OMS (Order Management Systems) ───────────────────────
    Connector(
        "fluent_commerce", "Fluent Commerce",
        "Distributed order management: routing, fulfillment, inventory visibility",
        ConnectorCategory.OMS, ["COO", "CFO"],
        ["FLUENT_URL", "FLUENT_CLIENT_ID", "FLUENT_CLIENT_SECRET"],
        data_provided=[
            "orders", "fulfillment", "routing_rules",
            "inventory_positions", "returns", "ship_from_store",
            "click_collect", "orchestration",
        ],
        icon="FC",
    ),
    Connector(
        "vinculum", "Vinculum",
        "OMS and warehouse management: multi-channel, fulfillment, reverse logistics",
        ConnectorCategory.OMS, ["COO", "CFO"],
        ["VINCULUM_URL", "VINCULUM_API_KEY"],
        data_provided=[
            "orders", "fulfillment", "inventory_sync",
            "marketplace_integration", "returns", "reverse_logistics",
            "warehouse_management", "last_mile",
        ],
        icon="VN",
    ),
    Connector(
        "manhattan_active", "Manhattan Active Omni",
        "Enterprise OMS: order orchestration, store fulfillment, customer service",
        ConnectorCategory.OMS, ["COO"],
        ["MANHATTAN_URL", "MANHATTAN_CLIENT_ID", "MANHATTAN_CLIENT_SECRET"],
        data_provided=[
            "order_orchestration", "store_fulfillment",
            "customer_service", "inventory_visibility",
            "bopis", "ship_from_store",
        ],
        icon="MA",
    ),
    Connector(
        "kibo_commerce", "Kibo Commerce",
        "Unified commerce: OMS, e-commerce, personalization",
        ConnectorCategory.OMS, ["COO", "CMO"],
        ["KIBO_CLIENT_ID", "KIBO_CLIENT_SECRET"],
        data_provided=[
            "orders", "fulfillment", "inventory",
            "catalog", "personalization",
        ],
        icon="KB",
    ),
    Connector(
        "fabric_oms", "fabric OMS",
        "Headless OMS: order routing, split shipments, dropship",
        ConnectorCategory.OMS, ["COO"],
        ["FABRIC_API_KEY"],
        data_provided=[
            "orders", "routing", "split_shipments",
            "dropship", "inventory_allocation",
        ],
        icon="FB",
    ),
    Connector(
        "orderbot", "Orderbot (Dsco)",
        "Dropship and marketplace order automation",
        ConnectorCategory.OMS, ["COO"],
        ["ORDERBOT_API_KEY"],
        data_provided=["orders", "dropship", "vendor_compliance", "edi"],
        icon="OB",
    ),
    Connector(
        "celect", "Celect (Nike/acquired)",
        "AI-powered inventory optimization and demand sensing",
        ConnectorCategory.OMS, ["COO", "CFO"],
        ["CELECT_API_KEY"],
        data_provided=[
            "demand_sensing", "inventory_optimization",
            "allocation", "markdown_optimization",
        ],
        icon="CE",
    ),
    Connector(
        "aptos_oms", "Aptos OMS",
        "Retail OMS: order brokering, fulfillment, in-store pickup",
        ConnectorCategory.OMS, ["COO"],
        ["APTOS_URL", "APTOS_API_KEY"],
        data_provided=[
            "order_brokering", "fulfillment", "bopis",
            "inventory", "customer_orders",
        ],
        icon="AP",
    ),
    Connector(
        "oms_ibm_sterling", "IBM Sterling Order Management",
        "Enterprise OMS: multi-channel orchestration, promising, fulfillment",
        ConnectorCategory.OMS, ["COO"],
        ["STERLING_URL", "STERLING_USER", "STERLING_PASS"],
        data_provided=[
            "order_orchestration", "promising", "fulfillment",
            "inventory_visibility", "returns",
        ],
        icon="SO",
    ),
    Connector(
        "increff", "Increff",
        "Inventory and OMS for fashion/retail: allocation, replenishment",
        ConnectorCategory.OMS, ["COO", "CFO"],
        ["INCREFF_API_KEY"],
        data_provided=[
            "inventory_allocation", "replenishment",
            "assortment_planning", "oms", "warehouse",
        ],
        icon="IF",
    ),
    Connector(
        "anchanto", "Anchanto",
        "E-commerce logistics and OMS: multi-marketplace, fulfillment, returns",
        ConnectorCategory.OMS, ["COO"],
        ["ANCHANTO_URL", "ANCHANTO_API_KEY"],
        data_provided=[
            "orders", "fulfillment", "returns",
            "marketplace_sync", "warehouse", "last_mile",
        ],
        icon="AN",
    ),

    # ── Returns & Reverse Logistics ──────────────────────────
    Connector(
        "loop_returns", "Loop Returns",
        "Automated returns, exchanges, store credit, fraud prevention",
        ConnectorCategory.RETURNS_FULFILLMENT, ["COO", "CFO"],
        ["LOOP_API_KEY"],
        data_provided=[
            "returns", "exchanges", "store_credit",
            "return_reasons", "fraud_detection", "analytics",
        ],
        icon="LR",
    ),
    Connector(
        "narvar", "Narvar",
        "Post-purchase: tracking, returns, notifications, concierge",
        ConnectorCategory.RETURNS_FULFILLMENT, ["COO", "CMO"],
        ["NARVAR_API_KEY"],
        data_provided=[
            "tracking_pages", "return_portal", "notifications",
            "delivery_estimates", "customer_experience",
        ],
        icon="NR",
    ),
    Connector(
        "returnly", "Returnly (Affirm)",
        "Instant exchanges, refunds, return analytics",
        ConnectorCategory.RETURNS_FULFILLMENT, ["COO", "CFO"],
        ["RETURNLY_API_KEY"],
        data_provided=[
            "returns", "instant_exchanges", "refunds",
            "return_rate", "analytics",
        ],
        icon="RT",
    ),
    Connector(
        "aftership", "AfterShip",
        "Shipment tracking, returns management, estimated delivery",
        ConnectorCategory.RETURNS_FULFILLMENT, ["COO"],
        ["AFTERSHIP_API_KEY"],
        data_provided=[
            "tracking", "returns", "delivery_estimates",
            "notifications", "analytics",
        ],
        icon="AS",
    ),

    # ── Marketplace Aggregators ──────────────────────────────
    Connector(
        "channelengine", "ChannelEngine",
        "Multi-marketplace integration: list, sell, fulfill across 700+ channels",
        ConnectorCategory.MARKETPLACE, ["COO", "CMO", "CSO"],
        ["CHANNELENGINE_API_KEY"],
        data_provided=[
            "listings", "orders", "fulfillment",
            "repricing", "marketplace_analytics",
        ],
        icon="CE",
    ),
    Connector(
        "channeladvisor", "ChannelAdvisor",
        "Multi-channel commerce: marketplaces, digital marketing, fulfillment",
        ConnectorCategory.MARKETPLACE, ["COO", "CMO"],
        ["CHANNELADVISOR_API_KEY"],
        data_provided=[
            "listings", "orders", "inventory",
            "repricing", "advertising", "analytics",
        ],
        icon="CA",
    ),
    Connector(
        "linnworks", "Linnworks",
        "Multi-channel order and inventory management",
        ConnectorCategory.MARKETPLACE, ["COO"],
        ["LINNWORKS_APP_ID", "LINNWORKS_APP_SECRET"],
        data_provided=[
            "orders", "inventory", "listings",
            "shipping", "warehouse",
        ],
        icon="LW",
    ),
    Connector(
        "sellbrite", "Sellbrite (GoDaddy)",
        "Multi-channel listing and inventory sync",
        ConnectorCategory.MARKETPLACE, ["COO", "CMO"],
        ["SELLBRITE_API_KEY"],
        data_provided=["listings", "inventory_sync", "orders", "channels"],
        icon="SB",
    ),

    # ── Tax & Compliance ─────────────────────────────────────
    Connector(
        "avalara", "Avalara",
        "Automated tax compliance: sales tax, VAT, excise, customs",
        ConnectorCategory.TAX_COMPLIANCE, ["CFO", "CLO"],
        ["AVALARA_ACCOUNT_ID", "AVALARA_LICENSE_KEY"],
        data_provided=[
            "tax_calculation", "tax_filing", "exemptions",
            "returns", "vat", "customs_duties",
        ],
        icon="AV",
    ),
    Connector(
        "vertex", "Vertex",
        "Enterprise tax technology: indirect tax, compliance, reporting",
        ConnectorCategory.TAX_COMPLIANCE, ["CFO"],
        ["VERTEX_URL", "VERTEX_CLIENT_ID", "VERTEX_CLIENT_SECRET"],
        data_provided=[
            "tax_calculation", "compliance", "reporting",
            "audit_support", "data_integrity",
        ],
        icon="VX",
    ),
    Connector(
        "taxjar", "TaxJar (Stripe)",
        "Sales tax automation: calculation, nexus, filing",
        ConnectorCategory.TAX_COMPLIANCE, ["CFO"],
        ["TAXJAR_API_KEY"],
        data_provided=[
            "tax_calculation", "nexus_tracking",
            "auto_filing", "reporting",
        ],
        icon="TJ",
    ),
    Connector(
        "sovos", "Sovos",
        "Global tax compliance: VAT, e-invoicing, 1099, regulatory reporting",
        ConnectorCategory.TAX_COMPLIANCE, ["CFO", "CLO"],
        ["SOVOS_API_KEY"],
        data_provided=[
            "vat_compliance", "e_invoicing", "tax_reporting",
            "1099", "regulatory",
        ],
        icon="SV",
    ),

    # ── Travel & Expense Management ──────────────────────────
    Connector(
        "sap_concur", "SAP Concur",
        "Travel booking, expense management, invoice processing",
        ConnectorCategory.TRAVEL_EXPENSE, ["CFO", "COO"],
        ["CONCUR_CLIENT_ID", "CONCUR_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "travel_requests", "expense_reports", "invoices",
            "itineraries", "receipts", "policy_compliance",
        ],
        icon="SC",
    ),
    Connector(
        "navan", "Navan (TripActions)",
        "Business travel and expense management",
        ConnectorCategory.TRAVEL_EXPENSE, ["CFO", "COO"],
        ["NAVAN_API_KEY"],
        data_provided=[
            "travel_bookings", "expenses", "policy_compliance",
            "carbon_tracking", "analytics",
        ],
        icon="NV",
    ),
    Connector(
        "travelperk", "TravelPerk",
        "Business travel management, booking, approvals",
        ConnectorCategory.TRAVEL_EXPENSE, ["CFO", "COO"],
        ["TRAVELPERK_API_KEY"],
        data_provided=[
            "bookings", "invoices", "travelers",
            "approvals", "sustainability",
        ],
        icon="TP",
    ),

    # ── Learning & Development ───────────────────────────────
    Connector(
        "cornerstone", "Cornerstone OnDemand",
        "Learning management, talent management, content",
        ConnectorCategory.LEARNING, ["CHRO"],
        ["CORNERSTONE_URL", "CORNERSTONE_API_KEY"],
        data_provided=[
            "courses", "enrollments", "completions",
            "certifications", "skills", "learning_paths",
        ],
        icon="CS",
    ),
    Connector(
        "docebo", "Docebo",
        "AI-powered LMS: learning, training, compliance",
        ConnectorCategory.LEARNING, ["CHRO"],
        ["DOCEBO_URL", "DOCEBO_CLIENT_ID", "DOCEBO_CLIENT_SECRET"],
        data_provided=[
            "courses", "users", "certifications",
            "analytics", "compliance_training",
        ],
        icon="DO",
    ),
    Connector(
        "lessonly", "Lessonly (Seismic)",
        "Team training and enablement platform",
        ConnectorCategory.LEARNING, ["CHRO", "CSO"],
        ["LESSONLY_API_KEY"],
        data_provided=["lessons", "paths", "completions", "practice"],
        icon="LS",
    ),

    # ── Real Estate / Facilities ─────────────────────────────
    Connector(
        "envoy", "Envoy",
        "Workplace platform: visitor management, desks, deliveries",
        ConnectorCategory.REAL_ESTATE, ["COO"],
        ["ENVOY_API_KEY"],
        data_provided=[
            "visitors", "deliveries", "desk_bookings",
            "rooms", "capacity",
        ],
        icon="EV",
    ),
    Connector(
        "robin", "Robin",
        "Hybrid office management: desks, rooms, scheduling",
        ConnectorCategory.REAL_ESTATE, ["COO", "CHRO"],
        ["ROBIN_API_KEY"],
        data_provided=[
            "desks", "rooms", "reservations",
            "office_analytics", "capacity",
        ],
        icon="RB",
    ),

    # ── CMS (Content Management Systems) ─────────────────────
    Connector(
        "contentful", "Contentful",
        "Headless CMS: content models, entries, assets, locales, publishing",
        ConnectorCategory.CMS, ["CMO", "COO"],
        ["CONTENTFUL_SPACE_ID", "CONTENTFUL_ACCESS_TOKEN"],
        data_provided=[
            "entries", "content_types", "assets", "locales",
            "publishing_status", "scheduled_content", "webhooks",
        ],
        icon="CF",
    ),
    Connector(
        "strapi", "Strapi",
        "Open-source headless CMS: content types, REST/GraphQL, media",
        ConnectorCategory.CMS, ["CMO", "COO"],
        ["STRAPI_URL", "STRAPI_API_TOKEN"],
        data_provided=[
            "content_types", "entries", "media",
            "users", "roles", "webhooks",
        ],
        icon="ST",
    ),
    Connector(
        "wordpress", "WordPress",
        "Website CMS: posts, pages, media, SEO, WooCommerce",
        ConnectorCategory.CMS, ["CMO"],
        ["WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD"],
        data_provided=[
            "posts", "pages", "media", "comments",
            "categories", "tags", "users", "seo_metadata",
        ],
        icon="WP",
    ),
    Connector(
        "sanity", "Sanity",
        "Structured content platform: real-time editing, GROQ queries",
        ConnectorCategory.CMS, ["CMO"],
        ["SANITY_PROJECT_ID", "SANITY_TOKEN"],
        data_provided=[
            "documents", "assets", "schemas",
            "datasets", "history", "webhooks",
        ],
        icon="SN",
    ),
    Connector(
        "prismic", "Prismic",
        "Headless CMS: slices, custom types, scheduling, A/B testing",
        ConnectorCategory.CMS, ["CMO"],
        ["PRISMIC_REPO", "PRISMIC_ACCESS_TOKEN"],
        data_provided=[
            "documents", "custom_types", "slices",
            "releases", "experiments",
        ],
        icon="PR",
    ),
    Connector(
        "storyblok", "Storyblok",
        "Headless CMS with visual editor: stories, components, assets",
        ConnectorCategory.CMS, ["CMO"],
        ["STORYBLOK_API_KEY"],
        data_provided=[
            "stories", "components", "assets",
            "datasources", "spaces", "activity_log",
        ],
        icon="SB",
    ),
    Connector(
        "ghost", "Ghost",
        "Publishing platform: posts, members, newsletters, subscriptions",
        ConnectorCategory.CMS, ["CMO"],
        ["GHOST_URL", "GHOST_ADMIN_API_KEY"],
        data_provided=[
            "posts", "pages", "members", "newsletters",
            "subscriptions", "tiers", "analytics",
        ],
        icon="GH",
    ),
    Connector(
        "webflow", "Webflow",
        "Visual web design + CMS: sites, collections, forms, e-commerce",
        ConnectorCategory.CMS, ["CMO"],
        ["WEBFLOW_API_TOKEN"],
        data_provided=[
            "sites", "collections", "items", "forms",
            "orders", "memberships", "analytics",
        ],
        icon="WF",
    ),
    Connector(
        "adobe_experience_manager", "Adobe Experience Manager (AEM)",
        "Enterprise CMS and digital experience platform",
        ConnectorCategory.CMS, ["CMO"],
        ["AEM_URL", "AEM_USER", "AEM_PASS"],
        data_provided=[
            "pages", "assets", "content_fragments",
            "workflows", "templates", "experience_fragments",
        ],
        icon="AEM",
    ),
    Connector(
        "sitecore", "Sitecore",
        "Enterprise DXP: content, personalization, commerce, analytics",
        ConnectorCategory.CMS, ["CMO"],
        ["SITECORE_URL", "SITECORE_CLIENT_ID", "SITECORE_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "content", "personalization", "analytics",
            "forms", "campaigns", "xdb_contacts",
        ],
        icon="SC",
    ),

    # ── DAM (Digital Asset Management) ───────────────────────
    Connector(
        "cloudinary", "Cloudinary",
        "Media management: images, video, transformation, CDN, AI tagging",
        ConnectorCategory.DAM, ["CMO"],
        ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"],
        data_provided=[
            "assets", "transformations", "folders",
            "tags", "analytics", "ai_tagging", "video",
        ],
        icon="CL",
    ),
    Connector(
        "bynder", "Bynder",
        "Digital asset management: brand portal, templates, workflow",
        ConnectorCategory.DAM, ["CMO"],
        ["BYNDER_URL", "BYNDER_ACCESS_TOKEN"],
        oauth=True,
        data_provided=[
            "assets", "collections", "metaproperties",
            "brand_guidelines", "templates", "workflows",
        ],
        icon="BY",
    ),
    Connector(
        "brandfolder", "Brandfolder (Smartsheet)",
        "Brand asset management: assets, guidelines, analytics",
        ConnectorCategory.DAM, ["CMO"],
        ["BRANDFOLDER_API_KEY"],
        data_provided=[
            "assets", "brand_guidelines", "collections",
            "analytics", "guest_links",
        ],
        icon="BF",
    ),
    Connector(
        "dam_io", "DAM.io (Acquia DAM / Widen)",
        "Enterprise DAM: assets, metadata, workflows, brand portals",
        ConnectorCategory.DAM, ["CMO"],
        ["WIDEN_URL", "WIDEN_ACCESS_TOKEN"],
        data_provided=[
            "assets", "metadata", "workflows",
            "portals", "embed_links", "analytics",
        ],
        icon="WD",
    ),

    # ── Product Management ───────────────────────────────────
    Connector(
        "productboard", "Productboard",
        "Product management: features, insights, roadmap, portal",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["COO", "CMO"],
        ["PRODUCTBOARD_API_TOKEN"],
        data_provided=[
            "features", "insights", "roadmap",
            "objectives", "portal", "customer_needs",
        ],
        icon="PB",
    ),
    Connector(
        "pendo", "Pendo",
        "Product analytics, in-app guidance, feedback, roadmap",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["CMO", "COO"],
        ["PENDO_INTEGRATION_KEY"],
        data_provided=[
            "usage_analytics", "guides", "feedback",
            "nps", "roadmap", "feature_adoption",
        ],
        icon="PE",
    ),
    Connector(
        "launchdarkly", "LaunchDarkly",
        "Feature flags, experimentation, progressive delivery",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["COO"],
        ["LAUNCHDARKLY_API_KEY"],
        data_provided=[
            "feature_flags", "experiments", "segments",
            "environments", "audit_log",
        ],
        icon="LD",
    ),
    Connector(
        "split", "Split.io",
        "Feature delivery, experimentation, feature flags",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["COO"],
        ["SPLIT_API_KEY"],
        data_provided=["feature_flags", "experiments", "impressions", "metrics"],
        icon="SP",
    ),
    Connector(
        "aha", "Aha!",
        "Product roadmap, strategy, ideas portal, release planning",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["COO", "CMO"],
        ["AHA_URL", "AHA_API_KEY"],
        data_provided=[
            "ideas", "features", "releases", "roadmap",
            "strategy", "epics", "requirements",
        ],
        icon="AH",
    ),
    Connector(
        "canny", "Canny",
        "Feature request tracking, voting, changelog, roadmap",
        ConnectorCategory.PRODUCT_MANAGEMENT, ["COO", "CMO"],
        ["CANNY_API_KEY"],
        data_provided=[
            "feature_requests", "votes", "changelog",
            "roadmap", "status_updates",
        ],
        icon="CN",
    ),

    # ── Design ───────────────────────────────────────────────
    Connector(
        "figma", "Figma",
        "Design files, components, comments, dev handoff, variables",
        ConnectorCategory.DESIGN, ["CMO", "COO"],
        ["FIGMA_ACCESS_TOKEN"],
        data_provided=[
            "files", "components", "comments",
            "teams", "projects", "versions",
        ],
        icon="FG",
    ),
    Connector(
        "canva", "Canva (Enterprise)",
        "Design platform: templates, brand kit, team collaboration",
        ConnectorCategory.DESIGN, ["CMO"],
        ["CANVA_API_KEY"],
        oauth=True,
        data_provided=[
            "designs", "templates", "brand_kit",
            "folders", "team_activity",
        ],
        icon="CV",
    ),
    Connector(
        "adobe_creative_cloud", "Adobe Creative Cloud",
        "Creative suite: Photoshop, Illustrator, Premiere, libraries",
        ConnectorCategory.DESIGN, ["CMO"],
        ["ADOBE_CLIENT_ID", "ADOBE_CLIENT_SECRET"],
        oauth=True,
        data_provided=[
            "libraries", "assets", "fonts",
            "colors", "projects",
        ],
        icon="AC",
    ),

    # ── Observability / Error Monitoring ─────────────────────
    Connector(
        "new_relic", "New Relic",
        "Full-stack observability: APM, infrastructure, logs, synthetics, AIOps",
        ConnectorCategory.OBSERVABILITY, ["COO"],
        ["NEW_RELIC_API_KEY", "NEW_RELIC_ACCOUNT_ID"],
        data_provided=[
            "apm", "infrastructure", "logs", "synthetics",
            "browser", "mobile", "alerts", "dashboards",
        ],
        icon="NR",
    ),
    Connector(
        "elastic", "Elastic (ELK Stack)",
        "Search, observability, security: Elasticsearch, Kibana, APM",
        ConnectorCategory.OBSERVABILITY, ["COO"],
        ["ELASTIC_URL", "ELASTIC_API_KEY"],
        data_provided=[
            "logs", "metrics", "apm", "uptime",
            "security", "dashboards",
        ],
        icon="EL",
    ),
    Connector(
        "grafana", "Grafana",
        "Observability dashboards: metrics, logs, traces from any source",
        ConnectorCategory.OBSERVABILITY, ["COO"],
        ["GRAFANA_URL", "GRAFANA_API_KEY"],
        data_provided=[
            "dashboards", "alerts", "annotations",
            "datasources", "panels",
        ],
        icon="GF",
    ),
    Connector(
        "instabug", "Instabug",
        "Mobile bug reporting, crash analytics, performance monitoring, surveys",
        ConnectorCategory.OBSERVABILITY, ["COO", "CMO"],
        ["INSTABUG_API_TOKEN"],
        data_provided=[
            "bug_reports", "crash_reports", "performance",
            "session_replay", "surveys", "feature_requests",
        ],
        icon="IB",
    ),
    Connector(
        "bugsnag", "Bugsnag",
        "Error monitoring: stability score, error grouping, release tracking",
        ConnectorCategory.OBSERVABILITY, ["COO"],
        ["BUGSNAG_API_KEY"],
        data_provided=[
            "errors", "stability_score", "releases",
            "sessions", "breadcrumbs",
        ],
        icon="BS",
    ),
    Connector(
        "rollbar", "Rollbar",
        "Real-time error tracking, deploy tracking, people tracking",
        ConnectorCategory.OBSERVABILITY, ["COO"],
        ["ROLLBAR_ACCESS_TOKEN"],
        data_provided=[
            "errors", "deploys", "rql_queries",
            "people_tracking", "alerts",
        ],
        icon="RB",
    ),
    Connector(
        "crashlytics_standalone", "Firebase Crashlytics",
        "Dedicated crash reporting: crash-free rate, ANR rate, stack traces, "
        "velocity alerts, regression detection",
        ConnectorCategory.OBSERVABILITY, ["COO", "CSO"],
        ["FIREBASE_CREDENTIALS_JSON", "FIREBASE_PROJECT_ID"],
        data_provided=[
            "crash_free_rate", "crash_reports", "anr_rate",
            "stack_traces", "velocity_alerts", "regressions",
            "affected_users", "device_breakdown",
        ],
        icon="FC",
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
