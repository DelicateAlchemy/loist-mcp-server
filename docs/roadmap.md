# Product Roadmap - Future Enhancements

**Status**: This document tracks future enhancements and feature requests that are **not part of the current MVP**. Items here are considered for future phases when current functionality proves successful.

**Last Updated**: December 15, 2025

---

## Overview

The Music Library MCP Server has a solid MVP foundation with core audio processing, metadata management, and MCP integration. This roadmap outlines potential future enhancements based on user feedback and market needs.

### Current MVP Status ✅

**Core Features (Completed)**
- Audio ingestion and metadata extraction
- Full-text search across library
- MCP protocol integration
- A2A-ready architecture
- Production deployment on Google Cloud

**See also**: [`docs/mcp-architecture.md`](../docs/mcp-architecture.md) for current architecture details.

---

## Service Layer Extensions

### Batch Operations API
**Priority**: Medium | **Phase**: Future (Phase 2-3)

**Current State**: ✅
- Internal batch operations exist (`update_processing_status_batch()` in `database/operations.py`)
- Basic batch processing support for audio ingestion workflows

**Future Enhancement**:
- Public API exposure for batch metadata updates
- Bulk operations across multiple tracks
- Transactional batch updates with rollback
- Progress tracking for long-running batch operations

**Use Cases**:
- Bulk metadata updates from spreadsheets
- Batch processing of playlist imports
- Mass tag corrections

**Related**: [`database/operations.py`](../database/operations.py) - existing batch functions

### Advanced Search with Aggregations
**Priority**: Medium | **Phase**: Future (Phase 2-3)

**Current State**: ✅
- Basic full-text search with filters
- Keyword search across metadata
- Artist, album, genre filtering

**Future Enhancement**:
- Faceted search with aggregations
- Analytics and reporting (genre distribution, decade analysis)
- Semantic search capabilities
- Advanced filters (tempo, key, energy level)
- Saved search templates
- Scalability to millions of records with optimized indexing

**Use Cases**:
- "Show me all rock songs from the 80s"
- "Find tracks similar to this mood"
- "Generate playlist analytics"

**Related**: [`docs/query-tools-api.md`](../docs/query-tools-api.md) - current search capabilities

### Playlist and Collection Management
**Priority**: Low | **Phase**: Future (Phase 3+)

**Current State**: ❌ Not implemented

**Future Enhancement**:
- User-created playlists and collections
- Shared playlists between agents
- Playlist collaboration features
- Export/import capabilities
- Integration with external playlist services

**Use Cases**:
- Curated music collections
- Agent-generated playlists
- Collaborative playlist building
- Export to external services

**Related**: [`docs/a2a-integration-analysis.md`](../docs/a2a-integration-analysis.md) - agent collaboration patterns

### Additional Caching Optimizations
**Priority**: Medium | **Phase**: Future (Phase 2)

**Current State**: ✅
- Signed URL caching (13.5 min TTL)
- Thread-safe cache implementation
- Hit/miss statistics tracking

**Future Enhancement**:
- Query result caching (metadata search results)
- Metadata field caching
- Multi-level cache hierarchy
- Cache warming strategies
- Performance monitoring and optimization

**Use Cases**:
- Improved response times for repeated searches
- Reduced database load
- Better performance under high concurrency

**Related**: [`docs/mcp-resources-api.md`](../docs/mcp-resources-api.md) - current caching implementation

### Song Publishing Enhancements
**Priority**: Low | **Phase**: Future (Post-MVP)

**Current State**: ✅ MVP Complete
- Repository and service layer for parties, works, and relationships
- Auto-work creation when saving audio tracks (audio-first workflow)
- Split validation warnings (non-blocking)
- Basic search using ILIKE pattern matching

**Future Enhancements**:
- **Full-text search optimization**: Switch `search_works` to use `search_vector` TSVECTOR column (created in migration 010) for improved performance on large datasets
- **Work merging**: Add `merge_works()` service method to consolidate multiple works when users realize recordings belong to the same composition
- **Work deletion**: Add `delete_work()` service method with proper checks for recordings (schema enforces `ON DELETE RESTRICT`)

**Use Cases**:
- Improved search performance as work catalog grows
- Consolidating duplicate works created during initial ingestion
- Managing work lifecycle (deletion when no longer needed)

**Related**: 
- [`docs/songs-database-planning.md`](../docs/songs-database-planning.md) - Song publishing implementation plan
- [`docs/songs-schema-design-philosophy.md`](../docs/songs-schema-design-philosophy.md) - Schema design rationale

---

## Advanced Features

### A2A Protocol Enhancements
**Priority**: Low | **Phase**: Future (Phase 3+)

**Current State**: ✅ Basic A2A-ready
- Agent Card discovery
- JSON-RPC task coordination
- Bridge pattern architecture

**Future Enhancement**:
- Real-time progress updates (SSE)
- Webhook callbacks
- Multi-agent collaboration
- Advanced error recovery
- Agent marketplace integration

**Related**: [`docs/a2a-integration-analysis.md`](../docs/a2a-integration-analysis.md) - A2A analysis and implementation

### Performance & Scalability
**Priority**: Medium | **Phase**: Future (Phase 2-3)

**Current State**: ✅ Production-ready
- Cloud Run autoscaling
- PostgreSQL connection pooling
- GCS optimization

**Future Enhancement**:
- Advanced database optimizations
- Multi-region deployment
- CDN integration
- Advanced monitoring and alerting

**Related**: [`docs/architecture-overview.md`](../docs/architecture-overview.md) - current performance optimizations

### Enhanced Audio Processing
**Priority**: Low | **Phase**: Future (Phase 3+)

**Current State**: ✅ Comprehensive
- Multi-format support (MP3, WAV, FLAC, AAC, OGG)
- Metadata extraction
- Waveform generation
- Format conversion

**Future Enhancement**:
- Audio analysis (tempo, key detection)
- Quality enhancement
- Audio cleanup and restoration
- Advanced format support

### Robust Large File Handling
**Priority**: Medium | **Phase**: Future (Phase 2-3)

**Current State**: ✅ Basic support
- FFmpeg conversion is functional for small to medium files.

**Future Enhancement**:
- **Efficient Memory/CPU Management**: Implement streaming processing in FFmpeg to handle large files (e.g., 100MB+) without loading them entirely into memory.
- **Resource Limiting**: Run FFmpeg as a child process with strict timeouts and resource caps to prevent oversubscription.
- **Concurrency Management**: Limit the number of concurrent conversion jobs.
- **Reliable Temp File Strategy**: Use a robust disk-based temporary file strategy with guaranteed cleanup on success or failure.
- **Intelligent URL Expiration**: Ensure signed URLs for GCS have an expiration time that accommodates potentially long conversion times for large files.
- **Interruption Handling**: Gracefully handle and recover from download/conversion interruptions.

**Use Cases**:
- Processing and serving large audio files like podcasts, DJ mixes, or high-resolution tracks.
- Ensuring server stability under heavy conversion load.

---

## Deployment & Infrastructure

### A2A Custom Domain Mapping
**Priority**: Low | **Phase**: Future (Post-MVP)

**Current State**: ✅ MVP uses direct `.run.app` URLs
- A2A services deployed to Cloud Run with direct URLs
- Agent Card configured with `.run.app` URLs for MVP
- Services: `a2a-staging` and `a2a-prod` in `us-central1` region

**Future Enhancement**:
- Custom domain mapping for A2A services (`a2a.loist.io`, `a2a.staging.loist.io`)
- Application Load Balancer setup for `us-central1` region (native domain mapping not supported)
- Update Agent Card URLs to use custom domains
- Update Postman environment files with custom domain URLs
- Production branding and polish

**Technical Requirements**:
- **Regional Limitation**: Native Cloud Run domain mappings not supported in `us-central1` (only `us-east1`, `us-east4`, `us-west1`)
- **Load Balancer Required**: Custom domains in `us-central1` require Application Load Balancer
- **Cost**: Additional ~$20-50/month for Load Balancer infrastructure
- **Implementation**: Follow same pattern as MCP custom domain setup (see `docs/custom-domain-mapping-guide.md`)

**Use Cases**:
- Professional branding for production A2A services
- Simplified agent discovery URLs
- Consistent domain naming across services

**Related**:
- [`docs/custom-domain-mapping-guide.md`](../docs/custom-domain-mapping-guide.md) - Load Balancer setup guide for MCP services
- [`docs/a2a-mvp-tasks.md`](../docs/a2a-mvp-tasks.md) - A2A MVP implementation (DOM1 task deferred)

**Deferred Rationale**:
- MVP focus on functionality over branding
- Direct `.run.app` URLs sufficient for MVP testing and integration
- Load Balancer adds complexity and cost that can be deferred until production polish needed

---

## Decision Framework

### When to Implement Roadmap Items

**Move to Active Development when**:
- Current MVP proves successful with real users
- Clear user demand for specific features
- Business requirements dictate new capabilities
- Performance issues require optimization

**Evaluation Criteria**:
- User feedback and usage patterns
- Business value and ROI
- Technical feasibility
- Resource availability
- Competitive landscape

### Prioritization Guidelines

**High Priority** (Phase 2):
- Features that enhance current user experience
- Performance improvements
- Reliability enhancements
- Basic missing functionality

**Medium Priority** (Phase 2-3):
- Nice-to-have enhancements
- Advanced features with clear use cases
- Optimization opportunities

**Low Priority** (Phase 3+):
- Advanced features without immediate demand
- Nice-to-have capabilities
- Experimental features

---

## Contributing to the Roadmap

**To suggest new roadmap items**:
1. Check if the feature already exists in current implementation
2. Add to this document with clear description and rationale
3. Include use cases and priority assessment
4. Link to related documentation

**To promote roadmap items to active development**:
1. Gather user feedback demonstrating demand
2. Create detailed requirements document
3. Assess technical feasibility and effort
4. Present business case for prioritization

---

## Related Documentation

- [`docs/mcp-architecture.md`](../docs/mcp-architecture.md) - Current architecture
- [`docs/a2a-integration-analysis.md`](../docs/a2a-integration-analysis.md) - A2A protocol analysis
- [`docs/a2a-mvp-tasks.md`](../docs/a2a-mvp-tasks.md) - A2A MVP implementation tracking
- [`docs/custom-domain-mapping-guide.md`](../docs/custom-domain-mapping-guide.md) - Custom domain setup guide
- [`docs/api-endpoint-refactoring.md`](../docs/api-endpoint-refactoring.md) - Recent architecture decisions
- [`README.md`](../README.md) - Project overview and current features</contents>
</xai:function_call name="search_replace">
<parameter name="file_path">/Users/Gareth/loist-mcp-server/docs/mcp-audit-tasks.md
