"""fact_selector.py

Centralized selection logic for choosing the "best" canonical fact from
`financial_metrics` given messy/duplicative inputs.

This is the single source of truth for:
- confidence-aware selection
- basic sanity checks (e.g., KPI minimum magnitude)
- provenance return (document/page/method)

Downstream consumers (findings, report) should rely on this module so their
outputs stay coherent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple, List


@dataclass(frozen=True)
class MetricCandidate:
    value: float
    currency: Optional[str]
    document_id: Optional[int]
    source_page: Optional[int]
    extraction_method: Optional[str]
    confidence: Optional[float]


def parse_number(value: Any) -> Optional[float]:
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
        text = (
            text.replace(',', '')
            .replace('£', '')
            .replace('$', '')
            .replace('%', '')
            .strip()
        )
        if text in {'-', '—'}:
            return None
        parsed = float(text)
        return -parsed if negative else parsed
    except Exception:
        return None


def best_metric_candidate(
    cur,
    company_id: int,
    line_item: str,
    period_label: str,
    value_type: str,
    *,
    min_abs_value: Optional[float] = None,
) -> Optional[MetricCandidate]:
    """Return the best candidate for a given metric key.

    Ordering: highest confidence first, then newest row.
    """

    if not period_label:
        return None

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
         ORDER BY COALESCE(fm.confidence, 0) DESC, fm.id DESC
         LIMIT 50
        """,
        (company_id, line_item, period_label, value_type),
    )

    for (val, currency, document_id, source_page, extraction_method, confidence) in cur.fetchall():
        parsed = parse_number(val)
        if parsed is None:
            continue
        if min_abs_value is not None and abs(parsed) < min_abs_value:
            continue
        return MetricCandidate(
            value=float(parsed),
            currency=currency,
            document_id=document_id,
            source_page=source_page,
            extraction_method=extraction_method,
            confidence=confidence,
        )

    return None


def list_metric_months(
    cur,
    company_id: int,
    line_item: str,
    value_type: str = 'Actual',
) -> List[str]:
    cur.execute(
        """
        SELECT p.period_label
          FROM financial_metrics fm
          JOIN line_item_definitions lid ON fm.line_item_id = lid.id
          JOIN periods p ON fm.period_id = p.id
         WHERE fm.company_id = %s
           AND lid.name = %s
           AND fm.value_type = %s
           AND p.period_type = 'Monthly'
         GROUP BY p.period_label, p.start_date
         ORDER BY p.start_date
        """,
        (company_id, line_item, value_type),
    )

    return [pl for (pl,) in cur.fetchall() if pl]


def find_latest_usable_month(
    cur,
    company_id: int,
    line_item: str,
    *,
    min_abs_value: Optional[float] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Return (current_period, previous_period) with usable Actual values."""

    periods = list_metric_months(cur, company_id, line_item, 'Actual')
    if not periods:
        return (None, None)

    current = None
    previous = None

    for idx in range(len(periods) - 1, -1, -1):
        pl = periods[idx]
        if best_metric_candidate(
            cur,
            company_id,
            line_item,
            pl,
            'Actual',
            min_abs_value=min_abs_value,
        ) is not None:
            current = pl
            for j in range(idx - 1, -1, -1):
                ppl = periods[j]
                if best_metric_candidate(
                    cur,
                    company_id,
                    line_item,
                    ppl,
                    'Actual',
                    min_abs_value=min_abs_value,
                ) is not None:
                    previous = ppl
                    break
            break

    return (current, previous)
