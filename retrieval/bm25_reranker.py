"""BM25 keyword reranker — first stage of the 3-stage reranking pipeline."""
from typing import Any

from rank_bm25 import BM25Okapi


def bm25_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 50,
) -> list[dict[str, Any]]:
    """Rerank candidates by BM25 keyword score.

    Each candidate must have a 'text' key. Returns top_k sorted by BM25 score descending.

    Args:
        query: Natural-language query string.
        candidates: List of dicts, each must have a 'text' key.
        top_k: Maximum results to return.

    Returns:
        Top-k candidates with added 'bm25_score' key, sorted descending.
    """
    if not candidates:
        return []

    tokenized_corpus = [c["text"].lower().split() for c in candidates]
    tokenized_query = query.lower().split()
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)

    scored = [
        {**c, "bm25_score": float(scores[i])}
        for i, c in enumerate(candidates)
    ]
    scored.sort(key=lambda x: x["bm25_score"], reverse=True)
    return scored[:top_k]
