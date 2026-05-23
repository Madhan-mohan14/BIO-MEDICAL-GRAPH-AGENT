# Biomedical Graph RAG Agent

A multi-agent biomedical question-answering system built on Google ADK, Neo4j (Hetionet v1.0), and Gemini 2.0 Flash.

Ask questions like *"What diseases does Ibuprofen treat?"* or *"What genes does Metformin bind?"* — the system queries a knowledge graph, runs semantic vector search, supplements with web search, and synthesizes a grounded answer with confidence scoring.

## Architecture

```
React UI (frontend/)
    ↕ SSE /query/stream  |  WebSocket /ws/{user_id}  |  REST
FastAPI (api/main.py)
    ↓ Google ADK Runner
SequentialAgent — orchestrator
    ├── ParallelAgent (run concurrently)
    │   ├── cypher_agent    → Cypher queries on Hetionet graph
    │   ├── semantic_agent  → 3-stage vector reranking (BM25 → Semantic → CrossEncoder)
    │   └── web_agent       → Google Search for post-2016 findings
    └── synthesis_agent     → merges all three → structured answer
HITL layer
    confidence < 0.70 → WebSocket alert → human review
    NEW_EDGE detected → /approve-edge → Neo4j write
```

## Dataset

**Hetionet v1.0** — expert-curated biomedical knowledge graph:
- 47,031 nodes across 11 types (Disease, Compound, Gene, Symptom, Anatomy, Side Effect, Biological Process, Cellular Component, Molecular Function, Pathway, Pharmacologic Class)
- 388,154 relationships across 11 types (TREATS, PALLIATES, ASSOCIATES, BINDS, CAUSES, PRESENTS, RESEMBLES, LOCALIZES, INCLUDES, COVARIES, INTERACTS)
- 768-dim node embeddings (all-mpnet-base-v2) stored in Neo4j vector index

## Retrieval Pipeline

```
Query
  ↓ Cypher traversal (graph path reasoning, multi-hop)
  ↓ Vector search → BM25 top-50 → Semantic cosine top-20 → CrossEncoder top-10
  ↓ Web search (Google Search, post-2016 recency)
  ↓ Synthesis + confidence scoring
  ↓ HITL gate (confidence < 0.70)
  → Streamed answer
```

## Stack

| Layer | Technology |
|---|---|
| Agents | Google ADK (SequentialAgent, ParallelAgent) |
| LLM | Gemini 2.0 Flash |
| Graph DB | Neo4j AuraDB (Hetionet v1.0) |
| Embeddings | sentence-transformers/all-mpnet-base-v2 |
| Reranking | rank-bm25 + cosine similarity + ms-marco-MiniLM-L-6-v2 |
| API | FastAPI + SSE streaming + WebSocket |
| Frontend | React 18 + Vite + react-force-graph (3D) |
| Eval | RAGAS (faithfulness, relevancy, recall, precision) + BioHopR 15-query benchmark |
| Deploy | Docker + GitHub Actions → Cloud Run |

## Setup

```bash
# 1. Clone and create environment
git clone https://github.com/Madhan-mohan14/BIO-MEDICAL-GRAPH-AGENT.git
cd BIO-MEDICAL-GRAPH-AGENT
uv venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in GOOGLE_API_KEY and NEO4J_* credentials

# 3. Load data (one-time, ~40 min total)
uv run python data/download_hetionet.py
uv run python data/load_neo4j.py
uv run python data/generate_embeddings.py

# 4. Start API server
uv run uvicorn api.main:app --reload --port 8080

# 5. Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key (aistudio.google.com) |
| `GOOGLE_ADK_MODEL` | Yes | Default: `gemini-2.0-flash` |
| `NEO4J_URI` | Yes | AuraDB URI or `bolt://neo4j.het.io` (public read-only) |
| `NEO4J_USERNAME` | Yes | Neo4j username |
| `NEO4J_PASSWORD` | Yes | Neo4j password |
| `DATABASE_URL` | Cloud only | Cloud SQL Postgres for session persistence |
| `GOOGLE_CLOUD_PROJECT` | Cloud only | GCP project ID |
| `MCP_TOOLBOX_URL` | Optional | Enables MCP Toolbox for cypher_agent |

## Running Evals

```bash
# BioHopR 15-query benchmark (requires running API)
uv run python eval/evaluate.py

# RAGAS retrieval quality audit (Groq LLM-as-judge)
uv run python eval/ragas_eval.py
```

## API Routes

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/query/stream` | SSE streaming pipeline |
| POST | `/query` | Non-streaming JSON response |
| POST | `/approve-edge` | HITL: write approved web-discovered edge to Neo4j |
| POST | `/feedback` | Store thumbs-up/down rating |
| GET | `/benchmark/queries` | 15 BioHopR eval queries |
| WS | `/ws/{user_id}` | HITL push events |

## Project Structure

```
agents/          Google ADK agents (orchestrator, cypher, semantic, web, synthesis)
api/             FastAPI server with SSE + WebSocket
data/            Hetionet ingestion scripts (download, load, embed)
eval/            RAGAS + BioHopR evaluation harness
frontend/        React + Vite UI with 3D force graph
hitl/            Human-in-the-loop (confidence checker, edge approver, feedback)
memory/          Session service + VertexAI long-term memory
retrieval/       3-stage reranking pipeline (BM25, semantic, CrossEncoder)
safety/          Gemini-as-judge callback (blocks personal medical advice)
tests/           Unit + integration tests
tools/           Neo4j tool functions (read-only)
```
