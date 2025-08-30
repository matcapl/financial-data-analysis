"""
Financial repository implementation
Handles database operations for financial entities
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from .base import BaseRepository
from utils import get_db_connection
from app.models.domain.financial import FinancialRecord, FinancialMetric, AnalyticalQuestion


class FinancialRecordRepository(BaseRepository[FinancialRecord]):
    """Repository for financial records"""
    
    def create(self, record: FinancialRecord) -> FinancialRecord:
        """Insert a new financial record"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO financial_data 
                    (company_id, date, description, amount, category, subcategory)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at
                """, (
                    record.company_id,
                    record.date,
                    record.description,
                    record.amount,
                    record.category,
                    record.subcategory
                ))
                
                result = cur.fetchone()
                record.id = result[0]
                record.created_at = result[1]
                conn.commit()
                return record
    
    def get_by_id(self, id: int) -> Optional[FinancialRecord]:
        """Get financial record by ID"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, company_id, date, description, amount, category, subcategory, created_at
                    FROM financial_data WHERE id = %s
                """, (id,))
                
                row = cur.fetchone()
                if row:
                    return FinancialRecord(
                        id=row[0],
                        company_id=row[1],
                        date=row[2],
                        description=row[3], 
                        amount=row[4],
                        category=row[5],
                        subcategory=row[6],
                        created_at=row[7]
                    )
                return None
    
    def get_by_company(self, company_id: int) -> List[FinancialRecord]:
        """Get all financial records for a company"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, company_id, date, description, amount, category, subcategory, created_at
                    FROM financial_data WHERE company_id = %s
                    ORDER BY date DESC
                """, (company_id,))
                
                records = []
                for row in cur.fetchall():
                    records.append(FinancialRecord(
                        id=row[0],
                        company_id=row[1],
                        date=row[2],
                        description=row[3],
                        amount=row[4],
                        category=row[5], 
                        subcategory=row[6],
                        created_at=row[7]
                    ))
                return records
    
    def get_all(self) -> List[FinancialRecord]:
        """Get all financial records"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, company_id, date, description, amount, category, subcategory, created_at
                    FROM financial_data ORDER BY date DESC
                """)
                
                records = []
                for row in cur.fetchall():
                    records.append(FinancialRecord(
                        id=row[0],
                        company_id=row[1],
                        date=row[2],
                        description=row[3],
                        amount=row[4],
                        category=row[5],
                        subcategory=row[6], 
                        created_at=row[7]
                    ))
                return records
    
    def update(self, id: int, record: FinancialRecord) -> Optional[FinancialRecord]:
        """Update financial record"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE financial_data 
                    SET description = %s, amount = %s, category = %s, subcategory = %s
                    WHERE id = %s
                    RETURNING id, company_id, date, description, amount, category, subcategory, created_at
                """, (
                    record.description,
                    record.amount,
                    record.category,
                    record.subcategory,
                    id
                ))
                
                row = cur.fetchone()
                if row:
                    conn.commit()
                    return FinancialRecord(
                        id=row[0],
                        company_id=row[1],
                        date=row[2],
                        description=row[3],
                        amount=row[4],
                        category=row[5],
                        subcategory=row[6],
                        created_at=row[7]
                    )
                return None
    
    def delete(self, id: int) -> bool:
        """Delete financial record"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM financial_data WHERE id = %s", (id,))
                deleted = cur.rowcount > 0
                if deleted:
                    conn.commit()
                return deleted
    
    def exists(self, id: int) -> bool:
        """Check if financial record exists"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM financial_data WHERE id = %s", (id,))
                return cur.fetchone() is not None


class FinancialMetricRepository(BaseRepository[FinancialMetric]):
    """Repository for financial metrics"""
    
    def create(self, metric: FinancialMetric) -> FinancialMetric:
        """Insert a new financial metric"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO financial_metrics 
                    (company_id, metric_name, metric_type, value, period, calculation_date, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    metric.company_id,
                    metric.metric_name,
                    metric.metric_type.value,
                    metric.value,
                    metric.period,
                    metric.calculation_date,
                    metric.metadata
                ))
                
                metric.id = cur.fetchone()[0]
                conn.commit()
                return metric
    
    def get_by_company(self, company_id: int) -> List[FinancialMetric]:
        """Get all metrics for a company"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, company_id, metric_name, metric_type, value, period, calculation_date, metadata
                    FROM financial_metrics WHERE company_id = %s
                    ORDER BY calculation_date DESC
                """, (company_id,))
                
                metrics = []
                for row in cur.fetchall():
                    metrics.append(FinancialMetric(
                        id=row[0],
                        company_id=row[1],
                        metric_name=row[2],
                        metric_type=row[3],
                        value=row[4],
                        period=row[5],
                        calculation_date=row[6],
                        metadata=row[7]
                    ))
                return metrics
    
    def get_by_id(self, id: int) -> Optional[FinancialMetric]:
        """Get metric by ID"""
        # Implementation similar to FinancialRecord
        pass
    
    def get_all(self) -> List[FinancialMetric]:
        """Get all metrics"""
        # Implementation similar to get_by_company but without company filter
        pass
    
    def update(self, id: int, metric: FinancialMetric) -> Optional[FinancialMetric]:
        """Update metric"""
        # Implementation similar to FinancialRecord
        pass
    
    def delete(self, id: int) -> bool:
        """Delete metric"""
        # Implementation similar to FinancialRecord
        pass
    
    def exists(self, id: int) -> bool:
        """Check if metric exists"""
        # Implementation similar to FinancialRecord
        pass