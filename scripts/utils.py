import hashlib
import json
import os
import psycopg2
import pandas as pd
from datetime import datetime, date
from typing import Dict, Any, Optional

def hash_datapoint(company_id: int, period_id: int, line_item: str, value_type: str, frequency: str) -> str:
    key = f"{company_id}-{period_id}-{line_item}-{value_type}-{frequency}"
    return hashlib.sha256(key.encode()).hexdigest()

def log_event(event_type: str, details: Dict[str, Any], log_file_path: str = None) -> None:
    timestamp = datetime.now().isoformat()
    log_entry = {"timestamp": timestamp, "event_type": event_type, "details": details}
    print(f"[{timestamp}] {event_type}: {details}")
    if not log_file_path:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = f"{log_dir}/system_log_{datetime.now().strftime('%Y%m%d')}.json"
    try:
        logs = json.load(open(log_file_path, "r")) if os.path.exists(log_file_path) else []
        logs.append(log_entry)
        with open(log_file_path, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Warning: Log write failed: {e}")

def get_db_connection() -> psycopg2.extensions.connection:
    conn_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "finance"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "yourpass"),
        "port": os.getenv("DB_PORT", 5432)
    }
    try:
        return psycopg2.connect(**conn_params)
    except psycopg2.Error as e:
        log_event("database_error", {"error": str(e)})
        raise

def clean_numeric_value(value: Any) -> Optional[float]:
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").replace("(", "-").replace(")", "").strip()
        if not cleaned or cleaned in ["-", "—", "N/A", "n/a", "#N/A"]:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None

def parse_period(period_label: str, period_type: str) -> Dict[str, Any]:
    period_str = str(period_label).strip().lower()
    try:
        if period_type == "Monthly":
            parsed = pd.to_datetime(period_str, errors="coerce")
            if pd.notna(parsed):
                year, month = parsed.year, parsed.month
            else:
                for i, month_name in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                    if month_name in period_str:
                        month = i + 1
                        year = int(period_str[-4:]) if period_str[-4:].isdigit() else 2025
                        break
                else:
                    month, year = 1, 2025
            start_date = date(year, month, 1)
            end_date = date(year, month + 1, 1) - pd.Timedelta(days=1) if month < 12 else date(year, 12, 31)
            return {"label": f"{year}-{month:02d}", "type": "Monthly", "start_date": start_date, "end_date": end_date}
        elif period_type == "Quarterly":
            if "q" in period_str:
                quarter = int(period_str[period_str.index("q") + 1])
                year = int(period_str[-4:]) if period_str[-4:].isdigit() else 2025
            else:
                quarter, year = 1, 2025
            start_month = (quarter - 1) * 3 + 1
            start_date = date(year, start_month, 1)
            end_month = start_month + 2
            end_date = date(year, end_month + 1, 1) - pd.Timedelta(days=1) if end_month < 12 else date(year, 12, 31)
            return {"label": f"Q{quarter} {year}", "type": "Quarterly", "start_date": start_date, "end_date": end_date}
        elif period_type == "Yearly":
            year = int(period_str[-4:]) if period_str[-4:].isdigit() else 2025
            return {"label": f"YTD {year}", "type": "Yearly", "start_date": date(year, 1, 1), "end_date": date(year, 12, 31)}
    except Exception as e:
        log_event("period_parse_error", {"period_label": period_label, "error": str(e)})
        return {"label": period_str, "type": period_type, "start_date": date(2025, 1, 1), "end_date": date(2025, 12, 31)}