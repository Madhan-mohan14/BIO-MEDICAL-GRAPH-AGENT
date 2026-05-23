"""PubMed open-access paper ingestion pipeline for Hetionet GraphRAG.

Fetches 5 biomedical papers from PubMed Central (open-access), chunks each
abstract into 300-token sliding windows, embeds them with all-mpnet-base-v2,
and stores them as Chunk nodes in Neo4j with MENTIONS edges to existing
Hetionet entities (Compound, Disease, Gene).

Graph schema added by this pipeline:
    (:Chunk {id, text, embedding, pmid, title, source})
    (:Chunk)-[:MENTIONS]->(:Compound|Disease|Gene)

Usage:
    uv pip install -r ingestion/requirements.txt
    uv run python ingestion/ingest_papers.py

neo4j_for_adk usage:
    The `graphdb` object from neo4j_for_adk provides ADK-native graph queries.
    We use it here to look up existing Hetionet node names so we can match
    them against chunk text (entity linking step).
    For writes (creating Chunk nodes + MENTIONS edges) we use the raw
    neo4j driver, since neo4j_for_adk is read-focused.
"""
import os
import sys
import time
import hashlib
import textwrap
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

# ── neo4j_for_adk read interface ───────────────────────────────────────────────
# neo4j_for_adk wraps Neo4j as an ADK-compatible tool.
# Its graphdb object can run parameterized Cypher for read queries.
try:
    from neo4j_for_adk import graphdb as _adk_graphdb
    _HAS_ADK_GRAPHDB = True
except ImportError:
    _adk_graphdb = None
    _HAS_ADK_GRAPHDB = False
    print("[warn] neo4j_for_adk not installed — falling back to raw driver for reads.")
    print("       Install: uv pip install neo4j-for-adk")

# ── Config ─────────────────────────────────────────────────────────────────────

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
CHUNK_TOKENS = 300
CHUNK_OVERLAP = 50

# PubMed IDs — open-access papers directly relevant to biomedical knowledge graphs
# and drug repurposing (the domain of this project).
PMIDS = [
    "26158728",  # Himmelstein et al. — Hetionet drug repurposing (the dataset we use)
    "33974656",  # Knowledge graph embedding methods for drug-target interaction
    "36380181",  # Graph neural networks for biomedical data
    "34433990",  # Drug repurposing with graph-based machine learning
    "35985955",  # Biomedical knowledge graphs: overview and applications
]

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# ── Neo4j driver (singleton for writes) ───────────────────────────────────────

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


# ── Step 1: Fetch PubMed abstracts via NCBI E-utilities ───────────────────────

def fetch_pubmed_abstract(pmid: str) -> dict[str, str]:
    """Fetch title + abstract for a PubMed paper via NCBI E-utilities.

    Args:
        pmid: PubMed ID string (e.g. '26158728').

    Returns:
        Dict with keys: pmid, title, abstract, source.
    """
    time.sleep(0.4)  # NCBI rate limit: max 3 requests/sec without API key
    resp = requests.get(
        NCBI_EFETCH,
        params={"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"},
        timeout=15,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml-xml")

    title_tag = soup.find("ArticleTitle")
    title = title_tag.get_text(separator=" ").strip() if title_tag else f"PubMed:{pmid}"

    abstract_parts = soup.find_all("AbstractText")
    abstract = " ".join(p.get_text(separator=" ").strip() for p in abstract_parts)

    if not abstract:
        abstract = title  # fallback to title if no abstract

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "source": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


# ── Step 2: Chunk text with sliding window ─────────────────────────────────────

def _tokenize_simple(text: str) -> list[str]:
    """Whitespace tokenizer — avoids heavy tokenizer dependency."""
    return text.split()


def chunk_text(text: str, tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping token windows.

    Args:
        text: Input text to chunk.
        tokens: Window size in whitespace tokens.
        overlap: Number of tokens to carry over between windows.

    Returns:
        List of chunk strings.
    """
    words = _tokenize_simple(text)
    if len(words) <= tokens:
        return [text]

    chunks = []
    step = tokens - overlap
    for start in range(0, len(words), step):
        window = words[start : start + tokens]
        chunks.append(" ".join(window))
        if start + tokens >= len(words):
            break
    return chunks


# ── Step 3: Load entity names from Hetionet ───────────────────────────────────

def load_entity_names() -> list[dict[str, str]]:
    """Return all Compound, Disease, and Gene names from Hetionet.

    Uses neo4j_for_adk.graphdb when available; falls back to raw driver.
    Keeps only names with >= 4 characters to avoid spurious substring matches.

    Returns:
        List of dicts with keys: name, kind.
    """
    cypher = (
        "MATCH (n) WHERE n.name IS NOT NULL "
        "AND (n:Compound OR n:Disease OR n:Gene) "
        "RETURN n.name AS name, labels(n)[0] AS kind"
    )

    if _HAS_ADK_GRAPHDB:
        # neo4j_for_adk.graphdb exposes .run_cypher(query) -> list[dict]
        rows = _adk_graphdb.run_cypher(cypher)
    else:
        # Raw driver fallback
        driver = _get_driver()
        with driver.session() as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher)))
            rows = [{"name": r["name"], "kind": r["kind"]} for r in result]

    # Filter short names that cause too many false-positive substring matches
    return [r for r in rows if len(r.get("name", "")) >= 4]


# ── Step 4: Entity linking (substring match) ───────────────────────────────────

def extract_mentions(chunk_text: str, entity_names: list[dict]) -> list[dict]:
    """Find Hetionet entities mentioned in a chunk by case-insensitive substring match.

    Args:
        chunk_text: The chunk string to scan.
        entity_names: List of {name, kind} dicts from load_entity_names().

    Returns:
        List of matched entity dicts with keys: name, kind.
    """
    chunk_lower = chunk_text.lower()
    seen = set()
    matches = []
    for entity in entity_names:
        name = entity["name"]
        if name.lower() in chunk_lower and name not in seen:
            seen.add(name)
            matches.append(entity)
    return matches


# ── Step 5: Write Chunk nodes + MENTIONS edges to Neo4j ───────────────────────

def _chunk_id(pmid: str, chunk_index: int) -> str:
    return hashlib.md5(f"{pmid}:{chunk_index}".encode()).hexdigest()[:16]


def write_chunks_to_neo4j(
    pmid: str,
    title: str,
    source_url: str,
    chunks: list[str],
    embeddings: list[list[float]],
    mentions_per_chunk: list[list[dict]],
) -> int:
    """Write Chunk nodes and MENTIONS edges to Neo4j.

    Uses MERGE so re-running this script is safe (idempotent).

    Args:
        pmid: PubMed ID.
        title: Paper title (stored on each Chunk for provenance).
        source_url: PubMed URL stored on each Chunk.
        chunks: List of chunk text strings.
        embeddings: Corresponding embedding vectors.
        mentions_per_chunk: Entity matches for each chunk.

    Returns:
        Number of Chunk nodes written.
    """
    driver = _get_driver()

    with driver.session() as session:
        def _write(tx, chunk_text, embedding, chunk_id, pmid, title, source_url):
            tx.run(
                "MERGE (c:Chunk {id: $id}) "
                "SET c.text = $text, c.embedding = $embedding, "
                "    c.pmid = $pmid, c.title = $title, c.source = $source",
                id=chunk_id,
                text=chunk_text,
                embedding=embedding,
                pmid=pmid,
                title=title,
                source=source_url,
            )

        def _mention(tx, chunk_id, entity_name, entity_kind):
            # Dynamic label via apoc is unavailable on AuraDB Free;
            # use a conditional MATCH per known type instead.
            label_map = {
                "Compound": "Compound",
                "Disease": "Disease",
                "Gene": "Gene",
            }
            label = label_map.get(entity_kind, "Gene")
            tx.run(
                f"MATCH (chunk:Chunk {{id: $cid}}) "
                f"MATCH (entity:{label} {{name: $name}}) "
                "MERGE (chunk)-[:MENTIONS]->(entity)",
                cid=chunk_id,
                name=entity_name,
            )

        for i, (text, emb, mentions) in enumerate(
            zip(chunks, embeddings, mentions_per_chunk)
        ):
            cid = _chunk_id(pmid, i)
            session.execute_write(_write, text, emb, cid, pmid, title, source_url)
            for entity in mentions:
                session.execute_write(
                    _mention, cid, entity["name"], entity["kind"]
                )

    return len(chunks)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_ingestion() -> None:
    """Fetch 5 PubMed papers, chunk, embed, and load into Neo4j.

    Idempotent — MERGE ensures re-runs don't create duplicates.
    """
    print("Loading sentence-transformers/all-mpnet-base-v2 ...")
    model = SentenceTransformer(EMBED_MODEL)

    print("Loading Hetionet entity names for entity linking ...")
    entity_names = load_entity_names()
    print(f"  Loaded {len(entity_names)} entity names (Compound + Disease + Gene).")

    total_chunks = 0

    for pmid in PMIDS:
        print(f"\n{'=' * 60}")
        print(f"  PubMed ID: {pmid}")
        paper = fetch_pubmed_abstract(pmid)
        print(f"  Title: {textwrap.shorten(paper['title'], 70)}")
        print(f"  Abstract length: {len(paper['abstract'])} chars")

        # Chunk
        chunks = chunk_text(paper["abstract"])
        print(f"  Chunks produced: {len(chunks)}")

        # Embed
        embeddings = model.encode(chunks, show_progress_bar=False).tolist()

        # Entity linking
        mentions_per_chunk = [extract_mentions(c, entity_names) for c in chunks]
        total_mentions = sum(len(m) for m in mentions_per_chunk)
        print(f"  Entity mentions found: {total_mentions}")

        # Write to Neo4j
        n = write_chunks_to_neo4j(
            pmid=pmid,
            title=paper["title"],
            source_url=paper["source"],
            chunks=chunks,
            embeddings=embeddings,
            mentions_per_chunk=mentions_per_chunk,
        )
        total_chunks += n
        print(f"  Written {n} Chunk nodes to Neo4j.")

    print(f"\n{'=' * 60}")
    print(f"  Done. Total Chunk nodes written: {total_chunks}")
    print("  Query to verify:")
    print("    MATCH (c:Chunk)-[:MENTIONS]->(e) RETURN c.pmid, e.name, labels(e) LIMIT 20")


if __name__ == "__main__":
    run_ingestion()
