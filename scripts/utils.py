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
    """Get database connection using environment variables"""
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'finance'),
        'user': os.getenv('DB_USER', 'postgres'),
        'port': int(os.getenv('DB_PORT', '5432'))
    }
    
    # Add password if provided
    db_password = os.getenv('DB_PASSWORD')
    if db_password:
        conn_params['password'] = db_password
    
    try:
        return psycopg2.connect(**conn_params)
    except psycopg2.Error as e:
        log_event('database_error', {'error': str(e)})
        raise

def log_event(event_type, data):
    """Log events to JSON file"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data': data
    }
    
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    with open('logs/events.json', 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

def clean_numeric_value(value_str):
    """Clean and convert string to numeric value"""
    if not value_str or value_str == '' or str(value_str).strip() == '':
        return None
    
    # Convert to string and clean
    cleaned = str(value_str).replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()
    
    # Handle parentheses as negative
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
    
    try:
        # Try integer first
        if '.' not in cleaned:
            return int(cleaned)
        else:
            return float(cleaned)
    except (ValueError, TypeError):
        return None

def parse_period(period_str, period_type=None):
    """
    Enhanced period parsing with better date handling
    """
    if not period_str:
        return None
    
    period_str = str(period_str).strip()
    
    # Default period type if not provided
    if not period_type:
        if 'Q' in period_str.upper():
            period_type = 'Quarterly'
        else:
            period_type = 'Monthly'
    
    # Handle YTD
    if 'YTD' in period_str.upper():
        year_match = re.search(r'20\d{2}', period_str)
        if year_match:
            year = int(year_match.group())
        else:
            year = datetime.now().year
        
        return {
            'type': 'Yearly',
            'label': f'YTD {year}',
            'start_date': date(year, 1, 1),
            'end_date': date(year, 12, 31)
        }
    
    # Handle quarters
    quarter_match = re.search(r'Q(\d)', period_str, re.IGNORECASE)
    if quarter_match:
        quarter_num = int(quarter_match.group(1))
        year_match = re.search(r'20\d{2}', period_str)
        year = int(year_match.group()) if year_match else datetime.now().year
        
        quarter_starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        quarter_ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        
        start_month, start_day = quarter_starts[quarter_num]
        end_month, end_day = quarter_ends[quarter_num]
        
        return {
            'type': 'Quarterly',
            'label': f'Q{quarter_num} {year}',
            'start_date': date(year, start_month, start_day),
            'end_date': date(year, end_month, end_day)
        }
    
    # Handle months
    month_mapping = {
        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'MAY': 5, 'JUNE': 6,
        'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'JUN': 6, 'JUL': 7,
        'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    
    for month_name, month_num in month_mapping.items():
        if month_name in period_str.upper():
            # Extract year if present
            year_match = re.search(r'20\d{2}', period_str)
            year = int(year_match.group()) if year_match else datetime.now().year
            
            # Calculate last day of month
            if month_num == 2:  # February
                last_day = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
            elif month_num in [4, 6, 9, 11]:  # April, June, September, November
                last_day = 30
            else:
                last_day = 31
            
            return {
                'type': 'Monthly',
                'label': period_str,
                'start_date': date(year, month_num, 1),
                'end_date': date(year, month_num, last_day)
            }
    
    # Default fallback - try to parse as is
    return {
        'type': period_type or 'Monthly',
        'label': period_str,
        'start_date': datetime.now().date(),
        'end_date': datetime.now().date()
    }

def hash_datapoint(company_id, period_id, line_item, value_type, frequency):
    """Generate a hash for deduplicating data points"""
    data_string = f"{company_id}|{period_id}|{line_item}|{value_type}|{frequency}"
    return hashlib.md5(data_string.encode()).hexdigest()

# Additional utility functions for the enhanced system
def validate_line_item(line_item):
    """Validate that the line item is one of the supported types"""
    valid_items = ['Revenue', 'Gross Profit', 'EBITDA']
    return line_item in valid_items

def format_currency(value, currency='USD'):
    """Format numeric value as currency"""
    if value is None:
        return 'N/A'
    
    if currency == 'USD':
        return f"${value:,.2f}"
    elif currency == 'EUR':
        return f"€{value:,.2f}"
    elif currency == 'GBP':
        return f"£{value:,.2f}"
    else:
        return f"{value:,.2f} {currency}"

def calculate_percentage_change(current, previous):
    """Calculate percentage change between two values"""
    if previous is None or previous == 0:
        return None
    
    if current is None:
        return None
    
    return ((current - previous) / abs(previous)) * 100