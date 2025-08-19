#!/usr/bin/env python3
"""
calc_metrics.py - Fixed version for derived metrics calculation

FIXED ISSUES:
1. Uses period_id instead of period_label (matches schema)
2. Proper foreign key lookups for periods table
3. Handles period creation for YTD calculations
4. Robust error handling and logging
5. Matches derived_metrics table schema exactly
"""

import psycopg2
import json
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from utils import get_db_connection, log_event


def calculate_percentage(current, previous):
    """Calculate percentage change between two values."""
    if previous is None or previous == 0 or current is None:
        return None
    return ((current - previous) / previous) * 100


def get_or_create_period(cur, period_label, period_type="Monthly", start_date=None, end_date=None):
    """Get period_id or create period if it doesn't exist."""
    # First try to find existing period
    cur.execute(
        "SELECT id FROM periods WHERE period_label = %s AND period_type = %s",
        (period_label, period_type)
    )
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Create new period if it doesn't exist
    cur.execute(
        """
        INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (period_type, period_label, start_date, end_date, datetime.now(), datetime.now())
    )
    return cur.fetchone()[0]


def calculate_ytd(cur, company_id, year, line_item_id):
    """Calculate Year-to-Date totals and return constituent periods."""
    cur.execute(
        """
        SELECT p.period_label, fm.value, p.id
        FROM financial_metrics fm
        JOIN periods p ON fm.period_id = p.id
        WHERE fm.company_id = %s
        AND fm.frequency = 'Monthly'
        AND fm.line_item_id = %s
        AND EXTRACT(YEAR FROM p.start_date) = %s
        AND fm.value_type = 'Actual'
        ORDER BY p.start_date
        """,
        (company_id, line_item_id, year)
    )
    rows = cur.fetchall()
    if not rows:
        return None, []
    
    total = sum(val for _, val, _ in rows if val is not None)
    labels = [label for label, _, _ in rows]
    return total, labels


def main():
    if len(sys.argv) < 2:
        print("Usage: python calc_metrics.py <company_id>")
        sys.exit(1)

    company_id = int(sys.argv[1])
    
    log_event("calc_metrics_started", {
        "company_id": company_id,
        "timestamp": datetime.now().isoformat()
    })

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Load seeded line items
            cur.execute("""
                SELECT id, name
                FROM line_item_definitions
                WHERE name IN ('Revenue', 'Gross Profit', 'EBITDA')
            """)
            line_items = cur.fetchall()
            
            if not line_items:
                raise Exception("No line items found. Ensure database is properly seeded.")

            for line_item_id, line_item_name in line_items:
                log_event("processing_line_item", {
                    "line_item_id": line_item_id,
                    "line_item_name": line_item_name
                })
                
                # Fetch all metrics for this company + line item with period info
                cur.execute(
                    """
                    SELECT
                        p.period_label,
                        p.id as period_id,
                        fm.value_type,
                        fm.frequency,
                        fm.value,
                        EXTRACT(YEAR FROM p.start_date) AS year,
                        p.start_date,
                        fm.id as fm_id
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    WHERE fm.company_id = %s
                    AND fm.line_item_id = %s
                    ORDER BY p.start_date
                    """,
                    (company_id, line_item_id)
                )
                metrics = cur.fetchall()

                if not metrics:
                    log_event("no_metrics_found", {
                        "line_item_id": line_item_id,
                        "company_id": company_id
                    })
                    continue

                # Organize by frequency and value_type
                monthly = {}
                quarterly = {}
                for row in metrics:
                    period_label, period_id, value_type, frequency, value, year, start_date, fm_id = row
                    key = (period_label, value_type)
                    data = (value, fm_id, period_id, start_date)
                    
                    if frequency == "Monthly":
                        monthly[key] = data
                    elif frequency == "Quarterly":
                        quarterly[key] = data

                years = {int(row[5]) for row in metrics if row[5] is not None}

                # CALCULATION 1: Month-over-Month growth
                for (period_label, value_type), (value, fm_id, period_id, start_date) in monthly.items():
                    if value_type != "Actual" or value is None:
                        continue
                        
                    # Find previous month period
                    prev_month_start = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)
                    cur.execute(
                        """
                        SELECT p.period_label, p.id 
                        FROM periods p 
                        WHERE p.start_date = %s AND p.period_type = 'Monthly'
                        """,
                        (prev_month_start,)
                    )
                    prev_period = cur.fetchone()
                    
                    if prev_period:
                        prev_label, prev_period_id = prev_period
                        prev_data = monthly.get((prev_label, "Actual"))
                        
                        if prev_data:
                            prev_value, _, _, _ = prev_data
                            mom_growth = calculate_percentage(value, prev_value)
                            
                            if mom_growth is not None:
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note,
                                        corroboration_status, frequency, created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (base_metric_id, company_id, period_id, calculation_type) 
                                    DO UPDATE SET 
                                        calculated_value = EXCLUDED.calculated_value,
                                        updated_at = EXCLUDED.updated_at
                                    """,
                                    (
                                        fm_id, "MoM Growth", company_id, period_id,
                                        mom_growth, "%", [fm_id],
                                        f"Month-over-month growth: {period_label} vs {prev_label}",
                                        "Ok", "Monthly", datetime.now(), datetime.now()
                                    )
                                )

                # CALCULATION 2: Quarter-over-Quarter growth
                for (period_label, value_type), (value, fm_id, period_id, start_date) in quarterly.items():
                    if value_type != "Actual" or value is None:
                        continue
                        
                    # Find previous quarter (approximately 90 days back)
                    prev_quarter_date = start_date - timedelta(days=90)
                    cur.execute(
                        """
                        SELECT p.period_label, p.id, fm.value, fm.id
                        FROM periods p
                        JOIN financial_metrics fm ON p.id = fm.period_id
                        WHERE p.period_type = 'Quarterly'
                        AND p.start_date <= %s
                        AND fm.company_id = %s
                        AND fm.line_item_id = %s
                        AND fm.value_type = 'Actual'
                        ORDER BY p.start_date DESC
                        LIMIT 1
                        """,
                        (prev_quarter_date, company_id, line_item_id)
                    )
                    prev_quarter = cur.fetchone()
                    
                    if prev_quarter:
                        prev_label, _, prev_value, _ = prev_quarter
                        qoq_growth = calculate_percentage(value, prev_value)
                        
                        if qoq_growth is not None:
                            cur.execute(
                                """
                                INSERT INTO derived_metrics (
                                    base_metric_id, calculation_type, company_id, period_id,
                                    calculated_value, unit, source_ids, calculation_note,
                                    corroboration_status, frequency, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (base_metric_id, company_id, period_id, calculation_type) 
                                DO UPDATE SET 
                                    calculated_value = EXCLUDED.calculated_value,
                                    updated_at = EXCLUDED.updated_at
                                """,
                                (
                                    fm_id, "QoQ Growth", company_id, period_id,
                                    qoq_growth, "%", [fm_id],
                                    f"Quarter-over-quarter growth: {period_label} vs {prev_label}",
                                    "Ok", "Quarterly", datetime.now(), datetime.now()
                                )
                            )

                # CALCULATION 3: Year-over-Year growth
                for year in years:
                    for freq_dict, freq_name in [(monthly, "Monthly"), (quarterly, "Quarterly")]:
                        for (period_label, value_type), (value, fm_id, period_id, start_date) in freq_dict.items():
                            if value_type != "Actual" or value is None:
                                continue
                                
                            # Find same period in previous year
                            prev_year_start = date(start_date.year - 1, start_date.month, start_date.day)
                            cur.execute(
                                """
                                SELECT fm.value 
                                FROM financial_metrics fm
                                JOIN periods p ON fm.period_id = p.id
                                WHERE p.start_date = %s
                                AND fm.company_id = %s
                                AND fm.line_item_id = %s
                                AND fm.value_type = 'Actual'
                                """,
                                (prev_year_start, company_id, line_item_id)
                            )
                            prev_year_result = cur.fetchone()
                            
                            if prev_year_result:
                                prev_value = prev_year_result[0]
                                yoy_growth = calculate_percentage(value, prev_value)
                                
                                if yoy_growth is not None:
                                    cur.execute(
                                        """
                                        INSERT INTO derived_metrics (
                                            base_metric_id, calculation_type, company_id, period_id,
                                            calculated_value, unit, source_ids, calculation_note,
                                            corroboration_status, frequency, created_at, updated_at
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (base_metric_id, company_id, period_id, calculation_type) 
                                        DO UPDATE SET 
                                            calculated_value = EXCLUDED.calculated_value,
                                            updated_at = EXCLUDED.updated_at
                                        """,
                                        (
                                            fm_id, "YoY Growth", company_id, period_id,
                                            yoy_growth, "%", [fm_id],
                                            f"Year-over-year growth: {period_label} vs previous year",
                                            "Ok", freq_name, datetime.now(), datetime.now()
                                        )
                                    )

                # CALCULATION 4: Year-to-Date calculations
                for year in years:
                    ytd_total, ytd_labels = calculate_ytd(cur, company_id, year, line_item_id)
                    
                    if ytd_total is None:
                        continue
                    
                    # Create or get YTD period
                    ytd_label = f"YTD {year}"
                    ytd_period_id = get_or_create_period(
                        cur, ytd_label, "Yearly", 
                        date(year, 1, 1), date(year, 12, 31)
                    )
                    
                    # Calculate YTD vs previous year
                    prev_ytd_total, _ = calculate_ytd(cur, company_id, year - 1, line_item_id)
                    
                    if prev_ytd_total:
                        ytd_growth = calculate_percentage(ytd_total, prev_ytd_total)
                        
                        if ytd_growth is not None:
                            # Find a representative base_metric_id for this year
                            cur.execute(
                                """
                                SELECT fm.id FROM financial_metrics fm
                                JOIN periods p ON fm.period_id = p.id
                                WHERE fm.company_id = %s 
                                AND fm.line_item_id = %s
                                AND EXTRACT(YEAR FROM p.start_date) = %s
                                AND fm.value_type = 'Actual'
                                ORDER BY p.start_date DESC
                                LIMIT 1
                                """,
                                (company_id, line_item_id, year)
                            )
                            base_metric_result = cur.fetchone()
                            
                            if base_metric_result:
                                base_metric_id = base_metric_result[0]
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note,
                                        corroboration_status, frequency, created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (base_metric_id, company_id, period_id, calculation_type) 
                                    DO UPDATE SET 
                                        calculated_value = EXCLUDED.calculated_value,
                                        updated_at = EXCLUDED.updated_at
                                    """,
                                    (
                                        base_metric_id, "YTD Growth", company_id, ytd_period_id,
                                        ytd_growth, "%", [base_metric_id],
                                        f"Year-to-date growth for {year} vs {year-1}",
                                        "Ok", "Yearly", datetime.now(), datetime.now()
                                    )
                                )

            conn.commit()
            
            # Log completion
            cur.execute(
                "SELECT COUNT(*) FROM derived_metrics WHERE company_id = %s",
                (company_id,)
            )
            derived_count = cur.fetchone()[0]
            
            log_event("calculations_completed", {
                "company_id": company_id,
                "processed_line_items": len(line_items),
                "derived_metrics_created": derived_count,
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"✅ Metrics calculation completed for company {company_id}")
            print(f"📊 Created {derived_count} derived metrics across {len(line_items)} line items")


if __name__ == "__main__":
    main()