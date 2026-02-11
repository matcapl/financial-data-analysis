# Next Steps — Robust, Cross-Company

## Top 3 safe incremental changes (real impact)
1) **Add a 1-command scorecard** (coverage + key issues) and run it after every upload.
2) **Harden unit/scale detection into structured fields** (don’t rely on notes), and validate consistency.
3) **Second-company trial with a fixed checklist** (1–2 packs only) to force generality.

## Critique (read this first)
- "Derived metrics table" is useful but not required to improve correctness right now. The validator already computes derived series in-memory; persisting them adds schema + data lifecycle complexity and risks distracting from extraction/mapping improvements.
- "Quarter/Annual ingestion" is underspecified. Many board packs do not include explicit quarterly/annual revenue facts in a consistent format; building extraction for them may have low ROI until we see a second-company pack that actually contains these tables.
- "Period scope taxonomy beyond YTD" can become an ontology project. It only pays off if we can reliably infer these scopes from documents; otherwise we create categories that stay empty or are misclassified.
- "Report improvements" help demos but don’t fix truth quality. Without fixing extraction/mapping + units, better prose can mask data issues.
- Some items are phrased as inevitabilities ("will make corroboration meaningful"). In practice, corroboration still fails when documents mix definitions (group vs site), scopes (YTD vs Period), or units.

Goal: raise Track A (useful reports) + Track B (durable truth DB) while staying versatile across board-pack styles.

## Priority 0 — Don’t regress
- Keep the invariant: **raw evidence is always preserved** (`extracted_facts_raw`) and canonical/promotion is conservative.
- Keep the invariant: **best view should prefer “missing” over “wrong”**.

## Priority 1 — Second-company trial (generalisation test)
Purpose: expose overfitting and missing general heuristics.
- Add company #2 PDFs under `projects/inputs/<CompanyName>/`.
- Require stable ID (Companies House number) and implement a non-nFamily override entry in `config/company_overrides.yaml`.
- Run 1–2 packs first; only widen after:
  - Monthly `Revenue` `period_scope=Period` exists with plausible magnitude.
  - `documents.metadata.quality_report.ok_for_revenue_analyst` is true or explainable.
  - `validation_report` is not dominated by `scale_outlier`.

## Priority 2 — Derived metrics table (optional, defer unless needed)
Purpose: enable auditability of derived series without polluting ingested truth.
- Real impact: medium (helps debugging + UI), but not required for correctness because validator can derive on-demand.
- Cost/risk: adds schema + data lifecycle complexity.
- Recommendation: defer until after company #2 trial, unless you need derived series visible in UI.

## Priority 3 — Unit/scale discipline (general)
Purpose: avoid silent unit mismatches and make corroboration meaningful.
- Real impact: high (this repeatedly caused false mismatches and bad best-view promotion).
- Implementation: moderate. Start by adding structured fields (even if nullable) and populating them from the existing unit detection.
- Avoid overclaim: unit detection will not solve semantic mismatches (group vs site, YTD vs Period), but it removes a common failure mode.
- Minimal safe checks:
  - if two candidates for same (metric, period, scope) imply different scales, flag.
  - if annual vs sum(monthly) mismatch is ~1000×, flag “scale mismatch suspected”.

## Priority 4 — Period scope taxonomy beyond YTD
Purpose: prevent semantic collisions.
- Extend `period_scope` enum-ish values:
  - `Period`, `YTD`, `FY`, `LTM`, `BudgetYTD` (only when observed in docs).
- Improve context tagging:
  - tables with FY totals should not be coerced into `Yearly` unless `period_label` is a year.

## Priority 5 — Quarter/Annual ingestion (only when present)
Purpose: enable corroboration where documents actually contain these facts.
- Real impact: conditional. If the docs don’t contain quarter/annual tables, extraction work here is wasted.
- Recommendation: implement only after we confirm company #2 (or a different nFamily pack) has clean quarterly/annual facts.
- Minimal safe action: ensure anything labeled FY is not mis-stored as `Yearly` unless `period_label` is a 4-digit year.

## Priority 6 — Reporting improvements (Track A)
Purpose: demoable outputs even with gaps.
- Report should:
  - always cite evidence (doc/page/table/col)
  - explicitly state missing corroboration (budget/PY/YTD/quarterly/annual)
  - never treat mismatched YTD as corroboration.

## Maintenance / hygiene
- Reduce noise:
  - remove obsolete `version:` from `docker-compose.yml` warning (optional).
- Add a one-command “scorecard” script:
  - prints coverage, latest month, top validation issues.
