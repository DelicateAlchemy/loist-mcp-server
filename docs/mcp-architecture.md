# MCP Server Architecture

This document provides an overview of the Loist MCP Server's architecture, design principles, and key decisions.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Bridge Pattern: MCP (stdio) vs. A2A (HTTP)](#bridge-pattern-mcp-stdio-vs-a2a-http)
- [Tool Design: Core vs. Operational](#tool-design-core-vs-operational)
- [A2A Compatibility](#a2a-compatibility)
- [Zero-Resource Design Rationale](#zero-resource-design-rationale)

---

## Architecture Overview

The server is designed with a clean, layered architecture to separate concerns and improve maintainability.

- **MCP Protocol Layer (`server.py`)**: This is the entry point for all MCP communication. It handles the JSON-RPC 2.0 protocol over standard input/output (stdio), parsing requests and formatting responses. It is responsible for dispatching calls to the appropriate services.

- **Service Layer (`src/services/`)**: This layer contains the core business logic of the application. Each service (e.g., `AudioProcessingService`, `SearchService`) encapsulates a specific domain of functionality. Services are called by the protocol layer and interact with the repository layer to access data.

- **Repository Layer (`database/operations.py`)**: This layer abstracts data access. It provides a clean API for querying and modifying the database, hiding the underlying SQL from the service layer. This follows the Repository Pattern, making it easier to manage data operations and swap out the data source if needed.

- **Infrastructure**:
  - **PostgreSQL**: The primary database for storing all audio metadata, track information, and application state.
  - **Google Cloud Storage (GCS)**: Used for storing all binary audio and image files.

---

## Bridge Pattern: MCP (stdio) vs. A2A (HTTP)

A key architectural decision is the separation of the MCP server from a potential Agent-to-Agent (A2A) server, forming a "Bridge Pattern." This is necessary because they serve different purposes and use fundamentally different communication transports.

- **MCP Transport (stdio)**: The current server uses stdio for communication. This is ideal for local tool usage by Large Language Models (LLMs) and IDE extensions (like Cursor), which execute the server as a local process and communicate over standard streams. It is simple, fast, and secure for local operations.

- **A2A Transport (HTTP)**: A2A communication, by contrast, requires an HTTP transport for agent discovery and coordination across a network. It involves web servers, public-facing endpoints (like `/.well-known/agent.json`), and different security considerations (e.g., CORS, authentication).

- **Shared Business Logic**: While the transports are different, both the MCP server and a future A2A server would call the same underlying **Service Layer** functions. This ensures that core business logic remains consistent, regardless of how it is exposed.

This separation allows the MCP server to remain a lightweight, specialized tool for local use, while a separate application can handle the complexities of network-based agent interaction.

> For more details on this design, see the [A2A Protocol Integration Analysis](a2a-integration-analysis.md).

---

## Tool Design: Core vs. Operational

The server's functions are categorized into two distinct types of tools, which are exposed differently.

### Core Business Tools (MCP)
These tools represent the core functionality of the application and are exposed via the MCP JSON-RPC protocol. They are designed for agentic workflows.

- `process_audio_complete`
- `search_library`
- `get_audio_metadata`
- `update_metadata`
- `delete_audio`
- `get_embed_url`
- `download_audio`

**Tool Granularity**: The tools are intentionally designed to be granular and single-purpose. Research has shown that this approach is more token-efficient for LLM agents compared to large, multi-purpose tools with many parameters.

### Operational Tools (HTTP-Only)
These tools are for monitoring, health checks, and operational visibility. They are exposed as simple, stateless HTTP GET endpoints and are **not** part of the MCP toolset.

- `/health/ready`, `/health/live`, `/health/database` (Health Checks)
- `get_waveform_metrics_tool` (Metrics)
- `get_circuit_breaker_status` (System State)

This separation ensures that the MCP tool surface remains clean and focused on core business capabilities, while operational endpoints follow standard, well-understood HTTP conventions.

---

## A2A Compatibility

The current MCP tool design is already **A2A-ready**. This means that if and when an A2A server is developed, the existing tools can be exposed through it with minimal changes. The key characteristics that ensure this compatibility are:

- **Typed Schemas**: All tools have clearly defined input and output schemas.
- **Idempotent Reads**: Read-only operations (`get_audio_metadata`, `search_library`) are idempotent and have no side effects.
- **Explicit Side Effects**: Operations that modify state (`process_audio_complete`, `delete_audio`) have clear and explicit side effects.

The A2A protocol would not replace the MCP tools; rather, it would make them **discoverable** and **callable** by other agents over a network.

---

## Tool vs. Resource Design

The server strategically uses both MCP Tools and MCP Resources to provide a clean and efficient API. The design philosophy is to use the right primitive for the job:

-   **Tools are for Actions**: Operations that involve processing, computation, or state changes are implemented as `tools`. This includes `process_audio_complete`, `search_library`, and `delete_audio`. These are actions that an agent asks the server to *do*.

-   **Resources are for Data**: Accessing the results of previous actions, especially binary or large data, is handled by `resources`. This provides a stable, URI-based way to retrieve data like audio streams or thumbnails. The server provides the following resources:
    -   `music-library://audio/{id}/stream`: For streaming audio content.
    -   `music-library://audio/{id}/thumbnail`: For retrieving album artwork.
    -   `music-library://audio/{id}/metadata`: For retrieving track metadata as a JSON object.

This separation aligns with the MCP specification, where tools perform work and resources represent the data artifacts resulting from that work. It allows for a clean, noun/verb distinction in the API.
