# server/scripts/persistence.py - Database operations layer using existing patterns
from datetime import datetime
from utils import get_db_connection, log_event, hash_datapoint


class DatabasePersistence:
    """Handles database operations using existing connection patterns"""
    
    def __init__(self, company_id: int = 1):
        self.company_id = company_id
        self.current_file_hashes = set()  # Track duplicates within current file
        
    def persist_row(self, normalized_row: dict, conn, cur) -> dict:
        """
        Persist a single normalized row to database
        Returns: {"status": "inserted"|"skipped"|"error", "message": str}
        """
        
        row_number = normalized_row.get('_row_number', 0)
        
        try:
            # 1. Lookup line_item_id (consistent with existing ingest_xlsx.py logic)
            cur.execute("SELECT id FROM line_item_definitions WHERE name=%s", (normalized_row["line_item"],))
            li = cur.fetchone()
            
            if not li:
                cur.execute("SELECT name FROM line_item_definitions")
                available = [r[0] for r in cur.fetchall()]
                raise Exception(f"Line item not found: {normalized_row['line_item']}. Available: {available}")
            line_item_id = li[0]
            
            # 2. Lookup or insert period_id (consistent with existing logic)
            period_info = normalized_row.get("_period_info")
            if period_info:
                cur.execute(
                    "SELECT id FROM periods WHERE period_type=%s AND period_label=%s",
                    (period_info["type"], period_info["label"])
                )
                pr = cur.fetchone()
                
                if pr:
                    period_id = pr[0]
                else:
                    # Insert new period
                    cur.execute(
                        "INSERT INTO periods "
                        "(period_type,period_label,start_date,end_date,created_at,updated_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                        (period_info["type"], period_info["label"],
                         period_info["start_date"], period_info["end_date"],
                         datetime.now(), datetime.now())
                    )
                    period_id = cur.fetchone()[0]
            else:
                raise Exception(f"Period information missing for row {row_number}")
                
            # 3. Compute hash for deduplication (using existing utility)
            row_hash = hash_datapoint(
                self.company_id, period_id,
                normalized_row["line_item"], normalized_row["value_type"],
                normalized_row["frequency"], normalized_row["value"]
            )
            
            # 4. In-file duplicate check (consistent with existing logic)
            if row_hash in self.current_file_hashes:
                log_event("duplicate_skipped_infile", {
                    "row_number": row_number, 
                    "hash": row_hash
                })
                return {"status": "skipped", "message": "Duplicate within file"}
                
            # 5. Database duplicate check (consistent with existing logic)
            cur.execute("SELECT id FROM financial_metrics WHERE hash=%s", (row_hash,))
            existing = cur.fetchone()
            
            if existing:
                log_event("duplicate_skipped_db", {
                    "row_number": row_number,
                    "hash": row_hash,
                    "existing_id": existing[0]
                })
                return {"status": "skipped", "message": "Duplicate in database"}
                
            # 6. Insert metric (using correct table name from schema)
            cur.execute(
                """INSERT INTO financial_metrics (
                    company_id, period_id, line_item_id, value_type, frequency,
                    value, currency, source_file, source_page, source_type,
                    notes, hash, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.company_id, period_id, line_item_id,
                    normalized_row["value_type"], normalized_row["frequency"],
                    normalized_row["value"], normalized_row["currency"],
                    normalized_row["source_file"], normalized_row["source_page"],
                    normalized_row["source_type"], normalized_row.get("notes"),
                    row_hash, datetime.now(), datetime.now()
                )
            )
            
            # 7. Track success
            self.current_file_hashes.add(row_hash)
            
            log_event("metric_inserted", {
                "row_number": row_number,
                "line_item": normalized_row["line_item"],
                "period_label": normalized_row.get("period_label"),
                "value_type": normalized_row["value_type"],
                "value": normalized_row["value"],
                "hash": row_hash
            })
            
            return {"status": "inserted", "message": "Successfully inserted"}
            
        except Exception as e:
            log_event("persistence_error", {
                "row_number": row_number,
                "error": str(e),
                "line_item": normalized_row.get("line_item"),
                "period_label": normalized_row.get("period_label")
            })
            return {"status": "error", "message": str(e)}
            
    def persist_batch(self, normalized_rows: list) -> dict:
        """
        Persist a batch of normalized rows to database
        Returns: {"inserted": int, "skipped": int, "errors": int, "total": int}
        """
        
        results = {"inserted": 0, "skipped": 0, "errors": 0, "total": len(normalized_rows)}
        
        log_event("batch_persistence_started", {
            "company_id": self.company_id,
            "total_rows": len(normalized_rows)
        })
        
        # Use existing connection pattern from utils.py
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for normalized_row in normalized_rows:
                    try:
                        result = self.persist_row(normalized_row, conn, cur)
                        
                        if result["status"] == "inserted":
                            results["inserted"] += 1
                        elif result["status"] == "skipped":
                            results["skipped"] += 1
                        else:
                            results["errors"] += 1
                            
                    except Exception as e:
                        results["errors"] += 1
                        row_number = normalized_row.get('_row_number', 0)
                        log_event("batch_row_error", {
                            "row_number": row_number,
                            "error": str(e)
                        })
                        
                # Commit all changes at once
                conn.commit()
                
        log_event("batch_persistence_completed", {
            "company_id": self.company_id,
            **results
        })
        
        return results


def persist_data(normalized_rows: list, company_id: int = 1) -> dict:
    """Convenience function for backward compatibility"""
    persistence = DatabasePersistence(company_id)
    return persistence.persist_batch(normalized_rows)


if __name__ == "__main__":
    # Test persistence with sample data
    sample_normalized_row = {
        "_row_number": 1,
        "line_item": "Revenue",
        "period_label": "Feb 2025",
        "value": 1000000.0,
        "value_type": "Actual",
        "frequency": "Monthly",
        "currency": "USD",
        "source_file": "test.csv",
        "source_page": 1,
        "source_type": "Raw",
        "notes": "",
        "_period_info": {
            "type": "Monthly",
            "label": "Feb 2025",
            "start_date": "2025-02-01",
            "end_date": "2025-02-28"
        }
    }
    
    try:
        persistence = DatabasePersistence(company_id=1)
        result = persistence.persist_batch([sample_normalized_row])
        print(f"Persistence result: {result}")
    except Exception as e:
        print(f"Persistence test failed: {e}")