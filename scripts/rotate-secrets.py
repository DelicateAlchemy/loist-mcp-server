#!/usr/bin/env python3
"""
Secret Rotation Automation Script for Loist Music Library MCP Server

This script provides automated rotation capabilities for different types of secrets
used in the MCP server deployment.

Usage:
    python scripts/rotate-secrets.py --secret-type bearer-token
    python scripts/rotate-secrets.py --secret-type db-password --dry-run
    python scripts/rotate-secrets.py --list-secrets
"""

import argparse
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Google Cloud imports
from google.cloud import secretmanager
from google.cloud import sql
from google.api_core import exceptions as google_exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecretRotator:
    """Handles secret rotation operations."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.secret_client = secretmanager.SecretManagerServiceClient()
        self.sql_client = sql.Client()

    def list_secrets(self) -> List[str]:
        """List all secrets in the project."""
        logger.info(f"Listing secrets in project: {self.project_id}")

        parent = f"projects/{self.project_id}"
        secrets = []

        try:
            for secret in self.secret_client.list_secrets(request={"parent": parent}):
                secrets.append(secret.name.split('/')[-1])
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

        return secrets

    def rotate_bearer_token(self, dry_run: bool = False) -> bool:
        """Rotate the MCP bearer token."""
        secret_name = "mcp-bearer-token"
        logger.info(f"Rotating bearer token secret: {secret_name}")

        if dry_run:
            logger.info("[DRY RUN] Would generate new bearer token and create new secret version")
            return True

        try:
            # Generate new token
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            new_token = ''.join(secrets.choice(alphabet) for _ in range(64))

            # Create new secret version
            secret_path = self.secret_client.secret_path(self.project_id, secret_name)
            payload = new_token.encode('UTF-8')

            response = self.secret_client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": payload}
                }
            )

            logger.info(f"Created new version: {response.name}")
            logger.info("Bearer token rotated successfully")
            logger.info("⚠️  Remember to update client applications with the new token")

            return True

        except Exception as e:
            logger.error(f"Failed to rotate bearer token: {e}")
            return False

    def rotate_database_password(self, dry_run: bool = False) -> bool:
        """Rotate the database password."""
        secret_name = "db-password"
        instance_name = "loist-music-library-db"
        user_name = "music_library_user"

        logger.info(f"Rotating database password for user: {user_name}")

        if dry_run:
            logger.info("[DRY RUN] Would generate new password, update database user, and create new secret version")
            return True

        try:
            # Generate new password
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits + string.punctuation
            # Remove problematic characters for database passwords
            alphabet = alphabet.replace("'", "").replace('"', "").replace('\\', "")
            new_password = ''.join(secrets.choice(alphabet) for _ in range(32))

            # Update database user password
            logger.info(f"Updating password for database user: {user_name}")
            instance = self.sql_client.instance(instance_name)
            user = instance.user(user_name)
            user.update(password=new_password)

            # Create new secret version
            secret_path = self.secret_client.secret_path(self.project_id, secret_name)
            payload = new_password.encode('UTF-8')

            response = self.secret_client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": payload}
                }
            )

            logger.info(f"Created new secret version: {response.name}")
            logger.info("Database password rotated successfully")

            # Trigger deployment to use new password
            logger.info("⚠️  Consider triggering a deployment to use the new password")

            return True

        except Exception as e:
            logger.error(f"Failed to rotate database password: {e}")
            return False

    def get_secret_info(self, secret_name: str) -> Dict:
        """Get information about a secret."""
        try:
            secret_path = self.secret_client.secret_path(self.project_id, secret_name)
            secret = self.secret_client.get_secret(request={"name": secret_path})

            # Get versions
            versions = []
            for version in self.secret_client.list_secret_versions(request={"parent": secret_path}):
                versions.append({
                    'name': version.name.split('/')[-1],
                    'state': version.state.name,
                    'create_time': version.create_time
                })

            return {
                'name': secret_name,
                'create_time': secret.create_time,
                'labels': dict(secret.labels),
                'rotation': getattr(secret, 'rotation', None),
                'versions': versions
            }

        except google_exceptions.NotFound:
            logger.error(f"Secret not found: {secret_name}")
            return {}
        except Exception as e:
            logger.error(f"Failed to get secret info: {e}")
            return {}

    def cleanup_old_versions(self, secret_name: str, keep_versions: int = 5) -> bool:
        """Disable old secret versions, keeping only the most recent ones."""
        logger.info(f"Cleaning up old versions for secret: {secret_name}")

        try:
            secret_path = self.secret_client.secret_path(self.project_id, secret_name)

            # Get all enabled versions
            versions = []
            for version in self.secret_client.list_secret_versions(
                request={"parent": secret_path, "filter": "state:ENABLED"}
            ):
                versions.append(version)

            # Sort by creation time (newest first)
            versions.sort(key=lambda v: v.create_time, reverse=True)

            # Keep the most recent versions, disable the rest
            if len(versions) > keep_versions:
                for version in versions[keep_versions:]:
                    version_id = version.name.split('/')[-1]
                    logger.info(f"Disabling old version: {version_id}")

                    self.secret_client.disable_secret_version(
                        request={"name": version.name}
                    )

                logger.info(f"Cleaned up {len(versions) - keep_versions} old versions")
            else:
                logger.info(f"No cleanup needed, only {len(versions)} versions exist")

            return True

        except Exception as e:
            logger.error(f"Failed to cleanup versions: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Secret rotation automation for MCP server')
    parser.add_argument('--project-id', default=os.getenv('GOOGLE_CLOUD_PROJECT'),
                       help='Google Cloud project ID')
    parser.add_argument('--secret-type', choices=['bearer-token', 'db-password'],
                       help='Type of secret to rotate')
    parser.add_argument('--list-secrets', action='store_true',
                       help='List all secrets in the project')
    parser.add_argument('--info', metavar='SECRET_NAME',
                       help='Get information about a specific secret')
    parser.add_argument('--cleanup', metavar='SECRET_NAME',
                       help='Clean up old versions of a secret')
    parser.add_argument('--keep-versions', type=int, default=5,
                       help='Number of versions to keep when cleaning up (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')

    args = parser.parse_args()

    # Get project ID
    project_id = args.project_id
    if not project_id:
        logger.error("Project ID not provided. Use --project-id or set GOOGLE_CLOUD_PROJECT environment variable")
        sys.exit(1)

    rotator = SecretRotator(project_id)

    if args.list_secrets:
        secrets = rotator.list_secrets()
        if secrets:
            print("Secrets in project:")
            for secret in secrets:
                print(f"  - {secret}")
        else:
            print("No secrets found")
        return

    if args.info:
        info = rotator.get_secret_info(args.info)
        if info:
            print(f"Secret: {info['name']}")
            print(f"Created: {info['create_time']}")
            print(f"Labels: {info['labels']}")
            if info.get('rotation'):
                print(f"Rotation: Next rotation at {info['rotation'].next_rotation_time}")
            print("Versions:")
            for version in info['versions']:
                print(f"  - {version['name']}: {version['state']} ({version['create_time']})")
        return

    if args.cleanup:
        success = rotator.cleanup_old_versions(args.cleanup, args.keep_versions)
        if success:
            print(f"Successfully cleaned up old versions of {args.cleanup}")
        else:
            print(f"Failed to cleanup {args.cleanup}")
            sys.exit(1)
        return

    if args.secret_type:
        success = False

        if args.secret_type == 'bearer-token':
            success = rotator.rotate_bearer_token(args.dry_run)
        elif args.secret_type == 'db-password':
            success = rotator.rotate_database_password(args.dry_run)

        if success:
            if args.dry_run:
                print(f"[DRY RUN] {args.secret_type} rotation would succeed")
            else:
                print(f"Successfully rotated {args.secret_type}")

                # Offer to cleanup old versions
                response = input("Would you like to cleanup old versions? (y/N): ").strip().lower()
                if response == 'y':
                    rotator.cleanup_old_versions(f"{args.secret_type.replace('-', '-')}", 5)
        else:
            print(f"Failed to rotate {args.secret_type}")
            sys.exit(1)

        return

    parser.print_help()


if __name__ == '__main__':
    main()
