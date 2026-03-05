#!/usr/bin/env python3
"""
Direct PPT generation test — GMG branding, AI & Human Brain topic.

Tests the full PPT generation pipeline with a rich research outline
that simulates what the LLM researcher would produce.
Run from project root: python3 scripts/test_ppt_gmg.py
"""

from __future__ import annotations
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    print("=" * 65)
    print("  GMG PPT Generation Test")
    print("  Topic: Impact of Excessive Use of Agentic AI on Human Brain")
    print("=" * 65)

    from agentic_cxo.agents.creative_director import CreativeDirectorAgent
    from agentic_cxo.tools.presentation_generator import (
        PresentationGeneratorTool,
        set_creative_director,
    )

    # ── 1. Initialize Creative Director ─────────────────────────────
    print("\n[1/4] Initializing Creative Director...")
    cd = CreativeDirectorAgent()
    set_creative_director(cd)
    print("      Creative Director ready.")

    # ── 2. Simulate brand lookup for gmg.com ────────────────────────
    print("\n[2/4] Configuring GMG brand...")
    try:
        from agentic_cxo.tools.brand_intelligence import BrandStore, BrandProfile
        store = BrandStore()
        # Set a professional dark brand for GMG
        gmg_brand = BrandProfile(
            domain="gmg.com",
            company_name="GMG",
            primary_color="#1a1a2e",     # Deep navy
            secondary_color="#e94560",   # Red accent
            heading_font="Calibri",
            body_font="Calibri",
        )
        store.store(gmg_brand)
        print("      GMG brand profile saved.")
    except Exception as e:
        print(f"      Brand setup warning: {e}")

    # ── 3. Rich Research Outline ─────────────────────────────────────
    print("\n[3/4] Preparing research outline...")
    RESEARCH_OUTLINE = """
## Executive Summary: The Agentic AI Brain Crisis

Agentic AI is transforming productivity at unprecedented scale — 700M+ active users,
77% workforce adoption, $15.7B market in 2025 growing 50% annually. But beneath the
efficiency gains lies a silent cognitive revolution. MIT Media Lab (2025) found that
heavy AI users show 34% decline in analytical reasoning, 25% reduction in independent
decision-making, and 48% decrease in sustained deep focus. The human brain, shaped by
200,000 years of challenge-driven neuroplasticity, is being systematically under-stimulated
by AI delegation — creating measurable cognitive atrophy in key executive function regions.

## Agentic AI Global Market Scale

- 700M+ monthly active users across major agentic AI platforms (OpenAI, 2025)
- 77% of knowledge workers use AI tools weekly — highest adoption in history
- 4x productivity gains reported in AI-assisted complex task completion
- 30% of workers aged 18-25 began careers with AI as primary cognitive assistant
- $15.7 billion global agentic AI market in 2025, projected $72B by 2030
- 50% year-over-year market growth outpacing all prior technology adoption curves
- 4.2x ROI reported by enterprises implementing full agentic AI workflows

## How Agentic AI Reshapes the Brain

- Prefrontal Cortex: Reduced activation during AI-assisted decision tasks; fMRI studies show
  40% less neural engagement when AI provides recommendations vs. independent problem-solving
- Hippocampus: Episodic and spatial memory consolidation declines 22% with heavy AI navigation
  dependency (UCL Navigation Study, 2024) — equivalent to 10 years of aging acceleration
- Default Mode Network: Suppressed during extended AI interaction, reducing mind-wandering
  that is critical for creativity, insight, and long-term goal planning
- Anterior Cingulate Cortex: Cognitive effort monitoring reduced when AI handles task routing,
  weakening the brain's ability to self-regulate attention and effort allocation
- Mirror Neuron Systems: Social cognition and empathy pathways show reduced activation in
  heavy AI communication users — 18% decline in emotional recognition accuracy
- Reward Plasticity Risk: Dopaminergic pathways recalibrated to expect AI-mediated gratification,
  reducing tolerance for necessary cognitive struggle and delayed reward

## MIT Media Lab Study 2025 — Key Findings

- Study Design: 500 participants, 6-month longitudinal, randomized into high-AI, moderate-AI,
  and AI-free cognitive task groups
- Critical thinking assessment scores: High-AI group declined 28 points vs. 2-point gain
  in AI-free group over 6 months
- Task independence: High-AI users required AI assistance for 67% of tasks they previously
  solved independently at study start
- Learning transfer: High-AI group showed 41% lower retention of learned skills when AI
  tools were removed — "cognitive scaffolding dependency"
- Creativity metrics (divergent thinking tests): High-AI group 31% lower than control
- Quote from lead researcher: "We are not just outsourcing tasks — we are outsourcing
  the very cognitive processes that build and maintain neural architecture"

## The Hidden Cost: Cognitive Debt

Cognitive debt is the accumulating deficit of mental capability caused by chronic AI delegation.
Like financial debt, it compounds silently until a tipping point.

- BUILD: Accepting AI recommendations without analysis weakens prefrontal decision circuits;
  each accepted recommendation without evaluation reduces independent decision confidence 3-7%
- AVOID: Delegating research and information synthesis erodes pattern recognition;
  the hippocampus requires challenge to maintain its indexing and retrieval functions
- REPLACE: Using AI for complex analysis prevents development of systems thinking;
  neural pathways for multi-variable reasoning require regular activation to maintain

## The Evidence: Critical Thinking in Decline

- 34% decline in analytical reasoning scores among heavy AI users (MIT Media Lab, 2025)
- 25% reduction in independent decision-making confidence after 6 months AI dependency
- 48% decrease in sustained deep focus capacity (measured by distraction-free work sessions)
- 31% lower creative output (divergent thinking) in high-AI groups vs. control
- 28% faster task completion — but 41% lower skill retention without AI present
- 19% increase in decision errors when AI tools temporarily unavailable in high-dependency users
- Stanford confirmation: students using AI for homework show 35% lower conceptual understanding

## The Most Vulnerable: Developing Brains

- Ages 0-7: Critical period for foundational cognitive architecture; AI exposure during
  language acquisition may alter prefrontal-hippocampal connectivity pathways permanently
- Ages 8-14: Executive function development peak; over-reliance on AI task assistance
  during this window risks underdeveloped anterior cingulate cortex (impulse control center)
- Ages 15-25: Neuroplasticity highest — also highest risk period; 62% of this age group
  use AI daily; professional habits formed now will persist for entire career
- University students using AI for academic work show 35% lower concept retention vs.
  those engaging deeply with material (Stanford Learning Lab, 2024)
- Early career AI dependency creates "cognitive glass ceiling" — workers capable of
  directing AI but unable to independently validate or innovate beyond AI outputs

## The Trade-Off: Efficiency vs Cognition

Benefits of Agentic AI:
- Productivity increases up to 40% in routine knowledge work tasks
- Access to vast information synthesis in seconds vs. hours of research
- Democratization of expertise — junior workers with AI match senior productivity
- Reduced cognitive load for repetitive tasks frees capacity for strategic thinking
- Error reduction in rule-based tasks by 60-80% with AI verification

Cognitive Risks of Excessive Agentic AI:
- Critical thinking decline 34% in heavy users (MIT, 2025)
- Independent decision-making confidence reduced 25% after 6 months dependency
- Deep focus capacity down 48% — attention span fragmentation documented
- Skill atrophy: 41% lower performance when AI tools unavailable
- Innovation pipeline risk: AI generates incremental solutions, not breakthrough insights
- Workforce strategic thinking gap: organizations over-dependent on AI lose competitive
  edge when AI tools fail, are disrupted, or when novel situations exceed AI training

## Strategic Recommendations for GMG

1. Implement "Cognitive Hygiene" Policy: Mandate AI-free problem-solving periods for
   all knowledge workers — minimum 2 hours daily of unassisted deep work to maintain
   neural pathway activation in executive function regions

2. AI Usage Monitoring & Calibration: Deploy analytics to track AI dependency ratios
   per employee; intervene when individual dependency exceeds 70% for core tasks
   (red zone for cognitive atrophy risk)

3. Education Program: Launch "AI Literacy + Cognitive Resilience" training covering
   neuroscience of AI dependency, personal cognitive monitoring, and optimal AI integration
   strategies — target completion within Q1 for all knowledge workers

4. Develop Cognitive Agility Assessments: Quarterly testing of analytical reasoning,
   creative problem-solving, and independent decision-making separate from AI-assisted work
   to detect early cognitive decline signals

5. Design AI-Augmented Not AI-Replaced Workflows: Audit all workflows to ensure humans
   retain understanding of underlying processes; AI handles execution, humans maintain
   strategic oversight and conceptual mastery

## Neuroscience of Responsible AI Integration

- Optimal balance: 60-70% AI assistance for execution, 100% human ownership of strategy
  and judgment — preserves neural pathways for high-order thinking
- "Cognitive sparring" practice: Deliberately solve problems without AI first, then
  compare to AI solution — maintains independent reasoning while leveraging AI insights
- Learning phases: AI should be withheld during initial learning to allow schema formation
  before being introduced as efficiency accelerator — prevents dependency formation
- Regular "digital detox" periods restore baseline cognitive function; 48-hour AI-free
  periods show measurable improvement in analytical reasoning (Yale Mind Studies, 2024)
- Organizations with structured AI governance show 3x better retention of critical thinking
  skills vs. organizations with unstructured AI access (McKinsey Future of Work, 2025)

## Sources & Research Foundation

- MIT Media Lab (2025): "Cognitive Impact of Sustained AI Delegation" — 6-month longitudinal
- Stanford Learning Lab (2024): "AI Tools and Academic Skill Retention"
- UCL Navigation Study (2024): "GPS/AI Navigation and Hippocampal Volume"
- McKinsey Global Institute (2025): "Future of Work: AI Adoption and Skill Transformation"
- Yale Mind Studies (2024): "Digital Detox and Cognitive Recovery"
- Journal of Neuroscience (2024): "Neuroplasticity Under Reduced Cognitive Demand Conditions"
- World Economic Forum (2025): "AI Skills Gap and Cognitive Workforce Readiness"
- OpenAI Usage Report (2025): "Global Agentic AI Adoption Statistics"
"""

    # ── 4. Generate PPT ──────────────────────────────────────────────
    print("\n[4/4] Generating presentation...")
    tool = PresentationGeneratorTool()

    progress_log = []
    def progress_callback(msg):
        progress_log.append(msg)
        print(f"      > {msg}")

    result = tool.execute(
        title="Impact of Excessive Use of Agentic AI on Human Brain",
        outline=RESEARCH_OUTLINE.strip(),
        brand_domain="gmg.com",
        document_type="presentation",
        subtitle="Research-Informed Analysis with Strategic Recommendations for GMG",
        progress_callback=progress_callback,
    )

    # ── 5. Results ───────────────────────────────────────────────────
    print("\n" + "=" * 65)
    if result.success:
        print("  ✓ PPT GENERATION SUCCESSFUL")
        print("=" * 65)
        from pathlib import Path
        pptx_path = result.data.get("path", "")
        url = result.data.get("url", "")
        slides = result.data.get("slides_count", 0)
        brand = result.data.get("brand_used", "default")
        doc_type = result.data.get("document_type", "presentation")

        print(f"\n  Title      : {result.data.get('title')}")
        print(f"  Slides     : {slides}")
        print(f"  Brand      : {brand}")
        print(f"  Doc Type   : {doc_type}")
        print(f"  File Path  : {pptx_path}")
        print(f"  Static URL : {url}")

        if pptx_path:
            p = Path(pptx_path)
            if p.exists():
                size_kb = p.stat().st_size / 1024
                print(f"  File Size  : {size_kb:.1f} KB")
                print(f"\n  ✓ File verified at: {p.resolve()}")
            else:
                print(f"\n  ✗ WARNING: File not found at {pptx_path}")

        print(f"\n  Download URL: {url}")
        print("\n  Summary preview:")
        print("  " + result.summary[:300].replace("\n", "\n  "))
    else:
        print("  ✗ PPT GENERATION FAILED")
        print("=" * 65)
        print(f"  Error: {result.error}")
        return 1

    print("\n" + "=" * 65)
    print("  Test complete. Inspect the .pptx file to verify quality.")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
