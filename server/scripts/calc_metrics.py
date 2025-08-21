#!/usr/bin/env python3
"""
calc_metrics.py - YAML-driven derived metrics calculation engine

Features:
- Reads observation definitions from config/observations.yaml
- Uses DB foreign key lookups for periods and line items
- Handles YTD, MoM, QoQ, YoY growth and other observations configured in YAML
- Robust error handling and detailed logging
- Uses schema and config consistently (e.g., period_id, line_item_id)
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import yaml
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from utils import get_db_connection, log_event


def load_observations():
    obs_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'observations.yaml')
    with open(obs_path, 'r') as f:
        obs_config = yaml.safe_load(f)
    return obs_config.get('observations', [])


def calculate_percentage(current, previous):
    if previous is None or previous == 0 or current is None:
        return None
    try:
        return float((current - previous) / previous * 100)
    except Exception:
        return None


def get_period_id(cur, period_label, period_type):
    cur.execute(
        "SELECT id FROM periods WHERE period_label = %s AND period_type = %s",
        (period_label, period_type)
    )
    res = cur.fetchone()
    return res[0] if res else None


def get_line_item_id(cur, line_item_name):
    cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (line_item_name,))
    res = cur.fetchone()
    return res if res else None


def get_financial_metrics(cur, company_id, line_item_id):
    cur.execute(
        """
        SELECT p.period_label, p.id AS period_id, fm.value_type, fm.frequency,
               fm.value, EXTRACT(YEAR FROM p.start_date) AS year, p.start_date, fm.id AS fm_id
        FROM financial_metrics fm
        JOIN periods p ON fm.period_id = p.id
        WHERE fm.company_id = %s AND fm.line_item_id = %s
        ORDER BY p.start_date
        """, (company_id, line_item_id)
    )
    return cur.fetchall()


def calculate_ytd(cur, company_id, year, line_item_id):
    cur.execute(
        """
        SELECT SUM(fm.value) AS total_value
        FROM financial_metrics fm
        JOIN periods p ON fm.period_id = p.id
        WHERE fm.company_id = %s AND fm.line_item_id = %s AND fm.value_type = 'Actual'
        AND p.period_type = 'Monthly'
        AND EXTRACT(YEAR FROM p.start_date) = %s
        """,
        (company_id, line_item_id, year)
    )
    res = cur.fetchone()
    return float(res[0]) if res and res is not None else None


def insert_or_update_derived_metric(cur, base_metric_id, calculation_type, company_id, period_id,
                                    calculated_value, unit, source_ids, calculation_note,
                                    corroboration_status, frequency):
    cur.execute(
        """
        INSERT INTO derived_metrics (
            base_metric_id, calculation_type, company_id, period_id,
            calculated_value, unit, source_ids, calculation_note,
            corroboration_status, frequency, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (base_metric_id, company_id, period_id, calculation_type) DO UPDATE SET
            calculated_value = EXCLUDED.calculated_value,
            updated_at = EXCLUDED.updated_at
        """,
        (
            base_metric_id, calculation_type, company_id, period_id,
            calculated_value, unit, source_ids, calculation_note,
            corroboration_status, frequency
        )
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python calc_metrics.py <company_id>")
        sys.exit(1)

    company_id = int(sys.argv[1])
    log_event("calc_metrics_started", {"company_id": company_id, "timestamp": datetime.now().isoformat()})

    observations = load_observations()
    if not observations:
        log_event("calc_metrics_no_observations", {"message": "No observations loaded from YAML"})
        print("No observations defined. Exiting.")
        return

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Preload all line items from the line_item_definitions table
            cur.execute("SELECT id, name FROM line_item_definitions")
            line_items_map = {row['name']: row['id'] for row in cur.fetchall()}

            if not line_items_map:
                raise Exception("No line items found. Ensure database seeded properly.")

            total_processed = 0

            for obs in observations:
                calc_type = obs.get('calculation_type')
                obs_id = obs.get('id')
                period_type = obs.get('frequency') or "Monthly"
                sql_query = obs.get('sql_query')
                materiality = obs.get('materiality') or 0.05

                for line_item_name, line_item_id in line_items_map.items():
                    try:
                        # Fetch financial metrics for this company and line item
                        metrics = get_financial_metrics(cur, company_id, line_item_id)
                        if not metrics:
                            continue

                        # Index metrics by period_label and value_type for lookups
                        metrics_index = {}
                        for m in metrics:
                            key = (m['period_label'], m['value_type'])
                            metrics_index[key] = m

                        # Now calculate derived metrics based on observation ID/calculation type
                        # Use generalized approach for commonly defined growth calculations
                        if calc_type in ["MoM Growth", "QoQ Growth", "YoY Growth"]:
                            for (period_label, value_type), record in metrics_index.items():
                                if value_type != "Actual" or record['value'] is None:
                                    continue
                                base_val = record['value']
                                base_metric_id = record['fm_id']
                                period_id = record['period_id']
                                start_date = record['start_date']

                                # Determine previous period label per calculation type
                                prev_period_label = None
                                if calc_type == "MoM Growth" and period_type == "Monthly":
                                    prev_month_start = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)
                                    cur.execute(
                                        "SELECT period_label FROM periods WHERE start_date = %s AND period_type = 'Monthly'",
                                        (prev_month_start,)
                                    )
                                    prev = cur.fetchone()
                                    prev_period_label = prev['period_label'] if prev else None

                                elif calc_type == "QoQ Growth" and period_type == "Quarterly":
                                    prev_quarter_start = start_date - timedelta(days=90)
                                    cur.execute(
                                        """
                                        SELECT p.period_label 
                                        FROM periods p
                                        WHERE p.period_type = 'Quarterly' 
                                        AND p.start_date <= %s
                                        ORDER BY p.start_date DESC LIMIT 1
                                        """,
                                        (prev_quarter_start,)
                                    )
                                    prev = cur.fetchone()
                                    prev_period_label = prev['period_label'] if prev else None

                                elif calc_type == "YoY Growth":
                                    prev_year_start = date(start_date.year - 1, start_date.month, start_date.day)
                                    cur.execute(
                                        "SELECT period_label FROM periods WHERE start_date = %s AND period_type = %s",
                                        (prev_year_start, period_type)
                                    )
                                    prev = cur.fetchone()
                                    prev_period_label = prev['period_label'] if prev else None

                                if not prev_period_label:
                                    continue
                                prev_record = metrics_index.get((prev_period_label, "Actual"))
                                if not prev_record or prev_record['value'] is None:
                                    continue

                                prev_val = prev_record['value']
                                pct_change = calculate_percentage(base_val, prev_val)
                                if pct_change is None or abs(pct_change) < materiality * 100:
                                    continue

                                insert_or_update_derived_metric(
                                    cur,
                                    base_metric_id,
                                    calc_type,
                                    company_id,
                                    period_id,
                                    pct_change,
                                    "%",
                                    [base_metric_id],
                                    f"{calc_type} for {period_label} vs {prev_period_label}",
                                    "Ok",
                                    period_type
                                )
                                total_processed += 1

                        # Handle YTD separately
                        elif calc_type == "YTD Growth":
                            years = set(m['year'] for m in metrics if m['year'] is not None)
                            for year in years:
                                ytd_total = calculate_ytd(cur, company_id, int(year), line_item_id)
                                prev_ytd_total = calculate_ytd(cur, company_id, int(year) - 1, line_item_id)
                                if ytd_total is None or prev_ytd_total is None or prev_ytd_total == 0:
                                    continue

                                pct_change = calculate_percentage(ytd_total, prev_ytd_total)
                                if pct_change is None or abs(pct_change) < materiality * 100:
                                    continue

                                # Create/get YTD period_id
                                ytd_label = f"YTD {year}"
                                ytd_period_id = get_period_id(cur, ytd_label, "Yearly")
                                if not ytd_period_id:
                                    ytd_period_id = get_or_create_period(cur, ytd_label, "Yearly",
                                                                        date(year, 1, 1), date(year, 12, 31))

                                # Use any base_metric_id from given year as representative
                                cur.execute(
                                    """
                                    SELECT fm.id FROM financial_metrics fm
                                    JOIN periods p ON fm.period_id = p.id
                                    WHERE fm.company_id = %s AND fm.line_item_id = %s 
                                    AND EXTRACT(YEAR FROM p.start_date) = %s
                                    ORDER BY p.start_date LIMIT 1
                                    """,
                                    (company_id, line_item_id, year)
                                )
                                base_metric_res = cur.fetchone()
                                base_metric_id = base_metric_res['id'] if base_metric_res else None
                                if not base_metric_id:
                                    continue

                                insert_or_update_derived_metric(
                                    cur,
                                    base_metric_id,
                                    calc_type,
                                    company_id,
                                    ytd_period_id,
                                    pct_change,
                                    "%",
                                    [base_metric_id],
                                    f"{calc_type} for year {year} vs {int(year)-1}",
                                    "Ok",
                                    "Yearly"
                                )
                                total_processed += 1

                        else:
                            # For other calculations, you can add logic here as per YAML config
                            pass

                    except Exception as exc:
                        log_event("calc_metrics_error", {
                            "company_id": company_id,
                            "line_item": line_item_name,
                            "error": str(exc),
                            "observation_id": obs_id
                        })
                        continue

            conn.commit()

            log_event("calc_metrics_completed", {
                "company_id": company_id,
                "total_derived_metrics": total_processed,
                "timestamp": datetime.now().isoformat()
            })
            print(f"✅ Calculated {total_processed} derived metrics for company_id={company_id}")

if __name__ == "__main__":
    main()
