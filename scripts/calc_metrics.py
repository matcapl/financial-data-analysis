import psycopg2
import json
from datetime import datetime, date
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
        SELECT period_id, value FROM financial_metrics
        WHERE company_id = %s AND frequency = 'Monthly' AND line_item_id = %s
        AND EXTRACT(YEAR FROM start_date) = %s
        ORDER BY start_date
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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM line_item_definitions WHERE name IN ('Revenue', 'Gross Profit', 'EBITDA')")
            line_items = cur.fetchall()
            cur.execute("SELECT DISTINCT company_id FROM financial_metrics")
            companies = cur.fetchall()

            for company_id, in companies:
                for line_item_id, line_item_name in line_items:
                    # Fetch all metrics for the company and line item
                    cur.execute(
                        """
                        SELECT period_id, value_type, frequency, value, EXTRACT(YEAR FROM start_date) AS year
                        FROM financial_metrics
                        WHERE company_id = %s AND line_item_id = %s
                        ORDER BY start_date
                        """,
                        (company_id, line_item_id)
                    )
                    metrics = cur.fetchall()

                    # Organize by frequency and period
                    monthly = {(row[0], row[1]): row[3] for row in metrics if row[2] == "Monthly"}
                    quarterly = {(row[0], row[1]): row[3] for row in metrics if row[2] == "Quarterly"}
                    years = set(row[4] for row in metrics)

                    # Calculate MoM and QoQ
                    for period_id, value_type in monthly:
                        if value_type != "Actual":
                            continue
                        cur.execute("SELECT period_label, start_date FROM periods WHERE id = %s", (period_id,))
                        period_label, start_date = cur.fetchone()
                        prev_period_id = None
                        if start_date.month > 1:
                            prev_start = date(start_date.year, start_date.month - 1, 1)
                            cur.execute("SELECT id FROM periods WHERE start_date = %s AND period_type = 'Monthly'", (prev_start,))
                            prev_period_id = cur.fetchone()[0] if cur.fetchone() else None
                        if prev_period_id and (prev_period_id, "Actual") in monthly:
                            value = monthly.get((period_id, "Actual"))
                            prev_value = monthly.get((prev_period_id, "Actual"))
                            mom = calculate_percentage(value, prev_value)
                            if mom is not None:
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
                                        mom, "%", json.dumps([period_id, prev_period_id]), "Month-over-month growth", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

                    for period_id, value_type in quarterly:
                        if value_type != "Actual":
                            continue
                        cur.execute("SELECT period_label, start_date FROM periods WHERE id = %s", (period_id,))
                        period_label, start_date = cur.fetchone()
                        prev_period_id = None
                        if start_date.month > 3:
                            prev_start = date(start_date.year, start_date.month - 3, 1)
                            cur.execute("SELECT id FROM periods WHERE start_date = %s AND period_type = 'Quarterly'", (prev_start,))
                            prev_period_id = cur.fetchone()[0] if cur.fetchone() else None
                        if prev_period_id and (prev_period_id, "Actual") in quarterly:
                            value = quarterly.get((period_id, "Actual"))
                            prev_value = quarterly.get((prev_period_id, "Actual"))
                            qoq = calculate_percentage(value, prev_value)
                            if qoq is not None:
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
                                        qoq, "%", json.dumps([period_id, prev_period_id]), "Quarter-over-quarter growth", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

                        # Corroboration check
                        cur.execute(
                            "SELECT value FROM financial_metrics WHERE company_id = %s AND line_item_id = %s AND period_id = %s AND value_type = 'Actual'",
                            (company_id, line_item_id, period_id)
                        )
                        quarterly_value = cur.fetchone()[0] if cur.fetchone() else None
                        cur.execute(
                            """
                            SELECT value FROM financial_metrics fm
                            JOIN periods p ON fm.period_id = p.id
                            WHERE fm.company_id = %s AND fm.line_item_id = %s AND fm.frequency = 'Monthly'
                            AND p.start_date >= %s AND p.end_date <= %s AND fm.value_type = 'Actual'
                            """,
                            (company_id, line_item_id, start_date, start_date + pd.Timedelta(days=90))
                        )
                        monthly_values = [row[0] for row in cur.fetchall()]
                        status, note = check_corroboration(cur, company_id, period_id, line_item_id, monthly_values, quarterly_value)
                        cur.execute(
                            """
                            UPDATE financial_metrics SET corroboration_status = %s, notes = %s
                            WHERE company_id = %s AND period_id = %s AND line_item_id = %s AND value_type = 'Actual'
                            """,
                            (status, note, company_id, period_id, line_item_id)
                        )

                    # Calculate YoY
                    for year in years:
                        for period_id, value_type in [(p, v) for p, v in metrics if v == "Actual"]:
                            cur.execute("SELECT start_date FROM periods WHERE id = %s", (period_id,))
                            start_date = cur.fetchone()[0]
                            prev_year_start = date(start_date.year - 1, start_date.month, 1)
                            cur.execute(
                                "SELECT id FROM periods WHERE start_date = %s AND period_type = %s",
                                (prev_year_start, monthly.get((period_id, "Actual")) and "Monthly" or "Quarterly")
                            )
                            prev_period_id = cur.fetchone()[0] if cur.fetchone() else None
                            if prev_period_id:
                                value = monthly.get((period_id, "Actual")) or quarterly.get((period_id, "Actual"))
                                prev_value = monthly.get((prev_period_id, "Actual")) or quarterly.get((prev_period_id, "Actual"))
                                yoy = calculate_percentage(value, prev_value)
                                if yoy is not None:
                                    cur.execute(
                                        """
                                        INSERT INTO derived_metrics (
                                            base_metric_id, calculation_type, frequency, company_id, period_id,
                                            calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                            created_at, updated_at
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            line_item_id, "YoY Growth", monthly.get((period_id, "Actual")) and "Monthly" or "Quarterly",
                                            company_id, period_id, yoy, "%", json.dumps([period_id, prev_period_id]), "Year-over-year growth", "Ok",
                                            datetime.now(), datetime.now()
                                        )
                                    )

                    # Calculate YTD
                    for year in years:
                        ytd_sum, source_ids = calculate_ytd(cur, company_id, year, line_item_id)
                        if ytd_sum is None:
                            log_event("ytd_skipped", {"reason": "No monthly data for YTD", "year": year, "line_item": line_item_name})
                            continue
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
                                    ytd_growth, "%", json.dumps(source_ids), "Year-to-date growth", "Ok",
                                    datetime.now(), datetime.now()
                                )
                            )

                    # Calculate Variance vs Budget
                    for period_id, value_type in [(p, v) for p, v in metrics if v == "Actual"]:
                        if (period_id, "Budget") in monthly or (period_id, "Budget") in quarterly:
                            value = monthly.get((period_id, "Actual")) or quarterly.get((period_id, "Actual"))
                            budget = monthly.get((period_id, "Budget")) or quarterly.get((period_id, "Budget"))
                            variance = calculate_percentage(value, budget)
                            if variance is not None:
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                        base_metric_id, calculation_type, frequency, company_id, period_id,
                                        calculated_value, unit, source_ids, calculation_note, corroboration_status,
                                        created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        line_item_id, "Variance vs Budget", monthly.get((period_id, "Actual")) and "Monthly" or "Quarterly",
                                        company_id, period_id, variance, "%", json.dumps([period_id]), "Variance vs budget", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )
            conn.commit()
            log_event("calculations_completed", {"companies_processed": len(companies), "line_items_processed": len(line_items)})

if __name__ == "__main__":
    main()