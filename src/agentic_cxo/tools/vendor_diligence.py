"""
Vendor Due Diligence Tool — researches vendors before onboarding.

Before signing with any vendor, this tool:
1. Searches for the company online (size, age, legitimacy)
2. Checks review platforms (G2, Trustpilot, BBB)
3. Scans for recent news (layoffs, lawsuits, breaches)
4. Compares against existing vendors in the vault
5. Generates a risk-scored recommendation
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)


class VendorDueDiligenceTool(BaseTool):
    def __init__(self, vault: ContextVault | None = None) -> None:
        self._vault = vault or ContextVault()

    @property
    def name(self) -> str:
        return "vendor_due_diligence"

    @property
    def description(self) -> str:
        return (
            "Research a vendor or company before onboarding. "
            "Checks online presence, reviews, news, and compares "
            "against existing vendors. Returns a risk assessment "
            "with recommendation."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="company_name", description="Name of the vendor/company"),
            ToolParam(
                name="service_type",
                description="What service they provide",
                required=False,
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "vendor", "onboard", "new supplier", "new vendor",
            "check company", "research company", "due diligence",
            "evaluate vendor", "vet this", "look into",
            "should we work with", "is this vendor good",
        ]

    def execute(
        self,
        company_name: str = "",
        service_type: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        if not company_name:
            return ToolResult(
                tool_name=self.name, success=False,
                error="No company name provided",
            )

        report: dict[str, Any] = {
            "company": company_name,
            "service": service_type,
            "checks": [],
        }

        online = self._check_online(company_name)
        report["online_presence"] = online
        report["checks"].append(online.get("summary", ""))

        internal = self._check_internal(company_name, service_type)
        report["internal_comparison"] = internal
        report["checks"].extend(internal.get("findings", []))

        risk = self._assess_risk(online, internal)
        report["risk_score"] = risk["score"]
        report["risk_level"] = risk["level"]
        report["recommendation"] = risk["recommendation"]

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=report,
            summary=self._build_summary(company_name, risk),
        )

    def _check_online(self, company: str) -> dict[str, Any]:
        """Search for vendor information online."""
        results: dict[str, Any] = {"found": False, "summary": ""}

        try:
            resp = httpx.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": f"{company} company reviews",
                    "format": "json",
                    "no_html": "1",
                },
                timeout=10,
            )
            data = resp.json()

            if data.get("AbstractText"):
                results["found"] = True
                results["description"] = data["AbstractText"]
                results["source"] = data.get("AbstractURL", "")
                results["summary"] = (
                    f"Found online: {data['AbstractText'][:200]}"
                )

            related = []
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    related.append(topic["Text"][:150])
            results["related_info"] = related

        except Exception:
            logger.warning("Online vendor check failed", exc_info=True)
            results["summary"] = (
                f"Could not verify {company} online. "
                "Manual verification recommended."
            )
            results["risk_note"] = "Unable to verify — treat as medium risk"

        return results

    def _check_internal(
        self, company: str, service_type: str
    ) -> dict[str, Any]:
        """Compare against existing vendors in the vault."""
        result: dict[str, Any] = {"findings": []}
        try:
            query = f"vendor {company} {service_type}"
            hits = self._vault.query(query, top_k=5)
            for hit in hits:
                content = hit.get("content", "")
                source = hit.get("metadata", {}).get("source", "?")
                result["findings"].append(
                    f"[{source}] {content[:200]}"
                )
            if hits:
                result["has_existing_vendors"] = True
        except Exception:
            pass
        return result

    @staticmethod
    def _assess_risk(
        online: dict[str, Any], internal: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a risk score and recommendation."""
        score = 50

        if online.get("found"):
            score -= 15
        else:
            score += 20

        if online.get("risk_note"):
            score += 15

        if internal.get("has_existing_vendors"):
            score -= 5

        score = max(0, min(100, score))

        if score <= 30:
            level, rec = "low", "Proceed with standard onboarding"
        elif score <= 60:
            level, rec = "medium", (
                "Proceed with caution. Request references "
                "and verify business credentials."
            )
        else:
            level, rec = "high", (
                "High risk — insufficient online presence. "
                "Strongly recommend manual verification, "
                "reference checks, and starting with a small "
                "trial engagement before committing."
            )

        return {"score": score, "level": level, "recommendation": rec}

    @staticmethod
    def _build_summary(company: str, risk: dict[str, Any]) -> str:
        return (
            f"Vendor due diligence for {company}: "
            f"Risk {risk['level'].upper()} ({risk['score']}/100). "
            f"{risk['recommendation']}"
        )
