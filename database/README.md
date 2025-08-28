# Database Migration System

This directory contains the database migration system that replaces the previous YAML-based schema generation.

## 📁 Directory Structure

```
database/
├── migrations/           # Migration files
├── migrate.py           # Migration runner
├── seed.py             # Data seeding script  
└── README.md           # This file
```

## 🚀 Quick Start

### Apply All Migrations
```bash
python database/migrate.py up
```

### Check Migration Status
```bash
python database/migrate.py status
```

### Create New Migration
```bash
python database/migrate.py create "Add user preferences table"
```

### Rollback Last Migration
```bash
python database/migrate.py down
```

## 📝 Migration Files

Migration files are numbered sequentially and follow this naming pattern:
```
001_create_core_tables.sql
002_seed_initial_data.sql  
003_create_financial_metrics_tables.sql
```

### Migration File Template
```sql
-- Migration: Description of what this migration does
-- Version: 001
-- Description: Detailed description
-- Author: Developer Name
-- Date: YYYY-MM-DD

-- Migration Up (Apply changes)
CREATE TABLE example (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

-- Migration Down (Rollback changes)
-- This migration does not support automatic rollback
```

## 🔧 Available Commands

| Command | Description |
|---------|-------------|
| `up` | Apply all pending migrations |
| `down` | Rollback the last migration |
| `status` | Show current migration status |
| `create "description"` | Create a new migration file |
| `reset` | Rollback ALL migrations (dangerous!) |

## 📊 Migration History

| Version | Description | Status |
|---------|-------------|---------|
| 000 | Create migrations tracking table | System |
| 001 | Create core tables | ✅ |
| 002 | Seed initial data | ✅ |
| 003 | Create financial metrics tables | ✅ |
| 004 | Create questions and reports tables | ✅ |

## 🎯 Best Practices

### Creating Migrations
1. **One Purpose Per Migration**: Each migration should do one logical thing
2. **Descriptive Names**: Use clear, descriptive names for migrations
3. **Test Rollbacks**: Always test that rollbacks work (when applicable)
4. **Data Safety**: Use `IF NOT EXISTS` and `ON CONFLICT` for safety

### Migration Content
```sql
-- ✅ Good: Safe operations
CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY);
INSERT INTO config VALUES ('key', 'value') ON CONFLICT DO NOTHING;

-- ❌ Avoid: Destructive operations without safeguards
DROP TABLE users;  -- Dangerous!
DELETE FROM important_data;  -- Also dangerous!
```

### Development Workflow
1. **Create Migration**: `python database/migrate.py create "Add feature"`
2. **Edit SQL**: Add your changes to the generated file
3. **Apply Migration**: `python database/migrate.py up`
4. **Test**: Verify the changes work as expected
5. **Commit**: Add the migration file to git

## 🔄 Migration vs. YAML Schema

### Old YAML-based Approach
- Generated entire schema from YAML
- No version control of schema changes  
- Difficult to track what changed when
- Risky for production deployments

### New Migration-based Approach
- ✅ **Incremental Changes**: Each change is tracked separately
- ✅ **Version Control**: Full git history of schema changes
- ✅ **Rollback Support**: Can undo changes safely
- ✅ **Team Collaboration**: Multiple developers can work without conflicts
- ✅ **Production Safe**: Only applies new changes, doesn't recreate everything

## 🚨 Important Notes

### Database Connection
The migration system uses the same database connection as the application (from `server.scripts.utils.get_db_connection()`). Make sure your database is configured correctly.

### Production Usage
- Always backup your database before running migrations in production
- Test migrations in staging environment first  
- Never run `reset` command in production
- Monitor migration logs for any issues

### Rollbacks
Not all migrations can be automatically rolled back. For complex migrations that change data or drop columns, you may need to manually specify rollback SQL.

## 🐛 Troubleshooting

### Migration Fails
```bash
# Check what went wrong
python database/migrate.py status

# Fix the issue in the migration file, then try again
python database/migrate.py up
```

### Database Connection Issues
```bash
# Verify database connection works
python -c "from server.scripts.utils import get_db_connection; print('✅ DB Connected')"
```

### Reset Everything (Development Only)
```bash
# ⚠️ WARNING: This deletes all data!
python database/migrate.py reset
python database/migrate.py up
```

## 📚 Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Database Migration Best Practices](https://flywaydb.org/documentation/concepts/migrations)
- [SQL Style Guide](https://www.sqlstyle.guide/)