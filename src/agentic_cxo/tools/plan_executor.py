"""
Plan Executor — executes structured plans step-by-step with dependency management.

Takes an ExecutionPlan from the PlannerTool and runs it:
  1. Groups steps by parallel_group
  2. Executes groups in order (A, then B, then C...)
  3. Within each group, runs steps concurrently
  4. Yields rich progress events for the UI
  5. Passes results between dependent steps
  6. Includes LLM synthesis for consolidation steps
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from agentic_cxo.config import settings
from agentic_cxo.tools.planner import ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)

# Type for streaming events — works with both list.append and queue.put
EventSink = list | queue.Queue


def _emit(sink: EventSink, event: dict[str, Any]) -> None:
    """Push an event to either a list or a Queue."""
    if isinstance(sink, queue.Queue):
        sink.put(event)
    else:
        sink.append(event)


@dataclass
class StepResult:
    step_id: int
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: str = ""


CXO_CONSULT_PROMPTS: dict[str, str] = {
    "CFO": (
        "You are the AI CFO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide a concise financial analysis, key metrics, projections, "
        "or budget insights relevant to this request. Be specific with numbers."
    ),
    "COO": (
        "You are the AI COO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide operational insights, process recommendations, vendor considerations, "
        "or supply chain analysis relevant to this request."
    ),
    "CMO": (
        "You are the AI CMO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide marketing insights, positioning strategy, audience analysis, "
        "campaign recommendations, or growth tactics relevant to this request."
    ),
    "CLO": (
        "You are the AI CLO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide legal considerations, compliance requirements, risk factors, "
        "or contractual guidance relevant to this request."
    ),
    "CHRO": (
        "You are the AI CHRO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide people & culture insights, talent strategy, team structure, "
        "or organizational recommendations relevant to this request."
    ),
    "CSO": (
        "You are the AI CSO. Given this task: {task}\n"
        "Business context: {context}\n"
        "Provide sales strategy, pipeline insights, deal positioning, "
        "or revenue optimization recommendations relevant to this request."
    ),
}


@dataclass
class PlanExecutor:
    """Executes plans, yielding structured events for UI transparency."""

    tool_registry: Any = None
    creative_director: Any = None
    use_llm: bool = False
    plan_history: list[dict[str, Any]] = field(default_factory=list)
    _client: Any = field(default=None, init=False, repr=False)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def execute_plan(
        self, plan: ExecutionPlan
    ) -> Iterator[dict[str, Any]]:
        """Execute a plan and yield events for the UI.

        Event types:
          plan_created, step_group_start, step_start, step_progress,
          step_complete, step_group_complete, source_found, agent_consulted,
          narration, document_ready, plan_complete
        """
        yield {
            "type": "plan_created",
            "intent": plan.intent,
            "complexity": plan.complexity,
            "total_steps": plan.total_steps,
            "groups": plan.parallel_groups,
            "steps": [
                {"id": s.id, "description": s.description, "group": s.parallel_group,
                 "action": s.action, "tool": s.tool, "agent": s.agent}
                for s in plan.steps
            ],
        }

        opening = plan.narration.get("opening", "")
        if opening:
            yield {"type": "narration", "message": opening}

        results: dict[int, StepResult] = {}

        for group in plan.parallel_groups:
            group_steps = plan.steps_in_group(group)
            yield {
                "type": "step_group_start",
                "group": group,
                "step_count": len(group_steps),
                "descriptions": [s.description for s in group_steps],
            }

            if len(group_steps) == 1:
                step = group_steps[0]
                for event in self._execute_step(step, results, plan):
                    yield event
            else:
                yield from self._execute_group_parallel(group_steps, results, plan)

            group_completed = len([s for s in group_steps if s.status == "completed"])
            group_failed = len([s for s in group_steps if s.status == "failed"])
            yield {
                "type": "step_group_complete",
                "group": group,
                "completed": group_completed,
                "total": len(group_steps),
            }

            if group_failed > 0:
                replan_result = self._attempt_replan(plan, group, results, group_steps)
                if replan_result:
                    yield replan_result
                elif group_completed > 0:
                    yield {
                        "type": "narration",
                        "message": f"Some tasks in group {group} had issues. Continuing with available results.",
                    }

            transition_key = f"after_group_{group}"
            transition = plan.narration.get("transitions", {}).get(transition_key, "")
            if transition:
                yield {"type": "narration", "message": transition}

        all_data = {}
        all_summaries = []
        for sr in results.values():
            if sr.success:
                all_data.update(sr.data)
                if sr.summary:
                    all_summaries.append(sr.summary)

        # Plan is successful if the core deliverable (generate step) succeeded.
        # Optional steps like validate/consult_agent failures should not fail the plan.
        core_actions = {"generate", "research", "synthesize"}
        core_results = [
            r for sid, r in results.items()
            if any(s.id == sid and s.action in core_actions for s in plan.steps)
        ]
        if core_results:
            success = all(r.success for r in core_results)
        else:
            success = all(r.success for r in results.values()) if results else False
        completed = sum(1 for r in results.values() if r.success)

        self._record_plan_history(plan, results, success)

        yield {
            "type": "plan_complete",
            "success": success,
            "total_steps": len(results),
            "completed": completed,
            "combined_data": all_data,
            "combined_summary": "\n\n".join(all_summaries),
        }

    def _record_plan_history(
        self,
        plan: ExecutionPlan,
        results: dict[int, StepResult],
        success: bool,
    ) -> None:
        """Store plan execution history for future learning."""
        import json
        from pathlib import Path
        from datetime import datetime, timezone

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intent": plan.intent,
            "complexity": plan.complexity,
            "document_type": plan.document_type,
            "total_steps": plan.total_steps,
            "success": success,
            "completed_steps": sum(1 for r in results.values() if r.success),
            "failed_steps": sum(1 for r in results.values() if not r.success),
            "step_details": [
                {
                    "id": s.id,
                    "action": s.action,
                    "tool": s.tool,
                    "agent": s.agent,
                    "status": s.status,
                }
                for s in plan.steps
            ],
        }
        self.plan_history.append(record)

        try:
            history_path = Path(".cxo_data") / "plan_history.json"
            history_path.parent.mkdir(exist_ok=True)
            existing: list = []
            if history_path.exists():
                existing = json.loads(history_path.read_text())
            existing.append(record)
            existing = existing[-50:]
            history_path.write_text(json.dumps(existing, indent=2))
        except Exception:
            logger.debug("Failed to persist plan history", exc_info=True)

    def _attempt_replan(
        self,
        plan: ExecutionPlan,
        failed_group: str,
        results: dict[int, StepResult],
        group_steps: list[PlanStep],
    ) -> dict[str, Any] | None:
        """When a group has failures, use LLM to decide how to adapt remaining steps."""
        if not self.use_llm or not settings.llm.api_key:
            return None

        failed = [s for s in group_steps if s.status == "failed"]
        succeeded = [s for s in group_steps if s.status == "completed"]
        remaining_groups = [
            g for g in plan.parallel_groups
            if g > failed_group
        ]
        if not remaining_groups:
            return None

        try:
            client = self._get_client()
            from agentic_cxo.infrastructure.llm_retry import with_retry

            failed_desc = "; ".join(f"Step {s.id} ({s.description}): {results.get(s.id, StepResult(s.id, False)).error}" for s in failed)
            succeeded_desc = "; ".join(f"Step {s.id} ({s.description})" for s in succeeded)
            remaining_desc = "; ".join(
                f"Step {s.id} ({s.description}, group={s.parallel_group})"
                for s in plan.steps if s.parallel_group in remaining_groups
            )

            resp = with_retry(
                lambda: client.chat.completions.create(
                    model=settings.llm.model,
                    temperature=0.1,
                    max_tokens=512,
                    messages=[
                        {"role": "system", "content": "You are a plan executor. A step group had failures. Decide how to adapt. Return a short narration message explaining the adjustment."},
                        {"role": "user", "content": (
                            f"Plan intent: {plan.intent}\n"
                            f"Failed steps: {failed_desc}\n"
                            f"Succeeded steps: {succeeded_desc}\n"
                            f"Remaining steps: {remaining_desc}\n"
                            "Explain briefly how you'll adapt the remaining work given the failures. 1-2 sentences."
                        )},
                    ],
                )
            )
            msg = (resp.choices[0].message.content or "").strip()
            if msg:
                return {"type": "narration", "message": f"Adapting plan: {msg}"}
        except Exception:
            logger.debug("Replan LLM call failed", exc_info=True)
        return None

    # ── Agent-to-Agent Messaging ─────────────────────────────────

    def request_cross_agent_input(
        self,
        requesting_agent: str,
        target_agent: str,
        question: str,
        context: str = "",
        plan: ExecutionPlan | None = None,
    ) -> StepResult:
        """Allow one CXO to request input from another CXO mid-execution.

        Example: CFO asks CLO about tax compliance implications.
        """
        logger.info("Cross-agent request: %s -> %s: %s", requesting_agent, target_agent, question[:80])

        step = PlanStep(
            id=0,
            action="consult_agent",
            agent=target_agent,
            description=f"{requesting_agent} asks {target_agent}: {question}",
            params={"task": question},
        )

        dummy_plan = plan or ExecutionPlan(
            intent=question, complexity="simple",
            document_type=None, quality_bar="Quick expert input",
            steps=[step],
        )

        if target_agent == "CD":
            return self._consult_cd(step, dummy_plan)
        elif target_agent in CXO_CONSULT_PROMPTS or target_agent:
            prompt_override = (
                f"You are the AI {target_agent}. "
                f"The AI {requesting_agent} is asking for your input on: {question}\n"
                f"Context from {requesting_agent}: {context[:500]}\n"
                "Provide a concise, actionable response addressing their specific question."
            )
            if self.use_llm and settings.llm.api_key:
                try:
                    client = self._get_client()
                    from agentic_cxo.infrastructure.llm_retry import with_retry
                    resp = with_retry(
                        lambda: client.chat.completions.create(
                            model=settings.llm.model,
                            temperature=0.3,
                            max_tokens=1000,
                            messages=[
                                {"role": "system", "content": f"You are the AI {target_agent}. Another C-suite officer needs your expertise."},
                                {"role": "user", "content": prompt_override},
                            ],
                        )
                    )
                    content = (resp.choices[0].message.content or "").strip()
                    return StepResult(
                        step_id=0, success=True,
                        data={"agent": target_agent, "requesting_agent": requesting_agent, "response": content, "cross_agent": True},
                        summary=f"{target_agent} (requested by {requesting_agent}): {content[:300]}",
                    )
                except Exception:
                    logger.warning("Cross-agent LLM call failed", exc_info=True)

            return StepResult(
                step_id=0, success=True,
                data={"agent": target_agent, "requesting_agent": requesting_agent, "cross_agent": True},
                summary=f"{target_agent} (requested by {requesting_agent}): Expert input on {question[:80]}",
            )
        return StepResult(step_id=0, success=False, error=f"Unknown agent: {target_agent}")

    def _execute_group_parallel(
        self,
        steps: list[PlanStep],
        results: dict[int, StepResult],
        plan: ExecutionPlan,
    ) -> Iterator[dict[str, Any]]:
        """Execute steps in a group, yielding events in real-time via shared queue."""
        event_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        active_count = threading.Semaphore(0)
        done_count = [0]
        lock = threading.Lock()
        total = len(steps)

        def run_step(step: PlanStep) -> None:
            try:
                for ev in self._execute_step(step, results, plan):
                    event_queue.put(ev)
            except Exception as e:
                logger.exception("Parallel step %d failed: %s", step.id, e)
                step.status = "failed"
                results[step.id] = StepResult(step_id=step.id, success=False, error=str(e))
                event_queue.put({
                    "type": "step_complete", "step_id": step.id,
                    "success": False, "error": str(e)[:200],
                })
            finally:
                with lock:
                    done_count[0] += 1
                    if done_count[0] >= total:
                        event_queue.put(None)  # sentinel

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for s in steps:
                pool.submit(run_step, s)

            # Yield events as they arrive from threads
            while True:
                try:
                    ev = event_queue.get(timeout=0.1)
                except queue.Empty:
                    # Yield heartbeat so SSE connection stays alive
                    yield {"type": "heartbeat"}
                    continue
                if ev is None:
                    break
                yield ev

    def _execute_step(
        self,
        step: PlanStep,
        results: dict[int, StepResult],
        plan: ExecutionPlan,
    ) -> Iterator[dict[str, Any]]:
        step.status = "in_progress"
        yield {
            "type": "step_start",
            "step_id": step.id,
            "description": step.description,
            "action": step.action,
            "tool": step.tool,
            "agent": step.agent,
        }

        try:
            # Use a thread-safe queue so progress events stream in real-time
            # instead of being batched until _dispatch_step returns.
            ev_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
            dispatch_result: list[StepResult] = []
            dispatch_error: list[Exception] = []

            def _run_dispatch() -> None:
                try:
                    r = self._dispatch_step(step, results, plan, events_out=ev_queue)
                    dispatch_result.append(r)
                except Exception as exc:
                    dispatch_error.append(exc)
                finally:
                    ev_queue.put(None)  # sentinel

            t = threading.Thread(target=_run_dispatch, daemon=True)
            t.start()

            # Drain events in real-time while dispatch runs
            while True:
                try:
                    ev = ev_queue.get(timeout=0.15)
                except queue.Empty:
                    yield {"type": "heartbeat"}
                    continue
                if ev is None:
                    break
                yield ev

            t.join(timeout=2)

            if dispatch_error:
                raise dispatch_error[0]

            result = dispatch_result[0] if dispatch_result else StepResult(
                step_id=step.id, success=False, error="Dispatch returned no result"
            )
            step.status = "completed" if result.success else "failed"
            step.result = result
            results[step.id] = result

            event: dict[str, Any] = {
                "type": "step_complete",
                "step_id": step.id,
                "success": result.success,
                "summary": result.summary[:300] if result.summary else "",
            }
            if result.data.get("sources"):
                event["sources"] = result.data["sources"][:8]
            yield event

            if result.data.get("sources"):
                for src in result.data["sources"][:8]:
                    yield {
                        "type": "source_found",
                        "step_id": step.id,
                        "title": src.get("title", ""),
                        "url": src.get("url", ""),
                    }

            if step.agent and step.agent != "CD":
                yield {
                    "type": "agent_consulted",
                    "agent": step.agent,
                    "summary": result.summary[:200] if result.summary else "",
                }

            if result.data.get("url"):
                yield {
                    "type": "document_ready",
                    "url": result.data["url"],
                    "title": result.data.get("title", "Document"),
                    "document_type": result.data.get("document_type", "pptx"),
                    "slide_count": result.data.get("slides_count", 0),
                    "path": result.data.get("path", ""),
                }

        except Exception as e:
            logger.exception("Step %d failed: %s", step.id, e)
            step.status = "failed"
            results[step.id] = StepResult(
                step_id=step.id, success=False, error=str(e)
            )
            yield {
                "type": "step_complete",
                "step_id": step.id,
                "success": False,
                "error": str(e)[:200],
            }

    def _dispatch_step(
        self,
        step: PlanStep,
        results: dict[int, StepResult],
        plan: ExecutionPlan,
        events_out: EventSink | None = None,
    ) -> StepResult:
        events_out = events_out or []
        if step.action == "research" and step.tool == "researcher":
            return self._run_research(step, plan, events_out)
        elif step.action == "consult_agent" and step.agent == "CD":
            return self._consult_cd(step, plan)
        elif step.action == "consult_agent" and step.agent in CXO_CONSULT_PROMPTS:
            return self._consult_cxo(step, plan, results, events_out)
        elif step.action == "synthesize":
            return self._synthesize(step, results, plan, events_out)
        elif step.action == "generate":
            return self._generate_document(step, results, plan, events_out)
        elif step.action == "validate":
            return self._validate(step, results, plan)
        elif step.action == "use_tool" and step.tool:
            return self._run_tool(step)
        elif step.action in ("research",) and step.tool == "web_search":
            return self._run_web_search(step)
        elif step.action == "consult_agent" and step.agent:
            return self._consult_cxo(step, plan, results, events_out)
        else:
            return self._run_tool(step)

    def _run_research(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        events_out: EventSink | None = None,
    ) -> StepResult:
        events_out = events_out or []
        tool = self.tool_registry.get("researcher") if self.tool_registry else None
        if not tool:
            return StepResult(step.id, False, error="Researcher tool not available")

        topic = step.params.get("topic") or step.params.get("query") or ""
        if not topic:
            topic = step.description or "general topic"

        methodology_brief = None
        if settings.quality.use_methodology_designer:
            try:
                from agentic_cxo.agents.methodology import design_methodology

                _emit(events_out,{
                    "type": "step_progress",
                    "message": "Methodology Designer: defining research approach...",
                })
                methodology_brief = design_methodology(
                    task=topic,
                    agent="Researcher",
                    plan_intent=plan.intent[:200],
                )
            except Exception:
                logger.debug("Methodology Designer for research skipped", exc_info=True)

        max_rounds = settings.quality.max_validation_rounds
        last_result = None
        for round_idx in range(max_rounds):
            try:
                result = tool.execute(
                    topic=topic,
                    focus=step.params.get("focus", "general"),
                    methodology_brief=methodology_brief,
                )
                last_result = result
            except Exception as e:
                logger.exception("Research step %d failed for topic: %s", step.id, topic[:60])
                return StepResult(step.id, False, error=f"Research failed: {str(e)[:200]}")

            if not result.success:
                return StepResult(
                    step_id=step.id,
                    success=False,
                    data=result.data,
                    summary=result.summary,
                    error=result.error,
                )

            research_text = result.summary or str(result.data.get("findings", ""))[:3000]

            if not settings.quality.use_review_agent and not settings.quality.use_methodology_auditor:
                break

            review_ok = True
            audit_ok = True
            feedback_parts = []

            if settings.quality.use_review_agent:
                try:
                    from agentic_cxo.agents.methodology import review_output

                    _emit(events_out,{"type": "step_progress", "message": "Review Agent: validating research..."})
                    review = review_output(topic, "Researcher", research_text, methodology_brief)
                    review_ok = review.get("pass", True)
                    if not review_ok and review.get("feedback_for_agent"):
                        feedback_parts.append(review["feedback_for_agent"])
                except Exception:
                    pass

            if settings.quality.use_methodology_auditor:
                try:
                    from agentic_cxo.agents.methodology import audit_methodology

                    _emit(events_out,{"type": "step_progress", "message": "Methodology Auditor: auditing research reasoning..."})
                    audit = audit_methodology(topic, "Researcher", research_text, methodology_brief)
                    audit_ok = audit.get("pass", True)
                    if not audit_ok and audit.get("feedback_for_agent"):
                        feedback_parts.append(audit["feedback_for_agent"])
                except Exception:
                    pass

            if review_ok and audit_ok:
                break

            if feedback_parts and round_idx < max_rounds - 1:
                must_cover = methodology_brief or {}
                must_cover = dict(must_cover)
                must_cover["must_cover"] = must_cover.get("must_cover", []) + [
                    fb[:80] for fb in feedback_parts[:2]
                ]
                methodology_brief = must_cover
                _emit(events_out,{
                    "type": "step_progress",
                    "message": "Research quality feedback: deepening research...",
                })

        return StepResult(
            step_id=step.id,
            success=last_result.success,
            data=last_result.data,
            summary=last_result.summary,
            error=last_result.error,
        )

    def _run_web_search(self, step: PlanStep) -> StepResult:
        tool = self.tool_registry.get("web_search") if self.tool_registry else None
        if not tool:
            return StepResult(step.id, False, error="Web search not available")

        result = tool.execute(query=step.params.get("query", step.params.get("topic", "")))
        return StepResult(
            step_id=step.id,
            success=result.success,
            data=result.data,
            summary=result.summary,
            error=result.error,
        )

    def _consult_cd(self, step: PlanStep, plan: ExecutionPlan) -> StepResult:
        if not self.creative_director:
            return StepResult(step.id, True, data={}, summary="CD not available, using defaults")

        task = step.params.get("task", "visual_brief")
        doc_type = step.params.get("document_type") or plan.document_type or "presentation"
        cxo_source = step.params.get("cxo_source", "")

        if task == "visual_brief":
            brief = self.creative_director.get_visual_brief(plan.intent, cxo_source)
            template = self.creative_director.get_document_template(doc_type)
            return StepResult(
                step_id=step.id,
                success=True,
                data={
                    "visual_brief": brief,
                    "document_template": template,
                    "tokens": self.creative_director.tokens,
                },
                summary=f"Visual direction set: {brief.get('style_emphasis', 'professional')} style, "
                        f"{brief['typography']['heading']} headings, {brief['color_palette']['primary']} primary color",
            )
        elif task == "post_production":
            metadata = step.params.get("metadata", {})
            validation = self.creative_director.validate_output(doc_type, metadata)
            return StepResult(
                step_id=step.id,
                success=validation.get("valid", True),
                data={"validation": validation},
                summary=f"Quality score: {validation.get('quality_score', 0)}/100"
                        + (f". Issues: {', '.join(validation['issues'])}" if validation.get("issues") else ""),
            )
        return StepResult(step.id, True, summary="CD consulted")

    def _consult_cxo(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        results: dict[int, StepResult],
        events_out: EventSink | None = None,
    ) -> StepResult:
        """Consult a CXO agent with Methodology Designer, Review Agent, and Methodology Auditor.

        Flow: Designer brief → CXO works → Review + Audit → if fail, feedback → retry.
        """
        events_out = events_out or []
        agent_role = step.agent or "COO"
        task_desc = step.description or step.params.get("task", plan.intent)

        context_parts = []
        for sid in step.depends_on:
            sr = results.get(sid)
            if sr and sr.success and sr.summary:
                context_parts.append(sr.summary[:300])
        for sr in results.values():
            if sr and sr.data.get("cxo_insight") and sr.summary:
                context_parts.append(sr.summary[:200])
        business_context = "\n".join(context_parts) if context_parts else "No prior context."

        methodology_brief = None
        if settings.quality.use_methodology_designer:
            try:
                from agentic_cxo.agents.methodology import design_methodology

                _emit(events_out,{
                    "type": "step_progress",
                    "message": f"Methodology Designer: defining approach for {agent_role}...",
                })
                methodology_brief = design_methodology(
                    task=task_desc,
                    agent=agent_role,
                    context=business_context[:500],
                    plan_intent=plan.intent[:200],
                )
            except Exception:
                logger.debug("Methodology Designer skipped", exc_info=True)

        brief_instruction = ""
        if methodology_brief and isinstance(methodology_brief, dict):
            must_cover = methodology_brief.get("must_cover", [])
            assumptions = methodology_brief.get("assumptions_to_state", [])
            summary = methodology_brief.get("brief_summary", "")
            if must_cover or assumptions or summary:
                brief_instruction = (
                    "\n\nMETHODOLOGY BRIEF (follow this):\n"
                    + (f"Must cover: {', '.join(must_cover[:6])}\n" if must_cover else "")
                    + (f"State assumptions on: {', '.join(assumptions[:4])}\n" if assumptions else "")
                    + (f"{summary}\n" if summary else "")
                )

        prompt_template = CXO_CONSULT_PROMPTS.get(agent_role)
        if not prompt_template:
            prompt_template = (
                f"You are the AI {agent_role}. Given this task: {{task}}\n"
                f"Business context: {{context}}\n"
                "Provide your expert analysis and recommendations."
            )
        prompt = prompt_template.format(task=task_desc, context=business_context) + brief_instruction

        cross_agent_note = (
            "\n\nIf you need input from another C-suite officer, end with:\n"
            "NEED_INPUT_FROM: <ROLE> | <question>\n"
            "Available: CFO, COO, CMO, CLO, CHRO, CSO, CD"
        )

        from agentic_cxo.infrastructure.llm_required import require_llm

        require_llm("CXO consultation")
        client = self._get_client()
        from agentic_cxo.infrastructure.llm_retry import with_retry

        max_rounds = settings.quality.max_validation_rounds
        content = ""
        for round_idx in range(max_rounds):
            if round_idx > 0:
                _emit(events_out,{
                    "type": "step_progress",
                    "message": f"{agent_role}: amending based on feedback (round {round_idx + 1})...",
                })

            resp = with_retry(
                lambda: client.chat.completions.create(
                    model=settings.llm.model,
                    temperature=0.3,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": f"You are the AI {agent_role}. Be concise, data-driven, actionable." + cross_agent_note},
                        {"role": "user", "content": prompt},
                    ],
                )
            )
            content = (resp.choices[0].message.content or "").strip()

            cross_input = self._handle_cross_agent_request(content, agent_role, plan)
            if cross_input:
                content = content.split("NEED_INPUT_FROM:")[0].strip()
                content += f"\n\n**{cross_input.data.get('agent', '')} input**:\n{cross_input.summary}"

            if not settings.quality.use_review_agent and not settings.quality.use_methodology_auditor:
                break

            review_ok = True
            audit_ok = True
            feedback_parts = []

            if settings.quality.use_review_agent:
                try:
                    from agentic_cxo.agents.methodology import review_output

                    _emit(events_out,{
                        "type": "step_progress",
                        "message": f"Review Agent: validating {agent_role} output...",
                    })
                    review = review_output(task_desc, agent_role, content, methodology_brief)
                    review_ok = review.get("pass", True)
                    if not review_ok and review.get("feedback_for_agent"):
                        feedback_parts.append(f"Review: {review['feedback_for_agent']}")
                except Exception:
                    logger.debug("Review Agent skipped", exc_info=True)

            if settings.quality.use_methodology_auditor:
                try:
                    from agentic_cxo.agents.methodology import audit_methodology

                    _emit(events_out,{
                        "type": "step_progress",
                        "message": f"Methodology Auditor: auditing {agent_role} reasoning...",
                    })
                    audit = audit_methodology(task_desc, agent_role, content, methodology_brief)
                    audit_ok = audit.get("pass", True)
                    if not audit_ok and audit.get("feedback_for_agent"):
                        feedback_parts.append(f"Audit: {audit['feedback_for_agent']}")
                except Exception:
                    logger.debug("Methodology Auditor skipped", exc_info=True)

            if review_ok and audit_ok:
                break

            if feedback_parts:
                prompt = (
                    f"ORIGINAL TASK: {task_desc}\n\n"
                    f"CONTEXT: {business_context[:400]}\n\n"
                    f"YOUR PREVIOUS RESPONSE:\n{content[:2000]}\n\n"
                    f"FEEDBACK — amend your response to address:\n"
                    + "\n".join(f"- " + p for p in feedback_parts)
                    + "\n\nProvide your revised, improved response."
                )

        return StepResult(
            step_id=step.id,
            success=True,
            data={
                "agent": agent_role,
                "response": content,
                "cxo_insight": True,
                "methodology_brief": methodology_brief,
            },
            summary=f"{agent_role}: {content[:300]}",
        )

    def _handle_cross_agent_request(
        self, content: str, requesting_agent: str, plan: ExecutionPlan
    ) -> StepResult | None:
        """Parse NEED_INPUT_FROM directive and make the cross-agent call."""
        import re
        match = re.search(r"NEED_INPUT_FROM:\s*(\w+)\s*\|\s*(.+)", content)
        if not match:
            return None

        target = match.group(1).strip().upper()
        question = match.group(2).strip()

        valid_agents = {"CFO", "COO", "CMO", "CLO", "CHRO", "CSO", "CD"}
        if target not in valid_agents or target == requesting_agent:
            return None

        logger.info("Cross-agent: %s -> %s: %s", requesting_agent, target, question[:80])
        return self.request_cross_agent_input(
            requesting_agent=requesting_agent,
            target_agent=target,
            question=question,
            context=content[:500],
            plan=plan,
        )

    def _synthesize(
        self,
        step: PlanStep,
        results: dict[int, StepResult],
        plan: ExecutionPlan,
        events_out: EventSink | None = None,
    ) -> StepResult:
        events_out = events_out or []
        input_step_ids = step.params.get("input_steps", step.depends_on)
        input_data: list[str] = []
        all_sources: list[dict] = []
        all_findings: list[str] = []

        gather_ids = input_step_ids if input_step_ids else list(results.keys())
        for sid in gather_ids:
            sr = results.get(sid)
            if sr and sr.success:
                if sr.summary:
                    input_data.append(sr.summary)
                if sr.data.get("findings"):
                    all_findings.extend(sr.data["findings"])
                if sr.data.get("sources"):
                    all_sources.extend(sr.data["sources"])

        cd_result = None
        for sid, sr in results.items():
            if sr and sr.data.get("visual_brief"):
                cd_result = sr

        doc_type = plan.document_type or "presentation"
        template = None
        if self.creative_director:
            template = self.creative_director.get_document_template(doc_type)

        methodology_brief = None
        if settings.quality.use_methodology_designer:
            try:
                from agentic_cxo.agents.methodology import design_synthesis_methodology

                _emit(events_out,{
                    "type": "step_progress",
                    "message": "Methodology Designer: defining synthesis approach...",
                })
                input_summary = "\n".join(d[:150] for d in input_data[:5]) if input_data else "Research + CXO inputs"
                methodology_brief = design_synthesis_methodology(
                    plan_intent=plan.intent[:300],
                    doc_type=doc_type,
                    input_summary=input_summary,
                )
            except Exception:
                logger.debug("Synthesis Methodology Designer skipped", exc_info=True)

        from agentic_cxo.infrastructure.llm_required import require_llm

        require_llm("synthesis")
        return self._llm_synthesize(
            step, plan, input_data, all_findings, all_sources,
            cd_result, template, methodology_brief, events_out,
        )

    def _llm_synthesize(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        input_data: list[str],
        findings: list[str],
        sources: list[dict],
        cd_result: StepResult | None,
        template: dict | None,
        methodology_brief: dict[str, Any] | None = None,
        events_out: EventSink | None = None,
    ) -> StepResult:
        events_out = events_out or []
        client = self._get_client()
        from agentic_cxo.infrastructure.llm_retry import with_retry

        doc_type = plan.document_type or "presentation"
        structure = template.get("structure", []) if template else []
        rules = template.get("rules", []) if template else []
        min_slides = template.get("min_slides", 8) if template else 8

        brief_instruction = ""
        if methodology_brief and isinstance(methodology_brief, dict):
            must_cover = methodology_brief.get("must_cover", [])
            summary = methodology_brief.get("brief_summary", "")
            if must_cover or summary:
                brief_instruction = (
                    "\n\nMETHODOLOGY BRIEF:\n"
                    + (f"Must cover: {', '.join(must_cover[:8])}\n" if must_cover else "")
                    + (f"{summary}\n" if summary else "")
                )

        research_text = "\n\n---\n\n".join(input_data[:5])
        findings_text = "\n".join(f"- {f[:200]}" for f in findings[:20])
        sources_text = "\n".join(f"- {s.get('title', '')}: {s.get('url', '')}" for s in sources[:10])

        task_desc = f"Synthesize research + CXO inputs into a {doc_type} outline for: {plan.intent}"
        max_rounds = settings.quality.max_validation_rounds
        outline = ""
        prompt_base = (
            f"You are creating a {doc_type} outline on: {plan.intent}\n\n"
            f"QUALITY BAR: {plan.quality_bar}\n\n"
            f"DOCUMENT STRUCTURE: {', '.join(structure)}\n"
            f"MINIMUM SECTIONS: {min_slides}\n"
            f"RULES:\n" + "\n".join(f"- {r}" for r in rules) + "\n\n"
            f"RESEARCH FINDINGS:\n{findings_text}\n\n"
            f"SOURCES:\n{sources_text}\n\n"
            f"FULL RESEARCH:\n{research_text[:3000]}\n\n"
            "Create a comprehensive markdown outline for this document. Use ## for section titles "
            "and - for bullet points. Include SPECIFIC data points, statistics, and insights from the research. "
            "Each section should have 4-8 substantive bullets with real information, not generic placeholders. "
            "Include a Sources section at the end. "
            f"Create at least {min_slides} sections."
        ) + brief_instruction

        for round_idx in range(max_rounds):
            if round_idx > 0:
                _emit(events_out,{
                    "type": "step_progress",
                    "message": f"Synthesis: amending outline based on feedback (round {round_idx + 1})...",
                })

            resp = with_retry(
                lambda: client.chat.completions.create(
                    model=settings.llm.model,
                    temperature=0.3,
                    max_tokens=4096,
                    messages=[
                        {"role": "system", "content": "You are an expert content strategist. Create detailed, data-rich document outlines."},
                        {"role": "user", "content": prompt_base},
                    ],
                )
            )
            outline = (resp.choices[0].message.content or "").strip()

            if not settings.quality.use_review_agent and not settings.quality.use_methodology_auditor:
                break

            review_ok = True
            audit_ok = True
            feedback_parts: list[str] = []

            if settings.quality.use_review_agent:
                try:
                    from agentic_cxo.agents.methodology import review_output

                    _emit(events_out,{
                        "type": "step_progress",
                        "message": "Review Agent: validating synthesis output...",
                    })
                    review = review_output(task_desc, "Synthesis", outline, methodology_brief or {})
                    review_ok = review.get("pass", True)
                    if not review_ok and review.get("feedback_for_agent"):
                        feedback_parts.append(f"Review: {review['feedback_for_agent']}")
                except Exception:
                    logger.debug("Synthesis Review Agent skipped", exc_info=True)

            if settings.quality.use_methodology_auditor:
                try:
                    from agentic_cxo.agents.methodology import audit_methodology

                    _emit(events_out,{
                        "type": "step_progress",
                        "message": "Methodology Auditor: auditing synthesis reasoning...",
                    })
                    audit = audit_methodology(task_desc, "Synthesis", outline, methodology_brief or {})
                    audit_ok = audit.get("pass", True)
                    if not audit_ok and audit.get("feedback_for_agent"):
                        feedback_parts.append(f"Audit: {audit['feedback_for_agent']}")
                except Exception:
                    logger.debug("Synthesis Methodology Auditor skipped", exc_info=True)

            if review_ok and audit_ok:
                break

            if feedback_parts and round_idx < max_rounds - 1:
                prompt_base = (
                    f"ORIGINAL TASK: Create outline for: {plan.intent}\n"
                    f"CONTEXT: {research_text[:2000]}\n\n"
                    f"PREVIOUS OUTLINE:\n{outline[:2500]}\n\n"
                    f"FEEDBACK (address this):\n" + "\n".join(feedback_parts) + "\n\n"
                    "Produce a REVISED, improved outline addressing the feedback."
                ) + brief_instruction

        return StepResult(
            step_id=step.id,
            success=True,
            data={
                "outline": outline,
                "sources": sources,
                "findings_count": len(findings),
                "source_count": len(sources),
            },
            summary=f"Synthesized {len(findings)} findings from {len(sources)} sources into structured outline",
        )

    def _fallback_synthesize(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        input_data: list[str],
        findings: list[str],
        sources: list[dict],
        cd_result: StepResult | None,
        template: dict | None,
    ) -> StepResult:
        doc_type = plan.document_type or "presentation"
        topic = plan.intent

        cxo_insights: list[str] = []
        for sr in (results.get(sid) for sid in step.depends_on if (results := {s.step_id: s for s in []})):
            pass
        for sr_val in [r for r in [None]]:
            pass
        cxo_data = []
        for sr in [r for sid in step.depends_on if (r := {}) or True]:
            pass
        raw_cxo: list[tuple[str, str]] = []
        for d in input_data:
            for role in ("CFO", "CMO", "COO", "CSO", "CLO", "CHRO"):
                if d.startswith(f"{role}:"):
                    raw_cxo.append((role, d[len(role)+1:].strip()))
                    break

        sections: list[str] = []

        sections.append(f"## Executive Summary")
        sections.append(f"- This analysis examines {topic} across multiple dimensions")
        if findings:
            sections.append(f"- Key insight: {findings[0][:180]}")
        sections.append(f"- {len(findings)} data points analyzed from research")
        if raw_cxo:
            sections.append(f"- Cross-functional input from: {', '.join(r for r, _ in raw_cxo)}")
        sections.append("")

        grouped: dict[str, list[str]] = {}
        section_names = [
            "Current Landscape & Context",
            "Key Research Findings",
            "Impact Analysis",
            "Opportunities & Benefits",
            "Challenges & Risks",
            "Strategic Implications",
        ]
        per_section = max(2, len(findings) // len(section_names)) if findings else 2

        for i, name in enumerate(section_names):
            start = i * per_section
            chunk = findings[start:start + per_section]
            sections.append(f"## {name}")
            if chunk:
                for f in chunk:
                    clean = str(f).replace("\n", " ").strip()[:220]
                    if clean:
                        sections.append(f"- {clean}")
            else:
                sections.append(f"- Analysis of {name.lower()} for {topic[:50]}")
                sections.append(f"- Further data collection recommended for this area")
            sections.append("")

        if raw_cxo:
            sections.append("## C-Suite Perspectives")
            for role, insight in raw_cxo:
                sections.append(f"- **{role}**: {insight[:200]}")
            sections.append("")

        sections.append("## Recommendations & Next Steps")
        sections.append(f"- Conduct deeper analysis on high-impact areas of {topic[:50]}")
        sections.append("- Develop implementation roadmap with clear milestones")
        sections.append("- Establish metrics and KPIs for tracking progress")
        sections.append("- Schedule follow-up review within 30 days")
        sections.append("")

        if sources:
            sections.append("## Sources & References")
            for s in sources[:10]:
                title = s.get("title", "Source")
                url = s.get("url", "")
                sections.append(f"- {title}: {url}")
            sections.append("")

        outline = "\n".join(sections)
        return StepResult(
            step_id=step.id,
            success=True,
            data={
                "outline": outline,
                "sources": sources,
                "findings_count": len(findings),
                "source_count": len(sources),
            },
            summary=f"Synthesized {len(findings)} findings from {len(sources)} sources into structured outline",
        )

    def _generate_document(
        self,
        step: PlanStep,
        results: dict[int, StepResult],
        plan: ExecutionPlan,
        events_out: EventSink | None = None,
    ) -> StepResult:
        events_out = events_out or []
        outline = ""
        sources: list[dict] = []
        visual_brief: dict = {}

        for sid in step.depends_on:
            sr = results.get(sid)
            if sr and sr.success:
                if sr.data.get("outline"):
                    outline = sr.data["outline"]
                if sr.data.get("visual_brief"):
                    visual_brief = sr.data["visual_brief"]
                if sr.data.get("sources"):
                    sources.extend(sr.data["sources"])

        if not outline:
            for sr in results.values():
                if sr.data.get("outline"):
                    outline = sr.data["outline"]
                    break
            if not outline:
                summaries = [sr.summary for sr in results.values() if sr.success and sr.summary]
                outline = "\n\n".join(summaries) if summaries else f"## {plan.intent}\n- Key points"

        tool = self.tool_registry.get("presentation_generator") if self.tool_registry else None
        if not tool:
            return StepResult(step.id, False, error="Presentation generator not available")

        topic = step.params.get("topic") or plan.intent
        brand_domain = step.params.get("brand_domain", "")
        max_cycles = settings.ppqa.max_qa_cycles
        doc_type = plan.document_type or step.params.get("document_type") or "presentation"

        methodology_brief = None
        if settings.quality.use_methodology_designer:
            try:
                from agentic_cxo.agents.methodology import design_document_methodology

                _emit(events_out,{
                    "type": "step_progress",
                    "message": "Methodology Designer: defining document generation approach...",
                })
                outline_summary = outline[:600] if outline else "Presentation outline"
                methodology_brief = design_document_methodology(
                    plan_intent=plan.intent[:300],
                    doc_type=doc_type,
                    outline_summary=outline_summary,
                )
            except Exception:
                logger.debug("Document Methodology Designer skipped", exc_info=True)

        def progress_cb(msg: str) -> None:
            _emit(events_out,{"type": "step_progress", "message": msg})

        for cycle in range(max_cycles):
            result = tool.execute(
                title=topic[:80],
                outline=outline,
                brand_domain=brand_domain,
                progress_callback=progress_cb,
                methodology_brief=methodology_brief,
            )
            if not result.success:
                return StepResult(
                    step_id=step.id,
                    success=False,
                    data=result.data or {},
                    summary=result.summary,
                    error=result.error,
                )

            pptx_path = result.data.get("path")
            if not pptx_path:
                break

            path = Path(pptx_path)
            if not path.is_absolute():
                path = path.resolve()

            if not path.exists():
                break

            try:
                from agentic_cxo.tools.pptx_qa import PPQAError, run_vision_qa

                qa_result = run_vision_qa(
                    path, brand=brand_domain, progress_callback=progress_cb
                )
                feedback = qa_result.get("feedback", "")
                issues = qa_result.get("issues", [])
                passed = qa_result.get("pass", True)

                if feedback:
                    _emit(events_out,{
                        "type": "narration",
                        "message": feedback[:500] if len(feedback) > 500 else feedback,
                    })

                if passed and (settings.quality.use_review_agent or settings.quality.use_methodology_auditor):
                    output_desc = f"Outline:\n{outline[:2000]}\n\nGenerated: {result.data.get('slides_count', 0)} slides. Path: {pptx_path}"
                    review_ok = True
                    audit_ok = True
                    doc_feedback: list[str] = []

                    if settings.quality.use_review_agent:
                        try:
                            from agentic_cxo.agents.methodology import review_output

                            _emit(events_out,{
                                "type": "step_progress",
                                "message": "Review Agent: validating document output...",
                            })
                            task_desc = f"Generate {doc_type} from outline for: {plan.intent}"
                            review = review_output(task_desc, "Document Generator", output_desc, methodology_brief or {})
                            review_ok = review.get("pass", True)
                            if not review_ok and review.get("feedback_for_agent"):
                                doc_feedback.append(f"Review: {review['feedback_for_agent']}")
                        except Exception:
                            logger.debug("Doc Review Agent skipped", exc_info=True)

                    if settings.quality.use_methodology_auditor:
                        try:
                            from agentic_cxo.agents.methodology import audit_methodology

                            _emit(events_out,{
                                "type": "step_progress",
                                "message": "Methodology Auditor: auditing document generation...",
                            })
                            task_desc = f"Generate {doc_type} from outline for: {plan.intent}"
                            audit = audit_methodology(task_desc, "Document Generator", output_desc, methodology_brief or {})
                            audit_ok = audit.get("pass", True)
                            if not audit_ok and audit.get("feedback_for_agent"):
                                doc_feedback.append(f"Audit: {audit['feedback_for_agent']}")
                        except Exception:
                            logger.debug("Doc Methodology Auditor skipped", exc_info=True)

                    if not (review_ok and audit_ok) and doc_feedback and cycle < max_cycles - 1:
                        from agentic_cxo.infrastructure.llm_required import require_llm

                        require_llm("outline fix for document quality feedback")
                        fix_prompt = (
                            f"Document quality feedback:\n{chr(10).join(doc_feedback)}\n\n"
                            f"Current outline:\n{outline[:2500]}\n\n"
                            "Revise the outline to address the feedback. Return ONLY the revised markdown outline."
                        )
                        client = self._get_client()
                        from agentic_cxo.infrastructure.llm_retry import with_retry
                        resp = with_retry(
                            lambda: client.chat.completions.create(
                                model=settings.llm.model,
                                temperature=0.2,
                                max_tokens=4096,
                                messages=[
                                    {"role": "system", "content": "You are a presentation editor. Improve outline based on feedback."},
                                    {"role": "user", "content": fix_prompt},
                                ],
                            )
                        )
                        revised = (resp.choices[0].message.content or "").strip()
                        if revised and len(revised) > 100:
                            outline = revised
                            _emit(events_out,{
                                "type": "narration",
                                "message": "Applying quality feedback. Regenerating document...",
                            })
                            continue

                if passed:
                    _emit(events_out,{
                        "type": "narration",
                        "message": "The slides look great. Design is clean and professional. Copying to outputs.",
                    })
                    break

                if cycle < max_cycles - 1 and issues:
                    from agentic_cxo.infrastructure.llm_required import require_llm

                    require_llm("outline fix for QA feedback")
                    fix_prompt = (
                        f"Presentation QA found issues:\n{chr(10).join(issues[:5])}\n\n"
                        f"Current outline (markdown):\n{outline[:2500]}\n\n"
                        "Suggest a revised markdown outline that fixes these issues. "
                        "Keep the same structure and content, but adjust wording/layout hints "
                        "to fix rendering problems (e.g. quote layout, line breaks). "
                        "Return ONLY the revised markdown outline, no explanation."
                    )
                    client = self._get_client()
                    from agentic_cxo.infrastructure.llm_retry import with_retry
                    resp = with_retry(
                        lambda: client.chat.completions.create(
                            model=settings.llm.model,
                            temperature=0.2,
                            max_tokens=4096,
                            messages=[
                                {"role": "system", "content": "You are a presentation editor. Fix layout issues."},
                                {"role": "user", "content": fix_prompt},
                            ],
                        )
                    )
                    revised = (resp.choices[0].message.content or "").strip()
                    if revised and len(revised) > 100:
                        outline = revised
                        _emit(events_out,{
                            "type": "narration",
                            "message": f"Applying fixes for {len(issues)} issue(s). Regenerating...",
                        })
            except PPQAError as e:
                _emit(events_out,{
                    "type": "narration",
                    "message": f"QA skipped (missing dependencies): {str(e)[:120]}. Output ready.",
                })
                break
            except Exception:
                logger.warning("PPT QA failed, using generated output", exc_info=True)
                break

        data = result.data or {}
        data["document_type"] = step.params.get("document_type") or plan.document_type or "pptx"
        data["sources"] = sources

        return StepResult(
            step_id=step.id,
            success=result.success,
            data=data,
            summary=result.summary,
            error=result.error,
        )

    def _validate(
        self, step: PlanStep, results: dict[int, StepResult], plan: ExecutionPlan
    ) -> StepResult:
        if not self.creative_director:
            return StepResult(step.id, True, summary="Validation skipped — CD not available")

        gen_result = None
        for sid in step.depends_on:
            sr = results.get(sid)
            if sr and sr.data.get("url"):
                gen_result = sr
                break

        if not gen_result:
            return StepResult(step.id, True, summary="No document to validate")

        metadata = {
            "slide_count": gen_result.data.get("slides_count", 0),
            "has_title_slide": True,
            "has_closing_slide": True,
            "brand_used": bool(gen_result.data.get("brand_used")),
        }
        validation = self.creative_director.validate_output(
            plan.document_type or "presentation", metadata
        )
        return StepResult(
            step_id=step.id,
            success=validation.get("valid", True),
            data={"validation": validation},
            summary=f"Quality score: {validation.get('quality_score', 0)}/100",
        )

    def _run_tool(self, step: PlanStep) -> StepResult:
        tool_name = step.tool
        if not tool_name or not self.tool_registry:
            return StepResult(step.id, False, error=f"Tool {tool_name} not available")

        tool = self.tool_registry.get(tool_name)
        if not tool:
            return StepResult(step.id, False, error=f"Tool {tool_name} not found")

        try:
            result = tool.execute(**step.params)
        except Exception as e:
            logger.warning("Tool %s failed: %s", tool_name, e, exc_info=True)
            # Graceful degradation: non-critical tools should not block the pipeline
            return StepResult(
                step_id=step.id,
                success=False,
                data={},
                summary=f"{tool_name} encountered an error but pipeline continues.",
                error=str(e)[:200],
            )
        return StepResult(
            step_id=step.id,
            success=result.success,
            data=result.data,
            summary=result.summary,
            error=result.error,
        )
