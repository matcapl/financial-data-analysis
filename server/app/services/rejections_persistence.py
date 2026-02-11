import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.utils.utils import get_db_connection

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        # Keep raw precision when possible
        return Decimal(str(value).replace(",", "").strip().strip("()"))
    except Exception:
        return None


def persist_fact_rejections(
    rejections: List[Dict[str, Any]],
    *,
    company_id: int,
    document_id: Optional[int] = None,
) -> Dict[str, int]:
    """Persist rejected candidates so the pipeline doesn't silently drop rows.

    This is intentionally best-effort: failures here should not fail ingestion.
    """

    if not rejections:
        return {"inserted": 0, "errors": 0}

    insert_sql = """
        INSERT INTO fact_rejections (
            document_id,
            company_id,
            stage,
            reason,
            context_key,
            line_item_text,
            scenario,
            value_text,
            value_numeric,
            currency,
            period_label_raw,
            period_label_canonical,
            period_type,
            source_file,
            source_page,
            source_table,
            source_row,
            source_col,
            extraction_method,
            confidence,
            details
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    inserted = 0
    errors = 0

    with get_db_connection() as conn:
        cur = conn.cursor()
        for r in rejections:
            try:
                cur.execute(
                    insert_sql,
                    (
                        document_id,
                        company_id,
                        r.get("stage") or "normalization",
                        r.get("reason") or "unknown",
                        r.get("context_key"),
                        r.get("line_item_text"),
                        r.get("scenario"),
                        r.get("value_text"),
                        _to_decimal(r.get("value_numeric")),
                        r.get("currency"),
                        r.get("period_label_raw"),
                        r.get("period_label_canonical"),
                        r.get("period_type"),
                        r.get("source_file"),
                        r.get("source_page"),
                        r.get("source_table"),
                        r.get("source_row"),
                        r.get("source_col"),
                        r.get("extraction_method"),
                        r.get("confidence"),
                        r.get("details") or {},
                    ),
                )
                inserted += 1
            except Exception as e:
                errors += 1
                logger.debug("fact rejection insert failed: %s", e)

        try:
            conn.commit()
        except Exception:
            conn.rollback()
            errors += 1

    return {"inserted": inserted, "errors": errors}
