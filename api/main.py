"""FastAPI app — streaming SSE + WebSocket HITL + ADK session lifecycle.

Session architecture:
  InMemorySessionService — per-request state, zero-config.
  VertexAiMemoryBankService — cross-session long-term memory (opt-in via env vars).
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.genai import types
from pydantic import BaseModel

from agents.orchestrator import orchestrator
from hitl.confidence_checker import parse_synthesis_output, check_confidence
from hitl.edge_approver import parse_new_edge_from_web, write_approved_edge
from hitl.feedback_handler import store_feedback as _store_feedback
from memory.services import get_session_service, get_memory_service

# ── Services ─────────────────────────────────────────────────────────────────
session_service = get_session_service()
memory_service = get_memory_service()

runner: Runner | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runner
    runner_kwargs: dict = dict(
        agent=orchestrator,
        app_name="hetionet",
        session_service=session_service,
    )
    if memory_service is not None:
        runner_kwargs["memory_service"] = memory_service
    runner = Runner(**runner_kwargs)
    yield


app = FastAPI(title="Hetionet GraphRAG", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket connection manager ─────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections keyed by user_id."""

    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections[user_id] = ws

    def disconnect(self, user_id: str) -> None:
        self.connections.pop(user_id, None)

    async def send(self, user_id: str, payload: dict) -> None:
        ws = self.connections.get(user_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(user_id)


ws_manager = ConnectionManager()


# ── Request models ────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    session_id: str | None = None


class ApproveEdgeRequest(BaseModel):
    session_id: str
    user_id: str = "anonymous"
    edge: dict
    approved: bool


class FeedbackRequest(BaseModel):
    session_id: str
    user_id: str = "anonymous"
    query: str
    answer: str
    rating: str  # 'up' or 'down'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query")
async def query_json(req: QueryRequest) -> dict[str, Any]:
    """Non-streaming query endpoint. Runs the same pipeline as /query/stream
    but returns a single JSON object. Used by the eval harness and direct API calls.
    """
    if runner is None:
        raise HTTPException(status_code=503, detail="Runner not ready")

    session_id = req.session_id or str(uuid.uuid4())
    try:
        await session_service.create_session(
            app_name="hetionet",
            user_id=req.user_id,
            session_id=session_id,
        )
    except Exception:
        pass

    final_text = ""
    try:
        async for event in runner.run_async(
            user_id=req.user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=req.query)],
            ),
        ):
            if event.is_final_response() and event.content:
                final_text = event.content.parts[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    parsed = parse_synthesis_output(final_text)
    return {
        "session_id": session_id,
        "answer": parsed["answer"],
        "confidence": parsed["confidence"],
        "sources": parsed["sources"],
        "reasoning": parsed["reasoning"],
        "needs_review": parsed["needs_review"],
        "raw": final_text,
    }


@app.post("/query/stream")
async def query_stream(req: QueryRequest) -> StreamingResponse:
    """Stream a biomedical query as Server-Sent Events.

    Events:
      {"type":"agent","name":"<agent>"}     — pipeline step activated
      {"type":"delta","text":"<chunk>"}     — synthesis partial text
      {"type":"hitl","event_type":"..."}    — low_confidence or new_edge
      {"type":"done","answer":...}          — final structured result
      {"type":"error","message":"..."}      — pipeline error
    """
    if runner is None:
        raise HTTPException(status_code=503, detail="Runner not ready")

    async def event_stream() -> AsyncGenerator[str, None]:
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        session_id = req.session_id or str(uuid.uuid4())
        try:
            await session_service.create_session(
                app_name="hetionet",
                user_id=req.user_id,
                session_id=session_id,
            )
        except Exception:
            pass  # session may already exist (resumed conversation)

        final_text = ""
        seen_agents: set[str] = set()

        try:
            async for event in runner.run_async(
                user_id=req.user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=req.query)],
                ),
            ):
                author = getattr(event, "author", None)

                # Emit active agent name (skip internal parallel_gather wrapper)
                if author and author not in seen_agents and author not in ("user", "parallel_gather"):
                    seen_agents.add(author)
                    yield sse({"type": "agent", "name": author})

                # Stream partial synthesis text
                if (
                    author == "synthesis_agent"
                    and event.content
                    and not event.is_final_response()
                ):
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield sse({"type": "delta", "text": part.text})

                # Capture final response
                if event.is_final_response() and event.content:
                    final_text = event.content.parts[0].text

        except Exception as e:
            # Python 3.11+ asyncio.TaskGroup wraps failures in ExceptionGroup
            if hasattr(e, 'exceptions') and e.exceptions:
                inner = e.exceptions[0]
                msg = f"{type(inner).__name__}: {inner}"
            else:
                msg = str(e)
            yield sse({"type": "error", "message": msg})
            return

        parsed = parse_synthesis_output(final_text)

        # HITL checkpoint 1: low confidence
        if check_confidence(parsed["confidence"], session_id, parsed["answer"], parsed["reasoning"]):
            asyncio.create_task(ws_manager.send(req.user_id, {
                "type": "low_confidence",
                "session_id": session_id,
                "confidence": parsed["confidence"],
                "answer": parsed["answer"],
                "reasoning": parsed["reasoning"],
            }))
            yield sse({"type": "hitl", "event_type": "low_confidence",
                       "confidence": parsed["confidence"]})

        # HITL checkpoint 2: new edge from web
        if parsed.get("new_edge"):
            asyncio.create_task(ws_manager.send(req.user_id, {
                "type": "new_edge",
                "session_id": session_id,
                "new_edge": parsed["new_edge"],
            }))
            yield sse({"type": "hitl", "event_type": "new_edge",
                       "new_edge": parsed["new_edge"]})

        yield sse({
            "type": "done",
            "session_id": session_id,
            "answer": parsed["answer"],
            "confidence": parsed["confidence"],
            "sources": parsed["sources"],
            "reasoning": parsed["reasoning"],
            "needs_review": parsed["needs_review"],
            "citations": parsed["citations"],
            "raw": final_text,
        })

        # Background: commit session facts to long-term memory
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/approve-edge")
async def approve_edge(req: ApproveEdgeRequest) -> dict[str, Any]:
    """Approve or reject a new edge proposed by the pipeline."""
    if not req.approved:
        return {"session_id": req.session_id, "result": "rejected"}
    edge = (
        parse_new_edge_from_web(req.edge.get("new_edge", ""))
        if isinstance(req.edge.get("new_edge"), str)
        else req.edge
    )
    if edge is None:
        raise HTTPException(status_code=400, detail="Cannot parse edge payload")
    written = write_approved_edge(edge)
    return {
        "session_id": req.session_id,
        "result": "written" if written else "nodes_not_found",
        "edge": edge,
    }


@app.post("/feedback")
async def feedback(req: FeedbackRequest) -> dict[str, Any]:
    """Store thumbs-up/down feedback for a session response."""
    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    return _store_feedback(
        session_id=req.session_id,
        query=req.query,
        answer=req.answer,
        rating=req.rating,
        user_id=req.user_id,
    )


@app.get("/benchmark/queries")
def benchmark_queries() -> dict[str, Any]:
    """Return the 15 BioHopR benchmark queries."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from eval.evaluate import BENCHMARK_QUERIES
        return {"total": len(BENCHMARK_QUERIES), "queries": BENCHMARK_QUERIES}
    except ImportError:
        return {"total": 0, "queries": [], "error": "eval/evaluate.py not found"}


@app.get("/traces/{session_id}")
async def traces(session_id: str) -> dict[str, Any]:
    """Cloud Trace spans for a session. Stub until GCP is connected."""
    return {"session_id": session_id, "spans": []}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    """WebSocket endpoint for HITL events (low_confidence, new_edge)."""
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)


# Serve the built React frontend. Mounted last so API routes take priority.
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
