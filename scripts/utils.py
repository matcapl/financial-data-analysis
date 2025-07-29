import psycopg2
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using environment variables"""
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'finance'),
        'user': os.getenv('DB_USER', 'postgres'),  # Now reads from .env
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
    if not value_str or value_str.strip() == '':
        return None
    
    # Remove common formatting characters
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

def parse_period(period_str):
    """Parse period string into standardized format"""
    if not period_str:
        return None
    
    period_str = period_str.strip().upper()
    
    # Handle YTD
    if 'YTD' in period_str:
        return 'YTD'
    
    # Handle quarters
    if 'Q' in period_str:
        return period_str
    
    # Handle months
    month_mapping = {
        'JANUARY': '01', 'FEBRUARY': '02', 'MARCH': '03',
        'APRIL': '04', 'MAY': '05', 'JUNE': '06',
        'JULY': '07', 'AUGUST': '08', 'SEPTEMBER': '09',
        'OCTOBER': '10', 'NOVEMBER': '11', 'DECEMBER': '12',
        'JAN': '01', 'FEB': '02', 'MAR': '03',
        'APR': '04', 'JUN': '06', 'JUL': '07',
        'AUG': '08', 'SEP': '09', 'OCT': '10',
        'NOV': '11', 'DEC': '12'
    }
    
    for month_name, month_num in month_mapping.items():
        if month_name in period_str:
            # Extract year if present
            import re
            year_match = re.search(r'20\d{2}', period_str)
            if year_match:
                return f"{year_match.group()}-{month_num}"
            else:
                return f"2024-{month_num}"  # Default year
    
    return period_str
