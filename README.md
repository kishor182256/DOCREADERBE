# DOCREADER Backend

A production-oriented FastAPI application scaffold with a clean layered structure.

## Structure

- app/main.py - FastAPI application entrypoint
- app/api/v1 - API routers and endpoints
- app/core - application configuration
- app/schemas - Pydantic schemas
- app/services - business logic services
- tests - endpoint tests

## Run locally

1. Create and activate a virtual environment
2. Install requirements: `pip install -r requirements.txt`
3. Start the server: `uvicorn app.main:app --reload`
4. Open: http://127.0.0.1:8000/docs

## Test

Run: `pytest`
