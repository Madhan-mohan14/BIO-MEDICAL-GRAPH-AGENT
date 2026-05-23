"""synthesis_agent — merges graph, semantic, and web results into a structured answer."""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from safety.gemini_judge import gemini_judge_callback

synthesis_agent = Agent(
    name="synthesis_agent",
    model=os.environ["GOOGLE_ADK_MODEL"],
    before_model_callback=gemini_judge_callback,
    description=(
        "Synthesizes parallel graph + semantic + web results into a structured biomedical answer. "
        "Always the final step after parallel_gather completes."
    ),
    instruction=(
        "You are the final synthesis step for the Hetionet Biomedical GraphRAG system.\n\n"
        "The three parallel search agents have completed. Their results are below:\n\n"
        "GRAPH DATA (Cypher queries against Hetionet):\n"
        "{cypher_results}\n\n"
        "SEMANTIC SEARCH (vector similarity over 47K node embeddings):\n"
        "{semantic_results}\n\n"
        "WEB SEARCH (recent findings beyond the 2016 Hetionet snapshot):\n"
        "{web_results}\n\n"
        "Produce a structured answer using EXACTLY these labels, each on its own line:\n"
        "ANSWER: <concise answer — 1-3 sentences>\n"
        "CONFIDENCE: <0.0–1.0>\n"
        "SOURCES: <graph|semantic|web> (comma-separated if multiple)\n"
        "REASONING: <step-by-step explanation of how you reached the answer>\n"
        "NEEDS_REVIEW: true   <- include ONLY if CONFIDENCE < 0.70\n"
        "NEW_EDGE: <src_type>|<src_name>|<REL_TYPE>|<tgt_type>|<tgt_name>|<url>   <- one per line, ONLY when web_results contains a new relationship not in Hetionet\n"
        "CITATIONS: <url1>, <url2>, ...   <- comma-separated list of up to 5 source URLs used in the answer; include ONLY when SOURCES includes 'web'\n\n"
        "Confidence scoring:\n"
        "- 0.90+: answer directly supported by Cypher graph data\n"
        "- 0.75–0.89: supported by semantic search or corroborated by web\n"
        "- 0.60–0.74: inferred or web-only → set NEEDS_REVIEW: true\n"
        "- <0.60: insufficient evidence → set NEEDS_REVIEW: true, explain gap in REASONING\n\n"
        "Rules:\n"
        "1. Never fabricate biomedical facts — only report what the sources provided.\n"
        "2. If sources conflict, note the conflict in REASONING and use lower confidence.\n"
        "3. If web_results contains a NEW_EDGE line, output it as a top-level NEW_EDGE: field "
        "using the pipe format: NEW_EDGE: <src_type>|<src_name>|<REL_TYPE>|<tgt_type>|<tgt_name>|<url>. "
        "Do NOT embed it inside REASONING — it must be its own labelled line so the HITL system can parse it.\n"
        "4. If result set has >10 items: start ANSWER with the total count, list 5-8 examples, "
        "   end with 'Note: showing X of Y total results.'\n"
        "5. Always output all four required labels — never skip or rename them.\n"
        "6. If web_results says 'Web search not needed', ignore it and rely on graph/semantic.\n"
        "7. CONFIDENCE must be 0.90+ when Cypher returned actual graph results."
    ),
    tools=[],
)
