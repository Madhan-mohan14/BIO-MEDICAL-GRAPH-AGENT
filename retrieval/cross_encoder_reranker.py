"""Cross-encoder reranker — third stage of the 3-stage reranking pipeline."""
from typing import Any

from sentence_transformers import CrossEncoder

_cross_encoder: CrossEncoder | None = None
_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(_MODEL)
    return _cross_encoder


def cross_encoder_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Rerank candidates using a cross-encoder relevance model.

    Each candidate must have a 'text' key. Returns top_k sorted by cross-encoder score.

    Args:
        query: Natural-language query string.
        candidates: List of dicts, each must have a 'text' key.
        top_k: Maximum results to return.

    Returns:
        Top-k candidates with added 'cross_encoder_score' key, sorted descending.
    """
    if not candidates:
        return []

    model = _get_cross_encoder()
    pairs = [[query, c["text"]] for c in candidates]
    scores = model.predict(pairs)

    scored = [
        {**c, "cross_encoder_score": float(scores[i])}
        for i, c in enumerate(candidates)
    ]
    scored.sort(key=lambda x: x["cross_encoder_score"], reverse=True)
    return scored[:top_k]
