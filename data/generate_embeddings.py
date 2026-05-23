"""Generate sentence-transformer embeddings and store as Neo4j node properties.

Model: all-mpnet-base-v2 (768-dim, cosine similarity) — runs locally, no API quota.
Source: nodes.csv (all 11 node types, 47K nodes)
Index:  Neo4j vector index 'hetionet_node_embeddings' (recreated if it exists)

Safe to re-run — skips nodes that already have an embedding property.
"""
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

load_dotenv()

DATA_DIR   = Path(__file__).parent
NODES_CSV  = DATA_DIR / "nodes.csv"

EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_DIM   = 768
BATCH_SIZE      = 256   # sentence-transformers handles large CPU batches fine
WRITE_BATCH     = 500   # nodes per Neo4j write transaction

EMBED_NODE_TYPES = {
    "Disease", "Compound", "Gene", "Side Effect", "Symptom",
    "Anatomy", "Biological Process", "Cellular Component",
    "Molecular Function", "Pathway", "Pharmacologic Class",
}


def get_driver() -> Driver:
    user = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(user, os.environ["NEO4J_PASSWORD"]),
    )


def node_to_text(kind: str, name: str) -> str:
    return f"{kind}: {name}"


def create_vector_index(driver: Driver) -> None:
    with driver.session() as session:
        try:
            session.run("DROP INDEX hetionet_node_embeddings IF EXISTS")
        except Exception:
            pass
        session.execute_write(
            lambda tx: tx.run(
                "CREATE VECTOR INDEX hetionet_node_embeddings IF NOT EXISTS "
                "FOR (n:_Embedded) ON n.embedding "
                "OPTIONS {indexConfig: {"
                "  `vector.dimensions`: $dims,"
                "  `vector.similarity_function`: 'cosine'"
                "}}",
                dims=EMBEDDING_DIM,
            )
        )
    print(f"Vector index 'hetionet_node_embeddings' ready ({EMBEDDING_DIM}-dim cosine)")


def get_already_embedded(driver: Driver) -> set[str]:
    with driver.session() as session:
        rows = session.execute_read(
            lambda tx: list(tx.run(
                "MATCH (n:_Embedded) RETURN n.identifier AS id"
            ))
        )
    return {r["id"] for r in rows}


def write_embeddings(
    driver: Driver,
    batch: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Write embeddings grouped by kind to use per-label indexes."""
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for n, emb in zip(batch, embeddings):
        by_kind[n["kind"]].append({
            "identifier": n["identifier"],
            "embedding": emb,
        })

    with driver.session() as session:
        for kind, rows in by_kind.items():
            session.execute_write(
                lambda tx, k=kind, r=rows: tx.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (n:`{k}` {{identifier: row.identifier}}) "
                    f"SET n.embedding = row.embedding, n:_Embedded",
                    rows=r,
                )
            )


def load_nodes_to_embed() -> list[dict]:
    print("Reading nodes from nodes.csv...")
    df = pd.read_csv(NODES_CSV, dtype=str)
    df = df[df["kind"].isin(EMBED_NODE_TYPES)]
    print(f"  {len(df):,} nodes to consider for embedding")
    return df[["identifier", "kind", "name"]].to_dict("records")


def main() -> None:
    print("=== Sentence-Transformer Embedding Generation ===")
    print(f"Model : {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim, local)\n")

    print("Loading model (downloads ~420MB on first run)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("Model loaded.\n")

    driver = get_driver()
    try:
        create_vector_index(driver)

        nodes = load_nodes_to_embed()
        already_done = get_already_embedded(driver)
        to_embed = [n for n in nodes if n["identifier"] not in already_done]
        print(f"Already embedded : {len(already_done):,}")
        print(f"To embed now     : {len(to_embed):,}\n")

        if not to_embed:
            print("All nodes already have embeddings. Done.")
            return

        write_buf: list[dict] = []
        write_emb: list[list[float]] = []

        batches = [to_embed[i:i + BATCH_SIZE] for i in range(0, len(to_embed), BATCH_SIZE)]
        for batch in tqdm(batches, desc="Embedding", unit="batch"):
            texts = [node_to_text(n["kind"], n["name"]) for n in batch]
            vecs = model.encode(texts, show_progress_bar=False).tolist()

            write_buf.extend(batch)
            write_emb.extend(vecs)

            if len(write_buf) >= WRITE_BATCH:
                write_embeddings(driver, write_buf, write_emb)
                write_buf.clear()
                write_emb.clear()

        if write_buf:
            write_embeddings(driver, write_buf, write_emb)

        with driver.session() as session:
            count = session.execute_read(
                lambda tx: tx.run("MATCH (n:_Embedded) RETURN count(n) AS c").single()["c"]
            )
        print(f"\nDone: {count:,} nodes with embeddings in Neo4j vector index")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
