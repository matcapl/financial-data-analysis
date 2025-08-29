#!/usr/bin/env python3
"""
calc_metrics.py - YAML-driven derived metrics calculation engine (FIXED PATHS)

Features:
- Reads observation definitions from config/observations.yaml
- Uses DB foreign key lookups for periods and line items
- Handles YTD, MoM, QoQ, YoY growth and other observations configured in YAML
- Robust error handling and detailed logging
- Uses schema and config consistently (e.g., period_id, line_item_id)
- FIXED: Uses absolute paths from project root
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import yaml
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from pathlib import Path

# FIXED: Use absolute path resolution from project root
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'server' / 'scripts'))

from utils import get_db_connection, log_event

def load_observations():
    """Load observations from config/observations.yaml using absolute path"""
    obs_path = project_root / 'config' / 'observations.yaml'
    if not obs_path.exists():
        raise FileNotFoundError(f"observations.yaml not found at {obs_path}")
    with open(obs_path, 'r') as f:
        obs_config = yaml.safe_load(f)
    observations = obs_config.get('observations', [])
    log_event("observations_loaded", {
        "config_path": str(obs_path),
        "observations_count": len(observations)
    })
    return observations

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
    return float(res[0]) if res and res[0] is not None else None

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

    total_processed = 0
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Preload line items
            cur.execute("SELECT id, name FROM line_item_definitions")
            line_items_map = {row['name']: row['id'] for row in cur.fetchall()}
            if not line_items_map:
                raise Exception("No line items found. Ensure database seeded properly.")

            for obs in observations:
                calc_type = obs.get('calculation_type')
                period_type = obs.get('frequency') or "Monthly"
                materiality = obs.get('materiality') or 0.05

                for name, li_id in line_items_map.items():
                    try:
                        metrics = get_financial_metrics(cur, company_id, li_id)
                        if not metrics:
                            continue

                        # Index by (period_label, value_type)
                        index = {(m['period_label'], m['value_type']): m for m in metrics}
                        # Growth calculations
                        if calc_type in ["MoM Growth", "QoQ Growth", "YoY Growth"]:
                            for (pl, vt), rec in index.items():
                                if vt != "Actual" or rec['value'] is None:
                                    continue
                                prev_label = None
                                start_date = rec['start_date']
                                # Determine prev_label
                                if calc_type == "MoM Growth":
                                    prev_start = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)
                                    cur.execute(
                                        "SELECT period_label FROM periods WHERE start_date = %s AND period_type = 'Monthly'",
                                        (prev_start,)
                                    )
                                    r = cur.fetchone()
                                    prev_label = r['period_label'] if r else None
                                elif calc_type == "QoQ Growth":
                                    prev_start = start_date - timedelta(days=90)
                                    cur.execute(
                                        """
                                        SELECT period_label FROM periods
                                        WHERE period_type = 'Quarterly' AND start_date <= %s
                                        ORDER BY start_date DESC LIMIT 1
                                        """, (prev_start,)
                                    )
                                    r = cur.fetchone()
                                    prev_label = r['period_label'] if r else None
                                else:  # YoY Growth
                                    prev_start = date(start_date.year - 1, start_date.month, start_date.day)
                                    cur.execute(
                                        "SELECT period_label FROM periods WHERE start_date = %s AND period_type = %s",
                                        (prev_start, period_type)
                                    )
                                    r = cur.fetchone()
                                    prev_label = r['period_label'] if r else None

                                if not prev_label:
                                    continue
                                prev = index.get((prev_label, "Actual"))
                                if not prev or prev['value'] is None:
                                    continue

                                pct = calculate_percentage(rec['value'], prev['value'])
                                if pct is None or abs(pct) < materiality * 100:
                                    continue
                                insert_or_update_derived_metric(
                                    cur, rec['fm_id'], calc_type, company_id,
                                    rec['period_id'], pct, "%", [rec['fm_id']],
                                    f"{calc_type} for {pl} vs {prev_label}",
                                    "Ok", period_type
                                )
                                total_processed += 1

                        # YTD Growth
                        elif calc_type == "YTD Growth":
                            years = {m['year'] for m in metrics if m['year'] is not None}
                            for yr in years:
                                ytd = calculate_ytd(cur, company_id, int(yr), li_id)
                                prev_ytd = calculate_ytd(cur, company_id, int(yr) - 1, li_id)
                                if ytd is None or prev_ytd is None or prev_ytd == 0:
                                    continue
                                pct = calculate_percentage(ytd, prev_ytd)
                                if pct is None or abs(pct) < materiality * 100:
                                    continue
                                # YTD period id
                                ytd_label = f"YTD {yr}"
                                cur.execute(
                                    "SELECT id FROM periods WHERE period_label = %s AND period_type = 'Yearly'",
                                    (ytd_label,)
                                )
                                r = cur.fetchone()
                                ytd_id = r['id'] if r else None
                                if not ytd_id:
                                    # Create
                                    cur.execute(
                                        """
                                        INSERT INTO periods (period_label, period_type, start_date, end_date, created_at, updated_at)
                                        VALUES (%s, 'Yearly', %s, %s, NOW(), NOW()) RETURNING id
                                        """, (ytd_label, date(int(yr),1,1), date(int(yr),12,31))
                                    )
                                    ytd_id = cur.fetchone()['id']
                                # Base metric selection
                                cur.execute(
                                    """
                                    SELECT fm.id FROM financial_metrics fm
                                    JOIN periods p ON fm.period_id = p.id
                                    WHERE fm.company_id = %s AND fm.line_item_id = %s
                                      AND EXTRACT(YEAR FROM p.start_date) = %s
                                    ORDER BY p.start_date LIMIT 1
                                    """, (company_id, li_id, yr)
                                )
                                bm = cur.fetchone()
                                if not bm:
                                    continue
                                insert_or_update_derived_metric(
                                    cur, bm['id'], calc_type, company_id,
                                    ytd_id, pct, "%", [bm['id']],
                                    f"{calc_type} for year {yr} vs {yr-1}",
                                    "Ok", "Yearly"
                                )
                                total_processed += 1

                    except Exception as e:
                        log_event("calc_metrics_error", {
                            "company_id": company_id,
                            "line_item": name,
                            "error": str(e),
                            "observation": obs.get('id')
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
