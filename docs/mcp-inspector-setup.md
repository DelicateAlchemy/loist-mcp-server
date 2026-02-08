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

## Proxy Configuration

If you are using the MCP Inspector through a proxy, you may need to configure the proxy to pass through the `Authorization` header. This is a requirement if the MCP server has authentication enabled.

Please refer to your proxy's documentation for instructions on how to configure header passthrough.
