"""Wipe everything from Neo4j: all nodes, relationships, indexes, and the vector index.

Run before a clean reload. Deletes in batches of 10,000 to avoid heap exhaustion.
"""
import os

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

load_dotenv()


def get_driver() -> Driver:
    user = os.environ.get("NEO4J_USER") or os.environ["NEO4J_USERNAME"]
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(user, os.environ["NEO4J_PASSWORD"]),
    )


def drop_all_indexes(driver: Driver) -> None:
    with driver.session() as session:
        # Drop vector index explicitly first
        try:
            session.run("DROP INDEX hetionet_node_embeddings IF EXISTS")
            print("Dropped vector index 'hetionet_node_embeddings'")
        except Exception as e:
            print(f"  vector index: {e}")

        # Drop all remaining non-lookup indexes
        try:
            rows = session.execute_read(
                lambda tx: list(tx.run(
                    "SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name"
                ))
            )
            for row in rows:
                try:
                    session.run(f"DROP INDEX `{row['name']}` IF EXISTS")
                except Exception:
                    pass
            print(f"Dropped {len(rows)} additional indexes")
        except Exception as e:
            print(f"  index listing: {e}")


def delete_all(driver: Driver) -> None:
    with driver.session() as session:
        before = session.execute_read(
            lambda tx: tx.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        )
        print(f"Nodes before: {before:,}")

        if before == 0:
            print("Already empty.")
            return

        deleted = 0
        while True:
            n = session.execute_write(
                lambda tx: tx.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS c"
                ).single()["c"]
            )
            deleted += n
            print(f"  {deleted:,} / {before:,} deleted...", end="\r", flush=True)
            if n == 0:
                break

        print(f"\nDeleted {deleted:,} nodes and all relationships.")


def verify(driver: Driver) -> None:
    with driver.session() as session:
        n = session.execute_read(
            lambda tx: tx.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        )
        r = session.execute_read(
            lambda tx: tx.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        )
    status = "CLEAN" if n == 0 and r == 0 else "WARNING: not fully empty"
    print(f"After clear: {n:,} nodes, {r:,} relationships — {status}")


def main() -> None:
    print("=== Neo4j Clear ===")
    driver = get_driver()
    try:
        drop_all_indexes(driver)
        delete_all(driver)
        verify(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
