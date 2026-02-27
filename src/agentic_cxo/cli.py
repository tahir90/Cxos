"""
CLI — command-line interface for the Agentic CXO system.

Usage:
  cxo ingest <file>              Ingest a document into the Context Vault
  cxo objective <title> <desc>   Dispatch an objective to CXO agents
  cxo query <text>               Query the Context Vault
  cxo status                     Show system status
  cxo serve                      Start the REST API server
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="cxo",
    help="Agentic CXO — AI-driven C-suite agents with modular context management",
)
console = Console()


def _cockpit():
    from agentic_cxo.orchestrator import Cockpit
    return Cockpit()


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to file or directory to ingest"),
    source: str = typer.Option("cli", help="Source label"),
):
    """Ingest a document into the Context Vault."""
    cockpit = _cockpit()
    p = Path(path)
    if p.is_dir():
        result = cockpit.refinery.refine_directory(p)
    else:
        result = cockpit.ingest_file(str(p))

    console.print(Panel(
        f"[bold green]Ingested[/bold green] {result.total_chunks} chunks "
        f"({result.total_tokens:,} tokens)\n\n"
        f"[bold]Executive Summary:[/bold]\n{result.executive_summary}",
        title=f"Context Vault — {p.name}",
    ))


@app.command()
def objective(
    title: str = typer.Argument(..., help="Objective title"),
    description: str = typer.Argument(..., help="Objective description"),
    assigned_to: Optional[str] = typer.Option(None, help="Assign to specific agent role"),
    constraint: Optional[list[str]] = typer.Option(None, help="Constraints"),
):
    """Dispatch a business objective to CXO agents."""
    from agentic_cxo.models import Objective

    cockpit = _cockpit()
    obj = Objective(
        title=title,
        description=description,
        constraints=constraint or [],
        assigned_to=assigned_to,
    )

    results = cockpit.dispatch(obj)

    for role, actions in results.items():
        table = Table(title=f"Agent {role} — Actions")
        table.add_column("ID", style="dim")
        table.add_column("Description")
        table.add_column("Risk", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Citations")

        for a in actions:
            status = (
                "[green]Approved[/green]" if a.approved
                else "[yellow]Pending[/yellow]" if a.approved is None
                else "[red]Rejected[/red]"
            )
            risk_colors = {
                "low": "green", "medium": "yellow",
                "high": "red", "critical": "bold red",
            }
            risk_style = risk_colors.get(a.risk.value, "white")
            table.add_row(
                a.action_id,
                a.description[:80],
                f"[{risk_style}]{a.risk.value}[/{risk_style}]",
                status,
                ", ".join(a.citations[:3]) or "—",
            )
        console.print(table)


@app.command()
def query(
    text: str = typer.Argument(..., help="Query text"),
    top_k: int = typer.Option(5, help="Number of results"),
):
    """Query the Context Vault."""
    cockpit = _cockpit()
    hits = cockpit.vault.query(text, top_k=top_k)

    if not hits:
        console.print("[yellow]No results found. Ingest some documents first.[/yellow]")
        return

    for i, hit in enumerate(hits, 1):
        meta = hit.get("metadata", {})
        console.print(Panel(
            f"{hit['content'][:300]}...\n\n"
            f"[dim]Source: {meta.get('source', '?')} | "
            f"Urgency: {meta.get('urgency', '?')} | "
            f"Distance: {hit.get('distance', '?'):.4f}[/dim]",
            title=f"Result {i}",
        ))


@app.command()
def status():
    """Show system status."""
    cockpit = _cockpit()
    info = cockpit.status()
    table = Table(title="Agentic CXO — System Status")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    for k, v in info.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host"),
    port: int = typer.Option(8000, help="Port"),
):
    """Start the REST API server."""
    import uvicorn
    console.print(f"[bold green]Starting Agentic CXO API on {host}:{port}[/bold green]")
    uvicorn.run("agentic_cxo.api.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
