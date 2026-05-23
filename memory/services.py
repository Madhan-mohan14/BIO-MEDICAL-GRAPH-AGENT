"""Memory service factory.

Short-term (per-session state): InMemorySessionService — zero-config, fast.
Long-term (cross-session): VertexAiMemoryBankService — uses Agent Engine.
  Returns None if VERTEX_AI_AGENT_ENGINE_ID not set; Runner degrades gracefully.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_session_service():
    """Return InMemorySessionService for short-term session state.

    Returns:
        InMemorySessionService instance.
    """
    from google.adk.sessions import InMemorySessionService
    return InMemorySessionService()


def get_memory_service():
    """Return VertexAiMemoryBankService if configured, else None.

    Args: none — reads VERTEX_AI_AGENT_ENGINE_ID, GOOGLE_CLOUD_PROJECT,
        GOOGLE_CLOUD_LOCATION from environment.

    Returns:
        VertexAiMemoryBankService instance, or None if not configured.
    """
    engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not engine_id or not project:
        return None
    try:
        from google.adk.memory import VertexAiMemoryBankService
        resource_name = (
            f"projects/{project}/locations/{location}/reasoningEngines/{engine_id}"
        )
        return VertexAiMemoryBankService(reasoning_engine_resource_name=resource_name)
    except Exception:
        return None
