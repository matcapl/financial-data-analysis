import psycopg2
import json
from datetime import datetime, date
import os
from dotenv import load_dotenv
import hashlib
import re
import yaml
import pandas as pd

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

def load_yaml_config(file_path):
    """Load and return a YAML configuration file."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log_event('yaml_load_error', {'file': file_path, 'error': str(e)})
        raise ValueError(f"Failed to load YAML config {file_path}: {e}")

def load_fields_config():
    """Load fields configuration from fields.yaml."""
    return load_yaml_config('config/fields.yaml')

def get_field_synonyms():
    """Get field synonyms from fields.yaml."""
    config = load_fields_config()
    synonyms = {}
    for field_name, field_data in config['fields'].items():
        synonyms[field_name] = field_data['synonyms']
    return synonyms

def get_line_item_aliases():
    """Get line item aliases from fields.yaml."""
    config = load_fields_config()
    aliases = {}
    for item in config['line_items']:
        name = item['name']
        for alias in item['aliases']:
            aliases[alias.lower()] = name
        aliases[name.lower()] = name
    return aliases

def parse_period(period_str, period_type=None):
    """
    FIXED: Enhanced period parsing using fields.yaml instead of missing periods.yaml.
    Fallback handling when YAML config sections are missing.
    """
    if not period_str or (isinstance(period_str, float) and pd.isna(period_str)):
        return None

    period_str = str(period_str).strip()

    # FIXED: Load from fields.yaml instead of missing periods.yaml
    try:
        fields_config = load_yaml_config('config/fields.yaml')
        date_formats = fields_config.get('date_formats', [])
        period_types = fields_config.get('period_types', ['Monthly', 'Quarterly', 'Yearly'])
        auto_create_config = fields_config.get('auto_create_periods', {})
    except Exception as e:
        # Fallback configuration if fields.yaml is missing or malformed
        log_event('config_fallback', {'error': str(e), 'message': 'Using fallback period config'})
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%b %Y", "%B %Y", "Q%s %Y"]
        period_types = ['Monthly', 'Quarterly', 'Yearly']
        auto_create_config = {'enabled': True, 'default_type': 'Monthly'}

    # Auto-detect period type if not provided
    if not period_type:
        period_type = 'Quarterly' if 'Q' in period_str.upper() else 'Monthly'

    # Year-to-date parsing
    if 'YTD' in period_str.upper():
        year_match = re.search(r'20\d{2}', period_str)
        year = int(year_match.group()) if year_match else datetime.now().year
        return {
            'type': 'Yearly',
            'label': f'YTD {year}',
            'start_date': date(year, 1, 1),
            'end_date': date(year, 12, 31)
        }

    # Quarter parsing
    quarter_match = re.search(r'Q(\d)', period_str, re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year_match = re.search(r'20\d{2}', period_str)
        year = int(year_match.group()) if year_match else datetime.now().year

        starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

        sm, sd = starts[quarter]
        em, ed = ends[quarter]

        return {
            'type': 'Quarterly',
            'label': f'Q{quarter} {year}',
            'start_date': date(year, sm, sd),
            'end_date': date(year, em, ed)
        }

    # Month parsing
    month_map = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    upper = period_str.upper()
    for name, mnum in month_map.items():
        if name in upper:
            year_match = re.search(r'20\d{2}', period_str)
            year = int(year_match.group()) if year_match else datetime.now().year

            # Calculate last day of month
            if mnum == 2:
                ld = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            elif mnum in (4, 6, 9, 11):
                ld = 30
            else:
                ld = 31

            return {
                'type': 'Monthly',
                'label': period_str,
                'start_date': date(year, mnum, 1),
                'end_date': date(year, mnum, ld)
            }

    # Try parsing with YAML-defined date formats
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(period_str, fmt).date()
            return {
                'type': period_type or 'Monthly',
                'label': period_str,
                'start_date': parsed_date,
                'end_date': parsed_date
            }
        except ValueError:
            continue

    # FIXED: Better fallback with period creation enabled
    log_event('period_parse_fallback', {
        'period_str': period_str, 
        'period_type': period_type,
        'message': 'Using intelligent fallback period creation'
    })

    return {
        'type': period_type or auto_create_config.get('default_type', 'Monthly'),
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

def seed_line_item_definitions():
    """Seed line_item_definitions table from fields.yaml if entries are missing."""
    config = load_fields_config()
    line_items = config.get('line_items', [])

    if not line_items:
        log_event('seed_error', {'message': 'No line_items in fields.yaml'})
        raise ValueError("No line_items defined in fields.yaml")

    conn = get_db_connection()
    with conn.cursor() as cur:
        # Check existing entries
        cur.execute("SELECT name FROM line_item_definitions")
        existing = {r[0] for r in cur.fetchall()}

        # Insert missing ones
        inserted = 0
        for item in line_items:
            name = item['name']
            if name not in existing:
                cur.execute(
                    "INSERT INTO line_item_definitions (id, name, description, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (item['id'], name, item.get('description', ''), datetime.now(), datetime.now())
                )
                inserted += 1

        conn.commit()

        if inserted > 0:
            log_event('seed_success', {'inserted_count': inserted, 'message': 'Seeded line_item_definitions from fields.yaml'})

        return inserted
