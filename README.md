# Financial Data Analysis System

Enterprise-grade financial data processing system with TypeScript React frontend, FastAPI backend, and comprehensive monitoring. Processes Excel/CSV/PDF files to calculate metrics, generate insights, and produce analytical reports.

## Key Features

🚀 **Modern Tech Stack**
- **Frontend**: TypeScript React + Tailwind CSS with drag & drop file upload
- **Backend**: FastAPI with direct Python integration (no Node.js complexity)
- **Database**: PostgreSQL with automated migrations and comprehensive seeding
- **Monitoring**: Real-time metrics, error tracking, and performance monitoring
- **Deployment**: Multi-stage Docker builds, Docker Compose, Railway/Vercel ready

📊 **Financial Analytics**
- Multi-format ingestion (Excel, CSV, PDF with OCR)
- Automated metric calculation (Revenue, Gross Profit, EBITDA, ratios)
- Intelligent question generation from data patterns
- PDF report generation with insights and recommendations

🔧 **Enterprise Operations**
- Correlation ID tracking across all requests
- Rate limiting (100 requests/minute per IP)
- Database connection pooling (5-20 connections)
- Memory monitoring with automatic garbage collection
- Structured JSON logging with automatic error detection
- Performance monitoring with slow operation alerts
- System resource monitoring (CPU, memory, disk)
- Automated CI/CD with comprehensive testing

## Quick Start

### Prerequisites
- Python 3.10+ 
- Node.js 18+
- PostgreSQL database
- [uv package manager](https://docs.astral.sh/uv/)

### Setup (30 seconds)
```bash
git clone <repository-url>
cd financial-data-analysis

# Complete setup - installs dependencies and sets up database
make setup

# Start both servers
make server  # FastAPI backend (port 4000)
make client  # React frontend (port 3000)

# Visit http://localhost:3000
```

### Docker Development
```bash
# Start database services
make docker-dev

# Or full containerized development
make docker-dev-full

# Build production image
make docker-build
```

## System Architecture

### Processing Pipeline
1. **File Upload** → Drag & drop CSV/Excel/PDF files
2. **Data Extraction** → Multi-format parsing with OCR support
3. **Metric Calculation** → Financial ratios, variance analysis, time-series
4. **Question Generation** → AI-powered insights from data patterns
5. **Report Generation** → PDF reports with charts and recommendations

### Database Schema
- **Companies** → Organization data
- **Financial Metrics** → Core financial data with period normalization
- **Derived Metrics** → Calculated ratios, variances, time-series analysis
- **Questions** → Generated analytical questions from patterns
- **Reports** → PDF report metadata and storage

### API Endpoints
```bash
# Core functionality
GET  /health                    # System health check
POST /api/upload               # File upload and processing
POST /api/generate-report      # PDF report generation
GET  /api/reports              # List generated reports

# Monitoring and observability
GET  /api/monitoring/metrics/health     # System metrics and performance
GET  /api/monitoring/metrics           # Application metrics
GET  /api/monitoring/errors/summary    # Error analytics
```

## Development Commands

### Local Development
```bash
make setup          # Complete setup for new developers
make server         # Start FastAPI backend
make client         # Start React TypeScript frontend
make test           # Run all tests
make ci-check       # Full CI validation
```

### Docker Operations
```bash
make docker-build      # Build optimized production image  
make docker-dev        # Start PostgreSQL and Redis
make docker-dev-full   # Full containerized development
make docker-stop       # Stop all Docker services
```

### Monitoring
```bash
make monitoring-health   # System health and performance dashboard
make monitoring-metrics  # Application metrics overview
make monitoring-errors   # Error tracking and analytics
```

### Database Operations
```bash
make test-db                           # Test database connection
.venv/bin/python3 database/migrate.py up    # Apply migrations
.venv/bin/python3 database/seed.py          # Add development data
```

## Production Deployment

### Railway (Backend)
```bash
railway login
railway new financial-data-backend
railway add postgresql
railway deploy
```

### Vercel (Frontend)
```bash
cd client
vercel --prod
```

### Docker Production
```bash
# Build and run production container
make docker-build
docker run -p 4000:4000 -e DATABASE_URL=your_db_url financial-data-analysis:latest
```

## Monitoring and Observability

### Real-Time Monitoring Features
- **Request Correlation**: Unique IDs track requests across the system
- **Performance Metrics**: Automatic timing for all API calls and database queries
- **Error Analytics**: Centralized error tracking with pattern detection
- **System Monitoring**: CPU, memory, and disk usage tracking
- **Alert System**: Automated alerts for high error rates and critical issues

### Log Files
```bash
tail -f logs/financial-api-enhanced.log    # Structured application logs
tail -f logs/metrics.jsonl                 # Performance metrics
tail -f logs/errors.jsonl                  # Error events  
tail -f logs/alerts.jsonl                  # Alert notifications
```

## Technologies

### Frontend Stack
- **TypeScript** - Type-safe React development
- **Tailwind CSS** - Utility-first styling with custom design system
- **React 18** - Modern hooks and concurrent features
- **Drag & Drop** - Advanced file upload with visual feedback

### Backend Stack  
- **FastAPI** - High-performance Python web framework
- **SQLAlchemy** - Database ORM with repository pattern
- **Pydantic** - Data validation and configuration management
- **PostgreSQL** - Relational database with full-text search

### DevOps & Monitoring
- **Docker** - Multi-stage builds with security hardening
- **Docker Compose** - Local development environment
- **psutil** - System resource monitoring
- **Structured Logging** - JSON logs with correlation tracking
- **GitHub Actions** - Automated CI/CD pipeline

## File Structure

```
financial-data-analysis/
├── client/                     # TypeScript React frontend
│   ├── src/
│   │   ├── components/         # TypeScript React components
│   │   ├── contexts/           # React Context with TypeScript
│   │   └── types/              # TypeScript type definitions
│   ├── tsconfig.json          # TypeScript configuration
│   └── tailwind.config.js     # Tailwind CSS customization
├── server/                     # FastAPI backend
│   ├── main.py                # Application entry point with monitoring
│   └── app/
│       ├── api/               # API endpoints and routers
│       ├── core/              # Configuration, monitoring, rate limiting
│       ├── models/            # Pydantic data models
│       ├── repositories/      # Database access layer
│       ├── services/          # Business logic and data processing
│       ├── utils/             # Shared utilities and logging
│       └── tests/             # All tests
├── database/                   # Database migrations and seeding
│   ├── migrations/            # SQL migration files
│   ├── migrate.py            # Migration management
│   └── seed.py               # Comprehensive development data
├── scripts/                   # Consolidated CI/CD tools
│   ├── ci_manager.py         # Main CI/CD operations
│   ├── manage.py             # Data management utilities  
│   └── docker-build.sh       # Docker build automation
├── config/                    # YAML configurations
├── docker-compose.yml         # Development environment
├── Dockerfile                 # Multi-stage production build
└── Makefile                   # Development commands
```

## Troubleshooting

### Common Issues

**React Build Issues**
```bash
cd client
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

**Python Dependencies**
```bash
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install psutil==6.1.0  # For monitoring
```

**Database Connection**
```bash
make test-db
.venv/bin/python3 database/migrate.py status
```

**Port Conflicts**
```bash
make kill-ports
lsof -ti:3000,4000 | xargs kill -9
```

**Docker Issues**
```bash
make docker-stop
docker system prune -f
make docker-build
```

## Support

- **Documentation**: See `DEVELOPER_GUIDE.md` and `CI_CD_GUIDE.md`
- **Health Check**: `curl http://localhost:4000/health`
- **Monitoring Dashboard**: `make monitoring-health`
- **Error Analytics**: `make monitoring-errors`

---

**Enterprise FastAPI Architecture** - Complete financial data analysis system with TypeScript frontend, comprehensive monitoring, and production-ready deployment infrastructure.