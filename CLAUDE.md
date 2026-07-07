# loist-mcp-server

FastMCP server for audio ingestion, metadata extraction, and music library management.
Python 3.11 | FastMCP 2.12+ | FastAPI | PostgreSQL | Google Cloud Storage

## Architecture

Layered architecture with dependency injection via repository pattern:

```
src/tools/          MCP tool endpoints (query, update, download, embed, process_audio)
src/services/       Business logic (audio, party, work, download, streaming)
src/repositories/   Data access abstraction (audio, party, work) - ABC interfaces + Postgres impl
src/schemas/        Pydantic models (party, work, publishing, metadata, http_api)
src/storage/        GCS client, waveform storage, retry logic
src/metadata/       Audio metadata extraction (ID3, BWF, XMP, format validation)
src/resources/      MCP resource providers (audio_stream, thumbnail, cache)
src/exceptions/     Exception hierarchy with circuit breaker, retry, recovery
src/a2a_server/     Agent-to-Agent HTTP server (FastAPI, port 8081)
src/config.py       Pydantic BaseSettings configuration (ServerConfig)
src/server.py       Main MCP server bootstrap and tool/resource registration
src/http_api.py     FastAPI HTTP route registration
database/           PostgreSQL operations, connection pooling, migrations
database/operations.py  All SQL queries
database/pool.py    psycopg2 connection pooling
database/migrations/    Numbered SQL files (NNN_description.sql)
```

## Running Locally

```bash
# Docker (recommended) - starts MCP server + A2A server + PostgreSQL
docker-compose up -d
curl http://localhost:8080/health/ready

# Direct (requires local PostgreSQL and env vars from .env)
python run_server.py    # HTTP on port 8080
```

Environment: copy `.env.example` to `.env`. Key vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `GCS_BUCKET_NAME`, `GCS_PROJECT_ID`, `SERVER_TRANSPORT` (stdio|http|sse).

Migrations: `python database/migrate.py --action=apply` (see `database/migrations/README.md`).

## Testing

```bash
# Unit tests only (no external deps)
pytest tests/ -m "not (requires_db or requires_gcs or slow or requires_tools)" -v

# All tests (requires database + GCS)
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=75

# Specific markers
pytest tests/ -m unit -v
pytest tests/ -m requires_db -v
```

Markers (auto-assigned via root `conftest.py`): `unit`, `requires_db`, `requires_gcs`, `requires_tools`, `slow`, `regression`.

## Code Style

- **Formatter**: `black --line-length 100` (target py311)
- **Imports**: `isort --profile black --line-length 100`
- **Linter**: `ruff check` (line-length 100, rules E/W/F/C, max-complexity 12)
- **Types**: `mypy --config-file .mypy.ini` (strict mode)
- **Security**: `bandit -r src/ -c pyproject.toml`

## Conventions

- Services are `async def`. Repositories use sync psycopg2.
- Repository pattern: ABC interface + `PostgresXxxRepository` + module-level `get_xxx_repository()` for DI.
- Pydantic schemas: `XxxInput` for request validation, `XxxOutput` for responses. Use `Field(...)` with constraints.
- Exceptions: custom hierarchy rooted at `MusicLibraryError` in `src/exceptions_core.py`.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` constants.
- Imports: `from src.module import ...` (not bare `from module`).
- Config: all settings in `src/config.py` via `pydantic_settings.BaseSettings`.
- Database: raw SQL in `database/operations.py`, migrations in `database/migrations/`.

## Branching

- `dev` is the integration branch: all feature branches are cut from `origin/dev` and PR back into `dev`. Staging deploys track `dev`.
- `main` is the release branch: it only receives merges **from** `dev` (release promotion). Never commit or merge features directly to `main` — that caused a months-long main/dev divergence (LOI-43).
- Always `git fetch origin` and branch from `origin/dev`, not a local `dev`, which may be stale.
