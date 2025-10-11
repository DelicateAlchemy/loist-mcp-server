#!/usr/bin/env python3
"""
Database CLI for Loist Music Library MCP Server.

Provides commands for database operations including:
- Migrations (up, down, status)
- Connection testing
- Health checks
- Data operations

Usage:
    python -m database.cli migrate up
    python -m database.cli migrate status
    python -m database.cli health
    python -m database.cli test-connection
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_command(args):
    """Handle migration commands."""
    from database.migrate import DatabaseMigrator
    
    try:
        migrator = DatabaseMigrator(database_url=args.database_url)
        
        if args.migrate_action == 'up':
            logger.info("Applying pending migrations...")
            success = migrator.migrate_up()
            return 0 if success else 1
            
        elif args.migrate_action == 'down':
            if not args.version:
                logger.error("Migration version required for rollback")
                return 1
            logger.info(f"Rolling back migration {args.version}...")
            success = migrator.migrate_down(args.version)
            return 0 if success else 1
            
        elif args.migrate_action == 'status':
            migrator.get_status()
            return 0
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


def health_command(args):
    """Check database health."""
    try:
        from database import get_connection_pool
        
        logger.info("Checking database health...")
        pool = get_connection_pool()
        health = pool.health_check()
        
        if health["healthy"]:
            logger.info("✅ Database is healthy")
            logger.info(f"Database Version: {health['database_version']}")
            logger.info(f"Min Connections: {health['min_connections']}")
            logger.info(f"Max Connections: {health['max_connections']}")
            
            stats = health['stats']
            logger.info(f"Connections Created: {stats['connections_created']}")
            logger.info(f"Queries Executed: {stats['queries_executed']}")
            return 0
        else:
            logger.error("❌ Database health check failed")
            logger.error(f"Error: {health.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 1


def test_connection_command(args):
    """Test database connection."""
    try:
        from database import get_connection
        
        logger.info("Testing database connection...")
        
        with get_connection(retry=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                
                cur.execute("SELECT current_database()")
                database = cur.fetchone()[0]
                
                cur.execute("SELECT current_user")
                user = cur.fetchone()[0]
                
        logger.info("✅ Connection successful")
        logger.info(f"Database: {database}")
        logger.info(f"User: {user}")
        logger.info(f"Version: {version}")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return 1


def stats_command(args):
    """Show connection pool statistics."""
    try:
        from database import get_connection_pool
        
        pool = get_connection_pool()
        stats = pool.get_stats()
        
        print("\n=== Connection Pool Statistics ===")
        print(f"Connections Created: {stats['connections_created']}")
        print(f"Connections Closed: {stats['connections_closed']}")
        print(f"Connections Failed: {stats['connections_failed']}")
        print(f"Queries Executed: {stats['queries_executed']}")
        
        if stats['last_health_check']:
            from datetime import datetime
            last_check = datetime.fromtimestamp(stats['last_health_check'])
            print(f"Last Health Check: {last_check.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return 1


def create_sample_data_command(args):
    """Create sample data for testing."""
    try:
        from database.utils import AudioTrackDB
        from uuid import uuid4
        import random
        
        logger.info(f"Creating {args.count} sample tracks...")
        
        artists = ["The Beatles", "Pink Floyd", "Led Zeppelin", "Queen", "The Rolling Stones"]
        genres = ["Rock", "Pop", "Jazz", "Blues", "Electronic"]
        
        for i in range(args.count):
            track_id = uuid4()
            artist = random.choice(artists)
            track = AudioTrackDB.insert_track(
                track_id=track_id,
                title=f"Sample Track {i+1}",
                audio_path=f"audio/sample-{track_id}.mp3",
                artist=artist,
                album=f"Sample Album {random.randint(1, 10)}",
                genre=random.choice(genres),
                year=random.randint(1960, 2024),
                duration=random.uniform(120.0, 360.0),
                channels=2,
                sample_rate=44100,
                bitrate=320,
                format="mp3"
            )
            
            if (i + 1) % 10 == 0:
                logger.info(f"Created {i + 1} tracks...")
        
        logger.info(f"✅ Successfully created {args.count} sample tracks")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Database CLI for Loist Music Library",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Database migrations')
    migrate_parser.add_argument(
        'migrate_action',
        choices=['up', 'down', 'status'],
        help='Migration action'
    )
    migrate_parser.add_argument(
        '--version',
        help='Migration version (for rollback)'
    )
    migrate_parser.add_argument(
        '--database-url',
        help='Database URL (defaults to config or DATABASE_URL env var)'
    )
    migrate_parser.set_defaults(func=migrate_command)
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check database health')
    health_parser.set_defaults(func=health_command)
    
    # Test connection command
    test_parser = subparsers.add_parser('test-connection', help='Test database connection')
    test_parser.set_defaults(func=test_connection_command)
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show connection pool statistics')
    stats_parser.set_defaults(func=stats_command)
    
    # Create sample data command
    sample_parser = subparsers.add_parser('create-sample-data', help='Create sample data for testing')
    sample_parser.add_argument(
        '--count',
        type=int,
        default=100,
        help='Number of sample tracks to create (default: 100)'
    )
    sample_parser.set_defaults(func=create_sample_data_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

