# server/scripts/persistence.py

import logging
from typing import List, Dict, Tuple
from utils import get_db_connection, log_event

logger = logging.getLogger(__name__)

def persist_data(
    rows: List[Dict],
    company_id: int,
    period_id: int
) -> int:
    """
    Insert only new rows into financial_metrics based on the compound uniqueness key:
      (company_id, period_id, line_item_id, value_type, source_file)

    Args:
        rows: List of normalized row dicts. Each dict must include:
            - company_id (int)
            - period_id (int)
            - line_item_id (int)
            - value (numeric)
            - value_type (str)
            - frequency (str)
            - currency (str)
            - source_file (str)
            - source_page (int)
            - source_type (str)
            - notes (str)
        company_id: ID of the company for this batch.
        period_id: ID of the period for this batch.

    Returns:
        Number of newly inserted rows.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch existing compound keys for this company & period
    cursor.execute(
        """
        SELECT
            company_id,
            period_id,
            line_item_id,
            value_type,
            source_file
        FROM financial_metrics
        WHERE company_id = %s
          AND period_id = %s
        """,
        (company_id, period_id),
    )
    existing_keys = {
        (cid, pid, liid, vtype, src)
        for cid, pid, liid, vtype, src in cursor.fetchall()
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
            row["source_file"],
        )
        if key not in existing_keys:
            new_rows.append(row)
    logger.info("New rows to insert: %d", len(new_rows))

    if not new_rows:
        cursor.close()
        conn.close()
        return 0

    # 3. Bulk insert with ON CONFLICT on the compound key
    # Prepare insert values placeholder
    values_template = ", ".join(["%s"] * 11)
    insert_sql = f"""
        INSERT INTO financial_metrics (
            company_id,
            period_id,
            line_item_id,
            value,
            value_type,
            frequency,
            currency,
            source_file,
            source_page,
            source_type,
            notes
        )
        VALUES ({values_template})
        ON CONFLICT (
            company_id,
            period_id,
            line_item_id,
            value_type,
            source_file
        )
        DO NOTHING
    """

    # Build data tuples
    insert_data: List[Tuple] = [
        (
            row["company_id"],
            row["period_id"],
            row["line_item_id"],
            row["value"],
            row["value_type"],
            row.get("frequency"),
            row.get("currency"),
            row["source_file"],
            row.get("source_page"),
            row.get("source_type"),
            row.get("notes"),
        )
        for row in new_rows
    ]

    # Execute batch insert
    try:
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        inserted = cursor.rowcount if cursor.rowcount is not None else len(new_rows)
        logger.info("Inserted %d new rows", inserted)
    except Exception as e:
        conn.rollback()
        logger.error("Error inserting rows: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()

    return inserted
