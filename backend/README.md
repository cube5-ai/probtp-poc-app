# PRO BTP Backend

Backend API for the PRO BTP Benefits Comparison POC.

## Development Setup

This project uses `uv` for dependency management and includes development tools like `ruff` and `mypy`.

### Prerequisites

- Python 3.11+
- uv 

### Getting Started

1. **Install dependencies:**
   ```bash
   uv sync --dev
   ```

2. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```
   Or use `uv run` to run commands in the virtual environment automatically.

### Development Tools

- **Code formatting and linting:** `uv run ruff check app/` and `uv run ruff format app/`
- **Type checking:** `uv run mypy app/`
- **Testing:** `uv run pytest`
- **Pre-commit hooks:** `uv run pre-commit install`

### Database Access (Cloud SQL Proxy)

The repository no longer ships with a local SQLite file. To work against the
managed PostgreSQL instance from your machine:

1. Install the Cloud SQL Auth Proxy and authenticate with the same project as
   the instance (`probtp-poc-prod`).
2. Start the proxy: `cloud-sql-proxy --port 5433 probtp-poc-prod:europe-west9:probtp-poc-db-prod`
3. Copy `backend/.env.example` to `backend/.env` (or update your existing file)
   and set `DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:5433/probtp-poc_prod`.

With the proxy running, `uvicorn` and the helper script `uv run python
test_db_connection.py` will both connect to Cloud SQL.

### Project Structure

- `app/` - Main application code
- `tests/` - Test files
- `alembic/` - Database migrations
- `pyproject.toml` - Project configuration and dependencies

### Key Dependencies

- FastAPI - Web framework
- SQLAlchemy + Alembic - Database ORM and migrations
- PostgreSQL + pgvector - Database with vector search
- Google Cloud libraries - Storage and authentication
- Firebase Admin - Authentication
- Structlog - Structured logging

### Tools Configuration

All development tools are configured in `pyproject.toml`:
- Ruff for linting and formatting
- MyPy for type checking
- Pytest for testing
- Coverage for test coverage
