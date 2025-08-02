# Financial Data Analysis System

This repository hosts a system for analyzing financial data from Excel and PDF files. It calculates key metrics like Revenue, Gross Profit, and EBITDA, generates insightful questions, and produces PDF reports. Deployable on Vercel, it features a React front-end for user interaction and a Node.js back-end for processing, with Python scripts handling data ingestion and report generation.

## Methodology

The system operates through these key steps:

1. **Data Ingestion**: Custom Python scripts (`ingest_xlsx.py` and `ingest_pdf.py`) process Excel and PDF files, extracting financial data.
2. **Metric Calculation**: Scripts (`calc_metrics.py`) compute financial metrics based on the ingested data.
3. **Question Generation**: The `questions_engine.py` script creates questions from the metrics to drive deeper analysis.
4. **Report Generation**: The `report_generator.py` script compiles metrics and questions into PDF reports, stored and served via Vercel Blob.

Data is managed in a PostgreSQL database with tables for companies, periods, financial metrics, derived metrics, questions, and reports, as defined in `financial_schema.sql` and `question_templates.sql`.

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
# Clone the repository
git clone https://github.com/matcapl/financial-data-analysis.git
cd financial-data-analysis

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install poetry
poetry install

# Install Node.js dependencies
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
   psql "postgresql://username:password@ep-xxx.neon.tech:5432/database?sslmode=require" -f schema/financial_schema.sql
   psql "postgresql://username:password@ep-xxx.neon.tech:5432/database?sslmode=require" -f schema/question_templates.sql
   ```

question_templates.sql must be deployed with matching financial_schema.sql.
If changes to metric definitions occur in the schema, corresponding question templates updates should be part of the same PR and deployment.

psql "$LOCAL_DATABASE_URL" -f schema/financial_schema.sql
psql "$LOCAL_DATABASE_URL" -f schema/question_templates.sql

psql "$DATABASE_URL" -f schema/financial_schema.sql
psql "$DATABASE_URL" -f schema/question_templates.sql


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

