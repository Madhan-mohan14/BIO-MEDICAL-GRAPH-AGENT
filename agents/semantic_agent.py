"""semantic_agent — vector similarity search over Hetionet node and chunk embeddings."""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from retrieval.search_and_rerank import search_and_rerank
from tools.neo4j_tools import search_chunks

semantic_agent = Agent(
    name="semantic_agent",
    model=os.environ["GOOGLE_ADK_MODEL"],
    output_key="semantic_results",
    description=(
        "Finds biomedical entities and research paper passages by semantic similarity. "
        "Uses 3-stage reranking (BM25 -> Semantic -> CrossEncoder) over Hetionet node "
        "embeddings and PubMed chunk embeddings. Use when the query uses approximate or "
        "descriptive terms — e.g. 'anti-inflammatory drug' instead of 'Ibuprofen'."
    ),
    instruction=(
        "You perform semantic similarity search over two indexes:\n"
        "1. Hetionet graph nodes (Disease, Compound, Gene, etc.) — for entity disambiguation.\n"
        "2. PubMed paper chunks (Chunk nodes) — for evidence from literature.\n\n"
        "Tools available:\n"
        "- search_and_rerank(query, top_k): searches Hetionet node embeddings, reranks "
        "  through BM25 -> Semantic cosine -> CrossEncoder. Returns results with: "
        "  identifier, kind, name, score, cross_encoder_score.\n"
        "- search_chunks(query, top_k): searches PubMed Chunk nodes by vector similarity. "
        "  Returns results with: chunk_id, text, pmid, title, source, score.\n\n"
        "When to use each tool:\n"
        "- search_and_rerank: entity disambiguation, 'what is X', 'find drugs for Y'\n"
        "- search_chunks: 'what does the literature say about X', 'recent research on Y'\n\n"
        "Workflow:\n"
        "1. Call search_and_rerank for entity-level results.\n"
        "2. Optionally call search_chunks if literature evidence is relevant.\n"
        "3. Report top results and suggest exact names for follow-up Cypher queries.\n\n"
        "Do NOT traverse the graph or answer multi-hop questions — "
        "pass those to cypher_agent. Your role is entity discovery and literature lookup."
    ),
    tools=[search_and_rerank, search_chunks],
)
