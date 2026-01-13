"""Demo endpoints

These endpoints exist to support a clean demo flow:
- upload a file (existing /api/upload)
- fetch a concise, human-readable revenue summary + questions

The goal is not to be a complete analytics API; it is a stable, meeting-ready output contract.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.utils.utils import get_db_connection
from app.utils.logging_config import setup_logger, log_with_context

router = APIRouter(prefix="/api/demo", tags=["demo"])
logger = setup_logger("financial-data-api")


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return float((current - previous) / previous * 100)


@router.get("/revenue-summary")
async def revenue_summary(company_id: int = Query(..., ge=1)) -> Dict[str, Any]:
    """Return a revenue-focused summary for demo purposes.

    Includes:
    - current month revenue (Actual)
    - MoM and YoY % change (computed from raw facts)
    - vs Budget % (if budget exists for same period)
    - top generated questions

    This endpoint intentionally returns a compact JSON contract that the frontend can render.
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Latest and previous revenue actuals
                cur.execute(
                    """
                    SELECT
                      p.id AS period_id,
                      p.period_label,
                      p.start_date,
                      fm.value::float AS value,
                      fm.currency,
                      fm.source_file,
                      fm.source_page,
                      fm.source_row
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    JOIN line_item_definitions li ON fm.line_item_id = li.id
                    WHERE fm.company_id = %s
                      AND li.name = 'Revenue'
                      AND fm.value_type = 'Actual'
                      AND p.period_type = 'Monthly'
                    ORDER BY p.start_date DESC
                    LIMIT 2
                    """,
                    (company_id,),
                )
                rows = cur.fetchall()

                if not rows:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No Revenue (Actual) metrics found for company_id {company_id}. Upload data first.",
                    )

                latest = rows[0]
                previous = rows[1] if len(rows) > 1 else None

                # YoY: same month prior year
                latest_start: date = latest[2]
                yoy_start = date(latest_start.year - 1, latest_start.month, 1)
                cur.execute(
                    """
                    SELECT fm.value::float AS value
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    JOIN line_item_definitions li ON fm.line_item_id = li.id
                    WHERE fm.company_id = %s
                      AND li.name = 'Revenue'
                      AND fm.value_type = 'Actual'
                      AND p.period_type = 'Monthly'
                      AND p.start_date = %s
                    LIMIT 1
                    """,
                    (company_id, yoy_start),
                )
                yoy_row = cur.fetchone()

                # Budget for same period (optional)
                cur.execute(
                    """
                    SELECT fm.value::float AS value
                    FROM financial_metrics fm
                    JOIN line_item_definitions li ON fm.line_item_id = li.id
                    WHERE fm.company_id = %s
                      AND li.name = 'Revenue'
                      AND fm.value_type = 'Budget'
                      AND fm.period_id = %s
                    ORDER BY fm.created_at DESC
                    LIMIT 1
                    """,
                    (company_id, latest[0]),
                )
                budget_row = cur.fetchone()

                # Questions
                cur.execute(
                    """
                    SELECT question_text, category, priority, created_at
                    FROM questions
                    WHERE company_id = %s
                    ORDER BY priority ASC, created_at DESC
                    LIMIT 12
                    """,
                    (company_id,),
                )
                questions = [
                    {
                        "text": q[0],
                        "category": q[1],
                        "priority": q[2],
                        "created_at": q[3].isoformat() if q[3] else None,
                    }
                    for q in cur.fetchall()
                ]

        summary = {
            "company_id": company_id,
            "revenue": {
                "period_label": latest[1],
                "value": latest[3],
                "currency": latest[4],
                "mom_change_pct": _pct_change(latest[3], previous[3] if previous else None),
                "yoy_change_pct": _pct_change(latest[3], yoy_row[0] if yoy_row else None),
                "vs_budget_pct": _pct_change(latest[3], budget_row[0] if budget_row else None),
                "sources": [
                    {
                        "source_file": latest[5],
                        "source_page": latest[6],
                        "source_row": latest[7],
                    }
                ],
            },
            "questions": questions,
        }

        log_with_context(
            logger,
            "info",
            "Demo revenue summary generated",
            company_id=company_id,
            period_label=latest[1],
            questions_count=len(questions),
        )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        log_with_context(logger, "error", "Demo revenue summary failed", company_id=company_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate demo summary: {str(e)}")
