# Financial Data Analysis - FastAPI Backend Setup
.PHONY: help setup install server client test-db test-api clean kill-ports ci-check deploy health validate aliases questions generate-periods validate-yaml

# Default target
help:
	@echo "Financial Data Analysis - FastAPI Setup Commands"
	@echo "=============================================="
	@echo "Development Commands:"
	@echo "make setup        - Complete setup for new developers"
	@echo "make install      - Install Python dependencies"
	@echo "make server       - Start FastAPI server on port 4000"
	@echo "make client       - Start React client on port 3000"
	@echo ""
	@echo "Testing Commands:"
	@echo "make test         - Run all tests"
	@echo "make test-unit    - Run unit tests only"
	@echo "make test-db      - Test database connection"
	@echo "make test-api     - Test API endpoints"
	@echo ""
	@echo "CI/CD Commands:"
	@echo "make ci-check     - Run full CI health check"
	@echo "make deploy       - Production deployment"
	@echo "make health       - Check application health"
	@echo "make validate     - Validate configuration"
	@echo ""
	@echo "Data Management Commands:"
	@echo "make aliases      - Manage period aliases (requires ARGS=...)"
	@echo "make questions    - Generate analytical questions"
	@echo "make validate-yaml - Validate YAML configuration files"
	@echo "make generate-periods - Generate periods.yaml"
	@echo ""
	@echo "Utility Commands:"
	@echo "make kill-ports   - Kill processes on ports 3000 and 4000"
	@echo "make clean        - Clean up generated files"
	@echo ""
	@echo "QUICK START:"
	@echo "1. make kill-ports"
	@echo "2. make setup"
	@echo "3. make server (in one terminal)"
	@echo "4. make client (in another terminal)"

# Kill any processes running on our ports
kill-ports:
	@.venv/bin/python3 scripts/ci_manager.py kill-ports

# Install Python dependencies
install:
	@echo "📦 Installing Python dependencies..."
	@if [ ! -d ".venv" ]; then echo "Creating virtual environment..." && uv venv; fi
	@echo "Installing Python dependencies..."
	@uv pip install -r requirements.txt
	@echo "📦 Installing React client dependencies..."
	cd client && npm install --legacy-peer-deps
	@echo "✅ All dependencies installed"

# Set up database
db-setup:
	@.venv/bin/python3 scripts/ci_manager.py db setup

# Test database connection
test-db:
	@.venv/bin/python3 scripts/ci_manager.py db check

# Start FastAPI server
server: kill-ports
	@echo "🚀 Starting FastAPI server on port 4000..."
	@if lsof -ti:4000 > /dev/null 2>&1; then echo "❌ Port 4000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	@.venv/bin/python3 server/main.py

# Start React client
client:
	@echo "🌐 Starting React client on port 3000..."
	@if lsof -ti:3000 > /dev/null 2>&1; then echo "❌ Port 3000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	cd client && npm start

# Test API endpoints
test-api:
	@.venv/bin/python3 scripts/ci_manager.py health

# Run all tests
test:
	@.venv/bin/python3 scripts/ci_manager.py test

# Run unit tests only
test-unit:
	@.venv/bin/python3 scripts/ci_manager.py test --type unit

# Clean up generated files
clean:
	@.venv/bin/python3 scripts/ci_manager.py clean

# CI/CD Commands using consolidated script
ci-check:
	@.venv/bin/python3 scripts/ci_manager.py check-all

deploy:
	@.venv/bin/python3 scripts/ci_manager.py deploy

health:
	@.venv/bin/python3 scripts/ci_manager.py health

validate:
	@.venv/bin/python3 scripts/ci_manager.py validate

# Data Management Commands
aliases:
	@.venv/bin/python3 scripts/manage.py aliases $(ARGS)

questions:
	@.venv/bin/python3 scripts/manage.py questions

validate-yaml:
	@.venv/bin/python3 scripts/manage.py validate-yaml

generate-periods:
	@.venv/bin/python3 scripts/manage.py generate-periods

# Complete setup for new developers
setup: install db-setup test-db
	@echo ""
	@echo "🎉 Setup completed successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Open two terminals"
	@echo "2. In terminal 1: make server"
	@echo "3. In terminal 2: make client"
	@echo "4. Visit http://localhost:3000"
	@echo ""