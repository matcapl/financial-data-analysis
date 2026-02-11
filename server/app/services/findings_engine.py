#!/usr/bin/env python3
"""findings_engine.py

Deterministic, board-pack oriented findings generation.

Initial scope (v0.x): generate a "Group Revenue" finding pack for the latest
usable monthly period, using the best available canonical metrics.

Outputs into reconciliation_findings so the report generator can surface the
highest-priority issues.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add proper path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'server'))

try:
    from app.utils.utils import get_db_connection
    from app.services.fact_selector import (
        best_metric_candidate,
        find_latest_usable_month,
        list_metric_months,
    )
except ImportError:
    sys.path.insert(0, str(project_root / 'server' / 'app' / 'utils'))
    from utils import get_db_connection
    from fact_selector import (
        best_metric_candidate,
        find_latest_usable_month,
        list_metric_months,
    )


@dataclass(frozen=True)
class BoardPackConfig:
    flat_threshold_pct: float
    revenue_min_abs_kpi_value: float
    revenue_ltm_months: int
    restatement_pct_threshold: float
    restatement_abs_threshold_gbp: float
    restatement_closed_period_months_ago: int


def _load_config() -> BoardPackConfig:
    cfg_path = project_root / 'config' / 'board_pack.yaml'
    data: Dict[str, Any] = {}
    if cfg_path.exists():
        with open(cfg_path, 'r') as f:
            data = yaml.safe_load(f) or {}

    flat = float(data.get('flat_threshold_pct', 1.0))
    revenue = data.get('metrics', {}).get('Revenue', {})

    min_abs = float(revenue.get('min_abs_kpi_value', 1000))
    ltm_months = int(revenue.get('ltm_months', 12))

    restatement = (data.get('reconciliation') or {}).get('restatement', {})
    rest_pct = float(restatement.get('pct_threshold', 2.0))
    rest_abs = float(restatement.get('abs_threshold_gbp', 50000))
    rest_closed = int(restatement.get('closed_period_months_ago', 2))

    return BoardPackConfig(
        flat_threshold_pct=flat,
        revenue_min_abs_kpi_value=min_abs,
        revenue_ltm_months=ltm_months,
        restatement_pct_threshold=rest_pct,
        restatement_abs_threshold_gbp=rest_abs,
        restatement_closed_period_months_ago=rest_closed,
    )


def _parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        negative = False
        if text.startswith('(') and text.endswith(')'):
            negative = True
            text = text[1:-1]
        text = text.replace(',', '').replace('£', '').replace('$', '').replace('%', '').strip()
        if text in {'-', '—'}:
            return None
        parsed = float(text)
        return -parsed if negative else parsed
    except Exception:
        return None


def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    return (float(curr) / float(prev) - 1.0) * 100.0


def _label_direction(pct: Optional[float], flat_threshold_pct: float) -> str:
    if pct is None:
        return 'n/a'
    if abs(pct) <= flat_threshold_pct:
        return 'flat'
    return 'up' if pct > 0 else 'down'


def _range_min_max(values: List[Optional[float]]) -> Optional[Tuple[float, float]]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return (min(vals), max(vals))


def _inside_range(pct: Optional[float], rng: Optional[Tuple[float, float]]) -> str:
    if pct is None or rng is None:
        return 'n/a'
    return 'inside' if rng[0] <= pct <= rng[1] else 'outside'


def _fmt_gbp(value: Optional[float]) -> str:
    if value is None:
        return 'n/a'
    try:
        return f"£{float(value):,.0f}"
    except Exception:
        return 'n/a'


def _fmt_range(rng: Optional[Tuple[float, float]]) -> str:
    if rng is None:
        return 'n/a'
    return f"{rng[0]:.1f}-{rng[1]:.1f}%"


def _best_metric_value(cur, company_id: int, line_item: str, period_label: str, value_type: str, min_abs: float) -> Optional[float]:
    """Compatibility wrapper; prefer using fact_selector directly."""

    cand = best_metric_candidate(
        cur,
        company_id,
        line_item,
        period_label,
        value_type,
        min_abs_value=min_abs if line_item == 'Revenue' and value_type in {'Actual', 'Budget', 'Prior Year'} else None,
    )
    return cand.value if cand else None


def _find_cross_document_restatements(cur, company_id: int, line_item: str, period_label: str, value_type: str, cfg: BoardPackConfig) -> Optional[Dict[str, Any]]:
    """Return evidence for cross-document differences if materially inconsistent.

    Also flags whether the period is considered "closed" (older than N months).
    """

    cur.execute(
        """
        SELECT
            fm.value,
            fm.currency,
            fm.document_id,
            fm.source_page,
            fm.extraction_method,
            fm.confidence
          FROM financial_metrics fm
          JOIN line_item_definitions lid ON fm.line_item_id = lid.id
          JOIN periods p ON fm.period_id = p.id
         WHERE fm.company_id = %s
           AND lid.name = %s
           AND p.period_label = %s
           AND fm.value_type = %s
           AND fm.document_id IS NOT NULL
         ORDER BY fm.document_id, COALESCE(fm.confidence, 0) DESC, fm.id DESC
        """,
        (company_id, line_item, period_label, value_type),
    )

    # Keep best candidate per document
    best_per_doc: Dict[int, Any] = {}
    for (val, currency, document_id, source_page, extraction_method, confidence) in cur.fetchall():
        if document_id is None:
            continue
        cand = best_per_doc.get(document_id)
        if cand is not None:
            continue
        parsed = None
        try:
            parsed = float(val) if isinstance(val, (int, float)) else None
        except Exception:
            parsed = None
        if parsed is None:
            from app.services.fact_selector import parse_number
            parsed = parse_number(val)
        if parsed is None:
            continue
        if line_item == 'Revenue' and value_type in {'Actual', 'Budget', 'Prior Year'} and abs(parsed) < cfg.revenue_min_abs_kpi_value:
            continue
        best_per_doc[document_id] = {
            'value': float(parsed),
            'currency': currency,
            'document_id': document_id,
            'source_page': source_page,
            'extraction_method': extraction_method,
            'confidence': confidence,
        }

    if len(best_per_doc) < 2:
        return None

    values = [d['value'] for d in best_per_doc.values()]
    min_v = min(values)
    max_v = max(values)
    abs_delta = abs(max_v - min_v)

    pct_delta = None
    if min_v != 0:
        pct_delta = abs_delta / abs(min_v) * 100.0

    if abs_delta < cfg.restatement_abs_threshold_gbp and (pct_delta is None or pct_delta < cfg.restatement_pct_threshold):
        return None

    # Determine whether period is "closed" based on start_date
    is_closed_period = False
    try:
        cur.execute(
            "SELECT start_date FROM periods WHERE period_label=%s AND period_type='Monthly'",
            (period_label,),
        )
        r = cur.fetchone()
        if r and r[0]:
            # If period is older than N months from today, consider closed.
            cur.execute(
                "SELECT (CURRENT_DATE - (%s::date))::int",
                (str(r[0])[:10],),
            )
            days_ago = int(cur.fetchone()[0])
            is_closed_period = days_ago >= int(cfg.restatement_closed_period_months_ago) * 30
    except Exception:
        is_closed_period = False

    return {
        'metric_name': line_item,
        'scenario': 'Group',
        'period_label': period_label,
        'value_type': value_type,
        'min_value': min_v,
        'max_value': max_v,
        'abs_delta': abs_delta,
        'pct_delta': pct_delta,
        'documents': sorted(best_per_doc.values(), key=lambda d: d['document_id']),
        'thresholds': {
            'pct_threshold': cfg.restatement_pct_threshold,
            'abs_threshold_gbp': cfg.restatement_abs_threshold_gbp,
            'closed_period_months_ago': cfg.restatement_closed_period_months_ago,
        },
        'closed_period': is_closed_period,
    }


def generate_revenue_findings(company_id: int) -> int:
    cfg = _load_config()

    with get_db_connection() as conn:
        cur = conn.cursor()

        revenue_periods = list_metric_months(cur, company_id, 'Revenue', 'Actual')
        if not revenue_periods:
            return 0

        current_period, prev_period = find_latest_usable_month(
            cur,
            company_id,
            'Revenue',
            min_abs_value=cfg.revenue_min_abs_kpi_value,
        )

        if not current_period:
            return 0

        def yoy_label(period_label: str) -> Optional[str]:
            if not period_label or len(period_label) < 7 or period_label[4] != '-':
                return None
            try:
                year = int(period_label[0:4])
                month = period_label[5:7]
                return f"{year - 1:04d}-{month}"
            except Exception:
                return None

        yoy_period = yoy_label(current_period)

        curr_actual_c = best_metric_candidate(
            cur,
            company_id,
            'Revenue',
            current_period,
            'Actual',
            min_abs_value=cfg.revenue_min_abs_kpi_value,
        )
        prev_actual_c = (
            best_metric_candidate(cur, company_id, 'Revenue', prev_period, 'Actual', min_abs_value=cfg.revenue_min_abs_kpi_value)
            if prev_period
            else None
        )
        curr_budget_c = best_metric_candidate(
            cur,
            company_id,
            'Revenue',
            current_period,
            'Budget',
            min_abs_value=cfg.revenue_min_abs_kpi_value,
        )
        curr_yoy_actual_c = (
            best_metric_candidate(cur, company_id, 'Revenue', yoy_period, 'Actual', min_abs_value=cfg.revenue_min_abs_kpi_value)
            if yoy_period
            else None
        )

        curr_actual = curr_actual_c.value if curr_actual_c else None
        prev_actual = prev_actual_c.value if prev_actual_c else None
        curr_budget = curr_budget_c.value if curr_budget_c else None
        curr_yoy_actual = curr_yoy_actual_c.value if curr_yoy_actual_c else None

        mom_pct = _pct_change(curr_actual, prev_actual)
        mom_dir = _label_direction(mom_pct, cfg.flat_threshold_pct)
        mom_abs = None if curr_actual is None or prev_actual is None else float(curr_actual) - float(prev_actual)

        yoy_pct = _pct_change(curr_actual, curr_yoy_actual)
        yoy_dir = _label_direction(yoy_pct, cfg.flat_threshold_pct)
        yoy_abs = None if curr_actual is None or curr_yoy_actual is None else float(curr_actual) - float(curr_yoy_actual)

        bud_pct = _pct_change(curr_actual, curr_budget)
        bud_dir = _label_direction(bud_pct, cfg.flat_threshold_pct)
        bud_abs = None if curr_actual is None or curr_budget is None else float(curr_actual) - float(curr_budget)

        def _fmt_pct(pct: Optional[float]) -> str:
            if pct is None:
                return 'n/a'
            return f"{pct:.1f}%"

        # LTM ranges for MoM/YoY/Budget variance
        end_idx = revenue_periods.index(current_period)
        start_idx = max(0, end_idx - cfg.revenue_ltm_months)
        window = revenue_periods[start_idx : end_idx + 1]

        ltm_mom = []
        for i in range(1, len(window)):
            a0 = _best_metric_value(cur, company_id, 'Revenue', window[i - 1], 'Actual', cfg.revenue_min_abs_kpi_value)
            a1 = _best_metric_value(cur, company_id, 'Revenue', window[i], 'Actual', cfg.revenue_min_abs_kpi_value)
            ltm_mom.append(_pct_change(a1, a0))

        ltm_yoy = []
        ltm_bud = []
        for pl in window:
            a = _best_metric_value(cur, company_id, 'Revenue', pl, 'Actual', cfg.revenue_min_abs_kpi_value)
            ay = _best_metric_value(cur, company_id, 'Revenue', yoy_label(pl), 'Actual', cfg.revenue_min_abs_kpi_value) if yoy_label(pl) else None
            ltm_yoy.append(_pct_change(a, ay))

            b = _best_metric_value(cur, company_id, 'Revenue', pl, 'Budget', cfg.revenue_min_abs_kpi_value)
            ltm_bud.append(_pct_change(a, b))

        mom_range = _range_min_max(ltm_mom)
        yoy_range = _range_min_max(ltm_yoy)
        bud_range = _range_min_max(ltm_bud)

        suggested_questions = [
            f"What were the primary drivers of Revenue in {current_period} (volume, price, mix)?",
            f"Is the MoM move ({_label_direction(mom_pct, cfg.flat_threshold_pct)} {_fmt_pct(mom_pct)}) timing/seasonality or structural?",
            f"If outside the typical LTM range, what changed vs the last 12 months?",
            f"What actions are in flight to address the variance vs budget ({_label_direction(bud_pct, cfg.flat_threshold_pct)} {_fmt_pct(bud_pct)})?",
            f"How confident are we that next month returns to the normal range? What leading indicators support that?",
        ]

        evidence = {
            'metric_name': 'Revenue',
            'period_label': current_period,
            'comparators': {
                'previous_period': prev_period,
                'yoy_period': yoy_period,
            },
            'values': {
                'actual': curr_actual,
                'previous_actual': prev_actual,
                'yoy_actual': curr_yoy_actual,
                'budget': curr_budget,
            },
            'sources': {
                'actual': None if curr_actual_c is None else {
                    'document_id': curr_actual_c.document_id,
                    'source_page': curr_actual_c.source_page,
                    'extraction_method': curr_actual_c.extraction_method,
                    'confidence': curr_actual_c.confidence,
                },
                'budget': None if curr_budget_c is None else {
                    'document_id': curr_budget_c.document_id,
                    'source_page': curr_budget_c.source_page,
                    'extraction_method': curr_budget_c.extraction_method,
                    'confidence': curr_budget_c.confidence,
                },
            },
            'deltas': {
                'mom_pct': mom_pct,
                'mom_abs': mom_abs,
                'yoy_pct': yoy_pct,
                'yoy_abs': yoy_abs,
                'budget_pct': bud_pct,
                'budget_abs': bud_abs,
            },
            'ranges': {
                'ltm_mom_pct': mom_range,
                'ltm_yoy_pct': yoy_range,
                'ltm_budget_pct': bud_range,
            },
            'range_flags': {
                'mom_inside': _inside_range(mom_pct, mom_range),
                'yoy_inside': _inside_range(yoy_pct, yoy_range),
                'budget_inside': _inside_range(bud_pct, bud_range),
            },
            'suggested_questions': suggested_questions,
            'config': {
                'flat_threshold_pct': cfg.flat_threshold_pct,
                'revenue_min_abs_kpi_value': cfg.revenue_min_abs_kpi_value,
                'revenue_ltm_months': cfg.revenue_ltm_months,
            },
        }

        # Severity: simple ranking based on outside typical range
        sev = 'info'
        if _inside_range(bud_pct, bud_range) == 'outside' or _inside_range(mom_pct, mom_range) == 'outside':
            sev = 'warning'

        def _fmt_pct(pct: Optional[float]) -> str:
            if pct is None:
                return 'n/a'
            return f"{pct:.1f}%"

        message = (
            f"Group revenue in {current_period} was {_fmt_gbp(curr_actual)}, {mom_dir} {_fmt_pct(mom_pct)} ({_fmt_gbp(mom_abs)}) vs {prev_period}; "
            f"{_inside_range(mom_pct, mom_range)} LTM MoM range {_fmt_range(mom_range)}. "
            f"YoY: {yoy_dir} {_fmt_pct(yoy_pct)} ({_fmt_gbp(yoy_abs)}) vs {yoy_period}; {_inside_range(yoy_pct, yoy_range)} LTM YoY range {_fmt_range(yoy_range)}. "
            f"Vs budget: {bud_dir} {_fmt_pct(bud_pct)} ({_fmt_gbp(bud_abs)}) vs {_fmt_gbp(curr_budget)}; {_inside_range(bud_pct, bud_range)} LTM budget range {_fmt_range(bud_range)}."
        )

        # Link to period_id
        cur.execute(
            "SELECT id FROM periods WHERE period_label = %s AND period_type = 'Monthly'",
            (current_period,),
        )
        r = cur.fetchone()
        period_id = r[0] if r else None

        # De-dupe: remove existing findings of this type for same period
        cur.execute(
            """
            DELETE FROM reconciliation_findings
             WHERE company_id = %s
               AND finding_type = 'boardpack_revenue_summary'
               AND COALESCE(period_id, -1) = COALESCE(%s, -1)
            """,
            (company_id, period_id),
        )

        cur.execute(
            """
            INSERT INTO reconciliation_findings (company_id, finding_type, severity, metric_name, scenario, period_id, message, evidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                company_id,
                'boardpack_revenue_summary',
                sev,
                'Revenue',
                'Group',
                period_id,
                message,
                json.dumps(evidence),
            ),
        )

        # Cross-document restatement checks (Revenue Actual/Budget)
        created = 1
        for vt in ('Actual', 'Budget'):
            rest_evidence = _find_cross_document_restatements(cur, company_id, 'Revenue', current_period, vt, cfg)
            if rest_evidence is None:
                continue

            # Link to period_id already computed
            cur.execute(
                """
                DELETE FROM reconciliation_findings
                 WHERE company_id = %s
                   AND finding_type = 'cross_document_restatement'
                   AND metric_name = 'Revenue'
                   AND scenario = 'Group'
                   AND COALESCE(period_id, -1) = COALESCE(%s, -1)
                """,
                (company_id, period_id),
            )

            sev2 = 'warning'
            if rest_evidence.get('closed_period'):
                sev2 = 'high'
            if rest_evidence.get('pct_delta') is not None and rest_evidence['pct_delta'] >= max(cfg.restatement_pct_threshold * 2, 5.0):
                sev2 = 'high'

            msg2 = (
                f"Restatement risk: Revenue {vt} for {current_period} varies across packs "
                f"({_fmt_gbp(rest_evidence['min_value'])} to {_fmt_gbp(rest_evidence['max_value'])})."
            )

            rest_evidence['suggested_questions'] = [
                f"Which number is the approved Revenue {vt} for {current_period}, and which pack/version is the source of truth?",
                f"Why does Revenue {vt} differ across packs (methodology change, reclassification, late postings, or target changes)?",
                f"Was this change approved? If so, when and by whom?",
                f"Does the restatement affect KPI narratives, bonuses, covenant optics, or board reporting commitments?",
                f"What controls prevent historical budget/targets being altered after period close?",
            ]

            cur.execute(
                """
                INSERT INTO reconciliation_findings (company_id, finding_type, severity, metric_name, scenario, period_id, message, evidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    company_id,
                    'cross_document_restatement',
                    sev2,
                    'Revenue',
                    'Group',
                    period_id,
                    msg2,
                    json.dumps(rest_evidence),
                ),
            )
            created += 1

        conn.commit()

        return created


def _insert_finding(
    cur,
    *,
    company_id: int,
    finding_type: str,
    severity: str,
    metric_name: str,
    scenario: str,
    period_id: Optional[int],
    message: str,
    evidence: Dict[str, Any],
) -> None:
    # De-dupe per type/metric/scenario/period
    cur.execute(
        """
        DELETE FROM reconciliation_findings
         WHERE company_id = %s
           AND finding_type = %s
           AND metric_name = %s
           AND scenario = %s
           AND COALESCE(period_id, -1) = COALESCE(%s, -1)
        """,
        (company_id, finding_type, metric_name, scenario, period_id),
    )

    cur.execute(
        """
        INSERT INTO reconciliation_findings (company_id, finding_type, severity, metric_name, scenario, period_id, message, evidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            company_id,
            finding_type,
            severity,
            metric_name,
            scenario,
            period_id,
            message,
            json.dumps(evidence),
        ),
    )


def _generate_simple_kpi_summary(cur, cfg: BoardPackConfig, company_id: int, metric: str) -> int:
    periods = list_metric_months(cur, company_id, metric, 'Actual')
    if not periods:
        return 0

    current_period, prev_period = find_latest_usable_month(
        cur,
        company_id,
        metric,
        min_abs_value=cfg.revenue_min_abs_kpi_value,
    )
    if not current_period:
        return 0

    def yoy_label(period_label: str) -> Optional[str]:
        if not period_label or len(period_label) < 7 or period_label[4] != '-':
            return None
        try:
            year = int(period_label[0:4])
            month = period_label[5:7]
            return f"{year - 1:04d}-{month}"
        except Exception:
            return None

    yoy_period = yoy_label(current_period)

    curr_actual_c = best_metric_candidate(cur, company_id, metric, current_period, 'Actual', min_abs_value=cfg.revenue_min_abs_kpi_value)
    curr_budget_c = best_metric_candidate(cur, company_id, metric, current_period, 'Budget', min_abs_value=cfg.revenue_min_abs_kpi_value)
    curr_prior_c = best_metric_candidate(cur, company_id, metric, current_period, 'Prior Year', min_abs_value=cfg.revenue_min_abs_kpi_value)

    curr_actual = curr_actual_c.value if curr_actual_c else None
    curr_budget = curr_budget_c.value if curr_budget_c else None
    curr_prior = curr_prior_c.value if curr_prior_c else None

    bud_pct = _pct_change(curr_actual, curr_budget)
    yoy_pct = _pct_change(curr_actual, curr_prior)

    suggested = [
        f"What are the main drivers of {metric} vs budget in {current_period}?",
        f"Is the {metric} YoY move ({_label_direction(yoy_pct, cfg.flat_threshold_pct)}) structural or timing?",
        f"What operating levers are we pulling to improve {metric} over the next 60–90 days?",
    ]

    evidence = {
        'metric_name': metric,
        'period_label': current_period,
        'comparators': {
            'previous_period': prev_period,
            'yoy_period': yoy_period,
        },
        'values': {
            'actual': curr_actual,
            'budget': curr_budget,
            'prior_year': curr_prior,
        },
        'sources': {
            'actual': None if curr_actual_c is None else {
                'document_id': curr_actual_c.document_id,
                'source_page': curr_actual_c.source_page,
                'extraction_method': curr_actual_c.extraction_method,
                'confidence': curr_actual_c.confidence,
            },
            'budget': None if curr_budget_c is None else {
                'document_id': curr_budget_c.document_id,
                'source_page': curr_budget_c.source_page,
                'extraction_method': curr_budget_c.extraction_method,
                'confidence': curr_budget_c.confidence,
            },
        },
        'deltas': {
            'budget_pct': bud_pct,
            'yoy_pct': yoy_pct,
        },
        'suggested_questions': suggested,
    }

    # Link to period_id
    cur.execute(
        "SELECT id FROM periods WHERE period_label = %s AND period_type = 'Monthly'",
        (current_period,),
    )
    r = cur.fetchone()
    period_id = r[0] if r else None

    sev = 'info'
    if bud_pct is not None and abs(bud_pct) >= 5.0:
        sev = 'warning'

    def _fmt_pct(pct: Optional[float]) -> str:
        if pct is None:
            return 'n/a'
        return f"{pct:.1f}%"

    msg = (
        f"{metric} in {current_period} was {_fmt_gbp(curr_actual)}; vs budget {_fmt_pct(bud_pct)} and YoY {_fmt_pct(yoy_pct)}."
    )

    _insert_finding(
        cur,
        company_id=company_id,
        finding_type=f"boardpack_{metric.lower().replace(' ', '_')}_summary",
        severity=sev,
        metric_name=metric,
        scenario='Group',
        period_id=period_id,
        message=msg,
        evidence=evidence,
    )

    # Restatement check for this KPI for the same period
    for vt in ('Actual', 'Budget'):
        rest_evidence = _find_cross_document_restatements(cur, company_id, metric, current_period, vt, cfg)
        if rest_evidence is None:
            continue
        rest_evidence['suggested_questions'] = [
            f"Which number is the approved {metric} {vt} for {current_period}, and which pack/version is the source of truth?",
            f"Why does {metric} {vt} differ across packs for {current_period}?",
        ]

        msg2 = f"Restatement risk: {metric} {vt} for {current_period} varies across packs."
        _insert_finding(
            cur,
            company_id=company_id,
            finding_type='cross_document_restatement',
            severity='warning',
            metric_name=metric,
            scenario='Group',
            period_id=period_id,
            message=msg2,
            evidence=rest_evidence,
        )

    return 1


def generate_kpi_findings(company_id: int) -> int:
    cfg = _load_config()
    created = 0

    with get_db_connection() as conn:
        cur = conn.cursor()
        created += generate_revenue_findings(company_id)
        created += _generate_simple_kpi_summary(cur, cfg, company_id, 'Gross Profit')
        created += _generate_simple_kpi_summary(cur, cfg, company_id, 'EBITDA')
        conn.commit()

    return created


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: python findings_engine.py <company_id>')
        raise SystemExit(1)

    company_id = int(sys.argv[1])
    created = generate_kpi_findings(company_id)
    print(f"created_findings={created}")


if __name__ == '__main__':
    main()
