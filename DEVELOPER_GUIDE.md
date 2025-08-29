# Developer Guide - Quick Start

A concise guide for developers to quickly get the financial data analysis system running locally.

## Prerequisites

- **Python** (v3.8+)
- **PostgreSQL** database
- **uv** - Python package manager ([install from uv.sh](https://docs.astral.sh/uv/))

## Quick Setup Commands

### Option A: Make Commands (Recommended)
```bash
# Clone repository
git clone <repository-url>
cd financial-data-analysis

# Complete setup (installs dependencies + database setup)
make setup

# Start servers (in separate terminals)
make server    # FastAPI backend (port 4000)
make client    # React frontend (port 3000)
```

### Option B: Manual Setup

#### 1. Clone Repository
```bash
git clone <repository-url>
cd financial-data-analysis
```

#### 2. Python Environment Setup
```bash
# Create virtual environment using uv
uv venv

# Activate virtual environment
source .venv/bin/activate     # macOS/Linux
# OR
.venv\Scripts\activate        # Windows

# Install Python dependencies
uv pip install -r requirements.txt
```

#### 3. Database Setup
```bash
# Create .env file with your database credentials
echo "DATABASE_URL=postgresql://username:password@localhost:5432/your_database" > .env
echo "ENVIRONMENT=development" >> .env
echo "PORT=4000" >> .env

# Apply database migrations (includes essential seed data)
.venv/bin/python3 database/migrate.py up

# Add comprehensive development data (optional but recommended)
.venv/bin/python3 database/seed.py

# Check migration and seeding status
.venv/bin/python3 database/migrate.py status
```

#### 4. Start FastAPI Backend Server
```bash
# Start FastAPI development server
.venv/bin/python3 server/main.py

# OR use uvicorn directly
uvicorn server.main:app --host 0.0.0.0 --port 4000 --reload
```

**Backend will be available at:** `http://localhost:4000`

#### 5. Start React Client
```bash
# Open new terminal and navigate to client directory
cd client

# Install React dependencies
npm install

# Start React development server
npm start
```

**Frontend will be available at:** `http://localhost:3000`

## Development Commands Reference

### Make Commands (Recommended)
```bash
# Setup and dependencies
make setup        # Complete setup for new developers
make install      # Install Python dependencies only
make kill-ports   # Kill processes on ports 3000 and 4000

# Development servers
make server       # Start FastAPI server (port 4000)
make client       # Start React client (port 3000)

# Testing
make test         # Run all tests
make test-unit    # Run unit tests only
make test-db      # Test database connection
make test-api     # Test API endpoints
make health       # Check application health

# CI/CD operations
make ci-check     # Run full CI health check
make deploy       # Production deployment
make validate     # Validate configuration

# Data management
make aliases ARGS="list"                    # List period aliases
make aliases ARGS="add --alias Q1 --canonical 2025-Q1"  # Add alias
make questions    # Generate analytical questions
make validate-yaml # Validate YAML configuration files
make generate-periods # Generate periods.yaml

# Utilities
make clean        # Clean up generated files
```

### Direct Python Commands
```bash
# Always use .venv/bin/python3 for consistency

# Database operations
.venv/bin/python3 database/migrate.py status
.venv/bin/python3 database/migrate.py up
.venv/bin/python3 database/seed.py

# CI management
.venv/bin/python3 scripts/ci_manager.py health
.venv/bin/python3 scripts/ci_manager.py db check
.venv/bin/python3 scripts/ci_manager.py test

# Data management
.venv/bin/python3 scripts/manage.py validate-yaml
.venv/bin/python3 scripts/manage.py questions

# Direct service execution
.venv/bin/python3 server/app/services/calc_metrics.py 1
.venv/bin/python3 server/app/services/questions_engine.py 1
.venv/bin/python3 server/app/services/report_generator.py 1
```

### API Testing Commands
```bash
# Health check
curl http://localhost:4000/health

# Test file upload
curl -F "file=@data/sample_data.csv" -F "company_id=1" http://localhost:4000/api/upload

# Test report generation
curl -X POST http://localhost:4000/api/generate-report \
     -H "Content-Type: application/json" \
     -d '{"company_id":1}'
```

### TypeScript React Frontend Commands
```bash
cd client

# Development server with TypeScript compilation and hot reload
npm start

# TypeScript type checking (no build)
npx tsc --noEmit

# Production build with TypeScript + Tailwind CSS
npm run build

# Run React tests with TypeScript support
npm test

# Install new dependency (with compatibility fix)
npm install package-name --legacy-peer-deps

# Install TypeScript types for dependency
npm install @types/package-name --legacy-peer-deps

# Tailwind CSS development
# Classes are compiled automatically during npm start
# Custom styles in src/index.css using @layer directives

# Dependency troubleshooting
rm -rf node_modules package-lock.json && npm install --legacy-peer-deps
```

### Database Commands

The system uses **database migrations** with full CI/CD integration and rollback capability.

```bash
# Migration Commands (using make)
make test-db      # Test database connection

# Direct migration commands
.venv/bin/python3 database/migrate.py status
.venv/bin/python3 database/migrate.py up
.venv/bin/python3 database/migrate.py down
.venv/bin/python3 database/migrate.py create "Add new feature"
.venv/bin/python3 database/migrate.py update-rollback

# Database seeding
.venv/bin/python3 database/seed.py

# CI/CD Integration using consolidated scripts
.venv/bin/python3 scripts/ci_manager.py db setup    # Setup database
.venv/bin/python3 scripts/ci_manager.py db check    # Test connection
.venv/bin/python3 scripts/ci_manager.py health      # Health check
.venv/bin/python3 scripts/ci_manager.py validate    # Validate config

# Database Testing
# Test database connection
.venv/bin/python3 -c "
import sys
sys.path.append('server/app/services')
from utils import get_db_connection
with get_db_connection() as conn:
    print('✅ Database connection successful!')
"

# Check tables and data
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM financial_metrics;"
psql "$DATABASE_URL" -c "SELECT name FROM line_item_definitions;"
```

#### CI/CD Migration Features

**Production Deployment:**
- `railway.json` uses `scripts/deploy-start.sh` - automatically runs migrations before app startup
- Docker includes all migration files via `COPY database ./database`
- GitHub Actions `.github/workflows/ci-cd.yml` provides comprehensive CI/CD pipeline

**Safety Features:**
- Pre-deployment migration system verification
- All migrations include rollback SQL for safe rollbacks
- Health checks verify migration status post-deployment
- Environment isolation with separate test databases
- Atomic migrations with transaction consistency

## File Structure

```
financial-data-analysis/
├── server/                # FastAPI backend server
│   ├── main.py           # FastAPI application entry point
│   └── app/              # Application package
│       ├── api/          # API routers and endpoints
│       │   └── v1/       # API v1 routes
│       ├── core/         # Core application components
│       │   ├── config.py # Pydantic configuration
│       │   └── background_tasks.py
│       ├── models/       # Data models
│       │   ├── api/      # API request/response models
│       │   └── domain/   # Business domain models
│       ├── repositories/ # Data access layer
│       └── services/     # Business logic modules
│           ├── pipeline_processor.py
│           ├── calc_metrics.py
│           ├── report_generator.py
│           └── utils.py
├── scripts/               # Consolidated CI/CD scripts
│   ├── ci_manager.py     # Main CI/CD operations
│   └── manage.py         # Data management utilities
├── client/                # Modern TypeScript React frontend
│   ├── src/
│   │   ├── App.tsx           # Main app component (TypeScript)
│   │   ├── index.tsx         # React entry point
│   │   ├── types/            # TypeScript type definitions
│   │   │   └── index.ts      # Shared interfaces
│   │   ├── contexts/         # React Context (TypeScript)
│   │   │   └── AppContext.tsx
│   │   └── components/       # TypeScript React components
│   │       ├── FileUpload.tsx    # Drag & drop upload
│   │       ├── ReportPreview.tsx # Report management
│   │       ├── LoadingSpinner.tsx
│   │       ├── StatusMessage.tsx
│   │       └── ProgressIndicator.tsx
│   ├── tsconfig.json     # TypeScript configuration
│   ├── tailwind.config.js # Tailwind CSS config
│   ├── postcss.config.js # PostCSS config
│   └── package.json
├── database/              # Database migrations
│   ├── migrate.py        # Migration management
│   ├── migrations/       # SQL migration files
│   └── seed.py          # Comprehensive seed data
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── conftest.py       # Test configuration
├── .github/workflows/     # GitHub Actions CI
├── config/                # YAML configurations
├── .venv/                 # Python virtual environment
├── .env                   # Environment variables
└── data/                  # Sample data files
```

## Modern TypeScript Frontend Guide

### Technologies Used
- **TypeScript**: Full type safety and enhanced developer experience
- **React 18**: Modern React with hooks and concurrent features
- **Tailwind CSS**: Utility-first CSS framework with custom design system
- **PostCSS**: CSS processing for Tailwind optimizations
- **Modern Build Tools**: Create React App with TypeScript support

### Key Features
- **Type-Safe Components**: All React components written in TypeScript
- **Drag & Drop Upload**: Advanced file upload with visual feedback
- **Responsive Design**: Mobile-first design with Tailwind CSS
- **Real-time Progress**: Step-by-step visual progress indicators
- **Error Handling**: User-friendly error states and messaging
- **Modern UI**: Gradients, animations, and glassmorphism effects

### Development Workflow
```bash
# Frontend development setup
cd client

# Install all dependencies (TypeScript, React, Tailwind)
npm install

# Development server with hot reload
npm start  # Available at http://localhost:3000

# Type checking without build
npx tsc --noEmit

# Production build
npm run build
```

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/database
NODE_ENV=development
PORT=4000
# Optional for production:
# VERCEL_BLOB_TOKEN=your_token
```

### Frontend (client/.env.local)
```bash
REACT_APP_API_URL=http://localhost:4000
```

## Testing the System

### 1. Upload Financial Data
- Go to `http://localhost:3000`
- Enter a company ID (e.g., `1`)
- Upload a CSV/Excel file from the `data/` directory
- Monitor the 6-stage processing pipeline

### 2. Generate Reports
- After successful upload, click "Generate Report"
- PDF reports are saved in `reports/` directory
- Download link will be provided

### 3. API Testing
```bash
# Health check
curl http://localhost:4000/health

# Upload test file
curl -F "file=@data/sample_data.csv" http://localhost:4000/api/upload

# Generate report
curl -X POST http://localhost:4000/api/generate-report \
     -H "Content-Type: application/json" \
     -d '{"company_id":1}'
```

## Docker Development

### Docker Compose Setup
```bash
# Start PostgreSQL and Redis for development
make docker-dev

# Start full containerized development environment
make docker-dev-full

# Stop all Docker services
make docker-stop

# Build production Docker image
make docker-build
```

### Docker Development Workflow
```bash
# Option 1: Hybrid development (recommended)
make docker-dev          # Start database services
make server              # Local FastAPI server
make client              # Local React development server

# Option 2: Fully containerized development
make docker-dev-full     # Everything in containers

# Option 3: Production testing
make docker-build        # Build production image
docker run -p 4000:4000 financial-data-analysis:latest
```

## Monitoring and Observability

### Real-Time Monitoring
```bash
# System health and performance metrics
make monitoring-health

# Application metrics and performance data
make monitoring-metrics

# Error tracking and analytics
make monitoring-errors

# Manual API calls for detailed monitoring
curl http://localhost:4000/api/monitoring/metrics/health
curl http://localhost:4000/api/monitoring/errors/summary
curl http://localhost:4000/api/monitoring/errors/slow-operations
```

### Performance Monitoring Features
- **Correlation IDs**: Track requests across the entire system
- **Automatic Timing**: All API requests and database queries timed automatically
- **Slow Operation Detection**: Alerts for operations taking >2 seconds
- **System Resource Monitoring**: CPU, memory, and disk usage tracking
- **Error Analytics**: Centralized error tracking with pattern detection

### Monitoring Files and Logs
```bash
# Structured log files (JSON format)
tail -f logs/financial-api-enhanced.log         # Application logs with correlation IDs
tail -f logs/metrics.jsonl                      # Performance metrics
tail -f logs/errors.jsonl                       # Error tracking
tail -f logs/alerts.jsonl                       # Alert events

# Legacy logs (for compatibility)
tail -f logs/financial-data-api.log             # Standard application logs
tail -f logs/pipeline-processor.log             # Data processing logs
```

## Troubleshooting

### Common Issues

**Virtual Environment Not Activated**
```bash
# Always activate before running Python scripts
source .venv/bin/activate
```

**Port Already in Use**
```bash
# Kill processes on ports
lsof -ti:3000 | xargs kill -9  # React
lsof -ti:4000 | xargs kill -9  # Backend
```

**Database Connection Error**
```bash
# Test database connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Apply/reapply migrations
source .venv/bin/activate
python database/migrate.py up

# Add comprehensive seed data for development
python database/seed.py
```

**Python Module Not Found**
```bash
# Ensure virtual environment is active and dependencies installed
source .venv/bin/activate
uv pip install -r requirements.txt

# For monitoring dependencies specifically
uv pip install psutil==6.1.0
```

**React TypeScript Build Issues**
```bash
# Clean and reinstall with compatibility fixes
cd client
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps

# Check TypeScript compilation
npx tsc --noEmit

# Force dependency resolution (if needed)
npm install --legacy-peer-deps --force
```

**Docker Issues**
```bash
# Clean Docker environment
make docker-stop
docker system prune -f

# Rebuild from scratch
make docker-build

# Check container logs
docker-compose logs backend
docker-compose logs postgres
```

**Monitoring Issues**
```bash
# Check monitoring endpoints
curl http://localhost:4000/health
curl http://localhost:4000/api/monitoring/metrics/health

# Check log files for errors
tail -f logs/financial-api-enhanced.log
tail -f logs/errors.jsonl

# Verify psutil dependency
.venv/bin/python3 -c "import psutil; print('✅ psutil working')"
```

### Development Tips

1. **Keep Virtual Environment Active**: Always run `source .venv/bin/activate` before Python commands
2. **Monitor Logs**: Both server and client show detailed logs in the terminal
3. **Database Inspection**: Use a PostgreSQL client to view processed data
4. **File Permissions**: Ensure uploaded files in `data/` directory are readable

## Production Deployment

For production deployment, see the main README.md file which covers:
- Railway deployment for backend
- Vercel deployment for frontend
- Environment variable configuration
- Database migration procedures

---

**Quick Start Summary (Recommended):**
1. `make setup` (installs deps + sets up database)
2. `make server` (FastAPI backend)
3. `make client` (React frontend)
4. Open `http://localhost:3000`

**Manual Alternative:**
1. `uv venv && source .venv/bin/activate`
2. `uv pip install -r requirements.txt`
3. Set up `.env` with `DATABASE_URL`
4. `.venv/bin/python3 database/migrate.py up && .venv/bin/python3 database/seed.py`
5. `.venv/bin/python3 server/main.py` (FastAPI backend)
6. `cd client && npm install && npm start` (React frontend)
7. Open `http://localhost:3000`