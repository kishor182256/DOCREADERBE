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

Use Python 3.11 or 3.12 for this project. Do not use Python 3.14 yet because some OCR dependencies, especially PyMuPDF, may not have compatible prebuilt Windows wheels and will try to compile from source.

```powershell
cd C:\DOCREADER\BACKEND
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Open: http://127.0.0.1:8000/docs

If `.venv` was already created with Python 3.14, remove or rename it first:

```powershell
cd C:\DOCREADER\BACKEND
Rename-Item .venv .venv-py314-broken
py -3.11 -m venv .venv
```

## Test

Run: `pytest`
