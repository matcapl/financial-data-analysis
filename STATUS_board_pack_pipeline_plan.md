# Status — Board-Pack Pipeline Plan (Ambition → Board-Grade)

Date: 2026-01-25

This is a status-oriented plan, written to emphasise *why* we are doing things and *what* we are trying to achieve, rather than being overly prescriptive about implementation steps. The goal is to keep the system’s direction disciplined while still leaving room for LLMs (and future engineering choices) to pleasantly surprise us.

## 1) The outcome we are aiming for (what “board-grade” means)

We are not trying to build “a PDF number extractor”. We are trying to produce a repeatable monthly/quarterly board experience that is:

- **Short and consistent**: a stable output structure that doesn’t sprawl as input documents vary.
- **Exception-led**: focuses attention on the 2–3 most material movements, not every metric.
- **Longitudinal**: builds a coherent story across months/quarters/YTD/years.
- **Auditable**: every claim can be traced back to a specific source document, page, and (where applicable) table region/cell coordinates.
- **Robust to pack variation**: still works when the pack layout changes or sections are missing.

This is a high bar because the inputs are semi-structured documents intended for humans, not stable datasets.

## 2) Why the naive “upload → ingest → DB → report” approach fails

Board packs are variable in exactly the ways that break naive pipelines:

- **PDFs are presentation-first**: tables are coordinates and text fragments, not clean rows/columns.
- **A pack is not one dataset**: the same document includes P&L, rollups, comparatives, budgets, operational dashboards, and narrative.
- **Periods are ambiguous**: month labels, FY conventions, implied periods, and multi-row headers.
- **Scale/unit is implicit**: £, £000, £m (sometimes mixed; sometimes only in footnotes).
- **Line item naming is inconsistent**: synonyms, grouping changes, and prose that resembles rows.

If the ingest stage is forced to “decide truth” too early (metric name, period, scale, scenario), errors become *persisted facts*. Downstream reporting then becomes noisy or—worse—plausible but wrong.

So the plan is not “extract harder”; it is to build a system that can **hold uncertainty, preserve evidence, and converge toward stable truth over time**.

## 3) The guiding principle: separate *capture* from *belief* from *narrative*

A credible bridge to board-grade output requires an internal separation of concerns:

- **Capture (raw extraction)**: record what was observed, with maximal provenance.
- **Belief (canonical facts)**: decide what we believe is true, under deterministic and explainable rules, optionally with human confirmation.
- **Narrative (findings and challenges)**: communicate what matters and why, using language and framing.

We do this because:

- It preserves auditability.
- It prevents DB pollution.
- It allows improvements to extraction without rewriting history.
- It gives a stable substrate for narrative generation.

## 4) How we should use LLMs (strong leverage, disciplined boundaries)

LLMs are extremely valuable here, but not as the authoritative source of numeric truth.

**Where LLMs shine**
- Summarising narrative sections.
- Suggesting line-item synonym mappings.
- Proposing period parsing interpretations.
- Drafting board-grade commentary and questions.

**Where LLMs are risky**
- Writing “facts” directly into a canonical DB.
- Producing deterministic numeric transformations without strict constraints.

**Therefore**: LLMs should act as **advisors and narrators**. They can propose mappings and interpretations, but the system should treat those proposals as candidates that require corroboration (deterministic checks) or explicit approval before becoming canonical.

This approach is more likely to produce trustworthy output because it aligns with the ambition’s requirements: correctness, consistency, repeatability, and auditability.

## 5) What “progress” looks like (the real milestones)

The most important milestones are not “support more formats” but:

- **Period attribution becomes reliable** (and explainable).
- **Scale/unit normalisation becomes reliable** (and explicit).
- **A small KPI spine becomes continuous over time**.
- **Provenance is complete** (doc/page/table/row/col/coordinates).
- **The system can say “unsure”** without producing overconfident nonsense.

A project can feel “amateur” until these foundations stabilise; that’s normal. Once they do, narrative quality and board usability improve rapidly.

## 6) The “KPI spine” approach (focus to close the ambition gap)

A board-grade pack is typically anchored on a stable KPI set.

We should intentionally focus first on a **minimal canonical KPI set** (e.g., ~10 metrics) that yields a coherent board narrative for most companies:

- Group Revenue
- Gross Profit (if available)
- EBITDA
- Operating Profit
- Net Profit
- Operating Cash Flow
- Net Cash / Cash Balance
- Net Debt
- Working Capital (or key components)
- Headline KPI(s) as needed

Rationale:

- A small set enables continuity and calibration.
- It reduces mapping ambiguity.
- It keeps the output short and consistent.
- It creates a stable foundation for later breadth (regional/divisional breakdowns, custom company metrics).

## 7) The “central truth DB” vision (per-company, coordinate-mapped, longitudinal)

Longer-term, we want a reliable middle database that—per company—maintains a consistent, continuously updated view of key financials.

**The end-state is:**

- Each company has a **unique company identifier**.
- Each uploaded document is associated with that company.
- The system stores a **time series** for the KPI spine, consistently recognised across documents.
- Each stored fact has:
  - a structured **period** (month/quarter/YTD/year; with clearly defined conventions)
  - a structured **scenario** (actual/budget/prior/forecast)
  - explicit **unit/scale** normalisation
  - **provenance and coordinates** (document id, page, and extracted region/cell evidence)
  - optional **derived data** (e.g., quarterly/annual rollups derived from monthly; deltas; margins)

This DB becomes the backbone for calibration, anomaly detection, and narrative stability.

### 7.1 Company identification (Companies House number)

It is sensible to anchor identity on a Companies House number (or equivalent canonical id per jurisdiction), because:

- It prevents silent duplication (“Acme Ltd” vs “Acme Limited”).
- It makes time series durable over years.
- It supports downstream governance and audit.

A practical approach can be hybrid:

- The system attempts **automatic identification** (from pack cover page, company name, footer, email domain, etc.).
- The user **confirms or corrects** the Companies House number.
- The confirmed id becomes part of the document ingestion contract.

This increases reliability without making the product unusably strict.

### 7.2 Derived data (monthly, quarterly, annual)

We ultimately want both:

- **Provided facts** (as stated in the pack).
- **Derived facts** (computed rollups and standardised views).

But derived facts must remain auditable:

- Derived values should record the computation recipe and the contributing canonical facts.
- If the source pack provides quarterly/annual rollups that disagree with derived ones, that should be flagged as a potential restatement or definition mismatch.

## 8) Why we are not over-prescribing implementation steps

This plan intentionally avoids pinning to one extraction library, one schema, or one interface design because:

- The main constraints are conceptual (uncertainty, provenance, determinism, calibration).
- Multiple technical paths could satisfy these constraints.
- We want room for LLM-assisted workflows and emergent improvements.

What must remain non-negotiable is the *shape* of the system:

- Evidence-first capture
- Deterministic canonical truth
- LLM-as-advisor/narrator
- Calibration + continuity as the core product

## 9) Two parallel tracks (important clarification)

We should explicitly treat the work as two related but distinct tracks.

### Track A — “Board member agent quality” (this repo’s immediate objective)

Goal: generate board-grade output from messy packs **reliably and defensibly**.

- The contract here is *board usefulness*: short, consistent, exception-led narrative.
- The core constraint is *trust*: every statement needs evidence and provenance.
- The system must handle uncertainty safely (prefer “insufficient evidence” over plausible-but-wrong).

This track is about building a robust **pipeline and reasoning surface** over semi-structured documents.

### Track B — “Central truth DB per company” (longer-term product substrate)

Goal: maintain a continuously updated, company-identified, coordinate-mapped time series for key metrics.

- The contract here is *durable data continuity*: stable company identity + consistent period/scenario/unit semantics.
- The core constraint is *governance*: preventing taxonomy drift and accidental redefinitions.

This track is about building a reliable **data product** that survives months/years of uploads.

### Why splitting tracks helps (and why it’s not a contradiction)

A common failure mode is trying to productise the “perfect database” too early and losing momentum on the board-grade narrative (or vice versa).

Splitting tracks lets us:

- push toward board-grade output quickly (Track A), while
- making sure the truth layer evolves in a governed, auditable way (Track B), without forcing premature multi-company design.

### How the tracks converge

They converge at the **truth boundary**:

- Track A needs a deterministic, provenance-rich “best view” of facts for narrative.
- Track B needs exactly the same evidence + mapping + period/unit discipline to avoid DB pollution.

So we can build Track A “now” in a way that naturally supports Track B later, without fully committing to the final DB product scope.

## 10) How LLMs fit across both tracks (handoff guidance)

LLMs should be used as *proposers* and *communicators*, not as authoritative writers into canonical truth.

- LLMs may propose mappings (observed label → canonical KPI), period interpretations, unit guesses, and narrative drafts.
- The system (deterministic checks) and/or a human must approve promotions into canonical facts.

This is the key: **pleasant surprises are welcome in candidate space; canonical truth must remain explainable.**

---

If we want a single sentence that captures the strategy:

**We are building a system that can safely learn from messy documents over time by separating what it sees from what it believes, anchoring belief in deterministic, auditable facts, and using LLMs to propose interpretations and generate board-grade narrative on top.**
