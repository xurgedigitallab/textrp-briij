# AGENTS.md

## Cursor Cloud specific instructions

This is the **Element Synapse** Matrix homeserver (Python 3 + Rust). See `CONTRIBUTING.md` section 4 for full developer setup and section 8 for testing instructions.

### Running the application

1. Generate config: `poetry run python -m synapse.app.homeserver --generate-config --server-name localhost --config-path homeserver.yaml --report-stats=no`
2. Start server: `poetry run python -m synapse.app.homeserver -c homeserver.yaml`
3. The server listens on `http://127.0.0.1:8008` by default.
4. The `register_new_matrix_user` CLI tool does **not** work in local dev mode because the admin API is mounted at `/_briij/admin` but the URL patterns still reference `/_synapse/admin` (path mismatch). Instead, enable registration in `homeserver.yaml` (`enable_registration: true` and `enable_registration_without_verification: true`) and use the Matrix client API directly:
   ```
   curl -X POST http://127.0.0.1:8008/_matrix/client/v3/register \
     -H 'Content-Type: application/json' \
     -d '{"username":"USER","password":"PASS","auth":{"type":"m.login.dummy"}}'
   ```

### Linting

- Full lint (Python + Rust + mypy + Go): `poetry run ./scripts-dev/lint.sh`
- Quick Python lint only: `poetry run ruff check --quiet synapse tests && poetry run ruff format --check synapse tests`
- Rust lint: `cargo clippy --bins --examples --lib --tests -- -D warnings`

### Testing

- Run all unit tests: `poetry run trial tests`
- Run a specific test: `poetry run trial tests.rest.admin.test_admin.VersionTestCase`
- Parallel tests: `poetry run trial -j4 tests`
- Tests use in-memory SQLite by default; no external services needed for unit tests.

### Login rate limiting (429 Too Many Requests)

XRPL wallet login does two POSTs to `/_matrix/client/v3/login` per attempt (challenge then complete). Default `rc_login` limits are strict (`per_second: 0.003`, `burst_count: 5`), so a few retries from the same IP or account can trigger **429 M_LIMIT_EXCEEDED**. For local/dev, relax login rate limits in `homeserver.yaml`:

```yaml
ratelimiting:
  rc_login:
    address:
      per_second: 1
      burst_count: 20
    account:
      per_second: 1
      burst_count: 20
```

Restart Briij after changing config.

### XRPL login flow (Briij vs UI / Xaman)

XRPL wallet login is a **two-step** flow against `POST /_matrix/client/v3/login`. The CLI client (`briij-cli`) implements the flow that works with the server; UI clients (e.g. Xaman) must match the same contract.

**Step 1 – Request challenge (initial request)**  
- Body: `{ "type": "io.briij.login.xrpl", "address": "<XRPL classic address>", "network": "xrpl" | "xahau", "preferred_localpart"?: "<matrix localpart>", "username"?: "<matrix localpart alias>", "display_name"?: "<profile display name>" }`.  
- `preferred_localpart` and `username` are aliases for the requested Matrix localpart. If both are present, they must match after normalization (lowercased/sanitized), otherwise the request is rejected with `M_INVALID_PARAM`.  
- Response: **HTTP 401** with body `{ "session": "<opaque session id>", "challenge": "<string to sign>" }`.  
- The client must treat **401 as success** for this step and parse `session` and `challenge` from the body.

**Step 2 – Complete login**  
- Body must include: `type`, `session`, `address`, `signature`, and optionally `network`.  
- The server accepts **two proof formats**:

  1. **Challenge signing (what briij-cli does)**  
     - Sign the **challenge string** (UTF-8 bytes) with the wallet’s Ed25519 key.  
     - Send the signature as **hex**: `signature: "<hex>"`, and **required** `public_key: "<hex>"` (wallet’s Ed25519 public key, hex).  
     - No submission to the ledger; works with any wallet that can sign arbitrary bytes (e.g. seed in CLI).

  2. **Xaman SignIn transaction**  
     - User signs a **SignIn** pseudo-transaction in Xaman; the backend receives the **signed transaction HEX blob**.  
     - Send that blob as `signature` (no `public_key` needed; the server derives the key from the decoded tx).  
     - The server decodes the blob with the XRPL binary codec. If the codec does **not** know the SignIn type (Xaman-specific), decode fails, the server falls back to requiring `public_key` and treating `signature` as a challenge signature—which then fails if the UI only sent the SignIn blob. So for Xaman-only flow to work, the server must successfully decode the SignIn transaction.

**Common UI issues**

- Treating the first POST as failure because of **401**. The first response is 401 with `session` and `challenge`; do not treat 401 as an error in step 1.  
- **Missing `public_key`** when using challenge signing (e.g. after getting the challenge, signing it in-app and sending only `signature`). The server requires `public_key` for the challenge-signature path.  
- **Requested username already taken** on first wallet login: completion fails with `M_USER_IN_USE` (`User ID already taken.`).  
- **Wrong username for an already-linked wallet**: completion fails with `M_FORBIDDEN` and a message like `This wallet is already linked to @user:server; requested username does not match.`  
- Sending a **SignIn blob** without the server supporting SignIn in the codec: you get “Missing public_key for XRPL login” because decode fails and the server expects challenge signature + public_key.  
- **Rate limiting (429)**: two POSTs per login; relax `rc_login` in `homeserver.yaml` for dev (see “Login rate limiting” above).

Reference implementation: `briij-cli` ([auth.rs](https://github.com/xurgedigitallab/briij-cli) – `request_challenge` then `complete_login` with hex `signature` and `public_key`).

### Using briij-cli with briij-server (current behavior)

Use this section when operating against a briij homeserver that has `xrpl_auth.enabled: true`.

#### Prerequisites

- Build/install `briij-cli` from the `briij-cli` repo.
- Set one wallet secret environment variable:
  - `BRIJJ_XRPL_SEED`, or
  - `XRPL_SECRET_KEY`
- Ensure the homeserver endpoint is reachable (default local dev: `http://127.0.0.1:8008`).

#### Login command

Basic login (autogenerated Matrix localpart):

```bash
export BRIJJ_XRPL_SEED='s...'
briij-cli login-xrpl --homeserver http://127.0.0.1:8008 --network xrpl
```

Login with a requested Matrix localpart:

```bash
export BRIJJ_XRPL_SEED='s...'
briij-cli login-xrpl --homeserver http://127.0.0.1:8008 --network xrpl --username alice_wallet
```

Notes:
- `--network` accepts `xrpl` or `xahau`.
- `--username` is the Matrix **localpart only** (do not include `@` or `:server`).
- On successful login, CLI stores session data under `$BRIIJ_CLI_DATA_DIR` or `~/.config/briij-cli/`.

#### What briij-cli sends to the server

- Step 1 (`POST /_matrix/client/v3/login`):
  - Always sends `type`, `address`, `network`.
  - Sends `preferred_localpart` when `--username` is provided.
  - Expects **HTTP 401** with `{session, challenge}` and treats that as success for challenge issuance.
- Step 2 (`POST /_matrix/client/v3/login`):
  - Sends `type`, `session`, `address`, `signature`, `public_key`, and requests a refresh token.

#### Expected error behavior

- **Requested username already exists**:
  - Server returns `M_USER_IN_USE` (typically `HTTP 400`).
  - CLI displays a message like `login failed with HTTP 400 Bad Request (M_USER_IN_USE): User ID already taken.`
- **Wallet already linked to another localpart**:
  - Server returns `M_FORBIDDEN` (`HTTP 403`) with a message indicating the linked MXID.
  - CLI displays the errcode and server message, for example:
    - `login failed with HTTP 403 Forbidden (M_FORBIDDEN): This wallet is already linked to @user:server; requested username does not match.`
- **Rate limiting**:
  - Two login POSTs happen per attempt; repeated retries can return `429 M_LIMIT_EXCEEDED`.
  - For local/dev, relax `ratelimiting.rc_login` as shown in this file and restart briij.

### Key caveats

- After any Rust code change, you must run `poetry install` or `maturin develop` to rebuild the native module. Python hot-reload does not pick up Rust changes.
- `python3-dev` and `libpq-dev` system packages are required to build `psycopg2` from source during `poetry install --extras all`.
- The `poetry.lock` file pins all dependency versions. Use `poetry install` (not `pip install`) to stay consistent with the lockfile.
- The lint script (`scripts-dev/lint.sh`) modifies files in-place to auto-fix style issues. Save your work before running it.

### Docker Compose full stack

A `docker-compose.full.yml` at the repo root runs the complete TextRP dev stack. The three companion repos are private; clone them using a `GITHUB_PAT` secret with read access to the `xurgedigitallab` org. **All companion repos must be on the `development` branch.**

```sh
cd /workspace
git clone https://x-access-token:${GITHUB_PAT}@github.com/xurgedigitallab/textrpv2-api.git && git -C textrpv2-api checkout development
git clone https://x-access-token:${GITHUB_PAT}@github.com/xurgedigitallab/textrp-connect.git && git -C textrp-connect checkout development
git clone https://x-access-token:${GITHUB_PAT}@github.com/xurgedigitallab/textrp-mobile-chat.git && git -C textrp-mobile-chat checkout development
git clone https://github.com/xurgedigitallab/briij-js-sdk.git  # public, default branch: develop
```

The `briij-js-sdk` (`@textrp/briij-js-sdk`, forked from `matrix-js-sdk`) lives at `/workspace/briij-js-sdk` on the `develop` branch. It uses **pnpm** (`pnpm-lock.yaml`). Install with `cd briij-js-sdk && pnpm install`. This SDK is developed in parallel with the briij homeserver -- changes to Synapse APIs or custom Matrix events should be reflected here.

| Service | Container | Port | Technology |
|---|---|---|---|
| Synapse (briij) | `workspace-briij-1` | 8008 | Python/Rust homeserver |
| textrpv2-api | `workspace-textrpv2-api-1` | 8080 | AdonisJS 6 / `Dockerfile.dev` |
| textrp-connect | `workspace-textrp-connect-1` | 3000 | Next.js 14 / `dockerfile` |
| textrp-mobile-chat | `workspace-textrp-mobile-chat-1` | 3002 | Next.js 16 / `Dockerfile` (internal port 3001) |
| PostgreSQL | `workspace-postgres-1` | 5432 (internal) | Two databases: `synapse` + `textrp_v2` |
| Redis | `workspace-redis-1` | 6379 (internal) | Shared by Synapse + API |

Start: `docker compose -f docker-compose.full.yml up --build -d`
Stop: `docker compose -f docker-compose.full.yml down`
Logs: `docker compose -f docker-compose.full.yml logs -f briij`

#### Required secrets (Cursor Cloud Secrets panel)

| Secret | Purpose |
|---|---|
| `GITHUB_PAT` | Fine-grained PAT with read access to the 3 private repos |
| `XUMM_KEY` | Xaman API key from https://apps.xumm.dev/ |
| `XUMM_KEY_SECRET` | Xaman API secret |
| `IDP_CLIENT_ID` | OAuth client ID created in textrp-connect Dev Console |
| `IDP_CLIENT_SECRET` | OAuth client secret from Dev Console |

#### Post-startup steps

1. Run API migrations: `docker exec workspace-textrpv2-api-1 node --import=tsx ace.js migration:run`
2. Register a Synapse user: `docker exec workspace-briij-1 register_new_matrix_user http://localhost:8008 -c /data/homeserver.yaml -u USER -p PASS -a`
3. For full SSO: log into textrp-connect at `http://localhost:3000`, create an OAuth client in the Dev Console with redirect `http://localhost:8080/v2/sso/callback`, then set the resulting `IDP_CLIENT_ID`/`IDP_CLIENT_SECRET`.

#### Key caveats (Docker stack)

- The Synapse config is at `data/homeserver.yaml` (Postgres-backed, Redis-enabled). If XRPL wallet login returns 429, add the `ratelimiting.rc_login` block from the "Login rate limiting" section above to that file and restart the briij container.
- A shared `ENC_KEY` must match between textrp-connect and textrpv2-api's `JWT_SECRET` / `IDP_JWT_SECRET`. See `DEV-SETUP.md` in textrpv2-api for the full auth wiring guide.
- `NEXT_PUBLIC_*` env vars in textrp-mobile-chat are baked at Docker build time (Next.js). The compose file passes them as build args; changes require `docker compose build textrp-mobile-chat`.
- The mobile-chat Next.js server rewrites `/wallet-api/*` to textrp-connect. The build arg `NEXT_PUBLIC_WALLET_API_URL` must use the Docker service name (`http://textrp-connect:3000`), not `localhost`.
- XRPL WebSocket may not be reachable in cloud environments; the API reports `xrpl: down` but database/redis are functional.
- Docker must be installed separately (not in the update script). Start the daemon with `sudo dockerd` if needed in cloud environments.
