# Bulk Certificate Generator API (`certgen`)

A high-performance backend REST API for bulk certificate generation built with **Python 3.12**, **FastAPI**, **SQLAlchemy 2.0 (Relational DB)**, and **ReportLab**.

The system enables organizations to submit bulk certificate generation jobs (up to 1,000 recipients per request), tracks real-time per-job and per-recipient status, isolates individual recipient failures, and provides individual PDF downloads as well as bulk ZIP archive exports.

---

## Technology Stack

- **Language:** Python 3.12 (managed via `uv`)
- **Web Framework:** FastAPI (with Pydantic v2 validation and auto-generated Swagger UI docs)
- **Database:** Relational Database via SQLAlchemy 2.0 (SQLite in WAL mode for zero-setup local evaluation, PostgreSQL-ready)
- **PDF Generation Engine:** ReportLab
- **Testing & Quality:** Pytest, HTTPX, PyPDF, Ruff

---

## Quickstart

### Prerequisites
Install `uv` (modern Python package manager):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 1. Setup Environment
```bash
uv sync
```

### 2. Run the Development Server
```bash
uv run uvicorn certgen.main:app --reload
```
- Interactive Swagger API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 3. Run Test Suite
```bash
uv run pytest
```

### 4. Code Formatting & Linting
```bash
uv run ruff check src tests
uv run ruff format src tests
```
