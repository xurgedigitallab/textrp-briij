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
