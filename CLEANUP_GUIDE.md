# Database Cleanup Guide

## Overview

The `cleanup_transient_data.py` script safely removes temporary/transient data from the database for development and testing environments. It includes robust production protection to prevent accidental data loss.

## Safety Features

### 🛡️ Production Protection
- **Environment Detection**: Automatically detects environment from settings
- **Production Blocking**: Refuses to run in production environment
- **Safe Environments**: Only runs in `development`, `test`, or `staging`

### 🔍 Data Categorization
The script categorizes database tables into two types:

**Transient Data (Will be cleaned):**
- `financial_metrics` - User uploaded financial data
- `derived_metrics` - Calculated metrics from financial data  
- `questions` - Generated analytical questions
- `live_questions` - Active question states
- `question_logs` - Question change logs
- `generated_reports` - PDF report metadata

**Persistent Data (Will be preserved):**
- `companies` - Company master data
- `periods` - Period definitions (months, quarters, years)
- `line_item_definitions` - Financial metric definitions
- `question_templates` - Question generation templates

## Usage

### Quick Commands (Recommended)

```bash
# Preview what would be deleted (safe to run anytime)
make cleanup-dry-run

# Execute cleanup in development
make cleanup-dev
```

### Direct Script Usage

```bash
# Preview cleanup without executing
python scripts/cleanup_transient_data.py --dry-run

# Execute with confirmation prompt
python scripts/cleanup_transient_data.py

# Execute without confirmation prompt
python scripts/cleanup_transient_data.py --confirm
```

## What Gets Cleaned

### Database Records
- Removes all user-uploaded financial data
- Clears generated analytical questions
- Removes calculated metrics and reports
- **Preserves** core configuration and reference data

### Files
- Clears uploaded files in `uploads/` directory
- Removes generated reports in `reports/` directory
- Cleans processed data files (if they exist)

## Example Output

```
🧹 Financial Data Analysis - Transient Data Cleanup
============================================================
🔍 Environment check: development
✅ Environment 'development' is safe for cleanup

📊 CURRENT DATA SUMMARY:
   🗑️ financial_metrics   :      610 records
   🗑️ questions           :   20,373 records
   🗑️ generated_reports   :       25 records
   💾 companies           :        6 records (preserved)
   💾 periods             :      344 records (preserved)

🧹 EXECUTING CLEANUP...
   ✅ Deleted 20,373 records from questions
   ✅ Deleted 25 records from generated_reports
   ✅ Deleted 610 records from financial_metrics
   ✅ Deleted 6 files from reports/

📈 CLEANUP SUMMARY:
   Database Records Deleted: 21,008
   Files Deleted: 6
   ✅ Cleanup completed successfully!
```

## When to Use

### Development Scenarios
- **Fresh Start**: Clear all test data to start with clean state
- **Testing**: Reset database between test runs
- **Data Migration**: Clean before importing new data sets
- **Performance Testing**: Remove large datasets after testing

### Before Major Changes
- Schema updates that require clean data
- New data import procedures
- Algorithm testing and validation

## Error Handling

### Production Protection
```
🚫 PRODUCTION ENVIRONMENT DETECTED!
   This script is designed for development and testing only.
   Execution blocked to prevent data loss.
```

### Database Connection Issues
- Script validates database connection before proceeding
- Shows clear error messages for connection problems
- Safely handles transaction rollbacks on errors

## Environment Configuration

The script automatically detects environment from:

1. `ENVIRONMENT` environment variable
2. Application settings in `server/app/core/config.py`

Supported environments:
- `development` ✅ (Safe)
- `test` ✅ (Safe) 
- `staging` ✅ (Safe)
- `production` ❌ (Blocked)

## Integration with Development Workflow

```bash
# 1. Fresh development setup
make setup
make cleanup-dry-run  # Preview current data
make cleanup-dev      # Clear if needed

# 2. Before testing new data processing
make cleanup-dev      # Clear old data
# Upload new test files via UI

# 3. Performance testing
# Load large dataset
make cleanup-dry-run  # Check data size
make cleanup-dev      # Clean after testing
```

## Troubleshooting

### Common Issues

**Script won't run:**
```bash
# Check environment
echo $ENVIRONMENT

# Ensure virtual environment is active  
source .venv/bin/activate

# Check database connection
make test-db
```

**Permission issues:**
```bash
# Make script executable
chmod +x scripts/cleanup_transient_data.py
```

**Unknown environment:**
- Set `ENVIRONMENT=development` in `.env` file
- Or export `ENVIRONMENT=development` before running

### Manual Verification

After cleanup, verify data state:
```bash
# Check record counts
make test-db

# Start server and check via API
make server
curl http://localhost:4000/api/reports  # Should be empty
```

## Best Practices

1. **Always dry-run first** - Use `--dry-run` to preview changes
2. **Development only** - Never attempt to run in production
3. **Backup important data** - Before major cleanups in staging
4. **Verify environment** - Check environment settings before running
5. **Check data summary** - Review what will be deleted before confirming

## Related Documentation

- [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) - Development setup and workflows
- [`CI_CD_GUIDE.md`](CI_CD_GUIDE.md) - Continuous integration processes
- [`config/tables.yaml`](config/tables.yaml) - Database schema definitions