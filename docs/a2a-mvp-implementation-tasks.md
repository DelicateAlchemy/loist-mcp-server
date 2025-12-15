# A2A MVP Implementation Planning Document

## ⚠️ **STATUS: PLANNING DOCUMENT - NOT IMPLEMENTED**

**Important:** This document contains **design and planning work only**. No A2A implementation code has been built. The ✅ checkmarks below represent **completed design decisions**, not completed code implementation.

**Context:** This planning document outlines the minimal viable A2A integration design for the Loist Music Library MCP Server. Based on A2A v0.3 (July 2025), this focuses on core discoverability and basic agent coordination without over-engineering.

**A2A-Ready Design Note:** Current MCP tool design is already A2A-compatible with typed schemas, idempotent reads, and explicit side effects. A2A builds on existing MCP capabilities rather than requiring major redesigns.

**See also**: [`mcp-audit-tasks.md`](../mcp-audit-tasks.md) for detailed research findings on tool granularity, A2A compatibility, and operational tools best practices.

---

## 🔬 SDK Research Findings (LOI-23)

**Research Date:** December 11, 2025  
**Source:** DeepWiki Codemap analysis of `a2aproject/a2a-python` repository

### Key Discovery: SDK Provides Built-in SQL Storage

The `a2a-sdk[postgresql]` package includes **complete task persistence** via `DatabaseTaskStore`. This significantly simplifies our implementation.

#### SDK Components Available

| Component | SDK Provides | Our Original Plan |
|-----------|--------------|-------------------|
| **Task Storage** | `DatabaseTaskStore` class | Custom `a2a_tasks` table |
| **JSON-RPC Server** | `A2AFastAPIApplication` | Manual JSON-RPC implementation |
| **Task States** | 7 states (enum) | 5 custom states |
| **Table Schema** | Auto-created via SQLAlchemy | Manual SQL migration |
| **Pydantic Mapping** | Automatic ORM ↔ Pydantic | Manual mapping |

#### SDK Task States (7 total)
- `submitted` - Initial state
- `working` - In progress  
- `input-required` - Waiting for user input
- `completed` - Successfully finished (terminal)
- `failed` - Error occurred (terminal)
- `canceled` - User canceled (terminal)
- `rejected` - Task rejected (terminal)

**Note**: Terminal states (`completed`, `canceled`, `failed`, `rejected`) cannot be modified. The SDK's `DefaultRequestHandler` automatically validates this via `TERMINAL_TASK_STATES` check before operations.

#### SDK Database Schema (auto-created)
```python
# From a2a.server.models.TaskMixin
id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
context_id: Mapped[str] = mapped_column(String(36), nullable=False)
kind: Mapped[str] = mapped_column(String(16), nullable=False, default='task')
status: Mapped[TaskStatus] = mapped_column(PydanticType(TaskStatus))
artifacts: Mapped[list[Artifact] | None] = mapped_column(PydanticListType(Artifact), nullable=True)
history: Mapped[list[Message] | None] = mapped_column(PydanticListType(Message), nullable=True)
task_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, name='metadata')
```

### Integration Strategy: Use SDK Defaults

For MVP, we use the SDK's default task model. The SDK's `DatabaseTaskStore` doesn't easily support custom models, so we'll use the metadata JSON field for any relationships if needed:

```python
# Use SDK's DatabaseTaskStore with default model
from a2a.server.tasks import DatabaseTaskStore
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(database_url.replace("postgresql://", "postgresql+asyncpg://"))

store = DatabaseTaskStore(
    engine=engine,
    create_table=True,  # SDK creates table automatically
    table_name='a2a_tasks'
)

# If audio track linking needed, store in metadata
task.metadata = {"audio_track_id": "uuid-here"}
await store.save(task)
```

### SDK JSON-RPC Server

The SDK provides a **complete JSON-RPC server**, not just storage:

```python
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler

# Complete server with one line
app = A2AFastAPIApplication(agent_card, handler)
fastapi_app = app.build()
```

**Built-in features:**
- Agent Card serving at `/.well-known/agent-card.json`
- Full JSON-RPC 2.0 protocol handling
- Request validation and routing
- Error handling with proper codes
- SSE streaming support
- Authentication via extended card

### Impact on Implementation Tasks

| Task | Original Approach | With SDK | Effort Change |
|------|-------------------|----------|---------------|
| **Task 3** | Manual SQL migration | SDK auto-creates (no migration) | **-80%** |
| **Task 4** | Manual JSON-RPC handlers | Use `A2AFastAPIApplication` | **-80%** |
| **Task 5** | Extract shared logic | Implement `RequestHandler` interface | **Similar** |
| **Task 6** | Message parsing utils | SDK provides `Message` types | **-50%** |

### Research Citations

**DatabaseTaskStore initialization:**
- `src/a2a/server/tasks/database_task_store.py:43` - Accepts SQLAlchemy engine, configurable table name
- `src/a2a/server/tasks/database_task_store.py:67` - Dynamic model selection

**TaskMixin schema:**
- `src/a2a/server/models.py:122-145` - All task columns with Pydantic types

**Custom model factory:**
- `src/a2a/server/models.py:156-184` - `create_task_model()` for custom base classes

**Complete server:**
- `src/a2a/server/apps/jsonrpc/fastapi_app.py:61-67` - `A2AFastAPIApplication`

---

**Database Requirements (Updated):**
- ✅ **Existing**: `audio_tracks` table stores processed audio metadata
- ✅ **SDK Provides**: `DatabaseTaskStore` handles task persistence automatically
- 📝 **No Migration Needed**: SDK auto-creates `a2a_tasks` table on startup
- 🔗 **Integration**: Use task `metadata` JSON field for relationships if needed

**Architecture Overview (Updated):**
- **MCP Server**: Existing FastMCP implementation with audio processing tools (stdio)
- **A2A Layer**: Use SDK's `A2AFastAPIApplication` for complete JSON-RPC server
- **Storage**: SDK's `DatabaseTaskStore` with default task model
- **Bridge Pattern**: Still needed for shared business logic between MCP and A2A

**Success Criteria (for future implementation):**
- Agent Card accessible at `/.well-known/agent-card.json` (SDK serves this automatically)
- Task creation via SDK's JSON-RPC `tasks/send` method
- Task status polling via SDK's JSON-RPC `tasks/get` method
- Integration with existing MCP tools via `RequestHandler` implementation
- Basic error handling provided by SDK

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
3. Specify skills array with 4-6 core business capabilities (not all 12 MCP tools):
   - ✅ `process_audio_complete` - Main ingestion capability
   - ✅ `search_library` - Primary query capability
   - ✅ `get_audio_metadata` - Lightweight metadata retrieval
   - ✅ `update_metadata` - Edit capability
   - ✅ `delete_audio` - Removal capability
   - ✅ `get_embed_url` - Embed generation (if agents need it)
4. Exclude operational/monitoring tools (HTTP-only, not MCP tools):
   - ❌ `health_check` - Use HTTP endpoint instead
   - ❌ `get_waveform_metrics_tool` - Use HTTP endpoint instead
   - ❌ `get_circuit_breaker_status` - Use HTTP endpoint instead
   - ❌ `check_waveform_availability` - Deprecated, to be removed
   - ❌ `list_embed_templates` - Utility, not core workflow
5. Add serviceEndpoint with JSON-RPC protocol
6. Include authentication configuration (bearer token)
7. Agent Card served automatically by SDK at `/.well-known/agent-card.json`
8. Create FastAPI route to serve the Agent Card
9. Add CORS headers for cross-origin access
10. Implement response caching for performance
11. Update OpenAPI documentation

**Agent Card Structure** (A2A v0.3 compliant):
```json
{
  "name": "Loist Music Library Processor",
  "description": "Audio processing and metadata extraction service",
  "url": "https://api.loist.music/a2a",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "defaultInputModes": ["application/json", "text/plain"],
  "defaultOutputModes": ["application/json"],
  "security": [{"BearerAuth": []}],
  "securitySchemes": {
    "BearerAuth": {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "JWT"
    }
  },
  "skills": [
    {
      "id": "process_audio_complete",
      "name": "Process audio (full)",
      "description": "Process audio file from URL and extract complete metadata including waveform, artwork, and tags",
      "tags": ["audio", "ingestion", "metadata", "waveform"]
    },
    {
      "id": "search_library",
      "name": "Search library",
      "description": "Search processed music library with text queries and metadata filters",
      "tags": ["search", "query", "metadata"]
    },
    {
      "id": "get_audio_metadata",
      "name": "Get metadata",
      "description": "Retrieve complete metadata for a processed audio track by ID",
      "tags": ["metadata", "retrieval"]
    },
    {
      "id": "update_metadata",
      "name": "Update metadata",
      "description": "Update metadata fields for an existing audio track",
      "tags": ["metadata", "update", "editing"]
    },
    {
      "id": "delete_audio",
      "name": "Delete audio",
      "description": "Remove an audio track from the library and delete associated files",
      "tags": ["deletion", "cleanup"]
    },
    {
      "id": "get_embed_url",
      "name": "Get embed URL",
      "description": "Generate embeddable player URLs for audio tracks with waveform visualization",
      "tags": ["embed", "player", "waveform"]
    }
  ]
}
```

**Output Requirements**:
- Valid Agent Card JSON file at `/.well-known/agent-card.json`
- HTTP endpoint serving the Agent Card (SDK automatic)
- CORS headers configured
- Response caching implemented

**Validation Criteria**:
- [ ] Agent Card JSON validates against A2A v0.3 schema
- [ ] `GET /.well-known/agent-card.json` returns 200 OK
- [ ] JSON contains required fields: name, url, version, capabilities, defaultInputModes, defaultOutputModes, skills
- [ ] Skills array includes all 6 core capabilities with proper id/name/description/tags
- [ ] Security configuration includes BearerAuth scheme
- [ ] CORS headers allow cross-origin requests
- [ ] OpenAPI documentation updated

**Files to Create/Modify**:
- `src/a2a/agent_card.py` (SDK-based AgentCard configuration)
- `src/a2a/app.py` (SDK A2AFastAPIApplication)
- `docs/openapi.yaml` (update)

**Dependencies**:
- Task 1: MCP server foundation verified

## Task 3: Configure SDK Database Storage

**Goal**: Configure SDK's `DatabaseTaskStore` for A2A task persistence

**Context**: SDK provides built-in task persistence with automatic schema creation. For MVP, we use the SDK's default task model. If audio track linking is needed, we'll store the relationship in the task's `metadata` JSON field rather than extending the schema.

**🔬 Research Update (LOI-23)**: SDK handles schema creation automatically via SQLAlchemy. No manual migration needed. The SDK's `DatabaseTaskStore` doesn't support custom models easily, so we use the default model and store relationships in metadata if needed.

**Input Requirements**:
- SDK package: `a2a-sdk[postgresql]`
- Existing `audio_tracks` table structure
- SQLAlchemy async engine configuration

**Implementation Steps**:
1. Verify SDK with PostgreSQL support: `a2a-sdk[postgresql]` already in requirements.txt
2. Create `DatabaseTaskStore` initialization function:
   ```python
   # src/a2a/storage.py
   from a2a.server.tasks import DatabaseTaskStore
   from sqlalchemy.ext.asyncio import create_async_engine
   
   async def create_task_store(database_url: str) -> DatabaseTaskStore:
       # Convert to async PostgreSQL URL
       async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
       
       engine = create_async_engine(
           async_url,
           pool_pre_ping=True
       )
       
       return DatabaseTaskStore(
           engine=engine,
           create_table=True,  # SDK creates table automatically
           table_name='a2a_tasks'
       )
   ```
3. Add convenience function for environment-based initialization:
   ```python
   async def get_task_store(database_url: Optional[str] = None) -> DatabaseTaskStore:
       if not database_url:
           database_url = os.getenv("DATABASE_URL")
       if not database_url:
           raise ValueError("Database URL required")
       return await create_task_store(database_url)
   ```
4. If audio track linking needed later, use metadata field:
   ```python
   # Store relationship in task metadata
   task.metadata = {"audio_track_id": "uuid-here"}
   await task_store.save(task)
   ```

**SDK-Provided Schema** (auto-created):
```
a2a_tasks table:
├── id (VARCHAR(36), PK, indexed)
├── context_id (VARCHAR(36), NOT NULL)
├── kind (VARCHAR(16), default='task')
├── status (JSON - TaskStatus Pydantic model)
├── artifacts (JSON - list[Artifact])
├── history (JSON - list[Message])
└── metadata (JSON)
```

**Output Requirements**:
- SDK `DatabaseTaskStore` initialized with default task model
- SDK auto-creates `a2a_tasks` table on startup
- Can save and retrieve tasks via SDK store
- Database URL validation and error handling

**Validation Criteria**:
- [ ] `a2a-sdk[postgresql]` installed in requirements.txt (already present)
- [ ] `DatabaseTaskStore` initializes without errors
- [ ] SDK auto-creates `a2a_tasks` table on startup
- [ ] Can save and retrieve tasks via SDK
- [ ] Database URL validation works correctly
- [ ] Error handling provides clear messages

**Files to Create/Modify**:
- `src/a2a/storage.py` (new - store initialization)

**Dependencies**:
- Task 1: MCP server foundation verified

## Task 4: Configure SDK JSON-RPC Server

**Goal**: Set up SDK's `A2AFastAPIApplication` with custom request handler

**Context**: SDK provides a complete JSON-RPC 2.0 server. We implement the `RequestHandler` interface to add our audio processing logic.

**🔬 Research Update (LOI-23)**: SDK provides `A2AFastAPIApplication` with built-in JSON-RPC protocol handling, request validation, Agent Card serving, and error handling. We only need to implement business logic.

**Input Requirements**:
- SDK package: `a2a-sdk[postgresql]`
- Agent Card configuration (from Task 2)
- `DatabaseTaskStore` configured (from Task 3)

**Implementation Steps**:
1. Create Agent Card configuration:
   ```python
   # src/a2a/agent_card.py
   from a2a.types import AgentCard, AgentSkill, AgentCapabilities

   AGENT_CARD = AgentCard(
       name="Loist Music Library Processor",
       description="Audio processing and metadata extraction service",
       url="https://api.loist.music/a2a",
       version="1.0.0",
       protocolVersion="0.3.0",
       capabilities=AgentCapabilities(
           streaming=False,
           pushNotifications=False,
           stateTransitionHistory=True
       ),
       defaultInputModes=["application/json", "text/plain"],
       defaultOutputModes=["application/json"],
       security=[{"BearerAuth": []}],
       securitySchemes={
           "BearerAuth": {
               "type": "http",
               "scheme": "bearer",
               "bearerFormat": "JWT"
           }
       },
       skills=[
           AgentSkill(
               id="process_audio_complete",
               name="Process audio (full)",
               description="Process audio file from URL and extract complete metadata including waveform, artwork, and tags",
               tags=["audio", "ingestion", "metadata", "waveform"]
           ),
           AgentSkill(
               id="search_library",
               name="Search library",
               description="Search processed music library with text queries and metadata filters",
               tags=["search", "query", "metadata"]
           ),
           AgentSkill(
               id="get_audio_metadata",
               name="Get metadata",
               description="Retrieve complete metadata for a processed audio track by ID",
               tags=["metadata", "retrieval"]
           ),
           AgentSkill(
               id="update_metadata",
               name="Update metadata",
               description="Update metadata fields for an existing audio track",
               tags=["metadata", "update", "editing"]
           ),
           AgentSkill(
               id="delete_audio",
               name="Delete audio",
               description="Remove an audio track from the library and delete associated files",
               tags=["deletion", "cleanup"]
           ),
           AgentSkill(
               id="get_embed_url",
               name="Get embed URL",
               description="Generate embeddable player URLs for audio tracks with waveform visualization",
               tags=["embed", "player", "waveform"]
           ),
       ]
   )
   ```

2. Implement `RequestHandler` interface:
   ```python
   # src/a2a/handler.py
   from a2a.server.request_handlers import RequestHandler
   from a2a.types import (
       SendMessageRequest, SendMessageResponse,
       GetTaskRequest, GetTaskResponse,
       Message, TaskStatus, TaskState
   )
   
   # Terminal states - SDK validates these automatically, but useful for our logic
   TERMINAL_TASK_STATES = {
       TaskState.completed, 
       TaskState.canceled, 
       TaskState.failed, 
       TaskState.rejected
   }
   
   class LoistRequestHandler(RequestHandler):
       def __init__(self, task_store, audio_processor):
           self.task_store = task_store
           self.audio_processor = audio_processor
       
       async def on_send_message(
           self, request: SendMessageRequest, context
       ) -> SendMessageResponse:
           # Extract audio URL from message
           audio_url = self._extract_audio_url(request.params.message)
           
           # Create task with 'working' status
           task = await self._create_task(request, TaskState.working)
           
           # Process audio (calls shared business logic)
           try:
               result = await self.audio_processor.process(audio_url)
               task.status = TaskStatus(state=TaskState.completed)
               task.artifacts = [result.to_artifact()]
           except Exception as e:
               task.status = TaskStatus(state=TaskState.failed, message=str(e))
           
           await self.task_store.save(task)
           return SendMessageResponse(result=task)
       
       async def on_get_task(
           self, request: GetTaskRequest, context
       ) -> GetTaskResponse:
           task = await self.task_store.get(request.params.task_id)
           return GetTaskResponse(result=task)
   ```

3. Build FastAPI application using SDK:
   ```python
   # src/a2a/app.py
   from a2a.server.apps import A2AFastAPIApplication
   from .agent_card import AGENT_CARD
   from .handler import LoistRequestHandler
   from .storage import create_task_store
   
   async def create_a2a_app():
       task_store = await create_task_store(DATABASE_URL)
       handler = LoistRequestHandler(task_store, audio_processor)
       
       # SDK handles everything: JSON-RPC, validation, Agent Card serving
       a2a_app = A2AFastAPIApplication(
           agent_card=AGENT_CARD,
           http_handler=handler
       )
       return a2a_app.build()
   ```

**SDK-Provided Endpoints** (automatic):
- `GET /.well-known/agent-card.json` - Agent Card discovery
- `POST /` - JSON-RPC endpoint (tasks/send, tasks/get, etc.)
- Full JSON-RPC 2.0 error handling
- Request validation via Pydantic
- Optional SSE streaming support

**JSON-RPC Examples** (SDK handles protocol, we handle logic):

**tasks/send** - SDK routes to `on_send_message()`:
```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "method": "tasks/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Process: https://example.com/track.mp3"}]
    }
  }
}
```

**tasks/get** - SDK routes to `on_get_task()`:
```json
{
  "jsonrpc": "2.0",
  "id": "req-456", 
  "method": "tasks/get",
  "params": {"taskId": "task-uuid-here"}
}
```

**Output Requirements**:
- `A2AFastAPIApplication` configured and running
- `RequestHandler` implementation with audio processing logic
- Agent Card served at standard endpoint
- JSON-RPC methods routed to handler

**Validation Criteria**:
- [ ] `A2AFastAPIApplication` builds without errors
- [ ] `GET /.well-known/agent-card.json` returns Agent Card
- [ ] `tasks/send` routes to `on_send_message()`
- [ ] `tasks/get` routes to `on_get_task()`
- [ ] SDK validates JSON-RPC format automatically
- [ ] Errors return proper JSON-RPC error responses

**Files to Create/Modify**:
- `src/a2a/agent_card.py` (new - Agent Card config)
- `src/a2a/handler.py` (new - RequestHandler implementation)
- `src/a2a/app.py` (new - FastAPI app using SDK)

**Dependencies**:
- Task 2: Agent Card design finalized
- Task 3: DatabaseTaskStore configured

## Task 5: Create Shared Business Logic Layer

**Goal**: Extract core processing logic into shared functions used by both MCP and A2A

**Context**: Avoid code duplication by creating a shared business logic layer that both MCP tools (stdio transport) and A2A endpoints (HTTP transport) can call. Separate apps are required due to fundamental transport differences: MCP uses stdio for local tool execution, A2A uses HTTP for agent coordination.

**Bridge Pattern Rationale**:
- **MCP Transport**: stdio (standard input/output streams) - designed for IDEs and LLMs to call tools locally
- **A2A Transport**: HTTP with JSON-RPC - designed for agent-to-agent discovery and task coordination
- **Why Separate Apps**: Transport protocols are fundamentally incompatible; MCP stdio doesn't support HTTP routing, A2A HTTP doesn't support stdio streams
- **Shared Logic**: Both transports call the same business functions to ensure identical behavior

**Input Requirements**:
- Current MCP tool implementations
- A2A JSON-RPC endpoints structure
- Audio processing workflow understanding

### Design: Shared Processing API (what gets extracted)

**Current reality**: The audio pipeline lives inside `src/tools/process_audio.py:process_audio_complete(...)` and is called by the MCP tool wrapper in `src/server.py`. There is no `process_audio_internal()` today; we need to define the shared surface area first.

**Principle**: The shared layer must be **transport-agnostic** (no FastMCP, no A2A SDK types) and provide a **stable contract** for both MCP and A2A adapters.

#### 1) Boundaries (what stays vs what moves)

**Move into shared business layer (`src/business/`)**:
- Core pipeline orchestration:
  - download (including SSRF validation)
  - metadata extraction / fallback / enrichment
  - storage upload (audio + artwork)
  - DB persistence + status transitions (processing/completed/failed)
  - cleanup of temp files
- Domain-level errors that are independent of transport

**Keep in transport adapters**:
- **MCP** adapter concerns:
  - converting MCP tool args (`source`, `options`) into a shared request
  - mapping shared errors into MCP `ProcessAudioException` (or MCP error dict)
  - MCP-specific response shape / field names (e.g., `audioId` vs `audio_id` if applicable)
- **A2A** adapter concerns:
  - parsing `Message`/`Part` into a URL/options (Task 6)
  - task status transitions in the A2A task store (`submitted → working → completed/failed`)
  - mapping shared errors into A2A task failure artifacts / error payload

#### 2) Shared function contract (canonical API)

Create a single “unit of work” function that both adapters call:

- **Name**: `process_audio_shared(...)` (replace the vague `process_audio_internal()` wording)
- **Location**: `src/business/audio_processor.py`
- **Signature (design-level)**:
  - Input: a transport-neutral request object (URL, headers, filename hint, options)
  - Output: a transport-neutral result object (audio_id, metadata, resources, timing)
  - Errors: raise a shared exception type with a structured error payload

**Key design choice**: The shared function should accept optional dependency overrides (DI) so we can unit test it without forcing end-to-end GCS/DB/network.

#### 3) Data model (request/result/error)

**Request fields** (minimum viable):
- `url: str` (HTTP/HTTPS only)
- `headers: dict[str, str] | None` (optional)
- `filename: str | None` (optional filename hint/override)
- `options: dict[str, Any]` (or a typed options model mirroring MCP options)

**Result fields** (minimum viable):
- `audio_id: str`
- `metadata: dict[str, Any]` (or reuse existing typed metadata schemas if stable)
- `resources: dict[str, Any]` (signed URLs / GCS URIs / artwork references)
- `timing: dict[str, float]` (optional, but helps debug both transports)

**Error fields** (minimum viable):
- `code: str` (stable set; e.g., `VALIDATION_ERROR`, `FETCH_FAILED`, `TIMEOUT`, `SIZE_EXCEEDED`, `STORAGE_ERROR`, `DATABASE_ERROR`, `METADATA_ERROR`)
- `message: str`
- `details: dict[str, Any] | None`
- `retryable: bool` (helps A2A decide whether to suggest retry)

#### 3.1) Canonical naming + error codes (lock these down before refactor)

**Canonical = shared = MCP internal**:
- Use **snake_case** field names to match the existing Pydantic models in `src/tools/schemas.py`:
  - `audio_id`, `processing_time`, `url_embed_link`, `audio_url`, `thumbnail_url`, `waveform_url`
- Treat this as the **shared contract**. Adapters may remap if we ever want an external camelCase API later.
- **Mirror note (anti-drift)**: The shared success/error payload should mirror the structure produced by `ProcessAudioOutput.model_dump()` and `ProcessAudioError.model_dump()` (snake_case) so MCP and A2A can reuse the same data shape end-to-end.

**Canonical error code set**: reuse MCP’s existing `ErrorCode` enum values (do not invent new strings unless required):
- `SIZE_EXCEEDED`, `INVALID_FORMAT`, `FETCH_FAILED`, `TIMEOUT`, `EXTRACTION_FAILED`, `STORAGE_FAILED`, `DATABASE_FAILED`, `VALIDATION_ERROR`

#### 3.2) Mapping table (Shared ↔ MCP ↔ A2A)

| Concept | Shared (canonical, snake_case) | MCP tool `process_audio_complete` | A2A task artifacts |
|---|---|---|---|
| Success flag | `success: bool` | `success` | artifact payload `success` (or artifact type implies success) |
| Track ID | `audio_id: str` | `audio_id` | artifact payload `audio_id`; optionally also `task.metadata.audio_id` |
| Metadata | `metadata: AudioMetadata` | `metadata` | artifact payload `metadata` |
| Resources | `resources: AudioResources` | `resources` | artifact payload `resources` |
| Embed link | `metadata.url_embed_link` | `metadata.url_embed_link` | artifact payload `metadata.url_embed_link` |
| Processing time | `processing_time: float` | `processing_time` | artifact payload `processing_time` (optional) |
| Error code | `error.code: ErrorCode` | `error` | failure artifact payload `error.code` |
| Error message | `error.message: str` | `message` | failure artifact payload `error.message` |
| Error details | `error.details: dict \| None` | `details` | failure artifact payload `error.details` |
| Retry hint | `error.retryable: bool` (optional) | *(not currently present)* | failure artifact payload `error.retryable` |

#### 4) Error mapping (shared → MCP vs A2A)

**Shared layer raises**: `AudioProcessingError` (exception) that contains the structured error payload above.

**MCP adapter**:
- translate shared `AudioProcessingError(code=...)` into existing MCP `ProcessAudioException/ErrorCode` where possible
- preserve `details` for client visibility

**A2A adapter**:
- mark task as `failed`
- attach a failure artifact that contains the structured error payload (and optionally a short human-readable summary)
- (optional) if `retryable=True`, include guidance in artifact metadata

#### 5) Determinism / “identical results”

The checklist says “identical results for same input”. In practice:
- **If you generate a new UUID every run**, the results cannot be byte-for-byte identical.
- Define “identical” as:
  - same extracted metadata fields (excluding nondeterministic fields like timestamps)
  - same stored resources (or same resource *structure* even if signed URLs differ)
  - same DB row contents except IDs/time-based fields

If strict determinism is needed, add an optional `audio_id` input to the shared request so both MCP and A2A can provide the same ID for the same operation.

#### 6) Module layout (minimal, testable)

**Required**:
- `src/business/__init__.py`
- `src/business/audio_processor.py`

**Recommended (if it keeps `audio_processor.py` from becoming huge)**:
- `src/business/audio_types.py` (request/result/error dataclasses/Pydantic models)
- `src/business/deps.py` (dependency injection container / protocol definitions)

If we want to keep the task strictly to two files for MVP, we can start with everything in `audio_processor.py` and split later.

#### 7) Refactor plan (mechanical steps, low risk)

1. **Introduce shared request/result/error types** (even if minimal dict-based initially).
2. **Move pipeline orchestration** from `src/tools/process_audio.py` into `src/business/audio_processor.py:process_audio_shared`.
3. Keep `src/tools/process_audio.py:process_audio_complete` as a thin adapter:
   - validate MCP input schema
   - call `process_audio_shared(...)`
   - format output in the exact existing shape
4. Update A2A handler to call `process_audio_shared(...)` using the URL extracted in Task 6.

#### 8) Validation criteria (what “done” means)

- Shared function exists: `src/business/audio_processor.py:process_audio_shared(...)`
- `src/tools/process_audio.py:process_audio_complete(...)` calls shared function and contains **no duplicated pipeline logic** beyond adapter concerns
- A2A handler calls the same shared function (after message parsing)
- Define and document what “identical results” means (see determinism note above)

### Implementation Steps

1. Create `src/business/` directory for shared logic
2. Create `src/business/audio_processor.py` with `process_audio_shared(...)` + shared error type
3. Refactor `src/tools/process_audio.py` to become an adapter around shared logic
4. Update A2A handler to call shared function (using Task 6 URL extraction)
5. Add minimal unit tests around shared logic with dependency injection (optional for MVP, but strongly recommended)

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
- [ ] Shared `process_audio_shared()` function exists (transport-agnostic)
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

**Goal**: Create utilities to extract audio URLs from A2A `Message` objects

**Context**: A2A sends parameters as messages with parts, not direct JSON. SDK provides typed `Message` and `Part` classes; we add domain-specific URL extraction.

**🔬 Research Update (LOI-23)**: SDK provides typed `Message`, `TextPart`, `FilePart` classes. We only need URL extraction logic, not message structure handling.

**Input Requirements**:
- SDK `Message` type from `a2a.types`
- Audio URL extraction requirements
- URL validation patterns

**Implementation Steps**:
1. Create `src/a2a/message_parser.py` with parsing functions:
   ```python
   # src/a2a/message_parser.py
   import re
   from urllib.parse import urlparse
   from a2a.types import Message, TextPart, FilePart
   
   # URL pattern for audio files
   AUDIO_URL_PATTERN = re.compile(
       r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:mp3|wav|flac|m4a|aac|ogg)',
       re.IGNORECASE
   )
   
   def extract_audio_url(message: Message) -> str | None:
       """Extract audio URL from A2A message parts.
       
       Checks:
       1. FilePart with audio MIME type
       2. TextPart containing audio URL
       """
       for part in message.parts:
           # Check for file parts with audio
           if isinstance(part, FilePart):
               if part.mime_type and part.mime_type.startswith('audio/'):
                   return part.uri
           
           # Check text parts for URLs
           if isinstance(part, TextPart):
               match = AUDIO_URL_PATTERN.search(part.text)
               if match:
                   return match.group(0)
       
       return None
   
   def validate_audio_url(url: str) -> bool:
       """Validate URL is safe to process."""
       parsed = urlparse(url)
       # Only allow HTTP/HTTPS
       if parsed.scheme not in ('http', 'https'):
           return False
       # Block internal IPs (SSRF protection)
       # ... existing SSRF checks from downloader ...
       return True
   ```

2. Integrate with `RequestHandler`:
   ```python
   # In src/a2a/handler.py
   from .message_parser import extract_audio_url, validate_audio_url
   
   class LoistRequestHandler(RequestHandler):
       async def on_send_message(self, request, context):
           audio_url = extract_audio_url(request.params.message)
           if not audio_url:
               raise ValueError("No audio URL found in message")
           if not validate_audio_url(audio_url):
               raise ValueError("Invalid or blocked audio URL")
           # ... continue processing
   ```

**SDK Types Used**:
```python
from a2a.types import (
    Message,      # Container with role and parts
    TextPart,     # Text content
    FilePart,     # File reference with URI and MIME type
    DataPart,     # Inline binary data
)
```

**Output Requirements**:
- URL extraction from `TextPart` content
- URL extraction from `FilePart` URIs
- SSRF protection via URL validation
- Clear error messages for missing URLs

**Validation Criteria**:
- [ ] Extracts URLs from `TextPart.text` content
- [ ] Extracts URLs from `FilePart.uri`
- [ ] Validates URL scheme (http/https only)
- [ ] SSRF protection blocks internal IPs
- [ ] Returns `None` gracefully for messages without URLs

**Files to Create/Modify**:
- `src/a2a/message_parser.py` (new)
- `src/a2a/handler.py` (integrate parser)

**Dependencies**:
- Task 4: JSON-RPC server configured (provides `Message` types)

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
   - Store audio_track_id in task.metadata if linking needed
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
   - Verify `/.well-known/agent-card.json` endpoint (SDK automatic)
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
- [ ] Agent Card returns valid JSON at `/.well-known/agent-card.json` (SDK automatic)
- [ ] `curl` test: `curl http://localhost:8080/.well-known/agent-card.json`
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
- New A2A files: `src/a2a/agent_card.py`, `src/a2a/handler.py`, `src/a2a/app.py`
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
        ('submitted', 'working', 'input-required', 'completed', 'failed', 'canceled', 'rejected')),
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

## 📋 **Design Work Completed (Planning Phase)**

**Based on detailed feedback and A2A v0.3 research - this document contains completed DESIGN work, not implementation:**

### 📝 **Planning & Design Structure**
- **10 focused tasks** outlined for future implementation
- **Clear dependencies** between tasks
- **Specific validation criteria** for each task completion
- **Self-contained** implementation chunks for future development

### 📋 **Agent Card Design (Task 2)**
- Designed `skills` array instead of `capabilities` object
- Added `serviceEndpoint` with `protocols: ["json-rpc"]`
- Added proper `authentication` object
- Specified A2A v0.3 compliant format

### 📋 **JSON-RPC API Design (Task 4)**
- ~~Planned `POST /a2a/v1/rpc` endpoint instead of REST~~
- **Updated**: Use SDK's `A2AFastAPIApplication` (handles protocol automatically)
- Implement `RequestHandler` interface for business logic
- SDK provides JSON-RPC routing, validation, error handling

### 📋 **Database Schema Design (Task 3)**
- ~~Designed simplified schema without over-engineering~~
- **Updated**: SDK's `DatabaseTaskStore` handles schema automatically
- Using SDK's default task model (no custom FK needed for MVP)
- If audio track linking needed, use `task.metadata` JSON field

### 📋 **Bridge Pattern Design (Task 5)**
- Designed shared business logic layer to avoid code duplication
- Planned MCP (stdio) and A2A (HTTP) integration
- Specified separate FastAPI app architecture

### 📋 **Component Integration Design**
- **Message Parsing** (Task 6): Use SDK's typed `Message`/`Part` classes + URL extraction
- **Processing Integration** (Task 7): Planned A2A to audio processing connection
- **Dual Server Deployment** (Task 8): Designed Docker Compose for both MCP and A2A
- **Agent Discovery Documentation** (Task 9): Planned how others find and use the service

### 📋 **Testing Strategy Design (Task 10)**
- Designed A2A compliance validation approach
- Planned end-to-end integration testing
- Created MVP completion checklist
- Established clear stop point criteria for Phase 2

### 📋 **Implementation Planning**
- Removed time/day estimates from planning
- Focused on deliverable completion criteria
- Each task measured by validation criteria

---

## 🔬 **SDK Research Update (LOI-23) - December 2025**

**Research Method**: DeepWiki Codemap analysis of `a2aproject/a2a-python`

### Key Findings

| Discovery | Impact |
|-----------|--------|
| SDK provides `DatabaseTaskStore` | Task 3 simplified: use SDK storage with defaults |
| SDK provides `A2AFastAPIApplication` | Task 4 simplified: implement `RequestHandler` interface |
| SDK has 7 task states (not 5) | Include `input-required` and `rejected` states |
| SDK uses `history` not `messages` | Naming alignment with SDK conventions |
| SDK uses default task model | Use `metadata` JSON field for relationships if needed |

### Effort Impact

| Task | Original Estimate | With SDK | Reduction |
|------|-------------------|----------|-----------|
| Task 3 (Database) | Manual SQL migration | SDK auto-creates (no migration) | **-80%** |
| Task 4 (JSON-RPC) | Manual handlers | Use SDK server | **-80%** |
| Task 6 (Parsing) | Manual message types | SDK provides types | **-50%** |

### Documentation Added

- SDK Research Findings section (top of document)
- Updated Task 3 with custom model pattern
- Updated Task 4 with `RequestHandler` implementation
- Updated Task 6 with SDK type usage
- Research citations with file paths and line numbers

**Status**: Planning document updated with SDK integration strategy. Implementation effort significantly reduced by leveraging SDK capabilities.

---

## 📋 **Schema Corrections Applied (Post-Review)**

### Agent Card v0.3 Compliance Fixes
- **Removed**: `agentId`, `serviceEndpoint`, `authentication` fields (outdated)
- **Added**: `protocolVersion`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `security`, `securitySchemes`
- **Updated**: Well-known path from `/.well-known/agent.json` to `/.well-known/agent-card.json`
- **Fixed**: Skills structure with required `id`, `name`, `description`, `tags` fields
- **Corrected**: SDK code examples to match A2A v0.3 AgentCard structure

### Architectural Alignment
- **Confirmed**: SDK provides complete JSON-RPC server (`A2AFastAPIApplication`)
- **Updated**: Task 2 to use SDK-served Agent Card (no manual JSON file needed)
- **Aligned**: All code examples with actual SDK types and patterns

**Review Status**: Critical schema issues resolved. Document now compliant with A2A v0.3 specification and SDK patterns.
