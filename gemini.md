# GEMINI.md - Project Context for AI Agents

> **Note:** This file provides project-specific context and workflows. See [AGENTS.md](AGENTS.md) for action-oriented rules that agents must follow.

## Project Overview

**Loist MCP Server** - FastMCP-based server for audio ingestion and embedding with the Music Library MCP protocol.

### Key Architecture Patterns

- **Repository Pattern**: Clean data access abstraction (`src/repositories/`)
- **Unified Exception Framework**: Comprehensive error handling (`src/exceptions/`)
- **FastMCP Integration**: MCP v1.16.0 protocol implementation
- **Docker-First Development**: Always use Docker/docker-compose (venv is outdated)

### Development Environment

**Local Development (Recommended):**
```bash
# Start local environment (uses local PostgreSQL - FREE)
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Stop environment
docker-compose down
```

**Cloud SQL Management:**
- **Cost**: ~£50-80/month when running 24/7
- **Local Dev**: Use Docker Compose (FREE)
- **Only Start Cloud SQL**: When testing staging/production deployments
- **Always Stop After Testing**: `./scripts/manage-cloud-sql.sh stop`

See [Cloud SQL Optimization Guide](.cursor/rules/cloud-sql-optimization.mdc) for detailed cost management.

## Long-Running Projects

For multi-session refactoring and feature work, use file-based project management:

### Project Management Conventions

**Always derive plans from spec files** rather than inventing tasks:
- Read spec documents (e.g., `docs/api-endpoint-refactoring.md`)
- Generate task lists from spec milestones
- Maintain rolling summaries for context

### Key Project Files

**Spec Files** (source of truth for planning):
- `docs/api-endpoint-refactoring.md` - API refactoring plan with milestones

**Task Management Files** (generated from specs):
- `docs/api-refactor-tasks.md` - Task checklist with IDs, grouped by phase
- `docs/api-refactor-summary.md` - Rolling summary of completed work
- `docs/api-refactor-research.md` - Answers to open questions

**Workflow:**
1. Read spec file to understand project structure
2. Generate/update task list file with IDs (e.g., R1, R2, E1, E2)
3. Before starting work: Read task list, pick next todo, mark as "doing"
4. After completing: Mark task "done", update summary file
5. At session start: Re-read task list and summary to restore context

### Context Window Management

**Use rolling summaries** to compress history:
- After each significant subtask: Update summary file with what changed
- When conversation is long: Produce "current state" summary from summary file
- Summary files are small and always readable, even in new sessions

See [AGENTS.md](AGENTS.md) for detailed project management rules.

## Key Workflows

### Intent Communication & Confidence Assessment

**Before Significant Actions:**
```
🎯 **Intent**: I'm going to [action] because [reason].
   - Files affected: [list]
   - Expected outcome: [outcome]
   - Potential risks: [risks, if any]
```

**Confidence Levels:**
- 🟢 **High** (0.8-1.0): Clear docs, familiar pattern, tested approach
- 🟡 **Medium** (0.5-0.8): Based on code patterns, may need verification
- 🟠 **Low** (0.3-0.5): Limited context, outdated docs possible, needs research
- 🔴 **Very Low** (<0.3): No clear information, external research needed

**When Confidence < 0.66:**
- Flag uncertainty proactively
- Provide Perplexity research prompts (copy-paste ready)
- Document decisions with reasoning

### Research Collaboration

**When to Request Research:**
- Confidence < 0.66 on technical decisions
- Version-specific behavior (Python, GCP, FastMCP)
- Cloud service configurations that may have changed
- Security best practices
- Performance optimizations

**Perplexity Prompt Format:**
```
🔍 **Suggested Perplexity Research**

**Topic**: [brief topic description]

**Prompt to copy**:
---
[Specific, contextual research question with relevant technical details]

Include: current best practices, recent changes, version-specific considerations.
Context: [brief project context relevant to the search]
---

**What to look for**: [specific aspects to validate]
```

### Decision Documentation

**For Uncertain Decisions (<0.8 confidence):**
```
📝 **Decision Record**

**Decision**: [what was decided]
**Confidence**: [level]
**Reasoning**: [why this approach]
**Alternatives considered**: [other options]
**Validation needed**: [how to verify this works]
**Rollback plan**: [if it doesn't work]
```

## Git Workflow

### Branch Structure
- **`main`**: Production (only merges from `dev` via PR)
- **`dev`**: Development integration (receives task branches)
- **`task-{id}`**: Feature branches (one per root task ID)

### Subtask Implementation Process

1. **Create branch**: `git checkout -b task-{id}` from `dev`
2. **Mark subtask in-progress**: Before starting work
3. **Implement**: One subtask at a time
4. **Commit**: One commit per subtask completion
5. **Mark subtask done**: After committing
6. **Repeat**: Until all subtasks complete
7. **Merge**: Push branch, create PR to `dev`

**Commit Format:**
```
feat(module): Implement [subtask title] (Task {id}.{subtaskId})

- Implementation detail 1
- Implementation detail 2
- Files changed: src/component.py, tests/test_component.py
```

See [Git Workflow Guide](.cursor/rules/git-workflow.mdc) for complete details.

## MCP Server Connection Management

**Critical**: MCP clients must restart after Docker container changes.

**Workflow:**
```bash
# 1. Stop container
docker-compose down

# 2. Make changes (code, config, etc.)

# 3. Start container
docker-compose up -d --build

# 4. Wait for health check
curl http://localhost:8080/health/ready

# 5. RESTART MCP CLIENT (required)
# Cursor: Cmd/Ctrl + Shift + P → "Developer: Reload Window"
# Claude Desktop: Restart application
```

**Why**: MCP sessions become invalid when containers restart. This is normal behavior, not a bug.

See [MCP Connection Guide](.cursor/rules/mcp-server-connection.mdc) for troubleshooting.

## Documentation Management

### README.md vs docs/

**Update README.md for:**
- New major features
- Breaking changes
- Installation changes
- Architecture shifts

**Create docs/ files for:**
- Content >500 words
- Technical depth (implementation details)
- Reference material (API specs, config schemas)
- Multiple scenarios (deployment environments)

**Principle**: README.md is the entry point. Detailed docs live in `docs/` with links from README.

See [Documentation Management Guide](.cursor/rules/documentation-management.mdc) for complete guidelines.

## Code Patterns

### Repository Pattern
- **Location**: `src/repositories/`
- **Pattern**: Abstract interface with implementations
- **Usage**: Dependency injection for testability

### Exception Framework
- **Location**: `src/exceptions/`
- **Pattern**: Unified error handling with recovery strategies
- **Integration**: Clean FastMCP serialization

### Database Operations
- **Pattern**: Batch operations for performance (75-80% faster)
- **Connection Pooling**: Optimized for Cloud Run
- **Full-Text Search**: PostgreSQL tsvector with weighted ranking

## Project-Specific Confidence Areas

### High Confidence (0.8+)
- Repository pattern usage
- Exception framework patterns
- Docker Compose local development
- Git workflow (task branches)
- PostgreSQL full-text search

### Medium Confidence (0.5-0.8)
- Cloud Build configuration details
- GCS signed URL implementation
- Cloud Run scaling settings
- MCP protocol edge cases

### Research Recommended (<0.5)
- GCP service-specific API changes
- Python/FastMCP version updates
- Security scanning tool configurations
- IAM permission changes

## Development Commands

### Local Development
```bash
# Start environment
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Run tests (ALWAYS use Docker - never local venv)
docker-compose exec mcp-server pytest tests/ -v
docker-compose exec mcp-server pytest tests/ --cov=src --cov-report=term-missing

# Verify imports work
docker-compose exec mcp-server python -c "from src.server import mcp; print('OK')"

# Health checks
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/database
```

### Cloud SQL Management
```bash
# Check status
./scripts/manage-cloud-sql.sh status

# Stop (save money!)
./scripts/manage-cloud-sql.sh stop

# Start (only when testing staging/production)
./scripts/manage-cloud-sql.sh start
```

### Code Quality
```bash
# Formatting
black src/ tests/ database/
isort src/ tests/ database/

# Linting
flake8 src/ tests/ database/
mypy src/ database/

# Security
bandit -r src/ database/
safety check
```

## Related Documentation

- **[AGENTS.md](AGENTS.md)** - Action-oriented rules (must-follow)
- **[README.md](README.md)** - Project overview and quick start
- **[docs/](docs/)** - Comprehensive technical documentation
- **[.cursor/rules/](.cursor/rules/)** - Detailed workflow guides

## Rule Maintenance

When creating or updating rules:
- Base on actual code patterns (3+ files)
- Include DO/DON'T examples from codebase
- Reference existing code when possible
- Keep rules DRY by referencing other rules
- Update when patterns change

See [Rule Maintenance Guide](.cursor/rules/rule-maintenance.mdc) for complete guidelines.

---

**Remember**: This file provides context. For action-oriented rules, see [AGENTS.md](AGENTS.md).
