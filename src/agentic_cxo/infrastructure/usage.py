"""
Usage Tracking — monitors consumption and costs.

Tracks:
  - Chat messages sent/received
  - LLM tokens consumed (input + output)
  - Actions executed
  - Connector API calls
  - Documents ingested
  - Scenarios run
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class UsageTracker:
    """Tracks system usage for billing and monitoring."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {
            "messages_sent": 0,
            "messages_received": 0,
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "llm_calls": 0,
            "actions_executed": 0,
            "actions_approved": 0,
            "actions_rejected": 0,
            "documents_ingested": 0,
            "chunks_created": 0,
            "vault_queries": 0,
            "scenarios_run": 0,
            "connector_calls": 0,
            "tools_invoked": 0,
            "reminders_created": 0,
            "decisions_logged": 0,
        }
        self._daily: dict[str, dict[str, int]] = {}
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "usage.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._counters.update(data.get("totals", {}))
                self._daily = data.get("daily", {})
            except Exception:
                pass

    def save(self) -> None:
        self._path().write_text(json.dumps({
            "totals": self._counters,
            "daily": self._daily,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }, indent=2))

    def track(self, metric: str, count: int = 1) -> None:
        if metric in self._counters:
            self._counters[metric] += count
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today not in self._daily:
            self._daily[today] = {}
        self._daily[today][metric] = (
            self._daily[today].get(metric, 0) + count
        )
        self.save()

    def track_llm(self, input_tokens: int, output_tokens: int) -> None:
        self.track("llm_calls")
        self.track("llm_input_tokens", input_tokens)
        self.track("llm_output_tokens", output_tokens)

    @property
    def totals(self) -> dict[str, int]:
        return dict(self._counters)

    def today(self) -> dict[str, int]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._daily.get(today, {})

    @property
    def estimated_cost(self) -> float:
        """Rough cost estimate based on GPT-4o pricing."""
        input_cost = self._counters["llm_input_tokens"] * 2.50 / 1_000_000
        output_cost = self._counters["llm_output_tokens"] * 10.00 / 1_000_000
        return round(input_cost + output_cost, 4)

    def summary(self) -> dict[str, Any]:
        return {
            "totals": self.totals,
            "today": self.today(),
            "estimated_llm_cost_usd": self.estimated_cost,
        }

    def clear(self) -> None:
        for k in self._counters:
            self._counters[k] = 0
        self._daily = {}
        self.save()
