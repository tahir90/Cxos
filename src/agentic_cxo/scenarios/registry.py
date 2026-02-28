"""
Scenario Registry — all 14 high-impact CXO scenarios defined as workflows.

Each scenario is a Scenario object with ordered ScenarioSteps that the
ScenarioEngine can execute end-to-end.
"""

from __future__ import annotations

from agentic_cxo.models import ActionRisk
from agentic_cxo.scenarios.engine import Scenario, ScenarioStep

# ═══════════════════════════════════════════════════════════════════════
# CFO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

CASH_FLOW_GUARDIAN = Scenario(
    scenario_id="cfo-cash-flow-guardian",
    name="The Cash-Flow Guardian",
    description=(
        "Burn rate increased by 12%. Identify the three largest non-payroll "
        "expense spikes, audit those vendors for duplicate billing, and "
        "re-forecast runway if we cut marketing spend by 15%."
    ),
    agent_role="CFO",
    category="finance",
    tags=["burn-rate", "expenses", "runway", "audit"],
    steps=[
        ScenarioStep(
            step_id="cfg-1",
            title="Detect expense spikes",
            description=(
                "Pull all non-payroll expenses for this month vs. last month. "
                "Rank by absolute increase and identify the top 3 spikes."
            ),
            agent_role="CFO",
            risk=ActionRisk.LOW,
            vault_query="non-payroll expenses increase monthly burn rate",
            output_key="expense_spikes",
        ),
        ScenarioStep(
            step_id="cfg-2",
            title="Audit vendors for duplicate billing",
            description=(
                "For each of the top 3 expense spikes, pull the vendor's "
                "invoice history. Flag any duplicate line items, overlapping "
                "date ranges, or charges that exceed contracted rates."
            ),
            agent_role="CFO",
            risk=ActionRisk.MEDIUM,
            vault_query="vendor invoices duplicate billing charges",
            depends_on=["cfg-1"],
            output_key="audit_results",
        ),
        ScenarioStep(
            step_id="cfg-3",
            title="Re-forecast runway with 15% marketing cut",
            description=(
                "Using current burn rate and cash reserves, model two scenarios: "
                "(A) status quo and (B) 15% reduction in marketing spend "
                "starting Monday. Output projected runway in months for each."
            ),
            agent_role="CFO",
            risk=ActionRisk.LOW,
            vault_query="marketing budget cash reserves burn rate runway forecast",
            depends_on=["cfg-1"],
            output_key="runway_forecast",
        ),
        ScenarioStep(
            step_id="cfg-4",
            title="Generate executive briefing",
            description=(
                "Compile findings into an executive briefing: top 3 spikes, "
                "duplicate billing audit results, and runway scenarios A vs B. "
                "Include recommendations and risk assessment."
            ),
            agent_role="CFO",
            risk=ActionRisk.LOW,
            depends_on=["cfg-2", "cfg-3"],
            output_key="briefing",
        ),
    ],
)

TAX_STRATEGIST = Scenario(
    scenario_id="cfo-tax-strategist",
    name="The Tax Strategist",
    description=(
        "Scan all communications for R&D keywords. Cross-reference with "
        "payroll data and generate an R&D Tax Credit report compliant "
        "with 2026 IRS guidelines."
    ),
    agent_role="CFO",
    category="finance",
    tags=["tax", "r&d-credit", "irs", "compliance"],
    steps=[
        ScenarioStep(
            step_id="ts-1",
            title="Scan communications for R&D keywords",
            description=(
                "Search Slack channels, Jira tickets, and internal documents "
                "from Q4 for keywords: 'research', 'development', 'prototype', "
                "'experiment', 'testing', 'innovation', 'patent'."
            ),
            agent_role="CFO",
            risk=ActionRisk.LOW,
            vault_query="research development prototype experiment Q4 R&D",
            output_key="rd_mentions",
        ),
        ScenarioStep(
            step_id="ts-2",
            title="Cross-reference with payroll data",
            description=(
                "Match R&D-flagged activities to employee payroll records. "
                "Calculate the percentage of each employee's time spent on "
                "qualifying R&D activities."
            ),
            agent_role="CFO",
            risk=ActionRisk.MEDIUM,
            vault_query="payroll employee hours R&D time allocation",
            depends_on=["ts-1"],
            output_key="payroll_match",
        ),
        ScenarioStep(
            step_id="ts-3",
            title="Validate IRS compliance",
            description=(
                "Verify that all flagged activities meet the IRS four-part "
                "test for R&D Tax Credits (Section 41): technological "
                "uncertainty, process of experimentation, technological in "
                "nature, and permitted purpose."
            ),
            agent_role="CFO",
            risk=ActionRisk.MEDIUM,
            vault_query="IRS section 41 R&D tax credit four-part test 2026",
            depends_on=["ts-1"],
            output_key="irs_validation",
        ),
        ScenarioStep(
            step_id="ts-4",
            title="Generate R&D Tax Credit report",
            description=(
                "Produce the final R&D Tax Credit report with supporting "
                "documentation: qualifying activities, employee allocations, "
                "total credit amount, and IRS compliance notes."
            ),
            agent_role="CFO",
            risk=ActionRisk.HIGH,
            depends_on=["ts-2", "ts-3"],
            output_key="tax_report",
        ),
    ],
)

COLLECTIONS_ENFORCER = Scenario(
    scenario_id="cfo-collections-enforcer",
    name="The Collections Enforcer",
    description=(
        "Identify every invoice >15 days overdue. Draft escalating reminders. "
        "For VIP clients, offer a 2% early-bird discount if settled within 24h."
    ),
    agent_role="CFO",
    category="finance",
    tags=["collections", "invoices", "overdue", "vip"],
    steps=[
        ScenarioStep(
            step_id="ce-1",
            title="Identify overdue invoices",
            description=(
                "Query all open invoices. Flag those more than 15 days past "
                "due date. Sort by amount descending. Tag each client as "
                "'VIP' or 'Standard' based on the top-5 revenue list."
            ),
            agent_role="CFO",
            risk=ActionRisk.LOW,
            vault_query="invoices overdue past due outstanding accounts receivable",
            output_key="overdue_list",
        ),
        ScenarioStep(
            step_id="ce-2",
            title="Draft escalating reminder sequence",
            description=(
                "For each Standard client, draft three emails: "
                "(1) Friendly reminder at 15 days. "
                "(2) Firm notice at 30 days with late-fee warning. "
                "(3) Final demand at 45 days with collections referral."
            ),
            agent_role="CFO",
            risk=ActionRisk.MEDIUM,
            depends_on=["ce-1"],
            output_key="standard_emails",
        ),
        ScenarioStep(
            step_id="ce-3",
            title="Draft VIP early-bird discount offers",
            description=(
                "For top-5 VIP clients with overdue invoices, draft a "
                "personalized email offering a one-time 2% discount if "
                "settled via the attached payment link within 24 hours. "
                "Tone: appreciative, not punitive."
            ),
            agent_role="CFO",
            risk=ActionRisk.HIGH,
            depends_on=["ce-1"],
            output_key="vip_emails",
        ),
        ScenarioStep(
            step_id="ce-4",
            title="Schedule and send campaign",
            description=(
                "Stage all emails in the outbound queue. VIP emails go first "
                "(morning). Standard reminders go in the afternoon. Log all "
                "sends to the collections audit trail."
            ),
            agent_role="CFO",
            risk=ActionRisk.HIGH,
            depends_on=["ce-2", "ce-3"],
            output_key="send_results",
            tools=["email_sender", "audit_logger"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# CMO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

VIRAL_RESPONDER = Scenario(
    scenario_id="cmo-viral-responder",
    name="The Viral Responder",
    description=(
        "Monitor Reddit/X for competitor outage mentions. If threads exceed "
        "100 comments, draft a comparison landing page highlighting our "
        "99.9% uptime and launch a $500 targeted ad set."
    ),
    agent_role="CMO",
    category="marketing",
    tags=["social-monitoring", "competitor", "viral", "ads"],
    steps=[
        ScenarioStep(
            step_id="vr-1",
            title="Monitor social platforms for competitor mentions",
            description=(
                "Scan Reddit and X (Twitter) for mentions of the competitor's "
                "brand + keywords: 'outage', 'down', 'broken', 'unavailable'. "
                "Filter to threads with 100+ comments or high engagement."
            ),
            agent_role="CMO",
            risk=ActionRisk.LOW,
            vault_query="competitor outage downtime social media mentions",
            output_key="viral_threads",
            tools=["social_monitor"],
        ),
        ScenarioStep(
            step_id="vr-2",
            title="Draft comparison landing page",
            description=(
                "Create a landing page highlighting: our 99.9% uptime SLA, "
                "migration ease, and customer testimonials. Include a CTA "
                "for a free trial. Tone: empathetic, not aggressive."
            ),
            agent_role="CMO",
            risk=ActionRisk.MEDIUM,
            vault_query="uptime SLA reliability testimonials migration",
            depends_on=["vr-1"],
            output_key="landing_page",
        ),
        ScenarioStep(
            step_id="vr-3",
            title="Configure targeted ad set",
            description=(
                "Build a $500 ad campaign targeting users who engaged with "
                "competitor outage threads. Platform: Reddit + X ads. "
                "Creative: link to the comparison landing page. "
                "Duration: 72 hours."
            ),
            agent_role="CMO",
            risk=ActionRisk.HIGH,
            depends_on=["vr-2"],
            output_key="ad_campaign",
            tools=["ad_platform"],
        ),
        ScenarioStep(
            step_id="vr-4",
            title="Launch and monitor campaign",
            description=(
                "Deploy the landing page and activate the ad set. "
                "Set up real-time monitoring for CTR, conversion rate, "
                "and cost-per-acquisition. Auto-pause if CPA exceeds $50."
            ),
            agent_role="CMO",
            risk=ActionRisk.HIGH,
            depends_on=["vr-3"],
            output_key="launch_metrics",
            tools=["ad_platform", "analytics"],
        ),
    ],
)

CHURN_ARCHITECT = Scenario(
    scenario_id="cmo-churn-architect",
    name="The Churn Architect",
    description=(
        "Flag Pro-plan users inactive for 7+ days. Review their support "
        "tickets to find pain points. Send personalized Loom video "
        "invitations to solve their specific issues."
    ),
    agent_role="CMO",
    category="marketing",
    tags=["churn", "retention", "personalization", "pro-plan"],
    steps=[
        ScenarioStep(
            step_id="ca-1",
            title="Identify at-risk Pro users",
            description=(
                "Query the user database for Pro-plan subscribers who "
                "haven't logged in for 7+ days. Rank by account value "
                "(MRR) descending."
            ),
            agent_role="CMO",
            risk=ActionRisk.LOW,
            vault_query="user activity login pro plan subscribers churn",
            output_key="at_risk_users",
            tools=["user_database"],
        ),
        ScenarioStep(
            step_id="ca-2",
            title="Analyze support ticket pain points",
            description=(
                "For each at-risk user, pull their last 3 support tickets. "
                "Classify the primary pain point: onboarding, feature gap, "
                "bug, performance, or billing."
            ),
            agent_role="CMO",
            risk=ActionRisk.LOW,
            vault_query="support tickets complaints issues pain points",
            depends_on=["ca-1"],
            output_key="pain_points",
        ),
        ScenarioStep(
            step_id="ca-3",
            title="Draft personalized Loom video invitations",
            description=(
                "For each at-risk user, draft an email with: "
                "(1) Acknowledge their specific pain point by name. "
                "(2) Invite them to a personalized 1-on-1 Loom walkthrough. "
                "(3) Include a calendar booking link. "
                "Tone: genuinely helpful, not salesy."
            ),
            agent_role="CMO",
            risk=ActionRisk.MEDIUM,
            depends_on=["ca-2"],
            output_key="outreach_emails",
        ),
        ScenarioStep(
            step_id="ca-4",
            title="Send and track re-engagement",
            description=(
                "Send all emails via the CRM. Track open rates, reply rates, "
                "and re-login events over the next 7 days. Report the "
                "save rate vs. churn rate."
            ),
            agent_role="CMO",
            risk=ActionRisk.MEDIUM,
            depends_on=["ca-3"],
            output_key="engagement_metrics",
            tools=["crm", "email_sender", "analytics"],
        ),
    ],
)

GLOBAL_LOCALIZER = Scenario(
    scenario_id="cmo-global-localizer",
    name="The Global Localizer",
    description=(
        "Take the top-performing US ad creative and localize for Brazil. "
        "Adjust pricing to BRL via purchasing power parity, swap imagery, "
        "and schedule the Tuesday launch."
    ),
    agent_role="CMO",
    category="marketing",
    tags=["localization", "international", "brazil", "ppp", "creative"],
    steps=[
        ScenarioStep(
            step_id="gl-1",
            title="Identify top US creative",
            description=(
                "Pull performance data for all active US ad creatives. "
                "Select the top performer by ROAS (return on ad spend). "
                "Extract copy, imagery, CTA, and pricing."
            ),
            agent_role="CMO",
            risk=ActionRisk.LOW,
            vault_query="ad creative performance ROAS US campaign top",
            output_key="source_creative",
        ),
        ScenarioStep(
            step_id="gl-2",
            title="Adjust pricing via PPP",
            description=(
                "Convert USD pricing to BRL using current purchasing power "
                "parity data (not just exchange rate). Factor in local "
                "competitor pricing and willingness-to-pay signals."
            ),
            agent_role="CMO",
            risk=ActionRisk.MEDIUM,
            vault_query="purchasing power parity Brazil BRL pricing",
            depends_on=["gl-1"],
            output_key="localized_pricing",
        ),
        ScenarioStep(
            step_id="gl-3",
            title="Localize creative assets",
            description=(
                "Translate ad copy to Brazilian Portuguese (not European). "
                "Swap background imagery for culturally relevant Brazilian "
                "assets. Adjust color palette if needed for local preferences."
            ),
            agent_role="CMO",
            risk=ActionRisk.MEDIUM,
            depends_on=["gl-1"],
            output_key="localized_creative",
            tools=["translation_api", "asset_library"],
        ),
        ScenarioStep(
            step_id="gl-4",
            title="Schedule Tuesday launch",
            description=(
                "Upload the localized creative to the ad platform. "
                "Set the launch date to next Tuesday at 9:00 AM BRT. "
                "Configure targeting for Brazil, ages 25-45, "
                "with interest-based audience matching."
            ),
            agent_role="CMO",
            risk=ActionRisk.HIGH,
            depends_on=["gl-2", "gl-3"],
            output_key="launch_schedule",
            tools=["ad_platform"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# CHRO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

HEADHUNTER = Scenario(
    scenario_id="chro-headhunter",
    name="The Headhunter",
    description=(
        "Recruit a Lead Rust Engineer with ZK-proof experience. Scrape "
        "GitHub for library contributors, find contacts, and send "
        "personalized outreach referencing their recent commits."
    ),
    agent_role="CHRO",
    category="people",
    tags=["recruiting", "engineering", "rust", "zk-proofs", "github"],
    steps=[
        ScenarioStep(
            step_id="hh-1",
            title="Scrape GitHub for target contributors",
            description=(
                "Search GitHub for top contributors to ZK-proof Rust "
                "libraries (e.g., bellman, arkworks, halo2). Filter for "
                "contributors with 50+ commits in the last 12 months."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            vault_query="rust engineer zero knowledge proof github contributor",
            output_key="candidate_list",
            tools=["github_api"],
        ),
        ScenarioStep(
            step_id="hh-2",
            title="Enrich candidate profiles",
            description=(
                "For each candidate, find: LinkedIn profile, personal blog, "
                "email (from git commits or personal site), and their most "
                "recent notable commit or PR."
            ),
            agent_role="CHRO",
            risk=ActionRisk.MEDIUM,
            depends_on=["hh-1"],
            output_key="enriched_profiles",
            tools=["linkedin_api", "contact_finder"],
        ),
        ScenarioStep(
            step_id="hh-3",
            title="Match candidates to our roadmap",
            description=(
                "Cross-reference each candidate's expertise (from their "
                "commit history) with our current engineering roadmap. "
                "Score relevance 1-10."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            vault_query="engineering roadmap rust zk proof milestones",
            depends_on=["hh-2"],
            output_key="relevance_scores",
        ),
        ScenarioStep(
            step_id="hh-4",
            title="Draft personalized outreach",
            description=(
                "For the top 10 candidates, draft a personalized email that: "
                "(1) Mentions their specific recent commit and why it's relevant. "
                "(2) Describes the role and what makes our team unique. "
                "(3) Includes a clear CTA to schedule a 15-min chat."
            ),
            agent_role="CHRO",
            risk=ActionRisk.HIGH,
            depends_on=["hh-3"],
            output_key="outreach_drafts",
        ),
    ],
)

CULTURE_PULSE = Scenario(
    scenario_id="chro-culture-pulse",
    name="The Culture Pulse",
    description=(
        "Anonymously analyze 30 days of internal Slack sentiment. "
        "Identify the primary source of workplace friction and draft "
        "a 3-point action plan for the All-Hands."
    ),
    agent_role="CHRO",
    category="people",
    tags=["culture", "sentiment", "slack", "retention", "morale"],
    steps=[
        ScenarioStep(
            step_id="cp-1",
            title="Ingest and anonymize Slack messages",
            description=(
                "Pull the last 30 days of public Slack channel messages. "
                "Strip all personally identifiable information. Replace "
                "names with anonymous identifiers."
            ),
            agent_role="CHRO",
            risk=ActionRisk.MEDIUM,
            vault_query="internal slack messages team communication",
            output_key="anonymized_messages",
            tools=["slack_api"],
        ),
        ScenarioStep(
            step_id="cp-2",
            title="Run sentiment analysis",
            description=(
                "Classify each message as positive, neutral, or negative. "
                "Aggregate by channel and by week. Identify the channels "
                "and time periods with the most negative sentiment."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            depends_on=["cp-1"],
            output_key="sentiment_report",
        ),
        ScenarioStep(
            step_id="cp-3",
            title="Identify friction sources",
            description=(
                "From the negative-sentiment clusters, extract the top "
                "themes: tooling frustration, process overhead, unclear "
                "expectations, workload imbalance, or interpersonal friction. "
                "Rank by frequency and intensity."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            depends_on=["cp-2"],
            output_key="friction_analysis",
        ),
        ScenarioStep(
            step_id="cp-4",
            title="Draft 3-point action plan",
            description=(
                "Produce a concise 3-point action plan for the founders to "
                "present at the next All-Hands. Each point should: name the "
                "issue, propose a concrete fix, and include a measurable "
                "success metric for 30 days out."
            ),
            agent_role="CHRO",
            risk=ActionRisk.MEDIUM,
            depends_on=["cp-3"],
            output_key="action_plan",
        ),
    ],
)

AUTOMATED_ONBOARDER = Scenario(
    scenario_id="chro-automated-onboarder",
    name="The Automated Onboarder",
    description=(
        "New Sales Director signed. Provision Salesforce/Slack/Gmail, "
        "build a 5-day training curriculum from the Sales Playbook, "
        "and schedule exec intro calls."
    ),
    agent_role="CHRO",
    category="people",
    tags=["onboarding", "provisioning", "training", "new-hire"],
    steps=[
        ScenarioStep(
            step_id="ao-1",
            title="Provision SaaS accounts",
            description=(
                "Create accounts for the new Sales Director in: "
                "Salesforce (Sales role), Slack (add to #sales, #general, "
                "#leadership channels), and Gmail (firstname.lastname@company). "
                "Set temporary passwords and enable MFA."
            ),
            agent_role="CHRO",
            risk=ActionRisk.MEDIUM,
            output_key="provisioned_accounts",
            tools=["salesforce_admin", "slack_admin", "google_admin"],
        ),
        ScenarioStep(
            step_id="ao-2",
            title="Build 5-day training curriculum",
            description=(
                "Parse the Sales Playbook from Notion. Extract key topics: "
                "ICP definition, objection handling, demo flow, pricing "
                "strategy, and CRM workflow. Create a day-by-day schedule "
                "with reading material and practice exercises."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            vault_query="sales playbook training onboarding curriculum",
            output_key="training_plan",
        ),
        ScenarioStep(
            step_id="ao-3",
            title="Schedule executive intro calls",
            description=(
                "Find open 30-minute slots on the calendars of: CEO, VP Sales, "
                "Head of Product, and Head of Engineering. Book intro calls "
                "within the first 5 days. Send calendar invites with context "
                "about the new hire's background."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            depends_on=["ao-1"],
            output_key="scheduled_meetings",
            tools=["calendar_api"],
        ),
        ScenarioStep(
            step_id="ao-4",
            title="Send welcome package",
            description=(
                "Email the new hire with: account credentials (encrypted), "
                "the 5-day training plan, meeting schedule, team org chart, "
                "and a personal welcome note from the CEO."
            ),
            agent_role="CHRO",
            risk=ActionRisk.LOW,
            depends_on=["ao-1", "ao-2", "ao-3"],
            output_key="welcome_email",
            tools=["email_sender"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# CLO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

CONTRACT_SENTINEL = Scenario(
    scenario_id="clo-contract-sentinel",
    name="The Contract Sentinel",
    description=(
        "Scan a new MSA for auto-renewal clauses and liability shifts. "
        "Redline problematic sections to match our corporate standard "
        "and email the draft back to the vendor's legal team."
    ),
    agent_role="CLO",
    category="legal",
    tags=["contract", "msa", "redline", "auto-renewal", "liability"],
    steps=[
        ScenarioStep(
            step_id="cs-1",
            title="Ingest and parse MSA",
            description=(
                "Parse the vendor's Master Service Agreement. Extract all "
                "clauses into structured sections: Term, Auto-Renewal, "
                "Termination, Liability, Indemnification, IP, Governing Law."
            ),
            agent_role="CLO",
            risk=ActionRisk.LOW,
            vault_query="master service agreement contract clauses template",
            output_key="parsed_clauses",
        ),
        ScenarioStep(
            step_id="cs-2",
            title="Flag problematic clauses",
            description=(
                "Compare each clause against our corporate standard templates. "
                "Flag: (1) Auto-renewal without 30-day opt-out. "
                "(2) Liability caps below $1M. (3) Indemnification that "
                "shifts risk to us. (4) IP assignment beyond deliverables."
            ),
            agent_role="CLO",
            risk=ActionRisk.MEDIUM,
            vault_query="corporate standard contract liability indemnification IP",
            depends_on=["cs-1"],
            output_key="flagged_clauses",
        ),
        ScenarioStep(
            step_id="cs-3",
            title="Generate redlined version",
            description=(
                "For each flagged clause, draft replacement language that "
                "matches our corporate standard. Mark changes in redline "
                "format with explanatory comments."
            ),
            agent_role="CLO",
            risk=ActionRisk.HIGH,
            depends_on=["cs-2"],
            output_key="redlined_draft",
        ),
        ScenarioStep(
            step_id="cs-4",
            title="Email redline to vendor legal",
            description=(
                "Draft a professional cover email to the vendor's legal alias. "
                "Attach the redlined MSA. Summarize the key changes requested. "
                "Propose a call to discuss within 5 business days."
            ),
            agent_role="CLO",
            risk=ActionRisk.HIGH,
            depends_on=["cs-3"],
            output_key="sent_email",
            tools=["email_sender"],
        ),
    ],
)

IP_DEFENDER = Scenario(
    scenario_id="clo-ip-defender",
    name="The IP Defender",
    description=(
        "Weekly sweep of App Store and Shopify for trademark violations. "
        "Verify against our partner database. Draft Cease & Desist for "
        "non-partners."
    ),
    agent_role="CLO",
    category="legal",
    tags=["ip", "trademark", "cease-desist", "app-store", "shopify"],
    steps=[
        ScenarioStep(
            step_id="ip-1",
            title="Sweep app stores for trademark usage",
            description=(
                "Search the Apple App Store, Google Play Store, and Shopify "
                "App Store for any products using our trademarked terms, "
                "logos, or UI design assets."
            ),
            agent_role="CLO",
            risk=ActionRisk.LOW,
            vault_query="trademark registered marks brand assets logos",
            output_key="potential_violations",
            tools=["app_store_api", "shopify_api"],
        ),
        ScenarioStep(
            step_id="ip-2",
            title="Cross-reference partner database",
            description=(
                "For each potential violation, check if the publisher is in "
                "our authorized partner database. Filter out licensed partners. "
                "Tag remaining as 'unauthorized use'."
            ),
            agent_role="CLO",
            risk=ActionRisk.LOW,
            vault_query="authorized partners licensed distributors agreements",
            depends_on=["ip-1"],
            output_key="confirmed_violations",
        ),
        ScenarioStep(
            step_id="ip-3",
            title="Draft Cease & Desist letters",
            description=(
                "For each confirmed unauthorized use, draft a formal C&D "
                "letter citing: the specific trademark registration number, "
                "the infringing product, and the required actions (remove "
                "within 14 business days)."
            ),
            agent_role="CLO",
            risk=ActionRisk.HIGH,
            depends_on=["ip-2"],
            output_key="cd_letters",
        ),
        ScenarioStep(
            step_id="ip-4",
            title="Send and log C&D notices",
            description=(
                "Send each C&D letter via certified email. Log the send "
                "date, recipient, and case number in the IP enforcement "
                "tracker. Set a 14-day follow-up reminder."
            ),
            agent_role="CLO",
            risk=ActionRisk.HIGH,
            depends_on=["ip-3"],
            output_key="enforcement_log",
            tools=["email_sender", "case_tracker"],
        ),
    ],
)

REGULATORY_AUDITOR = Scenario(
    scenario_id="clo-regulatory-auditor",
    name="The Regulatory Auditor",
    description=(
        "Summarize the impact of the California AI Transparency Act on "
        "our data processing. Flag agents needing human-in-the-loop "
        "triggers to comply by the June 1st deadline."
    ),
    agent_role="CLO",
    category="legal",
    tags=["regulation", "ai-transparency", "california", "compliance", "hitl"],
    steps=[
        ScenarioStep(
            step_id="ra-1",
            title="Parse the regulation",
            description=(
                "Ingest the full text of the California AI Transparency Act. "
                "Extract key requirements: disclosure obligations, "
                "human-in-the-loop mandates, data processing restrictions, "
                "and penalties for non-compliance."
            ),
            agent_role="CLO",
            risk=ActionRisk.LOW,
            vault_query=(
                "California AI Transparency Act regulation requirements "
                "disclosure human-in-the-loop"
            ),
            output_key="regulation_summary",
        ),
        ScenarioStep(
            step_id="ra-2",
            title="Map our data processing flows",
            description=(
                "Catalog all current AI agents and their data processing "
                "flows: what data they access, what decisions they make, "
                "and whether they have human oversight."
            ),
            agent_role="CLO",
            risk=ActionRisk.LOW,
            vault_query="data processing flows AI agents decisions automated",
            depends_on=["ra-1"],
            output_key="agent_catalog",
        ),
        ScenarioStep(
            step_id="ra-3",
            title="Flag non-compliant agents",
            description=(
                "Cross-reference the regulation requirements with our agent "
                "catalog. Identify the specific agents that currently lack "
                "required human-in-the-loop triggers. Rank by compliance gap."
            ),
            agent_role="CLO",
            risk=ActionRisk.MEDIUM,
            depends_on=["ra-1", "ra-2"],
            output_key="compliance_gaps",
        ),
        ScenarioStep(
            step_id="ra-4",
            title="Generate compliance remediation plan",
            description=(
                "For each non-compliant agent, specify: the exact trigger "
                "point where HITL must be added, the implementation effort "
                "(days), and a prioritized timeline to meet the June 1st "
                "deadline."
            ),
            agent_role="CLO",
            risk=ActionRisk.HIGH,
            depends_on=["ra-3"],
            output_key="remediation_plan",
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# CSO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

GHOSTBUSTER = Scenario(
    scenario_id="cso-ghostbuster",
    name="The Ghostbuster",
    description=(
        "Fortune 500 deal stalled for 14 days. Research the prospect's "
        "recent news. Draft a follow-up that congratulates their recent "
        "acquisition and proposes a Phase 1 pilot."
    ),
    agent_role="CSO",
    category="sales",
    tags=["deal-recovery", "follow-up", "enterprise", "personalized"],
    steps=[
        ScenarioStep(
            step_id="gb-1",
            title="Identify stalled deals",
            description=(
                "Query the CRM for all deals in 'Negotiation' or 'Proposal' "
                "stage that haven't had activity in 14+ days. Filter for "
                "Fortune 500 accounts. Sort by deal size descending."
            ),
            agent_role="CSO",
            risk=ActionRisk.LOW,
            vault_query="sales pipeline stalled deals inactive fortune 500",
            output_key="stalled_deals",
            tools=["crm"],
        ),
        ScenarioStep(
            step_id="gb-2",
            title="Research prospect intelligence",
            description=(
                "For each stalled deal, search LinkedIn, company press "
                "releases, and news for: recent acquisitions, leadership "
                "changes, product launches, or funding rounds from the "
                "last 30 days."
            ),
            agent_role="CSO",
            risk=ActionRisk.LOW,
            vault_query="prospect company news acquisitions leadership changes",
            depends_on=["gb-1"],
            output_key="prospect_intel",
            tools=["linkedin_api", "news_api"],
        ),
        ScenarioStep(
            step_id="gb-3",
            title="Draft personalized follow-ups",
            description=(
                "For each deal, draft a follow-up email that: "
                "(1) Congratulates them on the specific recent event. "
                "(2) Connects our product to their new situation. "
                "(3) Proposes a concrete 'Phase 1' pilot scoped to their "
                "new corporate structure. Include specific numbers."
            ),
            agent_role="CSO",
            risk=ActionRisk.HIGH,
            depends_on=["gb-2"],
            output_key="follow_up_drafts",
        ),
        ScenarioStep(
            step_id="gb-4",
            title="Send follow-ups and update CRM",
            description=(
                "Send each email via the sales sequencer. Update the CRM "
                "with the activity, the intelligence gathered, and set a "
                "3-day follow-up task. Notify the account owner."
            ),
            agent_role="CSO",
            risk=ActionRisk.HIGH,
            depends_on=["gb-3"],
            output_key="outreach_results",
            tools=["email_sender", "crm"],
        ),
    ],
)

PIPELINE_OPTIMIZER = Scenario(
    scenario_id="cso-pipeline-optimizer",
    name="The Pipeline Optimizer",
    description=(
        "Analyze Closed-Lost deals from 6 months. Identify top 3 requested "
        "features. Cross-reference with the engineering roadmap and identify "
        "5 prospects to re-engage today."
    ),
    agent_role="CSO",
    category="sales",
    tags=["pipeline", "closed-lost", "feature-gap", "re-engagement"],
    steps=[
        ScenarioStep(
            step_id="po-1",
            title="Analyze Closed-Lost deals",
            description=(
                "Pull all deals marked 'Closed-Lost' in the last 6 months. "
                "For each, extract: deal size, loss reason, competitor "
                "mentioned, and any feature requests from call notes."
            ),
            agent_role="CSO",
            risk=ActionRisk.LOW,
            vault_query="closed lost deals reasons features competitor analysis",
            output_key="lost_deal_analysis",
            tools=["crm"],
        ),
        ScenarioStep(
            step_id="po-2",
            title="Identify top 3 feature gaps",
            description=(
                "Aggregate all feature requests from lost deals. Rank by "
                "frequency and total deal value lost. Identify the top 3 "
                "features that, if built, would have closed the most revenue."
            ),
            agent_role="CSO",
            risk=ActionRisk.LOW,
            depends_on=["po-1"],
            output_key="feature_gaps",
        ),
        ScenarioStep(
            step_id="po-3",
            title="Cross-reference with engineering roadmap",
            description=(
                "Check which of the top 3 features are on the current "
                "engineering roadmap. For each, find: planned release date, "
                "current status (planned/in-progress/shipped), and any "
                "beta access available."
            ),
            agent_role="CSO",
            risk=ActionRisk.LOW,
            vault_query="engineering roadmap features planned release schedule",
            depends_on=["po-2"],
            output_key="roadmap_matches",
        ),
        ScenarioStep(
            step_id="po-4",
            title="Select and draft re-engagement for top 5 prospects",
            description=(
                "From the lost deals, select the 5 highest-value prospects "
                "whose requested feature is now shipped or in beta. "
                "Draft a re-engagement email that announces the feature, "
                "offers early access, and proposes a new demo call."
            ),
            agent_role="CSO",
            risk=ActionRisk.HIGH,
            depends_on=["po-3"],
            output_key="reengagement_emails",
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════

SCENARIO_REGISTRY: dict[str, Scenario] = {
    s.scenario_id: s
    for s in [
        CASH_FLOW_GUARDIAN,
        TAX_STRATEGIST,
        COLLECTIONS_ENFORCER,
        VIRAL_RESPONDER,
        CHURN_ARCHITECT,
        GLOBAL_LOCALIZER,
        HEADHUNTER,
        CULTURE_PULSE,
        AUTOMATED_ONBOARDER,
        CONTRACT_SENTINEL,
        IP_DEFENDER,
        REGULATORY_AUDITOR,
        GHOSTBUSTER,
        PIPELINE_OPTIMIZER,
    ]
}


def get_scenario(scenario_id: str) -> Scenario | None:
    return SCENARIO_REGISTRY.get(scenario_id)


def list_scenarios(category: str | None = None) -> list[Scenario]:
    scenarios = list(SCENARIO_REGISTRY.values())
    if category:
        scenarios = [s for s in scenarios if s.category == category]
    return scenarios
