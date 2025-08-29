# Financial Data Analysis - FastAPI Backend Setup
.PHONY: help setup install server client test-db test-api clean kill-ports

# Default target
help:
	@echo "Financial Data Analysis - FastAPI Setup Commands"
	@echo "=============================================="
	@echo "make setup        - Complete setup for new developers"
	@echo "make install      - Install Python dependencies"
	@echo "make server       - Start FastAPI server on port 4000"
	@echo "make client       - Start React client on port 3000"
	@echo "make test-db      - Test database connection"
	@echo "make test-api     - Test API endpoints"
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
	@echo "🔪 Killing processes on ports 3000 and 4000..."
	-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	-lsof -ti:4000 | xargs kill -9 2>/dev/null || true
	@echo "✅ Ports cleared"

# Install Python dependencies
install:
	@echo "📦 Installing Python dependencies..."
	@if [ ! -d ".venv" ]; then echo "Creating virtual environment..." && uv venv; fi
	@echo "Activating virtual environment and installing dependencies..."
	@bash -c "source .venv/bin/activate && uv pip install -r requirements.txt"
	@echo "📦 Installing React client dependencies..."
	cd client && npm install
	@echo "✅ All dependencies installed"

# Set up database
db-setup:
	@echo "🗄️ Setting up database..."
	@bash -c "source .venv/bin/activate && python database/migrate.py up"
	@bash -c "source .venv/bin/activate && python database/seed.py"
	@echo "✅ Database setup completed"

# Test database connection
test-db:
	@echo "🧪 Testing database connection..."
	@bash -c "source .venv/bin/activate && python -c \"from server.app.services.utils import get_db_connection; conn = get_db_connection(); print('✅ Database connection successful'); conn.close()\""
	@bash -c "source .venv/bin/activate && python database/migrate.py status"

# Start FastAPI server
server: kill-ports
	@echo "🚀 Starting FastAPI server on port 4000..."
	@if lsof -ti:4000 > /dev/null 2>&1; then echo "❌ Port 4000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	@bash -c "source .venv/bin/activate && python server/main.py"

# Start React client
client:
	@echo "🌐 Starting React client on port 3000..."
	@if lsof -ti:3000 > /dev/null 2>&1; then echo "❌ Port 3000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	cd client && npm start

# Test API endpoints
test-api:
	@echo "🧪 Testing API endpoints..."
	@echo "Testing health endpoint..."
	@curl -s http://localhost:4000/health | jq . || echo "❌ API server not responding on port 4000"
	@echo "Testing upload endpoint..."
	@curl -s -F "file=@data/sample_data.csv" http://localhost:4000/api/upload | jq .message || echo "❌ Upload endpoint failed"
	@echo "✅ API tests completed"

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	rm -rf logs/
	rm -rf __pycache__/
	rm -rf server/__pycache__/
	rm -rf server/app/__pycache__/
	rm -rf server/app/services/__pycache__/
	find . -name "*.pyc" -delete
	@echo "✅ Cleanup completed"

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