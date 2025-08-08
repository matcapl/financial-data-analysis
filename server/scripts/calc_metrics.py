import psycopg2
import json
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from utils import get_db_connection, log_event


def calculate_percentage(current, previous):
    if previous is None or previous == 0 or current is None:
        return None
    return ((current - previous) / previous) * 100


def calculate_ytd(cur, company_id, year, line_item_name):
    cur.execute(
        """
        SELECT fm.period_label, fm.value
        FROM financial_metrics fm
        JOIN periods p ON fm.period_label = p.period_label
        WHERE fm.company_id = %s
          AND fm.frequency = 'Monthly'
          AND fm.line_item = %s
          AND EXTRACT(YEAR FROM p.start_date) = %s
        ORDER BY p.start_date
        """,
        (company_id, line_item_name, year)
    )
    rows = cur.fetchall()
    if not rows:
        return None, []
    total = sum(val for _, val in rows if val is not None)
    labels = [label for label, _ in rows]
    return total, labels


def main():
    if len(sys.argv) < 2:
        print("Usage: python calc_metrics.py <company_id>")
        sys.exit(1)

    company_id = sys.argv[1]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Load seeded line items
            cur.execute("""
                SELECT id, name
                FROM line_item_definitions
                WHERE name IN ('Revenue', 'Gross Profit', 'EBITDA')
            """)
            line_items = cur.fetchall()

            for line_item_id, line_item_name in line_items:
                # Fetch all metrics for this company + line item
                cur.execute(
                    """
                    SELECT
                        fm.period_label,
                        fm.value_type,
                        fm.frequency,
                        fm.value,
                        EXTRACT(YEAR FROM p.start_date) AS year,
                        p.start_date
                    FROM financial_metrics fm
                    JOIN periods p ON fm.period_label = p.period_label
                    WHERE fm.company_id = %s
                      AND fm.line_item = %s
                    ORDER BY p.start_date
                    """,
                    (company_id, line_item_name)
                )
                metrics = cur.fetchall()

                # Organize by frequency
                monthly = {
                    (row[0], row[1]): row[3]
                    for row in metrics if row[2] == "Monthly"
                }
                quarterly = {
                    (row[0], row[1]): row[3]
                    for row in metrics if row[2] == "Quarterly"
                }
                years = {int(row[4]) for row in metrics if row[4] is not None}

                # Month-over-Month growth
                for (label, vt), val in monthly.items():
                    if vt != "Actual":
                        continue
                    cur.execute(
                        "SELECT start_date FROM periods WHERE period_label = %s",
                        (label,)
                    )
                    res = cur.fetchone()
                    if not res:
                        continue
                    sd = res[0]
                    prev_sd = (sd.replace(day=1) - timedelta(days=1)).replace(day=1)
                    cur.execute(
                        "SELECT period_label FROM periods WHERE start_date = %s AND period_type = 'Monthly'",
                        (prev_sd,)
                    )
                    pr = cur.fetchone()
                    if not pr:
                        continue
                    prev_label = pr[0]
                    if (prev_label, "Actual") in monthly:
                        prev_val = monthly[(prev_label, "Actual")]
                        mom = calculate_percentage(val, prev_val)
                        if mom is not None:
                            cur.execute(
                                """
                                INSERT INTO derived_metrics (
                                  base_metric_id, calculation_type, frequency,
                                  company_id, period_label,
                                  calculated_value, unit, source_ids,
                                  calculation_note, corroboration_status,
                                  created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    line_item_id, "MoM Growth", "Monthly",
                                    company_id, label,
                                    mom, "%", json.dumps([label, prev_label]),
                                    "Month-over-month growth", "Ok",
                                    datetime.now(), datetime.now()
                                )
                            )

                # Quarter-over-Quarter growth
                for (label, vt), val in quarterly.items():
                    if vt != "Actual":
                        continue
                    cur.execute(
                        "SELECT start_date FROM periods WHERE period_label = %s",
                        (label,)
                    )
                    res = cur.fetchone()
                    if not res:
                        continue
                    sd = res[0]
                    prev_date = sd - timedelta(days=90)
                    cur.execute(
                        """
                        SELECT period_label FROM periods
                        WHERE period_type = 'Quarterly'
                          AND start_date <= %s
                        ORDER BY start_date DESC
                        LIMIT 1
                        """,
                        (prev_date,)
                    )
                    pr = cur.fetchone()
                    if not pr:
                        continue
                    prev_label = pr[0]
                    if (prev_label, "Actual") in quarterly:
                        prev_val = quarterly[(prev_label, "Actual")]
                        qoq = calculate_percentage(val, prev_val)
                        if qoq is not None:
                            cur.execute(
                                """
                                INSERT INTO derived_metrics (
                                  base_metric_id, calculation_type, frequency,
                                  company_id, period_label,
                                  calculated_value, unit, source_ids,
                                  calculation_note, corroboration_status,
                                  created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    line_item_id, "QoQ Growth", "Quarterly",
                                    company_id, label,
                                    qoq, "%", json.dumps([label, prev_label]),
                                    "Quarter-over-quarter growth", "Ok",
                                    datetime.now(), datetime.now()
                                )
                            )

                # Year-over-Year growth
                for year in years:
                    for freq_dict in (monthly, quarterly):
                        for (label, vt), val in freq_dict.items():
                            if vt != "Actual":
                                continue
                            cur.execute(
                                "SELECT start_date FROM periods WHERE period_label = %s",
                                (label,)
                            )
                            res = cur.fetchone()
                            if not res:
                                continue
                            sd = res[0]
                            prev_start = date(sd.year - 1, sd.month, sd.day)
                            cur.execute(
                                "SELECT period_label FROM periods WHERE start_date = %s",
                                (prev_start,)
                            )
                            pr = cur.fetchone()
                            if not pr:
                                continue
                            prev_label = pr[0]
                            prev_val = freq_dict.get((prev_label, "Actual"))
                            if prev_val is None:
                                continue
                            yoy = calculate_percentage(val, prev_val)
                            if yoy is not None:
                                freq = "Monthly" if freq_dict is monthly else "Quarterly"
                                cur.execute(
                                    """
                                    INSERT INTO derived_metrics (
                                      base_metric_id, calculation_type, frequency,
                                      company_id, period_label,
                                      calculated_value, unit, source_ids,
                                      calculation_note, corroboration_status,
                                      created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                    """,
                                    (
                                        line_item_id, "YoY Growth", freq,
                                        company_id, label,
                                        yoy, "%", json.dumps([label, prev_label]),
                                        "Year-over-year growth", "Ok",
                                        datetime.now(), datetime.now()
                                    )
                                )

                # Year-to-Date growth
                for year in years:
                    total, labels = calculate_ytd(cur, company_id, year, line_item_name)
                    if total is None:
                        continue
                    ytd_label = f"YTD {year}"
                    cur.execute(
                        "SELECT 1 FROM periods WHERE period_label = %s",
                        (ytd_label,)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            """
                            INSERT INTO periods (
                              period_type, period_label,
                              start_date, end_date,
                              created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            ("Yearly", ytd_label, date(year,1,1), date(year,12,31), datetime.now(), datetime.now())
                        )
                    prev_total, _ = calculate_ytd(cur, company_id, year-1, line_item_name)
                    if prev_total:
                        growth = calculate_percentage(total, prev_total)
                        if growth is not None:
                            cur.execute(
                                """
                                INSERT INTO derived_metrics (
                                  base_metric_id, calculation_type, frequency,
                                  company_id, period_label,
                                  calculated_value, unit, source_ids,
                                  calculation_note, corroboration_status,
                                  created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    line_item_id, "YTD Growth", "Yearly",
                                    company_id, ytd_label,
                                    growth, "%", json.dumps(labels),
                                    "Year-to-date growth", "Ok",
                                    datetime.now(), datetime.now()
                                )
                            )

            conn.commit()
            log_event("calculations_completed", {
                "company_id": company_id,
                "processed_line_items": len(line_items)
            })
            print(f"Metrics calculation completed for company {company_id}")


if __name__ == "__main__":
    main()
