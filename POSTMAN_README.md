# Postman Setup for Local Development

This guide provides step-by-step instructions for setting up and using the Postman collection to test the Loist Music Library MCP server locally.

## 1. Prerequisites

- **Postman**: Ensure you have the [Postman desktop app](https://www.postman.com/downloads/) installed.
- **Running Local Server**: The MCP server must be running locally. You can start it using Docker Compose from the project root:
  ```bash
  docker-compose up
  ```
  This will start the server, typically available at `http://localhost:8080`.

## 2. Import the Collection

1.  Open Postman.
2.  Click on **File > Import...** (or `Cmd/Ctrl + O`).
3.  In the dialog that appears, select the `loist-music-library-local.postman_collection.json` file from the root of this project.
4.  Once imported, you will see a new collection named "Loist Music Library MCP - Local" in your Postman sidebar.

## 3. Configure the Environment

The collection uses environment variables to manage settings like the server's base URL and IDs for chaining requests.

### Create a New Environment

1.  In Postman, click the **"Environments"** tab on the left sidebar.
2.  Click the `+` button to create a new environment.
3.  Name the environment (e.g., "Loist MCP Local").

### Add Environment Variables

Add the following variables to your new environment:

| Variable | Initial Value | Description |
| :--- | :--- | :--- |
| `base_url` | `http://localhost:8080` | The base URL of your local MCP server. |
| `audio_id` | *(leave empty)* | This will be automatically populated when you run the "Process Audio Complete" request. It's used to chain requests. |
| `audio_source_url` | *(see below)* | The URL of an audio file you want to process. |

**To set `audio_source_url`**:
Find a direct URL to an audio file online (e.g., an MP3 file) and paste it as the value for this variable. This will be used by the "Process Audio Complete" request.

### Select the Active Environment

In the top-right corner of the Postman window, select the environment you just created from the dropdown menu. This makes the variables you defined available to the collection's requests.

## 4. How to Use the Collection

### Automatic MCP Session Initialization

The collection includes a **collection-level pre-request script** that automatically handles the MCP session initialization. This means you don't need to manually run the "Initialize MCP Session" request every time.

- When you run any MCP-related request, the script checks if a `sessionId` exists in the environment.
- If it doesn't, the script automatically sends an `initialize` request and saves the new `sessionId`.
- All subsequent requests in the collection will then use this `sessionId`.

### Recommended Workflow

1.  **Start with Health Checks**:
    - Open the "Health Checks" folder in the collection.
    - Run the **"MCP Health Check Tool"** request. This is a good way to verify that your local server is running and responsive.

2.  **Process an Audio File**:
    - Make sure you've set the `audio_source_url` variable in your environment.
    - Open the "MCP Tools" folder and run the **"Process Audio Complete"** request.
    - After a successful run, check the Postman console. The tests for this request will automatically extract the `audioId` from the response and save it to your environment variables.

3.  **Chain Requests**:
    - Now that `audio_id` is set, you can run other requests that depend on it, such as:
      - **"Get Audio Metadata"**
      - **"Update Metadata"**
      - **"Delete Audio"**
    - These requests will automatically use the `audio_id` from the environment.

## 5. Understanding the Folder Structure

- **Health Checks**: Requests for checking the status of the server and its dependencies.
- **MCP Tools**: Contains requests for each of the server's MCP tools (e.g., `process_audio_complete`, `search_library`).
- **MCP Resources**: For interacting with MCP resources (e.g., getting an audio stream URL).
- **HTTP API**: Direct tests for any custom HTTP endpoints (like `/embed/{audioId}`).
- **A2A (Agent-to-Agent)**: Requests related to the Agent-to-Agent protocol implementation.

By following these steps, you can effectively test all aspects of the Loist Music Library MCP server locally using the provided Postman collection.

## Troubleshooting

### MCP Session Initialization Issues

If you encounter errors like "Missing session ID" or "RESOURCE_NOT_FOUND" when running individual MCP tool requests, it's likely due to MCP session initialization issues.

**Problem**: The Postman collection uses asynchronous pre-request scripts for session initialization, which may not complete before the main request is sent.

**Solution**:

1. **For individual requests**: Always run the **"Initialize MCP Session"** request first (found in the "Health Checks" folder).
2. **For running the full collection**: The pre-request scripts should handle initialization automatically.
3. **If you see "RESOURCE_NOT_FOUND" errors**: This usually means the session wasn't properly initialized. Run "Initialize MCP Session" and try again.

**MCP Protocol Flow**:
```
1. Send "initialize" request → Get session ID from response header
2. Send "notifications/initialized" → Complete the handshake
3. Now you can call MCP tools like "tools/call"
```

The collection includes automatic session management, but due to Postman's synchronous nature, individual requests may require manual initialization.
