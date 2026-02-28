"""Central configuration for the Agentic CXO system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))


@dataclass
class ChunkingConfig:
    max_chunk_tokens: int = 512
    overlap_tokens: int = 64
    similarity_threshold: float = 0.5


@dataclass
class MemoryConfig:
    collection_name: str = "context_vault"
    persist_directory: str = ".vault"
    top_k: int = 5


@dataclass
class GuardrailConfig:
    require_human_approval_above_risk: float = 0.7
    max_autonomous_actions: int = 10
    budget_limit_usd: float = 10_000.0
    prohibited_actions: list[str] = field(
        default_factory=lambda: [
            "terminate_employee",
            "sign_contract_above_limit",
            "transfer_funds_above_limit",
        ]
    )


@dataclass
class AuthConfig:
    admin_password: str = field(
        default_factory=lambda: os.getenv("CXO_ADMIN_PASSWORD", "")
    )
    jwt_secret: str = field(
        default_factory=lambda: os.getenv(
            "CXO_JWT_SECRET", "cxo-secret-change-in-production-use-env-var"
        )
    )


@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


settings = Settings()
