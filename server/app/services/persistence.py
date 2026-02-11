# Canonical module: server/app/services/persistence.py

import logging
from typing import List, Dict, Any
from app.utils.utils import get_db_connection

logger = logging.getLogger(__name__)

def persist_data(
    rows: List[Dict[str, Any]],
    company_id: int,
    period_id: int
) -> Dict[str, int]:
    """
    Insert only new rows into financial_metrics based on the compound uniqueness key:
      (company_id, period_id, line_item_id, value_type, source_file)

    Args:
        rows: List of normalized row dicts...
        company_id: ID of the company for this batch.
        period_id: ID of the period for this batch.

    Returns:
        A dict with counts:
          {
            "inserted": <number of new rows>,
            "skipped":  <number of rows skipped due to existing key>,
            "errors":   <number of errors during insert>
          }
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Fetch existing compound keys for this company & period
        cursor.execute(
            """
            SELECT
                company_id,
                period_id,
                line_item_id,
                value_type,
                period_scope,
                source_file
            FROM financial_metrics
            WHERE company_id = %s
              AND period_id = %s
            """,
            (company_id, period_id),
        )
        existing_keys = {
            (cid, pid, liid, vtype, scope, src)
            for cid, pid, liid, vtype, scope, src in cursor.fetchall()
        }
        logger.debug("Existing keys: %s", existing_keys)

        # 2. Filter incoming rows to only those not already present
        new_rows = []
        for row in rows:
            key = (
                row["company_id"],
                row["period_id"],
                row["line_item_id"],
                row["value_type"],
                row.get("period_scope") or 'Period',
                row["source_file"],
            )
            if key not in existing_keys:
                new_rows.append(row)
        logger.info("New rows to insert: %d", len(new_rows))

        if not new_rows:
            return {"inserted": 0, "skipped": 0, "errors": 0}

        # 3. Bulk insert with ON CONFLICT on the compound key
        values_template = ", ".join(["%s"] * 19)
        insert_sql = f"""
            INSERT INTO financial_metrics (
                company_id,
                document_id,
                context_key,
                period_id,
                line_item_id,
                value,
                value_type,
                period_scope,
                frequency,
                currency,
                source_file,
                source_page,
                source_table,
                source_row,
                source_col,
                extraction_method,
                confidence,
                source_type,
                notes
            )
            VALUES ({values_template})
            ON CONFLICT (
                company_id,
                period_id,
                line_item_id,
                value_type,
                period_scope,
                source_file
            )
            DO NOTHING
        """

        insert_data = [
            (
                row["company_id"],
                row.get("document_id"),
                row.get("context_key"),
                row["period_id"],
                row["line_item_id"],
                row["value"],
                row["value_type"],
                row.get("period_scope") or 'Period',
                row.get("frequency"),
                row.get("currency"),
                row["source_file"],
                row.get("source_page"),
                row.get("source_table"),
                row.get("source_row"),
                row.get("source_col"),
                row.get("extraction_method"),
                row.get("confidence"),
                row.get("source_type"),
                row.get("notes"),
            )
            for row in new_rows
        ]

        inserted = 0
        skipped = 0
        errors = 0

        try:
            cursor.executemany(insert_sql, insert_data)
            conn.commit()
            inserted = cursor.rowcount or 0
            skipped = len(new_rows) - inserted
            logger.info("Inserted %d new rows, skipped %d", inserted, skipped)
        except Exception as e:
            conn.rollback()
            logger.error("Error inserting rows: %s", e)
            errors = len(new_rows)

        return {"inserted": inserted, "skipped": skipped, "errors": errors}
