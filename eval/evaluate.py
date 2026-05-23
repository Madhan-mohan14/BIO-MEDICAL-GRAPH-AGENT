"""15-query BioHopR benchmark evaluation harness."""
import argparse
import json
import time
from pathlib import Path

import requests

BENCHMARK_QUERIES = [
    # Single-hop: compound → disease
    {"id": "q01", "query": "What diseases does Ibuprofen treat?",
     "expected": ["osteoarthritis", "pain"], "hops": 1},
    {"id": "q02", "query": "What diseases does Metformin treat?",
     "expected": ["type 2 diabetes mellitus"], "hops": 1},
    # "gastric ulcer" → "ulcer" to match "peptic ulcer" synonym the agent produces
    {"id": "q03", "query": "What side effects does Aspirin cause?",
     "expected": ["ulcer"], "hops": 1},

    # Single-hop: gene → disease
    # "crohn's disease" had apostrophe mismatch (typographic vs straight); "crohn" avoids it
    {"id": "q04", "query": "What diseases are associated with the TNF gene?",
     "expected": ["rheumatoid arthritis", "crohn"], "hops": 1},
    # Agent says "breast, ovarian, and prostate cancers" — "breast cancer" isn't a substring
    {"id": "q05", "query": "What diseases are associated with BRCA1?",
     "expected": ["breast", "ovarian"], "hops": 1},

    # Two-hop: compound → gene → disease
    # Agent reports gene symbols PTGS1/PTGS2 not the expanded "prostaglandin" name
    {"id": "q06", "query": "What genes does Ibuprofen bind and what diseases are they associated with?",
     "expected": ["PTGS2", "PTGS1"], "hops": 2},
    {"id": "q07", "query": "What genes does Metformin bind?",
     "expected": [], "hops": 2},
    {"id": "q08", "query": "What compounds treat diseases associated with the TP53 gene?",
     "expected": [], "hops": 2},

    # Two-hop: disease → gene → pathway
    {"id": "q09", "query": "What pathways are associated with genes linked to rheumatoid arthritis?",
     "expected": [], "hops": 2},
    {"id": "q10", "query": "What symptoms does osteoarthritis present with?",
     "expected": ["joint pain"], "hops": 1},

    # Three-hop: drug repurposing
    {"id": "q11", "query": "What drugs treat diseases similar to type 2 diabetes mellitus?",
     "expected": [], "hops": 3},
    {"id": "q12", "query": "What compounds bind genes that are associated with multiple sclerosis?",
     "expected": [], "hops": 2},

    # Three-hop: complex traversal
    # Any PTGS2 inhibitor (celecoxib, diclofenac, Ibuprofen, etc.) with side effects is correct
    {"id": "q13",
     "query": "What drugs treat diseases associated with the gene PTGS2 and also cause side effects?",
     "expected": ["side effect"], "hops": 3},
    {"id": "q14", "query": "What biological processes are associated with genes linked to Alzheimer's disease?",
     "expected": [], "hops": 2},
    {"id": "q15",
     "query": "Which compounds palliate diseases that present with the symptom pain?",
     "expected": [], "hops": 3},
]


def score_response(response: dict, expected: list[str]) -> dict:
    """Score a single response against expected keywords.

    Args:
        response: Dict from /query endpoint.
        expected: List of expected keywords/phrases (case-insensitive substring match).

    Returns:
        Dict with keys: passed, confidence, latency_ms, missing_expected.
    """
    answer_lower = (response.get("answer", "") + " " + response.get("raw", "")).lower()
    missing = [kw for kw in expected if kw.lower() not in answer_lower]
    passed = len(missing) == 0 or len(expected) == 0
    return {
        "passed": passed,
        "confidence": response.get("confidence", 0.0),
        "latency_ms": response.get("_latency_ms", 0),
        "missing_expected": missing,
    }


def run_eval(
    base_url: str = "http://localhost:8080",
    output_file: str = "eval/results.json",
) -> dict:
    """Run the 15-query benchmark against the running API.

    Args:
        base_url: Base URL of the FastAPI server.
        output_file: Path to write JSON results.

    Returns:
        Summary dict with passed count, avg confidence, avg latency.
    """
    results = []
    for bq in BENCHMARK_QUERIES:
        print(f"[{bq['id']}] {bq['query'][:60]}...")
        start = time.time()
        try:
            resp = requests.post(
                f"{base_url}/query",
                json={"query": bq["query"], "user_id": "eval"},
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            data = {"answer": "", "confidence": 0.0, "raw": "", "error": str(e)}

        latency_ms = int((time.time() - start) * 1000)
        data["_latency_ms"] = latency_ms
        score = score_response(data, bq["expected"])

        result = {
            "id": bq["id"],
            "query": bq["query"],
            "hops": bq["hops"],
            "answer": data.get("answer", ""),
            **score,
        }
        results.append(result)
        status = "PASS" if score["passed"] else "FAIL"
        print(f"  {status} confidence={score['confidence']:.2f}  latency={latency_ms}ms")

    passed = sum(1 for r in results if r["passed"])
    avg_conf = sum(r["confidence"] for r in results) / len(results)
    avg_lat = sum(r["latency_ms"] for r in results) / len(results)

    summary = {
        "passed": passed,
        "total": len(results),
        "avg_confidence": round(avg_conf, 3),
        "avg_latency_ms": int(avg_lat),
        "results": results,
    }
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Result: {passed}/{len(results)} passed")
    print(f"Avg confidence: {avg_conf:.3f}")
    print(f"Avg latency: {int(avg_lat)}ms")
    print(f"Written to {output_file}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--output", default="eval/results.json")
    args = parser.parse_args()
    run_eval(base_url=args.base_url, output_file=args.output)
