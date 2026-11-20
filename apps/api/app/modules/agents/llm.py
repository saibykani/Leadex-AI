"""LLM provider adapters (REST via httpx; no vendor SDK).

- `ollama`    -> POST {base}/api/chat (stream=false). Unreachable => LLMUnavailable (never a fabricated reply).
- `openai`    -> POST {FAST_LLM_BASE_URL}/chat/completions (any OpenAI-compatible server). Opt-in; used for live
                 calls when configured because replies must arrive within ~2 s.
- `simulated` -> deterministic template text, always labelled simulated=True. It is NOT a language model.
"""
import time
from dataclasses import dataclass, field

import httpx

from app.modules.agents.config import ai_settings, http_client

PROVIDERS = ("ollama", "openai", "simulated")


class LLMUnavailable(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status, self.message = status, message  # status: not_configured | unreachable | error


@dataclass
class ModelSpec:
    provider: str = "simulated"
    model: str = "template"
    temperature: float = 0.3
    max_tokens: int = 512
    base_url: str | None = None


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    simulated: bool
    latency_ms: int
    tool_calls: list[dict] = field(default_factory=list)  # [{name, arguments}]


def ollama_base(spec: ModelSpec | None = None) -> str | None:
    return (spec.base_url if spec and spec.base_url else None) or ai_settings().ollama_base_url


def chat(spec: ModelSpec, messages: list[dict], tools: list[dict] | None = None, *,
         simulated_text: str = "") -> ChatResult:
    t0 = time.perf_counter()
    if spec.provider == "simulated":
        return ChatResult(simulated_text, "simulated", "template", True, int((time.perf_counter() - t0) * 1000))
    if spec.provider == "openai":
        return _openai_chat(spec, messages, tools, t0)
    if spec.provider != "ollama":
        raise LLMUnavailable("not_configured", f"Unknown provider '{spec.provider}'")
    base = ollama_base(spec)
    if not base:
        raise LLMUnavailable("not_configured", "OLLAMA_BASE_URL is not configured")
    payload: dict = {"model": spec.model, "messages": messages, "stream": False,
                     "options": {"temperature": spec.temperature, "num_predict": spec.max_tokens}}
    if tools:
        payload["tools"] = tools
    try:
        with http_client() as c:
            r = c.post(f"{base}/api/chat", json=payload)
    except httpx.HTTPError as e:
        raise LLMUnavailable("unreachable", f"Ollama unreachable at {base}: {type(e).__name__}") from e
    if r.status_code != 200:
        raise LLMUnavailable("error", f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        msg = r.json().get("message") or {}
    except ValueError as e:
        raise LLMUnavailable("error", "Ollama returned invalid JSON") from e
    calls = [{"name": (tc.get("function") or {}).get("name"), "arguments": (tc.get("function") or {}).get("arguments")}
             for tc in msg.get("tool_calls") or []]
    return ChatResult(msg.get("content") or "", "ollama", spec.model, False,
                      int((time.perf_counter() - t0) * 1000), calls)


def fast_configured() -> bool:
    s = ai_settings()
    return bool(s.fast_llm_base_url and s.fast_llm_model)


def fast_spec(temperature: float = 0.4, max_tokens: int = 160) -> ModelSpec | None:
    s = ai_settings()
    if not fast_configured():
        return None
    return ModelSpec("openai", s.fast_llm_model, temperature, max_tokens, s.fast_llm_base_url)


def _openai_chat(spec: ModelSpec, messages: list[dict], tools: list[dict] | None, t0: float) -> ChatResult:
    s = ai_settings()
    base = spec.base_url or s.fast_llm_base_url
    if not base:
        raise LLMUnavailable("not_configured", "FAST_LLM_BASE_URL is not configured")
    payload: dict = {"model": spec.model, "messages": messages, "temperature": spec.temperature,
                     "max_tokens": spec.max_tokens}
    if tools:
        payload["tools"] = tools
    headers = {"Authorization": f"Bearer {s.fast_llm_api_key}"} if s.fast_llm_api_key else {}
    try:
        with http_client() as c:
            r = c.post(f"{base}/chat/completions", json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise LLMUnavailable("unreachable", f"LLM endpoint unreachable: {type(e).__name__}") from e
    if r.status_code != 200:
        raise LLMUnavailable("error", f"LLM endpoint returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        msg = (r.json().get("choices") or [{}])[0].get("message") or {}
    except (ValueError, AttributeError) as e:
        raise LLMUnavailable("error", "LLM endpoint returned invalid JSON") from e
    calls = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            import json

            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        calls.append({"name": fn.get("name"), "arguments": args})
    ms = int((time.perf_counter() - t0) * 1000)
    return ChatResult(msg.get("content") or "", "openai", spec.model, False, ms, calls)


def embed(text: str) -> list[float]:
    s = ai_settings()
    if not s.ollama_base_url:
        raise LLMUnavailable("not_configured", "OLLAMA_BASE_URL is not configured")
    try:
        with http_client(timeout=15) as c:
            r = c.post(f"{s.ollama_base_url}/api/embeddings", json={"model": s.ollama_embed_model, "prompt": text})
        vec = r.json().get("embedding") if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError) as e:
        raise LLMUnavailable("unreachable", f"Embedding failed: {type(e).__name__}") from e
    if not vec:
        raise LLMUnavailable("error", f"Embedding failed (HTTP {r.status_code})")
    return vec


def _probe(url: str, headers: dict | None = None) -> tuple[str, dict]:
    try:
        with http_client(timeout=3) as c:
            r = c.get(url, headers=headers or {})
        if r.status_code == 200:
            return "available", r.json()
        return "error", {"http_status": r.status_code}
    except (httpx.HTTPError, ValueError) as e:
        return "unreachable", {"error": type(e).__name__}


def provider_status() -> list[dict]:
    s = ai_settings()
    out = []
    if s.ollama_base_url:
        st, body = _probe(f"{s.ollama_base_url}/api/tags")
        models = [m.get("name") for m in body.get("models", [])] if st == "available" else []
        out.append({"provider": "ollama", "kind": "llm+embeddings", "status": st, "url": s.ollama_base_url,
                    "models": models, "chat_model": s.ollama_chat_model, "embed_model": s.ollama_embed_model,
                    "simulated": False, "detail": None if st == "available" else body})
    else:
        out.append({"provider": "ollama", "kind": "llm+embeddings", "status": "not_configured", "url": None,
                    "models": [], "simulated": False, "detail": "Set OLLAMA_BASE_URL"})
    if s.qdrant_url:
        st, body = _probe(f"{s.qdrant_url}/collections", qdrant_headers())
        out.append({"provider": "qdrant", "kind": "vector_store", "status": st, "url": s.qdrant_url,
                    "simulated": False, "detail": None if st == "available" else body})
    else:
        out.append({"provider": "qdrant", "kind": "vector_store", "status": "not_configured", "url": None,
                    "simulated": False, "detail": "Set QDRANT_URL; retrieval falls back to keyword search"})
    if fast_configured():
        out.append({"provider": "openai", "kind": "llm (fast, OpenAI-compatible)", "status": "configured",
                    "url": s.fast_llm_base_url, "models": [s.fast_llm_model], "simulated": False,
                    "detail": "Used for live phone calls"})
    else:
        out.append({"provider": "openai", "kind": "llm (fast, OpenAI-compatible)", "status": "not_configured",
                    "url": None, "models": [], "simulated": False,
                    "detail": "Optional. Set FAST_LLM_BASE_URL, FAST_LLM_API_KEY and FAST_LLM_MODEL "
                              "for real-time calls"})
    out.append({"provider": "simulated", "kind": "llm", "status": "available", "url": None, "simulated": True,
                "detail": "Deterministic template responses for testing; not an AI model."})
    return out


def qdrant_headers() -> dict:
    key = ai_settings().qdrant_api_key
    return {"api-key": key} if key else {}
