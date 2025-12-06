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

The collection includes a **collection-level pre-request script** that automatically handles MCP session initialization **synchronously**. This ensures session initialization completes before the main request is sent, eliminating the intermittent failures caused by async timing issues.

- When you run any MCP-related request, the script checks if a `sessionId` exists in the environment.
- If it doesn't exist, the script **synchronously** initializes a new MCP session using a busy-wait pattern.
- The session initialization blocks until complete (with a 10-second timeout), ensuring the session is ready before the main request executes.
- All subsequent requests in the collection will then use the validated `sessionId`.

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

The collection now uses **synchronous session initialization**, which should eliminate most session-related issues. However, if you still encounter problems:

**Problem**: Session initialization fails or times out.

**Symptoms**:
- Error: "Session initialization timed out after 10000ms"
- Error: "Session initialization failed: [error details]"
- Error: "MCP session not initialized"

**Solutions**:

1. **Check server connectivity**: Ensure the MCP server is running and accessible:
   ```bash
   curl http://localhost:8080/health/ready
   ```

2. **Clear stale session data**: If you get timeout errors, clear the environment variables:
   - In Postman, go to your environment and clear `sessionId` and `sessionInitializedAt`
   - Or run the "Initialize MCP Session" request manually

3. **Manual initialization**: Run the "Initialize MCP Session" request first (found in "Health Checks" folder).

4. **Check for server errors**: Look at the Postman console for detailed error messages.

**New Synchronous Flow**:
```
1. Check if sessionId exists in environment
2. If not, send "initialize" request and BUSY-WAIT until complete
3. Send "notifications/initialized" synchronously
4. Validate session is ready, then proceed with main request
```

**Benefits of synchronous initialization**:
- ✅ No more race conditions between session init and main request
- ✅ Clear error messages guide troubleshooting
- ✅ Automatic retry logic for failed sessions
- ✅ Session age validation warns about stale sessions

### Newman CLI Alternative for Automated Testing

For reliable automated testing without GUI dependencies, use Newman (Postman's CLI companion):

**Installation**:
```bash
npm install -g newman
```

**Run the collection**:
```bash
# Basic run
newman run loist-music-library-local.postman_collection.json \
  --environment postman-env-local.json

# With detailed reporting
newman run loist-music-library-local.postman_collection.json \
  --environment postman-env-local.json \
  --reporters cli,json \
  --reporter-json-export results.json

# Run specific folder
newman run loist-music-library-local.postman_collection.json \
  --environment postman-env-local.json \
  --folder "MCP Tools"
```

**Advantages over GUI**:
- ✅ No async timing issues (Newman runs scripts synchronously)
- ✅ Consistent test execution
- ✅ CI/CD integration
- ✅ Automated reporting
- ✅ No manual intervention required

**Note**: Newman handles the collection's pre-request scripts correctly, so session initialization works reliably in automated environments.
