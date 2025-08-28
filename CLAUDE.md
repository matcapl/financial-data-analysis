# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a financial data analysis system that processes Excel/PDF files and generates analytical reports. The system has three main components:

### Frontend (React - client/)
- React client deployed on Vercel
- Handles file uploads and displays reports  
- Uses environment variable `REACT_APP_API_URL` to connect to backend

### Backend (Node.js + Python - server/)
- Express.js API server deployed on Railway (port 4000)
- Routes: `/api/upload`, `/api/generate-report`, `/health`, `/api/info`
- Orchestrates Python scripts for data processing
- Handles file uploads (10MB limit, .xlsx/.pdf/.csv only)

### Database (PostgreSQL)
- Hosted on Neon.tech (serverless Postgres)
- Schema generated from YAML configs in `config/`
- Tables: companies, periods, financial_metrics, derived_metrics, questions, etc.

## Data Processing Pipeline

The system follows a layered ingestion approach:

1. **Extraction** (`server/scripts/extraction.py`) - Raw data extraction from files
2. **Field Mapping** (`server/scripts/field_mapper.py`) - Maps raw fields to canonical metrics using `config/fields.yaml` and `config/taxonomy.yaml`
3. **Normalization** (`server/scripts/normalization.py`) - Normalizes periods/values using `config/periods.yaml`
4. **Persistence** (`server/scripts/persistence.py`) - Inserts data into database
5. **Metrics Calculation** (`server/scripts/calc_metrics.py`) - Computes derived metrics (MoM, QoQ, YoY, YTD)
6. **Question Generation** (`server/scripts/questions_engine.py`) - Generates analytical questions using `config/questions.yaml`
7. **Report Generation** (`server/scripts/report_generator.py`) - Creates PDF reports

## Key Configuration Files

All configuration is YAML-based in `config/`:

- `tables.yaml` - Database schema definitions
- `fields.yaml` - Column header mapping rules
- `taxonomy.yaml` - Canonical metric names and synonyms
- `periods.yaml` - Period normalization (converts "Feb 2025" → "2025-02")
- `observations.yaml` - Business rules and data quality checks
- `questions.yaml` - Question generation templates and thresholds

## Common Development Commands

### Build and Test
```bash
# Install dependencies
poetry install
cd server && npm install
cd ../client && npm install

# Run CI pipeline
./ci/01_validate_and_generate.sh    # Validate YAML and generate schema
./ci/02_drop_tables.sh              # Drop all database tables
./ci/03_apply_schema.sh             # Apply fresh schema
./ci/08_smoke_csv.sh                # Run smoke test with sample data
./ci/11_full_sample.sh              # Full integration test

# Alternative: Use makefile
make setup                          # Complete setup for new users
make server                         # Start API server (port 5000 - legacy, actual is 4000)
make client                         # Start React client (port 3000)
```

### Development Servers
```bash
# Start backend server
cd server && npm start              # Runs on port 4000

# Start frontend (separate terminal)
cd client && npm start              # Runs on port 3000

# Development with hot reload
cd server && npm run dev            # Uses nodemon
```

### Database Management
```bash
# Apply schema manually
psql "$DATABASE_URL" -f schema/001_financial_schema.sql
psql "$DATABASE_URL" -f schema/002_question_templates.sql

# Test database connection
python -c "from server.scripts.utils import get_db_connection; print('Connected:', get_db_connection().closed == 0)"
```

### Docker Development
```bash
# Build and run server container
docker build -t finance-server -f server/Dockerfile .
docker run --rm --env-file .env -p 4000:4000 finance-server

# Test container endpoints
curl http://localhost:4000/health
curl -F "file=@data/financial_data_template.csv" http://localhost:4000/api/upload
```

### Testing
```bash
# Health check
curl http://localhost:4000/health

# Upload test file
curl -F "file=@data/financial_data_template.csv" http://localhost:4000/api/upload

# Generate report
curl -X POST http://localhost:4000/api/generate-report -H "Content-Type: application/json" -d '{"company_id":1}'

# Check database contents
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM financial_metrics;"
```

## Code Architecture Patterns

### Python Scripts Location
All data processing scripts are in `server/scripts/`. Common utilities are in `server/scripts/utils.py`.

### Database Connection
Use `get_db_connection()` from `server/scripts/utils.py` for consistent database connections.

### Error Handling
API returns structured JSON errors. Python scripts log to console and return exit codes.

### File Processing
- Upload files go to `server/Uploads/`
- Generated reports go to `server/reports/`
- Sample data files in `data/`

### Configuration Updates
When changing YAML configs:
1. Run `python scripts/validate_yaml.py`
2. Run `python scripts/generate_schema.py` 
3. Apply new schema with `./ci/02_drop_tables.sh` then `./ci/03_apply_schema.sh`

## Important Notes

- The system is split across 3 hosting platforms: Vercel (frontend), Railway (backend), Neon.tech (database)
- Environment variables must be configured separately for each platform
- Python scripts are called as child processes from Node.js
- Reports are uploaded to Vercel Blob storage for persistence
- Database schema is auto-generated from YAML configs - never edit SQL files directly
- All financial metrics follow a canonical naming convention defined in `config/taxonomy.yaml`

## Troubleshooting

### Port Issues
```bash
make kill-ports                     # Kill processes on ports 3000 and 5000
lsof -ti:4000 | xargs kill -9       # Kill specific port
```

### Database Issues
- Check `DATABASE_URL` environment variable
- Verify schema with `psql "$DATABASE_URL" -c "\dt"`
- Reset schema with CI scripts in order

### Docker Issues
- Clear cache: `docker system prune -a`
- Check logs: `docker logs $(docker ps -q --filter "ancestor=finance-server")`

### File Upload Issues
- Check file size (10MB limit)
- Verify file type (.xlsx, .pdf, .csv only)
- Ensure Uploads directory exists and is writable