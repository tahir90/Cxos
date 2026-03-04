"""
Streaming LLM responses — token-by-token like ChatGPT.

Instead of waiting 10-20 seconds for the full response,
tokens stream to the browser via Server-Sent Events (SSE).

Supports CXO activity events so the UI can show which
C-Suite officer is working on what in real-time.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

# CXO role display metadata for streaming UI
CXO_STREAM_META: dict[str, dict[str, str]] = {
    "CFO": {"icon": "\U0001f4b0", "label": "Chief Financial Officer", "color": "#22c55e"},
    "COO": {"icon": "\u2699\ufe0f", "label": "Chief Operating Officer", "color": "#3b82f6"},
    "CMO": {"icon": "\U0001f4c8", "label": "Chief Marketing Officer", "color": "#8b5cf6"},
    "CLO": {"icon": "\u2696\ufe0f", "label": "Chief Legal Officer", "color": "#f59e0b"},
    "CHRO": {"icon": "\U0001f465", "label": "Chief Human Resources Officer", "color": "#ec4899"},
    "CSO": {"icon": "\U0001f4bc", "label": "Chief Sales Officer", "color": "#06b6d4"},
    "Co-Founder": {"icon": "\U0001f9e0", "label": "AI Co-Founder", "color": "#6366f1"},
    "CD": {"icon": "\U0001f3a8", "label": "Creative Director", "color": "#f97316"},
}


async def stream_chat_response(
    system_prompt: str,
    user_message: str,
    agent_role: str = "agent",
) -> AsyncIterator[str]:
    """
    Stream an LLM response token by token.

    Yields SSE-formatted strings: data: {"token": "...", "role": "..."}\n\n
    """
    if not settings.llm.api_key:
        yield _sse({
            "token": "LLM not configured. Set OPENAI_API_KEY.",
            "role": agent_role, "done": True,
        })
        return

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
        )

        # Enrich the role metadata for the UI
        meta = CXO_STREAM_META.get(agent_role, {})

        stream = await client.chat.completions.create(
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )

        yield _sse({
            "role": agent_role,
            "start": True,
            "agent_meta": meta,
        })

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield _sse({"token": delta.content, "role": agent_role})

        yield _sse({"role": agent_role, "done": True})

    except Exception as e:
        logger.error("Streaming failed: %s", e)
        yield _sse({"token": f"Error: {e}", "role": agent_role, "done": True})


async def stream_cxo_events(events: list[dict[str, Any]]) -> AsyncIterator[str]:
    """Stream CXO orchestration events as SSE.

    Event types supported:
    - cxo_start: A CXO agent has started analyzing
    - cxo_progress: Progress update from a CXO
    - cxo_complete: A CXO finished their analysis
    - cxo_cross_consult: One CXO is consulting another
    - orchestration_start: Multi-CXO orchestration began
    - orchestration_complete: All CXOs finished
    - synthesis_start: Co-founder is synthesizing
    - synthesis_complete: Synthesis done
    """
    for event in events:
        event_type = event.get("type", "status")
        agent = event.get("agent", "")

        # Enrich with display metadata
        if agent and agent in CXO_STREAM_META:
            event["agent_meta"] = CXO_STREAM_META[agent]

        yield _sse(event)


def format_cxo_activity(agent_role: str, activity: str) -> dict[str, Any]:
    """Create a standardized CXO activity event for streaming."""
    meta = CXO_STREAM_META.get(agent_role, {})
    icon = meta.get("icon", "")
    label = meta.get("label", agent_role)
    return {
        "type": "cxo_activity",
        "agent": agent_role,
        "agent_meta": meta,
        "message": f"{icon} {label}: {activity}",
    }


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"
