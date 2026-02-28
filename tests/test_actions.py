"""Tests for the Action Execution layer, Decision Log, Goal Tracker, and Scheduler."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.actions.decision_log import Decision, DecisionLog, DecisionStatus
from agentic_cxo.actions.executor import ActionQueue, ActionStatus, ExecutableAction
from agentic_cxo.actions.goal_tracker import Goal, GoalStatus, GoalTracker
from agentic_cxo.actions.scheduler import JobScheduler, ScheduledJob


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestActionQueue:
    def test_submit_low_risk_auto_executes(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="create_task",
            description="Create a task",
            params={"title": "Test task", "assigned_to": "John"},
        )
        result = q.submit(action)
        assert result.status == ActionStatus.COMPLETED
        assert "Test task" in result.result

    def test_submit_high_risk_queues(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="send_email",
            description="Send collection email",
            params={"to": "client@example.com", "subject": "Overdue", "body": "Pay up"},
        )
        result = q.submit(action)
        assert result.status == ActionStatus.PENDING_APPROVAL
        assert len(q.pending) == 1

    def test_approve_and_execute(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="send_email",
            description="Send email",
            params={"to": "x@y.com", "subject": "Hi", "body": "Hello"},
        )
        q.submit(action)
        result = q.approve(action.action_id)
        assert result is not None
        assert result.status == ActionStatus.COMPLETED
        assert "QUEUED" in result.result  # SMTP not configured

    def test_reject(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="send_email",
            description="Risky email",
            params={"to": "x@y.com", "subject": "Hi", "body": "..."},
        )
        q.submit(action)
        result = q.reject(action.action_id, "Too risky")
        assert result is not None
        assert result.status == ActionStatus.REJECTED

    def test_webhook_execution(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="fire_webhook",
            description="Test webhook",
            params={"url": "https://httpbin.org/post", "payload": {"test": True}},
        )
        q.submit(action)
        assert len(q.pending) == 1

    def test_generate_report(self):
        q = ActionQueue()
        action = ExecutableAction(
            action_type="generate_report",
            description="Weekly report",
            params={"type": "weekly", "content": "# Week 1\nAll good."},
        )
        result = q.submit(action)
        assert result.status == ActionStatus.COMPLETED
        assert "report" in result.result.lower()

    def test_persistence(self):
        q1 = ActionQueue()
        q1.submit(ExecutableAction(
            action_type="create_task",
            params={"title": "Persist test"},
        ))
        q2 = ActionQueue()
        assert len(q2.all_actions) >= 1


class TestDecisionLog:
    def test_log_decision(self):
        log = DecisionLog()
        d = log.log(Decision(
            title="Cut marketing 15%",
            description="Reduce marketing spend to extend runway",
            recommended_by="CFO",
            expected_outcome="Extend runway by 4 months",
        ))
        assert log.count == 1
        assert d.decision_id

    def test_update_outcome(self):
        log = DecisionLog()
        d = log.log(Decision(title="Test decision"))
        log.update_outcome(
            d.decision_id,
            status=DecisionStatus.NEGATIVE,
            actual_outcome="Leads dropped 60%",
            impact="$200k revenue lost",
            lessons="Never cut more than 20%",
        )
        updated = log.all_decisions[0]
        assert updated.status == DecisionStatus.NEGATIVE
        assert "60%" in updated.actual_outcome

    def test_open_decisions(self):
        log = DecisionLog()
        log.log(Decision(title="Open", status=DecisionStatus.TRACKING))
        log.log(Decision(title="Closed", status=DecisionStatus.POSITIVE))
        assert len(log.open_decisions) == 1

    def test_persistence(self):
        l1 = DecisionLog()
        l1.log(Decision(title="Persisted"))
        l2 = DecisionLog()
        assert l2.count == 1


class TestGoalTracker:
    def test_add_goal(self):
        gt = GoalTracker()
        g = gt.add(Goal(
            title="Hit $20M ARR",
            metric="ARR",
            target_value="$20M",
            current_value="$12.5M",
            deadline="Q4 2026",
            owner="CFO",
        ))
        assert len(gt.active_goals) == 1
        assert g.goal_id

    def test_update_goal(self):
        gt = GoalTracker()
        g = gt.add(Goal(title="Test", metric="ARR", target_value="$20M"))
        gt.update(g.goal_id, current_value="$15M", note="Q2 update")
        updated = gt.active_goals[0]
        assert updated.current_value == "$15M"
        assert len(updated.updates) == 1

    def test_at_risk_goals(self):
        gt = GoalTracker()
        gt.add(Goal(title="Ok", status=GoalStatus.ON_TRACK))
        gt.add(Goal(title="Bad", status=GoalStatus.AT_RISK))
        assert len(gt.at_risk) == 1

    def test_format_status(self):
        gt = GoalTracker()
        gt.add(Goal(
            title="Hit $20M ARR",
            current_value="$12.5M",
            target_value="$20M",
            status=GoalStatus.ON_TRACK,
        ))
        text = gt.format_status()
        assert "$20M" in text
        assert "$12.5M" in text

    def test_persistence(self):
        g1 = GoalTracker()
        g1.add(Goal(title="Persisted goal"))
        g2 = GoalTracker()
        assert len(g2.all_goals) == 1


class TestJobScheduler:
    def test_default_jobs_loaded(self):
        scheduler = JobScheduler()
        assert len(scheduler.all_jobs) >= 7

    def test_all_default_jobs_are_due(self):
        scheduler = JobScheduler()
        due = scheduler.due_jobs
        assert len(due) >= 7

    def test_mark_run(self):
        scheduler = JobScheduler()
        job = scheduler.all_jobs[0]
        scheduler.mark_run(job.job_id)
        assert not job.is_due()

    def test_custom_job(self):
        scheduler = JobScheduler()
        scheduler.add_job(ScheduledJob(
            job_id="custom",
            name="Custom Job",
            description="Test",
            frequency="daily",
            agent_role="CFO",
            action_template="Do something",
        ))
        assert any(j.job_id == "custom" for j in scheduler.all_jobs)

    def test_status_output(self):
        scheduler = JobScheduler()
        status = scheduler.get_status()
        assert len(status) >= 7
        assert all("job_id" in s for s in status)
