"""
Strategy Planner + PDF Report Generator.

Creates full campaign strategies with branded PDFs including:
- Executive summary
- Channel recommendations with budget allocation
- Target audience breakdown
- Timeline/milestones
- KPI targets with projected ROI
- Charts: budget split, projected performance, funnel
- All branded with company colors

The agent asks questions → gathers context → generates strategy → exports PDF.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data") / "reports"


class StrategyPlannerTool(BaseTool):
    """Creates ad/marketing strategies and exports branded PDF reports."""

    @property
    def name(self) -> str:
        return "strategy_planner"

    @property
    def description(self) -> str:
        return (
            "Create a full marketing or advertising campaign strategy. "
            "Ask about budget, goals, audience, timeline, then generate "
            "a branded PDF report with charts, budget allocation, "
            "channel recommendations, and projected ROI."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="type", description="campaign, seo, growth, brand (default: campaign)", required=False),
            ToolParam(name="budget", description="Total budget (e.g. $10000)", required=False),
            ToolParam(name="goal", description="Campaign goal", required=False),
            ToolParam(name="audience", description="Target audience", required=False),
            ToolParam(name="duration", description="Campaign duration (e.g. 3 months)", required=False),
            ToolParam(name="channels", description="Preferred channels", required=False),
            ToolParam(name="generate_pdf", description="true to generate PDF report", required=False),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "create strategy", "campaign strategy", "ad strategy",
            "marketing plan", "growth strategy", "create a plan",
            "marketing strategy", "advertising plan",
            "generate pdf", "create report", "strategy pdf",
            "campaign plan", "media plan",
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        strategy_type = kwargs.get("type", "campaign")
        budget = kwargs.get("budget", "")
        goal = kwargs.get("goal", "")
        audience = kwargs.get("audience", "")
        duration = kwargs.get("duration", "3 months")
        channels = kwargs.get("channels", "")
        gen_pdf = str(kwargs.get("generate_pdf", "false")).lower() == "true"

        strategy = self._build_strategy(strategy_type, budget, goal, audience, duration, channels)

        if gen_pdf:
            try:
                pdf_path = self._generate_pdf(strategy)
                strategy["pdf_path"] = str(pdf_path)
                strategy["pdf_url"] = f"/static/reports/{pdf_path.name}"
            except Exception as e:
                logger.error("PDF generation failed: %s", e)
                strategy["pdf_error"] = str(e)

        report = self._format_report(strategy)

        return ToolResult(
            self.name, True,
            data=strategy,
            summary=report,
        )

    def _build_strategy(self, stype: str, budget: str, goal: str, audience: str, duration: str, channels: str) -> dict[str, Any]:
        budget_num = self._parse_budget(budget)

        channel_split = self._recommend_channels(stype, budget_num, channels)
        kpis = self._project_kpis(stype, budget_num, channel_split)
        timeline = self._build_timeline(duration)

        return {
            "type": stype,
            "budget": budget,
            "budget_num": budget_num,
            "goal": goal or "Increase revenue and brand awareness",
            "audience": audience or "Target market (define in campaign brief)",
            "duration": duration,
            "channels": channel_split,
            "kpis": kpis,
            "timeline": timeline,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _recommend_channels(self, stype: str, budget: float, preferred: str) -> list[dict[str, Any]]:
        if stype == "seo":
            return [
                {"channel": "Content Marketing", "pct": 40, "amount": budget * 0.4, "rationale": "Blog posts, guides, pillar pages"},
                {"channel": "Technical SEO", "pct": 20, "amount": budget * 0.2, "rationale": "Site speed, schema, crawlability"},
                {"channel": "Link Building", "pct": 25, "amount": budget * 0.25, "rationale": "Guest posts, PR, partnerships"},
                {"channel": "Tools & Analytics", "pct": 15, "amount": budget * 0.15, "rationale": "Semrush, GA4, Ahrefs"},
            ]

        if budget < 5000:
            return [
                {"channel": "Meta Ads", "pct": 40, "amount": budget * 0.4, "rationale": "Best reach per dollar at low budgets"},
                {"channel": "Google Ads", "pct": 35, "amount": budget * 0.35, "rationale": "Intent-based, high conversion"},
                {"channel": "Content/SEO", "pct": 15, "amount": budget * 0.15, "rationale": "Long-term organic growth"},
                {"channel": "Email", "pct": 10, "amount": budget * 0.1, "rationale": "Highest ROI channel"},
            ]
        elif budget < 25000:
            return [
                {"channel": "Google Ads", "pct": 30, "amount": budget * 0.3, "rationale": "Search + Shopping campaigns"},
                {"channel": "Meta Ads", "pct": 25, "amount": budget * 0.25, "rationale": "Prospecting + retargeting"},
                {"channel": "LinkedIn Ads", "pct": 15, "amount": budget * 0.15, "rationale": "B2B lead gen if applicable"},
                {"channel": "Content/SEO", "pct": 15, "amount": budget * 0.15, "rationale": "Blog, video, thought leadership"},
                {"channel": "Email/CRM", "pct": 10, "amount": budget * 0.1, "rationale": "Nurture + retention campaigns"},
                {"channel": "TikTok/YouTube", "pct": 5, "amount": budget * 0.05, "rationale": "Brand awareness + testing"},
            ]
        else:
            return [
                {"channel": "Google Ads", "pct": 25, "amount": budget * 0.25, "rationale": "Full funnel: Search, PMax, Display, YouTube"},
                {"channel": "Meta Ads", "pct": 20, "amount": budget * 0.2, "rationale": "Advantage+ Shopping + prospecting"},
                {"channel": "LinkedIn Ads", "pct": 15, "amount": budget * 0.15, "rationale": "B2B thought leadership + lead gen"},
                {"channel": "TikTok Ads", "pct": 10, "amount": budget * 0.1, "rationale": "Creative-first brand awareness"},
                {"channel": "Content/SEO", "pct": 12, "amount": budget * 0.12, "rationale": "Pillar content strategy"},
                {"channel": "Email/CRM", "pct": 8, "amount": budget * 0.08, "rationale": "Lifecycle marketing automation"},
                {"channel": "PR/Influencer", "pct": 5, "amount": budget * 0.05, "rationale": "Brand credibility + reach"},
                {"channel": "Testing Reserve", "pct": 5, "amount": budget * 0.05, "rationale": "New channels, A/B tests"},
            ]

    def _project_kpis(self, stype: str, budget: float, channels: list) -> dict[str, Any]:
        if budget <= 0:
            return {"note": "Define budget to project KPIs"}

        cpl = 25 if stype in ("campaign", "growth") else 50
        cpa = 80
        roas = 3.5

        return {
            "projected_impressions": f"{int(budget / 0.005):,}",
            "projected_clicks": f"{int(budget / 1.5):,}",
            "projected_leads": f"{int(budget / cpl):,}",
            "projected_conversions": f"{int(budget / cpa):,}",
            "projected_revenue": f"${budget * roas:,.0f}",
            "target_roas": f"{roas}x",
            "target_cpl": f"${cpl}",
            "target_cpa": f"${cpa}",
        }

    def _build_timeline(self, duration: str) -> list[dict[str, str]]:
        return [
            {"phase": "Week 1-2", "focus": "Setup & Launch", "tasks": "Pixel setup, campaign creation, creative production, audience research"},
            {"phase": "Week 3-4", "focus": "Optimize", "tasks": "A/B test creatives, refine targeting, kill underperformers, scale winners"},
            {"phase": "Month 2", "focus": "Scale", "tasks": "Increase budget on winning channels, expand audiences, add new creatives"},
            {"phase": "Month 3", "focus": "Compound", "tasks": "Retargeting layers, lookalike audiences, content syndication, report results"},
        ]

    def _format_report(self, strategy: dict) -> str:
        report = f"## {strategy['type'].title()} Strategy\n\n"
        report += f"**Goal:** {strategy['goal']}\n"
        report += f"**Budget:** {strategy['budget'] or 'TBD'}\n"
        report += f"**Duration:** {strategy['duration']}\n"
        report += f"**Audience:** {strategy['audience']}\n\n"

        report += "### Channel Allocation\n\n"
        report += "| Channel | Budget | % | Rationale |\n"
        report += "|---------|--------|---|----------|\n"
        for ch in strategy["channels"]:
            report += f"| {ch['channel']} | ${ch['amount']:,.0f} | {ch['pct']}% | {ch['rationale']} |\n"

        if strategy["kpis"] and "note" not in strategy["kpis"]:
            report += "\n### Projected KPIs\n\n"
            for k, v in strategy["kpis"].items():
                label = k.replace("_", " ").replace("projected ", "").title()
                report += f"- **{label}:** {v}\n"

        report += "\n### Timeline\n\n"
        for phase in strategy["timeline"]:
            report += f"**{phase['phase']}** — {phase['focus']}\n"
            report += f"  {phase['tasks']}\n\n"

        if strategy.get("pdf_path"):
            report += f"\n📄 **[Download PDF Report]({strategy['pdf_url']})**\n"

        return report

    def _generate_pdf(self, strategy: dict) -> Path:
        """Generate a branded PDF with charts."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"strategy_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = DATA_DIR / filename

        # Copy to static for serving
        static_reports = Path("src/agentic_cxo/api/static/reports")
        static_reports.mkdir(parents=True, exist_ok=True)

        # Generate budget allocation pie chart
        chart_path = DATA_DIR / f"chart_{uuid.uuid4().hex[:6]}.png"
        channels = strategy.get("channels", [])
        if channels:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

            # Pie chart
            labels = [c["channel"] for c in channels]
            sizes = [c["pct"] for c in channels]
            brand_colors = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8", "#6d28d9", "#4f46e5", "#7c3aed"]
            ax1.pie(sizes, labels=labels, colors=brand_colors[:len(labels)], autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8})
            ax1.set_title("Budget Allocation", fontsize=11, fontweight="bold")

            # Bar chart
            amounts = [c["amount"] for c in channels]
            ax2.barh(labels, amounts, color=brand_colors[:len(labels)])
            ax2.set_xlabel("Budget ($)")
            ax2.set_title("Budget by Channel", fontsize=11, fontweight="bold")
            for i, v in enumerate(amounts):
                ax2.text(v + max(amounts) * 0.02, i, f"${v:,.0f}", va="center", fontsize=8)

            plt.tight_layout()
            plt.savefig(str(chart_path), dpi=150, bbox_inches="tight")
            plt.close()

        # Build PDF
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#6366f1"), spaceAfter=12)
        heading_style = ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#1e1b4b"), spaceAfter=8, spaceBefore=16)
        body_style = ParagraphStyle("CustomBody", parent=styles["Normal"], fontSize=10, spaceAfter=6, leading=14)

        story.append(Paragraph(f"{strategy['type'].title()} Strategy", title_style))
        story.append(Paragraph(f"Generated by Agentic CXO — {datetime.now().strftime('%B %d, %Y')}", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Executive Summary", heading_style))
        story.append(Paragraph(f"<b>Goal:</b> {strategy['goal']}", body_style))
        story.append(Paragraph(f"<b>Budget:</b> {strategy['budget'] or 'TBD'}", body_style))
        story.append(Paragraph(f"<b>Duration:</b> {strategy['duration']}", body_style))
        story.append(Paragraph(f"<b>Audience:</b> {strategy['audience']}", body_style))
        story.append(Spacer(1, 12))

        if chart_path.exists():
            story.append(Paragraph("Budget Allocation", heading_style))
            story.append(Image(str(chart_path), width=7 * inch, height=2.8 * inch))
            story.append(Spacer(1, 12))

        story.append(Paragraph("Channel Details", heading_style))
        table_data = [["Channel", "Budget", "%", "Rationale"]]
        for ch in channels:
            table_data.append([ch["channel"], f"${ch['amount']:,.0f}", f"{ch['pct']}%", ch["rationale"]])
        t = Table(table_data, colWidths=[1.5 * inch, 1 * inch, 0.5 * inch, 3.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        kpis = strategy.get("kpis", {})
        if kpis and "note" not in kpis:
            story.append(Paragraph("Projected KPIs", heading_style))
            for k, v in kpis.items():
                label = k.replace("_", " ").replace("projected ", "").title()
                story.append(Paragraph(f"<b>{label}:</b> {v}", body_style))
            story.append(Spacer(1, 12))

        story.append(Paragraph("Timeline", heading_style))
        for phase in strategy.get("timeline", []):
            story.append(Paragraph(f"<b>{phase['phase']}</b> — {phase['focus']}", body_style))
            story.append(Paragraph(f"<i>{phase['tasks']}</i>", body_style))

        doc.build(story)

        # Copy to static for web serving
        import shutil
        shutil.copy2(str(pdf_path), str(static_reports / filename))

        # Clean up chart
        if chart_path.exists():
            chart_path.unlink()

        logger.info("PDF generated: %s", pdf_path)
        return pdf_path

    @staticmethod
    def _parse_budget(budget: str) -> float:
        if not budget:
            return 10000
        import re
        m = re.search(r"[\d,]+(?:\.\d+)?", budget.replace(",", ""))
        if m:
            val = float(m.group())
            if "k" in budget.lower():
                val *= 1000
            if "m" in budget.lower():
                val *= 1_000_000
            return val
        return 10000
