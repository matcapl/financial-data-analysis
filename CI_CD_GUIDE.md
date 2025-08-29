# CI/CD Guide - FastAPI Backend

This guide covers the comprehensive CI/CD pipeline for the unified FastAPI backend architecture.

## Overview

The financial data analysis system includes a robust CI/CD pipeline that:
- ✅ Verifies FastAPI server functionality before deployment
- ✅ Runs database migrations automatically during deployment
- ✅ Provides rollback capabilities for safe database changes
- ✅ Tests the complete data processing pipeline
- ✅ Supports multiple deployment targets (Railway, Docker, GitHub Actions)

## CI/CD Pipeline Components

### 1. Migration System Check (`ci/00_migration_check.sh`)
Pre-deployment verification script that ensures:
- Migration system accessibility
- Database connectivity
- Migration file integrity
- Rollback SQL coverage
- Python dependencies availability

```bash
# Run migration system check
bash ci/00_migration_check.sh
```

### 2. Schema Application (`ci/03_apply_schema.sh`)
Enhanced CI/CD migration runner that:
- Loads environment variables safely
- Checks migration status before applying
- Applies pending migrations
- Shows final migration status
- Updates rollback SQL (non-critical)

```bash
# Apply migrations in CI/CD mode
bash ci/03_apply_schema.sh
```

### 3. Comprehensive Testing (`ci/12_comprehensive_check.sh`)
Full integration test that includes:
- Migration system verification (calls `00_migration_check.sh`)
- YAML configuration validation
- Python script presence checks
- Database schema compatibility testing
- Data ingestion pipeline testing
- Metrics calculation testing
- Question generation testing
- Database integrity validation

```bash
# Run full integration test
bash ci/12_comprehensive_check.sh
```

## Deployment Scripts

### 1. Production Start (`scripts/deploy-start.sh`)
Production deployment script that:
- Runs database migrations before starting the app
- Updates rollback SQL
- Shows migration status
- Starts the FastAPI application

```bash
# Used automatically in railway.json
bash scripts/deploy-start.sh
```

### 2. Health Check (`scripts/health-check.sh`)
Post-deployment verification that checks:
- Database connectivity and migration status
- Application health endpoint
- Migration system status
- No pending migrations

```bash
# Check deployment health
bash scripts/health-check.sh
```

## Platform Integrations

### Railway Deployment

**Configuration (`railway.json`):**
```json
{
  "build": {
    "builder": "dockerfile",
    "dockerfilePath": "server/Dockerfile"
  },
  "deploy": {
    "startCommand": "bash scripts/deploy-start.sh"
  }
}
```

**Features:**
- Automatic migration execution on deployment
- Rollback SQL updates
- Health monitoring integration

### Docker Deployment

**Enhanced Dockerfile:**
```dockerfile
# Copy database migrations
COPY database ./database

# Migration system included in container
CMD ["bash", "scripts/deploy-start.sh"]
```

**Features:**
- All migration files included in image
- Production-ready Python environment with FastAPI
- Automatic migration execution on container start

### GitHub Actions

**CI/CD Pipeline (`.github/workflows/ci-cd.yml`):**

#### Jobs:
1. **Migration Check** - Verifies migration system with PostgreSQL service
2. **Full Integration** - Runs comprehensive tests with database
3. **Docker Build** - Tests container build and migration inclusion

#### Features:
- PostgreSQL 15 service for realistic testing
- Python 3.11+ environment with FastAPI and uvicorn
- Migration rollback testing
- Docker image structure validation

```yaml
# Example job configuration
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_USER: postgres
      POSTGRES_DB: financial_test
```

## Migration Safety Features

### 1. Pre-deployment Verification
- Migration system accessibility checks
- Database connectivity validation
- Migration file integrity verification
- Dependency availability confirmation

### 2. Rollback Capability
- All migrations include rollback SQL in `/*ROLLBACK_START ... ROLLBACK_END*/` format
- Automatic rollback SQL extraction and storage
- Safe rollback execution with `python database/migrate.py down`

### 3. Environment Isolation
- Separate test databases for CI/CD testing
- Environment variable isolation
- No cross-contamination between environments

### 4. Atomic Operations
- Migrations run in database transactions
- All-or-nothing migration application
- Consistent database state maintenance

### 5. Status Monitoring
- Migration status checks before and after deployment
- Health endpoint validation
- Pending migration detection and alerting

## Usage Examples

### Local Development
```bash
# Check migration system
bash ci/00_migration_check.sh

# Apply migrations
bash ci/03_apply_schema.sh

# Run full integration test
bash ci/12_comprehensive_check.sh

# Check health
bash scripts/health-check.sh
```

### CI/CD Pipeline
```yaml
# In GitHub Actions
- name: Run migration system check
  run: bash ci/00_migration_check.sh

- name: Run database migrations  
  run: bash ci/03_apply_schema.sh

- name: Test rollback functionality
  run: |
    python3 database/migrate.py down
    python3 database/migrate.py up
```

### Production Deployment
```bash
# Railway automatically executes:
bash scripts/deploy-start.sh

# Which includes:
# 1. Migration execution
# 2. Rollback SQL updates
# 3. Application startup
```

## Troubleshooting

### Migration Check Failures
```bash
# Check specific components
python3 database/migrate.py --help        # System accessibility
python3 database/migrate.py status        # Database connectivity
ls -la database/migrations/*.sql          # File integrity
```

### Deployment Issues
```bash
# Check environment variables
echo $DATABASE_URL

# Test migration manually
python3 database/migrate.py up

# Verify health
bash scripts/health-check.sh
```

### Rollback Operations
```bash
# Emergency rollback
python3 database/migrate.py down

# Check status after rollback
python3 database/migrate.py status

# Re-apply if needed
python3 database/migrate.py up
```

## Best Practices

### Development
1. **Always test migrations locally** before committing
2. **Include rollback SQL** in all new migrations
3. **Run CI checks** before pushing to main branch
4. **Test rollback functionality** for critical migrations

### Deployment
1. **Monitor deployment logs** for migration status
2. **Verify health checks** post-deployment
3. **Have rollback plan** for critical deployments
4. **Test in staging** before production deployment

### Monitoring
1. **Check migration status** regularly
2. **Monitor database health** continuously
3. **Alert on pending migrations** in production
4. **Track rollback operations** for audit purposes

---

**For complete migration system documentation, see `database/README.md`**
**For development setup, see `DEVELOPER_GUIDE.md`**