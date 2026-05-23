"""orchestrator — parallel data gathering (Cypher + semantic + web) then synthesis.

Architecture:
  SequentialAgent
  ├── ParallelAgent  — cypher_agent + semantic_agent + web_agent run concurrently
  │     Each saves its output to a session state key via output_key.
  └── synthesis_agent — reads {cypher_results}, {semantic_results}, {web_results}
                        from session state via template placeholders.
"""
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import ParallelAgent, SequentialAgent

from agents.cypher_agent import cypher_agent
from agents.semantic_agent import semantic_agent
from agents.web_agent import web_agent
from agents.synthesis_agent import synthesis_agent

# Fan-out: all three data agents run concurrently.
# Each stores results via output_key → session state.
parallel_gather = ParallelAgent(
    name="parallel_gather",
    description=(
        "Runs Cypher graph queries, semantic vector search, and web search concurrently. "
        "Results are saved to session state for synthesis_agent."
    ),
    sub_agents=[cypher_agent, semantic_agent, web_agent],
)

# Root agent: gather in parallel, then synthesize.
orchestrator = SequentialAgent(
    name="biomedical_orchestrator",
    description=(
        "Biomedical GraphRAG pipeline over Hetionet (47K nodes, 388K relationships). "
        "Runs parallel Cypher + semantic + web search, then synthesizes a structured answer."
    ),
    sub_agents=[parallel_gather, synthesis_agent],
)
