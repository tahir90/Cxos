#!/usr/bin/env python3
"""End-to-end PPT generation test — same topic as Claude benchmark."""

import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def main():
    from agentic_cxo.config import settings
    from agentic_cxo.tools.planner import PlannerTool
    from agentic_cxo.tools.plan_executor import PlanExecutor
    from agentic_cxo.tools.framework import ToolRegistry
    from agentic_cxo.tools.researcher import ResearcherTool
    from agentic_cxo.tools.presentation_generator import PresentationGeneratorTool

    if not settings.llm.api_key or settings.llm.api_key == "sk-test-dummy-key-for-unit-tests":
        print("SKIP: Set OPENAI_API_KEY for live test")
        return 0

    prompt = (
        "Create a professional research presentation on: "
        "Excessive Use of Agentic AI on Human Brain Development. "
        "Include cognitive risks, neuroscience findings, and strategic recommendations. "
        "Use data, studies, and a dark professional theme."
    )

    print("Planning...")
    planner = PlannerTool(use_llm=True)
    plan = planner.create_plan(message=prompt)
    if not plan.steps:
        print("No plan steps (may need planning)")
        return 1

    print(f"Plan: {len(plan.steps)} steps")
    for s in plan.steps:
        print(f"  - {s.action} {s.agent or s.tool or ''}")

    registry = ToolRegistry()
    registry.register(ResearcherTool())
    registry.register(PresentationGeneratorTool())
    executor = PlanExecutor(tool_registry=registry)
    for ev in executor.execute_plan(plan):
        if ev.get("type") == "step_progress":
            print("  ", ev.get("message", ""))
        elif ev.get("type") == "step_complete":
            print("Step done:", ev.get("step_id"), ev.get("success"))
        elif ev.get("type") == "document_ready":
            print("\nDOCUMENT READY:", ev.get("url"), ev.get("path"))
            path = ev.get("path")
            if path:
                from pathlib import Path
                p = Path(path)
                if p.exists():
                    print(f"Output: {p.resolve()} ({p.stat().st_size} bytes)")
                    return 0

    print("No document generated")
    return 1


if __name__ == "__main__":
    sys.exit(main())
