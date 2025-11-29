# A2A MVP Implementation Task List (Revised)

**Context:** This task list implements the minimal viable A2A integration for the Loist Music Library MCP Server. Based on A2A v0.3 (July 2025), this focuses on core discoverability and basic agent coordination without over-engineering.

**Database Requirements Summary:**
- ✅ **Existing**: `audio_tracks` table stores processed audio metadata
- ➕ **New**: `a2a_tasks` table for A2A task coordination (separate from audio processing)
- 📋 **Migration**: `003_add_a2a_tasks.sql` needs revision for A2A compliance
- 🔗 **Integration**: A2A tasks create/update `audio_tracks` records when processing completes

**Architecture Overview:**
- **MCP Server**: Existing FastMCP implementation with audio processing tools (stdio)
- **A2A Layer**: Agent Card discovery + JSON-RPC 2.0 task coordination API
- **Bridge Pattern**: Separate FastAPI app for A2A HTTP endpoints delegating to MCP tools
- 
**Success Criteria:**
- Agent Card accessible at `/.well-known/agent.json` (A2A v0.3 compliant)
- Task creation via JSON-RPC 2.0 `tasks/send` method
- Task status polling via JSON-RPC 2.0 `tasks/get` method
- Integration with existing MCP tools via shared business logic
- Basic error handling and validation

---

## Task 1: Verify MCP Server Foundation

**Goal**: Ensure existing MCP server is stable and reliable before adding A2A layer

**Context**: A2A builds on top of working MCP functionality. Foundation must be solid.

**Input Requirements**:
- Current `docker-compose.yml` configuration
- Existing `src/server.py` FastMCP server
- Core MCP tools: `process_audio_complete`, `get_audio_metadata`, `search_library`

**Implementation Steps**:
1. Start MCP server with `docker-compose up`
2. Verify `/health/live` and `/health/ready` endpoints return 200 OK
3. Check server logs for startup errors or warnings
4. Test each core MCP tool with sample data
5. Verify error handling for invalid inputs
6. Check response format consistency
7. Validate async processing completes successfully
8. Review exception serialization patterns
9. Document current error handling for A2A integration

**Output Requirements**:
- MCP server starts without critical errors
- All core tools return expected responses
- Error handling patterns documented
- Clear understanding of current validation logic

**Validation Criteria**:
- [ ] Server responds to health checks
- [ ] No critical errors in startup logs
- [ ] All MCP tools work with test data
- [ ] Error responses are consistent
- [ ] Exception serialization documented
- [ ] Input validation patterns understood

**Files to Examine**:
- `docker-compose.yml`
- `src/server.py`
- `src/tools/process_audio.py`
- `src/tools/query_tools.py`
- `src/exceptions/`
- `src/error_utils.py`

**Dependencies**: None

---

## Task 2: Create A2A Agent Card

**Goal**: Implement A2A v0.3 compliant Agent Card for agent discovery

**Context**: Agent Card is the discovery mechanism for A2A - defines what your agent can do and how other agents can interact with it.

**Input Requirements**:
- A2A v0.3 specification understanding
- Current MCP tool capabilities
- Agent identity information

**Implementation Steps**:
1. Create Agent Card JSON structure following A2A v0.3 spec
2. Define agent identity (ID, name, version, description)
3. Specify skills array with 3 core capabilities:
   - process_audio (with input schema)
   - search_library
   - get_embed_url
4. Add serviceEndpoint with JSON-RPC protocol
5. Include authentication configuration
6. Save as `/.well-known/agent.json`
7. Create FastAPI route to serve the Agent Card
8. Add CORS headers for cross-origin access
9. Implement response caching for performance
10. Update OpenAPI documentation

**Agent Card Structure** (A2A v0.3 compliant):
```json
{
  "agentId": "loist-music-processor",
  "name": "Loist Music Library Processor",
  "version": "1.0.0",
  "description": "Audio processing and metadata extraction service",

  "skills": [
    {
      "name": "process_audio",
      "description": "Process audio file and extract metadata",
      "inputSchema": {
        "type": "object",
        "properties": {
          "audio_url": {"type": "string"},
          "extract_waveform": {"type": "boolean"}
        },
        "required": ["audio_url"]
      }
    },
    {
      "name": "search_library",
      "description": "Search processed music library"
    },
    {
      "name": "get_embed_url",
      "description": "Generate embeddable player URLs"
    }
  ],

  "serviceEndpoint": {
    "url": "https://api.loist.music/a2a",
    "protocols": ["json-rpc"]
  },

  "authentication": {
    "type": "bearer",
    "scheme": "Bearer"
  }
}
```

**Output Requirements**:
- Valid Agent Card JSON file at `/.well-known/agent.json`
- HTTP endpoint serving the Agent Card
- CORS headers configured
- Response caching implemented

**Validation Criteria**:
- [ ] Agent Card JSON validates against A2A v0.3 schema
- [ ] `GET /.well-known/agent.json` returns 200 OK
- [ ] JSON contains required fields: agentId, skills, serviceEndpoint
- [ ] Skills array includes all 3 core capabilities
- [ ] CORS headers allow cross-origin requests
- [ ] OpenAPI documentation updated

**Files to Create/Modify**:
- `/.well-known/agent.json` (new)
- `src/a2a/app.py` (new FastAPI app)
- `docs/openapi.yaml` (update)

**Dependencies**:
- Task 1: MCP server foundation verified

## Task 3: Implement A2A Database Schema

**Goal**: Create A2A-compliant database schema for task coordination

**Context**: Need new database table for A2A task coordination separate from existing audio_tracks table.

**Input Requirements**:
- Existing database migration system
- Current audio_tracks table structure
- A2A v0.3 task state requirements

**Implementation Steps**:
1. Create `database/migrations/003_add_a2a_tasks.sql` migration
2. Define `a2a_tasks` table with A2A-compliant fields:
   - task_id (VARCHAR(36) PRIMARY KEY)
   - status (VARCHAR(20) with A2A state constraints)
   - messages (JSONB NOT NULL for A2A message format)
   - artifacts (JSONB for task results)
   - error (JSONB for error details)
   - created_at, updated_at timestamps
3. Add indexes on status and created_at for efficient querying
4. Add foreign key relationship to audio_tracks table
5. Update database operations for A2A task management
6. Run migration to create table

**Database Schema** (A2A v0.3 compliant):
```sql
-- MVP: Simple task tracking (no retry logic for Phase 1)
CREATE TABLE a2a_tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(20) NOT NULL CHECK (status IN
        ('submitted', 'working', 'completed', 'failed', 'cancelled')),
    messages JSONB NOT NULL,
    artifacts JSONB,
    error JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_a2a_status ON a2a_tasks(status);
CREATE INDEX idx_a2a_created ON a2a_tasks(created_at DESC);

-- Link to existing audio_tracks when processing completes
ALTER TABLE audio_tracks
ADD COLUMN a2a_task_id VARCHAR(36) REFERENCES a2a_tasks(task_id);
```

**Output Requirements**:
- Migration script created and applied
- a2a_tasks table exists with correct schema
- Database operations for A2A tasks implemented

**Validation Criteria**:
- [ ] Migration runs without errors
- [ ] a2a_tasks table created with correct columns
- [ ] Status constraint includes all A2A states
- [ ] Indexes created for performance
- [ ] Foreign key relationship to audio_tracks works
- [ ] Database operations can insert/retrieve A2A tasks

**Files to Create/Modify**:
- `database/migrations/003_add_a2a_tasks.sql` (new)
- `database/operations.py` (add A2A task operations)

**Dependencies**:
- Task 1: MCP server foundation verified

## Task 4: Implement JSON-RPC 2.0 Task API

**Goal**: Create JSON-RPC 2.0 endpoints for A2A task creation and status polling

**Context**: A2A v0.3 uses JSON-RPC 2.0 as the primary protocol, not REST endpoints.

**Input Requirements**:
- A2A database schema implemented
- FastAPI application structure
- JSON-RPC 2.0 specification understanding

**Implementation Steps**:
1. Create JSON-RPC request/response models using Pydantic
2. Implement `tasks/send` method for task creation:
   - Parse A2A message format from request
   - Extract audio_url from message parts
   - Generate unique task ID
   - Store task in a2a_tasks table with 'submitted' status
   - Trigger async processing
   - Return task ID in JSON-RPC response
3. Implement `tasks/get` method for status polling:
   - Accept task ID parameter
   - Retrieve task from database
   - Return current status, messages, and artifacts
   - Handle not-found cases with proper JSON-RPC errors
4. Add proper error handling and validation
5. Implement message parsing utilities

**JSON-RPC Request/Response Examples**:

**tasks/send request:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "method": "tasks/send",
  "params": {
    "task": {
      "id": "task-uuid-here",
      "messages": [
        {
          "role": "user",
          "parts": [
            {
              "type": "text",
              "text": "Process this audio: https://example.com/track.mp3"
            }
          ]
        }
      ]
    }
  }
}
```

**tasks/send response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "result": {
    "task": {
      "id": "task-uuid-here",
      "status": "submitted",
      "messages": [...]
    }
  }
}
```

**tasks/get request:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-456",
  "method": "tasks/get",
  "params": {"taskId": "task-uuid-here"}
}
```

**Output Requirements**:
- JSON-RPC 2.0 compliant endpoints
- Task creation and status polling working
- Message parsing from A2A format
- Proper error responses

**Validation Criteria**:
- [ ] `tasks/send` accepts valid JSON-RPC requests
- [ ] Tasks are created in database with correct status
- [ ] `tasks/get` returns current task state
- [ ] Message parsing extracts audio URLs correctly
- [ ] Invalid requests return proper JSON-RPC errors
- [ ] Endpoints handle concurrent requests

**Files to Create/Modify**:
- `src/a2a/models.py` (JSON-RPC models)
- `src/a2a/endpoints.py` (RPC handlers)
- `src/a2a/message_parser.py` (message parsing utilities)

**Dependencies**:
- Task 3: A2A database schema implemented

## Task 5: Create Shared Business Logic Layer

**Goal**: Extract core processing logic into shared functions used by both MCP and A2A

**Context**: Avoid code duplication by creating a shared business logic layer that both MCP tools (stdio) and A2A endpoints (HTTP) can call.

**Input Requirements**:
- Current MCP tool implementations
- A2A JSON-RPC endpoints structure
- Audio processing workflow understanding

**Implementation Steps**:
1. Create `src/business/` directory for shared logic
2. Extract `process_audio_internal()` function from MCP tools:
   - Move core audio processing logic to `src/business/audio_processor.py`
   - Function should accept audio_url and return standardized dict format
   - Include error handling and validation
3. Update existing MCP tools to call shared business logic
4. Ensure A2A endpoints can also call the same shared functions
5. Add proper async/await handling for both stdio and HTTP contexts

**Bridge Architecture**:
```
┌──────────────────────────────────────┐
│     Your Application                 │
├──────────────────────────────────────┤
│                                      │
│  ┌─────────────┐  ┌──────────────┐  │
│  │  MCP Server │  │ A2A HTTP     │  │
│  │  (stdio)    │  │ Endpoints    │  │
│  └──────┬──────┘  └──────┬───────┘  │
│         │                │          │
│         └────────┬───────┘          │
│                  ▼                  │
│        ┌─────────────────┐         │
│        │  Shared Business │         │
│        │  Logic / Tools   │         │
│        └─────────────────┘         │
└──────────────────────────────────────┘
```

**Output Requirements**:
- Shared business logic functions extracted
- MCP tools refactored to use shared logic
- A2A endpoints can call same shared functions
- No duplication between MCP and A2A implementations

**Validation Criteria**:
- [ ] Shared `process_audio_internal()` function exists
- [ ] MCP tools call shared business logic
- [ ] A2A endpoints can call shared business logic
- [ ] Both MCP and A2A produce identical results
- [ ] No code duplication between implementations

**Files to Create/Modify**:
- `src/business/audio_processor.py` (new)
- `src/tools/process_audio.py` (refactor to use shared logic)
- `src/a2a/endpoints.py` (call shared logic)

**Dependencies**:
- Task 4: JSON-RPC Task API implemented

## Task 6: Implement Message Parsing Utilities

**Goal**: Create utilities to extract parameters from A2A message format

**Context**: A2A sends parameters as messages with parts, not direct JSON. Need to parse "Process this audio: https://..." from message structures.

**Input Requirements**:
- A2A message format specification
- Current task creation endpoint
- Audio URL extraction requirements

**Implementation Steps**:
1. Create `src/a2a/message_parser.py` with parsing functions
2. Implement `extract_audio_url()` function that:
   - Accepts A2A message array
   - Searches for user role messages
   - Parses text parts for audio URLs
   - Handles various message formats gracefully
   - Returns extracted URL or raises ValueError
3. Add URL validation and sanitization
4. Support natural language patterns like:
   - "Process this audio: https://example.com/track.mp3"
   - "Download and analyze: https://audio.url/file.wav"
   - Direct URLs in text parts

**Example Implementation**:
```python
def extract_audio_url(messages: list[Message]) -> str:
    """Extract audio URL from A2A message parts"""
    for message in messages:
        if message.role == "user":
            for part in message.parts:
                if part.type == "text":
                    # Parse "Process this audio: https://..."
                    url = extract_url_from_text(part.text)
                    if url:
                        return url
    raise ValueError("No audio URL found in messages")
```

**Output Requirements**:
- Message parsing utilities implemented
- Audio URL extraction working
- Support for various message formats
- Proper error handling for invalid messages

**Validation Criteria**:
- [ ] Can extract URLs from various message formats
- [ ] Handles missing URLs gracefully
- [ ] Validates extracted URLs
- [ ] Works with JSON-RPC task creation

**Files to Create/Modify**:
- `src/a2a/message_parser.py` (new)

**Dependencies**:
- Task 4: JSON-RPC Task API implemented

## Task 7: Connect A2A Tasks to Audio Processing

**Goal**: Bridge A2A task requests to existing audio processing pipeline

**Context**: A2A tasks should trigger the same audio processing that MCP tools perform, storing results in both a2a_tasks and audio_tracks tables.

**Input Requirements**:
- A2A task creation working
- Shared business logic layer
- Database operations for both tables
- Audio processing workflow

**Implementation Steps**:
1. Update JSON-RPC `tasks/send` handler to:
   - Extract audio_url from messages using parser
   - Create a2a_tasks record with 'submitted' status
   - Call shared `process_audio_internal()` function
   - Update task status to 'working', then 'completed'/'failed'
   - Store results in both a2a_tasks.artifacts and audio_tracks table
   - Link records via a2a_task_id foreign key
2. Handle async processing and status updates
3. Implement proper error handling and rollback
4. Add task status polling in `tasks/get` method

**Integration Flow**:
```
A2A Request → Message Parsing → Task Creation → Shared Processing → Results Storage
```

**Output Requirements**:
- A2A tasks trigger audio processing
- Results stored in both tables
- Task status updates work correctly
- Error handling preserves data integrity

**Validation Criteria**:
- [ ] A2A `tasks/send` creates database records
- [ ] Audio processing completes successfully
- [ ] Results appear in both a2a_tasks and audio_tracks
- [ ] Task status polling returns correct state
- [ ] Failed processing updates task status appropriately

**Files to Create/Modify**:
- `src/a2a/endpoints.py` (add processing integration)
- `database/operations.py` (A2A task operations)

**Dependencies**:
- Task 5: Shared business logic layer created
- Task 6: Message parsing utilities implemented

## Task 8: Update Docker Compose for Dual Servers

**Goal**: Configure Docker Compose to run both MCP (stdio) and A2A (HTTP) servers

**Context**: Need separate services for MCP server (stdio transport) and A2A server (HTTP transport) since they serve different protocols.

**Input Requirements**:
- Current `docker-compose.yml`
- MCP server startup command
- A2A FastAPI app startup command

**Implementation Steps**:
1. Add separate `a2a-server` service to docker-compose.yml:
   - Build from same Dockerfile
   - Run `python src/a2a/app.py` command
   - Expose port 8080 for HTTP access
   - Include necessary environment variables
   - Set proper dependencies (database, etc.)
2. Keep existing `mcp-server` service for stdio transport
3. Update health checks for both services
4. Add network configuration if needed
5. Update documentation for running both servers

**Docker Compose Configuration**:
```yaml
services:
  # Existing MCP server (stdio)
  mcp-server:
    build: .
    command: python src/server.py
    environment:
      - SERVER_TRANSPORT=stdio
    volumes:
      - .:/app

  # NEW: A2A HTTP server
  a2a-server:
    build: .
    command: python src/a2a/app.py
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - GCS_BUCKET=${GCS_BUCKET}
    depends_on:
      - postgres
```

**Output Requirements**:
- Both MCP and A2A servers can run simultaneously
- Proper port separation (stdio vs HTTP)
- Environment variables configured correctly
- Health checks working for both services

**Validation Criteria**:
- [ ] `docker-compose up` starts both servers
- [ ] MCP server accessible via stdio transport
- [ ] A2A server accessible on port 8080
- [ ] Both servers can access database and GCS
- [ ] No port conflicts or resource issues

**Files to Create/Modify**:
- `docker-compose.yml` (add a2a-server service)

**Dependencies**:
- Task 2: A2A Agent Card implemented
- Task 4: JSON-RPC Task API implemented

## Task 9: Document Agent Discovery Strategy

**Goal**: Create documentation for how other agents can discover and use this A2A service

**Context**: A2A is useless if no one can find or use the service. Need clear documentation for discovery and integration.

**Input Requirements**:
- Agent Card endpoint details
- A2A integration patterns
- Authentication requirements
- API usage examples

**Implementation Steps**:
1. Update README.md with A2A discovery information:
   - Agent Card endpoint URL
   - How to fetch and parse Agent Card
   - Authentication requirements
   - Basic integration examples
2. Create `docs/a2a-integration-guide.md` with:
   - Step-by-step integration guide
   - JSON-RPC usage examples
   - Error handling patterns
   - Testing instructions
3. Consider community registry submission:
   - Document process for submitting to a2a.how
   - Alternative discovery methods
4. Add troubleshooting section for common integration issues

**Integration Guide Content**:
- **Discovery**: How to find the agent
- **Authentication**: Bearer token setup
- **Task Submission**: JSON-RPC examples
- **Status Polling**: How to check task progress
- **Error Handling**: Common issues and solutions
- **Testing**: How to verify integration works

**Output Requirements**:
- Clear discovery documentation
- Complete integration guide
- Working examples for all major operations
- Troubleshooting information

**Validation Criteria**:
- [ ] README includes A2A discovery information
- [ ] Integration guide exists and is comprehensive
- [ ] Examples work with the actual API
- [ ] Troubleshooting covers common issues

**Files to Create/Modify**:
- `README.md` (add A2A section)
- `docs/a2a-integration-guide.md` (new)

**Dependencies**:
- Task 2: A2A Agent Card implemented
- Task 4: JSON-RPC Task API implemented

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

## Task 10: Comprehensive A2A Testing and Validation

**Goal**: Test complete A2A integration end-to-end and validate compliance

**Context**: Ensure the A2A implementation works correctly and follows specifications before considering MVP complete.

**Input Requirements**:
- All previous tasks completed
- Test audio files and URLs
- JSON-RPC testing tools
- Agent Card validation tools

**Implementation Steps**:
1. Test Agent Card discovery and validation:
   - Verify `/.well-known/agent.json` endpoint
   - Validate against A2A v0.3 schema
   - Test CORS headers and accessibility
2. Test JSON-RPC compliance:
   - Send `tasks/send` requests with proper format
   - Validate JSON-RPC 2.0 response structure
   - Test `tasks/get` status polling
   - Verify error responses follow JSON-RPC spec
3. Test end-to-end audio processing:
   - Submit A2A tasks with audio URLs
   - Verify processing completes successfully
   - Check results in both a2a_tasks and audio_tracks tables
   - Validate task status transitions
4. Test error handling and edge cases:
   - Invalid message formats
   - Malformed URLs
   - Database connection issues
   - Processing failures
5. Test dual server deployment:
   - Run both MCP and A2A servers
   - Verify no conflicts or resource issues
   - Test concurrent access to both services

**MVP Completion Checklist**:
- [ ] Agent Card returns valid JSON at `/.well-known/agent.json`
- [ ] `curl` test: `curl http://localhost:8080/.well-known/agent.json`
- [ ] JSON-RPC test: Send `tasks/send` request, get valid response
- [ ] Task polling: Create task, poll until completion
- [ ] MCP still works: Existing tools callable via stdio
- [ ] Bridge working: Both A2A and MCP create audio_tracks records
- [ ] Docker deployment: Both servers start without conflicts
- [ ] Integration docs: README and guide updated
- [ ] A2A compliance: Passes basic protocol validation

**Stop Point Criteria** (When to Stop Before Phase 2):
- [ ] No agents have called your Agent Card endpoint (check logs)
- [ ] No external requests to A2A endpoints (only your own tests)
- [ ] No user feedback requesting SSE/webhooks
- [ ] **If any of these are true, MVP is complete - stop here**

**Output Requirements**:
- Complete A2A integration tested end-to-end
- All validation criteria passing
- Documentation updated and accurate
- Clear decision point for Phase 2 features

**Validation Criteria**:
- [ ] Agent Card discovery works from external clients
- [ ] JSON-RPC protocol fully compliant
- [ ] Audio processing integration successful
- [ ] Error handling robust and predictable
- [ ] Dual server deployment stable
- [ ] All MVP completion checklist items checked
- [ ] Decision made about Phase 2 based on usage data

**Files to Create/Modify**:
- Test scripts for A2A compliance
- Integration test suite
- Updated documentation

**Dependencies**:
- Task 7: A2A tasks connected to audio processing
- Task 8: Docker Compose updated for dual servers
- Task 9: Agent discovery documented

---

## Future Phase 2: Progressive Enhancement (Optional)

**Only implement these if MVP shows actual demand from other agents**

### Real-time Updates (SSE)
- Implement Server-Sent Events for task progress streams
- Add optional SSE parameter to task creation
- Handle client disconnections gracefully

### Webhook Support
- Allow agents to register webhook URLs for notifications
- Implement webhook delivery with retries
- Add webhook signature validation

### Enhanced Error Recovery
- Add retry counters to task records
- Implement exponential backoff for transient failures
- Track retry attempts in task status

---

## Testing and Validation

### A2A Compliance Testing
- [ ] **Validate Agent Card against A2A v0.3 schema**
  - **Context**: Ensure Agent Card matches official A2A specification
  - **Tasks**:
    - Verify `skills` array structure (not `capabilities` object)
    - Validate `serviceEndpoint` with `protocols: ["json-rpc"]`
    - Check `authentication` object structure
    - Test JSON schema validation against A2A spec
  - **Validation**: Agent Card passes A2A v0.3 compliance checks

- [ ] **Test JSON-RPC 2.0 protocol compliance**
  - **Context**: Verify A2A endpoints follow JSON-RPC 2.0 specification
  - **Tasks**:
    - Test `tasks/send` method with proper JSON-RPC format
    - Validate `jsonrpc: "2.0"` and `id` fields
    - Check `tasks/get` method responses
    - Verify error responses follow JSON-RPC format
  - **Validation**: All A2A endpoints return valid JSON-RPC 2.0 responses
  - **Estimated Time**: 45 minutes

### Integration Testing
- [ ] **Test Agent Card discovery**
  - **Context**: Verify agents can discover your capabilities
  - **Tasks**:
    - Test Agent Card endpoint accessibility
    - Validate JSON schema compliance
    - Test CORS headers
    - Verify OpenAPI spec linkage
  - **Validation**: Agent Card loads and parses correctly

- [ ] **Test end-to-end task workflows**
  - **Context**: Verify complete A2A task lifecycle
  - **Tasks**:
    - Create tasks via A2A API
    - Poll for status updates
    - Verify result delivery
    - Test error scenarios
  - **Validation**: Full task lifecycle works reliably

- [ ] **Test MCP tool integration**
  - **Context**: Ensure A2A tasks properly invoke MCP functionality
  - **Tasks**:
    - Verify parameter mapping
    - Test result formatting
    - Check error propagation
    - Validate async processing
  - **Validation**: A2A and MCP work together seamlessly

### Documentation Updates
- [ ] **Update API documentation**
  - **Context**: Document new A2A endpoints for users and agents
  - **Tasks**:
    - Add A2A endpoints to OpenAPI spec
    - Document Agent Card structure
    - Include example requests/responses
    - Update API version
  - **Validation**: Complete API documentation available

- [ ] **Create A2A integration guide**
  - **Context**: Help other developers integrate with your A2A API
  - **Tasks**:
    - Document discovery process
    - Provide integration examples
    - Explain authentication
    - Include troubleshooting tips
  - **Validation**: Clear integration guide exists

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

**Simplified Database Schema (MVP):**
```sql
-- MVP: Simple task tracking (no retry logic for Phase 1)
CREATE TABLE a2a_tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(20) NOT NULL CHECK (status IN
        ('submitted', 'working', 'completed', 'failed', 'cancelled')),
    messages JSONB NOT NULL,
    artifacts JSONB,
    error JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_a2a_status ON a2a_tasks(status);
CREATE INDEX idx_a2a_created ON a2a_tasks(created_at DESC);

-- Link to existing audio_tracks when processing completes
ALTER TABLE audio_tracks
ADD COLUMN a2a_task_id VARCHAR(36) REFERENCES a2a_tasks(task_id);
```

**Why This Schema:**
- Matches A2A message-driven architecture (`messages`/`artifacts`)
- Uses A2A state names exactly (`submitted`, `working`, etc.)
- No premature optimization (retry_count removed)
- Clear relationship to existing `audio_tracks` table

---

## Key Revisions Made

**Based on detailed feedback and A2A v0.3 research - restructured into 10 manageable LLM agent tasks (~200k tokens each):**

### ✅ Task-Based Structure
- **10 focused tasks** instead of phases with time estimates
- **Clear dependencies** between tasks
- **Specific validation criteria** for each task completion
- **Self-contained** implementation chunks for LLM agents

### ✅ Fixed Agent Card Structure (Task 2)
- Changed from `capabilities` object to `skills` array
- Added `serviceEndpoint` with `protocols: ["json-rpc"]`
- Added proper `authentication` object
- Updated to A2A v0.3 compliant format

### ✅ Added JSON-RPC 2.0 Implementation (Task 4)
- Changed from REST `POST /tasks` to `POST /a2a/v1/rpc`
- Added `tasks/send` and `tasks/get` methods with examples
- Proper JSON-RPC 2.0 request/response format
- Message parsing utilities (Task 6)

### ✅ Simplified Database Schema (Task 3)
- Removed over-engineered fields (`retry_count`, `type`, etc.)
- Added A2A-compliant fields (`messages`, `artifacts`)
- Used A2A state names (`submitted`, `working`, `completed`, `failed`, `cancelled`)

### ✅ Bridge Pattern Architecture (Task 5)
- Shared business logic layer to avoid code duplication
- MCP (stdio) and A2A (HTTP) both call same functions
- Separate FastAPI app for A2A endpoints

### ✅ Added Missing Components
- **Message Parsing** (Task 6): Extract URLs from A2A message format
- **Processing Integration** (Task 7): Connect A2A to audio processing
- **Dual Server Deployment** (Task 8): Docker Compose for both MCP and A2A
- **Agent Discovery Documentation** (Task 9): How others find and use the service

### ✅ Comprehensive Testing (Task 10)
- A2A compliance validation
- End-to-end integration testing
- MVP completion checklist
- Clear stop point criteria for Phase 2

### ✅ Removed Time/Day Estimates
- No more "2-3 days" or "1 hour" estimates
- Focus on deliverable completion, not time spent
- Each task measured by validation criteria

**Result**: 10 focused, manageable tasks that an LLM agent can complete in single coding sessions, each with clear inputs, outputs, and validation criteria. Production-ready A2A MVP that matches real implementations.
