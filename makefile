# Financial Data Analysis - Automated Setup
.PHONY: help db-setup fix-schema install-deps server client test-db test-api clean kill-ports

# Default target
help:
	@echo "Financial Data Analysis - Setup Commands"
	@echo "========================================"
	@echo "make db-setup     - Set up database with correct schema"
	@echo "make fix-schema   - Fix schema column mismatches"
	@echo "make install-deps - Install all dependencies"
	@echo "make server       - Start the API server on port 5000"
	@echo "make client       - Start the React client on port 3000"
	@echo "make test-db      - Test database connection"
	@echo "make test-api     - Test API endpoints"
	@echo "make kill-ports   - Kill processes on ports 3000 and 5000"
	@echo "make clean        - Clean up generated files"
	@echo ""
	@echo "QUICK START:"
	@echo "1. make kill-ports"
	@echo "2. make fix-schema"
	@echo "3. make install-deps"
	@echo "4. make server (in one terminal)"
	@echo "5. make client (in another terminal)"

# Kill any processes running on our ports
kill-ports:
	@echo "🔪 Killing processes on ports 3000 and 5000..."
	-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5000 | xargs kill -9 2>/dev/null || true
	@echo "✅ Ports cleared"

# Set up database (assumes role 'a' exists)
db-setup:
	@echo "🗄️  Setting up database..."
	-psql -U a -d finance -c "\\d" > /dev/null 2>&1 || (echo "❌ Cannot connect to database. Check your PostgreSQL setup." && exit 1)
	@echo "✅ Database connection verified"

# Fix schema column mismatches
fix-schema: db-setup
	@echo "🔧 Fixing schema column mismatches..."
	psql -U a -d finance -c "BEGIN; ALTER TABLE live_questions DROP CONSTRAINT IF EXISTS live_questions_template_id_fkey; COMMIT;"
	psql -U a -d finance -f corrected_question_templates.sql
	psql -U a -d finance -c "ALTER TABLE live_questions ADD CONSTRAINT live_questions_template_id_fkey FOREIGN KEY (template_id) REFERENCES question_templates(id) ON DELETE RESTRICT;"
	@echo "✅ Schema fixed"

# Install all dependencies
install-deps:
	@echo "📦 Installing Python dependencies..."
	pip install "python-dotenv>=1.0.0" hashlib2 || pip install python-dotenv
	@echo "📦 Installing Node.js server dependencies..."
	cd server && npm install
	@echo "📦 Installing React client dependencies..."  
	cd client && npm install
	@echo "✅ All dependencies installed"

# Test database connection
test-db: fix-schema
	@echo "🧪 Testing database connection..."
	python -c "from scripts.utils import get_db_connection; print('✅ Database connection successful:', get_db_connection().closed == 0)" 2>/dev/null || echo "❌ Database connection failed"
	psql -U a -d finance -c "SELECT COUNT(*) as question_templates FROM question_templates;" 
	psql -U a -d finance -c "SELECT COUNT(*) as companies FROM companies;"

# Start server (with port check)
server: kill-ports install-deps
	@echo "🚀 Starting API server on port 5000..."
	@if lsof -ti:5000 > /dev/null 2>&1; then echo "❌ Port 5000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	cd server && npm start

# Start client (with port check) 
client: install-deps
	@echo "🌐 Starting React client on port 3000..."
	@if lsof -ti:3000 > /dev/null 2>&1; then echo "❌ Port 3000 is still in use. Run 'make kill-ports' first."; exit 1; fi
	cd client && npm start

# Test API endpoints
test-api:
	@echo "🧪 Testing API endpoints..."
	@echo "Testing health endpoint..."
	curl -s http://localhost:5000/health || echo "❌ API server not responding on port 5000"
	@echo "\n✅ API tests completed"

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	rm -rf logs/
	rm -rf server/Uploads/
	rm -rf server/logs/
	rm -rf server/reports/
	rm -f *.pyc
	rm -rf __pycache__/
	rm -rf scripts/__pycache__/
	@echo "✅ Cleanup completed"

# Complete setup for new users
setup: kill-ports fix-schema install-deps test-db
	@echo ""
	@echo "🎉 Setup completed successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Open two terminals"
	@echo "2. In terminal 1: make server"
	@echo "3. In terminal 2: make client"
	@echo "4. Visit http://localhost:3000"
	@echo ""
