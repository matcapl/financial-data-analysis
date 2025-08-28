# Database Seeding Guide

This guide covers the comprehensive database seeding system for the financial data analysis application.

## Overview

The seeding system provides:
- ✅ **Reference Data**: Essential line items, question templates, and system data
- ✅ **Example Data**: Demo companies and user preferences for testing/demonstration  
- ✅ **CI/CD Integration**: Automated seeding in deployment pipelines
- ✅ **Idempotent Operations**: Safe to run multiple times without duplication
- ✅ **Comprehensive Coverage**: 36+ line items, 12+ question templates, example companies

## Seeding Components

### 1. Core Reference Data

**Question Templates** (12 templates across 6 categories):
- `variance_analysis` - Budget vs actual variance analysis
- `trend_analysis` - Trend identification and pattern analysis  
- `benchmark_analysis` - Industry and peer benchmarking
- `cash_analysis` - Cash flow and liquidity analysis
- `profitability_analysis` - Margin and profitability insights
- `risk_analysis` - Financial risk and leverage assessment

**Financial Line Items** (36+ comprehensive definitions):
- **Income Statement**: Revenue, COGS, Operating Expenses, EBITDA, Net Income, etc.
- **Balance Sheet Assets**: Cash, Receivables, Inventory, PPE, Intangibles, etc.
- **Balance Sheet Liabilities**: Payables, Accruals, Short/Long-term Debt, etc.
- **Equity Items**: Common Stock, Retained Earnings, APIC, etc.
- **Cash Flow Items**: Operating/Investing/Financing Cash Flows, FCF, CapEx, etc.

### 2. Example/Demo Data

**Companies** (6 example companies):
- Demo Tech Corp (Technology)
- Sample Manufacturing Inc (Manufacturing)  
- Test Retail Ltd (Retail)
- Example Healthcare Co (Healthcare)
- Demo Financial Services (Financial Services)
- Example Company (Example Industry) - from migration

**User Preferences** (7 default settings):
- Default company, currency, period type
- Dashboard refresh interval
- Notification and report preferences
- Display format settings

## Usage

### Manual Seeding

```bash
# Basic seeding
python database/seed.py

# Verify seeding results
python -c "
import sys
sys.path.insert(0, 'server/scripts')
from utils import get_db_connection
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM question_templates')
        print(f'Question Templates: {cur.fetchone()[0]}')
        cur.execute('SELECT COUNT(*) FROM line_item_definitions') 
        print(f'Line Items: {cur.fetchone()[0]}')
        cur.execute('SELECT COUNT(*) FROM companies')
        print(f'Companies: {cur.fetchone()[0]}')
"
```

### CI/CD Integration

```bash
# CI/CD seeding script
bash ci/04_seed_database.sh

# Included in comprehensive testing
bash ci/12_comprehensive_check.sh
```

### Production Deployment

Seeding runs automatically during deployment via `scripts/deploy-start.sh`:
1. Applies database migrations
2. Updates rollback SQL
3. **Runs database seeding** (with error handling)
4. Starts the application

## Seeding Functions

### `seed_question_templates()`
Seeds analytical question templates for automatic question generation:
- 12 templates across 6 categories
- Parameterized with template variables
- Priority-based classification (1=high, 5=low)
- Conflict handling with `ON CONFLICT DO NOTHING`

### `seed_additional_line_items()`  
Seeds comprehensive financial line item definitions:
- 29 additional line items beyond migration seed data
- Organized by financial statement category
- Rich alias arrays for flexible data mapping
- Detailed descriptions for user guidance

### `seed_example_companies()`
Seeds demonstration companies for testing:
- 5 companies across different industries
- Industry classification included
- Safe for repeated execution

### `seed_user_preferences()`
Seeds default user preference examples:
- User ID 1 default preferences
- JSONB format for flexible value storage
- Upsert behavior for preference updates
- Common settings for dashboard, reports, notifications

## Data Structure

### Question Templates Schema
```sql
CREATE TABLE question_templates (
  id SERIAL PRIMARY KEY,
  question_text TEXT NOT NULL,
  category TEXT NOT NULL,
  priority INTEGER DEFAULT 3,
  template_variables TEXT[],
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**Categories**:
- `variance_analysis` - Budget variance questions
- `trend_analysis` - Trend pattern questions  
- `benchmark_analysis` - Performance comparison questions
- `cash_analysis` - Cash flow and liquidity questions
- `profitability_analysis` - Margin and efficiency questions
- `risk_analysis` - Financial risk assessment questions

### Line Item Definitions Schema
```sql
CREATE TABLE line_item_definitions (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  aliases TEXT[],
  description TEXT
);
```

**Categories**:
- Income Statement items (Revenue, COGS, Operating Expenses, etc.)
- Balance Sheet Assets (Cash, Receivables, Inventory, PPE, etc.)
- Balance Sheet Liabilities (Payables, Debt, Accruals, etc.)
- Equity items (Common Stock, Retained Earnings, etc.)
- Cash Flow items (Operating/Investing/Financing Cash Flows, etc.)

## CI/CD Integration Features

### Automated Pipeline Integration

**GitHub Actions** (`.github/workflows/ci-cd.yml`):
- Database seeding test in migration-check job
- Verification of seeded data counts and integrity
- PostgreSQL service for realistic testing environment

**Comprehensive Testing** (`ci/12_comprehensive_check.sh`):
- Step 3: Database seeding with verification
- Integration with full pipeline testing
- Data quality and relationship validation

**Production Deployment** (`scripts/deploy-start.sh`):
- Automatic seeding during deployment
- Non-critical error handling (won't fail deployment)
- Logging and status verification

### Seeding Verification

The CI pipeline includes comprehensive verification:
- **Count Validation**: Ensures minimum data thresholds
- **Relationship Integrity**: Validates foreign key relationships
- **Data Quality**: Checks for orphaned records and consistency
- **Template Coverage**: Verifies question template categories

```bash
# Verification thresholds
Templates: >= 5
Line Items: >= 10  
Companies: >= 2
```

## Best Practices

### Development
1. **Always run migrations first** before seeding
2. **Use ON CONFLICT handling** for idempotent operations
3. **Test seeding locally** before committing changes
4. **Verify data counts** after seeding operations

### Production
1. **Seeding is non-critical** for deployment success
2. **Monitor seeding logs** for potential issues
3. **Reference data updates** should be tested in staging
4. **Backup before** major seeding changes

### Data Management
1. **Migration seed data** is core/essential data
2. **Script seed data** is supplemental/example data
3. **Use meaningful names** and descriptions
4. **Maintain alias arrays** for flexible data mapping

## Troubleshooting

### Common Issues

**Table Structure Mismatch**:
```bash
# Fix by rolling back and reapplying migrations
python database/migrate.py down
python database/migrate.py up
python database/seed.py
```

**Seeding Verification Failure**:
```bash
# Check data counts manually
python -c "
import sys
sys.path.insert(0, 'server/scripts')  
from utils import get_db_connection
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM question_templates')
        print(f'Templates: {cur.fetchone()[0]}')
"
```

**CI/CD Seeding Failure**:
```bash
# Run seeding script manually to debug
bash ci/04_seed_database.sh
```

### Validation Commands

```bash
# Check seeding results
python -c "
import sys
sys.path.insert(0, 'server/scripts')
from utils import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Template categories
        cur.execute('SELECT category, COUNT(*) FROM question_templates GROUP BY category')
        print('Template Categories:')
        for cat, count in cur.fetchall():
            print(f'  {cat}: {count}')
            
        # Line item categories  
        cur.execute('SELECT name FROM line_item_definitions ORDER BY name')
        items = [row[0] for row in cur.fetchall()]
        print(f'\\nLine Items ({len(items)}): {items[:10]}...')
"
```

---

**For migration system documentation, see `database/README.md`**
**For CI/CD integration, see `CI_CD_GUIDE.md`**