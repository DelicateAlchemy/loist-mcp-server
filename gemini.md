# Gemini Code Assistant Customization

This document provides instructions for the Gemini code assistant to ensure its contributions align with the project's standards, conventions, and architecture.

## 1. Project Overview

- **Project Name:** Loist MCP Server
- **Description:** A FastMCP-based server for audio ingestion and embedding, designed for a music library system. It uses the Model Context Protocol (MCP).
- **Key Technologies:** Python 3.11, FastMCP, Pydantic, PostgreSQL, Google Cloud Storage, Docker.

## 2. Tech Stack & Conventions

| Category      | Tool/Library                               | Configuration/Notes                                       |
|---------------|--------------------------------------------|-----------------------------------------------------------|
| **Language**  | Python 3.11                                | Strict typing is required. Use modern Python features.    |
| **Framework** | FastMCP                                    | Main application framework. See `src/server.py`.          |
| **Config**    | Pydantic `BaseSettings`                    | Centralized in `src/config.py`. Loaded from `.env` file.  |
| **Database**  | PostgreSQL                                 | Interacted with via `psycopg2`. See `database/` module.   |
| **Storage**   | Google Cloud Storage (GCS)                 | Client logic is in `src/storage/gcs_client.py`.           |
| **Linting**   | `ruff`                                     | Configured in `pyproject.toml`. Run `ruff check .`        |
| **Formatting**| `black`                                    | Configured in `pyproject.toml` (line length 100).         |
| **Testing**   | `pytest`                                   | Tests are located in the `tests/` directory.              |
| **Packaging** | `uv`                                       | Used for virtual environment and package management.      |
| **Container** | Docker & Docker Compose                    | See `Dockerfile` and `docker-compose.yml`.                |

## 3. Development Workflow

- **Setup:**
  1. `uv venv --python 3.11`
  2. `source .venv/bin/activate`
  3. `uv pip install -r requirements.txt`
  4. `uv pip install -e ".[dev]"` (for development dependencies)

- **Running the Server:**
  - **Development (STDIO):** `python src/server.py`
  - **Development (HTTP):** Set `SERVER_TRANSPORT=http` in `.env` and run `python src/server.py`.
  - **Docker:** `docker-compose up`

- **Running Tests:**
  - `pytest tests/`

- **Code Quality:**
  - **Linting:** `ruff check src/ tests/`
  - **Formatting:** `black src/ tests/`

## 4. Task Management & Git Workflow

This project uses a `task-master` MCP for task management.

- **Workflow:**
  1. **Get Next Task:** Use `next_task` to identify the next subtask to work on.
  2. **Implement:** Implement the required changes for the subtask.
  3. **Test:** Run all relevant tests using `pytest tests/` to ensure your changes are correct and have not introduced any regressions.
  4. **Commit:** Once the tests pass, create a new Git commit for the completed subtask. The commit message should clearly describe the changes and reference the subtask ID (e.g., `feat(downloader): implement http download logic for subtask 3.1`).
  5. **Mark as Done:** After committing, mark the subtask as complete using `set_task_status --id <subtask-id> --status done`.

- **Commits:**
  - Each subtask should be a separate commit.
  - Do not bundle multiple subtasks into a single commit.

## 5. Instructions for Gemini

### General Principles

- **Adhere to Conventions:** Strictly follow the existing coding style, structure, and conventions outlined in this document and observed in the codebase.
- **Analyze First:** Before making changes, use `read_file` and `glob` to understand the relevant code, its context, and associated tests.
- **Verify Changes:** After modifying code, always run the relevant tests and linting/formatting commands to ensure correctness and quality.

### Code Generation & Modification

- **Typing:** All new functions and methods **must** include full type hints for arguments and return values.
- **Configuration:** Do not hardcode values. If a new setting is needed, add it to the `ServerConfig` class in `src/config.py` and document it.
- **Error Handling:** Use the custom exception hierarchy defined in `src/exceptions.py`. Wrap logic that can fail in `try...except` blocks and raise the appropriate custom exception.
- **Modularity:** Respect the existing project structure. For new, distinct functionality, create a new module. For example, a new downloader would go in the `src/downloader/` directory.
- **Database:** For database schema changes, create new migration files in `database/migrations/`. For new queries, add methods to the appropriate data access class.
- **Dependencies:** If you need to add a new dependency, add it to `requirements.txt` and `pyproject.toml` and then run `uv pip install -r requirements.txt`.

### Tool Usage

- **File Paths:** Always use absolute paths when using file system tools. The project root is `/Users/Gareth/loist-mcp-server`.
- **Shell Commands:**
  - Explain the purpose of any shell command, especially those that modify files or system state, before executing it.
  - Use non-interactive flags where possible (e.g., `npm init -y`).
- **Commits:** When asked to commit, follow these steps:
  1. Run `git status` to identify changes.
  2. Run `git add .` to stage all relevant changes.
  3. Propose a commit message that follows the conventional commit format (e.g., `feat: add user authentication endpoint`). The message should be clear and concise.