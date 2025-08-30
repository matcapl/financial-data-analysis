#!/usr/bin/env python3
"""
Database Transient Data Cleanup Script

Safely removes temporary/transient data from the database for development and testing.
PRODUCTION PROTECTED: Will refuse to run in production environment.

Usage:
    python scripts/cleanup_transient_data.py [--confirm] [--dry-run]
    
Options:
    --confirm   Proceed without interactive confirmation
    --dry-run   Show what would be deleted without executing
"""

import sys
import os
import argparse
import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / 'server'))

try:
    from app.utils.utils import get_db_connection
    from app.core.config import settings
except ImportError:
    print("ERROR: Could not import required modules. Run from project root.")
    sys.exit(1)


class DatabaseCleaner:
    """Handles safe cleanup of transient database data"""
    
    # Define what constitutes transient vs persistent data
    TRANSIENT_TABLES = {
        # Data that changes frequently and can be regenerated
        'financial_metrics': 'User uploaded financial data',
        'derived_metrics': 'Calculated metrics from financial data', 
        'questions': 'Generated analytical questions',
        'live_questions': 'Active question states',
        'question_logs': 'Question change logs',
        'generated_reports': 'PDF report metadata',
    }
    
    PERSISTENT_TABLES = {
        # Core configuration and reference data to preserve
        'companies': 'Company master data',
        'periods': 'Period definitions (months, quarters, years)',
        'line_item_definitions': 'Financial metric definitions',
        'question_templates': 'Question generation templates',
    }
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.environment = settings.environment
        self.deleted_counts = {}
        
    def check_environment_safety(self):
        """Prevent execution in production environment"""
        print(f"🔍 Environment check: {self.environment}")
        
        if self.environment == "production":
            print("🚫 PRODUCTION ENVIRONMENT DETECTED!")
            print("   This script is designed for development and testing only.")
            print("   Execution blocked to prevent data loss.")
            return False
            
        if self.environment not in ["development", "test", "staging"]:
            print(f"⚠️  Unknown environment '{self.environment}'")
            print("   This script only runs in: development, test, staging")
            return False
            
        print(f"✅ Environment '{self.environment}' is safe for cleanup")
        return True
    
    def get_database_info(self):
        """Get database connection info for verification"""
        db_url = os.getenv('DATABASE_URL', settings.database.url)
        
        # Extract database name from URL for display (mask credentials)
        if 'postgresql://' in db_url:
            try:
                # Extract just the database name
                db_name = db_url.split('/')[-1].split('?')[0]
                host_part = db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'localhost'
                return f"Database: {db_name} on {host_part}"
            except:
                return "Database: [connection string parsing failed]"
        
        return f"Database: {db_url[:50]}..."
    
    def show_cleanup_plan(self):
        """Display what will be cleaned up"""
        print(f"\n📋 CLEANUP PLAN")
        print(f"   Environment: {self.environment}")
        print(f"   {self.get_database_info()}")
        print(f"   Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        
        print(f"\n🗑️  TRANSIENT DATA TO BE REMOVED:")
        for table, description in self.TRANSIENT_TABLES.items():
            print(f"   • {table:<20} - {description}")
            
        print(f"\n💾 PERSISTENT DATA TO PRESERVE:")
        for table, description in self.PERSISTENT_TABLES.items():
            print(f"   • {table:<20} - {description}")
    
    def count_records(self, conn, table_name):
        """Get record count for a table"""
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cur.fetchone()[0]
        except Exception as e:
            print(f"   Warning: Could not count {table_name}: {e}")
            return 0
    
    def show_current_data_summary(self, conn):
        """Show current record counts"""
        print(f"\n📊 CURRENT DATA SUMMARY:")
        
        all_tables = {**self.TRANSIENT_TABLES, **self.PERSISTENT_TABLES}
        
        for table in all_tables:
            count = self.count_records(conn, table)
            status = "🗑️" if table in self.TRANSIENT_TABLES else "💾"
            print(f"   {status} {table:<20}: {count:>8,} records")
    
    def cleanup_transient_data(self, conn):
        """Remove transient data from specified tables"""
        print(f"\n🧹 {'SIMULATING' if self.dry_run else 'EXECUTING'} CLEANUP...")
        
        total_deleted = 0
        
        # Clean in reverse dependency order to avoid foreign key issues
        cleanup_order = [
            'question_logs',
            'live_questions', 
            'questions',
            'derived_metrics',
            'generated_reports',
            'financial_metrics',
        ]
        
        with conn.cursor() as cur:
            for table in cleanup_order:
                if table in self.TRANSIENT_TABLES:
                    try:
                        # Get count first
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        
                        if count > 0:
                            if not self.dry_run:
                                # Execute deletion
                                cur.execute(f"DELETE FROM {table}")
                                conn.commit()
                                print(f"   ✅ Deleted {count:,} records from {table}")
                            else:
                                print(f"   🔍 Would delete {count:,} records from {table}")
                            
                            self.deleted_counts[table] = count
                            total_deleted += count
                        else:
                            print(f"   ⚪ {table} is already empty")
                            
                    except Exception as e:
                        print(f"   ❌ Error cleaning {table}: {e}")
                        conn.rollback()
        
        return total_deleted
    
    def cleanup_file_uploads(self):
        """Clean up uploaded files and generated reports"""
        print(f"\n📁 {'SIMULATING' if self.dry_run else 'EXECUTING'} FILE CLEANUP...")
        
        directories_to_clean = [
            project_root / "uploads",
            project_root / "reports", 
            project_root / "data" / "processed"  # If exists
        ]
        
        total_files = 0
        
        for directory in directories_to_clean:
            if directory.exists():
                files = list(directory.glob("*"))
                file_count = len([f for f in files if f.is_file()])
                
                if file_count > 0:
                    if not self.dry_run:
                        for file in files:
                            if file.is_file():
                                file.unlink()
                        print(f"   ✅ Deleted {file_count} files from {directory.name}/")
                    else:
                        print(f"   🔍 Would delete {file_count} files from {directory.name}/")
                    
                    total_files += file_count
                else:
                    print(f"   ⚪ {directory.name}/ is already empty")
            else:
                print(f"   ⚪ {directory.name}/ does not exist")
        
        return total_files
    
    def show_cleanup_summary(self, deleted_records, deleted_files):
        """Display cleanup results"""
        print(f"\n📈 CLEANUP SUMMARY:")
        print(f"   Environment: {self.environment}")
        print(f"   Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Mode: {'DRY RUN' if self.dry_run else 'EXECUTED'}")
        
        print(f"\n   Database Records {'Simulated' if self.dry_run else 'Deleted'}: {deleted_records:,}")
        for table, count in self.deleted_counts.items():
            print(f"     • {table}: {count:,}")
        
        print(f"\n   Files {'Simulated' if self.dry_run else 'Deleted'}: {deleted_files:,}")
        
        if self.dry_run:
            print(f"\n💡 To execute cleanup, run: python {sys.argv[0]} --confirm")
        else:
            print(f"\n✅ Cleanup completed successfully!")


def main():
    parser = argparse.ArgumentParser(description="Clean transient data from database")
    parser.add_argument('--confirm', action='store_true', 
                       help='Skip confirmation prompts')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without executing')
    
    args = parser.parse_args()
    
    print("🧹 Financial Data Analysis - Transient Data Cleanup")
    print("=" * 60)
    
    cleaner = DatabaseCleaner(dry_run=args.dry_run)
    
    # Environment safety check
    if not cleaner.check_environment_safety():
        sys.exit(1)
    
    try:
        with get_db_connection() as conn:
            # Show what we're about to do
            cleaner.show_cleanup_plan()
            cleaner.show_current_data_summary(conn)
            
            # Confirmation for non-dry-run
            if not args.dry_run and not args.confirm:
                print(f"\n⚠️  This will permanently delete transient data!")
                response = input("Continue? (yes/no): ").lower().strip()
                if response != 'yes':
                    print("Cleanup cancelled.")
                    sys.exit(0)
            
            # Execute cleanup
            deleted_records = cleaner.cleanup_transient_data(conn)
            deleted_files = cleaner.cleanup_file_uploads()
            
            # Show results
            cleaner.show_cleanup_summary(deleted_records, deleted_files)
            
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()