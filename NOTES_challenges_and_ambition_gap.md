# Notes — Challenges & the Ambition Gap (Board-Pack Pipeline)

Date: 2026-01-21

This note is written as a reflective handoff: for A, for future agents, and for any future model that wants to reason about the project’s real constraints. It explains why “variable board packs” are hard, why that collides with a simple upload→ingest→report pipeline, and what a credible bridge from current code reality to board-grade output might look like.

## 1) What we are trying to do (ambition)

The ambition is not “extract numbers from files”. The ambition is:

- Take arbitrary board packs and financial artefacts arriving over time, in different formats.
- Build a coherent, longitudinal view of the business (months/quarters/YTD/years, scenarios like actual/budget/prior).
- Calibrate what is normal vs abnormal.
- Surface the 2–3 most important issues and present them with evidence, context, and the right challenges/questions.
- Do this reliably month after month.

A best-case board member experience is typically:

- Short (3–10 pages) and consistent.
- Anchored on a stable KPI set.
- Exception-led (what changed materially and why it matters).
- Auditable (every statement can be traced back to source pack/page/table).
- Adaptable (still works if the pack changes, or if one month’s data is partial).

That is an extremely high bar: it implies not just extraction but interpretation, quality gating, calibration, and narrative discipline.

## 2) Why variable input formats are the main problem

Board packs vary in ways that break naive extraction:

### 2.1 PDF vs XLSX/CSV are fundamentally different
- **XLSX/CSV** usually contains structured cells and stable headers. Errors are mostly mapping issues.
- **PDF** is a *presentation format*. Tables are shapes, text fragments, and coordinates. Extracting a “table” requires reconstructing layout and reading context.

Even when a PDF contains selectable text:
- column boundaries can shift
- merged cells exist
- headers can be multi-row
- values may be visually aligned but not textually grouped

When PDFs are scanned:
- OCR introduces noise
- characters can be misread (e.g., “£” or commas)

### 2.2 The pack is not one dataset
A board pack mixes:
- P&L by month
- YTD rollups
- prior year comparatives
- budgets and forecasts
- non-financial commentary
- operational dashboards

These sections are semantically different. A pipeline that treats “every table cell as a metric” will inevitably ingest nonsense.

### 2.3 Period labels are not consistently represented
Periods appear as:
- “Oct 25”, “October 2025”, “2025-10”, “Oct FY25”, “Oct (4 wks)”
- “YTD Oct 2025”, “Q2 FY25”, “FY25”
- or sometimes not as explicit text at all (implied by pack title)

If period attribution fails, the whole longitudinal model fails. You can have correct numbers but assigned to the wrong month.

### 2.4 Scale and units are often implicit
Values might be reported in:
- £, £000, £m
- sometimes mixed within the same pack
- sometimes indicated only in a header line or footnote

Without reliable scale detection + normalisation, comparisons can be wildly wrong.

### 2.5 Line item naming is inconsistent
Revenue can appear as:
- “Revenue”, “Sales”, “Turnover”, “Total Revenue”, “Net Sales”, “Group Revenue”
And packs often include prose lines that *look* like rows:
- “Safety: We finished the year at …”

If the system doesn’t distinguish financial line items from prose, the canonical store gets polluted.

## 3) Why this is problematic for “our system” (upload→ingest→DB→report)

A simple pipeline is attractive, but naive assumptions create failure modes:

- The ingest step is forced to decide: “is this a metric?” “what metric?” “what period?” “what scale?” “what scenario?”
- If those decisions are made incorrectly and persisted, everything downstream becomes noisy.
- Reports then become large, incoherent, and untrustworthy.

The system needs an internal separation of concerns:

- raw extraction (capture what was seen)
- canonical facts (what we believe)
- findings/narrative (what we think matters)

If those aren’t separated, you either:
- store nothing (too strict), or
- store everything (too noisy), or
- store partially wrong facts (worst outcome: plausible but incorrect).

## 4) What LLMs are realistically good at vs not (open-minded but grounded)

LLMs can be extremely helpful, but they are not magic.

### 4.1 What LLMs can help with (high leverage)
- **Language-heavy tasks**: summarising narrative text from packs.
- **Mapping suggestions**: proposing synonyms/aliases for line items.
- **Pattern recognition across messy headers**: suggesting period parsing rules.
- **Drafting**: turning structured findings into board-grade prose.
- **Question phrasing**: producing sharp challenges once the factual claim is known.

In short: LLMs are strong at generating *candidate interpretations and phrasing*.

### 4.2 What LLMs are weak/risky at (in this context)
- **Being a trusted source of numeric truth**.
- **Guaranteeing determinism and repeatability**.
- **Avoiding hallucinated numbers or “helpful” fabrications**.
- **Performing consistent accounting transformations without explicit constraints**.

A board-grade system must be auditable. If the system’s “facts” come from a stochastic model, it becomes difficult to defend outputs or debug regressions.

### 4.3 The key mismatch
Ambition demands:
- correctness, consistency, auditability, and robust calibration

But naive use of LLMs tends to give:
- fluent narratives, potentially wrong numbers, variable outputs

So the right use is typically:
- deterministic facts layer → LLM for narrative on top
- LLM for suggestions, not for authoritative DB writes

## 5) Why the current code can’t yet meet the ambition (and why that’s normal)

The project is building toward a professional architecture, but the hard parts are still being solved:

- robust period attribution for PDFs
- robust scale/unit normalisation
- broad taxonomy coverage without DB pollution
- complete provenance (doc/page/table/row/col)

Until those are stable, it’s normal for output to feel inconsistent or “amateur”: the system cannot yet trust the extracted signals.

## 6) How the gap can be bridged (non-prescriptive, but plausible paths)

This section is intentionally open-ended: it describes the shape of a bridge, not a single prescribed plan.

### 6.1 Separate “capture everything” from “believe and report”
A mature system typically holds:
- raw extraction (everything observed)
- canonical facts (high-confidence, normalised)
- findings (prioritised claims + evidence)

This allows the system to improve extraction without rewriting history, and to be transparent about what was dropped or uncertain.

### 6.2 Make the system calibration-first
Board thinking is delta + normal range.

To do that, you need:
- consistent time series
- stable definitions
- materiality thresholds

That suggests focusing on a small KPI set first, achieving continuity, then expanding.

### 6.3 Treat new uploads as corroboration events
A professional board system expects:
- multiple documents that refer to the same month
- occasional restatements

So it should:
- preserve competing candidates
- choose the best (with deterministic rules)
- flag material disagreements (restatement/governance)

### 6.4 Create a human-in-the-loop “review surface”
Even with strong engineering, board packs are idiosyncratic.

A pragmatic bridge is:
- highlight ambiguous mappings and scale/period uncertainty
- allow quick corrections
- feed those corrections back into mappings and rules

### 6.5 Use LLMs as advisors and narrators
A credible approach is:
- deterministic facts + findings
- LLM generates narrative and phrasing
- LLM proposes mapping updates (aliases / scale guesses)
- those proposals require approval or corroboration before affecting canonical facts

This can produce professional output while keeping the fact base defensible.

## 7) Open questions for a better model/person to think through

- What is the minimal canonical KPI set that yields a board-grade pack for this specific business?
- How should the system model revisions/restatements (versioned facts vs best view vs both)?
- What is the best way to extract period + scale reliably from board-pack PDFs (layout models, template detection, vendor OCR, or per-client templates)?
- What is the right balance between:
  - strict quality gating (fewer facts but cleaner)
  - permissive storage (more facts but requires downstream filtering)?
- How should the product present uncertainty without undermining trust?

## 8) Conclusion

This project is difficult because the inputs are not stable datasets; they are semi-structured documents intended for humans. The ambition (board-grade, consistent, auditable, adaptive) is real and achievable, but it requires a robust internal structure that separates extraction from belief, and a disciplined approach to using LLMs as assistants rather than as the canonical source of truth.

The most important thing is to keep the system’s core “truth layer” deterministic and explainable, while allowing flexibility and intelligence in the narrative and suggestion layers.

## 9) Addendum — two tracks that often get conflated

It’s common to mix up two goals:

### Track A: Board-member-quality agent output (near-term)

- Objective: produce short, consistent, exception-led board packs from messy uploads.
- Success looks like: trustworthy narrative + evidence citations, even when some data is missing.
- Hard constraint: *trust and auditability* (don’t be wrong with confidence).

### Track B: A durable “central truth DB” per company (longer-term)

- Objective: maintain an always-up-to-date, company-identified, coordinate-mapped time series.
- Success looks like: continuity over months/years, stable semantics (period/scenario/units), derived rollups.
- Hard constraint: *governance* (avoid taxonomy drift and accidental redefinitions).

These tracks are related but should be planned separately so we don’t either:

- over-productise early and stall the board-quality output, or
- generate impressive narrative without building a truth boundary that can evolve into a reliable database.

The bridge is the same structural idea:

- capture raw observations with provenance,
- keep candidate interpretations separate,
- promote to canonical truth only with deterministic corroboration or explicit approval.
