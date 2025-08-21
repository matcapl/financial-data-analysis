# server/scripts/normalization.py
import os
import yaml
import re
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
from utils import log_event, get_db_connection

# Load period configuration
def load_periods_config() -> Dict[str, Any]:
    """Load consolidated period configuration from periods.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'periods.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log_event("periods_config_load_error", {"error": str(e)})
        return {}

PERIODS_CONFIG = load_periods_config()

def normalize_period_label(raw_period: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize period labels to ISO 8601 canonical format using periods.yaml configuration.
    Returns (canonical_period, period_type) or (None, None) if not found.
    """
    if not raw_period or pd.isna(raw_period):
        return None, None
    
    raw_period_clean = str(raw_period).strip()
    if not raw_period_clean:
        return None, None
    
    # Direct lookup in period aliases
    period_aliases = PERIODS_CONFIG.get('period_aliases', {})
    for canonical, config in period_aliases.items():
        aliases = config.get('aliases', [])
        if raw_period_clean in aliases or raw_period_clean.lower() in [a.lower() for a in aliases]:
            return canonical, config.get('period_type')
    
    # Fallback pattern matching
    patterns = PERIODS_CONFIG.get('parsing', {}).get('patterns', {})
    
    # Monthly patterns
    for pattern_config in patterns.get('monthly_patterns', []):
        pattern = pattern_config.get('pattern', '')
        try:
            if re.search(pattern, raw_period_clean, re.IGNORECASE):
                # Extract year and month
                match = re.search(r'(\d{4})', raw_period_clean)
                if match:
                    year = match.group(1)
                    # Try to extract month
                    month_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2})', raw_period_clean, re.IGNORECASE)
                    if month_match:
                        month_str = month_match.group(1).lower()
                        month_map = {
                            'jan': '01', 'january': '01',
                            'feb': '02', 'february': '02',
                            'mar': '03', 'march': '03',
                            'apr': '04', 'april': '04',
                            'may': '05',
                            'jun': '06', 'june': '06',
                            'jul': '07', 'july': '07',
                            'aug': '08', 'august': '08',
                            'sep': '09', 'september': '09',
                            'oct': '10', 'october': '10',
                            'nov': '11', 'november': '11',
                            'dec': '12', 'december': '12'
                        }
                        if month_str in month_map:
                            return f"{year}-{month_map[month_str]}", "Monthly"
                        elif month_str.isdigit():
                            month_num = int(month_str)
                            if 1 <= month_num <= 12:
                                return f"{year}-{month_num:02d}", "Monthly"
        except re.error:
            continue
    
    # Quarterly patterns
    for pattern_config in patterns.get('quarterly_patterns', []):
        pattern = pattern_config.get('pattern', '')
        try:
            if re.search(pattern, raw_period_clean, re.IGNORECASE):
                match = re.search(r'(\d{4})', raw_period_clean)
                quarter_match = re.search(r'[qQ]?([1-4])', raw_period_clean)
                if match and quarter_match:
                    year = match.group(1)
                    quarter = quarter_match.group(1)
                    return f"{year}-Q{quarter}", "Quarterly"
        except re.error:
            continue
    
    # Yearly patterns
    for pattern_config in patterns.get('yearly_patterns', []):
        pattern = pattern_config.get('pattern', '')
        try:
            if re.search(pattern, raw_period_clean, re.IGNORECASE):
                match = re.search(r'(\d{4})', raw_period_clean)
                if match:
                    year = match.group(1)
                    return year, "Yearly"
        except re.error:
            continue
    
    log_event("period_normalization_failed", {
        "raw_period": raw_period_clean,
        "reason": "no_pattern_match"
    })
    return None, None

def normalize_value(raw_value: Any) -> Optional[Decimal]:
    """
    Normalize financial values to Decimal type.
    Handles various formats: $1,234.56, (1234.56), 1234.56, etc.
    """
    if raw_value is None or pd.isna(raw_value):
        return None
    
    value_str = str(raw_value).strip()
    if not value_str:
        return None
    
    # Remove common currency symbols and formatting
    value_str = re.sub(r'[$€£¥,\s]', '', value_str)
    
    # Handle parentheses as negative (accounting format)
    is_negative = False
    if value_str.startswith('(') and value_str.endswith(')'):
        is_negative = True
        value_str = value_str[1:-1]
    
    # Handle negative signs
    if value_str.startswith('-'):
        is_negative = True
        value_str = value_str[1:]
    
    # Try to convert to Decimal
    try:
        decimal_value = Decimal(value_str)
        return -decimal_value if is_negative else decimal_value
    except (InvalidOperation, ValueError):
        log_event("value_normalization_failed", {
            "raw_value": str(raw_value),
            "cleaned_value": value_str
        })
        return None

def normalize_text_field(raw_text: Any) -> Optional[str]:
    """Normalize text fields by cleaning whitespace and handling None/empty values."""
    if raw_text is None or pd.isna(raw_text):
        return None
    
    text_str = str(raw_text).strip()
    if not text_str or text_str.lower() in ['nan', 'none', 'null', '']:
        return None
    
    return text_str

def create_hash(company_id: int, period_id: int, line_item_id: int, value_type: str = 'Actual') -> str:
    """Create a unique hash for deduplication."""
    hash_input = f"{company_id}_{period_id}_{line_item_id}_{value_type}"
    return hashlib.md5(hash_input.encode()).hexdigest()

def lookup_or_create_period(canonical_period: str, period_type: str) -> Optional[int]:
    """
    Look up period ID in database, create if doesn't exist.
    Returns period_id or None if creation fails.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First try to find existing period
                cur.execute("""
                    SELECT id FROM periods 
                    WHERE period_label = %s AND period_type = %s
                """, (canonical_period, period_type))
                
                result = cur.fetchone()
                if result:
                    return result[0]
                
                # Period doesn't exist, create it
                # Extract start_date and end_date from periods.yaml config
                period_config = PERIODS_CONFIG.get('period_aliases', {}).get(canonical_period, {})
                start_date = period_config.get('start_date')
                end_date = period_config.get('end_date')
                
                if not start_date or not end_date:
                    # Fallback to generating dates
                    if period_type == "Monthly" and re.match(r'\d{4}-\d{2}', canonical_period):
                        year, month = canonical_period.split('-')
                        start_date = f"{year}-{month}-01"
                        # Calculate end date
                        if month == '12':
                            end_date = f"{int(year)+1}-01-01"
                        else:
                            next_month = int(month) + 1
                            end_date = f"{year}-{next_month:02d}-01"
                        cur.execute("SELECT (%s::date - INTERVAL '1 day')::date", (end_date,))
                        end_date = cur.fetchone()[0].strftime('%Y-%m-%d')
                    
                    elif period_type == "Quarterly" and re.match(r'\d{4}-Q[1-4]', canonical_period):
                        year, quarter = canonical_period.split('-Q')
                        quarter = int(quarter)
                        start_month = (quarter - 1) * 3 + 1
                        start_date = f"{year}-{start_month:02d}-01"
                        end_month = quarter * 3
                        if end_month == 12:
                            end_date = f"{year}-12-31"
                        else:
                            cur.execute("SELECT (date_trunc('quarter', %s::date) + INTERVAL '3 months' - INTERVAL '1 day')::date", (start_date,))
                            end_date = cur.fetchone()[0].strftime('%Y-%m-%d')
                    
                    elif period_type == "Yearly" and re.match(r'\d{4}', canonical_period):
                        start_date = f"{canonical_period}-01-01"
                        end_date = f"{canonical_period}-12-31"
                
                if start_date and end_date:
                    cur.execute("""
                        INSERT INTO periods (period_label, period_type, start_date, end_date, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                        RETURNING id
                    """, (canonical_period, period_type, start_date, end_date))
                    
                    period_id = cur.fetchone()[0]
                    conn.commit()
                    
                    log_event("period_created", {
                        "period_id": period_id,
                        "period_label": canonical_period,
                        "period_type": period_type,
                        "start_date": start_date,
                        "end_date": end_date
                    })
                    
                    return period_id
                else:
                    log_event("period_creation_failed", {
                        "canonical_period": canonical_period,
                        "period_type": period_type,
                        "reason": "could_not_determine_dates"
                    })
                    return None
                    
    except Exception as e:
        log_event("period_lookup_error", {
            "canonical_period": canonical_period,
            "period_type": period_type,
            "error": str(e)
        })
        return None

def lookup_line_item_id(line_item_name: str) -> Optional[int]:
    """Look up line item ID in database."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Direct name match
                cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (line_item_name,))
                result = cur.fetchone()
                if result:
                    return result[0]
                
                # Try case-insensitive match
                cur.execute("SELECT id FROM line_item_definitions WHERE LOWER(name) = LOWER(%s)", (line_item_name,))
                result = cur.fetchone()
                if result:
                    return result[0]
                
                # Try alias match
                cur.execute("""
                    SELECT id FROM line_item_definitions 
                    WHERE %s = ANY(aliases) OR LOWER(%s) = ANY(ARRAY(SELECT LOWER(unnest(aliases))))
                """, (line_item_name, line_item_name))
                result = cur.fetchone()
                if result:
                    return result[0]
                
                log_event("line_item_lookup_failed", {"line_item_name": line_item_name})
                return None
                
    except Exception as e:
        log_event("line_item_lookup_error", {"line_item_name": line_item_name, "error": str(e)})
        return None

def normalize_data(mapped_rows: List[Dict[str, Any]], source_file: str) -> Tuple[List[Dict[str, Any]], int]:
    """
    Normalize mapped data for database insertion.
    Returns (normalized_rows, error_count).
    """
    normalized_rows = []
    error_count = 0
    
    log_event("normalization_started", {
        "input_rows": len(mapped_rows),
        "source_file": source_file
    })
    
    for row_idx, row in enumerate(mapped_rows, 1):
        try:
            # Skip rows without essential data
            if not row.get('line_item') or not row.get('period_label') or row.get('value') is None:
                log_event("normalization_skip_incomplete", {
                    "row_number": row.get('_row_number', row_idx),
                    "missing_fields": [k for k in ['line_item', 'period_label', 'value'] if not row.get(k)]
                })
                error_count += 1
                continue
            
            # Normalize period
            canonical_period, period_type = normalize_period_label(row['period_label'])
            if not canonical_period:
                log_event("normalization_skip_period", {
                    "row_number": row.get('_row_number', row_idx),
                    "raw_period": row['period_label']
                })
                error_count += 1
                continue
            
            # Lookup/create period ID
            period_id = lookup_or_create_period(canonical_period, period_type)
            if not period_id:
                log_event("normalization_skip_period_id", {
                    "row_number": row.get('_row_number', row_idx),
                    "canonical_period": canonical_period
                })
                error_count += 1
                continue
            
            # Lookup line item ID
            line_item_id = lookup_line_item_id(row['line_item'])
            if not line_item_id:
                log_event("normalization_skip_line_item", {
                    "row_number": row.get('_row_number', row_idx),
                    "line_item": row['line_item']
                })
                error_count += 1
                continue
            
            # Normalize value
            normalized_value = normalize_value(row['value'])
            if normalized_value is None:
                log_event("normalization_skip_value", {
                    "row_number": row.get('_row_number', row_idx),
                    "raw_value": row['value']
                })
                error_count += 1
                continue
            
            # Create normalized row
            normalized_row = {
                'company_id': 1,  # Default company ID
                'period_id': period_id,
                'line_item_id': line_item_id,
                'value': float(normalized_value),  # Convert Decimal to float for JSON serialization
                'value_type': normalize_text_field(row.get('value_type')) or 'Actual',
                'frequency': normalize_text_field(row.get('frequency')) or period_type,
                'currency': normalize_text_field(row.get('currency')) or 'USD',
                'source_file': os.path.basename(source_file),
                'source_page': row.get('source_page') or row.get('_sheet_name'),
                'source_type': normalize_text_field(row.get('source_type')),
                'notes': normalize_text_field(row.get('notes')),
                'hash': create_hash(1, period_id, line_item_id, normalize_text_field(row.get('value_type')) or 'Actual'),
                '_row_number': row.get('_row_number', row_idx),
                '_canonical_period': canonical_period,
                '_period_type': period_type
            }
            
            normalized_rows.append(normalized_row)
            
        except Exception as e:
            log_event("normalization_row_error", {
                "row_number": row.get('_row_number', row_idx),
                "error": str(e),
                "row_sample": {k: v for k, v in row.items() if k in ['line_item', 'period_label', 'value']}
            })
            error_count += 1
            continue
    
    log_event("normalization_completed", {
        "input_rows": len(mapped_rows),
        "output_rows": len(normalized_rows),
        "error_count": error_count,
        "success_rate": len(normalized_rows) / len(mapped_rows) if mapped_rows else 0
    })
    
    return normalized_rows, error_count

# Import pandas for isna check
import pandas as pd

if __name__ == "__main__":
    # Test normalization functions
    test_periods = [
        "Feb 2025",
        "Q1 2025", 
        "2025",
        "February 2025",
        "2025-02",
        "invalid period"
    ]
    
    print("Testing period normalization:")
    for period in test_periods:
        canonical, ptype = normalize_period_label(period)
        print(f"  {period} → {canonical} ({ptype})")
    
    test_values = [
        "$1,234.56",
        "(500.00)",
        "1000",
        "invalid",
        None
    ]
    
    print("\nTesting value normalization:")
    for value in test_values:
        normalized = normalize_value(value)
        print(f"  {value} → {normalized}")
