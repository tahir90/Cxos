"""Central configuration for the Agentic CXO system."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

# Production mode: stricter validation
IS_PRODUCTION = os.getenv("CXO_ENV", "development").lower() in ("production", "prod", "1")


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    vision_model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))


@dataclass
class SearchConfig:
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))


@dataclass
class PPQAConfig:
    max_qa_cycles: int = 3
    slides_per_vision_batch: int = 4


@dataclass
class QualityConfig:
    max_validation_rounds: int = 3
    use_methodology_designer: bool = True
    use_methodology_auditor: bool = True
    use_review_agent: bool = True


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
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("CXO_JWT_SECRET", "cxo-secret-change-in-production-use-env-var")
    )
    admin_email: str = field(default_factory=lambda: os.getenv("CXO_ADMIN_EMAIL", "admin@cxo.ai"))
    admin_password: str = field(default_factory=lambda: os.getenv("CXO_ADMIN_PASSWORD", "admin123"))
    admin_name: str = field(default_factory=lambda: os.getenv("CXO_ADMIN_NAME", "Admin"))
    token_expire_hours: int = field(
        default_factory=lambda: int(os.getenv("CXO_TOKEN_EXPIRE_HOURS", "72"))
    )
    encryption_key: str = field(default_factory=lambda: os.getenv("CXO_ENCRYPTION_KEY", ""))


@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    ppqa: PPQAConfig = field(default_factory=PPQAConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


settings = Settings()


def validate_production_config() -> None:
    """Validate config at startup; exit if production is misconfigured."""
    if not IS_PRODUCTION:
        return
    secret = settings.auth.jwt_secret
    if not secret or secret in ("cxo-secret-change-in-production-use-env-var", "secret", "change-me"):
        print("FATAL: Set CXO_JWT_SECRET to a strong random value (e.g. openssl rand -hex 32)")
        sys.exit(1)
    admin_pass = settings.auth.admin_password
    if admin_pass in ("admin123", "password", "changeme", "123456"):
        print("FATAL: Set CXO_ADMIN_PASSWORD to a strong password")
        sys.exit(1)
