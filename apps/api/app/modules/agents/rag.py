"""Knowledge ingestion + retrieval.

Ingestion: chunk -> embed via Ollama (`nomic-embed-text`) -> upsert to Qdrant collection `leadex_org_<org hex>`
with payload {org_id, agent_id, knowledge_id, chunk_id}. If Ollama/Qdrant are unavailable chunks are stored with
embedding_status='keyword_only' (still searchable).

Retrieval: vector search with a MANDATORY org_id + agent_id payload filter (and results re-checked against the
tenant's rows in PostgreSQL); otherwise BM25-style keyword scoring over the tenant's chunks. Every result reports
`retrieval_mode` (vector | keyword | none) and citations.
"""
import math
import re
import uuid
from collections import Counter

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agents import llm
from app.modules.agents.config import ai_settings, http_client
from app.modules.agents.models import AgentKnowledge, KnowledgeChunk

_WORD = re.compile(r"[\w']+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def chunk_text(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    """Split on paragraphs, then pack into ~`size`-word windows with `overlap` words of context."""
    words = text.split()
    if not words:
        return []
    chunks, step = [], max(1, size - overlap)
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks


def collection(org_id: uuid.UUID) -> str:
    return f"leadex_org_{org_id.hex}"


def _qdrant_ensure(c: httpx.Client, base: str, name: str, dim: int) -> None:
    r = c.get(f"{base}/collections/{name}", headers=llm.qdrant_headers())
    if r.status_code == 404:
        r = c.put(f"{base}/collections/{name}", headers=llm.qdrant_headers(),
                  json={"vectors": {"size": dim, "distance": "Cosine"}})
    if r.status_code != 200:
        raise httpx.HTTPError(f"qdrant collection {name}: HTTP {r.status_code}")


def ingest(db: Session, doc: AgentKnowledge) -> None:
    """Create chunks for `doc` (already flushed) and try to index them in Qdrant."""
    texts = chunk_text(doc.content)
    chunks = [KnowledgeChunk(organization_id=doc.organization_id, agent_id=doc.agent_id, knowledge_id=doc.id,
                             ordinal=i, text=t, embedding_status="keyword_only") for i, t in enumerate(texts)]
    db.add_all(chunks)
    db.flush()
    doc.chunk_count = len(chunks)
    doc.embedding_status = "keyword_only"
    s = ai_settings()
    if not (chunks and s.ollama_base_url and s.qdrant_url):
        return
    try:
        vectors = [llm.embed(c.text) for c in chunks]
        points = [{"id": str(c.id), "vector": v,
                   "payload": {"org_id": str(doc.organization_id), "agent_id": str(doc.agent_id),
                               "knowledge_id": str(doc.id), "chunk_id": str(c.id)}}
                  for c, v in zip(chunks, vectors, strict=True)]
        name = collection(doc.organization_id)
        with http_client(timeout=15) as c:
            _qdrant_ensure(c, s.qdrant_url, name, len(vectors[0]))
            r = c.put(f"{s.qdrant_url}/collections/{name}/points?wait=true", headers=llm.qdrant_headers(),
                      json={"points": points})
        if r.status_code != 200:
            return
    except (llm.LLMUnavailable, httpx.HTTPError, ValueError):
        return
    for ch in chunks:
        ch.embedding_status, ch.embedding_model = "embedded", s.ollama_embed_model
    doc.embedding_status = "embedded"


def delete_vectors(org_id: uuid.UUID, knowledge_id: uuid.UUID) -> bool:
    """Best-effort removal from Qdrant (PostgreSQL rows are the source of truth)."""
    s = ai_settings()
    if not s.qdrant_url:
        return True
    try:
        with http_client(timeout=10) as c:
            r = c.post(f"{s.qdrant_url}/collections/{collection(org_id)}/points/delete?wait=true",
                       headers=llm.qdrant_headers(),
                       json={"filter": {"must": [{"key": "org_id", "match": {"value": str(org_id)}},
                                                 {"key": "knowledge_id", "match": {"value": str(knowledge_id)}}]}})
        return r.status_code in (200, 404)
    except httpx.HTTPError:
        return False


def _citation(ch: KnowledgeChunk, titles: dict, score: float) -> dict:
    return {"knowledge_id": str(ch.knowledge_id), "chunk_id": str(ch.id), "title": titles.get(ch.knowledge_id, ""),
            "ordinal": ch.ordinal, "score": round(score, 4), "text": ch.text[:400]}


def _vector_search(db, org_id, agent_id, query, k) -> list[tuple[KnowledgeChunk, float]] | None:
    s = ai_settings()
    if not (s.ollama_base_url and s.qdrant_url):
        return None
    try:
        vec = llm.embed(query)
        with http_client(timeout=10) as c:
            r = c.post(f"{s.qdrant_url}/collections/{collection(org_id)}/points/search", headers=llm.qdrant_headers(),
                       json={"vector": vec, "limit": k, "with_payload": True,
                             "filter": {"must": [{"key": "org_id", "match": {"value": str(org_id)}},
                                                 {"key": "agent_id", "match": {"value": str(agent_id)}}]}})
        if r.status_code != 200:
            return None
        hits = r.json().get("result") or []
    except (llm.LLMUnavailable, httpx.HTTPError, ValueError):
        return None
    ids, scores = [], {}
    for h in hits:
        try:
            cid = uuid.UUID(str(h.get("id")))
        except ValueError:
            continue
        ids.append(cid)
        scores[cid] = float(h.get("score") or 0)
    if not ids:
        return []
    # Re-check tenant ownership in PostgreSQL: never trust the vector store alone.
    rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids), KnowledgeChunk.organization_id == org_id,
                                                   KnowledgeChunk.agent_id == agent_id)).all()
    return sorted(((r, scores[r.id]) for r in rows), key=lambda x: -x[1])


def _keyword_search(chunks: list[KnowledgeChunk], query: str, k: int) -> list[tuple[KnowledgeChunk, float]]:
    q = set(tokenize(query))
    if not q or not chunks:
        return []
    docs = [tokenize(c.text) for c in chunks]
    n, avg = len(docs), (sum(len(d) for d in docs) / len(docs)) or 1.0
    df = Counter(t for d in docs for t in set(d))
    k1, b = 1.5, 0.75
    scored = []
    for ch, d in zip(chunks, docs, strict=True):
        tf, score = Counter(d), 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        if score > 0:
            scored.append((ch, score))
    return sorted(scored, key=lambda x: -x[1])[:k]


def retrieve(db: Session, org_id: uuid.UUID, agent_id: uuid.UUID, query: str, k: int = 4) -> tuple[str, list[dict]]:
    chunks = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.organization_id == org_id,
                                                     KnowledgeChunk.agent_id == agent_id)).all()
    if not chunks or not query.strip():
        return "none", []
    titles = dict(db.execute(select(AgentKnowledge.id, AgentKnowledge.title).where(
        AgentKnowledge.organization_id == org_id, AgentKnowledge.agent_id == agent_id)).all())
    hits = None
    if any(c.embedding_status == "embedded" for c in chunks):
        hits = _vector_search(db, org_id, agent_id, query, k)
    mode = "vector"
    if hits is None:
        hits, mode = _keyword_search(list(chunks), query, k), "keyword"
    return mode, [_citation(c, titles, s) for c, s in hits]
