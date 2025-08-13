# Financial Data Analysis System

This repository hosts a system for analyzing financial data from Excel and PDF files. It calculates key metrics like Revenue, Gross Profit, and EBITDA, generates insightful questions, and produces PDF reports. Deployable on Vercel, it features a React front-end for user interaction and a Node.js back-end for processing, with Python scripts handling data ingestion and report generation.

## Methodology

The system operates through these key steps:

1. **Data Ingestion**: Custom Python scripts (`ingest_xlsx.py` and `ingest_pdf.py`) process Excel and PDF files, extracting financial data.
2. **Metric Calculation**: Scripts (`calc_metrics.py`) compute financial metrics based on the ingested data.
3. **Question Generation**: The `questions_engine.py` script creates questions from the metrics to drive deeper analysis.
4. **Report Generation**: The `report_generator.py` script compiles metrics and questions into PDF reports, stored and served via Vercel Blob.

Data is managed in a PostgreSQL database with tables for companies, periods, financial metrics, derived metrics, questions, and reports, as defined in `001_financial_schema.sql` and `002_question_templates.sql`.

<!-- Running make db after cloning guarantees that every new developer has the schema and role in place before touching the UI. -->

This project is split into three specialized hosting environments to leverage each platform’s strengths. The React front-end is deployed on Vercel, which excels at serving static assets and delivering global CDN performance. Vercel builds the React app from the client/ folder, and rewrites all incoming routes to the compiled client/build directory. Environment variables (e.g. REACT_APP_API_URL) point the front-end to the back-end API without embedding secrets in source code.
The Express/Node API with embedded Python data-processing scripts is hosted on Railway, which supports long-running processes, containerized builds, custom ports, and direct PostgreSQL connections. Railway runs the server/api/index.js entrypoint and routes all /health, /api/*, and static assets through this single service. By running on Railway, your Python ingestion/calculation scripts execute reliably in a full Node + Python environment, unencumbered by Vercel’s serverless timeouts and stateless file system.
The PostgreSQL database is managed by Neon.tech, a serverless Postgres service with a generous free tier. Neon provides secure, channel-bound SSL connections and scales automatically. Schemas for financial metrics and question templates are applied directly to Neon via schema/ SQL files, ensuring your data persists independently of application hosts.
Points of Failure & Lessons Learned
Serverless Limitations – Vercel’s functions are ill-suited for Python-backed pipelines; child-processes and file I/O frequently exceed timeouts and lose local state.
Routing Configuration – Custom vercel.json builds and rewrites can override dashboard settings, leading to 404 or authentication walls if entrypoints aren’t precisely defined.
Environment Management – Mixing multiple CLI-generated .vercel/ metadata folders caused confusion; isolating the front-end on Vercel and back-end on Railway clarified which platform handles each component.
Database Connectivity – Local Postgres worked in development, but deploying required a hosted database. Neon.tech’s serverless Postgres offered a drop-in replacement, but environment variables must be quoted correctly and scoped to each hosting platform.
By aligning each part of the stack with the platform that best supports its runtime needs—static React on Vercel, dynamic Python/Node API on Railway, and serverless Postgres on Neon—this architecture maximizes reliability, performance, and developer productivity.

## Technologies

- **Front-End**
  - React app for user interaction and display (`client/` directory).
  - Environment variables (like `REACT_APP_API_URL`) point at backend API.

- **Back-End**
  - NodeJS/Express server handles HTTP API, file upload, task orchestration (`server/server.js`).
  - Invokes Python scripts for heavy-lifting (ingestion, metrics, analytics) (`server/scripts/` directory).

- **Middle/Glue**
  - Python scripts run in child-process or direct mode.
  - PostgreSQL DB for persistent analytics/state.

- **Data Tools**
  - Schema generator scripts (`config/` + `scripts/` -> `schema/` directory).
  - Config validation tools.
  - Smoke/integration test runner scripts.

- **Docker** (Dev/test infra)
- **YAML-based config** (for schema, mappings)
- **Shell (bash) scripts** for CI
- **Deployment**: Vercel for hosting and scalability.


# Complete Setup Guide: Financial Data Analysis System

## Prerequisites
- Git
- Docker Desktop
- Node.js 18+
- Python 3.10+
- A terminal/command line

## Step 1: Clone and Setup Repository

```bash
# 1. Clone the repository
git clone https://github.com/matcapl/financial-data-analysis.git
cd financial-data-analysis

# 2. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip setuptools wheel

# 3.1 IF you already HAVE poetry installed globally: Ensure poetry uses this active venv rather than creating its own
poetry config virtualenvs.create false --local
# OR 
# 3.2. IF you DO NOT have poetry installed: Install the Poetry CLI into this venv 
pip install poetry

# 4. Install project dependencies as defined in pyproject.toml
poetry install

# 5. Install Node.js dependencies
cd server
npm install
cd ..
```

## Step 2: Setup Database (NeonDB - Free Tier)

1. **Sign up for NeonDB**: Go to https://neon.tech and create a free account
2. **Create a new project**: Choose your region and project name
3. **Get connection string**: Copy the connection string from the dashboard
4. **Apply database schema**:
   ```bash
   # Use the connection string from Neon dashboard
   psql "postgresql://username:password@ep-xxx.neon.tech:5432/database?sslmode=require" -f schema/001_financial_schema.sql
   psql "postgresql://username:password@ep-xxx.neon.tech:5432/database?sslmode=require" -f schema/002_question_templates.sql
   ```

question_templates.sql must be deployed with matching 001_financial_schema.sql.
If changes to metric definitions occur in the schema, corresponding question templates updates should be part of the same PR and deployment.

psql "$LOCAL_DATABASE_URL" -f schema/001_financial_schema.sql
psql "$LOCAL_DATABASE_URL" -f schema/002_question_templates.sql

psql "$DATABASE_URL" -f schema/001_financial_schema.sql
psql "$DATABASE_URL" -f schema/002_question_templates.sql


## Step 3: Environment Configuration

Create `.env` file in project root:
```bash
echo "DATABASE_URL=postgresql://your_user:your_password@ep-xxx.neon.tech:5432/your_db?sslmode=require" > .env
```

## Step 4: Build and Test Locally

```bash
# Build Docker image
docker build -t finance-server -f server/Dockerfile .

# Find and kill process on a port
lsof -ti:4000 | xargs -r kill -9  

# Check Docker is open
open -a Docker

# Run container
docker run --rm --env-file .env -p 4000:4000 finance-server &
sleep 10
# sleep 5 or sleep 10 is optional - gives cursor for running commands in terminal but lose tail

# OR, if troubleshooting
# Stop any running container named finance-server (if you gave it a name)
docker stop finance-server 2>/dev/null || true

# Or kill any container using that image
docker ps -q --filter ancestor=finance-server | xargs -r docker stop

# Then rebuild and run
docker build -t finance-server -f server/Dockerfile .
docker run --rm --env-file .env -p 4000:4000 --name finance-server finance-server &
sleep 10

# Test health endpoint
curl http://localhost:4000/health

# Inspect available endpoints
curl http://localhost:4000/api/info

# Test file upload
for file in data/*; do
  echo "→ Uploading $file"
  curl -F "file=@$file" http://localhost:4000/api/upload
done
# or point to specific file if prefered
curl -F "file=@data/financial_data_template.csv" http://localhost:4000/api/upload

# Test database connection and contents
psql "$DATABASE_URL" -c "SELECT current_database();"
psql "$DATABASE_URL" -c "\dt public.*"

# Check the contents of first 20 rows of every table
psql "$DATABASE_URL" <<'SQL'
DO $$
DECLARE
  tbl RECORD;
  col_list TEXT;
  sample RECORD;
BEGIN
  FOR tbl IN
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
  LOOP
    -- Table name
    RAISE NOTICE '=== Table: %', tbl.table_name;
    -- Columns
    SELECT string_agg(column_name, ', ')
      INTO col_list
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = tbl.table_name;
    RAISE NOTICE 'Columns: %', col_list;
    -- Sample rows
    FOR sample IN
      EXECUTE format(
        'SELECT * FROM %I.%I LIMIT 20',
        'public',
        tbl.table_name
      )
    LOOP
      RAISE NOTICE '%', row_to_json(sample);
    END LOOP;
  END LOOP;
END
$$;
SQL

docker run --rm --env-file .env -p 4000:4000 finance-server &
sleep 5
psql "$DATABASE_URL" -c "\dt public.*"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM financial_metrics;"


# Test report generation
curl -X POST http://localhost:4000/api/generate-report \
     -H "Content-Type: application/json" \
     -d '{"company_id":1}'
```

docker logs --tail 50 finance-server_ci
docker logs --tail 250 finance-server_ci

if docker is complaining finance-server_ci is still running, must remove or rename teh existing one first:

docker rm -f finance-server_ci


## Step 5: Deploy to Railway (Optional - for Production)

1. **Sign up for Railway**: Go to https://railway.app and create account
2. **Install Railway CLI**: `npm install -g @railway/cli`
3. **Deploy**:
   ```bash
   cd server
   railway login
   railway new
   
   # Set environment variable in Railway dashboard:
   # DATABASE_URL=your_neon_connection_string
   
   railway up --dockerfile Dockerfile
   ```

## Step 6: Deploy Frontend to Vercel (Optional)

1. **Sign up for Vercel**: Go to https://vercel.com and create account
2. **Configure and deploy**:
   ```bash
   cd client
   echo "REACT_APP_API_URL=https://your-railway-url.up.railway.app" > .env.production
   npm run build
   npx vercel --prod
   ```

## Expected Test Results

### Health Check:
```json
{"status":"ok","timestamp":"2025-08-01T11:41:01.225Z","port":4000,"environment":"development"}
```

### File Upload Success:
```json
{
  "message":"File processed successfully! All pipeline steps completed.",
  "filename":"financial_data_template.csv",
  "company_id":1,
  "processing_steps":[
    "✓ File uploaded and validated",
    "✓ Data ingested from file", 
    "✓ Metrics calculated",
    "✓ Questions generated"
  ]
}
```

### Report Generation Success:
```json
{
  "message": "Report generated successfully",
  "company_id": 1,
  "report_filename": "report_1_1722513661225.pdf",
  "processing_steps": [
    "✓ Data availability verified",
    "✓ Metrics calculated", 
    "✓ Questions generated",
    "✓ PDF report created"
  ]
}
```

## Troubleshooting

### Database Connection Issues:
```bash
# Test connection string manually
psql "your_database_url_here" -c "SELECT 1;"
```

### Docker Issues:
```bash
# Clear Docker cache
docker system prune -a

# Check container logs
docker logs $(docker ps -q --filter "ancestor=finance-server")
```

### Port Conflicts:
```bash
# Find and kill processes on port 4000
lsof -ti:4000 | xargs kill -9
```



- **CI (Continuous Integration):** An automated process that builds and tests your code on each commit, ensuring new changes don’t break existing functionality.  
- **`set -euo pipefail`:**  
  - `-e` stops the script if any command exits with a non-zero status.  
  - `-u` treats unset variables as errors.  
  - `-o pipefail` returns failure if any command in a pipeline fails.  
This combination makes your script *fail fast* and avoids hidden errors.

The smoke test automates these core steps end-to-end:

1. **Prepare a Known Input**  
   - Generates a minimal CSV (`smoke.csv`) containing exactly one “Revenue” row for February 2025 with a value of 2,390,873.

2. **Seed Master Data**  
   - Ensures your database has entries for the three metrics (“Revenue,” “Gross Profit,” “EBITDA”) in `line_item_definitions`.

3. **Start the API Server**  
   - Builds the Docker image (or uses your local server) and launches it on port 4000.

4. **Upload the Test File**  
   - Calls `POST /api/upload` with `smoke.csv`, triggering ingestion, metric calculation, and question generation.

5. **Verify the Result**  
   - Queries the database for a “Revenue” metric record in the period “Feb 2025” and formats it as Excel would (with commas and two decimals).  
   - Compares this formatted value against the expected string “2,390,873.00.”

6. **Clean Up**  
   - Stops the test server container.

Running this against **your local database** uses the same commands but skips the Docker build/run steps. Pointing `$DATABASE_URL` at Neon (external) versus `localhost:5432` (local) is the only variable—everything else is identical. Docker simply packages your code and environment so the test works *consistently* for anyone, wherever they run it.

What’s essential now:
- Confirming that single revenue datapoint flows through ingestion and lands in `financial_metrics`.
- Automating that check so it fails loudly if anything in the pipeline breaks.

What’s distracting:
- Deep dives into PDF parsing variants, question‐generation details, or undici/Blob credential errors.  
- Multiple iterations on decimal‐stripping versus formatting—pick one format (`to_char(..., 'FM9G999G999D00')`) and standardize.  

Focus on solidifying this one smoke test. Once it reliably passes against both your local and your Neon database, you’ll have confidence the core ingestion works. All other concerns—fully parsing board packs, generating nuanced questions—can proceed once the pipeline’s foundation is verified.


# Expert Code Review and QA Test Plan for Financial Data Analysis System


## Intended Functionality

1. **Derived Metrics Calculation**  
   - Month-over-Month, Quarter-over-Quarter, Year-over-Year, Year-to-Date, and variance metrics computed by `calc_metrics.py`.

2. **Automatic Question Generation**  
   - `questions_engine.py` applies threshold rules (e.g., ±10% variance) to generate targeted analytical questions for each metric.

3. **PDF Report Bundling**  
   - `report_generator.py` assembles metric tables and generated questions into a formatted PDF.

4. **Blob Upload for Reports**  
   - `generate-report.js` pushes the generated PDF to a Vercel Blob container and returns the accessible URL.

## Comprehensive Test Plan

The following 20 tests progress from high-level smoke tests through detailed unit and integration checks.

| #  | Test Description                                        | Command / API Call                                                                                         | Expected Outcome / Assertion                                                                                                                                         |
|----|---------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | **Smoke Test: Core Pipeline**                           | `./ci/smoke_test.sh`                                                                                         | Prints “Smoke test passed: revenue=2390873” and exits `0`. Smoke CSV ingested end-to-end into `financial_metrics`.                                                    |
| 2  | **Health Endpoint**                                     | `curl -s http://localhost:4000/health`                                                                       | JSON `{ "status":"ok", ... }`.                                                                                                                                       |
| 3  | **API Info Endpoint**                                   | `curl -s http://localhost:4000/api/info`                                                                     | Returns Express-configured routes or version info.                                                                                                                   |
| 4  | **Upload CSV Template**                                 | `curl -F "file=@data/financial_data_template.csv" http://localhost:4000/api/upload`                          | JSON `{ "message":"File processed successfully!", "processing_steps":[…] }`.                                                                                          |
| 5  | **Upload Smoke CSV**                                    | `curl -F "file=@data/smoke.csv" http://localhost:4000/api/upload`                                             | Same success JSON, with `company_id`=1.                                                                                                                              |
| 6  | **Database Row Count Post-Upload**                      | `psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;"`                                        | Returns `>=1`.                                                                                                                                                        |
| 7  | **Derived Metrics Unit Test**                           | `pytest server/scripts/test_calc_metrics.py` (create test file invoking `calc_metrics.py`)                   | Assert correct MoM, QoQ, YoY, YTD, variance for provided sample data.                                                                                                |
| 8  | **Field Mapper Mapping**                                | `pytest server/scripts/test_field_mapper.py`                                                                  | Assert that input names map to canonical IDs (Revenue, Gross Profit, EBITDA).                                                                                        |
| 9  | **Question Engine Variance Threshold**                  | `pytest server/scripts/test_questions_engine.py`                                                              | For a metric variance of +15%, ensure a “positive variance” question is generated.                                                                                   |
| 10 | **Report Generator PDF Creation**                       | `python server/scripts/report_generator.py --input data/financial_data_template.csv --output out.pdf`         | `out.pdf` exists, nonzero file size, contains expected headings (“Revenue”, “Questions”).                                                                              |
| 11 | **Report Generator Question Inclusion**                 | Same command as #10; then `grep -q "Why did Revenue change"` `strings out.pdf`                                | Returns `0`.                                                                                                                                                          |
| 12 | **Blob Upload Simulation**                              | `node server/api/test_blob.js out.pdf`                                                                        | Returns a valid blob URL.                                                                                                                                             |
| 13 | **Generate-Report API Integration**                     | `curl -X POST http://localhost:4000/api/generate-report -H "Content-Type: application/json" -d '{"company_id":1}'` | JSON `"report_filename":"report_1_*.pdf"`, `"processing_steps"` includes PDF creation.                                                                                |
| 14 | **Error Handling: Missing File Upload**                 | `curl -X POST http://localhost:4000/api/upload`                                                               | HTTP `400` with error message “No file provided.”                                                                                                                     |
| 15 | **Error Handling: Invalid Company ID**                  | `curl -X POST .../generate-report -d '{"company_id":9999}'`                                                    | HTTP `404` or JSON error “Company not found.”                                                                                                                         |
| 16 | **Integration: Ingest PDF**                             | `curl -F "file=@data/test.pdf" http://localhost:4000/api/upload` (add a small PDF test file in `data/`)        | Data ingested successfully and metrics calculated.                                                                                                                    |
| 17 | **Database Schema Migration Idempotency**               | `./ci/migrate.sh && ./ci/migrate.sh`                                                                          | Second run detects no changes and exits `0`.                                                                                                                          |
| 18 | **Reset Local DB Script**                               | `./ci/reset_local_db.sh && psql "$DATABASE_URL" -c "\dt"`                                                      | Database tables are dropped and re-created; `\dt` shows only `public.*` base tables.                                                                                 |
| 19 | **Docker Container End-to-End**                         | `docker build -t test-server -f server/Dockerfile . && docker run --rm -p 4000:4000 -e DATABASE_URL=$DATABASE_URL test-server` plus smoke upload | Container responds to `/health`, ingestion and report generation work identically to local.                                                                            |
| 20 | **Code Style and Linting**                              | `npm run lint` (in `server/`) and `flake8 server/scripts`                                                      | No linting errors reported.                                                                                                                                           |

Each test uses existing files under `data/` (e.g., `financial_data_template.csv`, `smoke.csv`) and the provided database schemas. This ensures thorough coverage from high-level pipeline verification to granular unit tests of individual scripts and API endpoints.


--

Here's the **hybrid approach structure** with all the potential **breakage points** clearly identified:

## File Structure

```
financial-data-analysis/
├── schema/
│   ├── 001_financial_schema.sql          # Creates tables + canonical line items
│   ├── 002_question_templates.sql        # Question templates
│   └── migrations/                        # Future migrations
├── config/
│   ├── column_headers.yaml               # Header synonyms for ingestion
│   ├── line_item_aliases.yaml            # Metric name variants  
│   └── derived_metrics.yaml              # Calculated metrics (optional)
├── server/scripts/
│   ├── ingest_xlsx.py                    # Reads config YAMLs
│   ├── field_mapper.py                   # Uses YAML mappings
│   └── questions_engine.py               # References DB line items
└── ci/
    └── 003_smoke_test.sh                 # Creates test data
```

## Current "Revenue" Definitions (Potential Break Points)

### 1. **Schema Seed** (`schema/001_financial_schema.sql`)
```sql
-- BREAK POINT #1: Missing canonical names
INSERT INTO line_item_definitions (name) VALUES 
  ('Revenue'),           -- ⚠️ Must match exactly what ingestion expects
  ('Gross Profit'),      -- ⚠️ Case-sensitive
  ('EBITDA');            -- ⚠️ Typos break everything
```

### 2. **Smoke Test** (`ci/003_smoke_test.sh`)
```bash
# BREAK POINT #2: CSV data doesn't match canonical names
cat > data/smoke.csv <<EOF
line_item,period_label,value,value_type
Revenue,Feb 2025,2390873,Actual     # ⚠️ Must match DB exactly
EOF
```

### 3. **Ingestion Mapping** (`config/line_item_aliases.yaml`)
```yaml
# BREAK POINT #3: Missing aliases cause skips
line_items:
  Revenue:
    - revenue           # ⚠️ Case matters after normalization
    - sales
    - total_revenue
  EBITDA:
    - ebitda
    - earnings_before_interest
```

### 4. **Header Mapping** (`config/column_headers.yaml`)
```yaml
# BREAK POINT #4: Unknown headers get lowercased but not mapped
canonical_headers:
  line_item:
    - line_item
    - lineitem
    - metric
    - line item        # ⚠️ Spaces, case variations
  period_label:
    - period_label
    - period
    - date
```

### 5. **Ingestion Logic** (`server/scripts/ingest_xlsx.py`)
```python
# BREAK POINT #5: Config loading failures
try:
    with open("config/line_item_aliases.yaml") as f:
        aliases = yaml.safe_load(f)
except FileNotFoundError:
    # ⚠️ Silent failure or hard crash?
    aliases = {}

# BREAK POINT #6: Lookup failures
cur.execute("SELECT id FROM line_item_definitions WHERE name=%s", (canonical_name,))
if not cur.fetchone():
    # ⚠️ Row gets skipped silently
    return
```

## Critical Break Points

### **Break Point #1: Schema/Code Sync**
- **Risk**: SQL seed has "Revenue" but code expects "REVENUE" 
- **Fix**: Use consistent casing everywhere, add constraints

### **Break Point #2: Config File Loading**
- **Risk**: YAML file missing, malformed, or not in expected location
- **Fix**: Add validation, default fallbacks, clear error messages

### **Break Point #3: Multi-Source Truth**
- **Risk**: SQL has "Revenue", YAML has "Sales", CSV has "Total Sales"
- **Fix**: Single canonical source, everything else maps to it

### **Break Point #4: Case Sensitivity**
- **Risk**: Database is case-sensitive, CSV headers vary wildly
- **Fix**: Normalize everything to lowercase, then map

### **Break Point #5: Missing Dependencies**
- **Risk**: Ingestion loads config but DB tables don't exist yet
- **Fix**: Clear migration ordering, dependency validation

### **Break Point #6: Silent Failures**
- **Risk**: Rows get skipped without clear error messages
- **Fix**: Explicit validation, detailed logging

## Recommended Approach with Safety

### 1. **Single Source of Truth** (`schema/001_financial_schema.sql`)
```sql
-- Canonical definitions (lowercase for consistency)
INSERT INTO line_item_definitions (name, aliases) VALUES 
  ('revenue', '["sales","total_revenue","turnover"]'),
  ('gross_profit', '["gross_margin","gm"]'),
  ('ebitda', '["earnings_before_interest"]');
```

### 2. **Config Validation** (`server/scripts/config_loader.py`)
```python
def load_and_validate_config():
    """Load config with comprehensive validation"""
    try:
        # Load all configs
        configs = {}
        for file in ['column_headers.yaml', 'line_item_aliases.yaml']:
            with open(f"config/{file}") as f:
                configs[file] = yaml.safe_load(f)
        
        # Validate against database
        with get_db_connection() as conn:
            db_items = set(row[0] for row in 
                          conn.execute("SELECT name FROM line_item_definitions"))
            yaml_items = set(configs['line_item_aliases.yaml'].keys())
            
            missing = yaml_items - db_items
            if missing:
                raise ValueError(f"YAML references missing DB items: {missing}")
        
        return configs
    except Exception as e:
        log_event("config_validation_failed", {"error": str(e)})
        raise
```

### 3. **Defensive Ingestion** (`server/scripts/ingest_xlsx.py`)
```python
def _process_row(self, raw_row, row_number):
    # Load config once at startup, not per row
    if not hasattr(self, '_config'):
        self._config = load_and_validate_config()
    
    # Map headers defensively
    canonical_row = {}
    for raw_key, value in raw_row.items():
        canonical_key = self._map_header(raw_key.lower().strip())
        if canonical_key:
            canonical_row[canonical_key] = value
    
    # Validate required fields early
    required = ['line_item', 'period_label', 'value']
    missing = [field for field in required if not canonical_row.get(field)]
    if missing:
        raise ValueError(f"Row {row_number} missing required fields: {missing}")
    
    # Map line item with detailed error
    canonical_line_item = self._map_line_item(canonical_row['line_item'])
    if not canonical_line_item:
        raise ValueError(f"Row {row_number} unknown line item: {canonical_row['line_item']}")
```

## Testing the Break Points

Add this validation script:
```python
# scripts/validate_config.py
def validate_all_configs():
    """Test all potential break points"""
    issues = []
    
    # Check DB vs YAML consistency
    # Check file existence and YAML validity  
    # Check smoke test data vs canonical names
    # Check header mapping completeness
    
    if issues:
        print("❌ Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    print("✅ All configurations valid")
    return True
```


***

# **Complete Terminal Instructions for CI Green**

## **Step 1: Validate YAML Configuration**
```bash
# Validate all YAML files are properly formatted
echo "=== STEP 1: YAML Validation ==="
poetry run python scripts/validate_yaml.py
```

## **Step 2: Regenerate Schema Files**
```bash
# Generate fresh schema from your new tables.yaml
echo "=== STEP 2: Schema Generation ==="
poetry run python scripts/generate_schema.py
poetry run python scripts/generate_questions.py

# Check what was generated
echo "Generated schema preview:"
head -50 schema/001_financial_schema.sql
echo "Generated questions preview:"
head -20 schema/002_question_templates.sql
```

## **Step 3: Run CI Pipeline**
```bash
# Run CI pipeline step by step
echo "=== STEP 3: CI Pipeline ==="

# Step 3a: Drop all tables
echo "--- CI Step 1: Drop Tables ---"
ci/01_drop_tables.sh

# Step 3b: Reset/create schema
echo "--- CI Step 2: Reset Database ---"
ci/02_reset_db.sh

# Verify tables were created correctly
echo "--- Database Verification ---"
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "\d financial_metrics"
psql "$DATABASE_URL" -c "\d line_item_definitions"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM line_item_definitions;"

# Step 3c: Run smoke test
echo "--- CI Step 3: Smoke Test ---"
ci/03_smoke_csv.sh
```

## **Step 4: If Docker/Container Issues Occur**
```bash
# Container debugging commands (run these if smoke test fails)
echo "=== STEP 4: Docker Debugging (if needed) ==="

# Check if container is running
docker ps

# Check container logs (last 250 lines)
docker logs --tail 250 finance-server_ci

# Check container logs (last 50 lines with timestamps)
docker logs --tail 50 -t finance-server_ci

# If container is stuck/dead, force cleanup and retry
docker stop finance-server_ci 2>/dev/null || true
docker rm -f finance-server_ci 2>/dev/null || true

# Rebuild and test manually
docker build -t finance-server -f server/Dockerfile .
docker run --rm --env-file .env -p 4000:4000 --name finance-server_ci finance-server &

# Test health endpoint
sleep 10
curl -s http://localhost:4000/health

# Stop test container
docker stop finance-server_ci
```

## **Step 5: Database Debugging (if CI fails)**
```bash
# Database inspection commands
echo "=== STEP 5: Database Debugging ==="

# Check all tables exist
psql "$DATABASE_URL" -c "\dt public.*"

# Inspect financial_metrics structure
psql "$DATABASE_URL" -c "\d+ financial_metrics"

# Check line_item_definitions data
psql "$DATABASE_URL" -c "SELECT id, name FROM line_item_definitions;"

# Check if smoke test data exists
psql "$DATABASE_URL" -c "
SELECT 
  fm.id,
  c.name as company,
  p.period_label,
  li.name as line_item,
  fm.value
FROM financial_metrics fm
JOIN companies c ON fm.company_id = c.id
JOIN periods p ON fm.period_id = p.id  
JOIN line_item_definitions li ON fm.line_item_id = li.id
LIMIT 5;"
```

## **Step 6: Full Integration Test**
```bash
# Run remaining CI steps if smoke test passes
echo "=== STEP 6: Full Integration ==="

ci/04_integration_xlsx.sh
ci/05_full_sample.sh

# Final validation
echo "=== Final Status ==="
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_metrics FROM financial_metrics;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) as derived_metrics FROM derived_metrics;"
```

***

# **Expected Results at Each Step**

**Step 1:** Should print "fields.yaml OK", "observations.yaml OK", "questions.yaml OK"

**Step 2:** Should generate schema files without errors and show table definitions

**Step 3a:** Should print "01 | All tables dropped."

**Step 3b:** Should print "02 | Schema reset complete." and show tables like `financial_metrics`, `companies`, etc.

**Step 3c:** Should print "03 | Smoke CSV test passed: revenue=2,390,873.00"

***

**Run each step and share the output!** If any step fails, we'll debug using the container logs and database inspection commands. The key is to see exactly where the pipeline breaks and what error messages appear.


***

## 6. **Best Practice End-to-End CI Pipeline**

This is what a bulletproof CI pipeline should do:

**A. Validate Config**
- Run `scripts/validate_yaml.py` to ensure configs are never broken on commit.

**B. Build and Validate Docker Image**
- Build once, and only if code/dockerfile changes.

**C. Database Clean-Up and Schema Apply**
- Drop all tables.
- Re-apply schema and seed data.

**D. API Smoke Test**
- Bring up a fresh backend/API container using `.env`.
- Upload canonical “smoke” CSV and confirm metrics flow to DB.

**E. Frontend/Backend Integration Test**
- (Optional) Hit API endpoints from front-end using test data, confirm proper full-stack behavior.

**F. Extended Integration Test**
- Upload more complex files (XLSX, PDF), check full pipeline results.

**G. Clean Up**
- Stop and remove any test containers.

**H. Report**
- Print out summary results: which step failed, which passed, with links to logs if needed.


--

## Running the Full CI/Validation Pipeline

**1. Validate configs and generate SQL:**
./ci/00_config_validation.sh

**2. Drop all tables in the DB:**  
ci/01_drop_tables.sh

**3. Reset and apply the schema:**  
ci/02_reset_db.sh

**4. [CLEANUP] Make sure no server containers are running (avoid port conflicts):**  
docker ps
docker stop finance-server || true
docker stop finance-server_ci || true
docker rm finance-server || true
docker rm finance-server_ci || true

**5. Smoke test the pipeline:**  
ci/03_smoke_csv.sh

**6. Run extended integrations (optional, if set up):**  
ci/04_integration_xlsx.sh
ci/05_full_sample.sh
