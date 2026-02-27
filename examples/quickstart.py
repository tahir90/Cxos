"""
Quickstart — demonstrate the full Agentic CXO pipeline.

This example:
1. Creates a Cockpit (the pilot's control panel).
2. Ingests sample business documents into the Context Vault.
3. Dispatches objectives to AI CXO agents.
4. Shows the approval queue and decision audit trail.

No API key needed — runs fully offline with rule-based enrichment
and extractive summarization.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentic_cxo.models import Objective
from agentic_cxo.orchestrator import Cockpit

console = Console()


def main():
    console.print("\n[bold cyan]═══ Agentic CXO — Quickstart Demo ═══[/bold cyan]\n")

    # ── 1. Boot the Cockpit ──────────────────────────────────────
    cockpit = Cockpit(use_llm=False)
    console.print("[green]✓[/green] Cockpit initialized with agents:", list(cockpit.all_agents.keys()))

    # ── 2. Ingest sample documents ───────────────────────────────
    docs = {
        "quarterly_report.pdf": (
            "Q3 2025 revenue was $12.5 million, up 22% year-over-year. "
            "Operating expenses rose to $4.1 million due to the new Vietnam factory. "
            "Net profit margin improved to 18.3%. The board recommends allocating "
            "$500,000 to marketing expansion and $200,000 to legal compliance audits."
        ),
        "vendor_contract.pdf": (
            "Contract #VC-2025-089 with Vendor ABC Corp for raw material supply. "
            "Term: 24 months with auto-renewal clause. Penalty for early termination: $50,000. "
            "Volume discount: 5% on orders above $100,000. Payment terms: Net 30. "
            "This contract includes a non-compete clause for 12 months post-termination."
        ),
        "marketing_dashboard.csv": (
            "Campaign Alpha: 2.1M impressions, 45,000 clicks, $8,500 spend, ROI 3.2x. "
            "Campaign Beta: 800K impressions, 12,000 clicks, $15,000 spend, ROI 0.8x. "
            "Campaign Gamma: 5.4M impressions, 120,000 clicks, $22,000 spend, ROI 5.1x. "
            "Recommendation: immediately pause Campaign Beta and reallocate budget to Gamma."
        ),
    }

    for source, text in docs.items():
        result = cockpit.ingest(text, source=source)
        console.print(
            f"  [green]✓[/green] Ingested [bold]{source}[/bold]: "
            f"{result.total_chunks} chunks, {result.total_tokens:,} tokens"
        )

    console.print(f"\n  [bold]Vault total:[/bold] {cockpit.vault.count()} chunks indexed\n")

    # ── 3. Dispatch objectives ───────────────────────────────────
    objectives = [
        Objective(
            title="Budget optimization",
            description="Review all expenses and find at least $100k in savings for Q4",
            constraints=["Do not cut marketing below $300k", "Maintain vendor relationships"],
        ),
        Objective(
            title="Vendor risk assessment",
            description="Our Vietnam supply chain vendor is 2 weeks behind schedule. "
            "Find 3 alternative vendors and negotiate a 5% discount.",
        ),
        Objective(
            title="Contract compliance review",
            description="Scan all active contracts for auto-renewal clauses, "
            "non-compete restrictions, and liability exposure.",
        ),
        Objective(
            title="Marketing reallocation",
            description="Kill underperforming campaigns and reallocate budget "
            "to the highest-ROI channels.",
        ),
    ]

    for obj in objectives:
        console.print(Panel(
            f"[bold]{obj.title}[/bold]\n{obj.description}",
            title="Objective Dispatched",
            border_style="blue",
        ))

        results = cockpit.dispatch(obj)

        for role, actions in results.items():
            table = Table(title=f"Agent {role}")
            table.add_column("Action", max_width=60)
            table.add_column("Risk", justify="center")
            table.add_column("Status", justify="center")
            table.add_column("Citations")

            for a in actions:
                status = (
                    "[green]Auto-approved[/green]" if a.approved is True
                    else "[yellow]Awaiting approval[/yellow]" if a.approved is None
                    else "[red]Rejected[/red]"
                )
                risk_color = {
                    "low": "green", "medium": "yellow",
                    "high": "red", "critical": "bold red",
                }.get(a.risk.value, "white")
                table.add_row(
                    a.description[:60],
                    f"[{risk_color}]{a.risk.value}[/{risk_color}]",
                    status,
                    ", ".join(a.citations[:2]) or "—",
                )
            console.print(table)
        console.print()

    # ── 4. Show pending approvals ────────────────────────────────
    pending = cockpit.pending_approvals
    if pending:
        console.print(f"\n[yellow]⚠ {len(pending)} actions awaiting human approval:[/yellow]")
        for p in pending:
            console.print(f"  [{p.risk.value}] {p.agent_role}: {p.description}")

    # ── 5. System status ─────────────────────────────────────────
    status = cockpit.status()
    console.print(Panel(
        "\n".join(f"  {k}: {v}" for k, v in status.items()),
        title="System Status",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
