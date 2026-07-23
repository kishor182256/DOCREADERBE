# Enterprise Multimodal Document Intelligence Platform

## Project Vision

Enterprise Multimodal Document Intelligence Platform, or EMDIP, is a production-quality backend for understanding and reasoning over enterprise documents using modern AI techniques.

The long-term platform will support OCR, document understanding, knowledge graphs, vector search, Graph-RAG, LLM-based question answering, human feedback, LoRA dataset preparation, and multimodal inputs such as PDFs, images, and audio.

The system must be built incrementally. Each phase should be functional, testable, and maintainable before the next phase begins.

## Development Philosophy

Do not build the full platform at once.

Build one phase at a time. Keep each phase small, useful, and complete. Avoid placeholder abstractions unless they protect an immediate implementation boundary.

Code should remain clean, modular, testable, and extensible. Business logic belongs in services, not routers.

## Current MVP Constraints

The current MVP supports:

- Localhost
- Single user
- FastAPI
- SQLite
- Local file storage
- Synchronous request handling

The current MVP deliberately excludes:

- Authentication
- Docker runtime requirements
- Kubernetes
- Kafka
- Celery or background workers
- Cloud deployment
- Distributed architecture

Future local integrations may include Ollama, Neo4j, and Qdrant, but they must be added only when their phase begins.

## Target Architecture

The eventual document intelligence flow is:

1. Upload Document
2. OCR
3. Document Classification
4. Entity Extraction
5. Validation
6. Structured JSON
7. Embeddings
8. Qdrant
9. Knowledge Graph with Neo4j
10. Graph-RAG
11. LLM Question Answering
12. Human Feedback
13. LoRA Dataset Preparation

## Current Backend Structure

```text
app/
  api/
    v1/
      endpoints/
      api.py
  core/
  database/
  models/
  repositories/
  schemas/
  services/
  main.py
alembic/
uploads/
docs/
```

## Coding Standards

- Python 3.12
- FastAPI
- SQLAlchemy 2
- Pydantic v2
- Clean architecture
- Dependency injection
- Repository pattern
- Service layer
- Strong typing
- Small reusable modules
- One clear responsibility per module

Routers should coordinate HTTP concerns only. Services own business logic. Repositories own persistence operations. Schemas define request and response contracts. Models define database tables.

## Phase Roadmap

### Phase 1: Project Setup

Status: implemented.

Includes FastAPI, SQLite, SQLAlchemy, project settings, application startup, and health endpoint.

### Phase 2: Upload Service

Status: implemented.

Includes document upload through `POST /api/v1/documents/upload`, local file storage, SQLite metadata persistence, and duplicate-content protection.

### Phase 3: OCR

Status: not started.

Next phase should add OCR only. Do not add classification, extraction, embeddings, Qdrant, Neo4j, or LLM features during this phase.

### Future Phases

Phase 4: Document Classification

Phase 5: Entity Extraction

Phase 6: Validation

Phase 7: Embeddings

Phase 8: Qdrant

Phase 9: Neo4j

Phase 10: Graph-RAG

Phase 11: LLM Chat

Phase 12: Human Feedback

Phase 13: LoRA Dataset Preparation

## Implementation Rule

Before each phase begins, explain:

1. Architecture for that phase
2. Why it fits this backend
3. Folder/module changes
4. Testing approach

Then implement only that phase.

After each phase, verify locally and wait for approval before moving to the next phase.
