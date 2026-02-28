"""
Travel Analyzer Tool — catches overpriced business travel.

When a travel request comes in, this tool:
1. Compares the claimed cost against historical travel data
2. Checks if flexible dates could save money
3. Evaluates if the trip is necessary (vs. video call)
4. Generates a recommendation with savings estimate
"""

from __future__ import annotations

import re
from typing import Any

from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult


class TravelAnalyzerTool(BaseTool):
    def __init__(self, vault: ContextVault | None = None) -> None:
        self._vault = vault or ContextVault()

    @property
    def name(self) -> str:
        return "travel_analyzer"

    @property
    def description(self) -> str:
        return (
            "Analyze a business travel request for cost reasonableness. "
            "Compares against historical travel costs, checks if dates "
            "are flexible for cheaper options, and evaluates if the trip "
            "is necessary or could be replaced with a video call."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(
                name="description",
                description="Travel request details (destination, dates, purpose)",
            ),
            ToolParam(
                name="amount",
                description="Claimed cost / flight price",
                required=False,
            ),
            ToolParam(
                name="employee",
                description="Who is requesting",
                required=False,
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "travel", "flight", "trip", "business travel",
            "book a flight", "travel request", "hotel",
            "airline", "fly to", "travel to", "conference",
        ]

    def execute(
        self,
        description: str = "",
        amount: str = "",
        employee: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        analysis: dict[str, Any] = {
            "description": description,
            "employee": employee,
        }

        claimed = self._parse_amount(amount or description)
        analysis["claimed_amount"] = claimed

        historical = self._check_historical_travel(description)
        analysis["historical"] = historical

        flag = None
        if claimed and historical.get("avg_cost"):
            avg = historical["avg_cost"]
            if claimed > avg * 1.3:
                pct = int(((claimed - avg) / avg) * 100)
                flag = (
                    f"ALERT: Claimed amount ${claimed:,.0f} is "
                    f"{pct}% above historical average ${avg:,.0f}"
                )
            analysis["vs_historical"] = {
                "claimed": claimed,
                "average": avg,
                "difference_pct": (
                    int(((claimed - avg) / avg) * 100) if avg else 0
                ),
            }
        analysis["cost_flag"] = flag

        date_analysis = self._analyze_dates(description)
        analysis["date_analysis"] = date_analysis

        necessity = self._check_necessity(description)
        analysis["necessity_check"] = necessity

        recommendations = self._generate_recommendations(
            claimed, historical, date_analysis, necessity
        )
        analysis["recommendations"] = recommendations

        savings = self._estimate_savings(claimed, historical, date_analysis)
        analysis["potential_savings"] = savings

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=analysis,
            summary=self._build_summary(analysis),
        )

    def _check_historical_travel(
        self, description: str
    ) -> dict[str, Any]:
        """Search vault for past travel costs to the same destination."""
        result: dict[str, Any] = {"past_trips": []}

        destination = self._extract_destination(description)
        if not destination:
            return result

        try:
            query = f"travel flight {destination}"
            hits = self._vault.query(query, top_k=5)

            amounts: list[float] = []
            for hit in hits:
                content = hit.get("content", "")
                dollar_matches = re.findall(
                    r"\$([\d,]+(?:\.\d+)?)", content
                )
                for d in dollar_matches:
                    val = float(d.replace(",", ""))
                    if 100 < val < 10000:
                        amounts.append(val)
                        result["past_trips"].append({
                            "content": content[:150],
                            "amount": val,
                            "source": hit.get("metadata", {}).get(
                                "source", "?"
                            ),
                        })

            if amounts:
                result["avg_cost"] = sum(amounts) / len(amounts)
                result["min_cost"] = min(amounts)
                result["max_cost"] = max(amounts)

        except Exception:
            pass

        return result

    @staticmethod
    def _analyze_dates(description: str) -> dict[str, Any]:
        """Check if travel dates are flexible for cheaper options."""
        analysis: dict[str, Any] = {"flexible": True}

        urgent_kw = [
            "urgent", "emergency", "tomorrow", "asap",
            "must be", "required", "mandatory",
        ]
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in urgent_kw):
            analysis["flexible"] = False
            analysis["note"] = "Marked as urgent — limited flexibility"
            return analysis

        day_match = re.search(
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            desc_lower,
        )
        if day_match:
            day = day_match.group(1)
            if day in ("tuesday", "wednesday", "thursday"):
                analysis["note"] = (
                    "Midweek travel — good. These are typically cheapest."
                )
            else:
                analysis["note"] = (
                    f"{day.title()} travel is more expensive. "
                    "Shifting to Tue-Thu could save 20-40%."
                )
                analysis["savings_tip"] = "Shift to midweek"

        analysis["general_tip"] = (
            "Book 14+ days in advance. "
            "Flexible dates can save 20-40% on flights."
        )
        return analysis

    @staticmethod
    def _check_necessity(description: str) -> dict[str, Any]:
        """Evaluate if in-person travel is truly necessary."""
        desc_lower = description.lower()

        high_necessity = [
            "signing", "close deal", "client dinner", "board meeting",
            "conference", "trade show", "on-site", "inspection",
            "audit", "final presentation",
        ]
        low_necessity = [
            "meeting", "catch up", "check in", "discuss",
            "review", "update", "sync", "kickoff",
        ]

        if any(kw in desc_lower for kw in high_necessity):
            return {
                "necessary": True,
                "note": "This appears to require in-person presence.",
            }

        if any(kw in desc_lower for kw in low_necessity):
            return {
                "necessary": False,
                "note": (
                    "This meeting could potentially be done via video call. "
                    "Consider if in-person is truly required."
                ),
                "alternative": "Video call (Zoom/Google Meet)",
            }

        return {"necessary": True, "note": "Unable to assess — assume needed."}

    @staticmethod
    def _generate_recommendations(
        claimed: float | None,
        historical: dict[str, Any],
        dates: dict[str, Any],
        necessity: dict[str, Any],
    ) -> list[str]:
        recs: list[str] = []

        if not necessity.get("necessary"):
            recs.append(
                "Consider video call instead — "
                "saves the full travel cost"
            )

        if dates.get("savings_tip"):
            recs.append(dates["savings_tip"])

        avg = historical.get("avg_cost")
        if claimed and avg and claimed > avg * 1.3:
            recs.append(
                f"Request a lower fare — historical average "
                f"is ${avg:,.0f}, current claim is ${claimed:,.0f}"
            )
            recs.append("Get 2 alternative flight quotes")

        recs.append("Book 14+ days ahead for best rates")
        return recs

    @staticmethod
    def _estimate_savings(
        claimed: float | None,
        historical: dict[str, Any],
        dates: dict[str, Any],
    ) -> dict[str, Any]:
        savings: dict[str, Any] = {"total_potential": 0}

        avg = historical.get("avg_cost")
        if claimed and avg and claimed > avg:
            savings["vs_historical"] = claimed - avg
            savings["total_potential"] += claimed - avg

        if dates.get("savings_tip") and claimed:
            mid_savings = claimed * 0.25
            savings["date_flexibility"] = mid_savings
            savings["total_potential"] += mid_savings

        return savings

    @staticmethod
    def _extract_destination(text: str) -> str | None:
        patterns = [
            r"(?:to|from|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(NYC|LAX|SFO|ORD|DFW|JFK|ATL|BOS|SEA|DEN|MIA)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        if not text:
            return None
        m = re.search(r"\$?([\d,]+(?:\.\d+)?)", str(text))
        if m:
            val = float(m.group(1).replace(",", ""))
            if val > 50:
                return val
        return None

    @staticmethod
    def _build_summary(analysis: dict[str, Any]) -> str:
        parts = ["Travel analysis"]
        if analysis.get("claimed_amount"):
            parts.append(f"${analysis['claimed_amount']:,.0f}")
        if analysis.get("cost_flag"):
            parts.append("COST FLAG")
        savings = analysis.get("potential_savings", {})
        if savings.get("total_potential"):
            parts.append(
                f"Potential savings: ${savings['total_potential']:,.0f}"
            )
        return " | ".join(parts)
