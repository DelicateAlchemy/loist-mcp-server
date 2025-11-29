#!/usr/bin/env python3
"""
Run database migrations using Python and database connection pool.
This is more reliable than shell scripts for database operations.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the database directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / 'database'))

def get_secret(secret_name):
    """Get a secret value using gcloud CLI."""
    try:
        result = subprocess.run(
            ['gcloud', 'secrets', 'versions', 'access', 'latest', f'--secret={secret_name}'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def run_migrations(environment='auto'):
    """Run database migrations for the specified environment."""

    print("Running database migrations...")

    # Determine which secrets to use based on environment
    if environment in ['production', 'auto']:
        print("Trying production environment...")
        db_password = get_secret('db-password')
        db_connection_name = get_secret('db-connection-name')
        db_name = get_secret('db-name')
    else:
        db_password = None
        db_connection_name = None
        db_name = None

    # If production secrets not available or staging requested, try staging
    if (not db_password or not db_connection_name or environment == 'staging') and environment != 'production':
        if environment == 'auto':
            print("Production secrets not available, trying staging...")
        db_password = get_secret('db-password-staging')
        db_connection_name = get_secret('db-connection-name-staging')
        db_name = get_secret('db-name-staging') or 'loist_mvp_staging'

    if not db_password or not db_connection_name:
        print("Database secrets not available:")
        print(f"  DB_PASSWORD: {'set' if db_password else 'not set'}")
        print(f"  DB_CONNECTION_NAME: {'set' if db_connection_name else 'not set'}")
        print("Skipping migrations")
        return False

    print(f"Connecting to database: {db_connection_name}")

    # Start Cloud SQL proxy
    print("Starting Cloud SQL proxy...")
    import subprocess
    proxy_process = subprocess.Popen([
        './cloud_sql_proxy',
        f'-instances={db_connection_name}=tcp:5432'
    ])

    # Wait for proxy to start
    import time
    time.sleep(5)

    try:
        # Set environment variables for database connection
        os.environ['DB_HOST'] = 'localhost'
        os.environ['DB_PORT'] = '5432'
        os.environ['DB_NAME'] = db_name
        os.environ['DB_USER'] = 'music_library_user'
        os.environ['DB_PASSWORD'] = db_password

        # Set DATABASE_URL for the migrator (local proxy format)
        database_url = f'postgresql://music_library_user:{db_password}@localhost:5432/{db_name}'
        os.environ['DATABASE_URL'] = database_url

        # Import database modules
        from migrate import DatabaseMigrator

        # Run migrations
        migrator = DatabaseMigrator()

        # Show current status
        print("Checking current migration status...")
        migrator.get_status()

        # Apply all pending migrations
        print("\nApplying pending migrations...")
        success = migrator.migrate_up()

        if success:
            print("\n✅ All migrations completed successfully!")
            return True
        else:
            print("\n❌ Migration failed!")
            return False

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up Cloud SQL proxy
        print("Cleaning up Cloud SQL proxy...")
        try:
            proxy_process.terminate()
            proxy_process.wait(timeout=10)
        except Exception as e:
            print(f"Warning: Failed to clean up proxy: {e}")
            try:
                proxy_process.kill()
            except:
                pass

if __name__ == '__main__':
    environment = sys.argv[1] if len(sys.argv) > 1 else 'auto'
    success = run_migrations(environment)
    sys.exit(0 if success else 1)
