# Developer Guide - Quick Start

A concise guide for developers to quickly get the financial data analysis system running locally.

## Prerequisites

- **Python** (v3.8+)
- **PostgreSQL** database
- **uv** - Python package manager ([install from uv.sh](https://docs.astral.sh/uv/))

## Quick Setup Commands

### 1. Clone Repository
```bash
git clone <repository-url>
cd financial-data-analysis
```

### 2. Python Virtual Environment Setup

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

### 3. Database Setup

```bash
# Create .env file with your database credentials
echo "DATABASE_URL=postgresql://username:password@localhost:5432/your_database" > .env
echo "ENVIRONMENT=development" >> .env
echo "PORT=4000" >> .env

# Apply database migrations (includes essential seed data)
source .venv/bin/activate
python database/migrate.py up

# Add comprehensive development data (optional but recommended)
python database/seed.py

# Check migration and seeding status
python database/migrate.py status
psql "$DATABASE_URL" -c "SELECT COUNT(*) as line_items FROM line_item_definitions;"
```

### 4. Start FastAPI Backend Server

```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Start FastAPI development server with auto-reload
python server/main.py

# OR use uvicorn directly from project root
uvicorn server.main:app --host 0.0.0.0 --port 4000 --reload
```

**Backend will be available at:** `http://localhost:4000`

### 5. Start React Client

```bash
# Open new terminal and navigate to client directory
cd client

# Create React environment file
echo "REACT_APP_API_URL=http://localhost:4000" > .env.local

# Install React dependencies
npm install

# Start React development server
npm start
```

**Frontend will be available at:** `http://localhost:3000`

## Development Commands Reference

### Python Virtual Environment Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Deactivate virtual environment
deactivate

# Install new Python package
uv pip install package_name

# Show installed packages
uv pip list

# Update requirements.txt after adding dependencies to pyproject.toml
uv pip compile pyproject.toml -o requirements.txt

# Sync environment with requirements.txt
uv pip sync requirements.txt
```

### FastAPI Backend Development Commands

```bash
# Development server (auto-restart on changes)
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 4000 --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 4000

# Run specific Python scripts directly (with venv active)
source .venv/bin/activate
python server/app/services/calc_metrics.py 1
python server/app/services/questions_engine.py 1
python server/app/services/report_generator.py 1 /path/to/output.pdf

# Check server health
curl http://localhost:4000/health

# Test file upload
curl -F "file=@../data/sample_data.csv" http://localhost:4000/api/upload

# Test report generation
curl -X POST http://localhost:4000/api/generate-report \
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
# Basic Migration Commands
source .venv/bin/activate

# Check migration status
python database/migrate.py status

# Apply all pending migrations
python database/migrate.py up

# Rollback last migration
python database/migrate.py down

# Create new migration
python database/migrate.py create "Add new feature"

# Update rollback SQL from migration files
python database/migrate.py update-rollback

# CI/CD Integration Commands
# Run migration system check
bash ci/00_migration_check.sh

# Apply migrations in CI/CD mode
bash ci/03_apply_schema.sh

# Run comprehensive integration test (includes migrations)
bash ci/12_comprehensive_check.sh

# Check deployment health
bash scripts/health-check.sh

# Database Testing
# Test database connection
python -c "
import sys
sys.path.append('server/scripts')
from utils import get_db_connection
with get_db_connection() as conn:
    print('✅ Database connection successful!')
"

# Check tables and data
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM financial_metrics;"
psql "$DATABASE_URL" -c "SELECT name FROM line_item_definitions;"

# See database/README.md for complete migration documentation
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
│       └── services/     # Business logic modules
│           ├── pipeline_processor.py
│           ├── calc_metrics.py
│           ├── report_generator.py
│           └── utils.py
├── scripts/               # General utility scripts
├── client/                # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   └── package.json
├── database/              # Database migrations
│   ├── migrate.py
│   ├── migrations/
│   └── seed.py
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

**Quick Start Summary:**
1. `uv venv && source .venv/bin/activate`
2. `uv pip install -r requirements.txt`
3. Set up `.env` with `DATABASE_URL`
4. `python database/migrate.py up && python database/seed.py`
5. `python server/main.py` (FastAPI backend)
6. `cd client && npm install && npm start` (React frontend)
7. Open `http://localhost:3000`

**Alternative using Make:**
1. `make setup` (installs deps + sets up database)
2. `make server` (FastAPI backend)
3. `make client` (React frontend)
4. Open `http://localhost:3000`