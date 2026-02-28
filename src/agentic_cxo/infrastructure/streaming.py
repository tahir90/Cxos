"""
Streaming LLM responses — token-by-token like ChatGPT.

Instead of waiting 10-20 seconds for the full response,
tokens stream to the browser via Server-Sent Events (SSE).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)


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

        yield _sse({"role": agent_role, "start": True})

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield _sse({"token": delta.content, "role": agent_role})

        yield _sse({"role": agent_role, "done": True})

    except Exception as e:
        logger.error("Streaming failed: %s", e)
        yield _sse({"token": f"Error: {e}", "role": agent_role, "done": True})


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"
