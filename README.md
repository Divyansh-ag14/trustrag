# TrustRAG

TrustRAG is a production-grade RAG platform for enterprise knowledge — built for support, sales engineering, technical account management, and compliance teams that need grounded, source-cited answers over fragmented internal knowledge, not another PDF chatbot.

It combines hybrid retrieval, reranking, citation validation, and hallucination checks with a full evaluation and observability layer, so answer quality is measurable and failures turn into tracked knowledge gaps instead of silent misses.

## Features

- **Multi-source ingestion** — document uploads plus connectors for GitHub, Notion, and web sources
- **Hybrid retrieval** — vector search (Qdrant) fused with keyword search and reranked via Cohere
- **Grounded generation** — context construction with token budgeting, citation formatting, and citation validation
- **Trust checks** — hallucination detection and low-confidence fallback before an answer ships
- **Evaluation layer** — golden datasets, evaluation runs, and retrieval/answer quality metrics
- **Feedback & knowledge gaps** — failed or weak answers are tracked and routed for admin review
- **Observability** — request tracing, latency breakdown, token usage, and cost tracking per query
- **Admin workflows** — document management, evaluation review, and feedback triage
- **Streaming chat** — server-sent events for real-time answer streaming in the UI

## Architecture

**Backend** — FastAPI, async SQLAlchemy, Alembic, Pydantic v2, PostgreSQL, Qdrant, Redis, Celery

**Frontend** — Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts, Zustand

**RAG/ML** — OpenAI (generation + embeddings), Cohere Rerank, custom evaluation metrics

**Infra** — Docker Compose for local development, Nginx reverse proxy for production-like setups

## Project structure

```
backend/
  app/
    api/routes/     # auth, chat, documents, evaluation, feedback, knowledge_gaps, admin, analytics, connectors
    rag/             # query understanding, retrieval, reranking, context building, generation, citation/hallucination checks
    ingestion/       # document parsing and chunking
    connectors/      # GitHub, Notion, web scraper
    evaluation/       # evaluation metrics and runs
    models/          # SQLAlchemy models
    schemas/         # Pydantic schemas
    workers/         # background jobs
  alembic/           # database migrations
frontend/
  src/
    app/             # Next.js app router (auth + dashboard routes)
    components/      # chat, documents, connectors, layout, ui
    stores/          # Zustand state
    lib/             # typed API client
```

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker

### Setup

```bash
git clone <repo-url>
cd production-rag-pipeline
cp backend/.env.example backend/.env
```

Fill in `OPENAI_API_KEY` and `COHERE_API_KEY` in `backend/.env`, then:

```bash
make setup
```

This starts Postgres, Qdrant, and Redis via Docker Compose and runs database migrations.

### Run the app

In separate terminals:

```bash
make backend
```

```bash
make frontend
```

- Backend API: `http://localhost:8001` (docs at `/docs`)
- Frontend: `http://localhost:3000`

### Other useful commands

```bash
make seed   # load sample data and the golden evaluation set
make eval   # trigger an evaluation run
make test   # run backend tests
make clean  # stop infrastructure
```

## Configuration

All configuration is environment-based — see `backend/.env.example` for the full list, including database/vector store/cache URLs, LLM and embedding model selection, chunking and retrieval tuning, upload limits, and rate limiting. No secrets are hardcoded.
