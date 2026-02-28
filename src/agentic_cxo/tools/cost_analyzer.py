"""
Cost Analyzer Tool — catches inflated costs by comparing against
historical data and market benchmarks.

When an expense claim, vendor quote, or budget request comes in,
this tool:
1. Checks internal history for similar past expenses
2. Flags if the current cost is significantly higher
3. Suggests alternatives or timing adjustments
"""

from __future__ import annotations

import re
from typing import Any

from agentic_cxo.conversation.pattern_engine import EventStore
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult


class CostAnalyzerTool(BaseTool):
    def __init__(
        self,
        vault: ContextVault | None = None,
        event_store: EventStore | None = None,
    ) -> None:
        self._vault = vault or ContextVault()
        self._events = event_store or EventStore()

    @property
    def name(self) -> str:
        return "cost_analyzer"

    @property
    def description(self) -> str:
        return (
            "Analyze a cost, expense, or price for reasonableness. "
            "Compares against historical spending, past vendor rates, "
            "and internal benchmarks. Flags overcharges and suggests "
            "cheaper alternatives or timing."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="description", description="What the expense is for"),
            ToolParam(
                name="amount", description="Dollar amount", required=False
            ),
            ToolParam(
                name="vendor", description="Vendor name if applicable",
                required=False,
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "expense", "cost", "price", "quote", "invoice",
            "travel request", "flight", "hotel", "subscription",
            "is this too much", "too expensive", "compare price",
            "cheaper", "budget", "claim", "reimbursement",
        ]

    def execute(
        self,
        description: str = "",
        amount: str = "",
        vendor: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        findings: list[str] = []
        risk_level = "low"

        parsed_amount = self._parse_amount(amount or description)

        historical = self._check_historical(description, parsed_amount)
        if historical:
            findings.extend(historical["findings"])
            if historical.get("is_inflated"):
                risk_level = "high"

        vault_data = self._check_vault(description)
        if vault_data:
            findings.extend(vault_data)

        if not findings:
            findings.append(
                "No historical comparison data found. "
                "This appears to be a new type of expense."
            )

        recommendations = self._generate_recommendations(
            description, parsed_amount, risk_level
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "amount_parsed": parsed_amount,
                "risk_level": risk_level,
                "findings": findings,
                "recommendations": recommendations,
                "vendor": vendor,
            },
            summary=self._build_summary(
                description, parsed_amount, risk_level, findings
            ),
        )

    def _check_historical(
        self, description: str, amount: float | None
    ) -> dict[str, Any] | None:
        """Compare against past events for similar expenses."""
        events = self._events.all_events
        if not events:
            return None

        desc_lower = description.lower()
        similar: list[dict[str, Any]] = []

        for ev in events:
            text = ev.searchable_text
            words_desc = set(desc_lower.split())
            words_ev = set(text.split())
            overlap = len(words_desc & words_ev)
            if overlap >= 2:
                ev_amount = self._parse_amount(ev.amount or ev.impact)
                similar.append({
                    "action": ev.action,
                    "amount": ev_amount,
                    "date": ev.date,
                    "outcome": ev.outcome.value,
                })

        if not similar:
            return None

        findings: list[str] = []
        is_inflated = False

        for past in similar[:3]:
            findings.append(
                f"Similar past expense: '{past['action']}' "
                f"{'at $' + str(int(past['amount'])) if past['amount'] else ''} "
                f"({past['outcome']})"
            )
            if amount and past["amount"] and amount > past["amount"] * 1.3:
                pct = int(((amount - past["amount"]) / past["amount"]) * 100)
                findings.append(
                    f"ALERT: Current amount is {pct}% higher than "
                    f"the historical rate"
                )
                is_inflated = True

        return {"findings": findings, "is_inflated": is_inflated}

    def _check_vault(self, description: str) -> list[str]:
        """Search the vault for related cost data."""
        findings: list[str] = []
        try:
            hits = self._vault.query(description, top_k=3)
            for hit in hits:
                content = hit.get("content", "")
                amounts = re.findall(r"\$[\d,]+(?:\.\d+)?[MmKk]?", content)
                if amounts:
                    source = hit.get("metadata", {}).get("source", "?")
                    findings.append(
                        f"Related data [{source}]: {content[:150]}"
                    )
        except Exception:
            pass
        return findings

    @staticmethod
    def _generate_recommendations(
        description: str, amount: float | None, risk_level: str
    ) -> list[str]:
        recs: list[str] = []
        desc_lower = description.lower()

        if risk_level == "high":
            recs.append(
                "Request itemized breakdown from vendor before approval"
            )
            recs.append("Get 2-3 competitive quotes for comparison")

        if any(kw in desc_lower for kw in ["flight", "travel", "trip"]):
            recs.append("Check flexible dates — midweek flights are 20-40% cheaper")
            recs.append("Book 14+ days in advance for best rates")
            recs.append("Consider if this meeting can be done via video call")

        if any(kw in desc_lower for kw in ["subscription", "saas", "tool"]):
            recs.append("Check if annual billing offers a discount (typically 15-20%)")
            recs.append("Verify no overlap with existing tools")

        if amount and amount > 10000:
            recs.append("Expenses above $10k should require dual approval")

        return recs

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        if not text:
            return None
        m = re.search(r"\$?([\d,]+(?:\.\d+)?)\s*([MmKkBb])?", str(text))
        if not m:
            return None
        num = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").upper()
        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        return num * multipliers.get(suffix, 1)

    @staticmethod
    def _build_summary(
        desc: str, amount: float | None, risk: str, findings: list[str]
    ) -> str:
        parts = [f"Cost analysis for: {desc[:80]}"]
        if amount:
            parts.append(f"Amount: ${amount:,.0f}")
        parts.append(f"Risk: {risk.upper()}")
        parts.append(f"Findings: {len(findings)}")
        return " | ".join(parts)
