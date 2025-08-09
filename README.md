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

- **Front-End**: React for the user interface (`client/` directory).
- **Back-End**: Node.js (`server/server.js`) for API endpoints and processing.
- **Scripts**: Python for data handling and report generation (`scripts/` directory).
- **Database**: PostgreSQL for structured data storage (`schema/` directory).
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

## Minimal Working Setup

For just testing the core functionality (without deployment), you only need:
1. **Steps 1-4** above
2. **NeonDB account** (free tier)
3. **Docker Desktop**

The Railway and Vercel deployments are optional for production hosting.

-

This setup gives you a fully functional financial data analysis system running locally with cloud database persistence.

-

Your current structure is already well-organized and follows standard conventions. The Docker /app directory is just a container mount point - it doesn't dictate your repo structure.
Current Structure (Good):
text
financial-data-analysis/
├── client/              # React frontend
├── server/              # Node.js API + Python scripts
│   ├── api/            # Express routes
│   ├── scripts/        # Python processing scripts
│   └── Dockerfile      # Container definition
├── data/               # Sample data
├── schema/             # Database schemas
└── pyproject.toml      # Python dependencies

-

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

**Step-by-Step Setup:**

1. **Create the smoke CSV** at `data/smoke.csv`:
   ```csv
   line_item,period_label,period_type,value,source_file,source_page,notes
   Revenue,Feb 2025,Monthly,2390873,smoke.csv,1,smoke test
   ```

2. **Create a CI script** at `ci/smoke_test.sh`:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   # Load DATABASE_URL from .env
   export DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d '=' -f2-)"

   # Seed master line_item_definitions
   psql "$DATABASE_URL" &2
     docker logs finance-server_ci >&2
     docker stop finance-server_ci
     exit 1
   fi

   echo "Smoke test passed: revenue=$ACTUAL"

   # Clean up
   docker stop finance-server_ci
   ```

3. **Make it executable:**
   ```bash
   chmod +x ci/smoke_test.sh
   ```

4. **Run your smoke test locally:**
   ```bash
   ./ci/smoke_test.sh
   ```

If the script prints **“Smoke test passed”**, your ingestion and database pipeline works end-to-end. Any failure will stop immediately with error output and container logs for debugging.

Here’s a one-liner that creates `smoke.csv` on-the-fly, seeds master data, builds & runs Docker, uploads the CSV, checks the result, and tears down—all without needing external files:

```bash
bash -c '
set -euo pipefail

# 1. Create smoke.csv
cat > data/smoke.csv /dev/null
docker run --rm --env-file .env -d -p 4000:4000 --name finance-server_ci finance-server

# 5. Wait for health check
for i in {1..10}; do
  curl -s http://localhost:4000/health | grep -q '"status":"ok"' && break || sleep 1
done

# 6. Upload the generated smoke.csv
curl -fs -F "file=@data/smoke.csv" http://localhost:4000/api/upload

# 7. Verify insertion
EXPECTED=2390873
ACTUAL=$(psql "$DATABASE_URL" -t -c "
  SELECT value FROM financial_metrics fm
   JOIN line_item_definitions li ON fm.line_item_id=li.id
   JOIN periods p ON fm.period_id=p.id
   WHERE li.name='Revenue' AND p.period_label='Feb 2025';
" | tr -d '[:space:]')

if [[ \"$ACTUAL\" != \"$EXPECTED\" ]]; then
  echo \"Smoke test failed: expected $EXPECTED, got $ACTUAL\" >&2
  docker logs finance-server_ci >&2
  docker stop finance-server_ci
  exit 1
fi

echo \"Smoke test passed: revenue=$ACTUAL\"

# 8. Clean up
docker stop finance-server_ci
'
```

Steps:
1. Generates `data/smoke.csv` with the expected Revenue row.  
2. Seeds `line_item_definitions`.  
3. Builds and runs the Docker container.  
4. Uploads the generated CSV.  
5. Queries the DB for the revenue value and compares it to `2390873`.  
6. Prints pass/fail and stops the container.

You only need the standard CLI tools that you already have in your workflow—no new installs:
bash (built in)
Docker (for building & running the server)
psql (Postgres client)
curl
grep
Assuming those are in your PATH and your .env is configured, you can run the entire smoke test in one go 

--
# Development: Reset and migrate
ci/001_reset_local_db.sh
ci/002_migrate.sh


# CI: Just migrate (idempotent)
ci/002_migrate.sh

# Smoke test (unchanged)
ci/003_smoke_test.sh

--

--

Medium-term (company identification):
Extend the companies table:
sql
ALTER TABLE companies ADD COLUMN 
  company_house_number TEXT,
  ticker_symbol TEXT,
  aliases TEXT[];
Add company selection to upload flow:
After file upload, scan for company indicators (letterhead, company names)
Present a dropdown: "Is this [Detected Company Name] or create new?"
Pass company_id parameter to ingestion
Implement fuzzy matching:
Use pg_trgm extension for similarity scoring
Alert: "This data is 85% similar to [Existing Company]. Same entity?"
Focus for now: Get your smoke test passing by seeding the companies table in both databases. Company disambiguation can be layered on once the core pipeline is solid.
--


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

Run this before any deployment to catch mismatches early.

--

| Step | Component                                | Purpose                                                             | Tested By                                  | Databases       | Order | Coverage Completeness (%) |
|------|------------------------------------------|---------------------------------------------------------------------|---------------------------------------------|-----------------|-------|---------------------------|
| 1    | Environment Configuration                | Load `.env`, set `DATABASE_URL` for local & Neon                    | All CI scripts (via `--env-file .env`)      | Local, Neon     | 1     | 100%                      |
| 2    | Drop All Tables                          | Remove every existing table & data                                  | `000_drop_tables.sh`                        | Local, Neon     | 2     | 100%                      |
| 3    | Base Schema Reset                        | Apply `001_financial_schema.sql` & `002_question_templates.sql`     | `001_reset_db.sh`                           | Local, Neon     | 3     | 100%                      |
| 4    | Migration Tracking & Incremental Updates | Track & apply future migrations                                     | `002_migrate.sh`                            | Local, Neon     | 4     | 100%                      |
| 5    | CSV Ingestion                            | Parse CSV, map fields, dedupe, insert metrics                       | `003_smoke_csv.sh`                          | Local, Neon     | 5     | 100%                      |
| 6    | XLSX Ingestion                           | Parse XLSX, map fields, dedupe, insert metrics                      | `004_integration_xlsx.sh`                   | Local, Neon     | 6     |  75%*                     |
| 7    | Metric Calculation                       | Compute MoM/QoQ/YoY/YTD/variance metrics                            | Indirect via `/api/upload` in steps 5–6     | Local, Neon     | 5–6   |  80%†                     |
| 8    | Question Generation                      | Generate threshold-based analytical questions                       | Indirect via `/api/upload` in steps 5–6     | Local, Neon     | 5–6   |  80%†                     |
| 9    | Report Generation & Blob Upload          | Bundle into PDF, upload to Blob                                     | Not covered by CI                           | Local, Neon     | N/A   |   0%                      |
| 10   | Full-Sample End-to-End Report            | Loop through all sample files and report rows added (informational) | `005_full_sample_report.sh`                 | Local, Neon     | 7     |  90%                      |

* XLSX ingestion currently skips rows on mapping fallback errors—requires enhancement in `field_mapper.py`.  
† Metric/question functionality exercised by ingestion tests but lacks direct value/assertion checks beyond counts.

--

Perfect! Here's your **complete terminal command sequence** to validate, regenerate schemas, run CI, and debug any issues. Follow these steps in order and share the results at each stage:

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

[1] https://github.com/matcapl/financial-data-analysis/blob/main/scripts/validate_yaml.py

Excellent, you're thinking as a true *product owner and architect*. Let’s cover what “best practice” means for **.env management**, **Docker usage in CI**, the **parts and layers of your repo**, and how to design an end-to-end CI pipeline that’s robust and aligned with each function. Here’s a strategic breakdown:

***

## 1. **Best Practice for `.env` Setup**

- **Centralize `.env` in the project root.**
  - Example `.env` file:
    ```
    DATABASE_URL=postgresql://username:password@host:5432/dbname?sslmode=require
    API_SECRET=
    VERCEL_BLOB_TOKEN=
    ```

- **Never commit secrets to version control.**
  - Use `.env.example` (or `.env.sample`) as a template, containing:
    ```
    DATABASE_URL=
    API_SECRET=
    ```
    This helps onboarding and cloud deployment.

- **Scripts and services always auto-load `.env` if present** (as covered in previous answers).

- **For Docker:**  
  - Pass `.env` variables to Docker containers using `--env-file .env`  
    Example Docker run:
    ```bash
    docker run --rm --env-file .env -p 4000:4000 --name finance-server finance-server
    ```

- **For CI stacks (GitHub Actions, etc):**
  - They should securely inject secrets/environment via their own mechanism—never hardcoded into images.

***

## 2. **Docker + CI: What Should Be in Each Script?**

- **Docker build** (the static image) is typically outside per-test CI scripts.
  - You build once when the code or Dockerfile changes:
    ```bash
    docker build -t finance-server -f server/Dockerfile .
    ```

- **Run containers for integration/smoke tests** within each CI sequence.
  - The scripts should check: is a test server running? If not, start one with `docker run ...`.
  - **Shutdown/cleanup** (using `docker stop`, `docker rm`) should be handled at the end of each test to ensure predictable state and no port conflicts.

- **CI/01:** Should NOT build docker image, but can check for running test containers and shut them down.
- **CI/03 (smoke):** Should always bring up its own disposable server/container, run tests, then clean up.

***

## 3. **Repo Layers: Primary Functions and Structure**

Here’s the layered architecture for your project:

| Layer        | Directory      | Primary Function                       | Example Files         |
|--------------|---------------|----------------------------------------|----------------------|
| **Frontend** | `/client`     | React/JS client for user UI            | `src/`, `public/`    |
| **Backend**  | `/server`     | Node.js API, Python pipeline orchestration | `server.js`, `api/`  |
| **Python**   | `/server/scripts` | Data ingestion, metrics, analytics  | `ingest_xlsx.py`, `calc_metrics.py` |
| **Schema**   | `/schema`     | Auto-generated SQL for DB              | `001_financial_schema.sql` |
| **Config**   | `/config`     | YAML configs for schema and mapping    | `tables.yaml`, `fields.yaml` |
| **CI**       | `/ci`         | Scripts for DB reset, smoke/integration tests | `01_`, `02_`, ...   |
| **Data**     | `/data`       | Example and sample upload files        | `smoke.csv`, ...     |

***

## 4. **Front-End, Back-End, Middle/Glue, Data Tools**

- **Front-End**
  - React app for user interaction and display.
  - Environment variables (like `REACT_APP_API_URL`) point at backend API.

- **Back-End**
  - NodeJS/Express server handles HTTP API, file upload, task orchestration.
  - Invokes Python scripts for heavy-lifting (ingestion, metrics, analytics).

- **Middle/Glue**
  - Python scripts run in child-process or direct mode.
  - PostgreSQL DB for persistent analytics/state.

- **Data Tools**
  - Schema generator scripts.
  - Config validation tools.
  - Smoke/integration test runner scripts.

***

## 5. **Tools and Technologies**

- **NodeJS/Express** (APIs)
- **React** (Front-end)
- **Python (with pandas, psycopg2, etc.)** (Data processing and ingestion)
- **PostgreSQL** (Database)
- **Docker** (Dev/test infra)
- **YAML-based config** (for schema, mappings)
- **Shell (bash) scripts** for CI

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

***

## **Summary Table: CI Steps**

| Step | Function                | What It Tests                    | How to Run         |
|------|-------------------------|----------------------------------|--------------------|
| 0    | Config validation       | .yaml files                      | python validate_yaml.py |
| 1    | Schema setup            | DB clean + schema reloaded       | ci/01_drop_tables.shci/02_reset_db.sh |
| 2    | Backend/API             | API/server is up, healthy        | docker run ...     |
| 3    | Smoke test              | File->metric ingest core pipeline| ci/03_smoke_csv.sh |
| 4    | Integration             | Large and multi-file ingest      | ci/04..., ci/05... |
| 5    | Frontend integration    | UI/API flow                      | (optional) Cypress, Playwright, Selenium, etc. |
| 6    | Clean up                | Resource cleanup                 | docker stop/rm ... |
| 7    | Reporting               | Human-readable results/logs      | echo/logs          |

***

**Final Thought:**  
A good pipeline isn’t “adjunct”; it’s the living, breathing proof that every part of your repo, from config to UI to backend, works together.  
Automate what a developer or test engineer would do by hand, every hour, every day.  
Zero friction between config, code, infra, and tests—that’s strategic best practice CI.

If you want example GitHub Actions workflows, Makefile, or anything else, just ask!


Stop any running containers on 4000 before CI:

docker stop finance-server || true
docker stop finance-server_ci || true
docker rm finance-server || true
docker rm finance-server_ci || true


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


