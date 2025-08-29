#!/usr/bin/env python3
"""
Consolidated CI/CD Management Script
Replaces multiple bash scripts with a unified Python-based CLI tool
"""

import os
import sys
import subprocess
import time
import requests
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add server modules to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server" / "app" / "services"))

from logging_config import setup_logger, log_with_context

logger = setup_logger('ci-manager')


class CIManager:
    """Consolidated CI/CD operations manager"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.venv_python = self.project_root / ".venv" / "bin" / "python3"
        
        if not self.venv_python.exists():
            raise RuntimeError("Virtual environment not found. Run 'make install' first.")
    
    def log(self, message: str, level: str = "info"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [CI] {message}")
        
        if level == "error":
            log_with_context(logger, 'error', message)
        else:
            log_with_context(logger, 'info', message)
    
    def run_command(self, command: List[str], cwd: Optional[Path] = None, timeout: int = 60) -> Dict[str, Any]:
        """Run a command and return result"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out",
                "timeout": timeout
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def kill_ports(self, ports: List[int] = [3000, 4000]) -> bool:
        """Kill processes on specified ports"""
        self.log(f"Killing processes on ports {ports}...")
        
        all_killed = True
        for port in ports:
            try:
                # Find processes using the port
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True
                )
                
                if result.stdout.strip():
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        if pid:
                            subprocess.run(["kill", "-9", pid], check=False)
                            self.log(f"Killed process {pid} on port {port}")
                
            except Exception as e:
                self.log(f"Warning: Failed to kill port {port}: {e}")
                all_killed = False
        
        self.log("✅ Port cleanup completed")
        return all_killed
    
    def setup_database(self) -> bool:
        """Set up database with migrations and seeding"""
        self.log("🗄️ Setting up database...")
        
        # Run migrations
        migrate_result = self.run_command([
            str(self.venv_python), "migrate.py", "up"
        ], cwd=self.project_root / "database")
        
        if not migrate_result["success"]:
            self.log(f"❌ Database migrations failed: {migrate_result.get('stderr', 'Unknown error')}", "error")
            return False
        
        # Seed database
        seed_result = self.run_command([
            str(self.venv_python), "seed.py"
        ], cwd=self.project_root / "database")
        
        if not seed_result["success"]:
            self.log(f"❌ Database seeding failed: {seed_result.get('stderr', 'Unknown error')}", "error")
            return False
        
        self.log("✅ Database setup completed")
        return True
    
    def check_database(self) -> bool:
        """Check database connectivity and migration status"""
        self.log("🧪 Testing database connection...")
        
        try:
            from utils import get_db_connection
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Test basic connectivity
                    cur.execute("SELECT 1")
                    
                    # Check migration status
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'schema_migrations'
                        )
                    """)
                    
                    if cur.fetchone()[0]:
                        cur.execute("SELECT COUNT(*) FROM schema_migrations")
                        migration_count = cur.fetchone()[0]
                        self.log(f"✅ Database connected. Applied migrations: {migration_count}")
                    else:
                        self.log("✅ Database connected. No migrations table found.")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Database check failed: {e}", "error")
            return False
    
    def check_application_health(self, url: str = "http://localhost:4000", timeout: int = 30) -> bool:
        """Check application health endpoint"""
        self.log("🧪 Testing application health...")
        
        health_url = f"{url}/health"
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"✅ Application health check passed - Status: {data.get('status')}")
                    return True
                else:
                    self.log(f"⚠️ Health endpoint returned {response.status_code}")
                    
            except requests.RequestException as e:
                self.log(f"⏳ Application not ready, retry {attempt + 1}/{max_retries}... ({e})")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        self.log("❌ Application health check failed", "error")
        return False
    
    def run_tests(self, test_type: str = "all") -> bool:
        """Run test suites"""
        self.log(f"🧪 Running {test_type} tests...")
        
        if test_type in ["all", "unit"]:
            unit_result = self.run_command([
                str(self.venv_python), "-m", "pytest", "tests/unit/", "-v"
            ])
            
            if not unit_result["success"]:
                self.log("❌ Unit tests failed", "error")
                print(unit_result.get("stderr", ""))
                return False
            
            self.log("✅ Unit tests passed")
        
        if test_type in ["all", "integration"]:
            integration_result = self.run_command([
                str(self.venv_python), "-m", "pytest", "tests/integration/", "-v"
            ])
            
            if not integration_result["success"]:
                self.log("❌ Integration tests failed", "error")
                return False
            
            self.log("✅ Integration tests passed")
        
        return True
    
    def deploy_start(self, port: int = 4000) -> bool:
        """Start deployment with database setup"""
        self.log("🚀 Starting production deployment...")
        
        # Verify environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.log("❌ DATABASE_URL must be set for deployment", "error")
            return False
        
        self.log(f"Using database: {database_url[:50]}...")
        
        # Run migrations (non-critical errors logged but don't fail deployment)
        self.log("Running database migrations...")
        migrate_result = self.run_command([
            str(self.venv_python), "migrate.py", "up"
        ], cwd=self.project_root / "database")
        
        if migrate_result["success"]:
            self.log("✅ Database migrations completed")
        else:
            self.log(f"⚠️ Migration warning: {migrate_result.get('stderr', 'Unknown error')}")
        
        # Update rollback SQL (non-critical)
        rollback_result = self.run_command([
            str(self.venv_python), "migrate.py", "update-rollback"
        ], cwd=self.project_root / "database")
        
        if not rollback_result["success"]:
            self.log("⚠️ Warning: Failed to update rollback SQL (non-critical)")
        
        # Seed database (non-critical for production)
        seed_result = self.run_command([
            str(self.venv_python), "seed.py"
        ], cwd=self.project_root / "database")
        
        if not seed_result["success"]:
            self.log("⚠️ Warning: Database seeding failed (non-critical for production)")
        
        # Show migration status
        status_result = self.run_command([
            str(self.venv_python), "migrate.py", "status"
        ], cwd=self.project_root / "database")
        
        if status_result["success"]:
            self.log("Final migration status:")
            print(status_result["stdout"])
        
        # Start server
        self.log(f"Starting FastAPI server on port {port}...")
        
        env = os.environ.copy()
        env["PORT"] = str(port)
        
        try:
            subprocess.run([
                str(self.venv_python), "server/main.py"
            ], env=env, cwd=self.project_root)
            return True
            
        except KeyboardInterrupt:
            self.log("Server stopped by user")
            return True
        except Exception as e:
            self.log(f"❌ Server failed to start: {e}", "error")
            return False
    
    def validate_config(self) -> bool:
        """Validate configuration files"""
        self.log("🔍 Validating configuration...")
        
        # Test settings import
        try:
            sys.path.insert(0, str(self.project_root / "server"))
            from app.core.config import settings
            
            self.log(f"✅ Configuration valid - Environment: {settings.environment}")
            return True
            
        except Exception as e:
            self.log(f"❌ Configuration validation failed: {e}", "error")
            return False
    
    def clean_cache(self) -> bool:
        """Clean up cache files and temporary data"""
        self.log("🧹 Cleaning cache and temporary files...")
        
        patterns = [
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
            ".pytest_cache",
            "logs/"
        ]
        
        cleaned = 0
        for pattern in patterns:
            for path in self.project_root.rglob(pattern):
                if path.is_dir():
                    try:
                        import shutil
                        shutil.rmtree(path)
                        cleaned += 1
                    except Exception:
                        pass
                elif path.is_file():
                    try:
                        path.unlink()
                        cleaned += 1
                    except Exception:
                        pass
        
        self.log(f"✅ Cleaned {cleaned} cache files")
        return True
    
    def run_full_check(self) -> bool:
        """Run complete CI health check"""
        self.log("🔍 Running complete CI health check...")
        
        checks = [
            ("Configuration", self.validate_config),
            ("Database", self.check_database),
            ("Tests", lambda: self.run_tests("unit")),
        ]
        
        all_passed = True
        for name, check_func in checks:
            if not check_func():
                all_passed = False
                self.log(f"❌ {name} check failed", "error")
            else:
                self.log(f"✅ {name} check passed")
        
        return all_passed


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Financial Data Analysis CI/CD Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Run health checks")
    health_parser.add_argument("--url", default="http://localhost:4000", help="Application URL")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Start deployment")
    deploy_parser.add_argument("--port", type=int, default=4000, help="Port to deploy on")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--type", choices=["unit", "integration", "all"], default="all")
    
    # Database command
    db_parser = subparsers.add_parser("db", help="Database operations")
    db_subparsers = db_parser.add_subparsers(dest="db_command")
    db_subparsers.add_parser("setup", help="Setup database")
    db_subparsers.add_parser("check", help="Check database")
    
    # Utility commands
    subparsers.add_parser("clean", help="Clean cache files")
    subparsers.add_parser("kill-ports", help="Kill processes on ports 3000,4000")
    subparsers.add_parser("validate", help="Validate configuration")
    subparsers.add_parser("check-all", help="Run all CI checks")
    
    args = parser.parse_args()
    
    try:
        ci = CIManager()
        
        if args.command == "health":
            success = ci.check_application_health(args.url)
        elif args.command == "deploy":
            success = ci.deploy_start(args.port)
        elif args.command == "test":
            success = ci.run_tests(args.type)
        elif args.command == "db":
            if args.db_command == "setup":
                success = ci.setup_database()
            elif args.db_command == "check":
                success = ci.check_database()
            else:
                print("Database subcommand required: setup or check")
                return 1
        elif args.command == "clean":
            success = ci.clean_cache()
        elif args.command == "kill-ports":
            success = ci.kill_ports()
        elif args.command == "validate":
            success = ci.validate_config()
        elif args.command == "check-all":
            success = ci.run_full_check()
        else:
            parser.print_help()
            return 1
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ CI Manager failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())