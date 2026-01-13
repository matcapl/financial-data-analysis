import json
from typing import Any, Dict, List, Optional, Tuple

from app.utils.utils import get_db_connection


def _insert_finding(
    *,
    company_id: int,
    document_id: Optional[int],
    finding_type: str,
    severity: str,
    metric_name: Optional[str],
    scenario: Optional[str],
    period_id: Optional[int],
    message: str,
    evidence: Dict[str, Any],
) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reconciliation_findings (
                    company_id, document_id, finding_type, severity,
                    metric_name, scenario, period_id, message, evidence
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    company_id,
                    document_id,
                    finding_type,
                    severity,
                    metric_name,
                    scenario,
                    period_id,
                    message,
                    json.dumps(evidence),
                ),
            )
            finding_id = cur.fetchone()[0]
            conn.commit()
            return finding_id


def _clear_findings(company_id: int, document_id: Optional[int]) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if document_id is None:
                cur.execute("DELETE FROM reconciliation_findings WHERE company_id=%s", (company_id,))
            else:
                cur.execute(
                    "DELETE FROM reconciliation_findings WHERE company_id=%s AND document_id=%s",
                    (company_id, document_id),
                )
            conn.commit()


def run_reconciliation(company_id: int, document_id: Optional[int] = None, clear_existing: bool = True) -> Dict[str, Any]:
    """Run deterministic reconciliation checks and persist findings.

    Currently implemented:
    - Intra-document inconsistencies: same metric/period/scenario appears multiple times in same document with different values.
    - Cross-document restatements: same metric/period/scenario differs across documents.
    """

    if clear_existing:
        _clear_findings(company_id, document_id)

    created: List[int] = []

    created.extend(_check_intra_document_inconsistencies(company_id, document_id))
    created.extend(_check_time_rollups(company_id, document_id))

    # Only meaningful when scanning across documents.
    if document_id is None:
        created.extend(_check_cross_document_restatements(company_id))

    return {
        "company_id": company_id,
        "document_id": document_id,
        "findings_created": len(created),
        "finding_ids": created[:50],
    }


def _check_intra_document_inconsistencies(company_id: int, document_id: Optional[int]) -> List[int]:
    """Detect when a document contains multiple conflicting values for the same coordinate."""

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if document_id is None:
                cur.execute(
                    """
                    SELECT
                        fm.document_id,
                        lid.name AS metric_name,
                        fm.period_id,
                        p.period_label,
                        fm.value_type,
                        fm.currency,
                        MIN(fm.value) AS min_value,
                        MAX(fm.value) AS max_value,
                        COUNT(*) AS occurrences
                    FROM financial_metrics fm
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    JOIN periods p ON p.id=fm.period_id
                    WHERE fm.company_id=%s AND fm.document_id IS NOT NULL
                    GROUP BY fm.document_id, lid.name, fm.period_id, p.period_label, fm.value_type, fm.currency,
                             COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0)))
                    HAVING COUNT(*) > 1 AND MIN(fm.value) IS DISTINCT FROM MAX(fm.value)
                    ORDER BY occurrences DESC
                    LIMIT 200
                    """,
                    (company_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        fm.document_id,
                        lid.name AS metric_name,
                        fm.period_id,
                        p.period_label,
                        fm.value_type,
                        fm.currency,
                        MIN(fm.value) AS min_value,
                        MAX(fm.value) AS max_value,
                        COUNT(*) AS occurrences
                    FROM financial_metrics fm
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    JOIN periods p ON p.id=fm.period_id
                    WHERE fm.company_id=%s AND fm.document_id=%s
                    GROUP BY fm.document_id, lid.name, fm.period_id, p.period_label, fm.value_type, fm.currency,
                             COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0)))
                    HAVING COUNT(*) > 1 AND MIN(fm.value) IS DISTINCT FROM MAX(fm.value)
                    ORDER BY occurrences DESC
                    LIMIT 200
                    """,
                    (company_id, document_id),
                )

            rows = cur.fetchall()

    finding_ids: List[int] = []
    for (doc_id, metric_name, period_id, period_label, scenario, currency, context_key, min_value, max_value, occurrences) in rows:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.original_filename,
                        d.uploaded_at,
                        fm.value,
                        fm.source_page,
                        fm.source_table,
                        fm.source_row,
                        fm.source_col,
                        fm.context_key
                    FROM financial_metrics fm
                    JOIN documents d ON d.id=fm.document_id
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    WHERE fm.company_id=%s AND fm.document_id=%s
                      AND lid.name=%s AND fm.period_id=%s AND fm.value_type=%s AND fm.currency=%s
                      AND COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0)))=%s
                    ORDER BY fm.value DESC NULLS LAST
                    LIMIT 50
                    """,
                    (company_id, doc_id, metric_name, period_id, scenario, currency, context_key),
                )
                occ = cur.fetchall()

        evidence = {
            "period_label": period_label,
            "currency": currency,
            "context_key": context_key,
            "min_value": float(min_value) if min_value is not None else None,
            "max_value": float(max_value) if max_value is not None else None,
            "occurrences": [
                {
                    "document_id": doc_id,
                    "filename": r[0],
                    "uploaded_at": r[1].isoformat() if r[1] else None,
                    "value": float(r[2]) if r[2] is not None else None,
                    "source_page": r[3],
                    "source_table": r[4],
                    "source_row": r[5],
                    "source_col": r[6],
                    "context_key": r[7],
                }
                for r in occ
            ],
        }

        message = (
            f"Inconsistent values within document for {metric_name} ({scenario}) {period_label} {currency}: "
            f"min={min_value} max={max_value} across {occurrences} occurrences."
        )

        fid = _insert_finding(
            company_id=company_id,
            document_id=doc_id,
            finding_type="intra_document_inconsistency",
            severity="warning",
            metric_name=metric_name,
            scenario=scenario,
            period_id=period_id,
            message=message,
            evidence=evidence,
        )
        finding_ids.append(fid)

    return finding_ids




def _parse_month(period_label: str) -> Optional[Tuple[int, int]]:
    try:
        year_s, month_s = period_label.split('-')
        year = int(year_s)
        month = int(month_s)
        if 1 <= month <= 12:
            return year, month
    except Exception:
        return None
    return None


def _quarter_label(year: int, month: int) -> str:
    q = (month - 1) // 3 + 1
    return f"{year}-Q{q}"


def _check_time_rollups(company_id: int, document_id: Optional[int]) -> List[int]:
    """Exact rollup checks: sum(months) == quarter, sum(quarters) == year.

    Calendar year assumption (Jan-Dec).
    Only emits findings where both rolled-up components and an explicit total exist.
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if document_id is None:
                cur.execute(
                    """
                    SELECT
                        fm.document_id,
                        lid.name AS metric_name,
                        fm.value_type,
                        fm.currency,
                        p.period_type,
                        p.period_label,
                        fm.value,
                        fm.source_page,
                        fm.source_table,
                        fm.source_row,
                        fm.source_col,
                        COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0))) AS context_key
                    FROM financial_metrics fm
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    JOIN periods p ON p.id=fm.period_id
                    WHERE fm.company_id=%s AND fm.document_id IS NOT NULL
                    """,
                    (company_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        fm.document_id,
                        lid.name AS metric_name,
                        fm.value_type,
                        fm.currency,
                        p.period_type,
                        p.period_label,
                        fm.value,
                        fm.source_page,
                        fm.source_table,
                        fm.source_row,
                        fm.source_col,
                        COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0))) AS context_key
                    FROM financial_metrics fm
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    JOIN periods p ON p.id=fm.period_id
                    WHERE fm.company_id=%s AND fm.document_id=%s
                    """,
                    (company_id, document_id),
                )
            rows = cur.fetchall()

    # Index facts
    monthly = {}
    quarterly = {}
    yearly = {}

    # Store evidence for totals and components
    fact_evidence = {}

    for (doc_id, metric_name, scenario, currency, period_type, period_label, value, sp, st, sr, sc, ctx) in rows:
        key = (doc_id, metric_name, scenario, currency, ctx)
        fact_evidence.setdefault((doc_id, metric_name, scenario, currency, ctx, period_type, period_label), {
            'value': float(value) if value is not None else None,
            'source_page': sp,
            'source_table': st,
            'source_row': sr,
            'source_col': sc,
            'context_key': ctx,
        })

        if period_type == 'Monthly':
            parsed = _parse_month(period_label)
            if parsed and value is not None:
                monthly.setdefault(key, {})[period_label] = float(value)
        elif period_type == 'Quarterly':
            if value is not None:
                quarterly.setdefault(key, {})[period_label] = float(value)
        elif period_type == 'Yearly':
            if value is not None:
                yearly.setdefault(key, {})[period_label] = float(value)

    finding_ids: List[int] = []

    # Check monthly -> quarterly
    for key, months in monthly.items():
        doc_id, metric_name, scenario, currency, ctx = key
        if key not in quarterly:
            continue

        # Group month values into quarters
        by_quarter: Dict[str, List[Tuple[str, float]]] = {}
        for pl, val in months.items():
            parsed = _parse_month(pl)
            if not parsed:
                continue
            y, m = parsed
            ql = _quarter_label(y, m)
            by_quarter.setdefault(ql, []).append((pl, val))

        for ql, parts in by_quarter.items():
            if ql not in quarterly[key]:
                continue  # no explicit quarterly total to compare
            rolled = sum(v for _, v in parts)
            total = quarterly[key][ql]
            if rolled != total:
                evidence = {
                    'rollup': 'monthly_to_quarter',
                    'metric_name': metric_name,
                    'scenario': scenario,
                    'currency': currency,
                    'context_key': ctx,
                    'quarter': ql,
                    'rolled_sum': rolled,
                    'reported_total': total,
                    'components': [
                        {
                            'period_label': pl,
                            'value': v,
                            **fact_evidence.get((doc_id, metric_name, scenario, currency, ctx, 'Monthly', pl), {}),
                        }
                        for pl, v in sorted(parts)
                    ],
                    'total_fact': fact_evidence.get((doc_id, metric_name, scenario, currency, ctx, 'Quarterly', ql), {}),
                }
                msg = (
                    f"Time rollup mismatch in document for {metric_name} ({scenario}) {ql} {currency}: "
                    f"sum(months)={rolled} != quarter={total}."
                )
                fid = _insert_finding(
                    company_id=company_id,
                    document_id=doc_id,
                    finding_type='time_rollup_mismatch',
                    severity='warning',
                    metric_name=metric_name,
                    scenario=scenario,
                    period_id=None,
                    message=msg,
                    evidence=evidence,
                )
                finding_ids.append(fid)

    # Check quarterly -> yearly
    for key, quarters in quarterly.items():
        doc_id, metric_name, scenario, currency, ctx = key
        if key not in yearly:
            continue

        # Group quarters by year
        by_year: Dict[str, List[Tuple[str, float]]] = {}
        for ql, val in quarters.items():
            try:
                year_s, q_s = ql.split('-Q')
                year = int(year_s)
                by_year.setdefault(str(year), []).append((ql, val))
            except Exception:
                continue

        for yl, parts in by_year.items():
            if yl not in yearly[key]:
                continue
            rolled = sum(v for _, v in parts)
            total = yearly[key][yl]
            if rolled != total:
                evidence = {
                    'rollup': 'quarter_to_year',
                    'metric_name': metric_name,
                    'scenario': scenario,
                    'currency': currency,
                    'context_key': ctx,
                    'year': yl,
                    'rolled_sum': rolled,
                    'reported_total': total,
                    'components': [
                        {
                            'period_label': pl,
                            'value': v,
                            **fact_evidence.get((doc_id, metric_name, scenario, currency, ctx, 'Quarterly', pl), {}),
                        }
                        for pl, v in sorted(parts)
                    ],
                    'total_fact': fact_evidence.get((doc_id, metric_name, scenario, currency, ctx, 'Yearly', yl), {}),
                }
                msg = (
                    f"Time rollup mismatch in document for {metric_name} ({scenario}) {yl} {currency}: "
                    f"sum(quarters)={rolled} != year={total}."
                )
                fid = _insert_finding(
                    company_id=company_id,
                    document_id=doc_id,
                    finding_type='time_rollup_mismatch',
                    severity='warning',
                    metric_name=metric_name,
                    scenario=scenario,
                    period_id=None,
                    message=msg,
                    evidence=evidence,
                )
                finding_ids.append(fid)

    return finding_ids
def _check_cross_document_restatements(company_id: int) -> List[int]:
    """Detect when the same coordinate differs between documents (goalpost moves)."""

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    lid.name AS metric_name,
                    fm.period_id,
                    p.period_label,
                    fm.value_type,
                    fm.currency,
                    COALESCE(NULLIF(fm.context_key, ''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0))) AS context_key,
                    MIN(fm.value) AS min_value,
                    MAX(fm.value) AS max_value,
                    COUNT(DISTINCT fm.document_id) AS doc_count
                FROM financial_metrics fm
                JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                JOIN periods p ON p.id=fm.period_id
                WHERE fm.company_id=%s AND fm.document_id IS NOT NULL
                GROUP BY lid.name, fm.period_id, p.period_label, fm.value_type, fm.currency, COALESCE(NULLIF(fm.context_key, ''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0)))
                HAVING COUNT(DISTINCT fm.document_id) > 1 AND MIN(fm.value) IS DISTINCT FROM MAX(fm.value)
                ORDER BY doc_count DESC
                LIMIT 200
                """,
                (company_id,),
            )
            rows = cur.fetchall()

    finding_ids: List[int] = []
    for (metric_name, period_id, period_label, scenario, currency, context_key, min_value, max_value, doc_count) in rows:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        fm.document_id,
                        d.original_filename,
                        d.uploaded_at,
                        fm.value,
                        fm.source_page,
                        fm.source_table,
                        fm.source_row,
                        fm.source_col,
                        fm.context_key
                    FROM financial_metrics fm
                    JOIN documents d ON d.id=fm.document_id
                    JOIN line_item_definitions lid ON lid.id=fm.line_item_id
                    WHERE fm.company_id=%s
                      AND lid.name=%s AND fm.period_id=%s AND fm.value_type=%s AND fm.currency=%s
                      AND COALESCE(NULLIF(fm.context_key,''), CONCAT('p', fm.source_page, '_t', COALESCE(fm.source_table, 0)))=%s
                    ORDER BY d.uploaded_at ASC, fm.value DESC
                    LIMIT 100
                    """,
                    (company_id, metric_name, period_id, scenario, currency, context_key),
                )
                occ = cur.fetchall()

        evidence = {
            "period_label": period_label,
            "currency": currency,
            "context_key": context_key,
            "min_value": float(min_value) if min_value is not None else None,
            "max_value": float(max_value) if max_value is not None else None,
            "documents": [
                {
                    "document_id": r[0],
                    "filename": r[1],
                    "uploaded_at": r[2].isoformat() if r[2] else None,
                    "value": float(r[3]) if r[3] is not None else None,
                    "source_page": r[4],
                    "source_table": r[5],
                    "source_row": r[6],
                    "source_col": r[7],
                    "context_key": r[8],
                }
                for r in occ
            ],
        }

        message = (
            f"Restated values across documents for {metric_name} ({scenario}) {period_label} {currency}: "
            f"min={min_value} max={max_value} across {doc_count} documents."
        )

        fid = _insert_finding(
            company_id=company_id,
            document_id=None,
            finding_type="cross_document_restatement",
            severity="warning",
            metric_name=metric_name,
            scenario=scenario,
            period_id=period_id,
            message=message,
            evidence=evidence,
        )
        finding_ids.append(fid)

    return finding_ids
