from typing import List, Dict, Any
from utils import log_event, get_db_connection
import psycopg2
from psycopg2.extras import RealDictCursor

# If this doesn't work, we turn off perplexity
def persist_data(normalized_rows: List[Dict[str, Any]], company_id: int = 1) -> Dict[str, int]:
    """
    Persist normalized data to the database.
    Inserts every row (Actual and Budget separately), deduplicating only exact hash duplicates.
    Returns counts: {'inserted', 'skipped', 'errors'}.
    """
    if not normalized_rows:
        log_event("persistence_no_data", {"message": "No rows to persist"})
        return {'inserted': 0, 'skipped': 0, 'errors': 0}

    results = {'inserted': 0, 'skipped': 0, 'errors': 0}
    log_event("persistence_started", {"input_rows": len(normalized_rows), "company_id": company_id})

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for idx, row in enumerate(normalized_rows, 1):
                    try:
                        # Required fields
                        required = ['company_id', 'period_id', 'line_item_id', 'value', 'value_type', 'hash']
                        missing = [f for f in required if not row.get(f)]
                        if missing:
                            log_event("persistence_row_skip_missing_fields", {"row_number": idx, "missing_fields": missing})
                            results['errors'] += 1
                            continue

                        # Skip exact hash duplicates
                        cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (row['hash'],))
                        if cur.fetchone():
                            log_event("persistence_row_skip_duplicate", {"row_number": idx, "hash": row['hash']})
                            results['skipped'] += 1
                            continue

                        # Insert new record including source_type
                        cur.execute("""
                            INSERT INTO financial_metrics (
                            company_id, period_id, line_item_id,
                            value, value_type, frequency,
                            currency, source_file, source_page,
                            source_type, notes, hash,
                            created_at, updated_at
                            ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            NOW(), NOW()
                            ) RETURNING id
                        """, (
                            row['company_id'],
                            row['period_id'],
                            row['line_item_id'],
                            row['value'],
                            row.get('value_type', 'Actual'),
                            row.get('frequency', 'Monthly'),
                            row.get('currency', 'USD'),
                            row.get('source_file'),
                            row.get('source_page'),
                            row.get('source_type') or row.get('period_type'),
                            row.get('notes'),
                            row['hash']
                        ))
                        new_id = cur.fetchone()['id']
                        log_event("persistence_row_inserted", {
                            "row_number": idx,
                            "new_id": new_id,
                            "period_id": row['period_id'],
                            "line_item_id": row['line_item_id'],
                            "value": row['value']
                        })
                        results['inserted'] += 1

                        # Batch commit
                        if results['inserted'] % 100 == 0:
                            conn.commit()
                            log_event("persistence_batch_commit", {"rows_committed": results['inserted']})

                    except psycopg2.Error as db_err:
                        log_event("persistence_row_db_error", {
                            "row_number": idx,
                            "error": str(db_err),
                            "error_code": getattr(db_err, 'pgcode', None)
                        })
                        results['errors'] += 1
                        conn.rollback()
                        continue

                    except Exception as e:
                        log_event("persistence_row_error", {
                            "row_number": idx,
                            "error": str(e),
                            "error_type": type(e).__name__
                        })
                        results['errors'] += 1
                        continue

                conn.commit()
                log_event("persistence_completed", {
                    "input_rows": len(normalized_rows),
                    "inserted": results['inserted'],
                    "skipped": results['skipped'],
                    "errors": results['errors'],
                    "success_rate": results['inserted'] / len(normalized_rows)
                })

    except Exception as e:
        log_event("persistence_failed", {
            "error": str(e),
            "error_type": type(e).__name__,
            "partial_results": results
        })
        raise

    return results
