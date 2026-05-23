"""Entry point for adk web / adk run.

Run from project root:
    adk web          # opens browser UI at localhost:8000
    adk run agent    # CLI mode

For local uvicorn (API server):
    uv run uvicorn api.main:app --reload --port 8080
"""
from agents.orchestrator import orchestrator

# ADK discovers the root agent by looking for `root_agent` in this file.
root_agent = orchestrator
