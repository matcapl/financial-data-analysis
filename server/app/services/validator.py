"""validator.py

Deterministic validation over persisted facts.

This module produces a structured validation report used to:
- flag extraction/mapping/normalisation issues
- drive a safe feedback loop (quarantine + selection), not silent rewriting

It is designed to be robust across companies by using:
- per-(company, metric, value_type) distribution checks (median + outlier factors)
- minimal hardcoded thresholds as fallback

The output is stored under `documents.metadata.validation_report`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def _month_key(period_label: str) -> Optional[Tuple[int, int]]:
    """Parse YYYY-MM into (year, month)."""
    if not period_label or len(period_label) != 7 or period_label[4] != '-':
        return None
    y = period_label[:4]
    m = period_label[5:7]
    if not (y.isdigit() and m.isdigit()):
        return None
    year = int(y)
    month = int(m)
    if month < 1 or month > 12:
        return None
    return year, month


def _reconcile_ytd(
    *,
    period_series: Dict[str, float],
    ytd_series: Dict[str, float],
    tolerance_abs: float,
    tolerance_pct: float,
) -> List[ValidationIssue]:
    """Compare derived YTD(sum of Period months) vs ingested YTD by month."""

    issues: List[ValidationIssue] = []

    months = sorted(set(period_series.keys()) | set(ytd_series.keys()), key=lambda x: _month_key(x) or (0, 0))

    cum_by_year: Dict[int, float] = {}

    for pl in months:
        mk = _month_key(pl)
        if mk is None:
            continue
        year, month = mk

        if year not in cum_by_year:
            cum_by_year[year] = 0.0

        if month == 1:
            cum_by_year[year] = 0.0

        if pl in period_series:
            cum_by_year[year] += float(period_series[pl])

        if pl not in ytd_series:
            continue

        ing = float(ytd_series[pl])
        derived = cum_by_year[year]
        diff = derived - ing
        diff_pct = (diff / ing * 100.0) if ing != 0 else None

        abs_bad = abs(diff) > tolerance_abs
        pct_bad = (diff_pct is not None) and (abs(diff_pct) > tolerance_pct)

        if abs_bad and pct_bad:
            issues.append(
                ValidationIssue(
                    severity='warning',
                    code='revenue_ytd_mismatch',
                    message='Derived YTD from monthly Period does not match ingested YTD',
                    context={
                        'month': pl,
                        'derived_ytd': derived,
                        'ingested_ytd': ing,
                        'diff': diff,
                        'diff_pct': diff_pct,
                        'tolerance_abs': tolerance_abs,
                        'tolerance_pct': tolerance_pct,
                    },
                )
            )

    return issues


def _quarter_label(period_label: str) -> Optional[str]:
    mk = _month_key(period_label)
    if mk is None:
        return None
    year, month = mk
    q = ((month - 1) // 3) + 1
    return f"{year}-Q{q}"


def _derive_quarterly_sum(period_series: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m, v in period_series.items():
        q = _quarter_label(m)
        if not q:
            continue
        out[q] = out.get(q, 0.0) + float(v)
    return out


def _derive_yearly_sum(period_series: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m, v in period_series.items():
        mk = _month_key(m)
        if mk is None:
            continue
        year, _ = mk
        y = f"{year}"
        out[y] = out.get(y, 0.0) + float(v)
    return out


def _compare_derived_vs_ingested(
    *,
    derived: Dict[str, float],
    ingested: Dict[str, float],
    tolerance_abs: float,
    tolerance_pct: float,
    code: str,
    label: str,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    for period, derived_val in derived.items():
        if period not in ingested:
            issues.append(
                ValidationIssue(
                    severity='info',
                    code=f"missing_{code}",
                    message=f"Missing ingested {label} value for corroboration",
                    context={'period': period, 'derived': derived_val},
                )
            )
            continue

        ing = float(ingested[period])
        diff = float(derived_val) - ing
        diff_pct = (diff / ing * 100.0) if ing != 0 else None

        abs_bad = abs(diff) > tolerance_abs
        pct_bad = (diff_pct is not None) and (abs(diff_pct) > tolerance_pct)

        if abs_bad and pct_bad:
            issues.append(
                ValidationIssue(
                    severity='warning',
                    code=code,
                    message=f"Derived {label} does not match ingested",
                    context={
                        'period': period,
                        'derived': float(derived_val),
                        'ingested': ing,
                        'diff': diff,
                        'diff_pct': diff_pct,
                        'tolerance_abs': tolerance_abs,
                        'tolerance_pct': tolerance_pct,
                    },
                )
            )

    return issues


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # info|warning|error
    code: str
    message: str
    context: Dict[str, Any]


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: List[ValidationIssue]
    metrics_checked: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_contracts() -> Dict[str, Any]:
    base = Path(__file__).resolve().parent.parent.parent.parent
    cfg = base / 'config' / 'contracts.yaml'
    try:
        with open(cfg, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def validate_company_monthly_series(
    *,
    conn,
    company_id: int,
    contract_name: str = 'revenue_analyst_v1',
) -> ValidationReport:
    contracts = _load_contracts().get('contracts', {})
    contract = contracts.get(contract_name, {}) if isinstance(contracts, dict) else {}

    sanity = (contract.get('sanity') or {}) if isinstance(contract, dict) else {}
    out_low = float(sanity.get('outlier_factor_low') or 0.1)
    out_high = float(sanity.get('outlier_factor_high') or 10.0)
    fallback = sanity.get('min_abs_value_fallback') or {}

    reconciliation = (contract.get('reconciliation') or {}) if isinstance(contract, dict) else {}

    def _rec_cfg(name: str, default_enabled: bool = False) -> Tuple[bool, float, float]:
        cfg = (reconciliation.get(name) or {}) if isinstance(reconciliation, dict) else {}
        enabled = bool(cfg.get('enabled', default_enabled))
        tol_abs = float(cfg.get('tolerance_abs') or 1000)
        tol_pct = float(cfg.get('tolerance_pct') or 2.0)
        return enabled, tol_abs, tol_pct

    revenue_ytd_enabled, revenue_ytd_tol_abs, revenue_ytd_tol_pct = _rec_cfg('revenue_ytd', False)
    revenue_q_enabled, revenue_q_tol_abs, revenue_q_tol_pct = _rec_cfg('revenue_quarterly', False)
    revenue_y_enabled, revenue_y_tol_abs, revenue_y_tol_pct = _rec_cfg('revenue_yearly', False)

    required_metrics = contract.get('required_metrics') or []

    issues: List[ValidationIssue] = []
    metrics_checked: List[str] = []

    with conn.cursor() as cur:
        for spec in required_metrics:
            metric = str(spec.get('name') or '').strip()
            value_type = str(spec.get('value_type') or 'Actual').strip()
            period_type = str(spec.get('period_type') or 'Monthly').strip()
            if not metric:
                continue

            metrics_checked.append(metric)

            # Compute median for this metric/value_type.
            cur.execute(
                """
                SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY fm.value)
                FROM financial_metrics fm
                JOIN line_item_definitions li ON li.id = fm.line_item_id
                JOIN periods p ON p.id = fm.period_id
                WHERE fm.company_id = %s
                  AND li.name = %s
                  AND fm.value_type = %s
                  AND COALESCE(fm.period_scope, 'Period') = 'Period'
                  AND p.period_type = %s
                  AND fm.value IS NOT NULL
                """,
                (company_id, metric, value_type, period_type),
            )
            med = cur.fetchone()[0]

            min_abs = None
            try:
                min_abs = float(fallback.get(metric)) if metric in fallback else None
            except Exception:
                min_abs = None

            # Pull month series.
            cur.execute(
                """
                SELECT p.period_label, fm.id, fm.value, fm.source_file, fm.extraction_method, fm.confidence
                FROM financial_metrics fm
                JOIN line_item_definitions li ON li.id = fm.line_item_id
                JOIN periods p ON p.id = fm.period_id
                WHERE fm.company_id = %s
                  AND li.name = %s
                  AND fm.value_type = %s
                  AND COALESCE(fm.period_scope, 'Period') = 'Period'
                  AND p.period_type = %s
                ORDER BY p.period_label, COALESCE(fm.confidence, 0) DESC, fm.id DESC
                """,
                (company_id, metric, value_type, period_type),
            )
            rows = cur.fetchall()

            if not rows:
                issues.append(
                    ValidationIssue(
                        severity='error',
                        code='missing_series',
                        message=f"No {period_type} {metric} {value_type} facts persisted",
                        context={'metric': metric, 'value_type': value_type},
                    )
                )
                continue

            # Group candidates per month and flag suspicious scale outliers.
            by_month: Dict[str, List[Tuple]] = {}
            for pl, fid, val, src, method, conf in rows:
                by_month.setdefault(str(pl), []).append((fid, float(val), src, method, conf))

            for month, candidates in by_month.items():
                # use the top-ranked candidate (current selector behavior)
                fid, val, src, method, conf = candidates[0]
                abs_val = abs(val)

                if med is not None and float(med) > 0:
                    medv = float(med)
                    if abs_val < medv * out_low or abs_val > medv * out_high:
                        issues.append(
                            ValidationIssue(
                                severity='warning',
                                code='scale_outlier',
                                message=f"{metric} {value_type} for {month} looks out-of-scale vs median",
                                context={
                                    'metric': metric,
                                    'value_type': value_type,
                                    'month': month,
                                    'value': val,
                                    'median': medv,
                                    'factor_low': out_low,
                                    'factor_high': out_high,
                                    'source_file': src,
                                    'extraction_method': method,
                                    'confidence': conf,
                                    'financial_metrics_id': fid,
                                },
                            )
                        )
                elif min_abs is not None:
                    if abs_val < min_abs:
                        issues.append(
                            ValidationIssue(
                                severity='warning',
                                code='below_min_abs',
                                message=f"{metric} {value_type} for {month} is below minimum expected magnitude",
                                context={
                                    'metric': metric,
                                    'value_type': value_type,
                                    'month': month,
                                    'value': val,
                                    'min_abs_value': min_abs,
                                    'source_file': src,
                                    'extraction_method': method,
                                    'confidence': conf,
                                    'financial_metrics_id': fid,
                                },
                            )
                        )

    # Reconciliation inputs: best Revenue series (Monthly, Actual) by period_scope.
    period_series: Dict[str, float] = {}
    ytd_series: Dict[str, float] = {}

    if revenue_ytd_enabled or revenue_q_enabled or revenue_y_enabled:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked AS (
                  SELECT
                    p.period_label AS month,
                    COALESCE(fm.period_scope, 'Period') AS period_scope,
                    fm.value,
                    fm.confidence,
                    fm.id,
                    ROW_NUMBER() OVER (
                      PARTITION BY p.period_label, COALESCE(fm.period_scope, 'Period')
                      ORDER BY COALESCE(fm.confidence, 0) DESC, fm.id DESC
                    ) rn
                  FROM financial_metrics fm
                  JOIN periods p ON p.id=fm.period_id
                  JOIN line_item_definitions li ON li.id=fm.line_item_id
                  WHERE fm.company_id=%s
                    AND li.name='Revenue'
                    AND fm.value_type='Actual'
                    AND p.period_type='Monthly'
                    AND COALESCE(fm.period_scope,'Period') IN ('Period','YTD')
                )
                SELECT month, period_scope, value
                FROM ranked
                WHERE rn=1;
                """,
                (company_id,),
            )
            data = cur.fetchall()

        for month, scope, value in data:
            m = str(month)
            s = str(scope)
            v = float(value)
            if s == 'Period':
                period_series[m] = v
            elif s == 'YTD':
                ytd_series[m] = v

    if revenue_ytd_enabled:
        issues.extend(
            _reconcile_ytd(
                period_series=period_series,
                ytd_series=ytd_series,
                tolerance_abs=revenue_ytd_tol_abs,
                tolerance_pct=revenue_ytd_tol_pct,
            )
        )

    # Quarter/year corroboration: compare derived sums of monthly Period Revenue
    # against ingested Quarterly/Yearly Revenue when present.
    if revenue_q_enabled or revenue_y_enabled:
        derived_q = _derive_quarterly_sum(period_series)
        derived_y = _derive_yearly_sum(period_series)

        ing_q: Dict[str, float] = {}
        ing_y: Dict[str, float] = {}
        with conn.cursor() as cur:
            # Best (highest confidence) ingested quarterly/yearly Revenue Period facts
            cur.execute(
                """
                WITH ranked AS (
                  SELECT
                    p.period_label,
                    p.period_type,
                    fm.value,
                    fm.confidence,
                    fm.id,
                    ROW_NUMBER() OVER (
                      PARTITION BY p.period_label, p.period_type
                      ORDER BY COALESCE(fm.confidence,0) DESC, fm.id DESC
                    ) rn
                  FROM financial_metrics fm
                  JOIN periods p ON p.id=fm.period_id
                  JOIN line_item_definitions li ON li.id=fm.line_item_id
                  WHERE fm.company_id=%s
                    AND li.name='Revenue'
                    AND fm.value_type='Actual'
                    AND COALESCE(fm.period_scope,'Period')='Period'
                    AND p.period_type IN ('Quarterly','Yearly')
                )
                SELECT period_label, period_type, value
                FROM ranked
                WHERE rn=1;
                """,
                (company_id,),
            )
            for pl, pt, val in cur.fetchall():
                if pt == 'Quarterly':
                    ing_q[str(pl)] = float(val)
                elif pt == 'Yearly':
                    ing_y[str(pl)] = float(val)

        if revenue_q_enabled:
            issues.extend(
                _compare_derived_vs_ingested(
                    derived=derived_q,
                    ingested=ing_q,
                    tolerance_abs=revenue_q_tol_abs,
                    tolerance_pct=revenue_q_tol_pct,
                    code='revenue_quarter_sum_mismatch',
                    label='quarterly revenue',
                )
            )

        if revenue_y_enabled:
            issues.extend(
                _compare_derived_vs_ingested(
                    derived=derived_y,
                    ingested=ing_y,
                    tolerance_abs=revenue_y_tol_abs,
                    tolerance_pct=revenue_y_tol_pct,
                    code='revenue_annual_sum_mismatch',
                    label='annual revenue',
                )
            )

    ok = not any(i.severity == 'error' for i in issues)

    return ValidationReport(ok=ok, issues=issues, metrics_checked=metrics_checked)
