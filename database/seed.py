#!/usr/bin/env python3
"""
Database Seeding Script
Adds additional seed data beyond what's in migrations
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.scripts.utils import get_db_connection
    from server.scripts.logging_config import setup_logger, log_with_context
except ImportError:
    print("Error: Could not import database utilities.")
    sys.exit(1)

logger = setup_logger('database-seeder')

def seed_question_templates():
    """Seed question templates from YAML configuration"""
    templates = [
        {
            'question_text': 'Revenue is {variance_percent}% {variance_direction} budget (${actual_value} vs ${budget_value}). What explains this variance and what actions are required?',
            'category': 'variance_analysis',
            'priority': 5,
            'variables': ['variance_percent', 'variance_direction', 'actual_value', 'budget_value']
        },
        {
            'question_text': '{metric_name} has {trend_direction} by {change_percent}% over the last {period_count} periods. What is driving this trend?',
            'category': 'trend_analysis', 
            'priority': 4,
            'variables': ['metric_name', 'trend_direction', 'change_percent', 'period_count']
        },
        {
            'question_text': '{company_name} profit margin is {margin_value}%, which is {comparison} the industry average. How can this be improved?',
            'category': 'benchmark_analysis',
            'priority': 3,
            'variables': ['company_name', 'margin_value', 'comparison']
        },
        {
            'question_text': 'Cash flow from operations is {cash_flow_value}, while net income is {net_income_value}. What explains this {cash_quality}?',
            'category': 'cash_analysis',
            'priority': 4,
            'variables': ['cash_flow_value', 'net_income_value', 'cash_quality']
        }
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for template in templates:
                cur.execute("""
                    INSERT INTO question_templates (question_text, category, priority, template_variables)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    template['question_text'],
                    template['category'], 
                    template['priority'],
                    template['variables']
                ))
            conn.commit()
    
    log_with_context(logger, 'info', 'Question templates seeded', count=len(templates))

def seed_additional_line_items():
    """Add more comprehensive line item definitions"""
    line_items = [
        ('Cost of Goods Sold', ['cogs', 'cost_of_sales', 'direct_costs'], 'Direct costs of producing goods/services'),
        ('Operating Expenses', ['opex', 'operating_costs', 'operational_expenses'], 'General operating expenses'),
        ('Depreciation', ['depreciation_expense', 'amortization'], 'Depreciation and amortization expenses'),
        ('Interest Expense', ['interest_paid', 'financing_costs'], 'Interest paid on debt'),
        ('Tax Expense', ['taxes', 'income_tax', 'tax_provision'], 'Income tax expense'),
        ('Cash and Equivalents', ['cash', 'cash_equiv', 'liquid_assets'], 'Cash and short-term investments'),
        ('Accounts Receivable', ['receivables', 'ar', 'trade_receivables'], 'Money owed by customers'),
        ('Inventory', ['stock', 'goods_inventory'], 'Value of unsold inventory'),
        ('Accounts Payable', ['payables', 'ap', 'trade_payables'], 'Money owed to suppliers'),
        ('Long-term Debt', ['ltd', 'long_term_loans', 'debt'], 'Long-term borrowings')
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for name, aliases, description in line_items:
                cur.execute("""
                    INSERT INTO line_item_definitions (name, aliases, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, (name, aliases, description))
            conn.commit()
    
    log_with_context(logger, 'info', 'Additional line items seeded', count=len(line_items))

def main():
    """Run all seeding operations"""
    try:
        log_with_context(logger, 'info', 'Starting database seeding')
        
        seed_question_templates()
        seed_additional_line_items()
        
        log_with_context(logger, 'info', 'Database seeding completed successfully')
        
    except Exception as e:
        logger.error(f'Database seeding failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()