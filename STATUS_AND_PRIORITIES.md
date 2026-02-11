# Status & Priorities (Board-Pack Pipeline)

Last updated: 2026-01-21

This file is a working handoff for agents improving the repo.

## Current state (what works)

- **Upload → ingest → canonical DB**: ingestion persists a clean canonical subset instead of dumping raw rows.
- **Reports are usable**:
  - No longer dumps all `financial_metrics` rows into PDF.
  - Anchors KPI summary to the latest monthly period by `periods.start_date`.
  - If latest-period Revenue is missing/unreliable, it says so explicitly (no silent fallback).
- **Findings drive the front page**:
  - The report’s “Top Findings” + “Top Questions” come from `reconciliation_findings`.
  - `questions_engine.py` output is intentionally not used in the report.
- **Corroboration/restatement detection exists**:
  - Cross-document KPI differences create `cross_document_restatement` findings.
  - Severity increases when the affected period is considered “closed”.
- **Best-fact selection is consistent**:
  - A DB view `financial_metrics_best` exists (one best row per key).
  - `config/observations.yaml` now queries `financial_metrics_best`.

## Canonical entrypoints

- Server entrypoint: `server/main.py`
- Upload: `server/app/api/v1/endpoints/upload.py`
- Pipeline: `server/app/services/pipeline_processor.py`
- Findings: `server/app/services/findings_engine.py`
- Report: `server/app/services/report_generator.py`
- Selector: `server/app/services/fact_selector.py`

Avoid extending legacy: `server/main_old.py`.

## Key gaps / omissions

### 1) Coverage gap: taxonomy is too small
- Step 5 introduced strict line-item filtering: only known canonical `line_items` are persisted.
- Right now canonical set is effectively KPI-centric (Revenue/Gross Profit/EBITDA unless expanded).
- Outcome: many valid board-pack metrics are dropped even if extracted correctly.

**Fix**: expand `config/fields.yaml:line_items` to include the minimum board-pack metric set (e.g., 20–40 items).

### 2) Period coverage still incomplete
- Many extracted PDF rows have missing/wrong `period_label`.
- Filename period hints help, but multi-month tables still need better header parsing.

**Fix**: improve PDF header-mapped extraction to reliably assign month + value_type.

### 3) Units/scale normalisation not robust
- `normalization.py` can scale values if it sees evidence (`£000`, `£m`, etc.).
- `ingest_pdf.py` tries to propagate page-level unit hints, but often the PDF doesn’t expose them via text extraction.

**Fix**: detect scale at table-level (or known-pack rule), store scale explicitly, not just in notes.

### 4) Provenance is incomplete for evidence
- `document_id` is now always created when missing, but `source_table/source_row/source_col` are frequently `None`.
- Evidence in questions can be thin.

**Fix**: improve provenance capture for the high-signal tables (P&L).

### 5) Findings coverage is still shallow
- Findings exist for Revenue, Gross Profit, EBITDA.
- Missing: cash conversion, liquidity/runway, net debt, working capital, covenant headroom, outturn vs budget, forecast accuracy.

**Fix**: implement more findings types; each should include `suggested_questions`.

### 6) Quality gate is KPI-only and “drop on floor”
- KPI noise is rejected at normalisation (year tokens, tiny values).
- Rejections are logged but not persisted as a “quarantine” record.

**Fix**: add a quarantine table or enrich `extracted_facts_raw` with reject reasons.

## Known rough edges / current errors

- Some reports still show: “Insufficient reliable Revenue Actual for latest period …”.
  - This is expected until period+scale extraction improves.
- Evidence citations sometimes show `tNone rNone cNone` due to missing provenance.
- Question engine output can still be garbage; this is fine because it’s not consumed by the report.

## Priorities (recommended order)

1) **Expand canonical line-item taxonomy** (`config/fields.yaml`)
2) **Fix PDF period attribution** (multi-month table header parsing)
3) **Fix scale detection + explicit scale storage**
4) **Improve provenance fields** (doc/page/table/row/col)
5) **Add findings for cash/net debt/working capital/outturn/forecast accuracy**
6) **Add quarantine or rejection persistence**

## Where to add improvements (rules)

- Do not create parallel pipelines.
- Do not re-implement selection logic outside `fact_selector.py`.
- All board logic should output `reconciliation_findings`.
- Reports should surface findings + their `suggested_questions`.

## Quick run commands (local)

- Generate findings:
  - `./.venv/bin/python server/app/services/findings_engine.py <company_id>`

- Generate report:
  - `./.venv/bin/python server/app/services/report_generator.py <company_id> <output.pdf>`

- Run unit tests:
  - `./.venv/bin/python -m pytest tests/unit/ -q`
