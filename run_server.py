#!/usr/bin/env python3
"""
Server runner script that fixes module import issues.
This script properly sets up the Python path and runs the MCP server.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables for local development only (not for Cloud Run)
# Cloud Run provides these via environment variables/secrets
if not os.getenv('GOOGLE_CLOUD_PROJECT'):  # Only set defaults if not running on Cloud Run
    os.environ.setdefault('DATABASE_URL', 'postgresql://loist_user:dev_password@localhost:5432/loist_mvp')
    os.environ.setdefault('GCS_PROJECT_ID', 'loist-music-library')
    os.environ.setdefault('GCS_BUCKET_NAME', 'loist-mvp-audio-files')
    os.environ.setdefault('GCS_REGION', 'us-central1')
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', './service-account-key.json')
    os.environ.setdefault('SERVER_TRANSPORT', 'http')
    os.environ.setdefault('SERVER_PORT', '8080')
    os.environ.setdefault('AUTH_ENABLED', 'false')
    os.environ.setdefault('ENABLE_CORS', 'true')
    os.environ.setdefault('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000,http://localhost:5173')

# Now import and run the server
if __name__ == "__main__":
    from src.server import mcp
    
    # Run the server
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8080
    )
