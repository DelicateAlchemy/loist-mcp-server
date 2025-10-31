#!/usr/bin/env python3
"""
Wrapper script to run the MCP server in stdio mode for Cursor integration.
This ensures proper Python path setup and module imports work correctly.
"""
import sys
import os
from pathlib import Path

# Get project root and src directory
project_root = Path(__file__).parent.resolve()
src_dir = project_root / "src"

# Change to project root directory
os.chdir(str(project_root))

# Add both src directory and project root to Python path
# src_dir first (for 'from config import config' etc.)
# project_root second (for 'from database import ...')
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Ensure stdio mode is set
if "SERVER_TRANSPORT" not in os.environ:
    os.environ["SERVER_TRANSPORT"] = "stdio"

# Import and run the server
# The server.py file already adds its parent to sys.path, so imports should work
if __name__ == "__main__":
    from src.server import mcp
    mcp.run()

