"""semantic_agent — vector similarity search over Hetionet node embeddings."""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from retrieval.search_and_rerank import search_and_rerank

semantic_agent = Agent(
    name="semantic_agent",
    model=os.environ["GOOGLE_ADK_MODEL"],
    output_key="semantic_results",
    description=(
        "Finds biomedical entities by semantic similarity using Neo4j vector search + 3-stage "
        "reranking (BM25 -> Semantic -> CrossEncoder). Use when the user's query contains "
        "approximate or descriptive terms — e.g. 'anti-inflammatory drug' instead of 'Ibuprofen'."
    ),
    instruction=(
        "You perform semantic similarity search over the Hetionet biomedical knowledge graph "
        "using pre-computed all-mpnet-base-v2 vectors stored in a Neo4j vector index.\n\n"
        "Tool available:\n"
        "- search_and_rerank(query, top_k): retrieves top-50 candidates by vector similarity, "
        "  then reranks through BM25 -> Semantic cosine -> CrossEncoder. Returns up to top_k "
        "  results. Each result has: identifier, kind, name, score, text, cross_encoder_score.\n\n"
        "When to use:\n"
        "- The user describes a concept (e.g. 'drugs for inflammation') rather than an exact name\n"
        "- Exact Cypher lookups return 0 results (possible name mismatch)\n"
        "- The user asks 'what is similar to X' or 'find entities related to Y'\n\n"
        "Workflow:\n"
        "1. Call search_and_rerank with the user's query or a refined version of it.\n"
        "2. Report the top results (identifier, kind, name, cross_encoder_score).\n"
        "3. Suggest which exact names from the results could be used in follow-up Cypher queries.\n\n"
        "Do NOT attempt to traverse the graph or answer multi-hop questions — "
        "pass those to cypher_agent. Your role is entity discovery and name disambiguation."
    ),
    tools=[search_and_rerank],
)
