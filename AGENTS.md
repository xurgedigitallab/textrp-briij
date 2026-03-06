# AGENTS.md

## Cursor Cloud specific instructions

This is the **Element Synapse** Matrix homeserver (Python 3 + Rust). See `CONTRIBUTING.md` section 4 for full developer setup and section 8 for testing instructions.

### Running the application

1. Generate config: `poetry run python -m synapse.app.homeserver --generate-config --server-name localhost --config-path homeserver.yaml --report-stats=no`
2. Start server: `poetry run python -m synapse.app.homeserver -c homeserver.yaml`
3. The server listens on `http://127.0.0.1:8008` by default.
4. To register a user with the shared secret from config: `poetry run register_new_matrix_user -c homeserver.yaml -u USERNAME -p PASSWORD -a http://localhost:8008`

### Linting

- Full lint (Python + Rust + mypy + Go): `poetry run ./scripts-dev/lint.sh`
- Quick Python lint only: `poetry run ruff check --quiet synapse tests && poetry run ruff format --check synapse tests`
- Rust lint: `cargo clippy --bins --examples --lib --tests -- -D warnings`

### Testing

- Run all unit tests: `poetry run trial tests`
- Run a specific test: `poetry run trial tests.rest.admin.test_admin.VersionTestCase`
- Parallel tests: `poetry run trial -j4 tests`
- Tests use in-memory SQLite by default; no external services needed for unit tests.

### Key caveats

- After any Rust code change, you must run `poetry install` or `maturin develop` to rebuild the native module. Python hot-reload does not pick up Rust changes.
- `python3-dev` and `libpq-dev` system packages are required to build `psycopg2` from source during `poetry install --extras all`.
- The `poetry.lock` file pins all dependency versions. Use `poetry install` (not `pip install`) to stay consistent with the lockfile.
- The lint script (`scripts-dev/lint.sh`) modifies files in-place to auto-fix style issues. Save your work before running it.

### Docker Compose full stack

A `docker-compose.full.yml` at the repo root runs the complete TextRP dev stack:

| Service | Container | Port | Notes |
|---|---|---|---|
| Synapse (briij) | `workspace-briij-1` | 8008 | Built from `docker/Dockerfile`, uses Postgres + Redis |
| PostgreSQL | `workspace-postgres-1` | 5432 (internal) | `synapse` database, password `change_me` |
| Redis | `workspace-redis-1` | 6379 (internal) | For replication/caching |
| XRPL API | `workspace-textrpv2-api-1` | 3001 | Placeholder - replace with real `textrpv2-api` repo |
| OIDC Provider | `workspace-textrp-connect-1` | 8080 | Placeholder - replace with real `textrp-connect` repo |
| Frontend | `workspace-textrp-mobile-chat-1` | 3000 | Placeholder - replace with real `textrp-mobile-chat` repo |

Start: `docker compose -f docker-compose.full.yml up --build -d`
Stop: `docker compose -f docker-compose.full.yml down`
Logs: `docker compose -f docker-compose.full.yml logs -f briij`

- The Synapse config is at `data/homeserver.yaml` (Postgres-backed, Redis-enabled).
- Register a user: `docker exec workspace-briij-1 register_new_matrix_user http://localhost:8008 -c /data/homeserver.yaml -u USER -p PASS -a`
- The three companion repos (`textrpv2-api`, `textrp-connect`, `textrp-mobile-chat`) do not yet exist in the GitHub org. The compose file uses Node.js placeholder stubs. Replace the `build` contexts when the real repos are created.
- Docker must be installed separately (not included in the update script). Start the daemon with `sudo dockerd` if needed in cloud environments.
