# server/scripts/utils.py

import psycopg2
import json
from datetime import datetime, date
import os
from dotenv import load_dotenv
import hashlib
import re

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using DATABASE_URL"""
    try:
        return psycopg2.connect(os.environ["DATABASE_URL"])
    except psycopg2.Error as e:
        log_event('database_error', {'error': str(e)})
        raise

def log_event(event_type, data):
    """Log events to JSON file, serializing unknown types as strings"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data': data
    }

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Append to events.json
    with open('logs/events.json', 'a') as f:
        f.write(json.dumps(log_entry, default=str) + '\n')

def clean_numeric_value(value_str):
    """Clean and convert string to numeric value"""
    if value_str is None or str(value_str).strip() == '':
        return None

    cleaned = str(value_str).replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()

    # Handle parentheses as negative
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]

    try:
        return int(cleaned) if '.' not in cleaned else float(cleaned)
    except (ValueError, TypeError):
        return None

def parse_period(period_str, period_type=None):
    """
    Enhanced period parsing with better date handling
    """
    if not period_str:
        return None

    period_str = str(period_str).strip()

    if not period_type:
        period_type = 'Quarterly' if 'Q' in period_str.upper() else 'Monthly'

    # Year-to-date
    if 'YTD' in period_str.upper():
        year_match = re.search(r'20\d{2}', period_str)
        year = int(year_match.group()) if year_match else datetime.now().year
        return {
            'type': 'Yearly',
            'label': f'YTD {year}',
            'start_date': date(year, 1, 1),
            'end_date': date(year, 12, 31)
        }

    # Quarter
    quarter_match = re.search(r'Q(\d)', period_str, re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year_match = re.search(r'20\d{2}', period_str)
        year = int(year_match.group()) if year_match else datetime.now().year

        starts = {1:(1,1),2:(4,1),3:(7,1),4:(10,1)}
        ends   = {1:(3,31),2:(6,30),3:(9,30),4:(12,31)}
        sm, sd = starts[quarter]
        em, ed = ends[quarter]
        return {
            'type': 'Quarterly',
            'label': f'Q{quarter} {year}',
            'start_date': date(year, sm, sd),
            'end_date': date(year, em, ed)
        }

    # Month
    month_map = {
        'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,
        'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12
    }
    upper = period_str.upper()
    for name, mnum in month_map.items():
        if name in upper:
            year_match = re.search(r'20\d{2}', period_str)
            year = int(year_match.group()) if year_match else datetime.now().year
            if mnum == 2:
                ld = 29 if (year%4==0 and (year%100!=0 or year%400==0)) else 28
            elif mnum in (4,6,9,11):
                ld = 30
            else:
                ld = 31
            return {
                'type': 'Monthly',
                'label': period_str,
                'start_date': date(year, mnum, 1),
                'end_date': date(year, mnum, ld)
            }

    # Default fallback
    return {
        'type': period_type or 'Monthly',
        'label': period_str,
        'start_date': datetime.now().date(),
        'end_date': datetime.now().date()
    }

def hash_datapoint(company_id, period_id, line_item, value_type, frequency, value):
    """
    Compute a stable SHA256 hash for a data point, omitting timestamps to avoid duplicate skipping.
    """
    key = f"{company_id}|{period_id}|{line_item}|{value_type}|{frequency}|{value}"
    return hashlib.sha256(key.encode('utf-8')).hexdigest()
