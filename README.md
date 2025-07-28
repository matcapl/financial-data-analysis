Financial Data Analysis System
A system to ingest financial data from Excel and PDF board packs, compute metrics (Revenue, Gross Profit, EBITDA), generate questions, and produce PDF reports. Deployable on Vercel with a React front-end and Node.js back-end.
Prerequisites

Python 3.9+
Node.js 18+
PostgreSQL 13+
Tesseract OCR
Vercel account

Setup

Clone Repository:
git clone https://github.com/yourusername/financial-data-analysis.git
cd financial-data-analysis


Python Environment:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r <(poetry export --without-hashes)


PostgreSQL Setup:
psql -U postgres -d finance -f schema/financial_schema.sql
psql -U postgres -d finance -f schema/question_templates.sql


Client Setup:
cd client
npm install
npm run build


Server Setup:
cd server
npm install


Environment Variables:Create a .env file in the root:
DB_HOST=localhost
DB_NAME=finance
DB_USER=postgres
DB_PASSWORD=yourpass
DB_PORT=5432
VERCEL_BLOB_TOKEN=your_vercel_blob_token


Run Locally:
cd server
npm start
cd ../client
npm start


Deploy to Vercel:

Push to a GitHub repository.
Connect to Vercel and deploy the client and server directories as separate projects.
Set environment variables in Vercel dashboard.
Configure vercel.json for routing:{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/server/api/$1" },
    { "source": "/(.*)", "destination": "/client/build/$1" }
  ]
}





Usage

Upload .xlsx or .pdf files via the web interface (http://localhost:3000).
Click "Generate Report" to create a PDF with metrics, observations, and questions.
Download or preview the report.

Notes

Supports Revenue, Gross Profit, EBITDA with monthly, quarterly, and yearly (YTD) calculations.
Handles data gaps with notes and logging.
Questions are generated for changes exceeding thresholds (e.g., 10% MoM, 5% YoY).
Reports include sourced assertions and no adverbs.
