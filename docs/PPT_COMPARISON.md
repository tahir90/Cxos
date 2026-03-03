# Honest Comparison: Our PPT vs Claude's Benchmark

**Date:** 2026-03-03  
**Topic:** Excessive Use of Agentic AI on Human Brain Development  
**Our output:** `presentation_8e034d0a.pptx` (12 slides, ~47KB)

---

## Side-by-Side

| Aspect | Claude's benchmark | Our output |
|--------|-------------------|------------|
| **Title slide** | "Excessive Use of **Agentic AI** on Human Brain Development" — crisp, branded | "professional research presentation on the impact of excessive use of ag..." — **broken/generic title** |
| **Research depth** | MIT Media Lab 2025, Gerlich 2025, Microsoft Research, Doshi & Hauser 2024 — specific studies, years, findings | Generic bullets ("Misalignment with Human Values", "Loss of Control") — **no specific study citations or numbers** |
| **Data/metrics** | 700M+, 77%, 4x, 30%, -34%, -41%, -28% — large callouts | None surfaced in slides |
| **Layout variety** | Definition boxes, metric callouts, bar chart, two-column, comparison table, orange warning, green/red benefits-risks | Agenda, bullets, perspectives, numbered list, sources — **no data_metrics, comparison_table, benefits_risks, warning_callout** |
| **Bar chart** | Global AI User Growth (2020-2025) | Not supported |
| **Cognitive debt** | Dedicated slide with definition + "Before AI / With Agentic AI" table | Not present |
| **Developing brains** | Orange warning banner, age groups 13-17, 18-21 | Not present |
| **Trade-off** | Green benefits ✓ / Red risks ✗ | Not present |
| **Sources** | Cited in-line | 7 real URLs on Sources slide ✓ |

---

## Root causes

1. **Title** — Outline or `_clean_title` produced a generic phrase instead of the topic. The planner/synthesis may have passed a meta-description as the title.

2. **Research → Synthesis gap** — Researcher found real sources (EY, arxiv, MIT Sloan, etc.), but synthesis produced generic bullets. The Methodology Designer / synthesis prompt didn't push for specific studies, numbers, and structure (e.g. "Cognitive Debt", "Before/After AI").

3. **Slide spec** — LLM chose `content_bullets`, `perspectives`, `recommendations` instead of `data_metrics`, `comparison_table`, `benefits_risks`, `warning_callout`. Outline lacked the structured content (metrics, pros/cons, comparison rows) those layouts expect.

4. **Charts** — We have no bar-chart support in the PPT generator.

---

## Verdict

**Our output is not at Claude's level.** Main gaps:

- Title is wrong/generic
- Research synthesis is too generic; specific studies and numbers don’t flow into slides
- Rich layouts (metrics, comparison, benefits/risks, warning) are not being selected or used
- No chart support

Fixes would need to target: synthesis prompts, methodology briefs, slide_spec prompting, and chart support.
