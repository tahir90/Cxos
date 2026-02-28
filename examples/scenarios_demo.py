"""
Scenarios Demo — execute all 14 CXO business scenarios.

Demonstrates:
  - The Cash-Flow Guardian (CFO)
  - The Tax Strategist (CFO)
  - The Collections Enforcer (CFO)
  - The Viral Responder (CMO)
  - The Churn Architect (CMO)
  - The Global Localizer (CMO)
  - The Headhunter (CHRO)
  - The Culture Pulse (CHRO)
  - The Automated Onboarder (CHRO)
  - The Contract Sentinel (CLO)
  - The IP Defender (CLO)
  - The Regulatory Auditor (CLO)
  - The Ghostbuster (CSO)
  - The Pipeline Optimizer (CSO)

No API key needed — runs fully offline.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentic_cxo.orchestrator import Cockpit
from agentic_cxo.scenarios.registry import SCENARIO_REGISTRY

console = Console()

CATEGORY_COLORS = {
    "finance": "green",
    "marketing": "magenta",
    "people": "cyan",
    "legal": "yellow",
    "sales": "blue",
}


def main():
    console.print(
        "\n[bold cyan]"
        "══════════════════════════════════════════════════\n"
        "   AGENTIC CXO — 14 Scenario Execution Demo     \n"
        "══════════════════════════════════════════════════"
        "[/bold cyan]\n"
    )

    cockpit = Cockpit(use_llm=False)

    # Ingest sample data so the Vault has context for queries
    sample_docs = {
        "quarterly_report.pdf": (
            "Q3 2025 revenue was $12.5 million, up 22% year-over-year. "
            "Operating expenses rose to $4.1 million. Burn rate increased 12% "
            "due to new SaaS tools ($45k/mo) and contractor fees ($80k). "
            "Net profit margin improved to 18.3%. Cash reserves: $8.2M. "
            "Marketing budget: $500k/quarter. Payroll: $2.1M/month."
        ),
        "vendor_contracts.pdf": (
            "Contract #VC-2025-089 with Vendor ABC Corp. Term: 24 months, "
            "auto-renewal clause with 60-day opt-out. Penalty: $50k. "
            "Volume discount: 5% above $100k. Payment: Net 30. "
            "Non-compete clause: 12 months post-termination. "
            "Liability cap: $500k. Indemnification: mutual."
        ),
        "sales_pipeline.csv": (
            "Deal: Acme Corp (Fortune 500), Stage: Negotiation, "
            "Last activity: 18 days ago, Value: $450k. "
            "Deal: GlobalTech, Stage: Closed-Lost, Reason: Missing SSO feature. "
            "Deal: MegaCorp, Stage: Closed-Lost, Reason: No Rust SDK. "
            "Deal: DataFlow Inc, Stage: Closed-Lost, Reason: Missing webhook API."
        ),
        "engineering_roadmap.md": (
            "Q1 2026: SSO integration (shipped). Q2 2026: Rust SDK (in progress). "
            "Q3 2026: Webhook API v2 (planned). Q4 2026: ZK-proof module. "
            "Hiring: Lead Rust Engineer needed for ZK work."
        ),
        "marketing_campaigns.csv": (
            "Campaign Alpha: 2.1M impressions, $8.5k spend, ROI 3.2x. "
            "Campaign Beta: 800K impressions, $15k spend, ROI 0.8x. "
            "Campaign Gamma: 5.4M impressions, $22k spend, ROI 5.1x. "
            "Competitor XYZ had a 4-hour outage trending on Reddit."
        ),
        "hr_slack_summary.txt": (
            "Sentiment analysis of 30 days of Slack: 62% positive, 28% neutral, "
            "10% negative. Top friction: CI/CD pipeline slowness (mentioned 47 times). "
            "Secondary: unclear sprint priorities. Sales Playbook last updated Feb 2026."
        ),
        "invoices_ar.csv": (
            "Invoice #1042: Client Apex ($25,000), 22 days overdue, VIP client. "
            "Invoice #1055: Client Beta ($8,000), 18 days overdue, standard. "
            "Invoice #1061: Client Gamma ($45,000), 16 days overdue, VIP client."
        ),
        "ip_registry.txt": (
            "Trademark 'AgenticCXO' registered US #12345678. "
            "Logo assets version 3.1. Partner DB: PartnerAlpha (licensed), "
            "PartnerBeta (licensed). App Store listing 'CXO-Fake' detected, "
            "publisher: UnknownDev LLC — not in partner database."
        ),
        "ca_ai_act.txt": (
            "California AI Transparency Act 2026: all automated decision systems "
            "that affect consumer rights must disclose AI involvement. "
            "Human-in-the-loop required for: credit decisions, hiring, "
            "insurance underwriting. Penalty: $10k per violation. "
            "Deadline: June 1, 2026."
        ),
    }

    console.print("[bold]Ingesting sample business data...[/bold]\n")
    for source, text in sample_docs.items():
        result = cockpit.ingest(text, source=source)
        console.print(
            f"  [green]+[/green] {source}: "
            f"{result.total_chunks} chunks, {result.total_tokens:,} tokens"
        )

    console.print(
        f"\n  [bold]Vault:[/bold] {cockpit.vault.count()} chunks indexed\n"
    )

    # Execute all 14 scenarios
    for scenario in SCENARIO_REGISTRY.values():
        color = CATEGORY_COLORS.get(scenario.category, "white")
        console.print(Panel(
            f"[bold]{scenario.name}[/bold]\n"
            f"[dim]{scenario.description}[/dim]",
            title=f"[{color}]{scenario.agent_role}[/{color}] — {scenario.category}",
            border_style=color,
        ))

        result = cockpit.run_scenario_obj(scenario)

        table = Table(show_header=True, header_style="bold")
        table.add_column("Step", style="dim", width=8)
        table.add_column("Title", max_width=40)
        table.add_column("Risk", justify="center", width=10)
        table.add_column("Status", justify="center", width=20)
        table.add_column("Context", justify="center", width=8)

        for sr in result.step_results:
            status_map = {
                "completed": "[green]Completed[/green]",
                "blocked": "[yellow]Needs Approval[/yellow]",
                "pending": "[dim]Pending[/dim]",
                "failed": "[red]Failed[/red]",
            }
            status_str = status_map.get(sr.status.value, sr.status.value)

            risk_colors = {
                "low": "green", "medium": "yellow",
                "high": "red", "critical": "bold red",
            }
            rs = risk_colors.get(sr.action.risk.value, "white")

            table.add_row(
                sr.step_id,
                sr.action.description[:40],
                f"[{rs}]{sr.action.risk.value}[/{rs}]",
                status_str,
                str(len(sr.context_retrieved)),
            )

        console.print(table)

        summary = result.summary()
        parts = [f"[green]{summary['completed']}[/green]/{summary['total_steps']} completed"]
        if summary["blocked"] > 0:
            parts.append(f"[yellow]{summary['blocked']} awaiting approval[/yellow]")
        console.print("  " + " | ".join(parts) + "\n")

    # Final status
    status = cockpit.status()
    console.print(Panel(
        "\n".join(f"  {k}: {v}" for k, v in status.items()),
        title="Final System Status",
        border_style="green",
    ))

    pending = cockpit.pending_approvals
    if pending:
        console.print(
            f"\n[yellow bold]"
            f"{len(pending)} actions awaiting human pilot approval:"
            f"[/yellow bold]"
        )
        for p in pending[:10]:
            console.print(
                f"  [{p.risk.value}] {p.agent_role}: "
                f"{p.description[:70]}..."
            )


if __name__ == "__main__":
    main()
