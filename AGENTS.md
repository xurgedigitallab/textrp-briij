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

A `docker-compose.full.yml` at the repo root runs the complete TextRP dev stack. Clone the companion repos as siblings inside `/workspace` using a `GITHUB_PAT` secret with read access.

| Service | Container | Port | Technology |
|---|---|---|---|
| Synapse (briij) | `workspace-briij-1` | 8008 | Python/Rust homeserver |
| textrpv2-api | `workspace-textrpv2-api-1` | 8080 | AdonisJS 6 (XRPL proxy) |
| textrp-connect | `workspace-textrp-connect-1` | 3000 | Next.js 14 (OIDC/Xaman SSO) |
| textrp-mobile-chat | `workspace-textrp-mobile-chat-1` | 3002 | Next.js 16 (Matrix client) |
| PostgreSQL | `workspace-postgres-1` | 5432 (internal) | Two databases: `synapse` + `textrp_v2` |
| Redis | `workspace-redis-1` | 6379 (internal) | Shared by Synapse + API |

Start: `docker compose -f docker-compose.full.yml up --build -d`
Stop: `docker compose -f docker-compose.full.yml down`
Logs: `docker compose -f docker-compose.full.yml logs -f briij`

- After first start, run API migrations: `docker exec workspace-textrpv2-api-1 node --import=tsx ace.js migration:run`
- Register a Synapse user: `docker exec workspace-briij-1 register_new_matrix_user http://localhost:8008 -c /data/homeserver.yaml -u USER -p PASS -a`
- The Synapse config is at `data/homeserver.yaml` (Postgres-backed, Redis-enabled).
- A shared `ENC_KEY` must match between textrp-connect and textrpv2-api's `JWT_SECRET` / `IDP_JWT_SECRET`. See `DEV-SETUP.md` in textrpv2-api for the full auth wiring guide.
- XRPL WebSocket (`wss://s.altnet.rippletest.net:51233`) may not be reachable in some cloud environments; the API reports `xrpl: down` in health but database/redis are functional.
- Docker must be installed separately (not in the update script). Start the daemon with `sudo dockerd` if needed.
- For Xaman SSO to work end-to-end, set real `XUMM_KEY`/`XUMM_KEY_SECRET` from https://apps.xumm.dev/ in the `.env` file.
