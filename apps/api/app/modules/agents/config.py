"""AI infrastructure settings (Ollama, Qdrant). Read fresh on every call so tests/ops can change env at runtime."""
from contextvars import ContextVar

import httpx
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    # OLLAMA_BASE_URL is canonical; legacy OLLAMA_URL is accepted as a fallback.
    ollama_base_url: str | None = Field(default=None, validation_alias=AliasChoices("OLLAMA_BASE_URL", "OLLAMA_URL"))
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    ai_http_timeout_s: float = 30.0
    voice_kill_switch: bool = False  # global kill switch for all calls
    # Optional fast OpenAI-compatible endpoint (Groq, OpenRouter, Together, vLLM on a GPU, ...). Opt-in, paid.
    # Live phone calls need ~1-2 s replies, which a CPU-only Ollama cannot deliver.
    fast_llm_base_url: str | None = None  # e.g. https://api.groq.com/openai/v1
    fast_llm_api_key: str | None = None
    fast_llm_model: str | None = None

    @field_validator("ollama_base_url", "qdrant_url", "qdrant_api_key", "fast_llm_base_url", "fast_llm_api_key",
                     "fast_llm_model", mode="before")
    @classmethod
    def empty_is_none(cls, v):
        return (v or "").strip().rstrip("/") or None


def ai_settings() -> AISettings:
    return AISettings()


# Tests inject an httpx.MockTransport here; production leaves it None (real network).
http_transport: httpx.BaseTransport | None = None


# Per-call latency budget override (e.g. live phone turns cap LLM calls at a few seconds). Callers set it with
# `timeout_budget.set(...)` and reset the token afterwards; it never lengthens an explicitly shorter timeout.
timeout_budget: ContextVar[float | None] = ContextVar("ai_timeout_budget", default=None)


def http_client(timeout: float | None = None) -> httpx.Client:
    t = timeout or ai_settings().ai_http_timeout_s
    budget = timeout_budget.get()
    if budget is not None:
        t = min(t, budget)
    return httpx.Client(transport=http_transport, timeout=t)
