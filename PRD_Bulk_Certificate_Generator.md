# PRD — Bulk Certificate Generator (Backend API)

| | |
|---|---|
| **Document status** | Draft v1.0 — ready for planning |
| **Project type** | Backend take-home assignment (interview follow-up expected) |
| **Language / env** | Python 3.12, managed with **uv** |
| **Framework (chosen)** | FastAPI |
| **Database (chosen)** | SQLite via SQLAlchemy 2.0 (Postgres-ready) |
| **PDF engine (chosen)** | ReportLab |

> **How to use this document:** Sections 1–5 explain *what* and *why*. Sections 6–15 are the *technical spec*. Section 17 is the *step-by-step build plan* with checkboxes. Section 18 is the *Definition of Done*. Section 19 prepares you for the *interview*. Every requirement has an ID (e.g. `FR-12`) so you can reference it in commits, tests, and the README.

---

## 1. Overview

### 1.1 Problem
An organization finishes an event or course and needs to issue certificates to hundreds or thousands of participants. Doing this one API call at a time is slow, error-prone, and hard to track.

### 1.2 Solution
A backend REST API where a client submits **one request containing many recipients**. The system:

1. Validates the request and each recipient.
2. Creates a **job** and one **certificate record per recipient**.
3. Generates a PDF per valid recipient from **one fixed template**.
4. Tracks per-certificate and per-job status, so the client can poll progress.
5. Lets the client **download individual certificates** or **all of them as a ZIP**.

### 1.3 Source assignment (summary of the given brief)
- Python + one of FastAPI / Django REST / Flask + a relational DB.
- Bulk generation (not one API call per certificate).
- One predefined template; no template editor.
- Invalid data handled appropriately; one failure must not block the others.
- Job status must identify successes and failures.
- Sync vs background processing is our choice, **but the reasoning must be documented**.
- Tests for: job creation, input validation, certificate generation, job status/progress, individual failure handling, certificate retrieval.
- README: setup, run, test, submit request, retrieve certificates, design decisions.
- AI tools allowed, **but we must be able to explain and modify every line in the interview** (debugging live, handling a changed requirement).

---

## 2. Goals and Non-Goals

### 2.1 Goals
| ID | Goal |
|---|---|
| G1 | Fully satisfy every **required** item in the assignment, with clean, readable code. |
| G2 | Make the design **simple enough to explain in 5 minutes** and **easy to modify live**. |
| G3 | Make partial failure a first-class concept (per-certificate status + error reason). |
| G4 | Be honest about trade-offs: document why background tasks (not Celery) were chosen and when that stops being enough. |
| G5 | One-command setup and run using **uv**. |

### 2.2 Non-Goals (explicitly out of scope)
- Template editor or multiple certificate designs.
- User accounts, login, multi-tenancy (we document how to add an API key later).
- Email delivery of certificates (mentioned as a possible extension only).
- Frontend / UI.
- Distributed workers, message brokers (Celery/Redis), cloud storage (S3). We design an interface so they can be swapped in, but do not build them.
- Complex-script text shaping (e.g. Devanagari ligatures) — documented limitation, see §11.4.

> **Rule from the brief:** optional features must never come at the cost of required ones. Required work is done first; extras only after Definition of Done is met.

---

## 3. Users and User Stories

### 3.1 Personas
- **Client developer / integrator** — calls the API from an admin tool or script after an event.
- **Evaluator / interviewer** — reads the code, runs tests, asks "why did you do it this way?" and "change X".

### 3.2 User stories
| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-1 | client | submit many recipients in one request | I don't make N calls |
| US-2 | client | get an immediate response with a job ID | my request doesn't time out on large batches |
| US-3 | client | see progress (total / succeeded / failed / pending) | I know when it's done |
| US-4 | client | see *which* recipients failed and *why* | I can fix the data and resubmit |
| US-5 | client | download a single certificate | I can send it to one person |
| US-6 | client | download all certificates of a job as a ZIP | I can distribute in bulk |
| US-7 | client | have bad rows rejected without blocking good rows | one typo doesn't ruin a batch of 500 |
| US-8 | evaluator | run tests and the app with one or two commands | I can verify quickly |
| US-9 | evaluator | read a README explaining design decisions | I understand the reasoning |

---

## 4. Functional Requirements

**Priority legend (MoSCoW):** **M** = Must (required by brief), **S** = Should (small, high-value, do after Musts), **C** = Could (only if time remains).

### 4.1 Job creation
| ID | Requirement | Pri |
|---|---|---|
| FR-1 | `POST /api/v1/jobs` accepts one certificate-info object and a list of recipients. | M |
| FR-2 | The endpoint returns **`202 Accepted`** with the job ID, status, and URLs to poll — without waiting for generation. | M |
| FR-3 | Request-level (structural) problems reject the whole request with `422` (e.g. empty recipient list, too many recipients, missing course name, malformed JSON). | M |
| FR-4 | Recipient-level problems (bad email, empty name, duplicate) do **not** reject the request; that recipient is recorded as `failed` with `error_stage = "validation"` and a clear reason. Other recipients proceed. | M |
| FR-5 | The maximum recipients per request is configurable (default **1000**). Exceeding it returns `422`. | M |
| FR-6 | The job and **all** certificate rows are created in **one DB transaction** (all-or-nothing creation). | M |
| FR-7 | If *every* recipient is invalid, the job is created with status `failed` (no background work scheduled). | M |
| FR-8 | Optional `Idempotency-Key` header: same key + same job returns the original job instead of creating a duplicate. | S |

### 4.2 Generation
| ID | Requirement | Pri |
|---|---|---|
| FR-10 | Each valid recipient gets exactly one PDF generated from the single predefined template. | M |
| FR-11 | The PDF contains: certificate title, recipient name, course/event name, issuer name, issue date, optional achievement line, signatory name/title, and a unique certificate number. | M |
| FR-12 | A failure generating one certificate marks only that certificate `failed` (with error code + message) and processing **continues** with the rest. | M |
| FR-13 | Every certificate has a unique, human-readable **certificate number** (e.g. `CG-7K3M9PX2QD`). | M |
| FR-14 | Files are written **atomically** (write to temp file, then rename) so a crash never leaves a half-written PDF marked as success. | S |
| FR-15 | Processing is **idempotent**: re-running a job only processes certificates still `pending`. | S |
| FR-16 | On application startup, jobs left in `queued`/`processing` (e.g. after a crash) are resumed. | S |

### 4.3 Status and tracking
| ID | Requirement | Pri |
|---|---|---|
| FR-20 | `GET /api/v1/jobs/{job_id}` returns job status and progress counts (`total`, `succeeded`, `failed`, `pending`, `percent_complete`). | M |
| FR-21 | Job statuses: `queued`, `processing`, `completed`, `completed_with_errors`, `failed`. | M |
| FR-22 | Job detail includes timestamps: `created_at`, `started_at`, `completed_at`. | M |
| FR-23 | `GET /api/v1/jobs/{job_id}/certificates` lists certificates with per-item status, supports `?status=success|failed|pending` filter and pagination (`page`, `page_size`). | M |
| FR-24 | Job detail includes a preview of up to **20 failures** (index, name/email if available, error code, message). | S |
| FR-25 | `GET /api/v1/jobs` lists recent jobs (paginated). | C |

### 4.4 Retrieval
| ID | Requirement | Pri |
|---|---|---|
| FR-30 | `GET /api/v1/certificates/{certificate_id}` returns certificate metadata. | M |
| FR-31 | `GET /api/v1/certificates/{certificate_id}/download` returns the PDF (`application/pdf`, `Content-Disposition: attachment`). | M |
| FR-32 | Downloading a certificate that is not `success` returns `409` with a clear error code (`CERTIFICATE_NOT_READY` or `CERTIFICATE_FAILED`). | M |
| FR-33 | `GET /api/v1/jobs/{job_id}/download` returns a ZIP of all successful certificates (works while the job is still running — returns what exists so far; `409` if none exist). | S |
| FR-34 | `POST /api/v1/jobs/{job_id}/retry` re-queues failed *generation* failures (not validation failures). | C |

### 4.5 Operational
| ID | Requirement | Pri |
|---|---|---|
| FR-40 | `GET /health` returns `200` with `{"status": "ok"}` and checks DB connectivity. | S |
| FR-41 | Auto-generated OpenAPI docs available at `/docs`. (Free with FastAPI; make sure examples are filled in.) | M |
| FR-42 | Consistent JSON error format for all errors (see §9.6). | M |

---

## 5. Non-Functional Requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-1 | Performance | A 1000-recipient job should finish in **< 60 s** on a normal laptop (target to be *measured*, not assumed; ReportLab typically takes a few ms per simple PDF). |
| NFR-2 | Responsiveness | `POST /jobs` for 1000 recipients should return in **< 2 s** (DB insert only). |
| NFR-3 | Reliability | No job may stay in `processing` forever because of an exception. An outer `try/finally` always finalizes the job. |
| NFR-4 | Data integrity | Foreign keys enforced; unique constraints on `(job_id, sequence)` and `certificate_number`. |
| NFR-5 | Security | No user-supplied strings are used in file paths (file names derive from UUIDs only). Input length limits everywhere. No secrets in code. |
| NFR-6 | Maintainability | Layered code (API → service → renderer/storage → DB); type hints everywhere; `ruff` clean. |
| NFR-7 | Testability | Renderer and storage are injected so failures can be simulated in tests without monkey-patching internals. |
| NFR-8 | Reproducibility | `uv.lock` committed; `uv sync` reproduces the exact environment. |
| NFR-9 | Observability | Structured log lines include `job_id` and `certificate_id`; one log line per job start/finish and per failure. |
| NFR-10 | Portability | Works on Windows, macOS, Linux. (Use `pathlib`; avoid shell-only tooling in the README.) |

---

## 6. Technology Stack and uv Environment

### 6.1 Stack decisions
| Concern | Choice | Why | Alternative if asked |
|---|---|---|---|
| Web framework | **FastAPI** | Pydantic validation built in, auto docs, simple dependency injection (great for test overrides), `BackgroundTasks` built in | Django+DRF (more boilerplate), Flask (manual validation) |
| ORM | **SQLAlchemy 2.0** (sync) | Industry standard, typed, works with SQLite and Postgres | Django ORM, SQLModel |
| Database | **SQLite** (WAL mode) | Zero setup for evaluator; relational; swap via `DATABASE_URL` | Postgres |
| Validation | **Pydantic v2** + `email-validator` | Declarative rules, clear error messages | Marshmallow |
| PDF | **ReportLab** | Pure Python wheel (no system libs on Windows), precise layout, fast | WeasyPrint (HTML→PDF, needs Pango), Pillow (images) |
| Config | **pydantic-settings** | Typed env var config | `os.environ` |
| Tests | **pytest + httpx (TestClient)** | Standard | unittest |
| PDF test inspection | **pypdf** (dev) | Extract text to assert recipient name is in the PDF | — |
| Lint/format | **ruff** | One fast tool | black + flake8 |
| Env/package manager | **uv** | Fast, lockfile, manages Python version + venv | pip + venv |

> We use **sync** SQLAlchemy and sync route functions on purpose: PDF generation is CPU-bound, and sync code runs in FastAPI's threadpool. Async DB adds complexity with no benefit here. This is a likely interview question — see §19.

### 6.2 uv setup (copy-paste)

```bash
# 0. Install uv once (see https://docs.astral.sh/uv/getting-started/installation/)
#    macOS/Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh
#    Windows:      powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 1. Create the project (src layout, packaged app)
mkdir bulk-certificate-generator && cd bulk-certificate-generator
uv init --package --name certgen --python 3.12 .

# 2. Runtime dependencies
uv add fastapi "uvicorn[standard]" "sqlalchemy>=2.0" pydantic pydantic-settings email-validator reportlab

# 3. Dev dependencies (go in the [dependency-groups] dev table)
uv add --dev pytest pytest-cov httpx pypdf ruff

# 4. Day-to-day commands
uv sync                                   # create/refresh .venv from uv.lock
uv run uvicorn certgen.main:app --reload  # run the API on http://127.0.0.1:8000
uv run pytest                             # run tests
uv run pytest --cov=certgen               # with coverage
uv run ruff check . && uv run ruff format .
```

**Notes**
- Run `uv init --help` once to confirm flag names for your installed uv version; the intent is: *src layout, package name `certgen`, Python 3.12*.
- Commit `pyproject.toml`, `uv.lock`, and `.python-version`. Do **not** commit `.venv/`.
- An evaluator only needs: `uv sync` → `uv run uvicorn certgen.main:app` → `uv run pytest`. That is the README's setup story.
- No `pip install`, no manual `venv`, no `requirements.txt`. (Optional: `uv export --no-dev -o requirements.txt` if someone insists on pip.)

### 6.3 `pyproject.toml` target shape (after uv commands)

```toml
[project]
name = "certgen"
version = "0.1.0"
description = "Bulk Certificate Generator backend API"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy>=2.0",
    "pydantic",
    "pydantic-settings",
    "email-validator",
    "reportlab",
]

[dependency-groups]
dev = ["pytest", "pytest-cov", "httpx", "pypdf", "ruff"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```
(Keep the `[build-system]` block that `uv init --package` generates.)

---

## 7. Architecture

### 7.1 Component view

```
                 ┌───────────────────────────────────────────────┐
  Client ──HTTP─▶│ FastAPI app (api/ routers)                    │
                 │   • request schemas (Pydantic)                │
                 │   • error handlers → uniform JSON             │
                 └──────────────┬────────────────────────────────┘
                                │ calls
                 ┌──────────────▼────────────────┐
                 │ Services                      │
                 │  JobService  (create/query)   │
                 │  RecipientValidator           │
                 │  JobProcessor (background)    │
                 └───────┬───────────────┬───────┘
                         │               │
              ┌──────────▼───┐   ┌───────▼───────────────┐
              │ SQLAlchemy   │   │ CertificateRenderer   │  (interface)
              │ Session / DB │   │  └─ ReportLabRenderer │
              └──────────────┘   │ FileStorage           │  (interface)
                                 │  └─ LocalFileStorage  │
                                 └───────────────────────┘
```

### 7.2 Request lifecycle (happy path)
1. Client `POST /api/v1/jobs`.
2. Pydantic validates the **envelope** (certificate info, list size).
3. `RecipientValidator` validates **each** recipient independently → produces `valid` and `invalid` lists, including duplicate detection.
4. `JobService.create_job` opens **one transaction**: inserts the `jobs` row + N `certificates` rows (`pending` for valid, `failed`/validation for invalid). Commit.
5. If at least one `pending` row: schedule `JobProcessor.run(job_id)` via FastAPI `BackgroundTasks`. Else mark job `failed`.
6. Return `202` + job summary.
7. Background: `JobProcessor` marks job `processing`, loops over pending certificates, renders → stores → updates row (commit per certificate), finally sets job final status.
8. Client polls `GET /jobs/{id}` until status ∈ {`completed`, `completed_with_errors`, `failed`}.
9. Client downloads individually or as ZIP.

### 7.3 Layering rules (keeps code explainable)
- **Routers** know HTTP; they never contain business logic or SQL.
- **Services** know business rules; they receive a `Session` and collaborators (renderer, storage) — never import FastAPI.
- **Renderer** knows only: `render(data) -> bytes`. No DB, no file system.
- **Storage** knows only: `save(key, bytes) -> path`, `open(key)`, `exists(key)`. No business rules.

---

## 8. Data Model

### 8.1 Tables

#### `jobs`
| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | UUID4 |
| `status` | `String(24)` | `queued` / `processing` / `completed` / `completed_with_errors` / `failed` (indexed) |
| `title` | `String(100)` | e.g. "Certificate of Completion" |
| `course_name` | `String(150)` | event/course |
| `issuer_name` | `String(100)` | organization |
| `issue_date` | `Date` | |
| `signatory_name` | `String(100)` NULL | |
| `signatory_title` | `String(100)` NULL | |
| `total_count` | `Integer` | number of recipients submitted (fixed at creation) |
| `idempotency_key` | `String(100)` NULL, **unique** | optional (FR-8) |
| `created_at` / `started_at` / `completed_at` / `updated_at` | `DateTime(timezone=True)` | UTC |

#### `certificates`
| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | UUID4 |
| `job_id` | FK → `jobs.id` (`ON DELETE CASCADE`) | indexed |
| `sequence` | `Integer` | 0-based position in the request; **unique with `job_id`**; lets clients map results back to their input order |
| `status` | `String(16)` | `pending` / `success` / `failed` |
| `raw_input` | `JSON` | the original recipient object exactly as received (needed because invalid rows may lack a name/email) |
| `recipient_name` | `String(100)` NULL | normalized; NULL if invalid |
| `recipient_email` | `String(254)` NULL | normalized (lower-cased) |
| `reference_id` | `String(64)` NULL | client's own ID, echoed back |
| `achievement` | `String(100)` NULL | e.g. "with Distinction" |
| `certificate_number` | `String(20)` NULL, **unique** | assigned only to valid recipients |
| `error_stage` | `String(16)` NULL | `validation` or `generation` |
| `error_code` | `String(40)` NULL | machine-readable |
| `error_message` | `Text` NULL | human-readable |
| `file_path` | `String(255)` NULL | relative storage key, e.g. `<job_id>/<certificate_id>.pdf` |
| `file_size` | `Integer` NULL | bytes |
| `generated_at` | `DateTime` NULL | |
| `created_at` / `updated_at` | `DateTime` | |

**Indexes:** `(job_id, status)`, unique `(job_id, sequence)`, unique `certificate_number`.

### 8.2 State machines

**Certificate**
```
pending ──render+store ok──▶ success
   │
   └──── exception ─────────▶ failed (error_stage=generation)

(invalid on arrival) ───────▶ failed (error_stage=validation)   [created directly in this state]
```

**Job**
```
queued ─▶ processing ─▶ completed               (all success)
                     ├─▶ completed_with_errors  (≥1 success and ≥1 failed)
                     └─▶ failed                 (0 success)
queued ─▶ failed   (no valid recipients at creation)
```

### 8.3 Design decisions on the data model
- **Progress counts are computed with `GROUP BY status`, not stored counters.** Stored counters can drift under concurrency or crashes; a count query on an indexed column is cheap and always correct.
- **`raw_input` is stored as JSON** so invalid rows are fully auditable.
- **Certificates exist from job creation** (not created lazily). This means the client can see all N items immediately, and "pending" is a real, queryable state.
- **File paths are relative** to `STORAGE_DIR`, so moving the storage folder doesn't break rows.
- **UTC everywhere**; timestamps serialized as ISO-8601 with `Z`.

---

## 9. API Specification

Base path: `/api/v1`. All bodies are JSON unless stated.

### 9.1 `POST /api/v1/jobs` — create a generation job
**Request**
```json
{
  "certificate": {
    "title": "Certificate of Completion",
    "course_name": "Advanced Python Bootcamp",
    "issuer_name": "Acme Academy",
    "issue_date": "2026-10-01",
    "signatory_name": "Dr. Jane Roe",
    "signatory_title": "Program Director"
  },
  "recipients": [
    { "name": "Asha Patil", "email": "asha@example.com", "reference_id": "STU-001", "achievement": "with Distinction" },
    { "name": "Rohan Kulkarni", "email": "rohan@example.com" },
    { "name": "", "email": "not-an-email" }
  ]
}
```
Field rules: see §10.

**Response `202 Accepted`** (headers: `Location: /api/v1/jobs/{id}`)
```json
{
  "id": "5b0f6c0e-6e0a-4b6f-8f0e-3c1f6f3a9d11",
  "status": "queued",
  "created_at": "2026-10-09T10:15:30Z",
  "progress": { "total": 3, "succeeded": 0, "failed": 1, "pending": 2, "percent_complete": 33.3 },
  "links": {
    "self": "/api/v1/jobs/5b0f6c0e-...",
    "certificates": "/api/v1/jobs/5b0f6c0e-.../certificates",
    "download": "/api/v1/jobs/5b0f6c0e-.../download"
  }
}
```
> `percent_complete` = `(succeeded + failed) / total * 100`. Invalid recipients count as "processed" because they are final.

**Errors:** `422` (structural), `400` (malformed JSON), `500`.

### 9.2 `GET /api/v1/jobs/{job_id}` — job status and progress
**Response `200`**
```json
{
  "id": "5b0f6c0e-...",
  "status": "completed_with_errors",
  "certificate": {
    "title": "Certificate of Completion",
    "course_name": "Advanced Python Bootcamp",
    "issuer_name": "Acme Academy",
    "issue_date": "2026-10-01",
    "signatory_name": "Dr. Jane Roe",
    "signatory_title": "Program Director"
  },
  "created_at": "2026-10-09T10:15:30Z",
  "started_at": "2026-10-09T10:15:31Z",
  "completed_at": "2026-10-09T10:15:33Z",
  "progress": { "total": 3, "succeeded": 2, "failed": 1, "pending": 0, "percent_complete": 100.0 },
  "failures": [
    { "sequence": 2, "recipient_name": null, "recipient_email": null,
      "error_stage": "validation", "error_code": "INVALID_NAME",
      "error_message": "name: must not be empty; email: not a valid email address" }
  ],
  "failures_truncated": false,
  "links": { "self": "...", "certificates": "...", "download": "..." }
}
```
**Errors:** `404 JOB_NOT_FOUND`.

### 9.3 `GET /api/v1/jobs/{job_id}/certificates` — list certificates
Query: `status` (optional: `success|failed|pending`), `page` (default 1), `page_size` (default 50, max 200).

**Response `200`**
```json
{
  "job_id": "5b0f6c0e-...",
  "page": 1, "page_size": 50, "total_items": 3,
  "items": [
    {
      "id": "c1d0...", "sequence": 0, "status": "success",
      "certificate_number": "CG-7K3M9PX2QD",
      "recipient_name": "Asha Patil", "recipient_email": "asha@example.com",
      "reference_id": "STU-001",
      "download_url": "/api/v1/certificates/c1d0.../download",
      "generated_at": "2026-10-09T10:15:32Z",
      "error": null
    },
    {
      "id": "c9e2...", "sequence": 2, "status": "failed",
      "certificate_number": null, "recipient_name": null, "recipient_email": null,
      "reference_id": null, "download_url": null, "generated_at": null,
      "error": { "stage": "validation", "code": "INVALID_NAME", "message": "..." }
    }
  ]
}
```
Items are ordered by `sequence` ascending.

### 9.4 `GET /api/v1/certificates/{certificate_id}` — metadata
Same shape as one item above, plus `job_id` and `file_size`. `404 CERTIFICATE_NOT_FOUND`.

### 9.5 Downloads
| Endpoint | Success | Failure |
|---|---|---|
| `GET /api/v1/certificates/{id}/download` | `200`, `application/pdf`, `Content-Disposition: attachment; filename="CG-7K3M9PX2QD.pdf"` | `404 CERTIFICATE_NOT_FOUND`; `409 CERTIFICATE_NOT_READY` (pending); `409 CERTIFICATE_FAILED`; `500 FILE_MISSING` if the row says success but file is gone (log loudly) |
| `GET /api/v1/jobs/{id}/download` | `200`, `application/zip`, `Content-Disposition: attachment; filename="job-<short-id>-certificates.zip"`; contains `<certificate_number>.pdf` per success, plus `manifest.csv` (sequence, name, email, certificate_number, status, error) | `404 JOB_NOT_FOUND`; `409 NO_CERTIFICATES_AVAILABLE` |

ZIP is built into a `SpooledTemporaryFile` (spills to disk past a size threshold), then streamed — avoids holding hundreds of MB in RAM.

### 9.6 Error format (all non-2xx)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "recipients", "message": "must contain at least 1 item" }
    ]
  }
}
```
Implementation: custom exception classes (`AppError(code, message, status_code, details)`), plus handlers for `RequestValidationError`, `AppError`, and a catch-all for unexpected exceptions (logs stack trace, returns generic `500 INTERNAL_ERROR`, never leaks internals).

### 9.7 Status code summary
| Code | When |
|---|---|
| 200 | Reads, downloads |
| 202 | Job accepted |
| 400 | Malformed JSON |
| 404 | Unknown job/certificate |
| 409 | Download of a certificate that isn't ready/failed, or ZIP with nothing in it |
| 422 | Structural validation failure |
| 500 | Unexpected error |

### 9.8 Error code catalogue
| Code | Stage | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | request | Whole-request validation failure |
| `JOB_NOT_FOUND` | request | |
| `CERTIFICATE_NOT_FOUND` | request | |
| `CERTIFICATE_NOT_READY` | request | Still pending |
| `CERTIFICATE_FAILED` | request | Generation/validation failed; no file |
| `NO_CERTIFICATES_AVAILABLE` | request | ZIP requested but nothing succeeded yet |
| `MISSING_FIELD` | validation | Recipient lacks `name` or `email` |
| `INVALID_NAME` | validation | Empty/too long/control characters |
| `INVALID_EMAIL` | validation | Bad email syntax |
| `FIELD_TOO_LONG` | validation | `achievement` / `reference_id` over limit |
| `DUPLICATE_RECIPIENT` | validation | Same email already earlier in this job |
| `UNSUPPORTED_CHARACTERS` | generation | Name has glyphs the font can't draw (see §11.4) |
| `RENDER_ERROR` | generation | Renderer raised |
| `STORAGE_ERROR` | generation | Couldn't write the file |
| `UNEXPECTED_ERROR` | generation | Anything else |
| `PROCESSING_ABORTED` | generation | Job-level crash; remaining items failed |
| `INTERNAL_ERROR` | request | Unhandled server error |

---

## 10. Validation Specification

### 10.1 Two levels (important design decision)
| Level | Scope | On failure |
|---|---|---|
| **Envelope** (structural) | JSON shape, `certificate` fields, recipients list size | Reject entire request → `422` |
| **Recipient** (semantic) | Each recipient individually | Accept request; mark *that* recipient `failed` (validation); continue |

**Why:** the brief says one bad item shouldn't block the others, and a 500-row upload shouldn't be thrown away because of one typo. **Trade-off:** the client must check the job result rather than relying on a `422`. We document this in the README and expose failures prominently in job status.
**Implementation hint:** declare `recipients: list[dict[str, Any]]` on the envelope model, then validate each item with a `RecipientIn` model (via `RecipientIn.model_validate` in a loop, catching `ValidationError` per item). This avoids Pydantic failing the whole list on one bad entry.

### 10.2 Envelope rules
| Field | Rule |
|---|---|
| `certificate.title` | optional, default `"Certificate of Completion"`, 1–100 chars after trim |
| `certificate.course_name` | **required**, 1–150 chars |
| `certificate.issuer_name` | **required**, 1–100 chars |
| `certificate.issue_date` | **required**, ISO date `YYYY-MM-DD` |
| `certificate.signatory_name` | optional, ≤100 chars |
| `certificate.signatory_title` | optional, ≤100 chars |
| `recipients` | list, **1 ≤ length ≤ `MAX_RECIPIENTS_PER_JOB`** (default 1000) |

### 10.3 Recipient rules
| Field | Rule | Normalization |
|---|---|---|
| `name` | **required**; 1–100 chars after trim; no control characters (`\x00–\x1f`, `\x7f`) | trim; collapse internal whitespace runs to one space |
| `email` | **required**; valid per `email-validator` (`check_deliverability=False` — no DNS lookups); ≤254 chars | trim; lower-case |
| `reference_id` | optional; ≤64 chars | trim |
| `achievement` | optional; ≤100 chars; no control chars | trim; empty string → `null` |
| unknown extra keys | ignored (kept in `raw_input` only) | — |
| duplicate | same normalized email appearing earlier in the same job → later one fails `DUPLICATE_RECIPIENT` | first occurrence wins |

**Edge cases the tests must cover:** non-string `name` (e.g. `123`), `null` values, whitespace-only name, name with emoji, 100 vs 101 character names, same email in different case, recipient is not an object (e.g. a string).

### 10.4 Message quality
Collect **all** problems for a recipient and join them (e.g. `name: must not be empty; email: not a valid email address`). `error_code` is the *first* problem's code. This is much friendlier than failing on the first error.

---

## 11. Certificate Template Specification

### 11.1 Page
- **A4 landscape** (842 × 595 pt), single page, PDF.
- Double border (outer thick, inner thin), margin 36 pt.

### 11.2 Layout (top to bottom, centered)
1. **Issuer name** (small caps feel, 16 pt)
2. **Title** (e.g. "Certificate of Completion", 34 pt, bold serif)
3. Line: *"This certificate is proudly presented to"* (14 pt, italic)
4. **Recipient name** (40 pt bold, auto-shrinks — see below)
5. Thin horizontal rule under the name
6. Line: *"for successfully completing"* (14 pt)
7. **Course name** (24 pt bold; wraps to max 2 lines)
8. *(optional)* **Achievement** (16 pt italic), e.g. "with Distinction"
9. Bottom-left: **Issue date** ("Date: 01 October 2026")
10. Bottom-right: signature line + **signatory name** + *signatory title* (omitted if not provided)
11. Bottom-center small print: **Certificate No. CG-7K3M9PX2QD**

### 11.3 Text fitting rules
- **Recipient name:** start at 40 pt; shrink in 1 pt steps down to a minimum of 20 pt until `stringWidth ≤ available width`. Names are limited to 100 chars so they fit at 20 pt (verify in a test with a 100-char name).
- **Course name:** wrap into at most 2 lines with `simpleSplit`; if still too long, shrink font to min 14 pt.
- All dynamic text is rendered with `drawCentredString` / `drawString` — **never** interpreted as markup (avoids ReportLab `Paragraph` markup injection like `<b>` or `&`).

### 11.4 Fonts and character coverage (known limitation — document it)
- Bundle a free TTF family (e.g. **DejaVu Serif** regular/bold/italic) under `src/certgen/rendering/assets/fonts/` and register it with `pdfmetrics.registerFont`. Built-in PDF fonts (Helvetica/Times) only cover basic Latin and would silently print garbage for names like "Zoë" or "Łukasz".
- Before drawing, check each character of dynamic text against the font's character map. If a glyph is missing → raise `UnsupportedCharactersError` → certificate fails with `UNSUPPORTED_CHARACTERS`. **This is also our natural, realistic "single certificate failure" scenario.**
- **Limitation:** ReportLab does not perform complex-script shaping (e.g. Devanagari conjuncts, Arabic joining). Names in such scripts are rejected with a clear message rather than rendered incorrectly. Possible future fix: render via WeasyPrint/HarfBuzz with Noto fonts — documented as a trade-off.

### 11.5 Certificate number
Format `CG-` + 10 chars from Crockford-style Base32 (no `I L O U`), generated with `secrets`. On unique-constraint collision (astronomically unlikely) regenerate. Number is printed on the PDF **and** stored in the DB.

### 11.6 Renderer interface (for DI and tests)
```python
class CertificateData(BaseModel):          # immutable value object
    title: str
    course_name: str
    issuer_name: str
    issue_date: date
    signatory_name: str | None
    signatory_title: str | None
    recipient_name: str
    achievement: str | None
    certificate_number: str

class CertificateRenderer(Protocol):
    def render(self, data: CertificateData) -> bytes: ...
```
`ReportLabCertificateRenderer` implements it. Tests inject a `FlakyRenderer` that raises for a chosen name.

---

## 12. Processing Design (the documented decision)

### 12.1 Options considered
| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Synchronous in the request** | Simplest; no polling | Request blocks (1000 PDFs could take many seconds → timeouts); no real "progress" | ❌ Rejected: defeats the purpose of a status endpoint and doesn't scale |
| **B. FastAPI `BackgroundTasks` (in-process)** | No extra infrastructure; trivial to run & test; real progress tracking | Work is lost if the process dies (mitigated by recovery on startup, FR-16); runs on the web process; one process = limited throughput | ✅ **Chosen** |
| **C. Celery/RQ/Arq + Redis/RabbitMQ** | Durable, horizontally scalable, retries | Extra services to install; heavy for an evaluator to run; more to explain | ⏭ Documented as the production upgrade path |

### 12.2 Why B is enough here (README text)
- The workload is small-to-moderate (≤1000 items/job, ms per item).
- The evaluator must run the project in one command; Redis would break that.
- Status is persisted in the DB, not in memory, so the *design* already matches a queue-based architecture; only the "dispatch" line changes.
- Crash safety is addressed by idempotent processing + startup recovery.

### 12.3 Upgrade path (be ready to explain)
1. Replace `background_tasks.add_task(processor.run, job_id)` with `queue.enqueue(run_job, job_id)`.
2. Move to Postgres; let workers claim certificates with `SELECT … FOR UPDATE SKIP LOCKED` to parallelize within a job.
3. Replace `LocalFileStorage` with an `S3Storage` implementing the same interface.
4. Add retry with backoff for transient `STORAGE_ERROR`.

### 12.4 `JobProcessor.run(job_id)` algorithm
```
open own DB session (never reuse the request's session)
job = load job; if not found → log and return
job.status = processing; job.started_at = now (if not set); commit
try:
    ids = SELECT id FROM certificates WHERE job_id=? AND status='pending' ORDER BY sequence
    for cert_id in ids:
        cert = load certificate
        try:
            data = build CertificateData(job, cert)
            pdf_bytes = renderer.render(data)                 # may raise
            key = f"{job.id}/{cert.id}.pdf"
            storage.save(key, pdf_bytes)                      # atomic write; may raise
            cert.status='success'; cert.file_path=key; cert.file_size=len(pdf_bytes); cert.generated_at=now
        except UnsupportedCharactersError as e:  mark failed(UNSUPPORTED_CHARACTERS)
        except StorageError as e:                mark failed(STORAGE_ERROR)
        except Exception as e:                   log.exception; mark failed(RENDER_ERROR or UNEXPECTED_ERROR)
        commit   # per certificate → live progress, and a crash loses at most one item of work
except Exception:                                  # job-level crash
    log.exception
    mark all still-pending certificates failed(PROCESSING_ABORTED)
finally:
    counts = GROUP BY status
    job.status = completed | completed_with_errors | failed   (per §8.2)
    job.completed_at = now; commit
```
**Key properties:** a bad certificate never aborts the loop; the job can never be left in `processing`; re-running only touches `pending`.

### 12.5 Concurrency notes
- Each background run owns its own `Session`; sessions are never shared across threads.
- SQLite: enable `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `busy_timeout=5000` via an engine `connect` event listener, and `check_same_thread=False`.
- Multiple jobs can run at once (Starlette threadpool). Within one job, certificates are processed sequentially (simple, deterministic, easy to explain).
- In **tests**, Starlette's `TestClient` runs background tasks to completion *before* returning the response, so tests don't need `sleep`. Additionally, `JobProcessor` is directly callable in unit tests.

### 12.6 Startup recovery (FR-16)
In the FastAPI `lifespan` handler: find jobs with status `queued`/`processing`, and re-run them in a background thread. Because processing only touches `pending` certificates, this is safe. Skip when `CERTGEN_DISABLE_RECOVERY=true` (used in tests).

---

## 13. Storage Design
```python
class FileStorage(Protocol):
    def save(self, key: str, content: bytes) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...
```
`LocalFileStorage(root: Path)`:
- Resolve `root / key`, **assert the resolved path is inside `root`** (path-traversal guard even though keys are server-generated).
- `save`: create parent dirs → write to `*.tmp` in the same directory → `os.replace` to final name (atomic on same filesystem).
- Layout: `storage/certificates/<job_id>/<certificate_id>.pdf`. Folder `storage/` is git-ignored.

---

## 14. Configuration

Environment variables (prefix `CERTGEN_`), loaded by `pydantic-settings` (and `.env` if present). Provide `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `CERTGEN_DATABASE_URL` | `sqlite:///./data/certgen.db` | SQLAlchemy URL (swap to Postgres here) |
| `CERTGEN_STORAGE_DIR` | `./storage/certificates` | Where PDFs are saved |
| `CERTGEN_MAX_RECIPIENTS_PER_JOB` | `1000` | FR-5 |
| `CERTGEN_DISABLE_RECOVERY` | `false` | Skip startup recovery |
| `CERTGEN_LOG_LEVEL` | `INFO` | |

Settings are accessed through a `get_settings()` dependency (cached) so tests can override them cleanly.

---

## 15. Project Structure

```
bulk-certificate-generator/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore                 # .venv/, data/, storage/, __pycache__/, .pytest_cache/, .env, .ruff_cache/
├── README.md
├── docs/
│   └── PRD.md                 # this document (optional to ship)
├── src/certgen/
│   ├── __init__.py
│   ├── main.py                # create_app(), lifespan, router registration
│   ├── config.py              # Settings
│   ├── db.py                  # engine, SessionLocal, Base, SQLite pragmas, get_db dependency
│   ├── models.py              # Job, Certificate (+ enums)
│   ├── schemas.py             # Pydantic request/response models
│   ├── errors.py              # AppError hierarchy + exception handlers
│   ├── logging_config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py            # get_db, get_settings, get_renderer, get_storage
│   │   ├── jobs.py            # POST/GET jobs, list certs, zip
│   │   ├── certificates.py    # GET metadata, download
│   │   └── health.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── validation.py      # RecipientValidator
│   │   ├── job_service.py     # create_job, get_job, progress, list_certificates
│   │   ├── processor.py       # JobProcessor
│   │   ├── numbering.py       # certificate_number generator
│   │   └── archive.py         # build zip + manifest
│   ├── rendering/
│   │   ├── __init__.py
│   │   ├── base.py            # CertificateData, CertificateRenderer, errors
│   │   ├── pdf_renderer.py    # ReportLabCertificateRenderer
│   │   └── assets/fonts/      # DejaVuSerif*.ttf (+ license file)
│   └── storage/
│       ├── __init__.py
│       └── local.py           # LocalFileStorage
└── tests/
    ├── conftest.py            # temp DB + storage, app/client fixtures, FlakyRenderer
    ├── factories.py           # payload builders
    ├── test_job_creation.py
    ├── test_validation.py
    ├── test_rendering.py
    ├── test_processor.py
    ├── test_job_status.py
    ├── test_failure_handling.py
    ├── test_retrieval.py
    ├── test_archive.py
    └── test_storage.py
```

---

## 16. Testing Plan

### 16.1 Principles
- Each test uses an isolated **temp-file SQLite DB** and a **temp storage dir** (`tmp_path`). Prefer a file DB over `:memory:` because threads + in-memory SQLite need extra pooling workarounds.
- Override dependencies (`get_db`, `get_settings`, `get_renderer`, `get_storage`) via `app.dependency_overrides`.
- No `sleep()`: rely on TestClient running background tasks before returning, and call `JobProcessor` directly for unit tests.
- Failure simulation by **injection**, not monkey-patching: `FlakyRenderer(fail_for={"Boom Name"})`.

### 16.2 Required coverage (maps 1:1 to the brief)
| Brief requirement | Test file | Key test cases |
|---|---|---|
| **Creating a generation job** | `test_job_creation.py` | returns 202 + id + `Location`; creates `jobs` row + N `certificates` rows in one transaction; invalid rows stored as `failed/validation`; all-invalid → job `failed`; `max` recipients boundary (1000 ok, 1001 → 422); idempotency key returns same job *(if implemented)* |
| **Input validation** | `test_validation.py` | empty list → 422; missing `course_name` → 422; bad date → 422; per-recipient: missing name, whitespace name, 100/101 chars, bad email, non-string name, non-object item, duplicate email (case-insensitive), control chars; multiple errors joined; normalization (trim/lowercase/collapse spaces) |
| **Certificate generation** | `test_rendering.py`, `test_processor.py` | PDF bytes start with `%PDF`; `pypdf` extracts recipient name, course, issuer, certificate number; long name auto-shrinks and still renders; accented name `Zoë`/`Łukasz` OK; unsupported glyph raises `UnsupportedCharactersError`; markup-like name `<b>&</b>` printed literally; file written under `<job>/<cert>.pdf`; DB row has `file_path`, `file_size`, `generated_at` |
| **Job status/progress** | `test_job_status.py` | initial counts; counts after completion; `percent_complete`; statuses `completed` / `completed_with_errors` / `failed`; `started_at`/`completed_at` set; 404 unknown job; failure preview capped at 20 + `failures_truncated`; mid-run progress (processor with a hook that checks counts after N items) |
| **Handling an individual failure** | `test_failure_handling.py` | one recipient fails in the middle → others still `success`; failed item has `error_stage=generation`, code, message; job = `completed_with_errors`; storage failure → `STORAGE_ERROR`; job-level crash → pending items `PROCESSING_ABORTED`, job never stuck in `processing`; re-run only processes pending |
| **Retrieving certificates** | `test_retrieval.py`, `test_archive.py` | list all, filter by `status`, pagination (`page_size`, bounds); metadata endpoint; download returns PDF with correct headers; download pending → 409; download failed → 409; unknown id → 404; missing file on disk → 500 `FILE_MISSING`; ZIP contains one PDF per success + `manifest.csv`; ZIP with no successes → 409 |

### 16.3 Extra tests (cheap and impressive)
- `test_storage.py`: path traversal key (`../evil`) rejected; atomic save leaves no `.tmp` on success; failed write leaves no partial file.
- Certificate number uniqueness across 1000 generations.
- Health endpoint.
- Startup recovery re-processes a job left in `processing` (call recovery function directly).

### 16.4 Coverage target
≥ **85 %** line coverage on `src/certgen` (`uv run pytest --cov=certgen --cov-report=term-missing`). Report the real number in the README, not an aspirational one.

### 16.5 Example fixtures (sketch)
```python
@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path/'test.db'}",
                    storage_dir=tmp_path/"storage", disable_recovery=True)

@pytest.fixture
def client(settings, renderer):               # renderer defaults to the real one
    app = create_app(settings)
    app.dependency_overrides[get_renderer] = lambda: renderer
    with TestClient(app) as c:
        yield c

class FlakyRenderer:
    def __init__(self, inner, fail_for: set[str]): ...
    def render(self, data):
        if data.recipient_name in self.fail_for:
            raise RuntimeError("simulated render failure")
        return self.inner.render(data)
```

---

## 17. Implementation Plan (build in this order)

> Work in small commits. After each phase: `uv run ruff check . && uv run pytest` must pass. Tick the boxes as you go.

### Phase 0 — Project bootstrap (≈ 30 min)
- [ ] Install uv; run the commands in §6.2; confirm `uv run python -c "import fastapi, sqlalchemy, reportlab"` works.
- [ ] Create folder skeleton from §15 (empty `__init__.py` files).
- [ ] Add `.gitignore`, `.env.example`, `.python-version`; `git init` and first commit.
- [ ] Add `GET /health` and `create_app()`; run `uv run uvicorn certgen.main:app --reload`; open `/docs`.
- **Done when:** server starts; `/health` returns ok; `uv run pytest` runs (even with a single smoke test).

### Phase 1 — Config, DB, models (≈ 1 h)
- [ ] `config.py` with `Settings` + `get_settings()`.
- [ ] `db.py`: engine factory, SQLite pragmas (WAL, FK, busy_timeout), `SessionLocal`, `get_db`.
- [ ] `models.py`: `Job`, `Certificate`, status enums, constraints/indexes per §8.
- [ ] Create tables on startup (`Base.metadata.create_all`) — note in README that Alembic would be the next step.
- [ ] Tests: models persist; unique `(job_id, sequence)` enforced; cascade delete works.

### Phase 2 — Validation (≈ 1.5 h)
- [ ] `schemas.py`: `CertificateInfoIn`, `JobCreateIn` (envelope), `RecipientIn`.
- [ ] `services/validation.py`: `RecipientValidator.validate_all(raw_list) -> list[ValidatedItem]` with normalization, error aggregation, duplicate detection.
- [ ] `errors.py`: `AppError`, handlers, uniform JSON format.
- [ ] Tests: everything in §10 edge-case list. **Write these tests first (TDD) — validation is the easiest place to do it.**

### Phase 3 — Rendering (≈ 2 h)
- [ ] Add DejaVu fonts + license file to `rendering/assets/fonts/`.
- [ ] `rendering/base.py`: `CertificateData`, `CertificateRenderer`, `UnsupportedCharactersError`.
- [ ] `rendering/pdf_renderer.py`: layout per §11; font registration once (module-level lazy init); glyph coverage check; shrink-to-fit.
- [ ] `services/numbering.py`.
- [ ] Manual check: write a small script/test that saves a sample PDF to `./sample_certificate.pdf`; **open it and look at it**. Iterate on spacing until it looks good.
- [ ] Tests per §16.2 (rendering rows).

### Phase 4 — Storage (≈ 45 min)
- [ ] `storage/local.py` with atomic save, traversal guard.
- [ ] Tests: §16.3 storage cases.

### Phase 5 — Job creation (≈ 1.5 h)
- [ ] `services/job_service.py`: `create_job(session, payload, settings)` → one transaction; assigns `sequence`, `certificate_number` for valid rows; sets job `queued`/`failed`.
- [ ] `api/jobs.py`: `POST /jobs` returns 202 + `Location`; schedules the processor only if pending items exist.
- [ ] Progress query helper (`GROUP BY status`).
- [ ] Tests: creation rows of §16.2.

### Phase 6 — Processor (≈ 2 h)
- [ ] `services/processor.py` implementing §12.4 exactly.
- [ ] Wire into `POST /jobs` via `BackgroundTasks`, using DI for renderer/storage and a **session factory** (not the request session).
- [ ] Tests: success path, one failure in middle, storage failure, job-level crash, idempotent re-run.
- **Done when:** a 3-recipient request with one bad email + one `Boom` name yields `completed_with_errors` with exactly 1 success… (adjust per your sample) and the PDFs exist on disk.

### Phase 7 — Status & retrieval endpoints (≈ 2 h)
- [ ] `GET /jobs/{id}` with progress + failure preview.
- [ ] `GET /jobs/{id}/certificates` with filter + pagination.
- [ ] `GET /certificates/{id}` and `/download` with 404/409 handling (`FileResponse` or streaming).
- [ ] Tests: §16.2 status + retrieval rows.

### Phase 8 — ZIP download + recovery (≈ 1.5 h) *(Should)*
- [ ] `services/archive.py` with `SpooledTemporaryFile`, manifest CSV.
- [ ] `GET /jobs/{id}/download`.
- [ ] Startup recovery in `lifespan`; test by calling the recovery function directly.
- [ ] Optional: `Idempotency-Key` (FR-8).

### Phase 9 — Documentation & polish (≈ 1.5 h)
- [ ] README (outline in §17.1).
- [ ] Run a **load check**: script that submits 1000 recipients, polls, prints total time; record the real number in the README.
- [ ] `ruff format`, coverage report, remove dead code, re-read every file once.
- [ ] Fresh-clone test: clone into a new folder, `uv sync`, run server, run tests. (This is what the evaluator will do.)

**Total estimate:** ~14–16 hours of focused work. Phases 0–7 + README is the *minimum submission*; Phases 8–9 add polish.

### 17.1 README outline
1. What it is (2–3 sentences) and feature list
2. Prerequisites (uv; Python is auto-managed by uv)
3. Setup: `uv sync`
4. Run: `uv run uvicorn certgen.main:app --reload`; docs at `/docs`
5. Run tests: `uv run pytest` (+ coverage command)
6. Configuration table (env vars)
7. **Usage walkthrough with `curl`** (create job → poll → list → download → ZIP) — with real sample payload file `examples/sample_request.json`
8. API reference summary table (link to `/docs`)
9. **Design decisions**: sync vs background (with §12 reasoning), partial-failure model, two-level validation, computed progress, storage abstraction, SQLite choice, font/character limitation
10. Known limitations and what I'd do next (Celery + Postgres, S3, auth, Alembic, WeasyPrint for complex scripts)
11. Project structure map

---

## 18. Definition of Done and Acceptance Criteria

### 18.1 Checklist
- [ ] All **M** requirements implemented.
- [ ] `uv sync && uv run pytest` passes on a clean clone; no skipped/xfail tests without explanation.
- [ ] `uv run ruff check .` clean.
- [ ] Coverage ≥ 85 % (actual number in README).
- [ ] README complete per §17.1; all documented commands were actually executed and work.
- [ ] A 1000-recipient job was run end-to-end at least once; timing recorded.
- [ ] I can explain every file without looking at it (see §19).
- [ ] No secrets, no `.venv`, no generated PDFs, no DB files committed.

### 18.2 End-to-end acceptance scenarios
| # | Scenario | Expected |
|---|---|---|
| A1 | Submit 3 valid recipients | `202`; polling reaches `completed`; 3 PDFs downloadable; each contains correct name |
| A2 | Submit 5 recipients: 1 bad email, 1 duplicate, 3 valid | `202`; job `completed_with_errors`; `progress.failed=2`, `succeeded=3`; failure reasons visible in job detail and filtered list |
| A3 | Submit 3 recipients where the renderer fails for the 2nd | 1st and 3rd succeed; 2nd `failed` (`generation`); job `completed_with_errors` |
| A4 | Submit empty `recipients` | `422` with uniform error body |
| A5 | Submit 1001 recipients (limit 1000) | `422` |
| A6 | Submit only invalid recipients | `202`; job `failed`; no files created |
| A7 | Download a pending/failed certificate | `409` with specific code |
| A8 | Download ZIP after A2 | ZIP has 3 PDFs + `manifest.csv` listing 5 rows |
| A9 | Kill server mid-job, restart | Job resumes; ends in final status with all certificates accounted for |
| A10 | Unknown job ID | `404 JOB_NOT_FOUND` |

---

## 19. Interview Readiness

The brief warns that you may be asked to **explain, justify, debug, modify, or handle a changed requirement**. Prepare these.

### 19.1 Likely "why" questions — short answers
| Question | Answer |
|---|---|
| Why FastAPI? | Built-in validation via Pydantic, auto OpenAPI docs, simple dependency injection which made failure simulation in tests trivial. |
| Why background tasks instead of Celery? | Evaluator must run it in one command; workload is small; status is DB-backed so the design is queue-ready — only the dispatch line changes. Trade-off: in-process work can be lost on crash → mitigated with idempotent processing + startup recovery. |
| Why not just do it synchronously? | 1000 PDFs would block the request, risk timeouts, and make a "progress" endpoint pointless. |
| Why sync SQLAlchemy? | PDF rendering is CPU-bound; sync functions run in the threadpool; async DB adds complexity without benefit. |
| Why create certificate rows up front? | Gives clients a complete, stable list immediately; "pending" is queryable; invalid rows are auditable. |
| Why compute progress instead of storing counters? | Counters drift under crashes/concurrency; an indexed `GROUP BY` is cheap and always correct. |
| Why accept the request when some recipients are invalid? | One typo in 500 rows shouldn't discard the batch; brief explicitly wants valid ones to proceed. Trade-off: client must read results. |
| Why commit per certificate? | Live progress, and a crash loses at most one item. Trade-off: more commits (fine for SQLite at this scale; batch commits if profiling says so). |
| How do you prevent a stuck job? | `try/finally` always finalizes; job-level exceptions mark leftover pending items failed. |
| What happens if the server restarts mid-job? | Lifespan recovery re-queues `queued/processing` jobs; processor only handles `pending` items. |
| How would this scale? | Queue + workers, Postgres with `SKIP LOCKED`, S3 storage, retry/backoff (§12.3). |
| Security considerations? | UUID-based file paths + traversal guard, length limits, no markup interpretation, no internals in 500s; add API key/JWT for auth. |

### 19.2 "Changed requirement" drills — know where to edit
| Change | Where / how |
|---|---|
| "Add a second field on certificates (e.g. grade/score)" | `RecipientIn` + validator, `Certificate` model column, `CertificateData`, renderer layout, tests. |
| "Reject the whole request if any recipient is invalid" | In `create_job`, if any invalid → raise `AppError(422)` before inserting. ~5 lines. |
| "Max 5000 recipients" | Env var `CERTGEN_MAX_RECIPIENTS_PER_JOB`. |
| "Send email with the certificate attached" | New `Notifier` interface; call after `success` in the processor; track `email_status` column. |
| "Support retry of failed items" | Implement FR-34: reset `failed/generation` rows to `pending`, set job `queued`, schedule processor. |
| "Generate PNG instead of PDF" | New `PngRenderer` implementing `CertificateRenderer`; change dependency + content type. |
| "Allow duplicates" | Remove duplicate check in validator; drop test. |
| "Add a QR code for verification" | ReportLab `qr` widget in renderer; add `GET /verify/{certificate_number}` endpoint. |
| "Add auth" | FastAPI `Security` dependency with API key header on routers. |
| "Switch DB to Postgres" | Change `CERTGEN_DATABASE_URL`; remove SQLite pragmas branch; add `psycopg`. |
| "Cancel a running job" | Add `cancel_requested` flag on job; processor checks it each iteration; status `cancelled`. |

### 19.3 Live-debug practice
Before the interview, deliberately break things and fix them: rename a column, raise inside the renderer, return the wrong status code, remove `commit`. Make sure you can find the cause using logs + tests within minutes.

---

## 20. Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SQLite "database is locked" under concurrent jobs | Medium | Medium | WAL + `busy_timeout`; per-certificate short transactions; document Postgres for production |
| Background task lost on crash | Medium | Medium | Idempotent processor + startup recovery; documented limitation |
| Names with unsupported scripts | Medium (esp. non-Latin names) | Medium | Glyph coverage check → clear per-item failure; documented limitation + WeasyPrint upgrade path |
| Over-engineering eats time | High | High | Required items first (Phases 0–7); optional items only after DoD |
| Not understanding AI-generated code | Medium | **High** | Build phase by phase; type every layer's contract yourself; use §19 as a self-quiz; delete anything you can't explain |
| Large ZIP memory use | Low | Medium | `SpooledTemporaryFile` |
| TestClient/background timing flakiness | Low | Medium | Rely on TestClient semantics; call processor directly in unit tests; no sleeps |
| Windows path issues | Low | Low | `pathlib` only; test on the actual machine |

---

## 21. Assumptions and Open Questions

Defaults below are used **unless you decide otherwise**. Changing them is cheap if decided before Phase 5.

| # | Question | Default assumption |
|---|---|---|
| Q1 | Output format | PDF (the brief leaves it open) |
| Q2 | Is `email` required per recipient? | Yes (needed for identification/dedup; we do **not** send mail) |
| Q3 | Duplicate emails in a job | Later duplicates are marked failed (`DUPLICATE_RECIPIENT`) |
| Q4 | Recipient limit per request | 1000, configurable |
| Q5 | Future `issue_date` allowed? | Yes (no extra rule) |
| Q6 | Authentication | None (documented as out of scope) |
| Q7 | Data retention / cleanup of old files | Not implemented; documented |
| Q8 | Submission format & deadline | Unknown — confirm with the sender (repo link vs zip) |
| Q9 | Should invalid recipients ever cause a `422`? | No — only structural errors do |
| Q10 | Per-recipient custom fields beyond `achievement` | Not supported in v1 |

---

## Appendix A — Sample files

### A.1 `examples/sample_request.json`
```json
{
  "certificate": {
    "course_name": "Advanced Python Bootcamp",
    "issuer_name": "Acme Academy",
    "issue_date": "2026-10-01",
    "signatory_name": "Dr. Jane Roe",
    "signatory_title": "Program Director"
  },
  "recipients": [
    { "name": "Asha Patil", "email": "asha@example.com", "reference_id": "STU-001", "achievement": "with Distinction" },
    { "name": "Rohan Kulkarni", "email": "rohan@example.com", "reference_id": "STU-002" },
    { "name": "Zoë Łukasz", "email": "zoe@example.com" },
    { "name": "", "email": "bad-email" },
    { "name": "Asha Patil (again)", "email": "ASHA@example.com" }
  ]
}
```
Expected: 3 successes (rows 0–2), 2 failures (row 3 invalid name+email, row 4 duplicate email).

### A.2 curl walkthrough (for README)
```bash
# 1. Create a job
curl -s -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d @examples/sample_request.json

# 2. Poll status (replace JOB_ID)
curl -s http://127.0.0.1:8000/api/v1/jobs/JOB_ID

# 3. List only failures
curl -s "http://127.0.0.1:8000/api/v1/jobs/JOB_ID/certificates?status=failed"

# 4. Download one certificate
curl -s -OJ http://127.0.0.1:8000/api/v1/certificates/CERT_ID/download

# 5. Download everything as ZIP
curl -s -OJ http://127.0.0.1:8000/api/v1/jobs/JOB_ID/download
```

### A.3 `.gitignore` essentials
```
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.env
data/
storage/
*.db
sample_certificate.pdf
```

### A.4 uv cheat sheet
| Task | Command |
|---|---|
| Create/refresh env from lockfile | `uv sync` |
| Add runtime dependency | `uv add <pkg>` |
| Add dev dependency | `uv add --dev <pkg>` |
| Remove dependency | `uv remove <pkg>` |
| Run anything inside the env | `uv run <cmd>` |
| Run server | `uv run uvicorn certgen.main:app --reload` |
| Run tests | `uv run pytest` |
| Update lockfile | `uv lock` |
| Install exact lockfile versions (CI) | `uv sync --frozen` |
| Show dependency tree | `uv tree` |
| Pin Python version | `uv python pin 3.12` |

### A.5 Suggested commit sequence
1. `chore: bootstrap project with uv, health endpoint`
2. `feat: config, db, models`
3. `feat: recipient validation + error format`
4. `feat: pdf renderer and certificate numbering`
5. `feat: local file storage`
6. `feat: create job endpoint`
7. `feat: background job processor with per-item failure isolation`
8. `feat: job status, listing, and download endpoints`
9. `feat: zip download and startup recovery`
10. `docs: README with design decisions`
11. `test: coverage gaps and load check`

---

*End of PRD. Next step: begin **Phase 0** and ask to scaffold the project, one phase at a time, so each piece is understood before moving on.*
