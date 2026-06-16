"""
rag/retriever.py
----------------
ChromaDB retriever with feedback-weighted re-ranking.

How the feedback loop works:
  1. Every thumbs-up/down is stored in diagram_feedback with a score (+1/-1).
  2. Each diagram has a thumb_score (avg of all feedback).
  3. When we retrieve chunks, we check if any retrieved chunk came from a
     diagram that has feedback. If so, we boost (or penalise) its similarity
     score before final ranking.
  4. Over time, high-rated diagram examples bubble to the top of retrieval.

This means the RAG system gets measurably better as users give feedback —
which is the actual moat competitors without user data can't replicate.
"""
from __future__ import annotations
import os, asyncio, logging
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

BASE_DIR        = Path(__file__).resolve().parent.parent
CHROMA_DIR      = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "uml_knowledge"
EMBED_MODEL     = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DEFAULT_TOP_K   = int(os.getenv("RETRIEVER_TOP_K", "6"))

# How much feedback score influences retrieval rank
# 0.0 = feedback has no effect, 1.0 = fully overrides similarity
FEEDBACK_WEIGHT = float(os.getenv("FEEDBACK_WEIGHT", "0.15"))


@dataclass
class RetrievedChunk:
    text:          str
    source:        str
    diagram_type:  str
    content_type:  str
    score:         float          # cosine similarity (0–1)
    feedback_boost: float = 0.0   # applied from diagram feedback
    final_score:   float = field(init=False)

    def __post_init__(self):
        self.final_score = round(
            self.score * (1 - FEEDBACK_WEIGHT) + self.feedback_boost * FEEDBACK_WEIGHT, 4
        )


# ── Singleton helpers ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embed_model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(COLLECTION_NAME)


# ── Feedback score cache ──────────────────────────────────────────────────────
# Loaded lazily from DB; refreshed every N retrievals to avoid N+1 on every call

_feedback_cache: dict[str, float] = {}    # source_title → avg thumb_score
_cache_hits = 0
_CACHE_REFRESH_EVERY = 50   # refresh after this many retrieve() calls


def _refresh_feedback_cache():
    """
    Pull latest thumb_scores from the diagrams table and cache them by title.
    Runs synchronously via a new event loop if called from sync context.
    """
    global _feedback_cache
    try:
        import sqlalchemy as sa
        from db.models import Diagram
        from sqlalchemy import create_engine, select

        DB_PATH = Path(os.getenv("DB_PATH", "data/umlgen.db"))
        if not DB_PATH.exists():
            return

        engine = create_engine(f"sqlite:///{DB_PATH}")
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT title, thumb_score FROM diagrams WHERE thumb_score != 0")
            ).fetchall()
            _feedback_cache = {row[0]: float(row[1]) for row in rows}
        logger.debug("Feedback cache refreshed: %d entries", len(_feedback_cache))
    except Exception as e:
        logger.debug("Feedback cache refresh skipped: %s", e)


def _get_feedback_boost(chunk_text: str) -> float:
    """
    Look up whether this chunk's text matches any diagram title we have feedback for.
    Returns a value in [0, 1] (normalized from thumb_score range [-1, 1]).
    """
    if not _feedback_cache:
        return 0.5   # neutral when no feedback yet
    # Scan cache for any diagram title mentioned in the chunk
    for title, score in _feedback_cache.items():
        if title.lower() in chunk_text.lower():
            # Normalise from [-1, 1] → [0, 1]
            return (score + 1) / 2
    return 0.5   # neutral


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    diagram_type: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """
    Retrieve the most relevant UML knowledge chunks for *query*,
    re-ranked using accumulated user feedback.
    """
    global _cache_hits
    _cache_hits += 1
    if _cache_hits % _CACHE_REFRESH_EVERY == 0:
        _refresh_feedback_cache()

    model      = _get_embed_model()
    collection = _get_collection()
    query_emb  = model.encode(query).tolist()
    results: list[RetrievedChunk] = []

    # Filtered query (diagram-type specific)
    if diagram_type:
        filtered = collection.query(
            query_embeddings=[query_emb],
            n_results=min(top_k, collection.count()),
            where={"diagram_type": {"$in": [diagram_type, "general"]}},
            include=["documents", "metadatas", "distances"],
        )
        results.extend(_parse(filtered))

    # Unfiltered query (broad context)
    unfiltered = collection.query(
        query_embeddings=[query_emb],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    results.extend(_parse(unfiltered))

    # Deduplicate by text prefix, keep highest similarity
    seen: dict[str, RetrievedChunk] = {}
    for chunk in results:
        key = chunk.text[:100]
        if key not in seen or chunk.score > seen[key].score:
            seen[key] = chunk

    # Apply feedback boosts and re-rank by final_score
    for chunk in seen.values():
        chunk.feedback_boost = _get_feedback_boost(chunk.text)
        chunk.final_score = round(
            chunk.score * (1 - FEEDBACK_WEIGHT) + chunk.feedback_boost * FEEDBACK_WEIGHT, 4
        )

    ranked = sorted(seen.values(), key=lambda c: c.final_score, reverse=True)
    return ranked[:top_k]


def _parse(chroma_result: dict) -> list[RetrievedChunk]:
    chunks = []
    docs      = chroma_result.get("documents", [[]])[0]
    metas     = chroma_result.get("metadatas", [[]])[0]
    distances = chroma_result.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        similarity = 1.0 - dist if dist <= 1.0 else 1.0 / (1.0 + dist)
        chunks.append(RetrievedChunk(
            text=doc,
            source=meta.get("source", "unknown"),
            diagram_type=meta.get("diagram_type", "general"),
            content_type=meta.get("content_type", "unknown"),
            score=round(similarity, 4),
        ))
    return chunks
