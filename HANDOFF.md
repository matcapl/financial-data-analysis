# Financial Data Analysis — Handoff

## Purpose
This repo ingests board pack PDFs (and some XLSX), persists raw evidence + canonical metrics, and generates findings/reports.

Two tracks:
- Track A: generate useful report output.
- Track B: durable, consistent database persistence with provenance + corroboration.

This handoff captures the current state + how to resume cleanly.

## Current Status (as of 2026-02-04)

### What works end-to-end
- Docker services run and accept uploads.
- Upload pipeline persists:
  - `documents`
  - `extracted_facts_raw` (raw evidence)
  - `financial_metrics` (canonical candidates)
  - `financial_metrics_best` (truth-ish best view)
- Company identity resolution via Companies House number (best-effort).
- Month-matrix tables (months across columns) are extracted into month-level facts.

### Key robustness layers added
- `period_scope` coordinate added (separates `Period` vs `YTD` facts).
- Validation + quality reports stored into `documents.metadata`.
- Revenue YTD reconciliation:
  - flags mismatches in `validation_report`
  - prevents mismatched YTD Revenue from being promoted into `financial_metrics_best`.
- Scale-outlier filtering in best view (median-band).

### Known gaps
- Quarterly revenue facts are generally missing in PDFs; validator reports “missing corroboration”.
- Annual corroboration needs annual facts for 2025 and a complete monthly series for the same year.
- Some older packs (e.g. Dec-2024) still fail to yield reliable monthly Revenue Period.


## Key Files Changed / Added

### Extraction / ingestion
- `server/app/services/ingest_pdf.py`
  - month-matrix extractor
  - pdftotext fallback
  - improved context tagging + `period_scope` propagation
  - statutory accounts yearly Turnover/Revenue extraction

### Mapping / normalization / persistence
- `server/app/services/field_mapper.py` (propagates `period_scope`)
- `server/app/services/normalization.py`
  - respects Yearly period labels (doesn’t coerce `2024` to Monthly)
  - prefixes generic `source_file` (`page_*`) with filename to avoid cross-document collisions
- `server/app/services/persistence.py` (stores `period_scope` and uses it in dedup key)
- `server/app/services/raw_persistence.py` (stores `period_scope`)

### Identity
- `server/app/services/company_identity.py`
- `server/app/api/v1/endpoints/upload.py` (resolves `company_id` using CH number)

### Validation
- `server/app/services/quality_gate.py`
- `server/app/services/validator.py`
- `config/contracts.yaml`

### DB migrations / views
- `database/migrations/012_add_period_scope.sql`
- `database/migrations/013_backfill_period_scope_from_context.sql`
- `database/migrations/014_filter_revenue_ytd_on_reconciliation.sql`


## How to run (next session)

### Start services
```bash
cd projects/financial-data-analysis
docker compose up -d postgres backend
```

### Health check
```bash
curl -sf http://localhost:4000/health
```

### Upload a PDF
```bash
curl -s -X POST http://localhost:4000/api/upload \
  -F "company_id=1" \
  -F "file=@projects/inputs/<CompanyName>/<some-pack>.pdf"
```

### Quick DB scorecard
```bash
cd projects/financial-data-analysis

docker compose exec -T postgres psql -U financial_user -d financial_dev -c \
"SELECT id, original_filename,
        (metadata->'quality_report')->>'ok_for_revenue_analyst' AS ok,
        jsonb_array_length(metadata->'validation_report'->'issues') AS issues
 FROM documents
 ORDER BY id DESC
 LIMIT 10;"
```

### Revenue truth series (Monthly, Period)
```bash
docker compose exec -T postgres psql -U financial_user -d financial_dev -c \
"SELECT p.period_label, fm.value
 FROM financial_metrics_best fm
 JOIN periods p ON p.id=fm.period_id
 JOIN line_item_definitions li ON li.id=fm.line_item_id
 WHERE fm.company_id=<COMPANY_ID>
   AND li.name='Revenue'
   AND fm.value_type='Actual'
   AND p.period_type='Monthly'
   AND COALESCE(fm.period_scope,'Period')='Period'
 ORDER BY p.period_label;"
```


## Obligations for A (Company #2 onboarding)
The agent should ask for these if missing.

1) **Files**
- Save the new company PDFs under:
  - `projects/inputs/<CompanyName>/`
- Ideally include 2 consecutive board packs (e.g. Feb + Mar) to exercise MoM.

2) **Stable identity**
- Provide **Companies House number** (preferred) or equivalent stable identifier.
- If UK company: confirm it’s the correct CH number for dedup across name changes.

3) **What months / periods are covered**
- Tell the agent which months are in the packs.

4) **KPI definitions (minimal)**
- Confirm what “Revenue” means in this context (group revenue vs site vs segment).
- Optional later: confirm Cash/EBITDA semantics.

5) **Expected output / demo goal**
- Minimum demo: Monthly `Revenue` Period series + evidence + quality/validation report.


## What the agent should do first when company #2 is ready
1) Run the pipeline on 1–2 PDFs.
2) Check `documents.metadata.quality_report` + `validation_report`.
3) Verify monthly Revenue Period series exists and looks plausible.
4) Only then widen to the rest of the packs.


## Notes
- Missing YTD is acceptable; reconciliation triggers only when ingested YTD exists.
- YTD that doesn’t match derived cumulative monthly is flagged and filtered from `financial_metrics_best`.
- For corroboration across quarter/annual: needs ingested quarterly/yearly facts in the docs.
