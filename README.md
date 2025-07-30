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

For installation, usage, and further details, refer to the repository’s documentation.