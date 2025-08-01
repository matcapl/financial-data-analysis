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

## Step 3: Environment Configuration

Create `.env` file in project root:
```bash
echo "DATABASE_URL=postgresql://your_user:your_password@ep-xxx.neon.tech:5432/your_db?sslmode=require" > .env
```

## Step 4: Build and Test Locally

```bash
# Build Docker image
docker build -t finance-server -f server/Dockerfile .

# Run container
docker run --rm --env-file .env -p 4000:4000 finance-server &

# Wait 10 seconds for startup, then test
sleep 10

# Test health endpoint
curl http://localhost:4000/health

# Test file upload
curl -F "file=@data/financial_data_template.csv" http://localhost:4000/api/upload

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