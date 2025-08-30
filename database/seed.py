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
    from server.app.utils.utils import get_db_connection
    from server.app.utils.logging_config import setup_logger, log_with_context
except ImportError:
    print("Error: Could not import database utilities.")
    sys.exit(1)

logger = setup_logger('database-seeder')

def seed_question_templates():
    """Seed question templates from YAML configuration"""
    templates = [
        # Variance Analysis Templates
        {
            'question_text': 'Revenue is {variance_percent}% {variance_direction} budget (${actual_value} vs ${budget_value}). What explains this variance and what actions are required?',
            'category': 'variance_analysis',
            'priority': 5,
            'variables': ['variance_percent', 'variance_direction', 'actual_value', 'budget_value']
        },
        {
            'question_text': '{metric_name} is {variance_percent}% {variance_direction} than expected. What factors contributed to this variance?',
            'category': 'variance_analysis',
            'priority': 4,
            'variables': ['metric_name', 'variance_percent', 'variance_direction']
        },
        
        # Trend Analysis Templates
        {
            'question_text': '{metric_name} has {trend_direction} by {change_percent}% over the last {period_count} periods. What is driving this trend?',
            'category': 'trend_analysis', 
            'priority': 4,
            'variables': ['metric_name', 'trend_direction', 'change_percent', 'period_count']
        },
        {
            'question_text': 'The trend in {metric_name} shows {trend_pattern}. Is this sustainable and what are the implications?',
            'category': 'trend_analysis',
            'priority': 3,
            'variables': ['metric_name', 'trend_pattern']
        },
        
        # Benchmark Analysis Templates
        {
            'question_text': '{company_name} profit margin is {margin_value}%, which is {comparison} the industry average. How can this be improved?',
            'category': 'benchmark_analysis',
            'priority': 3,
            'variables': ['company_name', 'margin_value', 'comparison']
        },
        {
            'question_text': '{metric_name} performance is {performance_level} compared to industry benchmarks. What strategic actions should be considered?',
            'category': 'benchmark_analysis',
            'priority': 3,
            'variables': ['metric_name', 'performance_level']
        },
        
        # Cash Flow Analysis Templates
        {
            'question_text': 'Cash flow from operations is {cash_flow_value}, while net income is {net_income_value}. What explains this {cash_quality}?',
            'category': 'cash_analysis',
            'priority': 4,
            'variables': ['cash_flow_value', 'net_income_value', 'cash_quality']
        },
        {
            'question_text': 'Working capital has {change_direction} by {change_amount}. What impact does this have on cash flow and operations?',
            'category': 'cash_analysis',
            'priority': 4,
            'variables': ['change_direction', 'change_amount']
        },
        
        # Profitability Analysis Templates
        {
            'question_text': 'Gross margin has {margin_trend} to {current_margin}%. What pricing or cost factors are driving this change?',
            'category': 'profitability_analysis',
            'priority': 4,
            'variables': ['margin_trend', 'current_margin']
        },
        {
            'question_text': 'Operating leverage is {leverage_direction} as revenues {revenue_change}. How should operational efficiency be optimized?',
            'category': 'profitability_analysis',
            'priority': 3,
            'variables': ['leverage_direction', 'revenue_change']
        },
        
        # Risk Analysis Templates
        {
            'question_text': 'Debt-to-equity ratio is {debt_ratio}, indicating {risk_level} financial leverage. What are the implications for financial stability?',
            'category': 'risk_analysis',
            'priority': 2,
            'variables': ['debt_ratio', 'risk_level']
        },
        {
            'question_text': 'Current ratio of {current_ratio} suggests {liquidity_status}. What actions should be taken to manage liquidity risk?',
            'category': 'risk_analysis',
            'priority': 2,
            'variables': ['current_ratio', 'liquidity_status']
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
        # Income Statement Items
        ('Cost of Goods Sold', ['cogs', 'cost_of_sales', 'direct_costs'], 'Direct costs of producing goods/services'),
        ('Operating Expenses', ['opex', 'operating_costs', 'operational_expenses'], 'General operating expenses'),
        ('Depreciation', ['depreciation_expense', 'amortization'], 'Depreciation and amortization expenses'),
        ('Interest Expense', ['interest_paid', 'financing_costs'], 'Interest paid on debt'),
        ('Interest Income', ['interest_earned', 'interest_revenue'], 'Interest earned on investments'),
        ('Tax Expense', ['taxes', 'income_tax', 'tax_provision'], 'Income tax expense'),
        ('Research and Development', ['r_and_d', 'rd_expense', 'research_development'], 'Research and development costs'),
        ('Marketing Expenses', ['marketing_costs', 'advertising', 'marketing_spend'], 'Marketing and advertising expenses'),
        ('General and Administrative', ['g_and_a', 'admin_expenses', 'overhead'], 'General and administrative expenses'),
        
        # Balance Sheet Items - Assets
        ('Cash and Equivalents', ['cash', 'cash_equiv', 'liquid_assets'], 'Cash and short-term investments'),
        ('Accounts Receivable', ['receivables', 'ar', 'trade_receivables'], 'Money owed by customers'),
        ('Inventory', ['stock', 'goods_inventory'], 'Value of unsold inventory'),
        ('Prepaid Expenses', ['prepaids', 'prepaid_assets'], 'Expenses paid in advance'),
        ('Property Plant Equipment', ['ppe', 'fixed_assets', 'tangible_assets'], 'Fixed assets and equipment'),
        ('Intangible Assets', ['intangibles', 'goodwill', 'intellectual_property'], 'Intangible assets including goodwill'),
        ('Investments', ['investment_securities', 'marketable_securities'], 'Investment securities and holdings'),
        
        # Balance Sheet Items - Liabilities
        ('Accounts Payable', ['payables', 'ap', 'trade_payables'], 'Money owed to suppliers'),
        ('Accrued Expenses', ['accruals', 'accrued_liabilities'], 'Expenses incurred but not yet paid'),
        ('Short-term Debt', ['current_debt', 'short_term_loans'], 'Debt due within one year'),
        ('Long-term Debt', ['ltd', 'long_term_loans', 'non_current_debt'], 'Long-term borrowings'),
        ('Deferred Revenue', ['unearned_revenue', 'deferred_income'], 'Revenue received but not yet earned'),
        
        # Equity Items
        ('Common Stock', ['share_capital', 'common_shares'], 'Common stock issued'),
        ('Retained Earnings', ['accumulated_earnings', 'earned_surplus'], 'Accumulated retained earnings'),
        ('Additional Paid-in Capital', ['apic', 'share_premium'], 'Capital contributed above par value'),
        
        # Cash Flow Items
        ('Operating Cash Flow', ['cash_from_operations', 'operating_activities'], 'Cash flow from operating activities'),
        ('Investing Cash Flow', ['cash_from_investing', 'investment_activities'], 'Cash flow from investing activities'),
        ('Financing Cash Flow', ['cash_from_financing', 'financing_activities'], 'Cash flow from financing activities'),
        ('Free Cash Flow', ['fcf', 'unlevered_free_cash_flow'], 'Cash flow available after capital expenditures'),
        ('Capital Expenditures', ['capex', 'capital_investments'], 'Capital expenditure investments')
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

def seed_example_companies():
    """Add example companies for testing and demonstration"""
    companies = [
        ('Demo Tech Corp', 'Technology'),
        ('Sample Manufacturing Inc', 'Manufacturing'),
        ('Test Retail Ltd', 'Retail'),
        ('Example Healthcare Co', 'Healthcare'),
        ('Demo Financial Services', 'Financial Services')
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for name, industry in companies:
                cur.execute("""
                    INSERT INTO companies (name, industry)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, (name, industry))
            conn.commit()
    
    log_with_context(logger, 'info', 'Example companies seeded', count=len(companies))

def seed_user_preferences():
    """Add example user preferences for demonstration"""
    preferences = [
        (1, 'default_company_id', '1'),
        (1, 'preferred_currency', 'USD'),
        (1, 'default_period_type', 'Monthly'),
        (1, 'dashboard_refresh_interval', '300'),
        (1, 'email_notifications', 'true'),
        (1, 'report_format', 'PDF'),
        (1, 'decimal_places', '2')
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for user_id, key, value in preferences:
                cur.execute("""
                    INSERT INTO user_preferences (user_id, preference_key, preference_value)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (user_id, preference_key) DO UPDATE SET
                        preference_value = EXCLUDED.preference_value,
                        updated_at = NOW()
                """, (user_id, key, f'"{value}"'))
            conn.commit()
    
    log_with_context(logger, 'info', 'User preferences seeded', count=len(preferences))

def main():
    """Run all seeding operations"""
    try:
        log_with_context(logger, 'info', 'Starting comprehensive database seeding')
        
        # Seed core data
        seed_question_templates()
        seed_additional_line_items()
        
        # Seed example data for testing/demo
        seed_example_companies()
        seed_user_preferences()
        
        log_with_context(logger, 'info', 'Database seeding completed successfully')
        
    except Exception as e:
        logger.error(f'Database seeding failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()