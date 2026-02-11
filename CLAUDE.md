# CLAUDE.md (Updated)

This file is guidance for coding agents working on this repository.

Canonical reference: `AGENT_GUIDE.md`.

## Current architecture (canonical)

This repo runs a **FastAPI** backend and a **React** frontend.

### Frontend (`client/`)
- React client for uploading files and viewing generated reports.

### Backend (`server/`)
- Entry point: `server/main.py`
- Production start: `scripts/deploy-start.sh`
- API routes: `server/app/api/v1/router.py`
  - Upload: `server/app/api/v1/endpoints/upload.py`
  - Reports: `server/app/api/v1/endpoints/reports.py`

### Data pipeline (canonical path)
- Orchestrator: `server/app/services/pipeline_processor.py`
  - PDF ingestion: `server/app/services/ingest_pdf.py`
  - XLSX/CSV ingestion: `server/app/services/extraction.py` → `field_mapper.py` → `normalization.py` → `persistence.py`
  - Derived metrics: `server/app/services/calc_metrics.py`
  - Prioritisation/findings: `server/app/services/findings_engine.py`
  - Report generation: `server/app/services/report_generator.py`

### Selection + provenance (single source of truth)
- `server/app/services/fact_selector.py`
  - Confidence-aware selection of best metric candidate + evidence (doc/page/etc).

### Database
- PostgreSQL with migrations in `database/migrations/`.
- Key tables for the board-pack workflow:
  - Canonical facts: `financial_metrics`
  - Findings/prioritisation: `reconciliation_findings`
  - Raw extraction layer: `extracted_facts_raw`

## Legacy / avoid

- `server/main_old.py` is legacy and should not be extended.
- Prior docs referenced a `server/scripts/` directory and a Node backend; the canonical code lives in `server/app/services/` and the backend is FastAPI.

## Agent rules (avoid duplication)

- Do not create parallel pipelines.
- Do not re-implement selection logic outside `fact_selector.py`.
- New board logic should produce `reconciliation_findings` and be surfaced by `report_generator.py`.
