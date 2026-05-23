"""Integration tests for agents against real Hetionet (read-only)."""
import pytest


@pytest.mark.asyncio
async def test_graph_db_agent_ibuprofen():
    """graph_db_agent should return diseases for ibuprofen without hallucinating."""
    pass  # implement after graph_db_agent.py is complete
