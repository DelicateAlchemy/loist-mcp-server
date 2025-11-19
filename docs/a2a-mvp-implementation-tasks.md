# A2A MVP Implementation Task List

**Context:** This task list implements the minimal viable A2A integration for the Loist Music Library MCP Server. Based on A2A v0.3 (July 2025), this focuses on core discoverability and basic agent coordination without over-engineering.

**Database Requirements Summary:**
- ✅ **Existing**: `audio_tracks` table stores processed audio metadata
- ➕ **New**: `a2a_tasks` table for A2A task coordination (separate from audio processing)
- 📋 **Migration**: `003_add_a2a_tasks.sql` created and ready to apply
- 🔗 **Integration**: A2A tasks create/update `audio_tracks` records when processing completes

**Architecture Overview:**
- **MCP Server**: Existing FastMCP implementation with audio processing tools
- **A2A Layer**: Agent Card discovery + basic task coordination API
- **Integration**: HTTP-based task submission and status polling
- **Timeline**: 1-2 weeks total implementation

**Success Criteria:**
- Agent Card accessible at `/.well-known/agent.json`
- Task creation via POST `/tasks` endpoint
- Task status polling via GET `/tasks/{id}`
- Integration with existing MCP tools
- Basic error handling and validation

---

## Phase 0: Foundation Verification (2-3 days)

### Core MCP Server Health Check
- [ ] **Verify MCP server startup and basic connectivity**
  - **Context**: Ensure existing FastMCP server starts without errors and responds to health checks
  - **Why**: A2A builds on top of working MCP functionality - foundation must be solid
  - **Tasks**:
    - Start server with `docker-compose up`
    - Verify `/health` endpoint returns 200 OK
    - Check logs for any startup errors or warnings
  - **Files**: `docker-compose.yml`, `src/server.py`
  - **Validation**: Server responds to health checks, no critical errors in logs
  - **Dependencies**: None
  - **Estimated Time**: 30 minutes

- [ ] **Test core MCP tools functionality**
  - **Context**: Verify `process_audio_complete`, `get_audio_metadata`, `search_library` work reliably
  - **Why**: A2A exposes these tools to other agents - they must be trustworthy
  - **Tasks**:
    - Test each tool with sample data
    - Verify error handling for invalid inputs
    - Check response formats are consistent
    - Validate async processing completes successfully
  - **Files**: `src/tools/process_audio.py`, `src/tools/query_tools.py`
  - **Validation**: All tools return expected responses, handle errors gracefully
  - **Dependencies**: Server startup working
  - **Estimated Time**: 2 hours

- [ ] **Review existing error handling and validation**
  - **Context**: Assess current exception handling patterns and input validation
  - **Why**: A2A will expose these patterns externally - ensure they're robust
  - **Tasks**:
    - Check exception serialization in FastMCP
    - Review input validation in tool functions
    - Verify consistent error response formats
    - Document current error patterns for A2A mapping
  - **Files**: `src/exceptions/`, `src/error_utils.py`
  - **Validation**: Clear understanding of error handling patterns
  - **Dependencies**: Tool functionality verified
  - **Estimated Time**: 1 hour

---

## Phase 1: Minimal A2A Implementation (3-5 days)

### Agent Card Implementation
- [ ] **Create Agent Card JSON structure**
  - **Context**: Agent Card is the discovery mechanism for A2A - defines what your agent can do
  - **Why**: Other agents need to discover your capabilities automatically
  - **Tasks**:
    - Define agent identity (ID, name, version)
    - Specify 3 core skills: process_audio, search_library, get_embed_url
    - Include OpenAPI spec reference
    - Add basic authentication info
    - Use schema.org for music metadata compatibility
  - **Files**: New file `/.well-known/agent.json`
  - **Validation**: Valid JSON, accessible via HTTP GET
  - **Dependencies**: None
  - **Estimated Time**: 1 hour
  - **Example Structure**:
    ```json
    {
      "agentId": "loist-music-processor",
      "name": "Loist Music Library MCP Server",
      "version": "1.0.0-mvp",
      "capabilities": {
        "process_audio": {"description": "Process audio file and extract metadata"},
        "search_library": {"description": "Search processed music library"},
        "get_embed_url": {"description": "Generate embeddable player URLs"}
      },
      "endpoints": {
        "openapi": "https://api.loist.music/openapi.json",
        "tasks": "https://api.loist.music/tasks"
      }
    }
    ```

- [ ] **Implement Agent Card HTTP endpoint**
  - **Context**: Serve Agent Card at standard `/.well-known/agent.json` path
  - **Why**: A2A specification defines this as the discovery endpoint
  - **Tasks**:
    - Add route handler in FastAPI app
    - Set appropriate CORS headers
    - Cache the JSON response for performance
    - Add endpoint to OpenAPI documentation
  - **Files**: `src/server.py` (add route), `/.well-known/agent.json`
  - **Validation**: `GET /.well-known/agent.json` returns valid Agent Card
  - **Dependencies**: Agent Card JSON structure defined
  - **Estimated Time**: 30 minutes

- [ ] **Add Agent Card to OpenAPI specification**
  - **Context**: Document the Agent Card endpoint in your API spec
  - **Why**: Makes the A2A integration discoverable and self-documenting
  - **Tasks**:
    - Add endpoint documentation
    - Include example responses
    - Reference A2A specification
    - Update API version info
  - **Files**: `docs/openapi.yaml` (or wherever OpenAPI spec is stored)
  - **Validation**: OpenAPI spec includes Agent Card endpoint
  - **Dependencies**: Agent Card endpoint implemented
  - **Estimated Time**: 30 minutes

### Task API Implementation
- [ ] **Design and implement A2A tasks database schema**
  - **Context**: Need new database table for A2A task coordination (separate from existing audio_tracks table)
  - **Why**: A2A tasks coordinate multiple operations and need their own lifecycle management
  - **Database Changes Needed**:
    - Create `a2a_tasks` table with: id (UUID), type, status, input_data, result_data, created_at, updated_at, error_message, retry_count
    - Status enum: 'pending', 'processing', 'completed', 'failed'
    - JSONB fields for flexible input/result storage
    - Indexes on status, created_at for efficient querying
  - **Migration Script**: `database/migrations/003_add_a2a_tasks.sql` (already created)
  - **Files to Create**: Database migration, task model functions in `database/operations.py`
  - **Validation**: Migration applies successfully, table exists with correct schema
  - **Dependencies**: Database access working, migration system operational
  - **Estimated Time**: 2 hours
  - **Note**: This is separate from existing `audio_tracks` table which handles processed audio metadata
  - **Next Step**: After creating schema, run migration: `python database/migrate.py --action=up`

- [ ] **Implement task creation endpoint (POST /tasks)**
  - **Context**: Accept task requests and return immediate task IDs for async processing
  - **Why**: Core A2A task submission mechanism
  - **Tasks**:
    - Create POST route handler
    - Validate input parameters
    - Generate unique task ID
    - Store initial task record
    - Trigger async processing (delegate to existing MCP tools)
    - Return task ID in response
  - **Files**: `src/server.py` (add route), task storage functions
  - **Validation**: POST /tasks returns task ID, task appears in database
  - **Dependencies**: Task data model designed
  - **Estimated Time**: 2 hours

- [ ] **Implement task status endpoint (GET /tasks/{id})**
  - **Context**: Allow polling for task completion status and results
  - **Why**: A2A clients need to check task progress and get results
  - **Tasks**:
    - Create GET route with path parameter
    - Fetch task by ID from storage
    - Return status, progress, and results when complete
    - Handle not-found cases gracefully
    - Include proper error responses
  - **Files**: `src/server.py` (add route), task retrieval functions
  - **Validation**: GET /tasks/{id} returns correct status and data
  - **Dependencies**: Task creation endpoint working
  - **Estimated Time**: 1 hour

- [ ] **Integrate A2A tasks with existing MCP tools and database**
  - **Context**: Bridge A2A task requests to existing `process_audio_complete` MCP tool and audio_tracks table
  - **Why**: Leverage proven audio processing pipeline instead of reimplementing
  - **Tasks**:
    - Map A2A task types to MCP tool calls (e.g., "process_audio" → `process_audio_complete`)
    - Handle parameter translation between A2A JSON and MCP tool formats
    - Store task results in a2a_tasks table, link to audio_tracks records via track_id
    - Update task status as MCP processing progresses (pending → processing → completed/failed)
    - Capture and store MCP tool errors in a2a_tasks.error_message
    - Maintain error handling consistency between A2A and MCP layers
  - **Database Integration**: A2A task completion should result in audio_tracks record creation
  - **Files**: Task processing logic in `src/server.py`, database operations for task updates
  - **Validation**: A2A POST /tasks creates task record, invokes MCP tool, stores results in both tables
  - **Dependencies**: Task API, MCP tools, and database schema all working
  - **Estimated Time**: 3 hours

### Basic Error Handling and Validation
- [ ] **Implement consistent error responses**
  - **Context**: A2A clients need predictable error handling
  - **Why**: Enables reliable agent-to-agent communication
  - **Tasks**:
    - Define error response schema
    - Map internal errors to A2A error codes
    - Add error logging and monitoring
    - Include helpful error messages
  - **Files**: Error handling utilities, response formatting
  - **Validation**: All endpoints return consistent error formats
  - **Dependencies**: Task API endpoints implemented
  - **Estimated Time**: 1 hour

- [ ] **Add input validation and sanitization**
  - **Context**: Protect against malformed requests and potential attacks
  - **Why**: A2A exposes your API to unknown agents - security matters
  - **Tasks**:
    - Validate task parameters
    - Sanitize input data
    - Implement rate limiting basics
    - Add request size limits
  - **Files**: Validation middleware, input sanitization functions
  - **Validation**: Invalid requests are rejected with clear errors
  - **Dependencies**: Task endpoints implemented
  - **Estimated Time**: 1 hour

---

## Phase 2: Progressive Enhancement (3-7 days)

### Real-time Updates (Optional)
- [ ] **Implement Server-Sent Events (SSE) for task progress**
  - **Context**: Provide real-time updates for long-running tasks when clients request it
  - **Why**: Better UX for interactive agent workflows
  - **Tasks**:
    - Add SSE endpoint for task progress streams
    - Implement progress event publishing
    - Handle client disconnections gracefully
    - Add optional SSE parameter to task creation
  - **Files**: SSE route handler, progress streaming logic
  - **Validation**: Clients can subscribe to real-time task updates
  - **Dependencies**: Task API working
  - **Estimated Time**: 2 hours
  - **Note**: Only implement if users actually need real-time updates

### Webhook Support (Optional)
- [ ] **Add webhook callback system**
  - **Context**: Allow agents to register webhook URLs for task completion notifications
  - **Why**: Reduces polling overhead for agent orchestrators
  - **Tasks**:
    - Accept webhook URLs in task creation
    - Implement webhook delivery with retries
    - Add webhook signature validation
    - Handle failed webhook deliveries
  - **Files**: Webhook delivery service, signature validation
  - **Validation**: Task completion triggers webhook calls
  - **Dependencies**: Task completion handling working
  - **Estimated Time**: 2 hours
  - **Note**: Only implement if users need event-driven workflows

### Enhanced Error Recovery
- [ ] **Implement basic retry logic**
  - **Context**: Handle transient failures in audio processing
  - **Why**: Improves reliability for agent consumers
  - **Tasks**:
    - Add retry counters to task records
    - Implement exponential backoff
    - Track retry attempts in task status
    - Set reasonable retry limits
  - **Files**: Retry logic in task processing
  - **Validation**: Failed tasks retry automatically
  - **Dependencies**: Task processing working
  - **Estimated Time**: 1 hour

---

## Testing and Validation

### Integration Testing
- [ ] **Test Agent Card discovery**
  - **Context**: Verify agents can discover your capabilities
  - **Tasks**:
    - Test Agent Card endpoint accessibility
    - Validate JSON schema compliance
    - Test CORS headers
    - Verify OpenAPI spec linkage
  - **Validation**: Agent Card loads and parses correctly
  - **Estimated Time**: 30 minutes

- [ ] **Test end-to-end task workflows**
  - **Context**: Verify complete A2A task lifecycle
  - **Tasks**:
    - Create tasks via A2A API
    - Poll for status updates
    - Verify result delivery
    - Test error scenarios
  - **Validation**: Full task lifecycle works reliably
  - **Estimated Time**: 1 hour

- [ ] **Test MCP tool integration**
  - **Context**: Ensure A2A tasks properly invoke MCP functionality
  - **Tasks**:
    - Verify parameter mapping
    - Test result formatting
    - Check error propagation
    - Validate async processing
  - **Validation**: A2A and MCP work together seamlessly
  - **Estimated Time**: 1 hour

### Documentation Updates
- [ ] **Update API documentation**
  - **Context**: Document new A2A endpoints for users and agents
  - **Tasks**:
    - Add A2A endpoints to OpenAPI spec
    - Document Agent Card structure
    - Include example requests/responses
    - Update API version
  - **Validation**: Complete API documentation available
  - **Estimated Time**: 1 hour

- [ ] **Create A2A integration guide**
  - **Context**: Help other developers integrate with your A2A API
  - **Tasks**:
    - Document discovery process
    - Provide integration examples
    - Explain authentication
    - Include troubleshooting tips
  - **Validation**: Clear integration guide exists
  - **Estimated Time**: 1 hour

---

## Success Metrics and Next Steps

### MVP Success Criteria
- [ ] **Agent Discovery**: Agent Card accessible and valid
- [ ] **Task Creation**: POST /tasks endpoint working
- [ ] **Task Monitoring**: GET /tasks/{id} status polling working
- [ ] **MCP Integration**: A2A tasks successfully invoke MCP tools
- [ ] **Error Handling**: Consistent error responses across endpoints
- [ ] **Documentation**: OpenAPI spec and integration guide complete

### Post-MVP Considerations
- [ ] **Monitor A2A usage**: Track which features agents actually use
- [ ] **Gather feedback**: Ask integrating agents what they need
- [ ] **Iterate based on demand**: Only add SSE/webhooks if users request them
- [ ] **Consider A2A v0.4+**: Watch for protocol updates and adopt gradually

---

## Implementation Notes for Coding Agent

**Context Window Optimization:**
- Each task includes comprehensive context to avoid repeated lookups
- Tasks are atomic and independently verifiable
- Dependencies clearly stated to enable parallel work
- Validation criteria provided for each task completion

**Reasoning Model Guidance:**
- Tasks designed for step-by-step validation
- Include "why" explanations for architectural decisions
- Provide example structures and expected outcomes
- Flag optional components clearly

**File Organization:**
- New A2A files: `/.well-known/agent.json`, task route handlers
- Modified files: `src/server.py`, database schemas, OpenAPI spec
- Test files: Integration tests for A2A endpoints

**Rollback Strategy:**
- A2A features are additive - can be disabled if needed
- Agent Card is optional discovery mechanism
- Task API can fallback to direct MCP tool calls

**Security Considerations:**
- Input validation on all A2A endpoints
- Rate limiting for task creation
- Audit logging for agent interactions
- No sensitive data in Agent Card (public discovery info only)
