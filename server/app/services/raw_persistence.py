import logging
from typing import Any, Dict, List, Optional

from app.utils.utils import get_db_connection

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip().strip("()"))
    except Exception:
        return None


def persist_raw_facts(
    rows: List[Dict[str, Any]],
    document_id: int,
    company_id: int,
) -> Dict[str, int]:
    """Persist raw extracted facts with coordinates for later audit/reconciliation."""

    if not rows:
        return {"inserted": 0, "errors": 0}

    insert_sql = """
        INSERT INTO extracted_facts_raw (
            document_id,
            company_id,
            context_key,
            line_item_text,
            scenario,
            value_text,
            value_numeric,
            currency,
            period_label,
            period_type,
            source_page,
            source_table,
            source_row,
            source_col,
            extraction_method,
            confidence
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    inserted = 0
    errors = 0

    with get_db_connection() as conn:
        cur = conn.cursor()
        for row in rows:
            try:
                cur.execute(
                    insert_sql,
                    (
                        document_id,
                        company_id,
                        row.get("context_key") or (
                            f"p{row.get('source_page')}_t{row.get('source_table') or 0}" if row.get('source_page') else None
                        ),
                        row.get("line_item"),
                        row.get("value_type"),
                        None if row.get("value") is None else str(row.get("value")),
                        _to_float(row.get("value")),
                        row.get("currency"),
                        row.get("period_label"),
                        row.get("period_type"),
                        row.get("source_page"),
                        row.get("source_table"),
                        row.get("source_row"),
                        row.get("source_col"),
                        row.get("extraction_method"),
                        row.get("confidence"),
                    ),
                )
                inserted += 1
            except Exception as e:
                errors += 1
                logger.debug("raw fact insert failed: %s", e)

        conn.commit()

    return {"inserted": inserted, "errors": errors}
