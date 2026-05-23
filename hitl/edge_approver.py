"""HITL edge approver — parses new-edge candidates and writes approved ones to Neo4j."""
import os
from dotenv import load_dotenv

load_dotenv()

from neo4j import GraphDatabase, Driver

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


def parse_new_edge_from_web(new_edge_line: str) -> dict | None:
    """Parse a NEW_EDGE line from web_agent output into a structured dict.

    Expected format:
        <src_type>|<src_name>|<rel_type>|<tgt_type>|<tgt_name>|<evidence_url>

    Args:
        new_edge_line: The NEW_EDGE payload string (after stripping the 'NEW_EDGE:' prefix).

    Returns:
        Dict with keys: source_type, source_name, rel_type, target_type, target_name,
        evidence_url. Returns None if the line cannot be parsed.
    """
    parts = [p.strip() for p in new_edge_line.split("|")]
    if len(parts) < 5:
        return None
    return {
        "source_type": parts[0],
        "source_name": parts[1],
        "rel_type": parts[2],
        "target_type": parts[3],
        "target_name": parts[4],
        "evidence_url": parts[5] if len(parts) > 5 else "",
    }


def write_approved_edge(edge: dict) -> bool:
    """Write an approved new edge to Neo4j after human approval.

    Only called from the /approve-edge endpoint after explicit user confirmation.

    Args:
        edge: Dict with keys: source_type, source_name, rel_type, target_type,
              target_name, evidence_url.

    Returns:
        True if the edge was written, False if source or target node not found.
    """
    src_label = f"`{edge['source_type']}`"
    tgt_label = f"`{edge['target_type']}`"
    rel_type = edge["rel_type"].upper().replace(" ", "_")

    driver = _get_driver()
    with driver.session() as session:
        def _write(tx):
            return tx.run(
                f"MATCH (src:{src_label} {{name: $src_name}}) "
                f"MATCH (tgt:{tgt_label} {{name: $tgt_name}}) "
                f"MERGE (src)-[r:{rel_type}]->(tgt) "
                f"SET r.evidence_url = $url, r.human_approved = true "
                f"RETURN count(r) AS created",
                src_name=edge["source_name"],
                tgt_name=edge["target_name"],
                url=edge.get("evidence_url", ""),
            ).single()

        record = session.execute_write(_write)
        return bool(record and record["created"] > 0)
