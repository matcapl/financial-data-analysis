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
curl -F "file=@data/sample_data.csv" http://localhost:4000/api/v1/upload

# Test report generation
curl -X POST http://localhost:4000/api/v1/generate-report \
     -H "Content-Type: application/json" \
     -d '{"company_id":1}'
```

### Frontend Development Commands
```bash
cd client

# Development server
npm start

# Production build
npm run build

# Run tests
npm test

# Install new React dependency
npm install package-name
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
├── client/                # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
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