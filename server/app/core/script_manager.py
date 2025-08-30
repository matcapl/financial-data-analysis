"""
Consolidated script management
Replaces multiple bash scripts with Python-based CLI tools
"""

import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from logging_config import setup_logger, log_with_context

logger = setup_logger('script-manager')


class ScriptManager:
    """Manages deployment and operational scripts"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.server_path = self.project_root / "server"
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the system"""
        try:
            # Test server startup
            result = subprocess.run([
                sys.executable, 
                str(self.server_path / "main.py"),
                "--check"
            ], capture_output=True, text=True, timeout=10)
            
            return {
                "success": result.returncode == 0,
                "message": "Health check completed",
                "output": result.stdout,
                "errors": result.stderr if result.returncode != 0 else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Health check timed out",
                "errors": ["Server startup timeout"]
            }
        except Exception as e:
            return {
                "success": False, 
                "message": f"Health check failed: {str(e)}",
                "errors": [str(e)]
            }
    
    def deploy_start(self, port: Optional[int] = None) -> Dict[str, Any]:
        """Start the server for deployment"""
        try:
            env = {"PORT": str(port or 4000)}
            
            log_with_context(logger, 'info', 'Starting deployment server', 
                port=port or 4000,
                server_path=str(self.server_path)
            )
            
            # Start server
            result = subprocess.run([
                sys.executable,
                str(self.server_path / "main.py")
            ], env=env, cwd=str(self.project_root))
            
            return {
                "success": result.returncode == 0,
                "message": "Server started successfully" if result.returncode == 0 else "Server failed to start",
                "exit_code": result.returncode
            }
            
        except Exception as e:
            log_with_context(logger, 'error', 'Deployment start failed', error=str(e))
            return {
                "success": False,
                "message": f"Deploy start failed: {str(e)}",
                "errors": [str(e)]
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration files"""
        try:
            # Import settings to trigger validation
            sys.path.insert(0, str(self.server_path))
            from app.core.config import settings
            
            return {
                "success": True,
                "message": "Configuration validation passed",
                "config": {
                    "environment": settings.environment,
                    "debug": settings.debug,
                    "host": settings.host,
                    "port": settings.port
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Configuration validation failed: {str(e)}",
                "errors": [str(e)]
            }


# CLI interface functions
def run_health_check():
    """CLI function for health check"""
    manager = ScriptManager()
    result = manager.health_check()
    
    if result["success"]:
        print(f"✓ {result['message']}")
        return 0
    else:
        print(f"✗ {result['message']}")
        if result.get("errors"):
            for error in result["errors"]:
                print(f"  Error: {error}")
        return 1


def run_deploy_start(port: Optional[int] = None):
    """CLI function for deployment start"""
    manager = ScriptManager()
    result = manager.deploy_start(port)
    
    if result["success"]:
        print(f"✓ {result['message']}")
        return 0
    else:
        print(f"✗ {result['message']}")
        return result.get("exit_code", 1)


def run_config_validation():
    """CLI function for config validation"""
    manager = ScriptManager()
    result = manager.validate_config()
    
    if result["success"]:
        print(f"✓ {result['message']}")
        if result.get("config"):
            print("Configuration:")
            for key, value in result["config"].items():
                print(f"  {key}: {value}")
        return 0
    else:
        print(f"✗ {result['message']}")
        if result.get("errors"):
            for error in result["errors"]:
                print(f"  Error: {error}")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Financial Data Analysis Script Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Run health check")
    
    # Deploy start command
    deploy_parser = subparsers.add_parser("deploy", help="Start deployment server")
    deploy_parser.add_argument("--port", type=int, help="Port to run server on")
    
    # Config validation command
    config_parser = subparsers.add_parser("config", help="Validate configuration")
    
    args = parser.parse_args()
    
    if args.command == "health":
        sys.exit(run_health_check())
    elif args.command == "deploy":
        sys.exit(run_deploy_start(args.port))
    elif args.command == "config":
        sys.exit(run_config_validation())
    else:
        parser.print_help()
        sys.exit(1)