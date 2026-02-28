"""
Scheduled Jobs — the agent works while you sleep.

Automated monitoring that runs on a schedule:
- Daily: check overdue invoices, contract expirations, stalled deals
- Weekly: generate executive report, culture pulse, pipeline review
- On-event: new document ingested → auto-scan for deadlines

The founder doesn't ask for these. The agent does them proactively.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A recurring job the agent runs automatically."""

    job_id: str
    name: str
    description: str
    frequency: str  # daily, weekly, monthly, on_event
    agent_role: str
    action_template: str
    last_run: datetime | None = None
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    def is_due(self) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        now = datetime.now(timezone.utc)
        intervals = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
            "hourly": timedelta(hours=1),
        }
        interval = intervals.get(self.frequency)
        if interval is None:
            return False
        return now - self.last_run >= interval


DEFAULT_JOBS = [
    ScheduledJob(
        job_id="daily-invoice-check",
        name="Invoice Overdue Check",
        description="Scan for invoices overdue > 15 days and draft reminders",
        frequency="daily",
        agent_role="CFO",
        action_template=(
            "Check all invoices in the vault. Flag any that are overdue "
            "by more than 15 days. For each, draft a collection email."
        ),
    ),
    ScheduledJob(
        job_id="daily-contract-expiry",
        name="Contract Expiration Monitor",
        description="Check for contracts expiring within 30 days",
        frequency="daily",
        agent_role="CLO",
        action_template=(
            "Scan all contracts in the vault. Flag any with expiration "
            "or renewal dates within the next 30 days. Alert the founder."
        ),
    ),
    ScheduledJob(
        job_id="daily-deal-stall",
        name="Stalled Deal Detector",
        description="Flag deals with no activity for 14+ days",
        frequency="daily",
        agent_role="CSO",
        action_template=(
            "Check the sales pipeline for deals in negotiation or proposal "
            "stage with no activity for 14+ days. Draft follow-up emails."
        ),
    ),
    ScheduledJob(
        job_id="weekly-exec-report",
        name="Weekly Executive Report",
        description="Auto-generate the weekly executive summary",
        frequency="weekly",
        agent_role="CFO",
        action_template=(
            "Generate a weekly executive summary covering: revenue/burn rate, "
            "pipeline health, marketing performance, key decisions made, "
            "and upcoming deadlines."
        ),
    ),
    ScheduledJob(
        job_id="weekly-culture-pulse",
        name="Weekly Culture Pulse",
        description="Analyze team sentiment from the past week",
        frequency="weekly",
        agent_role="CHRO",
        action_template=(
            "Analyze any available team communication data for sentiment "
            "trends. Flag emerging issues. Update the culture health score."
        ),
    ),
    ScheduledJob(
        job_id="daily-burn-monitor",
        name="Burn Rate Monitor",
        description="Track daily cash position and burn rate",
        frequency="daily",
        agent_role="CFO",
        action_template=(
            "Calculate current burn rate based on latest financial data. "
            "Update runway projection. Alert if runway drops below 6 months."
        ),
    ),
    ScheduledJob(
        job_id="weekly-campaign-review",
        name="Campaign Performance Review",
        description="Analyze all active campaigns and kill underperformers",
        frequency="weekly",
        agent_role="CMO",
        action_template=(
            "Review all active marketing campaigns. Flag any with ROI below "
            "1.0x for immediate pausing. Recommend budget reallocation."
        ),
    ),
    ScheduledJob(
        job_id="weekly-ads-audit",
        name="Ads Health Audit",
        description="Score all ad platforms against 190+ checks",
        frequency="weekly",
        agent_role="CMO",
        action_template=(
            "Run an ads audit across all connected ad platforms. "
            "Score each platform, flag critical issues, and identify "
            "quick wins. Report findings in the morning briefing."
        ),
    ),
    ScheduledJob(
        job_id="monthly-seo-audit",
        name="SEO Health Audit",
        description="Audit website SEO health and track improvements",
        frequency="monthly",
        agent_role="CMO",
        action_template=(
            "Run an SEO audit on the company's primary website. "
            "Check technical SEO, content quality, schema markup, "
            "and AI search readiness. Compare with last month's score."
        ),
    ),
]


class JobScheduler:
    """
    Manages and executes scheduled jobs.

    On every check, runs any job that is due.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {
            j.job_id: j for j in DEFAULT_JOBS
        }

    def add_job(self, job: ScheduledJob) -> None:
        self._jobs[job.job_id] = job

    def remove_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    @property
    def all_jobs(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    @property
    def due_jobs(self) -> list[ScheduledJob]:
        return [j for j in self._jobs.values() if j.is_due()]

    def mark_run(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.last_run = datetime.now(timezone.utc)

    def get_status(self) -> list[dict[str, Any]]:
        return [
            {
                "job_id": j.job_id,
                "name": j.name,
                "frequency": j.frequency,
                "agent": j.agent_role,
                "enabled": j.enabled,
                "is_due": j.is_due(),
                "last_run": j.last_run.isoformat() if j.last_run else None,
            }
            for j in self._jobs.values()
        ]
