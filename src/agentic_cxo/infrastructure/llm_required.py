"""
LLM Required — explicit failure when LLM is unavailable.

No offline fallbacks. Enterprise-grade AI CXO requires LLM.
Prefers Anthropic Claude (ANTHROPIC_API_KEY) — api.anthropic.com is reachable
in the deployment environment. Falls back to OpenAI if only OPENAI_API_KEY is set.
"""

from __future__ import annotations


class LLMRequiredError(Exception):
    """Raised when an operation requires LLM but no API key is configured."""

    def __init__(self, operation: str, detail: str = "") -> None:
        self.operation = operation
        self.detail = detail
        msg = (
            f"LLM required for {operation}. "
            "Configure ANTHROPIC_API_KEY (preferred) or OPENAI_API_KEY in .env. "
        )
        if detail:
            msg += detail
        super().__init__(msg)


def require_llm(operation: str) -> None:
    """Ensure at least one LLM provider is configured. Raises LLMRequiredError if not."""
    from agentic_cxo.config import settings

    has_anthropic = bool(settings.llm.anthropic_api_key and settings.llm.anthropic_api_key.strip())
    has_openai = bool(settings.llm.api_key and settings.llm.api_key.strip())

    if not has_anthropic and not has_openai:
        raise LLMRequiredError(
            operation,
            "Set ANTHROPIC_API_KEY in .env (recommended) or OPENAI_API_KEY.",
        )
