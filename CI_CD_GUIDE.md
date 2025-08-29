# CI/CD Guide - Consolidated FastAPI Architecture

This guide covers the modernized CI/CD pipeline using consolidated Python scripts for the unified FastAPI backend architecture.

## Overview

The financial data analysis system includes an enterprise-grade CI/CD pipeline with comprehensive monitoring that:
- ✅ Consolidated CI operations into unified Python scripts (`scripts/ci_manager.py` and `scripts/manage.py`)
- ✅ Verifies FastAPI server functionality with health checks and performance monitoring
- ✅ Runs database migrations automatically during deployment with rollback capabilities
- ✅ Tests the complete data processing pipeline with performance profiling
- ✅ Supports GitHub Actions automated testing with PostgreSQL
- ✅ Multi-stage Docker builds with optimization and security hardening
- ✅ Real-time monitoring with metrics collection and error tracking
- ✅ Streamlined deployment with Railway, Docker, and Docker Compose

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

### 3. Docker Integration (`docker-compose.yml`)
Enterprise Docker setup with multi-stage builds:
- **Production**: Multi-stage build with frontend compilation and security hardening
- **Development**: Full development environment with PostgreSQL and Redis
- **Optimization**: Layer caching, minimal base images, non-root execution

```bash
# Docker operations
make docker-build      # Build optimized production image
make docker-dev        # Start PostgreSQL and Redis for development
make docker-dev-full   # Full containerized development environment
make docker-stop       # Stop all Docker services
```

### 4. Monitoring and Observability
Comprehensive monitoring system with real-time metrics:
- **Correlation tracking** across all requests with unique IDs
- **Performance monitoring** with automatic slow operation detection
- **Error tracking** with centralized analytics and alerting
- **System metrics** for CPU, memory, and disk usage

```bash
# Monitoring operations
make monitoring-health   # System health and performance metrics
make monitoring-metrics  # Application metrics dashboard
make monitoring-errors   # Error tracking and analytics
```

### 5. Make Integration
All operations are accessible via Make commands for developer convenience:

```bash
# Development workflow
make setup        # Complete setup with dependency resolution
make ci-check     # Full CI validation with monitoring
make health       # Application health check
make validate     # Configuration validation

# Testing
make test         # Run all tests
make test-unit    # Unit tests only
make test-db      # Database connection test

# Docker workflow
make docker-build      # Build production image
make docker-dev        # Start development services
make docker-stop       # Stop Docker services

# Monitoring
make monitoring-health   # Health and metrics dashboard
make monitoring-metrics  # Application performance metrics
make monitoring-errors   # Error tracking and analytics

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

## Enterprise Docker Architecture

### Multi-Stage Production Build

**Optimized Dockerfile Features:**
- **Frontend Build Stage**: Node.js 18 Alpine for TypeScript React + Tailwind compilation
- **Production Stage**: Python 3.11 slim with FastAPI backend
- **Security**: Non-root user execution, minimal attack surface
- **Optimization**: Layer caching, compressed builds, health checks

```dockerfile
# Multi-stage build example
FROM node:18-alpine AS frontend-builder
WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci --only=production
COPY client/ ./
RUN npm run build

FROM python:3.11-slim AS production
# Copy built frontend from build stage
COPY --from=frontend-builder /app/client/build ./client/build
```

### Docker Compose Development Environment

**Full Development Stack:**
```yaml
services:
  postgres:    # PostgreSQL 15 with health checks
  backend:     # FastAPI with volume mounts for development
  frontend-dev: # React dev server with hot reload (optional)
  redis:       # Redis caching (optional profile)
```

**Development Commands:**
```bash
# Start database services for development
make docker-dev

# Start full containerized development environment
make docker-dev-full

# Stop all services
make docker-stop

# Build optimized production image
make docker-build
```

## Monitoring and Observability

### Real-Time Monitoring System

**Correlation Tracking:**
- Unique correlation IDs for all requests
- Request/response logging with timing and context
- Cross-service request tracing

**Performance Monitoring:**
- Automatic slow operation detection (>2 seconds)
- Database query performance tracking
- System resource monitoring (CPU, memory, disk)
- Code profiling with memory usage analysis

**Error Tracking:**
- Centralized error collection with unique error IDs
- Automatic alerting for critical errors and high error rates
- Error analytics and pattern detection
- Stack trace preservation with context

### Monitoring APIs

**Health and Metrics Endpoints:**
```bash
# System health with performance data
curl http://localhost:4000/api/monitoring/metrics/health

# Application metrics summary
curl http://localhost:4000/api/monitoring/metrics

# Error tracking and analytics
curl http://localhost:4000/api/monitoring/errors/summary

# Slow operations analysis
curl http://localhost:4000/api/monitoring/errors/slow-operations
```

**Monitoring Commands:**
```bash
# Real-time monitoring via Make commands
make monitoring-health   # Comprehensive health dashboard
make monitoring-metrics  # Performance metrics overview
make monitoring-errors   # Error analytics and alerts
```

### Alert System

**Automated Alerting:**
- High error rate detection (>10 errors/minute)
- Repeated error patterns (>5 same error occurrences)
- Critical error immediate alerts
- System resource threshold warnings (CPU >80%, Memory >80%)

**Alert Log Files:**
- `logs/alerts.jsonl` - Structured alert events
- `logs/errors.jsonl` - Detailed error tracking
- `logs/metrics.jsonl` - Performance metrics history

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
1. **Backend Test** - FastAPI backend with PostgreSQL service using consolidated CI scripts
2. **Frontend Build** - TypeScript + React build and type checking

#### Features:
- **Backend**: PostgreSQL 15 service, Python 3.11+, FastAPI testing
- **Frontend**: Node.js 18+, TypeScript compilation, Tailwind CSS build
- Uses consolidated CI manager for all operations
- Streamlined workflow using Make commands

```yaml
# Backend workflow
- name: Setup Database
  run: make setup

- name: Run Tests
  run: make test

- name: CI Health Check
  run: make ci-check

# Frontend workflow  
- name: Setup Node.js
  uses: actions/setup-node@v3
  with:
    node-version: '18'

- name: Install Frontend Dependencies
  run: cd client && npm install

- name: TypeScript Type Check
  run: cd client && npx tsc --noEmit

- name: Build Frontend
  run: cd client && npm run build

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

#### Backend Development
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

#### Frontend Development
```bash
# TypeScript + React development
cd client

# Install dependencies
npm install

# TypeScript type checking
npx tsc --noEmit

# Development server with hot reload
npm start

# Production build
npm run build

# Integrated development (both servers)
make client  # React dev server (port 3000)
make server  # FastAPI server (port 4000)
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

#### Backend Development
1. **Use Make commands** for consistent operations (`make setup`, `make test`, `make ci-check`)
2. **Test migrations locally** before committing (`make test-db`)
3. **Run full CI validation** before pushing (`make ci-check`)
4. **Validate configurations** regularly (`make validate-yaml`)

#### Frontend Development
1. **TypeScript-first approach** - ensure type safety with `npx tsc --noEmit`
2. **Component-driven development** - build reusable TypeScript components
3. **Responsive design** - test across different screen sizes
4. **Build validation** - always test `npm run build` before deploying
5. **API integration testing** - verify all API calls work with backend

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

#### Backend Testing
1. **Run unit tests regularly** (`make test-unit`)
2. **Use integration testing** for pipeline validation
3. **Test database operations** independently (`make test-db`)
4. **Validate API endpoints** with health checks (`make health`)

#### Frontend Testing
1. **TypeScript compilation** - `npx tsc --noEmit` for type safety
2. **Build testing** - `npm run build` for production readiness
3. **Component testing** - React Testing Library for UI components
4. **API integration testing** - Test all API calls against running backend
5. **Cross-browser testing** - Test drag & drop functionality across browsers

## Frontend-Specific CI/CD Considerations

### TypeScript Build Pipeline
- **Type Safety**: All components are TypeScript with strict type checking
- **Build Optimization**: Webpack bundling with code splitting
- **Asset Optimization**: Tailwind CSS purging for minimal bundle size
- **Error Handling**: TypeScript compilation errors fail the build

### Modern UI Architecture
- **Component Library**: Reusable TypeScript components with Tailwind CSS
- **State Management**: Type-safe React Context with TypeScript interfaces
- **API Layer**: Strongly typed API calls with error handling
- **Responsive Design**: Mobile-first Tailwind CSS approach

### Deployment Considerations
- **Build Assets**: Static files generated in `client/build/`
- **Environment Variables**: `REACT_APP_API_URL` for API endpoint configuration
- **CDN Optimization**: Serve static assets from CDN for production
- **Browser Compatibility**: Modern browsers with ES6+ support

---

**For development setup, see `Developer_guide.md`**
**For database migration details, see migration system in `database/`**