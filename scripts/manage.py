#!/usr/bin/env python3
"""
Unified Management Script
Consolidates generate_questions.py, manage_aliases.py, validate_yaml.py, and other utilities
"""

import sys
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Add server modules to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server" / "app" / "services"))

from logging_config import setup_logger, log_with_context

logger = setup_logger('manage-script')


class ManagementTool:
    """Unified management operations"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.venv_python = self.project_root / ".venv" / "bin" / "python3"
    
    def validate_yaml_files(self) -> bool:
        """Validate all YAML configuration files"""
        print("🔍 Validating YAML configuration files...")
        
        yaml_files = list(self.config_dir.glob("*.yaml"))
        if not yaml_files:
            print("❌ No YAML files found in config directory")
            return False
        
        all_valid = True
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    yaml.safe_load(f)
                print(f"✅ {yaml_file.name} - Valid")
            except yaml.YAMLError as e:
                print(f"❌ {yaml_file.name} - Invalid: {e}")
                all_valid = False
            except Exception as e:
                print(f"❌ {yaml_file.name} - Error: {e}")
                all_valid = False
        
        return all_valid
    
    def manage_aliases(self, action: str, alias: str = None, canonical: str = None) -> bool:
        """Manage period aliases in periods.yaml"""
        periods_file = self.config_dir / "periods.yaml"
        
        if not periods_file.exists():
            print("❌ periods.yaml not found")
            return False
        
        try:
            with open(periods_file, 'r') as f:
                periods_data = yaml.safe_load(f)
            
            if action == "list":
                print("📋 Period Aliases:")
                for canonical_name, config in periods_data.get("period_aliases", {}).items():
                    aliases = config.get("aliases", [])
                    print(f"  {canonical_name}: {', '.join(aliases)}")
                return True
            
            elif action == "add":
                if not alias or not canonical:
                    print("❌ Both --alias and --canonical required for add")
                    return False
                
                if "period_aliases" not in periods_data:
                    periods_data["period_aliases"] = {}
                
                if canonical not in periods_data["period_aliases"]:
                    periods_data["period_aliases"][canonical] = {"aliases": []}
                
                if alias not in periods_data["period_aliases"][canonical]["aliases"]:
                    periods_data["period_aliases"][canonical]["aliases"].append(alias)
                    
                    with open(periods_file, 'w') as f:
                        yaml.safe_dump(periods_data, f, default_flow_style=False)
                    
                    print(f"✅ Added alias '{alias}' for '{canonical}'")
                    return True
                else:
                    print(f"⚠️ Alias '{alias}' already exists for '{canonical}'")
                    return True
            
            elif action == "remove":
                if not alias or not canonical:
                    print("❌ Both --alias and --canonical required for remove")
                    return False
                
                if (canonical in periods_data.get("period_aliases", {}) and 
                    alias in periods_data["period_aliases"][canonical].get("aliases", [])):
                    
                    periods_data["period_aliases"][canonical]["aliases"].remove(alias)
                    
                    with open(periods_file, 'w') as f:
                        yaml.safe_dump(periods_data, f, default_flow_style=False)
                    
                    print(f"✅ Removed alias '{alias}' from '{canonical}'")
                    return True
                else:
                    print(f"❌ Alias '{alias}' not found for '{canonical}'")
                    return False
            
            else:
                print("❌ Invalid action. Use: list, add, or remove")
                return False
                
        except Exception as e:
            print(f"❌ Failed to manage aliases: {e}")
            return False
    
    def generate_questions(self, company_id: int = None) -> bool:
        """Generate analytical questions for companies"""
        print("🧠 Generating analytical questions...")
        
        try:
            from questions_engine import main as generate_questions_main
            
            if company_id:
                # Generate for specific company
                result = generate_questions_main(company_id)
                print(f"✅ Generated questions for company {company_id}")
                return True
            else:
                # Generate for all companies with data
                from utils import get_db_connection
                
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT DISTINCT company_id FROM financial_data")
                        company_ids = [row[0] for row in cur.fetchall()]
                
                if not company_ids:
                    print("⚠️ No companies with financial data found")
                    return True
                
                for cid in company_ids:
                    try:
                        generate_questions_main(cid)
                        print(f"✅ Generated questions for company {cid}")
                    except Exception as e:
                        print(f"❌ Failed to generate questions for company {cid}: {e}")
                
                print(f"✅ Question generation completed for {len(company_ids)} companies")
                return True
                
        except Exception as e:
            print(f"❌ Question generation failed: {e}")
            return False
    
    def generate_periods_yaml(self) -> bool:
        """Generate periods.yaml configuration"""
        print("📅 Generating periods.yaml configuration...")
        
        try:
            from generate_periods_yaml2 import main as generate_periods_main
            
            result = generate_periods_main()
            print("✅ periods.yaml generation completed")
            return True
            
        except Exception as e:
            print(f"❌ periods.yaml generation failed: {e}")
            return False


def main():
    """CLI entry point for management tool"""
    parser = argparse.ArgumentParser(description="Financial Data Analysis Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # YAML validation
    subparsers.add_parser("validate-yaml", help="Validate YAML configuration files")
    
    # Alias management
    alias_parser = subparsers.add_parser("aliases", help="Manage period aliases")
    alias_parser.add_argument("action", choices=["list", "add", "remove"])
    alias_parser.add_argument("--alias", help="Alias name")
    alias_parser.add_argument("--canonical", help="Canonical period name")
    
    # Question generation
    questions_parser = subparsers.add_parser("questions", help="Generate analytical questions")
    questions_parser.add_argument("--company-id", type=int, help="Specific company ID (optional)")
    
    # Configuration generation
    subparsers.add_parser("generate-periods", help="Generate periods.yaml configuration")
    
    args = parser.parse_args()
    
    try:
        tool = ManagementTool()
        
        if args.command == "validate-yaml":
            success = tool.validate_yaml_files()
        elif args.command == "aliases":
            success = tool.manage_aliases(args.action, args.alias, args.canonical)
        elif args.command == "questions":
            success = tool.generate_questions(args.company_id)
        elif args.command == "generate-periods":
            success = tool.generate_periods_yaml()
        else:
            parser.print_help()
            return 1
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Management tool failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())