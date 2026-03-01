"""
Tool-Use Framework — lets CXO agents call external tools.

Like JARVIS: the agent decides what information it needs,
calls the right tool, gets results, and reasons about them.

Architecture:
  1. Tools register themselves with a schema (name, description, params)
  2. The LLM sees available tools and decides which to call
  3. The framework executes the tool and returns results
  4. The LLM incorporates results into its response

This uses OpenAI's function-calling API when available,
and falls back to keyword-based tool selection offline.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolParam:
    """A parameter that a tool accepts."""

    name: str
    description: str
    param_type: str = "string"
    required: bool = True


@dataclass
class ToolResult:
    """Result of executing a tool."""

    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class BaseTool(ABC):
    """Base class for all tools the agent can use."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """What this tool does (shown to LLM)."""

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParam]:
        """Parameters the tool accepts."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool and return results."""

    @property
    def trigger_keywords(self) -> list[str]:
        """Keywords that suggest this tool should be used (for offline mode)."""
        return []

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling schema."""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {
                "type": p.param_type,
                "description": p.description,
            }
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def openai_functions(self) -> list[dict[str, Any]]:
        return [t.to_openai_function() for t in self._tools.values()]

    def match_by_keywords(self, text: str) -> list[BaseTool]:
        """Find tools whose trigger keywords appear in the text."""
        text_lower = text.lower()
        matched: list[BaseTool] = []
        for tool in self._tools.values():
            if any(kw in text_lower for kw in tool.trigger_keywords):
                matched.append(tool)
        return matched


class ToolExecutor:
    """
    Executes tools based on LLM decisions or keyword matching.

    With LLM: uses function-calling to decide which tool to invoke.
    Without: matches keywords to suggest tools.
    """

    def __init__(
        self, registry: ToolRegistry, use_llm: bool = False
    ) -> None:
        self.registry = registry
        self.use_llm = use_llm

    def decide_and_execute(
        self,
        message: str,
        context: str = "",
        *,
        on_tool_start=None,
        on_tool_end=None,
    ) -> list[ToolResult]:
        """Decide which tools to use and execute them.
        Optionally call on_tool_start(tool_name, args) and on_tool_end(tool_name, result).
        """
        if self.use_llm and settings.llm.api_key:
            try:
                return self._llm_execute(
                    message, context,
                    on_tool_start=on_tool_start,
                    on_tool_end=on_tool_end,
                )
            except Exception:
                logger.warning("LLM tool execution failed, using keyword fallback",
                               exc_info=True)
        return self._keyword_execute(
            message,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

    def _llm_execute(
        self,
        message: str,
        context: str,
        *,
        on_tool_start=None,
        on_tool_end=None,
    ) -> list[ToolResult]:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.llm.api_key, base_url=settings.llm.base_url
        )
        functions = self.registry.openai_functions()
        if not functions:
            return []

        system_content = (
            "You are an AI assistant with access to external tools. "
            "BE PROACTIVE: when the user asks for a presentation, deck, or slides "
            "on a topic, ALWAYS use the researcher tool first to gather content, "
            "then use presentation_generator with that research as the outline. "
            "Never ask 'would you like me to research?' - just do it. "
            "NEVER say 'connect your presentation tool' or 'connect a search API' - "
            "researcher and presentation_generator are BUILT-IN and work immediately. "
            "Decide which tool(s) to call based on the user's request. "
            "If no tool is needed, respond normally."
            f"\n\nBusiness context: {context[:300]}"
        )

        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.0,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": message},
            ],
            tools=functions,
            tool_choice="auto",
        )

        results: list[ToolResult] = []
        choice = resp.choices[0]

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool = self.registry.get(tc.function.name)
                if tool:
                    try:
                        args = json.loads(tc.function.arguments)
                        if on_tool_start:
                            on_tool_start(tc.function.name, args)
                        result = tool.execute(**args)
                        results.append(result)
                        if on_tool_end:
                            on_tool_end(tc.function.name, result)
                    except Exception as e:
                        result = ToolResult(
                            tool_name=tc.function.name,
                            success=False,
                            error=str(e),
                        )
                        results.append(result)
                        if on_tool_end:
                            on_tool_end(tc.function.name, result)

        return results

    def _keyword_execute(
        self,
        message: str,
        *,
        on_tool_start=None,
        on_tool_end=None,
    ) -> list[ToolResult]:
        """Offline fallback: match tools by keywords."""
        matched = self.registry.match_by_keywords(message)
        results: list[ToolResult] = []

        for tool in matched[:3]:
            kwargs = self._extract_params(message, tool)
            try:
                if on_tool_start:
                    on_tool_start(tool.name, kwargs)
                result = tool.execute(**kwargs)
                results.append(result)
                if on_tool_end:
                    on_tool_end(tool.name, result)
            except Exception as e:
                result = ToolResult(
                    tool_name=tool.name,
                    success=False,
                    error=str(e),
                )
                results.append(result)
                if on_tool_end:
                    on_tool_end(tool.name, result)

        return results

    @staticmethod
    def _extract_params(message: str, tool: BaseTool) -> dict[str, Any]:
        """Best-effort parameter extraction from natural language."""
        kwargs: dict[str, Any] = {}
        for param in tool.parameters:
            if param.required:
                kwargs[param.name] = message[:200]
        return kwargs
