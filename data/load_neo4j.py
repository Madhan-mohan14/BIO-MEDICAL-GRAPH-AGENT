"""Filter Hetionet with pandas, then load into Neo4j AuraDB.

Actual edge counts from edges.csv (2,250,197 total):
  PARTICIPATES  814,664   Gene -> Biological Process / Pathway   DROP (too large)
  EXPRESSES     526,407   Anatomy -> Gene                        DROP (too large)
  REGULATES     265,672   Gene -> Gene                           DROP (too large)
  DOWNREGULATES 130,965   Gene -> Gene                           DROP (too large)
  UPREGULATES   124,335   Gene -> Gene                           DROP (too large)
  ─────────────────────────────────────────────────────────────────────
  CAUSES        138,944   Compound -> Side Effect               KEEP
  INTERACTS     147,164   Gene <-> Gene                         KEEP
  COVARIES       61,690   Gene <-> Gene                         KEEP
  ASSOCIATES     12,623   Gene <-> Disease                      KEEP
  BINDS          11,571   Compound <-> Gene                     KEEP
  RESEMBLES       7,029   Disease<->Disease, Compound<->Compound KEEP
  LOCALIZES       3,602   Disease -> Anatomy                    KEEP
  PRESENTS        3,357   Disease -> Symptom                    KEEP
  INCLUDES        1,029   Pathway -> Gene                       KEEP
  TREATS            755   Compound -> Disease                   KEEP
  PALLIATES         390   Compound -> Disease                   KEEP
  ─────────────────────────────────────────────────────────────────────
  TOTAL KEPT    388,154   (well under AuraDB Free ~400K limit)

Nodes: all 47,031 loaded (all 11 types).
Storage estimate: ~162 MB (AuraDB Free = 200 MB).
"""
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from tqdm import tqdm

load_dotenv()

DATA_DIR = Path(__file__).parent
NODES_CSV = DATA_DIR / "nodes.csv"
EDGES_CSV = DATA_DIR / "edges.csv"
FILTERED_EDGES_CSV = DATA_DIR / "filtered_edges.csv"

BATCH_SIZE = 500

# Drop only the 5 relationship types too large to fit in AuraDB Free.
DROP_REL_TYPES = {
    "PARTICIPATES",   # 814,664 Gene -> Biological Process / Pathway
    "EXPRESSES",      # 526,407 Anatomy -> Gene
    "REGULATES",      # 265,672 Gene -> Gene
    "DOWNREGULATES",  # 130,965 Gene -> Gene
    "UPREGULATES",    # 124,335 Gene -> Gene
}


def get_driver() -> Driver:
    user = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(user, os.environ["NEO4J_PASSWORD"]),
    )


# ── Pandas filter ─────────────────────────────────────────────────────────────

def filter_edges() -> pd.DataFrame:
    """Read edges.csv and drop the 5 oversized relationship types.

    Returns:
        Filtered edges DataFrame with ~388K rows.
    """
    print("Reading edges.csv...")
    edges_df = pd.read_csv(EDGES_CSV, dtype=str)
    print(f"  Raw: {len(edges_df):,} edges")

    kept = edges_df[~edges_df["rel_type"].isin(DROP_REL_TYPES)].copy()
    dropped_types = edges_df["rel_type"].unique()
    dropped_types = [r for r in dropped_types if r in DROP_REL_TYPES]

    print(f"  Dropped types ({len(dropped_types)}): {', '.join(sorted(DROP_REL_TYPES))}")
    print(f"  Kept: {len(kept):,} edges across {kept['rel_type'].nunique()} rel types")
    print()
    print("  Edge breakdown:")
    for rel, cnt in kept["rel_type"].value_counts().sort_values(ascending=False).items():
        print(f"    {rel}: {cnt:,}")

    kept.to_csv(FILTERED_EDGES_CSV, index=False)
    print(f"\n  Saved filtered_edges.csv")
    return kept


# ── Neo4j loader ──────────────────────────────────────────────────────────────

def create_indexes(driver: Driver) -> None:
    """Create identifier + name indexes for all 11 Hetionet node types."""
    node_types = [
        "Anatomy", "Biological Process", "Cellular Component", "Compound",
        "Disease", "Gene", "Molecular Function", "Pathway",
        "Pharmacologic Class", "Side Effect", "Symptom",
    ]
    with driver.session() as session:
        for kind in node_types:
            safe = kind.replace(" ", "")
            session.run(
                f"CREATE INDEX {safe.lower()}_identifier IF NOT EXISTS "
                f"FOR (n:`{kind}`) ON (n.identifier)"
            )
            session.run(
                f"CREATE INDEX {safe.lower()}_name IF NOT EXISTS "
                f"FOR (n:`{kind}`) ON (n.name)"
            )
    print(f"Indexes created for {len(node_types)} node types")


def load_nodes(driver: Driver, nodes_df: pd.DataFrame) -> None:
    """Load all 47K nodes into Neo4j grouped by kind.

    Args:
        driver: Connected Neo4j driver.
        nodes_df: Full nodes DataFrame (identifier, kind, name).
    """
    for kind, group in nodes_df.groupby("kind"):
        rows = group[["identifier", "name"]].to_dict("records")
        print(f"Loading {len(rows):,} {kind} nodes...")
        batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        with driver.session() as session:
            for batch in tqdm(batches, desc=kind, unit="batch", leave=False):
                session.execute_write(
                    lambda tx, b=batch, k=kind: tx.run(
                        f"UNWIND $rows AS row "
                        f"MERGE (n:`{k}` {{identifier: row.identifier}}) "
                        f"SET n.name = row.name",
                        rows=b,
                    )
                )


def load_edges(driver: Driver, edges_df: pd.DataFrame) -> None:
    """Load filtered edges grouped by (rel_type, source_kind, target_kind).

    Grouping by all three keys handles RESEMBLES correctly:
    it has two variants — Disease<->Disease and Compound<->Compound.

    Args:
        driver: Connected Neo4j driver.
        edges_df: Filtered edges DataFrame.
    """
    groups = edges_df.groupby(["rel_type", "source_kind", "target_kind"])
    for (rel_type, src_kind, tgt_kind), group in groups:
        rows = group[["source_id", "target_id"]].to_dict("records")
        print(f"Loading {len(rows):,} {rel_type} ({src_kind} -> {tgt_kind})...")
        batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        with driver.session() as session:
            for batch in tqdm(batches, desc=rel_type, unit="batch", leave=False):
                session.execute_write(
                    lambda tx, b=batch, sk=src_kind, tk=tgt_kind, rt=rel_type: tx.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (src:`{sk}` {{identifier: row.source_id}}) "
                        f"MATCH (tgt:`{tk}` {{identifier: row.target_id}}) "
                        f"MERGE (src)-[:{rt}]->(tgt)",
                        rows=b,
                    )
                )


def verify_load(driver: Driver) -> None:
    with driver.session() as session:
        n = session.execute_read(
            lambda tx: tx.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        )
        r = session.execute_read(
            lambda tx: tx.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        )
    print(f"\nVerification: {n:,} nodes, {r:,} relationships loaded into AuraDB")


def main() -> None:
    if not NODES_CSV.exists() or not EDGES_CSV.exists():
        print("ERROR: nodes.csv / edges.csv not found. Run download_hetionet.py first.")
        sys.exit(1)

    print("=== Hetionet Load (all nodes + 11 rel types) ===\n")

    print("Reading nodes.csv...")
    nodes_df = pd.read_csv(NODES_CSV, dtype=str)
    print(f"  {len(nodes_df):,} nodes ({nodes_df['kind'].nunique()} types)\n")

    edges_df = filter_edges()

    driver = get_driver()
    try:
        print("\nCreating indexes...")
        create_indexes(driver)

        print("\nLoading nodes...")
        load_nodes(driver, nodes_df)

        print("\nLoading edges...")
        load_edges(driver, edges_df)

        verify_load(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
