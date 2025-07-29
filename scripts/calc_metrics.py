import psycopg2
import json
from datetime import datetime, date, timedelta
from utils import get_db_connection, log_event

def calculate_percentage(current, previous):
    if previous is None or previous == 0 or current is None:
        return None
    return ((current - previous) / previous) * 100

def check_corroboration(cur, company_id, period_id, line_item_id, monthly_values, quarterly_value):
    if not monthly_values or quarterly_value is None:
        return "Pending", "No monthly data for corroboration"
    monthly_sum = sum(val for val in monthly_values if val is not None)
    if abs(monthly_sum - (quarterly_value or 0)) > 0.01:
        return "Conflict", f"Monthly sum {monthly_sum} does not match quarterly {quarterly_value}"
    return "Ok", "Monthly and quarterly values corroborated"

def calculate_ytd(cur, company_id, year, line_item_id):
    cur.execute(
        """
        SELECT fm.period_id, fm.value FROM financial_metrics fm
        JOIN periods p ON fm.period_id = p.id
        WHERE fm.company_id = %s AND fm.frequency = 'Monthly' AND fm.line_item_id = %s
        AND EXTRACT(YEAR FROM p.start_date) = %s
        ORDER BY p.start_date
        """,
        (company_id, line_item_id, year)
    )
    months = cur.fetchall()
    if not months:
        return None, []
    ytd_sum = sum(val for _, val in months if val is not None)
    source_ids = [row[0] for row in months]
    return ytd_sum, source_ids

def main():
    if len(sys.argv) < 2:
        print("Usage: python calc_metrics.py <company_id>")
        return

    company_id = int(sys.argv[1])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM line_item_definitions WHERE name IN ('Revenue', 'Gross Profit', 'EBITDA')")
            line_items = cur.fetchall()

            # Process only the specified company
            for line_item_id, line_item_name in line_items:
                # Fetch all metrics for the company and line item with proper JOIN
                cur.execute(
                    """
                    SELECT fm.period_id, fm.value_type, fm.frequency, fm.value, 
                           EXTRACT(YEAR FROM p.start_date) AS year, p.start_date
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_id = p.id
                    WHERE fm.company_id = %s AND fm.line_item_id = %s
                    ORDER BY p.start_date
                    """,
                    (company_id, line_item_id)
                )
                metrics = cur.fetchall()

                # Organize by frequency and period
                monthly = {(row[0], row[1]): row[3] for row in metrics if row[2] == "Monthly"}
                quarterly = {(row[0], row[1]): row[3] for row in metrics if row[2] == "Quarterly"}
                years = set(row[4] for row in metrics if row[4])

                # Calculate MoM growth
                for period_id, value_type in monthly:
                    if value_type != "Actual":
                        continue

                    cur.execute("SELECT period_label, start_date FROM periods WHERE id = %s", (period_id,))
                    result = cur.fetchone()
                    if not result:
                        continue
                    period_label, start_date = result

                    # Find previous month
                    prev_month = start_date.replace(day=1) - timedelta(days=1)
                    prev_start = prev_month.replace(day=1)

                    cur.execute("SELECT id FROM periods WHERE start_date = %s AND period_type = 'Monthly'", (prev_start,))
                    prev_result = cur.fetchone()
                    prev_period_id = prev_result[0] if prev_result else None

                    if prev_period_id and (prev_period_id, "Actual") in monthly:
                        value = monthly.get((period_id, "Actual"))
                        prev_value = monthly.get((prev_period_id, "Actual"))
                        mom = calculate_percentage(value, prev_value)

                        if mom is not None:
                            # Check if this calculation already exists
                            cur.execute(
                                """
                                SELECT id FROM derived_metrics 
                                WHERE base_metric_id = %s AND calculation_type = %s AND company_id = %s AND period_id = %s
                                """,
                                (line_item_id, "MoM Growth", company_id, period_id)
                            )
                            if not cur.fetchone():
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, frequency, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                        created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        line_item_id, "MoM Growth", "Monthly", company_id, period_id,
                                        mom, "%", json.dumps([period_id, prev_period_id]), 
                                        "Month-over-month growth", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

                # Calculate QoQ growth
                for period_id, value_type in quarterly:
                    if value_type != "Actual":
                        continue

                    cur.execute("SELECT period_label, start_date FROM periods WHERE id = %s", (period_id,))
                    result = cur.fetchone()
                    if not result:
                        continue
                    period_label, start_date = result

                    # Find previous quarter (approximately 3 months back)
                    prev_quarter = start_date - timedelta(days=90)

                    cur.execute(
                        "SELECT id FROM periods WHERE period_type = 'Quarterly' AND start_date <= %s ORDER BY start_date DESC LIMIT 1", 
                        (prev_quarter,)
                    )
                    prev_result = cur.fetchone()
                    prev_period_id = prev_result[0] if prev_result else None

                    if prev_period_id and (prev_period_id, "Actual") in quarterly:
                        value = quarterly.get((period_id, "Actual"))
                        prev_value = quarterly.get((prev_period_id, "Actual"))
                        qoq = calculate_percentage(value, prev_value)

                        if qoq is not None:
                            # Check if this calculation already exists
                            cur.execute(
                                """
                                SELECT id FROM derived_metrics 
                                WHERE base_metric_id = %s AND calculation_type = %s AND company_id = %s AND period_id = %s
                                """,
                                (line_item_id, "QoQ Growth", company_id, period_id)
                            )
                            if not cur.fetchone():
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, frequency, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                        created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        line_item_id, "QoQ Growth", "Quarterly", company_id, period_id,
                                        qoq, "%", json.dumps([period_id, prev_period_id]), 
                                        "Quarter-over-quarter growth", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

                # Calculate YoY growth
                for year in years:
                    for period_id, value_type in [(p, v) for p, v in monthly.keys() if v == "Actual"] + [(p, v) for p, v in quarterly.keys() if v == "Actual"]:
                        cur.execute("SELECT start_date FROM periods WHERE id = %s", (period_id,))
                        result = cur.fetchone()
                        if not result:
                            continue
                        start_date = result[0]

                        # Find same period previous year
                        prev_year_start = date(start_date.year - 1, start_date.month, start_date.day)

                        cur.execute(
                            "SELECT id FROM periods WHERE start_date = %s",
                            (prev_year_start,)
                        )
                        prev_result = cur.fetchone()
                        prev_period_id = prev_result[0] if prev_result else None

                        if prev_period_id:
                            value = monthly.get((period_id, "Actual")) or quarterly.get((period_id, "Actual"))
                            prev_value = monthly.get((prev_period_id, "Actual")) or quarterly.get((prev_period_id, "Actual"))
                            yoy = calculate_percentage(value, prev_value)

                            if yoy is not None:
                                frequency = "Monthly" if (period_id, "Actual") in monthly else "Quarterly"
                                # Check if this calculation already exists
                                cur.execute(
                                    """
                                    SELECT id FROM derived_metrics 
                                    WHERE base_metric_id = %s AND calculation_type = %s AND company_id = %s AND period_id = %s
                                    """,
                                    (line_item_id, "YoY Growth", company_id, period_id)
                                )
                                if not cur.fetchone():
                                    cur.execute(
                                        """
                                        INSERT INTO derived_metrics (
                                            base_metric_id, calculation_type, frequency, company_id, period_id,
                                            calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                            created_at, updated_at
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            line_item_id, "YoY Growth", frequency, company_id, period_id,
                                            yoy, "%", json.dumps([period_id, prev_period_id]), 
                                            "Year-over-year growth", "Ok",
                                            datetime.now(), datetime.now()
                                        )
                                    )

                # Calculate YTD
                for year in years:
                    ytd_sum, source_ids = calculate_ytd(cur, company_id, year, line_item_id)
                    if ytd_sum is None:
                        log_event("ytd_skipped", {"reason": "No monthly data for YTD", "year": year, "line_item": line_item_name})
                        continue

                    # Create or find YTD period
                    cur.execute(
                        "SELECT id FROM periods WHERE period_type = 'Yearly' AND period_label = %s",
                        (f"YTD {year}",)
                    )
                    period = cur.fetchone()
                    if not period:
                        cur.execute(
                            "INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                            ("Yearly", f"YTD {year}", date(year, 1, 1), date(year, 12, 31), datetime.now(), datetime.now())
                        )
                        period_id = cur.fetchone()[0]
                    else:
                        period_id = period[0]

                    prev_ytd_sum, _ = calculate_ytd(cur, company_id, year - 1, line_item_id)
                    ytd_growth = calculate_percentage(ytd_sum, prev_ytd_sum) if prev_ytd_sum else None

                    if ytd_growth is not None:
                        # Check if this calculation already exists
                        cur.execute(
                            """
                            SELECT id FROM derived_metrics 
                            WHERE base_metric_id = %s AND calculation_type = %s AND company_id = %s AND period_id = %s
                            """,
                            (line_item_id, "YTD Growth", company_id, period_id)
                        )
                        if not cur.fetchone():
                            cur.execute(
                                """
                                INSERT INTO derived_metrics (
                                    base_metric_id, calculation_type, frequency, company_id, period_id,
                                    calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                    created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    line_item_id, "YTD Growth", "Yearly", company_id, period_id,
                                    ytd_growth, "%", json.dumps(source_ids), 
                                    "Year-to-date growth", "Ok",
                                    datetime.now(), datetime.now()
                                )
                            )

                # Calculate Variance vs Budget
                for period_id, value_type in [(p, v) for p, v in monthly.keys() if v == "Actual"] + [(p, v) for p, v in quarterly.keys() if v == "Actual"]:
                    if (period_id, "Budget") in monthly or (period_id, "Budget") in quarterly:
                        value = monthly.get((period_id, "Actual")) or quarterly.get((period_id, "Actual"))
                        budget = monthly.get((period_id, "Budget")) or quarterly.get((period_id, "Budget"))
                        variance = calculate_percentage(value, budget)

                        if variance is not None:
                            frequency = "Monthly" if (period_id, "Actual") in monthly else "Quarterly"
                            # Check if this calculation already exists
                            cur.execute(
                                """
                                SELECT id FROM derived_metrics 
                                WHERE base_metric_id = %s AND calculation_type = %s AND company_id = %s AND period_id = %s
                                """,
                                (line_item_id, "Variance vs Budget", company_id, period_id)
                            )
                            if not cur.fetchone():
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, frequency, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                        created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        line_item_id, "Variance vs Budget", frequency, company_id, period_id,
                                        variance, "%", json.dumps([period_id]), 
                                        "Variance vs budget", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

            conn.commit()
            log_event("calculations_completed", {"company_processed": company_id, "line_items_processed": len(line_items)})
            print(f"Metrics calculation completed for company {company_id}")

if __name__ == "__main__":
    import sys
    main()
