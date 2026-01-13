# Board Pack Analyst (Fordhouse) – Product + Tech Reset

## What you’re building (crisp)
An internal **board-pack review assistant** for investment professionals.

Input: monthly board pack + management accounts + ad-hoc docs + history + budget/forecast + (optionally) minutes/notes.

Output (for tomorrow’s story):
- **What happened** (metrics, variances, exceptions)
- **Why it happened** (evidence-backed drivers: commentary + numbers)
- **So what** (risks, questions, challenges, next steps)
- **Citations** (every claim links to the source page/table/row)

The key product promise: *faster prep, higher-quality challenge questions, and consistent coverage month-to-month*.

## What’s “the middle” and why it’s currently weak
The “middle” is the **domain layer** between UI upload and backend storage/LLM output:

1) **Canonical data model / taxonomy**
- What counts as “Revenue”, “Gross profit”, “ARR”, “Bookings”, “Churn”, etc.
- How periods are represented (month/quarter/YTD, fiscal vs calendar)
- How business units/service lines/regions are represented

2) **Provenance**
- Every extracted number needs: source document + page + table + cell/row + extraction confidence.

3) **Normalization + reconciliation**
- Period normalization, units, sign conventions, currency
- Duplicate detection across files, restatements, updated packs

4) **Analysis engine**
- Variance logic + thresholds + “typical range” definitions
- KPI definitions live in config (not hard-coded), versioned

5) **Evidence-first generation**
- LLM is only for narrative synthesis and question phrasing; it should cite structured facts.

This repo already has the beginnings of (1)/(3)/(4) via `config/*.yaml` and the pipeline in `server/app/services/*`.
What’s missing is consistent provenance + a clean “analysis contract” that the UI and narrative layer can trust.

## Recommended v1 (tomorrow’s meeting version)
Keep it narrow: **Revenue Analyst POC** (matches your scope docs).

### User flow
1. Upload board pack / management accounts (CSV/XLSX/PDF)
2. System ingests → extracts → maps to canonical revenue metrics
3. System outputs one structured page:
   - MoM / YoY / vs Budget / YTD / outturn deltas
   - Exceptions (above threshold)
   - 5–10 questions + challenges, each with citations

### v1 success criteria
- Works on 1 portco end-to-end with repeatable output
- Output is consistent month-to-month
- Every claim is traceable to a source

## v2 (real “board pack analyst”)
Add layers incrementally:
- Qualitative commentary checks (“does the story match the numbers?”)
- Topic tracking across months (repeat issues, inconsistent narrative)
- Minutes/notes ingestion → “open questions” register
- Benchmarking packs (optional) + exit KPI tracking

## Concrete tech architecture (clean boundaries)
### Storage
- **Object store**: raw files (pdf/xlsx/csv), immutable, versioned
- **Relational DB**: canonical facts + derived metrics + questions + reports
- **Vector index** (optional v2): chunked text for semantic retrieval (commentary/minutes)

### Pipeline (deterministic core)
- Extract (tables/text) → Map (taxonomy) → Normalize (period/units) → Persist (facts) → Derive (metrics) → Generate (questions)

### “Narrative” layer (LLM)
- Inputs: *only* structured facts + retrieved citations
- Outputs: narrative paragraphs + question phrasing
- Guardrails: claim-checking against facts; refusal to invent numbers

## What to say if asked “why is this defensible?”
- Deterministic analysis for numbers (auditable, testable)
- LLM only for synthesis and language
- Provenance on every number prevents hallucinated business decisions

## 48-hour cleanup targets (if you want to ship a decent demo)
1. Make provenance first-class: store page/table/row references for each fact
2. Define a single “analysis output contract” JSON for:
   - revenue summary
   - exception list
   - questions/challenges (each with citations)
3. Add one integration test: sample CSV/XLSX → expected revenue deltas + question count

## Repo pointers (where this maps)
- Pipeline core: `server/app/services/pipeline_processor.py`
- Mapping/normalization: `server/app/services/field_mapper.py`, `server/app/services/normalization.py`
- Derived metrics: `server/app/services/calc_metrics.py`
- Question generation: `server/app/services/questions_engine.py`
- YAML configs: `config/*.yaml`

## Open questions to resolve (fast)
- What is the canonical revenue taxonomy for your first portco?
- Period rules: fiscal year start? how to treat 13-period calendars?
- Budget format: monthly budget vs run-rate vs reforecast?
- Minimum acceptable provenance for v1 (page-level is usually enough)
