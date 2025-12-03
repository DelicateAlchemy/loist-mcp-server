# MCP Inspector Setup Guide

This document provides instructions for setting up the MCP Inspector to connect to the loist-music-library MCP server.

## Prerequisites

- MCP Inspector application is installed.
- The loist-mcp-server is running locally.

## Configuration

1.  Create a configuration file at `~/.mcp-inspector/config.json`.
2.  Add the following content to the file:

    ```json
    {
      "mcpServers": {
        "loist-music-library": {
          "type": "streamable-http",
          "url": "http://localhost:8080/mcp"
        }
      }
    }
    ```

## Usage

1.  Start the MCP Inspector application.
2.  The `loist-music-library` server should appear in the list of available servers.
3.  Connect to the server to start inspecting MCP tools and resources.
