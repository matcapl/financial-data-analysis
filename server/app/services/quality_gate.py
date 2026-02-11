"""quality_gate.py

Deterministic pipeline quality checks.

Purpose:
- Provide a structured view of coverage/completeness at each stage.
- Surface blockers early (before report generation).

Design principles:
- Deterministic and debuggable (no LLM dependency).
- Works across companies by relying on canonical metrics/periods.
- Stores results in `documents.metadata` for UI/report consumption.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _is_monthly_period(period_label: str) -> bool:
    if not period_label or len(period_label) != 7:
        return False
    # YYYY-MM
    return period_label[4] == '-' and period_label[:4].isdigit() and period_label[5:7].isdigit()


def _month_to_int(period_label: str) -> Optional[int]:
    if not _is_monthly_period(period_label):
        return None
    year = int(period_label[:4])
    month = int(period_label[5:7])
    if month < 1 or month > 12:
        return None
    return year * 12 + (month - 1)


def _int_to_month(v: int) -> str:
    year = v // 12
    month = (v % 12) + 1
    return f"{year:04d}-{month:02d}"


def _month_range(end_month: str, months: int) -> List[str]:
    end = _month_to_int(end_month)
    if end is None:
        return []
    start = end - (months - 1)
    return [_int_to_month(v) for v in range(start, end + 1)]


def _normalize_value_type(value_type: Optional[str]) -> str:
    t = (value_type or '').strip().lower()
    if not t:
        return 'Actual'
    if 'budget' in t:
        return 'Budget'
    if 'prior' in t or 'py' in t or 'last year' in t:
        return 'Prior Year'
    if 'forecast' in t or 'outturn' in t or 'fcst' in t:
        return 'Forecast'
    if 'actual' in t:
        return 'Actual'
    return value_type or 'Actual'


@dataclass(frozen=True)
class MetricCoverage:
    metric: str
    months_present: int
    months_missing: int
    latest_month: Optional[str]
    months_present_list: List[str]


@dataclass(frozen=True)
class QualityReport:
    ok_for_revenue_analyst: bool
    blockers: List[str]
    warnings: List[str]
    coverage: Dict[str, MetricCoverage]
    latest_month: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # dataclasses nested dict conversion already handled by asdict
        return d


def assess_revenue_analyst_quality(
    *,
    normalized_rows: Iterable[Dict[str, Any]],
    required_metric: str = 'Revenue',
    ltm_months: int = 12,
) -> QualityReport:
    """Assess whether we can produce FH-style 'Group Revenue (always)' output.

    This version accepts normalized in-memory rows.
    For production/reporting, prefer `assess_revenue_analyst_quality_from_db`.
    """

    rows = list(normalized_rows or [])

    by_metric: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in rows:
        metric = str(r.get('line_item') or r.get('line_item_name') or '').strip()
        period = str(r.get('period_label') or '').strip()
        if not metric or not _is_monthly_period(period):
            continue

        vt = _normalize_value_type(r.get('value_type'))
        by_metric.setdefault((metric, vt), []).append(r)

    def months_for(metric: str, value_type: str) -> List[str]:
        ms = [r.get('period_label') for r in by_metric.get((metric, value_type), [])]
        ms = [m for m in ms if isinstance(m, str) and _is_monthly_period(m)]
        return sorted(set(ms), key=lambda x: _month_to_int(x) or 0)

    return _assess_from_month_sets(
        required_metric=required_metric,
        ltm_months=ltm_months,
        actual_months=months_for(required_metric, 'Actual'),
        budget_months=months_for(required_metric, 'Budget'),
        prior_year_months=months_for(required_metric, 'Prior Year'),
    )


def assess_revenue_analyst_quality_from_db(
    *,
    conn,
    company_id: int,
    required_metric: str = 'Revenue',
    ltm_months: int = 12,
) -> QualityReport:
    """Assess readiness using the persisted canonical facts in Postgres.

    This avoids mismatches between in-memory row shapes and what actually made it
    into `financial_metrics` / selector views.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              p.period_label,
              COALESCE(fm.value_type, 'Actual') AS value_type
            FROM financial_metrics fm
            JOIN periods p ON p.id = fm.period_id
            JOIN line_item_definitions li ON li.id = fm.line_item_id
            WHERE fm.company_id = %s
              AND li.name = %s
              AND COALESCE(fm.period_scope, 'Period') = 'Period'
              AND p.period_type = 'Monthly'
            """,
            (company_id, required_metric),
        )
        rows = cur.fetchall()

    actual_months = []
    budget_months = []
    prior_year_months = []

    for period_label, value_type in rows:
        pl = str(period_label or '')
        if not _is_monthly_period(pl):
            continue
        vt = _normalize_value_type(value_type)
        if vt == 'Actual':
            actual_months.append(pl)
        elif vt == 'Budget':
            budget_months.append(pl)
        elif vt == 'Prior Year':
            prior_year_months.append(pl)

    return _assess_from_month_sets(
        required_metric=required_metric,
        ltm_months=ltm_months,
        actual_months=sorted(set(actual_months), key=lambda x: _month_to_int(x) or 0),
        budget_months=sorted(set(budget_months), key=lambda x: _month_to_int(x) or 0),
        prior_year_months=sorted(set(prior_year_months), key=lambda x: _month_to_int(x) or 0),
    )


def _assess_from_month_sets(
    *,
    required_metric: str,
    ltm_months: int,
    actual_months: List[str],
    budget_months: List[str],
    prior_year_months: List[str],
) -> QualityReport:
    latest = actual_months[-1] if actual_months else None

    blockers: List[str] = []
    warnings: List[str] = []
    coverage: Dict[str, MetricCoverage] = {}

    if latest:
        ltm = _month_range(latest, ltm_months)
        present = set(actual_months)
        missing = [m for m in ltm if m not in present]

        coverage[required_metric] = MetricCoverage(
            metric=required_metric,
            months_present=len([m for m in ltm if m in present]),
            months_missing=len(missing),
            latest_month=latest,
            months_present_list=[m for m in ltm if m in present],
        )

        if len(ltm) >= 2:
            prev_month = ltm[-2]
            if prev_month not in present:
                blockers.append(f"Missing {required_metric} Actual for prior month {prev_month} (cannot compute MoM)")

        if len(missing) > 0:
            warnings.append(f"Missing {len(missing)}/{ltm_months} months of {required_metric} Actual in LTM window ending {latest}")

        if latest not in budget_months:
            warnings.append(f"Missing {required_metric} Budget for {latest} (cannot compute budget variance)")
        if latest not in prior_year_months:
            warnings.append(f"Missing {required_metric} Prior Year for {latest} (cannot compute YoY)")

    else:
        blockers.append(f"Missing monthly {required_metric} Actual series (cannot produce baseline revenue reporting)")

    ok = (len(blockers) == 0)

    return QualityReport(
        ok_for_revenue_analyst=ok,
        blockers=blockers,
        warnings=warnings,
        coverage=coverage,
        latest_month=latest,
    )
