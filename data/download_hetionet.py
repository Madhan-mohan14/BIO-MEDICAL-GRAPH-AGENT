"""Download Hetionet v1.0 JSON from GitHub and extract nodes + edges to CSV.

Relationship types are derived directly from the edge 'kind' field (verb),
uppercased — e.g. 'treats' → 'TREATS', 'upregulates' → 'UPREGULATES'.
No abbreviation mapping needed.
"""
import bz2
import csv
import json
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent
HETIONET_URL = "https://github.com/hetio/hetionet/raw/main/hetnet/json/hetionet-v1.0.json.bz2"
JSON_BZ2 = DATA_DIR / "hetionet-v1.0.json.bz2"
NODES_CSV = DATA_DIR / "nodes.csv"
EDGES_CSV = DATA_DIR / "edges.csv"


def download_file(url: str, dest: Path) -> None:
    """Stream-download a file with a progress bar.

    Args:
        url: Source URL.
        dest: Local destination path.
    """
    print(f"Downloading {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


def load_json(path: Path) -> dict[str, Any]:
    """Read Hetionet JSON, decompressing bz2 automatically.

    Args:
        path: Path to .json.bz2 file.

    Returns:
        Parsed JSON dict.
    """
    print(f"Loading {path}")
    with bz2.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def extract_nodes(hetnet: dict[str, Any]) -> list[dict[str, str]]:
    """Extract all nodes as flat dicts.

    Args:
        hetnet: Parsed Hetionet JSON dict.

    Returns:
        List of dicts with keys: identifier, kind, name.
    """
    rows = []
    for node in tqdm(hetnet["nodes"], desc="Extracting nodes"):
        rows.append({
            "identifier": str(node["identifier"]),
            "kind": node["kind"],
            "name": node.get("name", str(node["identifier"])),
        })
    return rows


def extract_edges(hetnet: dict[str, Any]) -> list[dict[str, str]]:
    """Extract all edges, deriving relationship type from the verb kind uppercased.

    Relationship type = edge['kind'].upper(), e.g. 'treats' → 'TREATS'.

    Args:
        hetnet: Parsed Hetionet JSON dict.

    Returns:
        List of dicts with keys: source_kind, source_id, target_kind, target_id, rel_type.
    """
    rows = []
    for edge in tqdm(hetnet["edges"], desc="Extracting edges"):
        src_kind, src_id = edge["source_id"]
        tgt_kind, tgt_id = edge["target_id"]
        rel_type = edge["kind"].upper().replace(" ", "_")
        rows.append({
            "source_kind": src_kind,
            "source_id": str(src_id),
            "target_kind": tgt_kind,
            "target_id": str(tgt_id),
            "rel_type": rel_type,
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    """Write list of dicts to CSV.

    Args:
        rows: List of dicts (all must have identical keys).
        path: Destination CSV path.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} rows to {path}")


def download_hetionet() -> tuple[list[dict], list[dict]]:
    """Download Hetionet and return (nodes, edges) as lists of dicts.

    Caches the bz2 file locally — re-runs skip the download.

    Returns:
        Tuple of (nodes, edges) where each is a list of flat dicts.
    """
    if not JSON_BZ2.exists():
        download_file(HETIONET_URL, JSON_BZ2)
    else:
        print(f"Using cached {JSON_BZ2}")

    hetnet = load_json(JSON_BZ2)
    nodes = extract_nodes(hetnet)
    edges = extract_edges(hetnet)

    write_csv(nodes, NODES_CSV)
    write_csv(edges, EDGES_CSV)

    return nodes, edges


if __name__ == "__main__":
    nodes, edges = download_hetionet()
    print(f"\nDone: {len(nodes):,} nodes, {len(edges):,} edges")

    rel_types = sorted({e["rel_type"] for e in edges})
    print(f"\n{len(rel_types)} unique relationship types:")
    for r in rel_types:
        print(f"  {r}")
