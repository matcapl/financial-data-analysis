# Developer Guide - Quick Start

A concise guide for developers to quickly get the financial data analysis system running locally.

## Prerequisites

- **Node.js** (v16+)
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
uv add pandas psycopg2-binary openpyxl fpdf2 pyyaml pathlib
```

### 3. Database Setup

```bash
# Create .env file with your database credentials
echo "DATABASE_URL=postgresql://username:password@localhost:5432/your_database" > .env
echo "NODE_ENV=development" >> .env
echo "PORT=4000" >> .env

# Apply database schema using the new migration system
source .venv/bin/activate
python database/migrate.py up

# Check migration status
python database/migrate.py status
```

### 4. Start Backend Server

```bash
# Navigate to server directory
cd server

# Install Node.js dependencies
npm install

# Start development server with hot reload
npm run dev
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
uv add package_name

# Remove Python package
uv remove package_name

# Show installed packages
uv pip list

# Update all packages
uv pip sync requirements.txt
```

### Backend Development Commands

```bash
cd server

# Development server (auto-restart on changes)
npm run dev

# Production mode
npm run start

# Install new Node.js dependency
npm install package-name

# Run specific Python scripts (with venv active)
source ../.venv/bin/activate
python scripts/calc_metrics.py 1
python scripts/questions_engine.py 1
python scripts/report_generator.py 1 /path/to/output.pdf

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
├── server/                 # Node.js backend
│   ├── api/
│   │   ├── index.js       # Main server
│   │   ├── upload-improved.js
│   │   └── generate-report.js
│   ├── scripts/           # Python processing
│   │   ├── pipeline_processor.py
│   │   ├── calc_metrics.py
│   │   └── report_generator.py
│   └── package.json
├── client/                 # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   └── package.json
├── .venv/                  # Python virtual environment
├── .env                    # Environment variables
└── data/                   # Sample data files
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

# Recreate schema
source .venv/bin/activate
python scripts/generate_schema.py
```

**Python Module Not Found**
```bash
# Ensure virtual environment is active and dependencies installed
source .venv/bin/activate
uv add pandas psycopg2-binary
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
2. `uv add pandas psycopg2-binary openpyxl fpdf2 pyyaml pathlib`
3. Set up `.env` with `DATABASE_URL`
4. `cd server && npm install && npm run dev`
5. `cd client && npm install && npm start`
6. Open `http://localhost:3000`