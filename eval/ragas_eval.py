"""Standalone RAGAS retrieval quality audit — Groq LLM judge, Neo4j context.

Uses legacy ragas.metrics singletons (faithfulness, answer_relevancy, context_recall,
context_precision) which satisfy the ragas.evaluate() isinstance(m, Metric) type check.
The newer ragas.metrics.collections classes are SimpleBaseMetric and fail that check.

LLM judge: Groq llama-3.1-8b-instant via LangchainLLMWrapper(ChatGroq(...)).
Embeddings: sentence-transformers/all-MiniLM-L6-v2 (local, no API key required).
Neo4j: falls back from AuraDB to public Hetionet bolt://neo4j.het.io automatically.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()

# AuraDB Free pauses after inactivity — fall back to public Hetionet if URI is not set
if not os.environ.get("NEO4J_URI"):
    os.environ["NEO4J_URI"] = "bolt://neo4j.het.io"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "neo4j"

from groq import Groq
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings as LCHFEmbeddings
from ragas import evaluate, EvaluationDataset
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
# Legacy metric singletons — these ARE ragas.metrics.base.Metric instances.
# The new ragas.metrics.collections classes are SimpleBaseMetric and fail the
# isinstance(m, Metric) check in ragas.evaluate().
from ragas.metrics import (  # noqa: E402  (import after env setup intentional)
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)

from tools.neo4j_tools import _run_cypher_params

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = "llama-3.1-8b-instant"


# ── Direct Cypher using public Hetionet relationship type names ────────────────

def fetch_compound_diseases(compound: str) -> list[dict]:
    """Get diseases treated or palliated by a compound.

    Args:
        compound: Title-case compound name (e.g. 'Ibuprofen').

    Returns:
        List of dicts with keys: disease, rel.
    """
    return _run_cypher_params(
        "MATCH (c:Compound {name:$n})-[r:TREATS_CtD|PALLIATES_CpD]-(d:Disease) "
        "RETURN d.name AS disease, type(r) AS rel",
        {"n": compound},
    )


def fetch_gene_diseases(gene: str) -> list[dict]:
    """Get diseases associated with a gene symbol.

    Args:
        gene: UPPERCASE gene symbol (e.g. 'TNF').

    Returns:
        List of dicts with key: disease.
    """
    return _run_cypher_params(
        "MATCH (g:Gene {name:$n})-[:ASSOCIATES_DaG]-(d:Disease) "
        "RETURN d.name AS disease",
        {"n": gene},
    )


def fetch_compound_side_effects(compound: str) -> list[dict]:
    """Get side effects caused by a compound.

    Args:
        compound: Title-case compound name (e.g. 'Aspirin').

    Returns:
        List of dicts with key: side_effect.
    """
    return _run_cypher_params(
        "MATCH (c:Compound {name:$n})-[:CAUSES_CcSE]-(se:`Side Effect`) "
        "RETURN se.name AS side_effect",
        {"n": compound},
    )


def fetch_compound_bound_genes(compound: str) -> list[dict]:
    """Get genes bound by a compound.

    Args:
        compound: Title-case compound name (e.g. 'Ibuprofen').

    Returns:
        List of dicts with key: gene.
    """
    return _run_cypher_params(
        "MATCH (c:Compound {name:$n})-[:BINDS_CbG]-(g:Gene) "
        "RETURN g.name AS gene",
        {"n": compound},
    )


def fetch_disease_symptoms(disease: str) -> list[dict]:
    """Get symptoms presented by a disease.

    Args:
        disease: Lowercase disease name (e.g. 'osteoarthritis').

    Returns:
        List of dicts with key: symptom.
    """
    return _run_cypher_params(
        "MATCH (d:Disease {name:$n})-[:PRESENTS_DpS]-(s:Symptom) "
        "RETURN s.name AS symptom",
        {"n": disease},
    )


# ── 5-question RAGAS eval set ─────────────────────────────────────────────────

RAGAS_QUESTIONS = [
    {
        "question": "What diseases does Ibuprofen treat?",
        "retrieve": lambda: fetch_compound_diseases("Ibuprofen"),
        "ground_truth": (
            "Ibuprofen treats or palliates osteoarthritis and pain-related conditions "
            "such as headache and backache."
        ),
    },
    {
        "question": "What diseases are associated with the TNF gene?",
        "retrieve": lambda: fetch_gene_diseases("TNF"),
        "ground_truth": (
            "The TNF gene is associated with rheumatoid arthritis, Crohn's disease, "
            "ankylosing spondylitis, and many other inflammatory conditions."
        ),
    },
    {
        "question": "What side effects does Aspirin cause?",
        "retrieve": lambda: fetch_compound_side_effects("Aspirin"),
        "ground_truth": (
            "Aspirin causes side effects including peptic ulcer, gastrointestinal "
            "bleeding, nausea, and heartburn."
        ),
    },
    {
        "question": "What genes does Ibuprofen bind?",
        "retrieve": lambda: fetch_compound_bound_genes("Ibuprofen"),
        "ground_truth": (
            "Ibuprofen binds PTGS1 (COX-1) and PTGS2 (COX-2), prostaglandin-endoperoxide "
            "synthase enzymes involved in pain and inflammation."
        ),
    },
    {
        "question": "What symptoms does osteoarthritis present with?",
        "retrieve": lambda: fetch_disease_symptoms("osteoarthritis"),
        "ground_truth": (
            "Osteoarthritis presents with symptoms including joint pain, stiffness, "
            "swelling, and reduced range of motion."
        ),
    },
]


# ── Groq answer generation ────────────────────────────────────────────────────

_groq_client = Groq(api_key=GROQ_API_KEY)


def generate_answer(question: str, context: str) -> str:
    """Generate a concise factual answer from Neo4j context using Groq.

    Args:
        question: Natural-language biomedical question.
        context: JSON-serialised Neo4j result rows.

    Returns:
        Concise answer string grounded solely in the provided context.
    """
    resp = _groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a biomedical assistant. Answer using ONLY the provided context. "
                    "Be concise and factual. Do not hallucinate."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0,
        max_tokens=256,
    )
    return resp.choices[0].message.content.strip()


# ── BioHopR keyword-match benchmark (pure retrieval, no LLM judge) ────────────

BIOHOPB_QUESTIONS = [
    {
        "question": "What diseases does Ibuprofen treat?",
        "retrieve": lambda: fetch_compound_diseases("Ibuprofen"),
        "expected": ["osteoarthritis"],
    },
    {
        "question": "What diseases are associated with the TNF gene?",
        "retrieve": lambda: fetch_gene_diseases("TNF"),
        "expected": ["rheumatoid arthritis", "crohn"],
    },
    {
        "question": "What side effects does Aspirin cause?",
        "retrieve": lambda: fetch_compound_side_effects("Aspirin"),
        "expected": ["peptic ulcer"],
    },
    {
        "question": "What genes does Ibuprofen bind?",
        "retrieve": lambda: fetch_compound_bound_genes("Ibuprofen"),
        "expected": ["PTGS1", "PTGS2"],
    },
    {
        "question": "What symptoms does osteoarthritis present with?",
        "retrieve": lambda: fetch_disease_symptoms("osteoarthritis"),
        "expected": ["joint pain"],
    },
]


def run_biohopR_benchmark() -> dict:
    """Run keyword-match recall over raw Neo4j results (no LLM judge).

    Returns:
        Dict with passed count, total, pct, and per-question results.
    """
    print("\n=== BioHopR Keyword-Match Benchmark (pure Neo4j retrieval) ===")
    results = []
    for bq in BIOHOPB_QUESTIONS:
        rows = bq["retrieve"]()
        context_text = json.dumps(rows).lower()
        missing = [kw for kw in bq["expected"] if kw.lower() not in context_text]
        passed = len(missing) == 0
        status = "PASS" if passed else f"FAIL (missing: {missing})"
        print(f"  [{status}] {bq['question'][:62]}")
        results.append({
            "question": bq["question"],
            "passed": passed,
            "missing": missing,
            "rows_retrieved": len(rows),
        })

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    pct = round(100 * passed_count / total)
    print(f"\n  Result: {passed_count}/{total} passed ({pct}%)")
    return {"passed": passed_count, "total": total, "pct": pct, "results": results}


# ── RAGAS evaluation ──────────────────────────────────────────────────────────

def run_ragas_eval() -> dict:
    """Run RAGAS on 5 biomedical questions with Groq as LLM judge.

    Uses legacy ragas.metrics singletons (faithfulness, answer_relevancy,
    context_recall, context_precision) with LangchainLLMWrapper(ChatGroq).

    Returns:
        Dict of metric_name -> float score (mean over 5 samples).
    """
    print("\n=== RAGAS Retrieval Quality Audit (Groq llama-3.1-8b-instant as judge) ===")

    # LLM judge: Groq via LangChain wrapper (BaseRagasLLM subclass)
    chat_llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0)
    ragas_llm = LangchainLLMWrapper(chat_llm)

    # Local embeddings for answer_relevancy — no API key required
    print("  Loading sentence-transformers/all-MiniLM-L6-v2 embeddings (local)...")
    hf_emb = LCHFEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    ragas_emb = LangchainEmbeddingsWrapper(hf_emb)

    # Inject judge LLM + embeddings into the legacy metric singletons
    faithfulness.llm = ragas_llm
    context_recall.llm = ragas_llm
    context_precision.llm = ragas_llm
    answer_relevancy.llm = ragas_llm
    answer_relevancy.embeddings = ragas_emb

    # Build dataset: retrieve context, generate Groq answer, record ground truth
    samples = []
    for bq in RAGAS_QUESTIONS:
        print(f"  Retrieving + generating for: {bq['question'][:55]}...")
        rows = bq["retrieve"]()
        context_str = json.dumps(rows, indent=2) if rows else "No results found in graph."
        answer = generate_answer(bq["question"], context_str)
        # EvaluationDataset.from_list expects these exact field names (RAGAS 0.4.x)
        samples.append({
            "user_input": bq["question"],
            "retrieved_contexts": [context_str],
            "response": answer,
            "reference": bq["ground_truth"],
        })

    dataset = EvaluationDataset.from_list(samples)

    print("\n  Running RAGAS metrics (faithfulness, answer_relevancy, context_recall, context_precision)...")
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        raise_exceptions=False,
        show_progress=True,
    )
    df = result.to_pandas()

    metric_cols = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    scores: dict[str, float | None] = {}
    for col in metric_cols:
        if col in df.columns:
            scores[col] = round(float(df[col].mean(skipna=True)), 4)
        else:
            scores[col] = None

    print("\n  RAGAS Scores (mean over 5 samples):")
    for k, v in scores.items():
        display = f"{v:.4f}" if v is not None else "N/A"
        print(f"    {k:<25} {display}")

    return scores


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    biohopR = run_biohopR_benchmark()
    ragas_scores = run_ragas_eval()

    output = {"biohopR": biohopR, "ragas": ragas_scores}
    out_path = os.path.join(os.path.dirname(__file__), "ragas_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 55)
    print("FINAL SUMMARY")
    print("=" * 55)
    print(f"  BioHopR retrieval:   {biohopR['passed']}/{biohopR['total']} passed ({biohopR['pct']}%)")
    print(f"  faithfulness:        {ragas_scores.get('faithfulness', 'n/a')}")
    print(f"  answer_relevancy:    {ragas_scores.get('answer_relevancy', 'n/a')}")
    print(f"  context_recall:      {ragas_scores.get('context_recall', 'n/a')}")
    print(f"  context_precision:   {ragas_scores.get('context_precision', 'n/a')}")
    print(f"\nResults saved to {out_path}")
