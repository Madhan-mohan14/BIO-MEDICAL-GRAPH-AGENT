"""3-stage reranking pipeline: BM25(top50) → Semantic cosine(top20) → CrossEncoder(top10)."""
from typing import Any

from retrieval.bm25_reranker import bm25_rerank
from retrieval.semantic_reranker import semantic_rerank
from retrieval.cross_encoder_reranker import cross_encoder_rerank


def rerank_pipeline(
    query: str,
    raw_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run the full 3-stage reranking pipeline over raw results.

    Each item in raw_results must have a 'text' key.

    Stage 1 — BM25: keyword matching, fast, prunes to top 50.
    Stage 2 — Semantic: text-embedding-004 cosine similarity, prunes to top 20.
    Stage 3 — CrossEncoder: ms-marco-MiniLM-L-6-v2, prunes to top 10.

    Args:
        query: Natural-language query string.
        raw_results: Combined results from Neo4j + vector search. Each must have 'text'.

    Returns:
        Top-10 results, sorted by cross-encoder score descending.
    """
    stage1 = bm25_rerank(query, raw_results, top_k=50)
    stage2 = semantic_rerank(query, stage1, top_k=20)
    stage3 = cross_encoder_rerank(query, stage2, top_k=10)
    return stage3
