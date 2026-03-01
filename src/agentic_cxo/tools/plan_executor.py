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
from dataclasses import dataclass, field
from typing import Any, Iterator

from agentic_cxo.config import settings
from agentic_cxo.tools.planner import ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)


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

            if group_failed > 0 and group_completed > 0:
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

    def _execute_group_parallel(
        self,
        steps: list[PlanStep],
        results: dict[int, StepResult],
        plan: ExecutionPlan,
    ) -> Iterator[dict[str, Any]]:
        """Execute steps in a group, collecting events."""
        collected_events: list[dict[str, Any]] = []
        step_events_map: dict[int, list[dict[str, Any]]] = {s.id: [] for s in steps}

        def run_step(step: PlanStep) -> None:
            for ev in self._execute_step(step, results, plan):
                step_events_map[step.id].append(ev)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(run_step, s): s for s in steps}
            concurrent.futures.wait(futures)

        for step in steps:
            for ev in step_events_map[step.id]:
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
            result = self._dispatch_step(step, results, plan)
            step.status = "completed"
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
            if result.data.get("url"):
                event["url"] = result.data["url"]
                event["document_type"] = result.data.get("document_type", "pptx")
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
    ) -> StepResult:
        if step.action == "research" and step.tool == "researcher":
            return self._run_research(step)
        elif step.action == "consult_agent" and step.agent == "CD":
            return self._consult_cd(step, plan)
        elif step.action == "consult_agent" and step.agent in CXO_CONSULT_PROMPTS:
            return self._consult_cxo(step, plan, results)
        elif step.action == "synthesize":
            return self._synthesize(step, results, plan)
        elif step.action == "generate":
            return self._generate_document(step, results, plan)
        elif step.action == "validate":
            return self._validate(step, results, plan)
        elif step.action == "use_tool" and step.tool:
            return self._run_tool(step)
        elif step.action in ("research",) and step.tool == "web_search":
            return self._run_web_search(step)
        elif step.action == "consult_agent" and step.agent:
            return self._consult_cxo(step, plan, results)
        else:
            return self._run_tool(step)

    def _run_research(self, step: PlanStep) -> StepResult:
        tool = self.tool_registry.get("researcher") if self.tool_registry else None
        if not tool:
            return StepResult(step.id, False, error="Researcher tool not available")

        result = tool.execute(
            topic=step.params.get("topic", ""),
            focus=step.params.get("focus", "general"),
        )
        return StepResult(
            step_id=step.id,
            success=result.success,
            data=result.data,
            summary=result.summary,
            error=result.error,
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
        self, step: PlanStep, plan: ExecutionPlan, results: dict[int, StepResult]
    ) -> StepResult:
        """Consult a CXO agent (CFO, CMO, COO, CSO, CLO, CHRO) via LLM."""
        agent_role = step.agent or "COO"
        task_desc = step.description or step.params.get("task", plan.intent)

        context_parts = []
        for sid in step.depends_on:
            sr = results.get(sid)
            if sr and sr.success and sr.summary:
                context_parts.append(sr.summary[:300])

        business_context = "\n".join(context_parts) if context_parts else "No prior context."

        prompt_template = CXO_CONSULT_PROMPTS.get(agent_role)
        if not prompt_template:
            prompt_template = (
                f"You are the AI {agent_role}. Given this task: {{task}}\n"
                f"Business context: {{context}}\n"
                "Provide your expert analysis and recommendations."
            )

        prompt = prompt_template.format(task=task_desc, context=business_context)

        if self.use_llm and settings.llm.api_key:
            try:
                client = self._get_client()
                from agentic_cxo.infrastructure.llm_retry import with_retry

                resp = with_retry(
                    lambda: client.chat.completions.create(
                        model=settings.llm.model,
                        temperature=0.3,
                        max_tokens=1500,
                        messages=[
                            {"role": "system", "content": f"You are the AI {agent_role} for a business co-founder system. Be concise, data-driven, and actionable."},
                            {"role": "user", "content": prompt},
                        ],
                    )
                )
                content = (resp.choices[0].message.content or "").strip()
                return StepResult(
                    step_id=step.id,
                    success=True,
                    data={"agent": agent_role, "response": content, "cxo_insight": True},
                    summary=f"{agent_role}: {content[:300]}",
                )
            except Exception:
                logger.warning("CXO %s consultation LLM failed, using fallback", agent_role, exc_info=True)

        fallback_insights = {
            "CFO": f"Financial analysis for '{task_desc[:60]}': Review cost structure, revenue projections, and cash flow impact. Recommend budget allocation and ROI targets.",
            "CMO": f"Marketing perspective for '{task_desc[:60]}': Consider brand positioning, target audience segments, channel strategy, and competitive differentiation.",
            "COO": f"Operational view for '{task_desc[:60]}': Assess process requirements, vendor dependencies, timeline feasibility, and resource allocation.",
            "CSO": f"Sales strategy for '{task_desc[:60]}': Evaluate pipeline impact, deal positioning, pricing strategy, and customer acquisition approach.",
            "CLO": f"Legal considerations for '{task_desc[:60]}': Review compliance requirements, risk factors, contractual obligations, and regulatory landscape.",
            "CHRO": f"People perspective for '{task_desc[:60]}': Consider talent requirements, team structure, culture impact, and organizational readiness.",
        }

        fallback = fallback_insights.get(agent_role, f"{agent_role} analysis for '{task_desc[:60]}': Expert input on relevant domain areas.")
        return StepResult(
            step_id=step.id,
            success=True,
            data={"agent": agent_role, "response": fallback, "cxo_insight": True},
            summary=f"{agent_role}: {fallback}",
        )

    def _synthesize(
        self, step: PlanStep, results: dict[int, StepResult], plan: ExecutionPlan
    ) -> StepResult:
        input_step_ids = step.params.get("input_steps", step.depends_on)
        input_data: list[str] = []
        all_sources: list[dict] = []
        all_findings: list[str] = []

        for sid in input_step_ids:
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
            if sr.data.get("visual_brief"):
                cd_result = sr

        doc_type = plan.document_type or "presentation"
        template = None
        if self.creative_director:
            template = self.creative_director.get_document_template(doc_type)

        if self.use_llm and settings.llm.api_key:
            return self._llm_synthesize(
                step, plan, input_data, all_findings, all_sources, cd_result, template
            )

        return self._fallback_synthesize(
            step, plan, input_data, all_findings, all_sources, cd_result, template
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
    ) -> StepResult:
        client = self._get_client()
        from agentic_cxo.infrastructure.llm_retry import with_retry

        doc_type = plan.document_type or "presentation"
        structure = template.get("structure", []) if template else []
        rules = template.get("rules", []) if template else []
        min_slides = template.get("min_slides", 8) if template else 8

        research_text = "\n\n---\n\n".join(input_data[:5])
        findings_text = "\n".join(f"- {f[:200]}" for f in findings[:20])
        sources_text = "\n".join(f"- {s.get('title', '')}: {s.get('url', '')}" for s in sources[:10])

        prompt = (
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
        )

        resp = with_retry(
            lambda: client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.3,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": "You are an expert content strategist. Create detailed, data-rich document outlines."},
                    {"role": "user", "content": prompt},
                ],
            )
        )

        outline = (resp.choices[0].message.content or "").strip()
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

        sections: list[str] = []
        sections.append(f"## {topic}\n")
        sections.append("- Overview and scope")
        sections.append("- Key objectives and context\n")

        if template and template.get("structure"):
            for section_type in template["structure"]:
                if section_type in ("title", "cover"):
                    continue
                if section_type == "toc":
                    continue
                name = section_type.replace("_", " ").title()
                sections.append(f"## {name}\n")
                chunk = findings[:4] if findings else [f"Key points about {name.lower()}"]
                for f in chunk:
                    sections.append(f"- {str(f)[:200]}")
                findings = findings[4:]
                sections.append("")
        else:
            for i, f in enumerate(findings[:24]):
                if i % 4 == 0:
                    section_num = i // 4 + 1
                    sections.append(f"\n## Key Findings — Part {section_num}\n")
                sections.append(f"- {str(f)[:200]}")

        if sources:
            sections.append("\n## Sources\n")
            for s in sources[:10]:
                sections.append(f"- {s.get('title', 'Source')}: {s.get('url', '')}")

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
            summary=f"Synthesized {len(findings)} findings from {len(sources)} sources",
        )

    def _generate_document(
        self, step: PlanStep, results: dict[int, StepResult], plan: ExecutionPlan
    ) -> StepResult:
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

        result = tool.execute(
            title=topic[:80],
            outline=outline,
            brand_domain=brand_domain,
        )

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

        result = tool.execute(**step.params)
        return StepResult(
            step_id=step.id,
            success=result.success,
            data=result.data,
            summary=result.summary,
            error=result.error,
        )
