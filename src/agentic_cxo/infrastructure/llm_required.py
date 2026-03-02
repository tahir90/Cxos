"""
LLM Required — explicit failure when LLM is unavailable.

No offline fallbacks. Enterprise-grade AI CXO requires LLM.
When OPENAI_API_KEY is missing or LLM call fails, we raise clearly.
"""

from __future__ import annotations


class LLMRequiredError(Exception):
    """Raised when an operation requires LLM but it is not available."""

    def __init__(self, operation: str, detail: str = "") -> None:
        self.operation = operation
        self.detail = detail
        msg = (
            f"LLM required for {operation}. "
            "Configure OPENAI_API_KEY for full AI CXO capabilities. "
        )
        if detail:
            msg += detail
        super().__init__(msg)


def require_llm(operation: str) -> None:
    """Ensure LLM (OpenAI API) is configured. Raises LLMRequiredError if not."""
    from agentic_cxo.config import settings

    if not settings.llm.api_key or not settings.llm.api_key.strip():
        raise LLMRequiredError(
            operation,
            "OPENAI_API_KEY is not set.",
        )
