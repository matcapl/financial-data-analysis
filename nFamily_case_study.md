# nFamily Case Study — Template Structure + Attempts

Date: 2026-01-26

Purpose: record a concrete, repeatable “proper template structure” for board-pack extraction and explain what we’ve tried on nFamily so far, what worked, what failed, and what the next fixes should be.

This is written as a durable handoff for future agents/LLMs.

---

## 1) Proposed template structure (the “proper” structure)

### 1.1 The guiding model

A board pack is not a dataset; it is a collection of semi-structured “statements” intended for humans.

A robust system needs a template structure that:

- is **section-aware** (P&L vs cash vs operational)
- is **period/scenario/scale aware**
- stores **provenance** (doc/page/table/row/col/coordinates)
- separates **raw observations** from **canonical facts**
- can tolerate partial data without hallucinating

### 1.2 Document → Statements → Facts

**A. Document**
- `document_id`
- metadata: filename, upload time, inferred company, Companies House number, etc.

**B. Statement (or “context key”)**
A board pack contains multiple tables that may reuse line items (e.g., Revenue appears in several places). We need a stable key to distinguish them.

- `context_key`: deterministic identifier (e.g., `p12_t3_pl`)
- optional `statement_type`: `pl`, `cashflow`, `balance_sheet`, `kpi_ops`, `sites`, `bridge` (etc.)
- extracted title / header text

**C. Observation (raw evidence)**
This is the raw extracted artefact (cells or text spans).

- extracted row label text
- extracted column header text
- raw cell value text
- page + coordinates

**D. Candidate Fact (interpretation)**
This is a parsed interpretation of an observation.

- canonical KPI candidate (or unknown)
- period candidate (with confidence)
- scenario candidate (Actual/Budget/Prior)
- scale/unit candidate

**E. Canonical Fact (best view)**
- deterministic selection rules (or explicit approval)
- stored as `financial_metrics` + “best view” query

### 1.3 Template “slots” (what the extractor should try to produce)

For each extracted table (statement), attempt to fill these slots:

1) **Title / Section** (string)
2) **Period axis** (list of period labels)
3) **Scenario axis** (Actual/Budget/Prior)
4) **Scale/unit** (e.g. £, £000)
5) **Line item axis** (row labels)
6) **Value matrix** (line item × period × scenario)

If any slot is missing, we should record that explicitly as a rejection reason, not silently drop data.

### 1.4 Why this structure is “proper”

This structure is more likely to achieve board-grade reliability because it aligns with the real failure modes:

- Period inference is hard → make it explicit.
- Scale inference is hard → store both raw and normalized.
- Line item mapping differs per company → separate global taxonomy from company overrides.
- Packs change month-to-month → anchor on evidence/provenance rather than brittle templates.

---

## 2) nFamily: inputs + goal

### 2.1 Inputs available

Located at: `projects/inputs/nFamily`

Observed files:
- Multiple monthly board pack PDFs (Dec-2024, Jan-2025, Feb-2025, Mar-2025, May-2025, Jun-2025, Sep-2025, Oct-2025)
- `nFamily_Group_Accounts_YE2024.pdf` (Companies House accounts style doc)
- `N Family Club numbers for report.xlsx`

### 2.2 Company identity

- Company: nFamily
- Companies House number: `11986090`

### 2.3 Success criterion (A’s definition)

We know we’re doing well when after ingesting the nFamily files we have ~5–7 reliable line items (longitudinally):

- Group revenue
- Group profit excluding start-up costs
- Group EBITDA excluding start-up costs
- Start-up costs
- Group EBITDA
- Cash balance / cash held on account
- Number of sites

---

## 3) Attempts so far (what we did)

### 3.1 DB + company setup

- Added `companies.companies_house_number` so identity can be stable.
- Created/updated `companies` row for nFamily with CH number `11986090`.

### 3.2 PDF ingestion (board packs)

- Ran ingestion over the nFamily PDFs.
- The pipeline persists canonical facts into `financial_metrics`.

**Result:** meaningful coverage for several KPIs.

At one point we had (approx):
- Revenue: 20 rows
- EBITDA: 28 rows
- EBITDA (excl Start-up Costs): 17 rows
- Start-up Costs: 15 rows
- Cash Balance (from “Opening/Closing Cash”): 20 rows

Missing / not yet reliably mapped:
- Number of Sites
- Group Profit (excl Start-up Costs)

### 3.3 Report generation

- Generated a PDF report for company_id=35:
  - `reports/nfamily_board_report.pdf`

This confirms the end-to-end path works (ingest → findings → report), even if KPI coverage is incomplete.

### 3.4 XLSX ingestion attempt (numbers workbook)

Problem observed:
- `N Family Club numbers for report.xlsx` extracted rows but mapping produced 0 rows.

Root cause (diagnosed):
- The workbook’s only visible sheet appears to be an `IRR target` sheet.
- Column headers were previously `Unnamed: n` (now improved), but even after header inference, the sheet content does not look like a KPI dataset (it looks like an IRR/capital schedule).

Conclusion:
- This workbook is probably not the source of monthly KPI facts we want; or it needs a dedicated extractor if KPI data exists in hidden sheets.

---

## 4) Fixes implemented (to move toward the “proper template”)

### 4.1 Stop silent drops: rejection persistence

- Added `fact_rejections` table and persistence.
- Updated normalization to return rejected rows with structured reasons.

This directly supports the template approach: missing slots become rejections, not silence.

### 4.2 Excel header inference

- Updated `server/app/services/extraction.py` to detect unusable headers and infer a better header row.

This addresses a core real-world failure mode for “numbers workbooks”.

### 4.3 Per-company overrides (without global taxonomy bloat)

- Added `config/company_overrides.yaml`.
- Wired `field_mapper.py` to optionally apply per-company alias overrides keyed by Companies House number.

This is the correct compromise: adaptable per company, but governed.

---

## 5) What’s still suboptimal (and what to do next)

### 5.1 nFamily Group Accounts PDF not extracting

Symptom:
- `nFamily_Group_Accounts_YE2024.pdf` → “No data extracted”.

Likely reason:
- Accounts-style PDFs have different layout than board packs; table detection and OCR heuristics may miss them.

Fix direction:
- Add a dedicated extraction mode for accounts PDFs:
  - detect statement pages by keywords ("profit and loss account", "balance sheet", "cash flow")
  - prefer OCR-to-searchable and then text+table parsing

### 5.2 “Number of Sites” mapping is too naive

We currently see lots of site-related labels in raw extraction (e.g. “Pre-Launch Sites”, “Central Site”, “Hove sites”).

But “Number of Sites” is not the same as “site EBITDA” lines.

Fix direction:
- Add a dedicated **ops/sites statement recogniser**:
  - identify the table where “sites” are a count (not a P&L line)
  - map only count-like rows to Number of Sites
  - add plausibility checks (integer-ish, small range)

### 5.3 “Profit excl start-up” needs a governed definition

This is company-specific and can be ambiguous:
- Is it Operating Profit? Profit? A specific “adjusted profit” line?

Fix direction:
- Introduce a “company metric definition” record:
  - for nFamily, store which observed line corresponds to “Group Profit (excl Start-up Costs)”
  - require human confirmation once

### 5.4 XLSX workflow needs sheet selection + hidden sheet detection

If the workbook contains KPI data in hidden sheets, we won’t see it via the current pandas sheet enumeration.

Fix direction:
- Use `openpyxl` to enumerate hidden sheets and extract them too.
- Add config `xlsx.allow` patterns for nFamily if we identify the correct tab(s).

---

## 6) Recommended next execution steps (for nFamily)

1) Inspect `N Family Club numbers for report.xlsx` for hidden sheets; confirm if KPI data exists.
2) Improve PDF extraction for ops/sites counts.
3) Add a small nFamily-specific mapping/definition for “Group Profit excl start-up”.
4) Re-run full ingestion and regenerate `reports/nfamily_board_report.pdf`.

---

## 7) Lessons applied (living changelog)

This section is the “closed loop”: each row is a real failure mode observed in nFamily, what we changed, and what improved. Keep appending to this over time.

| Date | Issue observed | Root cause | Fix applied | Impact / measurement |
|---|---|---|---|---|
| 2026-01-25 | XLSX ingestion mapped 0 rows (nFamily workbook) | Excel sheets had unusable/duplicate headers and wide timeseries structure; extractor errored on non-IRR sheets | `server/app/services/extraction.py`: header inference + unique headers; wide-timeseries explode; better header scoring | XLSX extraction no longer breaks on “Unnamed:” / duplicate column names; can produce long-form (line_item, period, value) rows |
| 2026-01-25 | Rows were silently dropped during normalization | Normalization skipped failures without persistence | `database/migrations/009_add_fact_rejections.sql` + `server/app/services/rejections_persistence.py` + `normalization.py` returning rejected rows | Pipeline debugging becomes evidence-driven (why rows dropped) rather than guessing |
| 2026-01-25 | Company identity too loose for longitudinal DB | No stable external identifier in schema | `database/migrations/010_add_companies_house_number.sql` + `TODO_company_identity.md` | Enables durable company identity (Track B ready) without blocking Track A |
| 2026-01-26 | Excel sheet processing crashed with “truth value of Series ambiguous” | Duplicate column names → pandas returns Series for `row[col]` | `server/app/services/extraction.py`: `_make_unique_headers` | Stops sheet-level extraction failures; allows multi-sheet ingestion |
| 2026-01-26 | “period_label” from Excel looked like `2020-05-01 00:00:00` and failed normalization | Period normalizer didn’t treat datetime-ish strings as months | `server/app/services/normalization.py`: datetime-string → `%Y-%m` monthly | XLSX-derived month labels normalize into existing period scheme |
| 2026-01-26 | PDF reruns reported failures when they only deduped | Pipeline treated persisted=0 as failure even if skipped>0 | `server/app/services/pipeline_processor.py`: treat “dedupe-only” as success | Reduces false negatives/noise in iterative runs |
| 2026-01-26 | “Sites” KPI mapping produced absurd values | “sites” labels appear in multiple non-count contexts; no plausibility constraints | (Planned) add a sites-count recogniser + plausibility rules | Not yet fixed; tracked here as a known gap |
| 2026-01-27 | KPI spine has gaps + outliers + scenario mixing | Multi-month tables not consistently extracted; some cells are budget/prior/variance; scale/units ambiguous | Generate explicit gaps/errors report + implement selection rules: Actual-only spine, outlier flags, KPI-specific plausibility constraints (esp. sites) and stronger statement/context selection | `reports/nfamily_gaps_and_errors.md` documents missing months + outlier candidates; next work is to eliminate 2025-04/07/08 gaps and fix scale issues |
| 2026-01-27 | PDF extractor hard-coded `period_label=2025-02` in multiple paths | Placeholder default leaked into production extraction, preventing filename-based period hint from applying | `server/app/services/ingest_pdf.py`: remove `2025-02` defaults and allow `period_hint` injection to set period | Reduces misnormalised months and improves odds of complete monthly series when headers don’t parse |

## 8) Notes for future LLMs/agents

- Do not treat a board pack as a single table. Always reason in terms of statements/contexts.
- Never promote LLM guesses to canonical truth without provenance and/or approval.
- Prefer narrow, evidence-backed mapping tasks to end-to-end “read the PDF and summarise” prompts.
