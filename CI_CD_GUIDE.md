# CI/CD Guide - Consolidated FastAPI Architecture

This guide covers the modernized CI/CD pipeline using consolidated Python scripts for the unified FastAPI backend architecture.

## Overview

The financial data analysis system includes a robust CI/CD pipeline that:
- ✅ Consolidated CI operations into unified Python scripts (`scripts/ci_manager.py` and `scripts/manage.py`)
- ✅ Verifies FastAPI server functionality with health checks
- ✅ Runs database migrations automatically during deployment
- ✅ Provides rollback capabilities for safe database changes
- ✅ Tests the complete data processing pipeline
- ✅ Supports GitHub Actions automated testing with PostgreSQL
- ✅ Streamlined deployment with Railway and Docker

## Consolidated CI/CD Architecture

### 1. Main CI Manager (`scripts/ci_manager.py`)
Unified CI/CD operations script that handles:
- Database setup and health checks
- Port management and cleanup
- Testing (unit and integration)
- Health monitoring
- Configuration validation
- Deployment operations

```bash
# Available commands
.venv/bin/python3 scripts/ci_manager.py health        # Health check
.venv/bin/python3 scripts/ci_manager.py db setup     # Database setup
.venv/bin/python3 scripts/ci_manager.py db check     # Database test
.venv/bin/python3 scripts/ci_manager.py test         # Run tests
.venv/bin/python3 scripts/ci_manager.py validate     # Config validation
.venv/bin/python3 scripts/ci_manager.py deploy       # Production deployment
.venv/bin/python3 scripts/ci_manager.py kill-ports   # Port cleanup
.venv/bin/python3 scripts/ci_manager.py check-all    # Full CI check
```

### 2. Data Management Tool (`scripts/manage.py`)
Consolidated data management utilities that handle:
- YAML configuration validation
- Period alias management
- Question generation
- Configuration file generation

```bash
# Available commands
.venv/bin/python3 scripts/manage.py validate-yaml    # Validate YAML files
.venv/bin/python3 scripts/manage.py aliases list     # List period aliases
.venv/bin/python3 scripts/manage.py questions        # Generate questions
.venv/bin/python3 scripts/manage.py generate-periods # Generate periods.yaml
```

### 3. Make Integration
All operations are accessible via Make commands for developer convenience:

```bash
# Development workflow
make setup        # Complete setup
make ci-check     # Full CI validation
make health       # Application health check
make validate     # Configuration validation

# Testing
make test         # Run all tests
make test-unit    # Unit tests only
make test-db      # Database connection test

# Data management
make aliases ARGS="list"                           # List aliases
make questions                                      # Generate questions
make validate-yaml                                 # Validate YAML
```

## Deployment Operations

### 1. Production Deployment
The CI manager handles production deployment operations:

```bash
# Production deployment with CI manager
.venv/bin/python3 scripts/ci_manager.py deploy

# Or via Make command
make deploy
```

**Deployment process:**
1. Database migration verification and application
2. Configuration validation
3. Health check verification
4. Application startup

### 2. Health Monitoring
Integrated health checks across the system:

```bash
# Application health check
.venv/bin/python3 scripts/ci_manager.py health

# Database connectivity test
.venv/bin/python3 scripts/ci_manager.py db check

# Or via Make commands
make health
make test-db
```

## Platform Integrations

### Railway Deployment

**Configuration (`railway.json`):**
```json
{
  "build": {
    "builder": "dockerfile",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": ".venv/bin/python3 server/main.py"
  }
}
```

**Features:**
- Simplified deployment using direct Python execution
- Automatic migration handling via startup logic
- Streamlined startup process

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

**CI/CD Pipeline (`.github/workflows/ci.yml`):**

#### Jobs:
1. **Test** - Full test suite with PostgreSQL service using consolidated CI scripts

#### Features:
- PostgreSQL 15 service for realistic testing
- Python 3.11+ environment with FastAPI dependencies
- Uses consolidated CI manager for all operations
- Streamlined workflow using Make commands

```yaml
# Workflow uses consolidated scripts
- name: Setup Database
  run: make setup

- name: Run Tests
  run: make test

- name: CI Health Check
  run: make ci-check

# PostgreSQL service
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

### Local Development Workflow
```bash
# Full setup and validation
make setup
make ci-check

# Direct CI manager usage
.venv/bin/python3 scripts/ci_manager.py db setup
.venv/bin/python3 scripts/ci_manager.py health
.venv/bin/python3 scripts/ci_manager.py test

# Data management
.venv/bin/python3 scripts/manage.py validate-yaml
.venv/bin/python3 scripts/manage.py questions
```

### CI/CD Pipeline (GitHub Actions)
```yaml
# Streamlined workflow using Make
- name: Setup Environment
  run: make setup

- name: Run Tests
  run: make test

- name: CI Health Check
  run: make ci-check

# Direct script usage for specific operations
- name: Database Migration Check
  run: .venv/bin/python3 scripts/ci_manager.py db check

- name: Validate Configuration
  run: .venv/bin/python3 scripts/ci_manager.py validate
```

### Production Deployment
```bash
# Railway deployment (simplified)
# Uses railway.json startCommand: ".venv/bin/python3 server/main.py"

# Manual deployment operations
.venv/bin/python3 scripts/ci_manager.py deploy

# Health verification post-deployment
.venv/bin/python3 scripts/ci_manager.py health
```

## Troubleshooting

### CI Manager Failures
```bash
# Debug CI operations
.venv/bin/python3 scripts/ci_manager.py db check     # Database connectivity
.venv/bin/python3 scripts/ci_manager.py validate     # Configuration validation
.venv/bin/python3 scripts/ci_manager.py health       # Application health

# Check individual components
.venv/bin/python3 database/migrate.py status         # Migration status
ls -la database/migrations/*.sql                     # Migration files
```

### Deployment Issues
```bash
# Check environment variables
echo $DATABASE_URL

# Test deployment process
.venv/bin/python3 scripts/ci_manager.py deploy

# Verify health
.venv/bin/python3 scripts/ci_manager.py health
```

### Database Issues
```bash
# Database setup and testing
.venv/bin/python3 scripts/ci_manager.py db setup
.venv/bin/python3 scripts/ci_manager.py db check

# Manual migration operations
.venv/bin/python3 database/migrate.py down
.venv/bin/python3 database/migrate.py status
.venv/bin/python3 database/migrate.py up
```

## Best Practices

### Development Workflow
1. **Use Make commands** for consistent operations (`make setup`, `make test`, `make ci-check`)
2. **Test migrations locally** before committing (`make test-db`)
3. **Run full CI validation** before pushing (`make ci-check`)
4. **Validate configurations** regularly (`make validate-yaml`)

### CI Script Usage
1. **Use consolidated scripts** instead of individual bash scripts
2. **Leverage CI manager** for all database and deployment operations
3. **Use management tool** for data-related operations
4. **Follow Make patterns** for team consistency

### Deployment
1. **Monitor deployment via CI manager** health checks
2. **Use deployment script** for production deployments
3. **Verify with health checks** post-deployment
4. **Maintain rollback capabilities** through migration system

### Testing
1. **Run unit tests regularly** (`make test-unit`)
2. **Use integration testing** for pipeline validation
3. **Test database operations** independently (`make test-db`)
4. **Validate API endpoints** with health checks (`make health`)

---

**For development setup, see `Developer_guide.md`**
**For database migration details, see migration system in `database/`**