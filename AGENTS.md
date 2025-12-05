# AGENTS.md - AI Agent Instructions

**Action-oriented rules for AI agents working in this codebase.**

## Critical Rules (MUST FOLLOW)

### Intent Communication
- **ALWAYS** state intent before significant actions (multi-file changes, infrastructure, migrations)
- Format: `🎯 Intent: [action] because [reason]. Files: [list]. Expected: [outcome]`
- **ALWAYS** summarize after completion: `✅ Completed: [summary]. Changes: [files]. Next: [steps]`

### Confidence Assessment
- **ALWAYS** rate confidence honestly (🟢 High 0.8+, 🟡 Medium 0.5-0.8, 🟠 Low 0.3-0.5, 🔴 Very Low <0.3)
- **FLAG** uncertainty when confidence < 0.66 or working with GCP/cloud services
- **PROVIDE** WebSearch research prompts when uncertain

### Cloud SQL Cost Optimization
- **NEVER** suggest starting Cloud SQL for local development
- **ALWAYS** use `docker-compose up -d` for local development (uses local PostgreSQL - FREE)
- **ONLY** suggest Cloud SQL when testing staging/production deployments
- **ALWAYS** remind to stop Cloud SQL after testing: `./scripts/manage-cloud-sql.sh stop`
- **CHECK** Cloud SQL status before starting work: `./scripts/manage-cloud-sql.sh status`

### Git Workflow
- **ALWAYS** create `task-{id}` branch from `dev` before starting work
- **ONE** commit per subtask completion (never batch multiple subtasks)
- **ALWAYS** mark subtask `in-progress` before starting, `done` after committing
- Commit format: `feat(module): [subtask title] (Task {id}.{subtaskId})\n\n- Details\n- Files: [list]`
- **NEVER** commit directly to `main` or `dev` branches

### MCP Server Connection
- **ALWAYS** restart MCP client after Docker container changes (`docker-compose down` → `docker-compose up -d`)
- **VERIFY** health checks before MCP operations: `curl http://localhost:8080/health/ready`
- **DON'T** troubleshoot "session ID" errors - restart MCP client instead

### Development Environment
- **ALWAYS** use Docker/docker-compose (not local venv - outdated dependencies)
- **VERIFY** container health before operations
- **USE** `docker-compose logs -f mcp-server` for debugging

### Documentation Management
- **UPDATE** README.md for high-impact changes (new features, breaking changes, installation changes)
- **CREATE** separate docs/ files for detailed content (>500 words, technical depth, reference material)
- **LINK** to detailed docs from README, don't duplicate content

### Code Citation Format
- **USE** code references for existing code: ` ```startLine:endLine:filepath`
- **USE** markdown code blocks for new/proposed code: ` ```language`
- **NEVER** mix formats or add line numbers to code content

### Project Management (Long-Running Work)

**When given a spec file (e.g., `docs/api-endpoint-refactoring.md`):**
- **PARSE** spec into task list and write to `docs/{project-name}-tasks.md`
- **FORMAT** tasks with IDs (e.g., R1, R2, E1, E2), status (todo/doing/done), brief description
- **GROUP** tasks by phase/milestone from spec
- **INCLUDE** open questions from spec as tracked items

**Before starting work:**
- **READ** task list file (`docs/{project-name}-tasks.md`)
- **PICK** next "todo" task (optionally filtered by phase/area if requested)
- **MARK** task as "doing" and write file back
- **STATE** intent using standard format: `🎯 Intent: [action] because [reason]...`

**After finishing work:**
- **MARK** task as "done" and write file back
- **UPDATE** summary file (`docs/{project-name}-summary.md`) with:
  - What was done (brief bullet)
  - Files touched
  - Outstanding follow-ups / new TODOs
- **RESEARCH** open questions if needed (see Research Collaboration below)

**At start of new session:**
- **READ** task list (`docs/{project-name}-tasks.md`) and summary (`docs/{project-name}-summary.md`)
- **SUMMARIZE** current state in 3-5 bullets before continuing
- **IDENTIFY** next task to work on

**Research for open questions:**
- **FOR** questions in spec's "Open Questions" section:
  - **PROPOSE** concrete WebSearch query
  - **CALL** WebSearch tool with query
  - **WRITE** answers to `docs/{project-name}-research.md` or update spec
- **KEEP** research grounded in project files, not transient chat

## Project-Specific Patterns

### High-Confidence Areas (0.8+)
- Repository pattern usage (`src/repositories/`)
- Exception framework patterns (`src/exceptions/`)
- Docker Compose local development
- Git workflow (task branches)
- PostgreSQL full-text search

### Research-Recommended Areas (<0.5)
- GCP service-specific API changes
- Python/FastMCP version updates
- Security scanning tool configurations
- IAM permission changes
- HTTP streaming best practices (Range requests, proxy vs redirect)
- Image optimization and caching strategies
- API versioning patterns

## Quick Reference Commands

```bash
# Local development
docker-compose up -d
docker-compose logs -f mcp-server

# Cloud SQL management
./scripts/manage-cloud-sql.sh status
./scripts/manage-cloud-sql.sh stop  # Save money!

# Health checks
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/database

# Testing
pytest tests/ -v
pytest --cov=src --cov-report=html
```

## Related Documentation

- **[GEMINI.md](gemini.md)** - Project context and detailed workflows
- **[README.md](README.md)** - Project overview and quick start
- **[docs/](docs/)** - Comprehensive technical documentation

---

**Remember**: These are non-negotiable rules. When in doubt, ask for clarification rather than guessing.

