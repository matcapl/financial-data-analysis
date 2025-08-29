#!/usr/bin/env python3
"""
Database Migration System
Replaces YAML-based schema generation with proper database migrations

Usage:
    python migrate.py up                    # Apply all pending migrations
    python migrate.py down                  # Rollback last migration
    python migrate.py status                # Show migration status
    python migrate.py create "description"  # Create new migration file
    python migrate.py reset                 # Rollback all migrations (dangerous)
"""

import os
import sys
import hashlib
import psycopg2
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.app.services.utils import get_db_connection
    from server.app.services.logging_config import setup_logger, log_with_context
except ImportError:
    print("Error: Could not import database utilities. Make sure you're in the project root.")
    sys.exit(1)

logger = setup_logger('database-migrations')

class MigrationManager:
    def __init__(self):
        self.migrations_dir = Path(__file__).parent / 'migrations'
        self.migrations_dir.mkdir(exist_ok=True)
        
    def get_connection(self):
        """Get database connection"""
        try:
            return get_db_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def ensure_migrations_table(self):
        """Create migrations table if it doesn't exist"""
        init_migration = self.migrations_dir / '000_create_migrations_table.sql'
        if not init_migration.exists():
            raise FileNotFoundError("Migration 000_create_migrations_table.sql not found")
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'schema_migrations'
                    );
                """)
                
                if not cur.fetchone()[0]:
                    # Execute initialization migration
                    with open(init_migration) as f:
                        cur.execute(f.read())
                    conn.commit()
                    log_with_context(logger, 'info', 'Migrations table created')
    
    def get_migration_files(self) -> List[Path]:
        """Get all migration files sorted by version"""
        files = []
        for file in self.migrations_dir.glob('*.sql'):
            if file.name.startswith('000_'):
                continue  # Skip initialization migration
            files.append(file)
        
        # Sort by version number
        files.sort(key=lambda x: x.name.split('_')[0])
        return files
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        self.ensure_migrations_table()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version FROM schema_migrations ORDER BY version")
                return [row[0] for row in cur.fetchall()]
    
    def get_pending_migrations(self) -> List[Path]:
        """Get list of pending migration files"""
        all_files = self.get_migration_files()
        applied = set(self.get_applied_migrations())
        
        pending = []
        for file in all_files:
            version = file.name.split('_')[0]
            if version not in applied:
                pending.append(file)
        
        return pending
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of migration file"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def parse_migration_file(self, file_path: Path) -> Tuple[str, str, str, str]:
        """Parse migration file to extract metadata and rollback SQL"""
        content = file_path.read_text()
        lines = content.split('\n')
        
        version = file_path.name.split('_')[0]
        description = file_path.name.replace(f"{version}_", "").replace(".sql", "").replace("_", " ")
        
        # Look for description in comments
        for line in lines:
            if line.startswith('-- Description:'):
                description = line.replace('-- Description:', '').strip()
                break
        
        # Extract rollback SQL from ROLLBACK_START/ROLLBACK_END markers
        rollback_sql = None
        in_rollback = False
        rollback_lines = []
        
        for line in lines:
            if '/*ROLLBACK_START' in line:
                in_rollback = True
                continue
            elif 'ROLLBACK_END*/' in line:
                in_rollback = False
                continue
            elif in_rollback:
                # Skip comment lines and empty lines in rollback section
                line = line.strip()
                if line and not line.startswith('--'):
                    rollback_lines.append(line)
        
        if rollback_lines:
            rollback_sql = '\n'.join(rollback_lines)
        
        # Remove rollback section from main SQL content
        main_sql_lines = []
        skip_rollback = False
        for line in lines:
            if '/*ROLLBACK_START' in line:
                skip_rollback = True
                continue
            elif 'ROLLBACK_END*/' in line:
                skip_rollback = False
                continue
            elif not skip_rollback:
                main_sql_lines.append(line)
        
        main_content = '\n'.join(main_sql_lines).strip()
        
        return version, description, main_content, rollback_sql
    
    def apply_migration(self, file_path: Path) -> bool:
        """Apply a single migration"""
        try:
            version, description, content, rollback_sql = self.parse_migration_file(file_path)
            checksum = self.calculate_checksum(file_path)
            
            log_with_context(logger, 'info', f'Applying migration {version}', 
                           version=version, description=description, has_rollback=rollback_sql is not None)
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Execute migration
                    cur.execute(content)
                    
                    # Record migration with rollback SQL
                    cur.execute("""
                        INSERT INTO schema_migrations (version, description, rollback_sql, checksum) 
                        VALUES (%s, %s, %s, %s)
                    """, (version, description, rollback_sql, checksum))
                    
                    conn.commit()
            
            log_with_context(logger, 'info', f'Migration {version} applied successfully',
                           version=version)
            return True
            
        except Exception as e:
            logger.error(f'Failed to apply migration {file_path.name}: {e}')
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get rollback SQL
                    cur.execute("SELECT rollback_sql FROM schema_migrations WHERE version = %s", (version,))
                    result = cur.fetchone()
                    
                    if not result or not result[0]:
                        log_with_context(logger, 'warn', f'No rollback SQL found for migration {version}',
                                       version=version)
                        return False
                    
                    rollback_sql = result[0]
                    
                    # Execute rollback
                    cur.execute(rollback_sql)
                    
                    # Remove migration record
                    cur.execute("DELETE FROM schema_migrations WHERE version = %s", (version,))
                    
                    conn.commit()
            
            log_with_context(logger, 'info', f'Migration {version} rolled back successfully',
                           version=version)
            return True
            
        except Exception as e:
            logger.error(f'Failed to rollback migration {version}: {e}')
            return False
    
    def migrate_up(self) -> bool:
        """Apply all pending migrations"""
        pending = self.get_pending_migrations()
        
        if not pending:
            log_with_context(logger, 'info', 'No pending migrations')
            return True
        
        log_with_context(logger, 'info', f'Applying {len(pending)} migrations')
        
        success = True
        for migration_file in pending:
            if not self.apply_migration(migration_file):
                success = False
                break
        
        return success
    
    def migrate_down(self) -> bool:
        """Rollback the last migration"""
        applied = self.get_applied_migrations()
        
        if len(applied) <= 1:  # Keep the initialization migration
            log_with_context(logger, 'info', 'No migrations to rollback')
            return True
        
        latest_version = applied[-1]
        return self.rollback_migration(latest_version)
    
    def update_rollback_sql(self) -> bool:
        """Update existing migrations with rollback SQL from migration files"""
        try:
            migration_files = self.get_migration_files()
            updated_count = 0
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for file in migration_files:
                        try:
                            version, description, content, rollback_sql = self.parse_migration_file(file)
                            
                            if rollback_sql:
                                # Update existing migration with rollback SQL
                                cur.execute("""
                                    UPDATE schema_migrations 
                                    SET rollback_sql = %s 
                                    WHERE version = %s AND rollback_sql IS NULL
                                """, (rollback_sql, version))
                                
                                if cur.rowcount > 0:
                                    updated_count += 1
                                    log_with_context(logger, 'info', f'Updated rollback SQL for migration {version}',
                                                   version=version)
                        
                        except Exception as e:
                            log_with_context(logger, 'warn', f'Failed to update rollback SQL for {file.name}',
                                           error=str(e))
                    
                    conn.commit()
            
            log_with_context(logger, 'info', f'Updated rollback SQL for {updated_count} migrations',
                           count=updated_count)
            return True
            
        except Exception as e:
            logger.error(f'Failed to update rollback SQL: {e}')
            return False
    
    def show_status(self):
        """Show current migration status"""
        try:
            applied = self.get_applied_migrations()
            pending = self.get_pending_migrations()
            
            print("\\n=== Migration Status ===")
            print(f"Applied migrations: {len(applied)}")
            print(f"Pending migrations: {len(pending)}")
            
            if applied:
                print("\\nApplied:")
                for version in applied:
                    print(f"  ✓ {version}")
            
            if pending:
                print("\\nPending:")
                for file in pending:
                    version = file.name.split('_')[0]
                    print(f"  ⏳ {version} - {file.name}")
            
            print()
            
        except Exception as e:
            logger.error(f'Failed to show status: {e}')
    
    def create_migration(self, description: str) -> str:
        """Create a new migration file"""
        # Get next version number
        existing_files = self.get_migration_files()
        if existing_files:
            latest_version = int(existing_files[-1].name.split('_')[0])
            next_version = f"{latest_version + 1:03d}"
        else:
            next_version = "001"
        
        # Create filename
        safe_description = description.lower().replace(' ', '_').replace('-', '_')
        filename = f"{next_version}_{safe_description}.sql"
        file_path = self.migrations_dir / filename
        
        # Create migration template
        template = f"""-- Migration: {description}
-- Version: {next_version}
-- Description: {description}
-- Author: Developer
-- Date: {datetime.now().strftime('%Y-%m-%d')}

-- Migration Up (Apply changes)


-- Migration Down (Rollback changes - update schema_migrations.rollback_sql manually if needed)
-- This migration does not support automatic rollback
"""
        
        file_path.write_text(template)
        
        log_with_context(logger, 'info', f'Created migration {filename}',
                       version=next_version, description=description)
        
        print(f"Created migration: {file_path}")
        print(f"Edit the file to add your SQL statements, then run: python migrate.py up")
        
        return str(file_path)

def main():
    parser = argparse.ArgumentParser(description='Database Migration Manager')
    parser.add_argument('command', choices=['up', 'down', 'status', 'create', 'reset', 'update-rollback'])
    parser.add_argument('description', nargs='?', help='Description for new migration')
    
    args = parser.parse_args()
    
    manager = MigrationManager()
    
    try:
        if args.command == 'up':
            success = manager.migrate_up()
            sys.exit(0 if success else 1)
            
        elif args.command == 'down':
            success = manager.migrate_down()
            sys.exit(0 if success else 1)
            
        elif args.command == 'status':
            manager.show_status()
            
        elif args.command == 'create':
            if not args.description:
                print("Error: Description required for creating migration")
                print("Usage: python migrate.py create 'Add user table'")
                sys.exit(1)
            manager.create_migration(args.description)
            
        elif args.command == 'reset':
            print("⚠️  WARNING: This will rollback ALL migrations!")
            confirm = input("Type 'yes' to continue: ")
            if confirm.lower() == 'yes':
                applied = manager.get_applied_migrations()
                for version in reversed(applied[1:]):  # Skip migration 000
                    manager.rollback_migration(version)
                print("All migrations rolled back.")
            else:
                print("Reset cancelled.")
                
        elif args.command == 'update-rollback':
            success = manager.update_rollback_sql()
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\\nOperation cancelled.")
        sys.exit(1)
    except Exception as e:
        logger.error(f'Migration failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()