"""Semantic search over Hetionet node embeddings stored in the Neo4j vector index.

Uses the same model as generate_embeddings.py (all-mpnet-base-v2, 768-dim)
so query vectors and stored vectors are always in the same space.
"""
import os
from typing import Any

import numpy as np
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from sentence_transformers import SentenceTransformer

load_dotenv()

EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_DIM   = 768

_driver: Driver | None = None
_model: SentenceTransformer | None = None


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        user = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(user, os.environ["NEO4J_PASSWORD"]),
        )
    return _driver


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _embed_query(text: str) -> list[float]:
    """Embed a single query string.

    Args:
        text: Query string to embed.

    Returns:
        768-dim float vector.
    """
    return _get_model().encode(text).tolist()


def search_neo4j_vector(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Search Hetionet nodes by semantic similarity using the Neo4j vector index.

    Args:
        query: Natural-language query string.
        top_k: Number of top results to return.

    Returns:
        List of dicts with keys: identifier, kind, name, score.
    """
    embedding = _embed_query(query)
    driver = _get_driver()
    with driver.session() as session:
        results = session.execute_read(
            lambda tx: list(tx.run(
                "CALL db.index.vector.queryNodes('hetionet_node_embeddings', $k, $emb) "
                "YIELD node, score "
                "RETURN node.identifier AS identifier, "
                "       labels(node)[0] AS kind, "
                "       node.name AS name, "
                "       score",
                k=top_k,
                emb=embedding,
            ))
        )
    return [dict(r) for r in results]


def semantic_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Rerank candidates by cosine similarity to a query embedding.

    Each candidate must have a 'text' key containing the string to compare against.

    Args:
        query: Natural-language query string.
        candidates: List of dicts, each must have a 'text' key.
        top_k: Number of results to return after reranking.

    Returns:
        Top-k candidates with added 'semantic_score' key, sorted descending.
    """
    if not candidates:
        return []

    model = _get_model()
    all_texts = [query] + [c["text"] for c in candidates]
    embeddings = np.array(model.encode(all_texts))
    query_emb = embeddings[0]
    doc_embs  = embeddings[1:]

    scores = np.dot(doc_embs, query_emb) / (
        np.linalg.norm(doc_embs, axis=1) * np.linalg.norm(query_emb) + 1e-9
    )
    scored = [
        {**c, "semantic_score": float(scores[i])}
        for i, c in enumerate(candidates)
    ]
    scored.sort(key=lambda x: x["semantic_score"], reverse=True)
    return scored[:top_k]
