"""Integration tests for ADK agents against live Hetionet (read-only).

Requires GOOGLE_API_KEY and NEO4J_* in the environment (or .env).
Run with: uv run pytest tests/test_agents.py -v
"""
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def _msg(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def _run(agent, query: str) -> str:
    """Run an agent to completion and return its final text response."""
    svc = InMemorySessionService()
    sess = await svc.create_session(app_name="test", user_id="test")
    runner = Runner(agent=agent, app_name="test", session_service=svc)
    async for event in runner.run_async(
        user_id="test",
        session_id=sess.id,
        new_message=_msg(query),
    ):
        if event.is_final_response() and event.content:
            return event.content.parts[0].text
    return ""


@pytest.mark.asyncio
async def test_cypher_agent_ibuprofen_treats_osteoarthritis():
    """cypher_agent must retrieve osteoarthritis as a disease treated by Ibuprofen.

    Validates: Hetionet TREATS_CtD relationship is traversed correctly
    and the agent returns a grounded answer (not hallucinated).
    """
    from agents.cypher_agent import cypher_agent

    response = await _run(cypher_agent, "What diseases does Ibuprofen treat?")

    assert response, "Agent returned empty response"
    assert "osteoarthritis" in response.lower(), (
        f"Expected 'osteoarthritis' in response (known TREATS_CtD fact), got:\n{response}"
    )


@pytest.mark.asyncio
async def test_cypher_agent_tnf_gene_associates_rheumatoid_arthritis():
    """cypher_agent must surface rheumatoid arthritis for the TNF gene.

    Validates: ASSOCIATES_DaG traversal from Gene to Disease works correctly.
    TNF is one of the most studied inflammatory genes; RA is a top association.
    """
    from agents.cypher_agent import cypher_agent

    response = await _run(
        cypher_agent, "What diseases are associated with the TNF gene?"
    )

    assert response, "Agent returned empty response"
    assert "rheumatoid arthritis" in response.lower(), (
        f"Expected 'rheumatoid arthritis' (TNF ASSOCIATES_DaG fact), got:\n{response}"
    )


@pytest.mark.asyncio
async def test_semantic_agent_surfaces_nsaid_for_anti_inflammatory_query():
    """semantic_agent must surface an NSAID when query is descriptive, not exact.

    Validates: 3-stage reranking (BM25 → Semantic → CrossEncoder) recovers known
    anti-inflammatory compounds without exact node name match.
    This is the primary use-case for the semantic agent — fuzzy entity disambiguation.
    """
    from agents.semantic_agent import semantic_agent

    response = await _run(
        semantic_agent,
        "Find anti-inflammatory drugs used for pain and swelling",
    )

    assert response, "Agent returned empty response"
    nsaids = ["ibuprofen", "aspirin", "naproxen", "celecoxib", "diclofenac", "indomethacin"]
    assert any(drug in response.lower() for drug in nsaids), (
        f"Expected at least one NSAID in semantic results, got:\n{response}"
    )
