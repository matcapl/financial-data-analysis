# server/scripts/persistence.py
from typing import Optional, List, Dict, Any, Tuple
from utils import log_event, get_db_connection
import psycopg2
from psycopg2.extras import RealDictCursor

def persist_data(normalized_rows: List[Dict[str, Any]], company_id: int = 1) -> Dict[str, int]:
    """
    Persist normalized data to the database with deduplication and error handling.
    Returns dict with counts: {'inserted': int, 'skipped': int, 'errors': int}
    """
    if not normalized_rows:
        log_event("persistence_no_data", {"message": "No rows to persist"})
        return {'inserted': 0, 'skipped': 0, 'errors': 0}
    
    results = {'inserted': 0, 'skipped': 0, 'errors': 0}
    
    log_event("persistence_started", {
        "input_rows": len(normalized_rows),
        "company_id": company_id
    })
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Process each row
                for row_idx, row in enumerate(normalized_rows, 1):
                    try:
                        # Validate required fields
                        required_fields = ['company_id', 'period_id', 'line_item_id', 'value', 'hash']
                        missing_fields = [field for field in required_fields if field not in row or row[field] is None]
                        
                        if missing_fields:
                            log_event("persistence_row_skip_missing_fields", {
                                "row_number": row.get('_row_number', row_idx),
                                "missing_fields": missing_fields
                            })
                            results['errors'] += 1
                            continue
                        
                        # Check for duplicates using hash
                        cur.execute("""
                            SELECT id FROM financial_metrics 
                            WHERE hash = %s
                        """, (row['hash'],))
                        
                        existing = cur.fetchone()
                        if existing:
                            log_event("persistence_row_skip_duplicate", {
                                "row_number": row.get('_row_number', row_idx),
                                "existing_id": existing['id'],
                                "hash": row['hash']
                            })
                            results['skipped'] += 1
                            continue
                        
                        # Alternative duplicate check by key fields
                        cur.execute("""
                            SELECT id FROM financial_metrics 
                            WHERE company_id = %s AND period_id = %s AND line_item_id = %s 
                            AND value_type = %s
                        """, (row['company_id'], row['period_id'], row['line_item_id'], 
                              row.get('value_type', 'Actual')))
                        
                        existing = cur.fetchone()
                        if existing:
                            log_event("persistence_row_skip_key_duplicate", {
                                "row_number": row.get('_row_number', row_idx),
                                "existing_id": existing['id'],
                                "keys": {
                                    "company_id": row['company_id'],
                                    "period_id": row['period_id'],
                                    "line_item_id": row['line_item_id'],
                                    "value_type": row.get('value_type', 'Actual')
                                }
                            })
                            results['skipped'] += 1
                            continue
                        
                        # Insert new record
                        insert_sql = """
                            INSERT INTO financial_metrics (
                                company_id, period_id, line_item_id, value, value_type, 
                                frequency, currency, source_file, source_page, source_type, 
                                notes, hash, created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                            ) RETURNING id
                        """
                        
                        insert_values = (
                            row['company_id'],
                            row['period_id'],
                            row['line_item_id'],
                            row['value'],
                            row.get('value_type', 'Actual'),
                            row.get('frequency', 'Monthly'),
                            row.get('currency', 'USD'),
                            row.get('source_file'),
                            row.get('source_page'),
                            row.get('source_type'),
                            row.get('notes'),
                            row['hash']
                        )
                        
                        cur.execute(insert_sql, insert_values)
                        new_id = cur.fetchone()['id']
                        
                        log_event("persistence_row_inserted", {
                            "row_number": row.get('_row_number', row_idx),
                            "new_id": new_id,
                            "period": row.get('_canonical_period'),
                            "line_item_id": row['line_item_id'],
                            "value": row['value']
                        })
                        
                        results['inserted'] += 1
                        
                        # Commit every 100 rows to avoid long transactions
                        if results['inserted'] % 100 == 0:
                            conn.commit()
                            log_event("persistence_batch_commit", {
                                "rows_committed": results['inserted']
                            })
                    
                    except psycopg2.Error as db_error:
                        log_event("persistence_row_db_error", {
                            "row_number": row.get('_row_number', row_idx),
                            "error": str(db_error),
                            "error_code": db_error.pgcode if hasattr(db_error, 'pgcode') else None
                        })
                        results['errors'] += 1
                        # Rollback the current transaction and continue
                        conn.rollback()
                        continue
                    
                    except Exception as e:
                        log_event("persistence_row_error", {
                            "row_number": row.get('_row_number', row_idx),
                            "error": str(e),
                            "error_type": type(e).__name__
                        })
                        results['errors'] += 1
                        continue
                
                # Final commit
                conn.commit()
                
                log_event("persistence_completed", {
                    "input_rows": len(normalized_rows),
                    "inserted": results['inserted'],
                    "skipped": results['skipped'],
                    "errors": results['errors'],
                    "success_rate": results['inserted'] / len(normalized_rows) if normalized_rows else 0
                })
    
    except Exception as e:
        log_event("persistence_failed", {
            "error": str(e),
            "error_type": type(e).__name__,
            "partial_results": results
        })
        raise
    
    return results

def validate_foreign_keys(normalized_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that all foreign key references exist in the database.
    Returns validation report.
    """
    validation_report = {
        'valid_periods': set(),
        'invalid_periods': set(),
        'valid_line_items': set(),
        'invalid_line_items': set(),
        'valid_companies': set(),
        'invalid_companies': set()
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                
                # Get all unique references from the data
                period_ids = set(row.get('period_id') for row in normalized_rows if row.get('period_id'))
                line_item_ids = set(row.get('line_item_id') for row in normalized_rows if row.get('line_item_id'))
                company_ids = set(row.get('company_id') for row in normalized_rows if row.get('company_id'))
                
                # Validate period IDs
                if period_ids:
                    cur.execute("SELECT id FROM periods WHERE id = ANY(%s)", (list(period_ids),))
                    valid_periods = set(row[0] for row in cur.fetchall())
                    validation_report['valid_periods'] = valid_periods
                    validation_report['invalid_periods'] = period_ids - valid_periods
                
                # Validate line item IDs
                if line_item_ids:
                    cur.execute("SELECT id FROM line_item_definitions WHERE id = ANY(%s)", (list(line_item_ids),))
                    valid_line_items = set(row[0] for row in cur.fetchall())
                    validation_report['valid_line_items'] = valid_line_items
                    validation_report['invalid_line_items'] = line_item_ids - valid_line_items
                
                # Validate company IDs
                if company_ids:
                    cur.execute("SELECT id FROM companies WHERE id = ANY(%s)", (list(company_ids),))
                    valid_companies = set(row[0] for row in cur.fetchall())
                    validation_report['valid_companies'] = valid_companies
                    validation_report['invalid_companies'] = company_ids - valid_companies
                
                log_event("foreign_key_validation", {
                    "period_ids_checked": len(period_ids),
                    "valid_periods": len(validation_report['valid_periods']),
                    "invalid_periods": len(validation_report['invalid_periods']),
                    "line_item_ids_checked": len(line_item_ids),
                    "valid_line_items": len(validation_report['valid_line_items']),
                    "invalid_line_items": len(validation_report['invalid_line_items']),
                    "company_ids_checked": len(company_ids),
                    "valid_companies": len(validation_report['valid_companies']),
                    "invalid_companies": len(validation_report['invalid_companies'])
                })
    
    except Exception as e:
        log_event("foreign_key_validation_error", {"error": str(e)})
        raise
    
    return validation_report

def get_persistence_statistics(company_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get statistics about persisted data.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Base query with optional company filter
                where_clause = "WHERE company_id = %s" if company_id else ""
                params = [company_id] if company_id else []
                
                # Total metrics
                cur.execute(f"SELECT COUNT(*) as total FROM financial_metrics {where_clause}", params)
                total_metrics = cur.fetchone()['total']
                
                # Metrics by value type
                cur.execute(f"""
                    SELECT value_type, COUNT(*) as count 
                    FROM financial_metrics {where_clause}
                    GROUP BY value_type 
                    ORDER BY count DESC
                """, params)
                by_value_type = dict(cur.fetchall())
                
                # Metrics by period type
                cur.execute(f"""
                    SELECT p.period_type, COUNT(*) as count 
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    {where_clause}
                    GROUP BY p.period_type 
                    ORDER BY count DESC
                """, params)
                by_period_type = dict(cur.fetchall())
                
                # Metrics by line item
                cur.execute(f"""
                    SELECT li.name, COUNT(*) as count 
                    FROM financial_metrics fm
                    JOIN line_item_definitions li ON fm.line_item_id = li.id
                    {where_clause}
                    GROUP BY li.name 
                    ORDER BY count DESC
                    LIMIT 10
                """, params)
                by_line_item = dict(cur.fetchall())
                
                # Recent activity
                cur.execute(f"""
                    SELECT DATE(created_at) as date, COUNT(*) as count 
                    FROM financial_metrics 
                    {where_clause}
                    GROUP BY DATE(created_at) 
                    ORDER BY date DESC 
                    LIMIT 7
                """, params)
                recent_activity = dict(cur.fetchall())
                
                stats = {
                    'total_metrics': total_metrics,
                    'by_value_type': by_value_type,
                    'by_period_type': by_period_type,
                    'by_line_item': by_line_item,
                    'recent_activity': recent_activity,
                    'company_id_filter': company_id
                }
                
                log_event("persistence_statistics_generated", {
                    "company_id": company_id,
                    "total_metrics": total_metrics,
                    "value_types": len(by_value_type),
                    "period_types": len(by_period_type),
                    "line_items": len(by_line_item)
                })
                
                return stats
    
    except Exception as e:
        log_event("persistence_statistics_error", {"error": str(e)})
        raise

from typing import Optional

if __name__ == "__main__":
    # Test persistence functions
    print("Testing persistence module...")
    
    # Get statistics
    try:
        stats = get_persistence_statistics()
        print(f"Total metrics in database: {stats['total_metrics']}")
        print(f"Value types: {list(stats['by_value_type'].keys())}")
        print(f"Period types: {list(stats['by_period_type'].keys())}")
    except Exception as e:
        print(f"Statistics error: {e}")
