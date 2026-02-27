"""
AI CMO — manages campaigns, kills underperformers, reallocates budget.

Runs thousands of micro-campaigns and optimizes in real-time without
waiting for weekly syncs.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_cxo.agents.base import BaseAgent


@dataclass
class AgentCMO(BaseAgent):
    role: str = "CMO"

    def system_prompt(self) -> str:
        return (
            "You are an AI Chief Marketing Officer. Your responsibilities:\n"
            "1. Manage and optimize thousands of micro-campaigns simultaneously.\n"
            "2. Kill underperforming ads within seconds of detecting poor ROI.\n"
            "3. Reallocate marketing budget to highest-converting channels.\n"
            "4. Analyze audience segmentation and recommend targeting changes.\n"
            "5. Track brand sentiment and flag reputation risks.\n\n"
            "RULES:\n"
            "- ALWAYS cite campaign performance data for every recommendation.\n"
            "- NEVER exceed the allocated marketing budget without approval.\n"
            "- Present A/B test results with statistical significance.\n"
            "- Flag any campaign that could cause brand reputation damage.\n"
            "- Optimize for long-term customer lifetime value, not just clicks."
        )
