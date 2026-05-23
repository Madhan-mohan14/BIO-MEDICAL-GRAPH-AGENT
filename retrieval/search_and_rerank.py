"""search_and_rerank — semantic vector search followed by 3-stage reranking.

Exposed as a single tool function for semantic_agent so the full BM25 ->
Semantic -> CrossEncoder pipeline is exercised on every vector search call.
"""
from typing import Any

from retrieval.semantic_reranker import search_neo4j_vector
from retrieval.pipeline import rerank_pipeline


def search_and_rerank(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Search Hetionet nodes by semantic similarity, then rerank through 3 stages.

    Stage 0 — Neo4j vector index: retrieves top-50 candidates by embedding cosine.
    Stage 1 — BM25: keyword-based pruning to top 50 (from the 50 candidates).
    Stage 2 — Semantic cosine rerank: prunes to top 20.
    Stage 3 — CrossEncoder (ms-marco-MiniLM-L-6-v2): prunes to top_k (default 10).

    Each Neo4j result is serialized as:
        "<kind>: <name> — <identifier>"
    before being scored by BM25 and CrossEncoder.

    Args:
        query: Natural-language query string (e.g. "anti-inflammatory drugs for arthritis").
        top_k: Number of final results to return after all reranking stages.

    Returns:
        List of dicts with keys: identifier, kind, name, score, bm25_score,
        semantic_score, cross_encoder_score, text.
    """
    raw = search_neo4j_vector(query, top_k=50)

    # Serialize each Neo4j result dict into a scorable text string.
    for item in raw:
        kind = item.get("kind") or ""
        name = item.get("name") or ""
        identifier = item.get("identifier") or ""
        item["text"] = f"{kind}: {name} — {identifier}".strip(" —")

    return rerank_pipeline(query, raw)[:top_k]
