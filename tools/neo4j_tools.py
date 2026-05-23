"""Direct Neo4j driver functions for Hetionet queries."""
import os
from typing import Any

import neo4j.time
import neo4j.spatial
import neo4j.graph
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

load_dotenv()

_driver: Driver | None = None


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        user = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(user, os.environ["NEO4J_PASSWORD"]),
        )
    return _driver


def _serialize(value: Any) -> Any:
    """Convert neo4j native types to JSON-safe Python types."""
    if isinstance(value, (neo4j.time.Date, neo4j.time.Time,
                          neo4j.time.DateTime, neo4j.time.Duration)):
        return str(value)
    if isinstance(value, neo4j.spatial.Point):
        return str(value)
    if isinstance(value, neo4j.graph.Node):
        return {"labels": list(value.labels), **{k: _serialize(v) for k, v in value.items()}}
    if isinstance(value, neo4j.graph.Relationship):
        return {"type": value.type, **{k: _serialize(v) for k, v in value.items()}}
    if isinstance(value, neo4j.graph.Path):
        return [_serialize(n) for n in value.nodes]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _records_to_dicts(records) -> list[dict[str, Any]]:
    """Convert neo4j Records to serialized dicts."""
    return [_serialize(dict(r)) for r in records]


def _run_cypher_params(query: str, params: dict) -> list[dict[str, Any]]:
    """Internal: execute a parameterized read-only Cypher query."""
    driver = _get_driver()
    with driver.session() as session:
        return session.execute_read(
            lambda tx: _records_to_dicts(tx.run(query, params))
        )


def run_cypher(query: str) -> list[dict[str, Any]]:
    """Execute a read-only Cypher query and return serialized results.

    Write the full query with literal values — no parameter substitution.
    Only available to graph_db_agent.

    Args:
        query: A complete read-only Cypher query string.

    Returns:
        List of dicts with the query result rows.
    """
    return _run_cypher_params(query, {})


def get_compound_diseases(compound_name: str) -> list[dict[str, Any]]:
    """Get diseases treated or palliated by a compound.

    Args:
        compound_name: Exact compound name as stored in Hetionet (e.g. 'Ibuprofen').

    Returns:
        List of dicts with keys: disease, relationship.
    """
    query = (
        "MATCH (c:Compound {name: $name})-[r:TREATS|PALLIATES]-(d:Disease) "
        "RETURN d.name AS disease, type(r) AS relationship "
        "ORDER BY d.name"
    )
    return _run_cypher_params(query, {"name": compound_name})


def get_disease_compounds(disease_name: str) -> list[dict[str, Any]]:
    """Get compounds that treat or palliate a disease.

    Args:
        disease_name: Exact disease name as stored in Hetionet (e.g. 'osteoarthritis').

    Returns:
        List of dicts with keys: compound, identifier, relationship.
    """
    query = (
        "MATCH (c:Compound)-[r:TREATS|PALLIATES]-(d:Disease {name: $name}) "
        "RETURN c.name AS compound, c.identifier AS identifier, type(r) AS relationship "
        "ORDER BY c.name"
    )
    return _run_cypher_params(query, {"name": disease_name})


def get_gene_diseases(gene_symbol: str) -> list[dict[str, Any]]:
    """Get diseases associated with a gene.

    Args:
        gene_symbol: Gene symbol as stored in Hetionet (e.g. 'TNF').

    Returns:
        List of dicts with keys: disease, identifier.
    """
    query = (
        "MATCH (g:Gene {name: $symbol})-[:ASSOCIATES]-(d:Disease) "
        "RETURN d.name AS disease, d.identifier AS identifier "
        "ORDER BY d.name"
    )
    return _run_cypher_params(query, {"symbol": gene_symbol})


def get_compound_side_effects(compound_name: str) -> list[dict[str, Any]]:
    """Get side effects caused by a compound.

    Args:
        compound_name: Exact compound name as stored in Hetionet (e.g. 'Ibuprofen').

    Returns:
        List of dicts with keys: side_effect, identifier.
    """
    query = (
        "MATCH (c:Compound {name: $name})-[:CAUSES]-(se:`Side Effect`) "
        "RETURN se.name AS side_effect, se.identifier AS identifier "
        "ORDER BY se.name"
    )
    return _run_cypher_params(query, {"name": compound_name})


def get_disease_symptoms(disease_name: str) -> list[dict[str, Any]]:
    """Get symptoms presented by a disease.

    Args:
        disease_name: Exact disease name as stored in Hetionet (e.g. 'osteoarthritis').

    Returns:
        List of dicts with keys: symptom, identifier.
    """
    query = (
        "MATCH (d:Disease {name: $name})-[:PRESENTS]-(s:Symptom) "
        "RETURN s.name AS symptom, s.identifier AS identifier "
        "ORDER BY s.name"
    )
    return _run_cypher_params(query, {"name": disease_name})


def get_gene_compounds(gene_symbol: str) -> list[dict[str, Any]]:
    """Get compounds that bind to a gene.

    Args:
        gene_symbol: Gene symbol as stored in Hetionet (e.g. 'PTGS2').

    Returns:
        List of dicts with keys: compound, identifier.
    """
    query = (
        "MATCH (c:Compound)-[:BINDS]-(g:Gene {name: $symbol}) "
        "RETURN c.name AS compound, c.identifier AS identifier "
        "ORDER BY c.name"
    )
    return _run_cypher_params(query, {"symbol": gene_symbol})


def get_disease_anatomy(disease_name: str) -> list[dict[str, Any]]:
    """Get anatomical locations where a disease is localized.

    Args:
        disease_name: Exact disease name as stored in Hetionet.

    Returns:
        List of dicts with keys: anatomy, identifier.
    """
    query = (
        "MATCH (d:Disease {name: $name})-[:LOCALIZES]-(a:Anatomy) "
        "RETURN a.name AS anatomy, a.identifier AS identifier "
        "ORDER BY a.name"
    )
    return _run_cypher_params(query, {"name": disease_name})


def get_similar_diseases(disease_name: str) -> list[dict[str, Any]]:
    """Get diseases that resemble the given disease.

    Args:
        disease_name: Exact disease name as stored in Hetionet.

    Returns:
        List of dicts with keys: similar_disease, identifier.
    """
    query = (
        "MATCH (d:Disease {name: $name})-[:RESEMBLES]-(d2:Disease) "
        "RETURN d2.name AS similar_disease, d2.identifier AS identifier "
        "ORDER BY d2.name"
    )
    return _run_cypher_params(query, {"name": disease_name})


def get_drug_repurposing_candidates(disease_name: str) -> list[dict[str, Any]]:
    """Find drug repurposing candidates via 2-hop compound→gene→disease paths.

    Args:
        disease_name: Exact disease name as stored in Hetionet.

    Returns:
        List of dicts with keys: compound, gene, path_length.
    """
    query = (
        "MATCH (c:Compound)-[:BINDS]-(g:Gene)-[:ASSOCIATES]-(d:Disease {name: $name}) "
        "WHERE NOT (c)-[:TREATS|PALLIATES]-(d) "
        "RETURN c.name AS compound, g.name AS gene "
        "ORDER BY c.name LIMIT 20"
    )
    return _run_cypher_params(query, {"name": disease_name})


def get_gene_pathways(gene_symbol: str) -> list[dict[str, Any]]:
    """Get biological pathways associated with a gene.

    Args:
        gene_symbol: Gene symbol as stored in Hetionet (e.g. 'TP53').

    Returns:
        List of dicts with keys: pathway, identifier.
    """
    # PARTICIPATES not loaded in AuraDB Free tier; INCLUDES links PharmacologicClass→Compound only.
    # Gene→Pathway traversal unavailable — return empty so agents don't hallucinate.
    return []


def count_gene_disease_associations(disease_name: str) -> dict[str, int]:
    """Count the total number of genes associated with a disease.

    Use this for any "how many genes" question — never estimate from a partial result set.

    Args:
        disease_name: Exact disease name as stored in Hetionet (e.g. 'type 2 diabetes mellitus').

    Returns:
        Dict with key 'count' containing the exact integer count.
    """
    query = (
        "MATCH (g:Gene)-[:ASSOCIATES]-(d:Disease {name: $name}) "
        "RETURN COUNT(g) AS count"
    )
    rows = _run_cypher_params(query, {"name": disease_name})
    return {"count": rows[0]["count"] if rows else 0}


def get_schema_node_types() -> list[str]:
    """Return all node label types in the Hetionet graph."""
    query = "CALL db.labels() YIELD label RETURN label ORDER BY label"
    return [r["label"] for r in _run_cypher_params(query, {})]


def get_schema_relationship_types() -> list[str]:
    """Return all relationship types in the Hetionet graph."""
    query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
    return [r["relationshipType"] for r in _run_cypher_params(query, {})]


def search_chunks(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search PubMed paper chunks by text substring match.

    Returns Chunk nodes ingested by ingestion/ingest_papers.py that contain
    the query terms, along with their source paper metadata.

    Note: This is a text-based fallback. For vector similarity search over
    chunks, the chunk vector index must be set up separately (see ingestion/).

    Args:
        query: Natural-language query string.
        top_k: Maximum number of chunk results to return.

    Returns:
        List of dicts with keys: chunk_id, text, pmid, title, source.
        Returns empty list if no Chunk nodes exist yet (run ingestion first).
    """
    words = query.lower().split()
    if not words:
        return []

    # Match chunks containing any query word in their text
    search_term = words[0]
    cypher = (
        "MATCH (c:Chunk) "
        "WHERE toLower(c.text) CONTAINS $term "
        "RETURN c.id AS chunk_id, c.text AS text, "
        "       c.pmid AS pmid, c.title AS title, c.source AS source "
        f"LIMIT {top_k}"
    )
    return _run_cypher_params(cypher, {"term": search_term})
